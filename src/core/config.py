"""Configuration management for Aprep agents."""

from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Anthropic API
    anthropic_api_key: str = Field(..., description="Anthropic API key")
    claude_model_sonnet: str = Field(
        default="claude-sonnet-4-20250514",
        description="Claude Sonnet model identifier",
    )
    claude_model_opus: str = Field(
        default="claude-opus-4-20250514",
        description="Claude Opus model identifier",
    )

    # Application settings
    log_level: str = Field(default="INFO", description="Logging level")
    environment: str = Field(default="development", description="Environment name")

    # Data paths
    ced_data_path: Path = Field(
        default=Path("./data/ced"),
        description="Path to CED documents",
    )
    templates_path: Path = Field(
        default=Path("./data/templates"),
        description="Path to template storage",
    )
    misconceptions_path: Path = Field(
        default=Path("./data/misconceptions"),
        description="Path to misconception database",
    )

    # API settings
    max_retries: int = Field(default=3, description="Maximum retry attempts")
    timeout_seconds: int = Field(default=30, description="API timeout in seconds")

    # Database Configuration
    database_url: str = Field(
        default="postgresql://aprep:aprep@localhost:5432/aprep_db",
        description="PostgreSQL database URL"
    )
    database_pool_size: int = Field(
        default=10,
        description="Database connection pool size"
    )
    database_max_overflow: int = Field(
        default=20,
        description="Database connection pool max overflow"
    )

    # Quality thresholds
    min_ced_alignment_score: float = Field(
        default=0.90,
        description="Minimum CED alignment score",
    )
    min_param_space_size: int = Field(
        default=30,
        description="Minimum parameter space size",
    )
    similarity_threshold: float = Field(
        default=0.80,
        description="Similarity threshold for plagiarism detection",
    )

    # Authentication & Security
    jwt_secret_key: str = Field(
        default="your-secret-key-change-this-in-production-min-32-characters-long",
        description="JWT secret key for token signing"
    )
    jwt_algorithm: str = Field(
        default="HS256",
        description="JWT algorithm"
    )
    jwt_access_token_expire_minutes: int = Field(
        default=30,
        description="Access token expiration in minutes"
    )
    jwt_refresh_token_expire_days: int = Field(
        default=7,
        description="Refresh token expiration in days"
    )
    password_reset_token_expire_hours: int = Field(
        default=1,
        description="Password reset token expiration in hours"
    )

    # CORS
    cors_origins: str = Field(
        default='["http://localhost:3000","http://localhost:8081","http://localhost:19006"]',
        description="Allowed CORS origins as JSON string"
    )

    # Email Configuration
    smtp_host: str = Field(default="smtp.gmail.com", description="SMTP server host")
    smtp_port: int = Field(default=587, description="SMTP server port")
    smtp_user: str = Field(default="", description="SMTP username")
    smtp_password: str = Field(default="", description="SMTP password")
    email_from: str = Field(default="noreply@aprep.com", description="From email address")
    email_from_name: str = Field(default="Aprep", description="From email name")

    def ensure_data_dirs(self) -> None:
        """Create data directories if they don't exist."""
        self.ced_data_path.mkdir(parents=True, exist_ok=True)
        self.templates_path.mkdir(parents=True, exist_ok=True)
        self.misconceptions_path.mkdir(parents=True, exist_ok=True)


# Global settings instance
settings = Settings()


def get_settings() -> Settings:
    """Get the global settings instance."""
    return settings
