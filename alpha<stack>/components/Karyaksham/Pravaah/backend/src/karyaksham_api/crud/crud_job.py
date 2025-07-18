```python
from typing import List, Optional, Any
from sqlalchemy.orm import Session
from sqlalchemy import select

from ..db.models.job import Job
from ..schemas.job import JobCreate, JobUpdate, JobStatus
from .base import CRUDBase


class CRUDJob(CRUDBase[Job, JobCreate, JobUpdate]):
    """
    CRUD operations for the Job model.
    Inherits common methods from CRUDBase and adds job-specific functionalities.
    """

    def create_with_owner(self, db: Session, *, obj_in: JobCreate, owner_id: int) -> Job:
        """
        Creates a new Job instance, associating it with a specific owner.
        """
        # Pydantic v2 uses model_dump() instead of dict()
        obj_in_data = obj_in.model_dump()
        
        db_obj = self.model(**obj_in_data, owner_id=owner_id)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def get_multi_by_owner(
        self, db: Session, *, owner_id: int, skip: int = 0, limit: int = 100
    ) -> List[Job]:
        """
        Retrieves multiple Job instances belonging to a specific owner.
        """
        stmt = (
            select(self.model)
            .where(self.model.owner_id == owner_id)
            .offset(skip)
            .limit(limit)
        )
        return db.scalars(stmt).all()

    def get_by_id_and_owner(self, db: Session, *, job_id: int, owner_id: int) -> Optional[Job]:
        """
        Retrieves a single Job instance by its ID, ensuring it belongs to the specified owner.
        """
        stmt = (
            select(self.model)
            .where(self.model.id == job_id, self.model.owner_id == owner_id)
        )
        return db.scalars(stmt).first()

    def update_status(
        self, db: Session, *, job: Job, new_status: JobStatus, output_path: Optional[str] = None
    ) -> Job:
        """
        Updates the status of a job and optionally sets its output path.
        Accepts a Job object directly, assuming it's already retrieved from DB.
        """
        job.status = new_status
        if output_path is not None:
            job.output_path = output_path
        
        db.add(job) # Ensure the object is tracked by the session
        db.commit()
        db.refresh(job)
        return job

    def remove_by_owner(self, db: Session, *, job_id: int, owner_id: int) -> Optional[Job]:
        """
        Removes a job by its ID, ensuring it belongs to the specified owner.
        Returns the removed job, or None if not found or not owned by the user.
        """
        job = self.get_by_id_and_owner(db, job_id=job_id, owner_id=owner_id)
        if job:
            db.delete(job)
            db.commit()
        return job


# Instantiate the CRUD object for the Job model, ready for import
job = CRUDJob(Job)
```