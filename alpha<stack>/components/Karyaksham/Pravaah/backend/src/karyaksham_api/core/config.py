from pydantic import Field, SecretStr, HttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic_core import Url as PydanticUrl # For type hints with PostgresDsn, RedisDsn

# Define custom Pydantic DSN types for clarity and potential future validation
class PostgresDsn(PydanticUrl):
    allowed_schemes = {'postgresql', 'postgresql+psycopg', 'postgresql+asyncpg'}

class RedisDsn(PydanticUrl):
    allowed_schemes = {'redis', 'rediss'}

class Settings(BaseSettings):
    """
    Application settings loaded from environment variables and .env file.
    Uses Pydantic's BaseSettings for type-safe configuration.
    """
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",  # Ignore environment variables not explicitly defined
        case_sensitive=True # Environment variables are case-sensitive by default
    )

    # --- Application Settings ---
    ENVIRONMENT: str = Field(
        "development",
        description="Application environment (e.g., development, production, testing)"
    )
    SECRET_KEY: SecretStr = Field(
        ...,
        description="Secret key for JWTs, session management, and other cryptographic operations."
                    " **MUST BE KEPT SECRET IN PRODUCTION.**"
    )
    DEBUG: bool = Field(
        False,
        description="Enable FastAPI debug mode, showing detailed errors."
                    " Should be False in production."
    )
    PROJECT_NAME: str = Field(
        "Karyaksham",
        description="The name of the project, used in API documentation."
    )
    API_V1_STR: str = Field(
        "/api/v1",
        description="The base path for API version 1 endpoints."
    )

    # --- PostgreSQL Database Settings ---
    POSTGRES_SERVER: str = Field(..., description="PostgreSQL database host (e.g., 'localhost', 'db')")
    POSTGRES_USER: str = Field(..., description="PostgreSQL database user")
    POSTGRES_PASSWORD: SecretStr = Field(..., description="PostgreSQL database password")
    POSTGRES_DB: str = Field(..., description="PostgreSQL database name")
    POSTGRES_PORT: int = Field(5432, description="PostgreSQL database port")

    @property
    def DATABASE_URL(self) -> PostgresDsn:
        """
        Constructs the full PostgreSQL database connection URL.
        Uses 'postgresql+psycopg' driver for async operations with SQLAlchemy.
        """
        return PostgresDsn(
            f"postgresql+psycopg://{self.POSTGRES_USER}:"
            f"{self.POSTGRES_PASSWORD.get_secret_value()}@"
            f"{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    # --- Redis Broker & Cache Settings ---
    REDIS_HOST: str = Field(..., description="Redis server host (e.g., 'localhost', 'redis')")
    REDIS_PORT: int = Field(6379, description="Redis server port")

    @property
    def REDIS_URL(self) -> RedisDsn:
        """
        Constructs the Redis connection URL, typically used for cache and message broker.
        Assumes database 0 for simplicity, can be extended if needed.
        """
        return RedisDsn(f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/0")

    @property
    def CELERY_BROKER_URL(self) -> RedisDsn:
        """
        The URL for Celery's message broker. Defaults to the REDIS_URL.
        """
        return self.REDIS_URL

    @property
    def CELERY_RESULT_BACKEND(self) -> RedisDsn:
        """
        The URL for Celery's result backend. Defaults to the REDIS_URL.
        """
        return self.REDIS_URL

    # --- Object Storage Settings (AWS S3, Google Cloud Storage, or MinIO) ---
    OBJECT_STORAGE_ENDPOINT: HttpUrl = Field(
        ...,
        description="Endpoint URL for the object storage service (e.g., 'http://minio:9000', 'https://s3.aws.com')"
    )
    OBJECT_STORAGE_ACCESS_KEY: SecretStr = Field(
        ...,
        description="Access key for the object storage service."
    )
    OBJECT_STORAGE_SECRET_KEY: SecretStr = Field(
        ...,
        description="Secret key for the object storage service."
    )
    OBJECT_STORAGE_BUCKET: str = Field(
        ...,
        description="Default bucket name for storing application data in object storage."
    )


# Create a singleton instance of the settings to be imported across the application
settings = Settings()