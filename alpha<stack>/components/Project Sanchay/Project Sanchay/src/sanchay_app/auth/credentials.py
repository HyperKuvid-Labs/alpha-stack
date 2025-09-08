import os
import logging
from typing import Optional, Dict

# python-dotenv is used for loading credentials from a .env file during local development.
# In production, environment variables are preferred.
try:
    from dotenv import dotenv_values, find_dotenv
except ImportError:
    # If python-dotenv is not installed, these functions will be None,
    # and .env file loading will be skipped gracefully.
    dotenv_values = None
    find_dotenv = None

# Set up logging for this module. The actual logging configuration (handlers, formatters)
# is expected to be done centrally in `sanchay_app.utils.logging_config`.
logger = logging.getLogger(__name__)

# Constants for environment variable keys used for AWS credentials.
AWS_ACCESS_KEY_ID_ENV_VAR = "AWS_ACCESS_KEY_ID"
AWS_SECRET_ACCESS_KEY_ENV_VAR = "AWS_SECRET_ACCESS_KEY"
AWS_REGION_ENV_VAR = "AWS_REGION"


class CredentialsManager:
    """
    Manages the loading and retrieval of sensitive credentials for external services.
    It prioritizes system environment variables and falls back to a `.env` file
    (if `python-dotenv` is installed) for local development.

    This class is implemented as a singleton to ensure credentials are loaded only once
    and consistently accessed across the application.
    """

    _instance: Optional["CredentialsManager"] = None
    _loaded_env_vars: Dict[str, str] = {}  # Stores all loaded credential values

    def __new__(cls):
        """
        Ensures that only one instance of CredentialsManager is created and used.
        """
        if cls._instance is None:
            cls._instance = super(CredentialsManager, cls).__new__(cls)
            cls._instance._load_credentials()
        return cls._instance

    def _load_credentials(self):
        """
        Internal method to load credentials. It first attempts to load from a `.env`
        file if `python-dotenv` is available, then overrides or adds values from
        actual system environment variables. System environment variables always
        take precedence.
        """
        # Attempt to load from .env file for local development
        if dotenv_values and find_dotenv:
            dotenv_path = find_dotenv()
            if dotenv_path:
                logger.info(f"Loading credentials from .env file: {dotenv_path}")
                self._loaded_env_vars.update(dotenv_values(dotenv_path))
            else:
                logger.debug("No .env file found in the current directory or its parents.")
        else:
            logger.debug("python-dotenv not installed, skipping .env file loading.")

        # Override or add credentials from actual environment variables.
        # This ensures system environment variables always take precedence.
        all_relevant_keys = {
            AWS_ACCESS_KEY_ID_ENV_VAR,
            AWS_SECRET_ACCESS_KEY_ENV_VAR,
            AWS_REGION_ENV_VAR,
            # Add other credential keys here as needed for different services
        }

        for key in all_relevant_keys:
            env_value = os.getenv(key)
            if env_value is not None:
                self._loaded_env_vars[key] = env_value
                logger.debug(f"Credential '{key}' loaded from environment variable.")
            elif key in self._loaded_env_vars:
                logger.debug(f"Credential '{key}' loaded from .env file.")
            else:
                logger.debug(f"Credential '{key}' not found in environment or .env file.")

        if not self._loaded_env_vars:
            logger.warning("No credentials were loaded from environment variables or .env file.")

    def _get_credential(self, key: str, required: bool = False) -> Optional[str]:
        """
        Retrieves a specific credential by its key.
        If `required` is True and the credential is not found, a ValueError is raised.
        """
        value = self._loaded_env_vars.get(key)
        if value is None and required:
            logger.error(f"Required credential '{key}' is missing. Check environment variables or .env file.")
            raise ValueError(f"Required credential '{key}' is missing.")
        return value

    def get_aws_access_key_id(self, required: bool = False) -> Optional[str]:
        """
        Retrieves the AWS Access Key ID.
        """
        return self._get_credential(AWS_ACCESS_KEY_ID_ENV_VAR, required=required)

    def get_aws_secret_access_key(self, required: bool = False) -> Optional[str]:
        """
        Retrieves the AWS Secret Access Key.
        """
        return self._get_credential(AWS_SECRET_ACCESS_KEY_ENV_VAR, required=required)

    def get_aws_region(self, required: bool = False) -> Optional[str]:
        """
        Retrieves the AWS Region.
        """
        return self._get_credential(AWS_REGION_ENV_VAR, required=required)

    def get_aws_credentials(self, required: bool = False) -> Dict[str, Optional[str]]:
        """
        Retrieves all AWS-related credentials as a dictionary, suitable for
        passing to AWS SDK clients (e.g., `boto3`).
        """
        access_key = self.get_aws_access_key_id(required=required)
        secret_key = self.get_aws_secret_access_key(required=required)
        region = self.get_aws_region(required=False)  # Region might have a default in SDK

        if required:
            if access_key is None:
                raise ValueError("Required AWS Access Key ID is missing.")
            if secret_key is None:
                raise ValueError("Required AWS Secret Access Key is missing.")

        return {
            "aws_access_key_id": access_key,
            "aws_secret_access_key": secret_key,
            "aws_region": region,
        }


# Export a singleton instance of the CredentialsManager for easy import
# throughout the application, e.g., `from sanchay_app.auth.credentials import credentials_manager`.
credentials_manager = CredentialsManager()