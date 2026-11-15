
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Central application configuration.

    Values can be overridden using environment variables
    or a local .env file.
    """

    # Application settings
    app_name: str = "Greenwheels Fleet Lease Service"
    app_version: str = "1.0.0"
    environment: str = "local"
    log_level: str = "INFO"

    # PostgreSQL database configuration
    database_url: str = (
        "postgresql+psycopg://greenwheels:"
        "replace_me_local_password@localhost:5432/greenwheels"
    )

    # SQLAlchemy connection pool configuration
    database_pool_size: int = Field(default=5, validation_alias="DB_POOL_SIZE")
    database_max_overflow: int = Field(
        default=5,
        validation_alias="DB_MAX_OVERFLOW",
    )
    database_pool_timeout: int = Field(
        default=30,
        validation_alias="DB_POOL_TIMEOUT",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
