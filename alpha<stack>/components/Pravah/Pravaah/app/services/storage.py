```python
from abc import ABC, abstractmethod
from typing import AsyncIterator, Optional
from pathlib import Path
import logging

import aiobotocore.session
from botocore.exceptions import ClientError
from anyio import Path as AsyncPath, to_thread

from config.settings import AppSettings

logger = logging.getLogger(__name__)

# --- Custom Exceptions ---

class FileStorageError(Exception):
    """Base exception for file storage operations."""
    pass

class FileStorageNotFoundError(FileStorageError):
    """Exception raised when a requested file is not found."""
    pass

# --- Abstract Base Class for Storage Client ---

class IStorageClient(ABC):
    """
    Abstract base class defining the interface for file storage operations.
    All methods are asynchronous to align with the FastAPI application.
    """

    @abstractmethod
    async def upload_file(self, local_file_path: Path, dest_path: str) -> None:
        """
        Uploads a file from the local filesystem to the storage backend.

        Args:
            local_file_path: The path to the file on the local filesystem.
            dest_path: The destination path/key in the storage backend.
        """
        pass

    @abstractmethod
    async def download_file(self, src_path: str, local_file_path: Path) -> None:
        """
        Downloads a file from the storage backend to the local filesystem.

        Args:
            src_path: The source path/key in the storage backend.
            local_file_path: The path where the file should be saved locally.
        """
        pass

    @abstractmethod
    async def file_exists(self, path: str) -> bool:
        """
        Checks if a file exists at the given path in the storage backend.

        Args:
            path: The path/key to check.

        Returns:
            True if the file exists, False otherwise.
        """
        pass

    @abstractmethod
    async def delete_file(self, path: str) -> None:
        """
        Deletes a file from the storage backend.

        Args:
            path: The path/key of the file to delete.
        """
        pass

    @abstractmethod
    async def list_files(self, prefix: str = "", recursive: bool = False) -> AsyncIterator[str]:
        """
        Lists files in the storage backend under a given prefix/directory.

        Args:
            prefix: The directory or key prefix to list.
            recursive: If True, lists files recursively in subdirectories.

        Yields:
            The path/key of each file.
        """
        pass

    @abstractmethod
    async def get_presigned_url(self, path: str, expiration: int = 3600) -> Optional[str]:
        """
        Generates a presigned URL for direct access to a file.
        Only applicable for S3-compatible storage.

        Args:
            path: The path/key of the file.
            expiration: The expiration time in seconds for the URL.

        Returns:
            A presigned URL string, or None if not supported by the storage type.
        """
        pass

# --- Local Filesystem Storage Client ---

class LocalStorageClient(IStorageClient):
    """
    Implements IStorageClient for local filesystem operations.
    All operations are wrapped in `anyio.to_thread` to prevent blocking the event loop.
    """
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir.resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"LocalStorageClient initialized with base directory: {self.base_dir}")

    async def _get_abs_path(self, relative_path: str) -> AsyncPath:
        """
        Converts a relative path string to an absolute AsyncPath within the base directory.
        Performs path sanitization to prevent directory traversal attacks.
        """
        # Strip leading slashes to ensure it's treated as relative to self.base_dir
        clean_relative_path_str = relative_path.lstrip('/')
        
        # Construct the full path within the base directory
        full_path = self.base_dir / clean_relative_path_str
        
        # Resolve the path to handle '..' and get its canonical form
        resolved_full_path = await to_thread(Path.resolve, full_path)
        
        # Crucially, verify that the resolved path is still within the base directory.
        # This prevents 'directory traversal' attacks where 'relative_path' might be "../../../etc/passwd"
        resolved_base_dir = await to_thread(Path.resolve, self.base_dir)
        
        try:
            await to_thread(resolved_full_path.relative_to, resolved_base_dir)
        except ValueError:
            # Path escapes the base directory
            raise ValueError(f"Attempted to access path '{relative_path}' outside base directory '{self.base_dir}'.")
            
        return AsyncPath(resolved_full_path) # Convert back to AsyncPath for subsequent operations

    async def upload_file(self, local_file_path: Path, dest_path: str) -> None:
        dest_abs_path = await self._get_abs_path(dest_path)
        await to_thread(dest_abs_path.parent.mkdir, parents=True, exist_ok=True)
        try:
            logger.debug(f"Uploading local://{local_file_path} to local://{dest_abs_path}")
            # Use read_bytes/write_bytes for simplicity; for very large files,
            # streaming with chunks would be more memory efficient.
            content = await to_thread(local_file_path.read_bytes)
            await to_thread(dest_abs_path.write_bytes, content)
            logger.info(f"Successfully uploaded {local_file_path} to {dest_abs_path}")
        except Exception as e:
            logger.error(f"Failed to upload file {local_file_path} to {dest_abs_path}: {e}", exc_info=True)
            raise FileStorageError(f"Failed to upload file to local storage: {e}") from e

    async def download_file(self, src_path: str, local_file_path: Path) -> None:
        src_abs_path = await self._get_abs_path(src_path)
        await to_thread(local_file_path.parent.mkdir, parents=True, exist_ok=True)
        try:
            logger.debug(f"Downloading local://{src_abs_path} to local://{local_file_path}")
            content = await to_thread(src_abs_path.read_bytes)
            await to_thread(local_file_path.write_bytes, content)
            logger.info(f"Successfully downloaded {src_abs_path} to {local_file_path}")
        except FileNotFoundError as e:
            logger.warning(f"File not found during download: {src_abs_path}")
            raise FileStorageNotFoundError(f"File not found in local storage: {src_abs_path}") from e
        except Exception as e:
            logger.error(f"Failed to download file {src_path} to {local_file_path}: {e}", exc_info=True)
            raise FileStorageError(f"Failed to download file from local storage: {e}") from e

    async def file_exists(self, path: str) -> bool:
        try:
            abs_path = await self._get_abs_path(path)
            return await to_thread(abs_path.is_file)
        except ValueError: # Path traversal attempt
            return False
        except Exception as e:
            logger.error(f"Failed to check existence of local file {path}: {e}", exc_info=True)
            raise FileStorageError(f"Failed to check file existence in local storage: {e}") from e

    async def delete_file(self, path: str) -> None:
        try:
            abs_path = await self._get_abs_path(path)
            if await to_thread(abs_path.is_file):
                logger.debug(f"Deleting local://{abs_path}")
                await to_thread(abs_path.unlink)
                logger.info(f"Successfully deleted local file: {abs_path}")
            else:
                logger.warning(f"Attempted to delete non-existent or non-file path: {abs_path}")
        except FileNotFoundError:
            logger.warning(f"Attempted to delete non-existent local file: {path}")
        except Exception as e:
            logger.error(f"Failed to delete local file {path}: {e}", exc_info=True)
            raise FileStorageError(f"Failed to delete file from local storage: {e}") from e

    async def list_files(self, prefix: str = "", recursive: bool = False) -> AsyncIterator[str]:
        try:
            target_dir = await self._get_abs_path(prefix)
            if not await to_thread(target_dir.exists):
                logger.warning(f"List files target does not exist: {target_dir}")
                return # No files to yield if path does not exist
            
            if await to_thread(target_dir.is_file):
                # If the prefix itself is a file, yield it directly
                yield (await to_thread(target_dir.relative_to, self.base_dir)).as_posix()
                return

            glob_pattern = "**/*" if recursive else "*"
            async for p in AsyncPath(target_dir).glob(glob_pattern):
                if await to_thread(p.is_file):
                    yield (await to_thread(p.relative_to, self.base_dir)).as_posix()
        except ValueError as e: # Catch path traversal
            logger.error(f"Path traversal detected during list_files: {e}")
            raise FileStorageError(f"Invalid path for list operation: {e}") from e
        except Exception as e:
            logger.error(f"Failed to list files in local storage with prefix '{prefix}': {e}", exc_info=True)
            raise FileStorageError(f"Failed to list files from local storage: {e}") from e

    async def get_presigned_url(self, path: str, expiration: int = 3600) -> Optional[str]:
        logger.debug("Presigned URLs are not supported for local storage.")
        return None

# --- S3 Compatible Storage Client ---

class S3StorageClient(IStorageClient):
    """
    Implements IStorageClient for S3-compatible object storage operations
    using aiobotocore for asynchronous interactions.
    """
    def __init__(self, bucket_name: str, aws_access_key_id: str, aws_secret_access_key: str, endpoint_url: Optional[str] = None):
        self.bucket_name = bucket_name
        self.aws_access_key_id = aws_access_key_id
        self.aws_secret_access_key = aws_secret_access_key
        self.endpoint_url = endpoint_url
        self._session = aiobotocore.session.get_session()
        logger.info(f"S3StorageClient initialized for bucket: {self.bucket_name}, endpoint: {self.endpoint_url or 'AWS S3'}")

    async def _get_client(self):
        """Creates an asynchronous S3 client."""
        return self._session.create_client(
            "s3",
            aws_access_key_id=self.aws_access_key_id,
            aws_secret_access_key=self.aws_secret_access_key,
            endpoint_url=self.endpoint_url
        )

    async def upload_file(self, local_file_path: Path, dest_path: str) -> None:
        try:
            async with self._get_client() as client:
                logger.debug(f"Uploading local://{local_file_path} to s3://{self.bucket_name}/{dest_path}")
                # aiobotocore's upload_file handles opening the file itself.
                await client.upload_file(str(local_file_path), self.bucket_name, dest_path)
                logger.info(f"Successfully uploaded {local_file_path} to s3://{self.bucket_name}/{dest_path}")
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code")
            logger.error(f"S3 ClientError during upload of {local_file_path} to {dest_path}: {error_code} - {e}", exc_info=True)
            raise FileStorageError(f"Failed to upload file to S3: {error_code}") from e
        except Exception as e:
            logger.error(f"Failed to upload file {local_file_path} to {dest_path}: {e}", exc_info=True)
            raise FileStorageError(f"Failed to upload file to S3: {e}") from e

    async def download_file(self, src_path: str, local_file_path: Path) -> None:
        await to_thread(local_file_path.parent.mkdir, parents=True, exist_ok=True)
        try:
            async with self._get_client() as client:
                logger.debug(f"Downloading s3://{self.bucket_name}/{src_path} to local://{local_file_path}")
                # aiobotocore's download_file handles opening the file itself.
                await client.download_file(self.bucket_name, src_path, str(local_file_path))
                logger.info(f"Successfully downloaded s3://{self.bucket_name}/{src_path} to {local_file_path}")
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code")
            if error_code == '404' or error_code == 'NoSuchKey':
                logger.warning(f"S3 file not found during download: {src_path}")
                raise FileStorageNotFoundError(f"File not found in S3: {src_path}") from e
            logger.error(f"S3 ClientError during download of {src_path} to {local_file_path}: {error_code} - {e}", exc_info=True)
            raise FileStorageError(f"Failed to download file from S3: {error_code}") from e
        except Exception as e:
            logger.error(f"Failed to download file {src_path} to {local_file_path}: {e}", exc_info=True)
            raise FileStorageError(f"Failed to download file from S3: {e}") from e

    async def file_exists(self, path: str) -> bool:
        try:
            async with self._get_client() as client:
                await client.head_object(Bucket=self.bucket_name, Key=path)
            return True
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code")
            if error_code == '404' or error_code == 'NoSuchKey':
                return False
            # Re-raise for other errors (e.g., permissions)
            logger.error(f"S3 ClientError checking existence of {path}: {error_code} - {e}", exc_info=True)
            raise FileStorageError(f"Failed to check file existence in S3: {error_code}") from e
        except Exception as e:
            logger.error(f"Failed to check existence of S3 file {path}: {e}", exc_info=True)
            raise FileStorageError(f"Failed to check file existence in S3: {e}") from e

    async def delete_file(self, path: str) -> None:
        try:
            async with self._get_client() as client:
                logger.debug(f"Deleting s3://{self.bucket_name}/{path}")
                await client.delete_object(Bucket=self.bucket_name, Key=path)
                logger.info(f"Successfully deleted S3 object: {path}")
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code")
            # S3 delete_object generally returns 204 even if object doesn't exist.
            # Only critical client errors should be re-raised here.
            logger.warning(f"S3 ClientError during deletion of {path}: {error_code} - {e}", exc_info=True)
            raise FileStorageError(f"Failed to delete file from S3: {error_code}") from e
        except Exception as e:
            logger.error(f"Failed to delete S3 file {path}: {e}", exc_info=True)
            raise FileStorageError(f"Failed to delete file from S3: {e}") from e

    async def list_files(self, prefix: str = "", recursive: bool = False) -> AsyncIterator[str]:
        try:
            async with self._get_client() as client:
                paginator = client.get_paginator('list_objects_v2')
                delimiter = '' if recursive else '/' # S3 uses delimiter to simulate folders
                
                async for page in paginator.paginate(Bucket=self.bucket_name, Prefix=prefix, Delimiter=delimiter):
                    # Yield objects (files)
                    for obj in page.get('Contents', []):
                        if not obj['Key'].endswith('/'): # Ensure we only yield file keys, not directory placeholders
                            yield obj['Key']
                    
                    # If not recursive, and if common prefixes are part of the desired output,
                    # you'd yield them here. For a function specifically named `list_files`,
                    # we typically only yield actual file keys.
                    # For example, if you wanted to list "folders" too:
                    # for common_prefix in page.get('CommonPrefixes', []):
                    #     yield common_prefix['Prefix']
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code")
            logger.error(f"S3 ClientError listing files with prefix '{prefix}': {error_code} - {e}", exc_info=True)
            raise FileStorageError(f"Failed to list files from S3: {error_code}") from e
        except Exception as e:
            logger.error(f"Failed to list S3 files with prefix '{prefix}': {e}", exc_info=True)
            raise FileStorageError(f"Failed to list files from S3: {e}") from e

    async def get_presigned_url(self, path: str, expiration: int = 3600) -> Optional[str]:
        try:
            async with self._get_client() as client:
                url = await client.generate_presigned_url(
                    'get_object', # Or 'put_object' for upload URLs
                    Params={'Bucket': self.bucket_name, 'Key': path},
                    ExpiresIn=expiration
                )
                logger.debug(f"Generated presigned URL for {path}")
                return url
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code")
            logger.error(f"S3 ClientError generating presigned URL for {path}: {error_code} - {e}", exc_info=True)
            raise FileStorageError(f"Failed to generate presigned URL for S3: {error_code}") from e
        except Exception as e:
            logger.error(f"Failed to generate presigned URL for S3 file {path}: {e}", exc_info=True)
            raise FileStorageError(f"Failed to generate presigned URL for S3: {e}") from e

# --- Storage Client Factory ---

_storage_client_instance: Optional[IStorageClient] = None

async def get_storage_client(settings: AppSettings) -> IStorageClient:
    """
    Returns a singleton instance of the appropriate storage client (S3 or local).
    This function acts as a dependency injector for FastAPI.
    """
    global _storage_client_instance
    if _storage_client_instance is None:
        storage_settings = settings.storage_settings
        
        # Prioritize S3 if configured
        if storage_settings.s3_bucket_name and \
           storage_settings.aws_access_key_id and \
           storage_settings.aws_secret_access_key:
            
            _storage_client_instance = S3StorageClient(
                bucket_name=storage_settings.s3_bucket_name,
                aws_access_key_id=storage_settings.aws_access_key_id,
                aws_secret_access_key=storage_settings.aws_secret_access_key,
                endpoint_url=storage_settings.s3_endpoint_url
            )
            logger.info("Using S3/MinIO storage backend.")
        else:
            # Fallback to local filesystem storage
            local_base_path = Path(storage_settings.local_storage_base_path)
            _storage_client_instance = LocalStorageClient(base_dir=local_base_path)
            logger.info(f"Using local file storage backend with base path: {local_base_path}")
            
    return _storage_client_instance

```