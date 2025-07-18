import uuid
from typing import List, Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from karyaksham_api.api.deps import get_db, get_current_active_user, get_object_storage_client
from karyaksham_api.core.config import settings
from karyaksham_api.crud.crud_job import job as crud_job
from karyaksham_api.db.models.user import User
from karyaksham_api.integrations.object_storage import ObjectStorageClient
from karyaksham_api.schemas.job import JobCreate, JobResponse, JobStatus, JobUpdate, JobDownloadUrlResponse
from karyaksham_workers.tasks.processing import process_file_task # Ensure this path is correct based on folder structure

router = APIRouter()

@router.post("/", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
async def create_job(
    job_in: JobCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    obj_storage: Annotated[ObjectStorageClient, Depends(get_object_storage_client)]
) -> JobResponse:
    """
    Initiates a new processing job.
    Generates a unique ID and a presigned URL for file upload.
    The job is initially set to PENDING_UPLOAD status.
    """
    job_id = uuid.uuid4()
    original_filename = job_in.original_filename
    
    # Define input and output file keys for object storage
    input_file_key = f"jobs/{current_user.id}/{job_id}/input/{original_filename}"
    
    # Derive an output filename, possibly based on requested output_format
    # This can be made more robust, e.g., by checking allowed formats.
    # For now, it simply replaces the extension or adds one.
    output_filename_base = original_filename.rsplit('.', 1)[0] if '.' in original_filename else original_filename
    output_extension = job_in.processing_parameters.output_format.lower() \
        if job_in.processing_parameters and job_in.processing_parameters.output_format else "out"
    output_file_key = f"jobs/{current_user.id}/{job_id}/output/{output_filename_base}.{output_extension}"

    # Generate presigned upload URL
    try:
        presigned_upload_url = await obj_storage.generate_presigned_upload_url(
            bucket_name=settings.OBJECT_STORAGE_BUCKET,
            object_name=input_file_key,
            expires_in_seconds=settings.PRESIGNED_URL_EXPIRY_SECONDS
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not generate presigned upload URL: {e}"
        )

    # Create job in database with PENDING_UPLOAD status
    job_data_for_db = JobUpdate(
        id=job_id,
        user_id=current_user.id,
        status=JobStatus.PENDING_UPLOAD,
        input_file_key=input_file_key,
        output_file_key=output_file_key,
        original_filename=original_filename,
        processing_parameters=job_in.processing_parameters
    )
    
    job = crud_job.create_with_owner(db=db, obj_in=job_data_for_db, owner_id=current_user.id)
    
    job_response = JobResponse.from_orm(job)
    job_response.presigned_upload_url = presigned_upload_url
    return job_response

@router.put("/{job_id}/confirm_upload", response_model=JobResponse)
async def confirm_job_upload(
    job_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)]
) -> JobResponse:
    """
    Confirms that the input file has been uploaded to object storage and
    dispatches the processing task to Celery.
    """
    job = crud_job.get(db=db, id=job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found."
        )
    if job.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this job."
        )
    if job.status != JobStatus.PENDING_UPLOAD:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Job is not in '{JobStatus.PENDING_UPLOAD.value}' status. Current status: {job.status.value}"
        )

    # Update job status to QUEUED
    updated_job = crud_job.update(
        db=db,
        db_obj=job,
        obj_in={"status": JobStatus.QUEUED}
    )

    # Dispatch Celery task for processing
    try:
        # Celery tasks usually require serializable arguments. UUID needs to be converted to str.
        process_file_task.delay(str(updated_job.id))
    except Exception as e:
        # If task dispatch fails, update job status to FAILED and log error
        crud_job.update(
            db=db,
            db_obj=job,
            obj_in={"status": JobStatus.FAILED, "error_message": f"Task dispatch failed: {e}"}
        )
        db.commit() # Ensure the status change is committed immediately
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to dispatch processing task: {e}"
        )

    return updated_job

@router.get("/", response_model=List[JobResponse])
def read_jobs(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    skip: int = 0,
    limit: int = 100
) -> List[JobResponse]:
    """
    Retrieve a list of jobs for the current authenticated user.
    Supports pagination.
    """
    jobs = crud_job.get_multi_by_owner(db=db, owner_id=current_user.id, skip=skip, limit=limit)
    return jobs

@router.get("/{job_id}", response_model=JobResponse)
def read_job_by_id(
    job_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)]
) -> JobResponse:
    """
    Retrieve a specific job by its ID, ensuring it belongs to the current user.
    """
    job = crud_job.get(db=db, id=job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found."
        )
    if job.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this job."
        )
    return job

@router.get("/{job_id}/download_url", response_model=JobDownloadUrlResponse)
async def get_job_download_url(
    job_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    obj_storage: Annotated[ObjectStorageClient, Depends(get_object_storage_client)]
) -> JobDownloadUrlResponse:
    """
    Generates a presigned download URL for the processed output file of a completed job.
    """
    job = crud_job.get(db=db, id=job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found."
        )
    if job.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this job."
        )
    if job.status != JobStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Job is not completed. Current status: {job.status.value}. Cannot generate download URL."
        )
    if not job.output_file_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Output file key not found for this job. Processing might have failed or not produced output."
        )

    try:
        presigned_download_url = await obj_storage.generate_presigned_download_url(
            bucket_name=settings.OBJECT_STORAGE_BUCKET,
            object_name=job.output_file_key,
            expires_in_seconds=settings.PRESIGNED_URL_EXPIRY_SECONDS
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not generate presigned download URL: {e}"
        )
    
    return JobDownloadUrlResponse(download_url=presigned_download_url)


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_job(
    job_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    obj_storage: Annotated[ObjectStorageClient, Depends(get_object_storage_client)]
):
    """
    Deletes a processing job and its associated files from object storage.
    """
    job = crud_job.get(db=db, id=job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found."
        )
    if job.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this job."
        )

    # Prevent deletion of jobs that are currently running to avoid data inconsistency.
    if job.status == JobStatus.RUNNING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete a job that is currently running. Please wait for it to complete or fail."
        )

    # Attempt to delete associated files from object storage
    # Log errors but do not necessarily block DB deletion, as files might be gone already or irrecoverable.
    # The job record in DB is the source of truth for its metadata.
    if job.input_file_key:
        try:
            await obj_storage.delete_object(settings.OBJECT_STORAGE_BUCKET, job.input_file_key)
        except Exception as e:
            # In a real app, use a proper logger here
            print(f"WARNING: Could not delete input file '{job.input_file_key}' for job {job_id}: {e}")
            # Optionally, mark for garbage collection or raise a specific warning in the response

    if job.output_file_key:
        try:
            await obj_storage.delete_object(settings.OBJECT_STORAGE_BUCKET, job.output_file_key)
        except Exception as e:
            print(f"WARNING: Could not delete output file '{job.output_file_key}' for job {job_id}: {e}")

    # Finally, remove the job record from the database
    crud_job.remove(db=db, id=job_id)
    
    # Return 204 No Content for successful deletion
    return {}