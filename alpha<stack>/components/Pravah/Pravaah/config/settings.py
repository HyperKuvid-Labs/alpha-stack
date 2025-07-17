from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, AnyHttpUrl
from typing import Optional


class AppSettings(BaseSettings):
    """
    Application-specific settings, loaded with prefix 'APP'.
    Example environment variables: APP__APP_NAME, APP__LOG_LEVEL
    """
    APP_NAME: str = "Pravah"
    APP_VERSION: str = "0.1.0"
    DEBUG_MODE: bool = Field(False, description="Enable debug mode for the application.")
    LOG_LEVEL: str = Field("INFO", description="Minimum logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).")


class DatabaseSettings(BaseSettings):
    """
    Database connection settings, loaded with prefix 'DATABASE'.
    Example environment variable: DATABASE__DATABASE_URL
    """
    DATABASE_URL: str = Field(
        ...,
        description="Connection string for the PostgreSQL database. "
                    "Example: postgresql://user:password@host:port/dbname"
    )


class AuthSettings(BaseSettings):
    """
    Authentication and JWT settings, loaded with prefix 'AUTH'.
    Example environment variables: AUTH__SECRET_KEY, AUTH__ALGORITHM
    """
    SECRET_KEY: str = Field(
        ...,
        description="Secret key for JWT token encoding and decoding. "
                    "MUST be a strong, randomly generated string in production."
    )
    ALGORITHM: str = Field("HS256", description="Algorithm used for JWT signing.")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(60, description="Access token expiration time in minutes.")


class StorageSettings(BaseSettings):
    """
    Cloud or local storage settings (e.g., S3, MinIO), loaded with prefix 'STORAGE'.
    Example environment variables: STORAGE__AWS_ACCESS_KEY_ID, STORAGE__S3_BUCKET_NAME
    """
    AWS_ACCESS_KEY_ID: Optional[str] = Field(None, description="AWS Access Key ID for S3/MinIO.")
    AWS_SECRET_ACCESS_KEY: Optional[str] = Field(None, description="AWS Secret Access Key for S3/MinIO.")
    S3_BUCKET_NAME: Optional[str] = Field(None, description="Name of the S3 bucket to use.")
    S3_ENDPOINT_URL: Optional[AnyHttpUrl] = Field(
        None,
        description="Custom S3 endpoint URL (e.g., for MinIO or localstack). "
                    "If not set, AWS default S3 endpoint is used."
    )


class Settings(BaseSettings):
    """
    Main application settings class, composed of nested settings categories.
    Loads settings from environment variables and a .env file.
    """
    app: AppSettings = AppSettings()
    database: DatabaseSettings = DatabaseSettings()
    auth: AuthSettings = AuthSettings()
    storage: StorageSettings = StorageSettings()

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,  # Environment variables are typically case-sensitive
        extra="ignore",       # Ignore environment variables not explicitly defined in any settings class
        env_nested_delimiter="__",  # Use double underscore for nested settings, e.g., APP__APP_NAME
    )


# Create a global settings instance to be imported throughout the application
settings = Settings()