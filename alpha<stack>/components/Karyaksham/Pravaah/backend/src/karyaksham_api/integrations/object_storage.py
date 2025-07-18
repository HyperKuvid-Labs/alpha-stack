import logging
from typing import AsyncIterator, Optional
from aiobotocore.session import get_session
from botocore.exceptions import ClientError

from karyaksham_api.core.config import settings

logger = logging.getLogger(__name__)

class ObjectStorageError(Exception):
    """Custom exception for object storage related errors."""
    pass

class ObjectStorageClient:
    """
    Client for interacting with S3-compatible object storage (AWS S3, MinIO, etc.).
    Designed for asynchronous operations using aiobotocore.
    """
    def __init__(self):
        self.session = get_session()
        self.bucket_name: str = settings.OBJECT_STORAGE_BUCKET
        self.endpoint_url: Optional[str] = settings.OBJECT_STORAGE_ENDPOINT
        self.aws_access_key_id: str = settings.OBJECT_STORAGE_ACCESS_KEY
        self.aws_secret_access_key: str = settings.OBJECT_STORAGE_SECRET_KEY
        # Safely get AWS_REGION from settings, defaulting if not found.
        # This allows MinIO to still work without an explicit region in .env.
        self.aws_region: str = getattr(settings, "AWS_REGION", "us-east-1")

        # Determine if SSL should be used. For MinIO local development, it might be http.
        # For production AWS S3, it will always be https.
        # We explicitly check for 'http://' at the start to disable SSL.
        self.use_ssl: bool = not (self.endpoint_url and self.endpoint_url.lower().startswith("http://"))

        self._s3_client = None # To hold the actual aiobotocore client instance


    async def connect(self):
        """
        Establishes connection to the S3 client.
        This method should be called once during application startup (e.g., FastAPI's on_event("startup")).
        """
        if self._s3_client is None:
            logger.info(f"Connecting to object storage at {self.endpoint_url or 'default AWS S3 endpoint'}...")
            try:
                self._s3_client = self.session.create_client(
                    "s3",
                    region_name=self.aws_region,
                    endpoint_url=self.endpoint_url,
                    aws_access_key_id=self.aws_access_key_id,
                    aws_secret_access_key=self.aws_secret_access_key,
                    use_ssl=self.use_ssl
                )
                # Enter the async context manager for the client to properly initialize it
                await self._s3_client.__aenter__()
                logger.info("Successfully connected to object storage.")
            except Exception as e:
                logger.error(f"Failed to connect to object storage: {e}")
                self._s3_client = None # Ensure client is None if connection fails
                raise ObjectStorageError(f"Failed to connect to object storage: {e}") from e
        else:
            logger.debug("Object storage client already connected.")

    async def disconnect(self):
        """
        Closes the S3 client connection.
        This method should be called once during application shutdown (e.g., FastAPI's on_event("shutdown")).
        """
        if self._s3_client:
            logger.info("Disconnecting from object storage...")
            try:
                # Exit the async context manager for the client to properly close it
                await self._s3_client.__aexit__(None, None, None)
                self._s3_client = None
                logger.info("Successfully disconnected from object storage.")
            except Exception as e:
                logger.error(f"Error disconnecting from object storage: {e}")
                raise ObjectStorageError(f"Error disconnecting from object storage: {e}") from e
        else:
            logger.debug("Object storage client not connected.")

    def _get_s3_client(self):
        """Helper method to retrieve the initialized S3 client, raising an error if not connected."""
        if self._s3_client is None:
            raise ObjectStorageError("Object storage client is not connected. Call .connect() first.")
        return self._s3_client

    async def generate_presigned_upload_url(self, file_key: str, expiration: int = 3600) -> str:
        """
        Generates a pre-signed URL for a client (e.g., web browser) to upload a file directly
        to the object storage using an HTTP PUT request.

        Args:
            file_key: The unique key (path) of the file in the bucket (e.g., 'user_id/uploads/my_file.csv').
            expiration: The duration in seconds for which the generated URL is valid.

        Returns:
            The pre-signed URL string.

        Raises:
            ObjectStorageError: If there's an issue generating the pre-signed URL.
        """
        client = self._get_s3_client()
        try:
            url = await client.generate_presigned_url(
                ClientMethod='put_object',
                Params={'Bucket': self.bucket_name, 'Key': file_key},
                ExpiresIn=expiration
            )
            logger.info(f"Generated presigned upload URL for {file_key} (expires in {expiration}s).")
            return url
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code")
            logger.error(f"Error generating presigned upload URL for {file_key}: {error_code} - {e}")
            raise ObjectStorageError(f"Could not generate presigned upload URL: {error_code}") from e
        except Exception as e:
            logger.exception(f"Unexpected error generating presigned upload URL for {file_key}.")
            raise ObjectStorageError("An unexpected error occurred generating presigned URL.") from e

    async def generate_presigned_download_url(self, file_key: str, expiration: int = 3600) -> str:
        """
        Generates a pre-signed URL for a client (e.g., web browser) to download a file directly
        from the object storage using an HTTP GET request.

        Args:
            file_key: The unique key (path) of the file in the bucket (e.g., 'user_id/processed/result.parquet').
            expiration: The duration in seconds for which the generated URL is valid.

        Returns:
            The pre-signed URL string.

        Raises:
            ObjectStorageError: If there's an issue generating the pre-signed URL.
        """
        client = self._get_s3_client()
        try:
            url = await client.generate_presigned_url(
                ClientMethod='get_object',
                Params={'Bucket': self.bucket_name, 'Key': file_key},
                ExpiresIn=expiration
            )
            logger.info(f"Generated presigned download URL for {file_key} (expires in {expiration}s).")
            return url
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code")
            logger.error(f"Error generating presigned download URL for {file_key}: {error_code} - {e}")
            raise ObjectStorageError(f"Could not generate presigned download URL: {error_code}") from e
        except Exception as e:
            logger.exception(f"Unexpected error generating presigned download URL for {file_key}.")
            raise ObjectStorageError("An unexpected error occurred generating presigned URL.") from e

    async def upload_file_content(self, file_key: str, content: bytes, content_type: str = 'application/octet-stream') -> None:
        """
        Uploads file content directly from the backend application to the object storage.
        This method is suitable for smaller files or when the backend itself generates and
        needs to store data (e.g., job logs, small results). For large user uploads,
        generating pre-signed URLs for direct client-to-storage upload is generally preferred.

        Args:
            file_key: The unique key (path) of the file in the bucket.
            content: The binary content of the file (as bytes).
            content_type: The MIME type of the file (e.g., 'text/csv', 'application/json').

        Raises:
            ObjectStorageError: If the upload operation fails.
        """
        client = self._get_s3_client()
        try:
            await client.put_object(Bucket=self.bucket_name, Key=file_key, Body=content, ContentType=content_type)
            logger.info(f"Uploaded file content to {file_key}.")
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code")
            logger.error(f"Error uploading file content to {file_key}: {error_code} - {e}")
            raise ObjectStorageError(f"Could not upload file content: {error_code}") from e
        except Exception as e:
            logger.exception(f"Unexpected error uploading file content to {file_key}.")
            raise ObjectStorageError("An unexpected error occurred during file upload.") from e

    async def download_file_stream(self, file_key: str) -> AsyncIterator[bytes]:
        """
        Downloads a file from object storage as an asynchronous stream.
        This method is ideal for handling large files efficiently by yielding chunks of bytes,
        avoiding loading the entire file into memory at once.

        Args:
            file_key: The unique key (path) of the file in the bucket.

        Yields:
            Chunks of bytes from the file.

        Raises:
            ObjectStorageError: If the download fails or the file is not found.
        """
        client = self._get_s3_client()
        try:
            response = await client.get_object(Bucket=self.bucket_name, Key=file_key)
            # The 'Body' of the S3 response is an aiohttp.StreamReader, which is an async context manager
            async with response['Body'] as stream:
                async for chunk in stream.iter_chunks():
                    yield chunk
            logger.info(f"Streamed download for {file_key} completed.")
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code")
            if error_code == 'NoSuchKey':
                logger.warning(f"File not found in object storage: {file_key}")
                raise ObjectStorageError(f"File not found: {file_key}") from e
            logger.error(f"Error downloading file {file_key}: {error_code} - {e}")
            raise ObjectStorageError(f"Could not download file: {error_code}") from e
        except Exception as e:
            logger.exception(f"Unexpected error streaming file from object storage: {file_key}.")
            raise ObjectStorageError("An unexpected error occurred during file download stream.") from e

    async def delete_file(self, file_key: str) -> None:
        """
        Deletes a file from the object storage.

        Args:
            file_key: The unique key (path) of the file to delete.

        Raises:
            ObjectStorageError: If the deletion operation fails.
        """
        client = self._get_s3_client()
        try:
            await client.delete_object(Bucket=self.bucket_name, Key=file_key)
            logger.info(f"Deleted file {file_key} from object storage.")
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code")
            logger.error(f"Error deleting file {file_key}: {error_code} - {e}")
            raise ObjectStorageError(f"Could not delete file: {error_code}") from e
        except Exception as e:
            logger.exception(f"Unexpected error deleting file {file_key}.")
            raise ObjectStorageError("An unexpected error occurred during file deletion.") from e