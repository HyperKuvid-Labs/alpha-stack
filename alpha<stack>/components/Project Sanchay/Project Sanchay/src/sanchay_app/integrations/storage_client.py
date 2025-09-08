import asyncio
import logging
from pathlib import Path
from typing import AsyncIterator, Optional, Dict, Any

import aiobotocore.session
from botocore.exceptions import ClientError, NoCredentialsError, PartialCredentialsError

# Assume config.settings can provide these or they are from environment variables
# The config module should handle loading from .env or environment vars.
from config import settings
from sanchay_app.utils.logging_config import get_logger

logger = get_logger(__name__)

class StorageClientError(Exception):
    """Custom exception for StorageClient errors."""
    pass

class StorageClient:
    """
    Client for interacting with S3-compatible object storage services (AWS S3, MinIO).

    Abstracts low-level API calls, providing a simplified asynchronous interface
    for uploading, downloading, listing, and managing files in remote storage.
    """

    def __init__(
        self,
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
        aws_endpoint_url: Optional[str] = None,
        aws_region: Optional[str] = None,
    ):
        """
        Initializes the S3 storage client.

        Credentials and endpoint URL can be provided explicitly or will be
        read from environment variables/config.settings by default.

        Args:
            aws_access_key_id (Optional[str]): AWS access key ID.
            aws_secret_access_key (Optional[str]): AWS secret access key.
            aws_endpoint_url (Optional[str]): Custom endpoint URL for S3-compatible services (e.g., MinIO).
            aws_region (Optional[str]): AWS region.
        """
        self._session = aiobotocore.session.get_session()
        
        # Determine configuration parameters, prioritizing explicit arguments, then settings.
        # Allow None for keys, as aiobotocore will handle default credential providers if not set.
        self._config: Dict[str, Any] = {
            "aws_access_key_id": aws_access_key_id if aws_access_key_id is not None else settings.AWS_ACCESS_KEY_ID,
            "aws_secret_access_key": aws_secret_access_key if aws_secret_access_key is not None else settings.AWS_SECRET_ACCESS_KEY,
            "endpoint_url": aws_endpoint_url if aws_endpoint_url is not None else settings.AWS_ENDPOINT_URL,
            "region_name": aws_region if aws_region is not None else settings.AWS_REGION,
        }

        # Filter out None values to let aiobotocore handle default credential chain
        # or standard endpoint for AWS if not explicitly provided.
        self._config = {k: v for k, v in self._config.items() if v is not None}
        
        logger.debug(f"StorageClient initialized with effective config (excluding secrets): "
                     f"{{'endpoint_url': '{self._config.get('endpoint_url')}', "
                     f"'region_name': '{self._config.get('region_name')}', "
                     f"'has_access_key': {self._config.get('aws_access_key_id') is not None}}}")

    async def _get_s3_client(self):
        """Returns an async S3 client context manager."""
        try:
            return self._session.create_client("s3", **self._config)
        except (NoCredentialsError, PartialCredentialsError) as e:
            logger.error(f"S3 client initialization failed due to missing or invalid credentials: {e}")
            raise StorageClientError(f"Cloud storage client could not be initialized. "
                                     f"Check credentials and region settings. Error: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error creating S3 client: {e}", exc_info=True)
            raise StorageClientError(f"An unexpected error occurred during S3 client creation: {e}") from e

    async def upload_file(self, local_file_path: Path, bucket_name: str, object_key: str):
        """
        Uploads a local file to the specified S3 bucket.

        Args:
            local_file_path (Path): The path to the local file to upload.
            bucket_name (str): The name of the S3 bucket.
            object_key (str): The key (path) of the object in the S3 bucket.

        Raises:
            StorageClientError: If the upload fails or the local file does not exist.
        """
        if not local_file_path.is_file():
            raise StorageClientError(f"Local file not found for upload: '{local_file_path}'")
        if not bucket_name or not object_key:
            raise StorageClientError("Bucket name and object key cannot be empty for upload.")

        logger.info(f"Uploading '{local_file_path}' to s3://{bucket_name}/{object_key}")
        try:
            async with self._get_s3_client() as client:
                # Open the file in binary read mode.
                # aiobotocore's put_object handles file-like objects for the Body parameter.
                with open(local_file_path, "rb") as data:
                    await client.put_object(Bucket=bucket_name, Key=object_key, Body=data)
            logger.info(f"Successfully uploaded '{object_key}' to '{bucket_name}'.")
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code")
            logger.error(f"S3 ClientError during upload for '{object_key}': {error_code} - {e}")
            raise StorageClientError(f"Failed to upload '{object_key}': {error_code} - {e.response.get('Error', {}).get('Message', '')}") from e
        except FileNotFoundError as e:
            logger.error(f"Local file not found during upload: '{local_file_path}' - {e}")
            raise StorageClientError(f"Local file not found: '{local_file_path}'") from e
        except Exception as e:
            logger.error(f"Unexpected error during upload for '{object_key}': {e}", exc_info=True)
            raise StorageClientError(f"An unexpected error occurred during upload: {e}") from e

    async def download_file(self, bucket_name: str, object_key: str, local_file_path: Path):
        """
        Downloads a file from the specified S3 bucket to a local path.

        Args:
            bucket_name (str): The name of the S3 bucket.
            object_key (str): The key (path) of the object in the S3 bucket.
            local_file_path (Path): The path where the file should be saved locally.

        Raises:
            StorageClientError: If the download fails.
        """
        if not bucket_name or not object_key or not local_file_path:
            raise StorageClientError("Bucket name, object key, and local file path cannot be empty for download.")

        logger.info(f"Downloading s3://{bucket_name}/{object_key} to '{local_file_path}'")
        try:
            async with self._get_s3_client() as client:
                response = await client.get_object(Bucket=bucket_name, Key=object_key)
                async with response["Body"] as stream:
                    # Ensure the parent directory exists before writing the file
                    local_file_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(local_file_path, "wb") as f:
                        # Stream the content in chunks to avoid loading large files into memory
                        async for chunk in stream.iter_chunks():
                            f.write(chunk)
            logger.info(f"Successfully downloaded '{object_key}' to '{local_file_path}'.")
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code")
            logger.error(f"S3 ClientError during download for '{object_key}': {error_code} - {e}")
            if error_code == "NoSuchKey" or e.response.get("ResponseMetadata", {}).get("HTTPStatusCode") == 404:
                raise StorageClientError(f"Object '{object_key}' not found in bucket '{bucket_name}'.") from e
            raise StorageClientError(f"Failed to download '{object_key}': {error_code} - {e.response.get('Error', {}).get('Message', '')}") from e
        except IOError as e:
            logger.error(f"IOError during file write for download target '{local_file_path}': {e}")
            raise StorageClientError(f"Failed to write downloaded file to '{local_file_path}': {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error during download for '{object_key}': {e}", exc_info=True)
            raise StorageClientError(f"An unexpected error occurred during download: {e}") from e

    async def list_objects(self, bucket_name: str, prefix: str = "") -> AsyncIterator[Dict[str, Any]]:
        """
        Lists objects in an S3 bucket with an optional prefix.

        Args:
            bucket_name (str): The name of the S3 bucket.
            prefix (str): An optional prefix to filter the objects.

        Yields:
            dict: Dictionary containing object metadata (e.g., 'Key', 'Size', 'LastModified').

        Raises:
            StorageClientError: If listing objects fails.
        """
        if not bucket_name:
            raise StorageClientError("Bucket name cannot be empty for listing objects.")

        logger.debug(f"Listing objects in bucket '{bucket_name}' with prefix '{prefix}'")
        try:
            async with self._get_s3_client() as client:
                paginator = client.get_paginator("list_objects_v2")
                async for page in paginator.paginate(Bucket=bucket_name, Prefix=prefix):
                    for obj in page.get("Contents", []):
                        yield obj
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code")
            logger.error(f"S3 ClientError during list_objects for '{bucket_name}/{prefix}': {error_code} - {e}")
            raise StorageClientError(f"Failed to list objects in '{bucket_name}': {error_code} - {e.response.get('Error', {}).get('Message', '')}") from e
        except Exception as e:
            logger.error(f"Unexpected error during list_objects: {e}", exc_info=True)
            raise StorageClientError(f"An unexpected error occurred during listing: {e}") from e

    async def delete_object(self, bucket_name: str, object_key: str):
        """
        Deletes an object from the specified S3 bucket.

        Args:
            bucket_name (str): The name of the S3 bucket.
            object_key (str): The key (path) of the object to delete.

        Raises:
            StorageClientError: If the deletion fails.
        """
        if not bucket_name or not object_key:
            raise StorageClientError("Bucket name and object key cannot be empty for deletion.")

        logger.info(f"Deleting s3://{bucket_name}/{object_key}")
        try:
            async with self._get_s3_client() as client:
                await client.delete_object(Bucket=bucket_name, Key=object_key)
            logger.info(f"Successfully deleted '{object_key}' from '{bucket_name}'.")
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code")
            logger.error(f"S3 ClientError during delete for '{object_key}': {error_code} - {e}")
            raise StorageClientError(f"Failed to delete '{object_key}': {error_code} - {e.response.get('Error', {}).get('Message', '')}") from e
        except Exception as e:
            logger.error(f"Unexpected error during delete for '{object_key}': {e}", exc_info=True)
            raise StorageClientError(f"An unexpected error occurred during deletion: {e}") from e

    async def object_exists(self, bucket_name: str, object_key: str) -> bool:
        """
        Checks if an object exists in the specified S3 bucket.

        Args:
            bucket_name (str): The name of the S3 bucket.
            object_key (str): The key (path) of the object to check.

        Returns:
            bool: True if the object exists, False otherwise.

        Raises:
            StorageClientError: If checking object existence fails due to reasons other than NoSuchKey.
        """
        if not bucket_name or not object_key:
            raise StorageClientError("Bucket name and object key cannot be empty for existence check.")

        logger.debug(f"Checking existence of s3://{bucket_name}/{object_key}")
        try:
            async with self._get_s3_client() as client:
                await client.head_object(Bucket=bucket_name, Key=object_key)
            return True
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code")
            http_status = e.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
            # 404 is the typical status code for HeadObject when the object doesn't exist
            if error_code == "NotFound" or http_status == 404:
                return False
            logger.error(f"S3 ClientError during object_exists check for '{object_key}': {error_code} - {e}")
            raise StorageClientError(f"Failed to check existence of '{object_key}': {error_code} - {e.response.get('Error', {}).get('Message', '')}") from e
        except Exception as e:
            logger.error(f"Unexpected error during object_exists check: {e}", exc_info=True)
            raise StorageClientError(f"An unexpected error occurred during existence check: {e}") from e