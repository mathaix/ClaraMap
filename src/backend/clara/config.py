"""Application configuration."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Application
    app_name: str = "Clara"
    app_version: str = "0.1.0"
    debug: bool = False

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/clara"

    # CORS
    cors_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    # Security
    secret_key: str = "dev-secret-key-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    # AI Models
    simulation_interviewer_model: str = "sonnet"
    simulation_user_model: str = "haiku"
    web_search_model: str = "claude-sonnet-4-20250514"
    router_model: str = "haiku"

    # Anthropic API (uses ANTHROPIC_API_KEY env var by default)
    anthropic_api_key: str | None = None

    # File Upload Configuration
    upload_dir: str = "./uploads"  # Local storage path (use S3 in production)
    max_file_size_mb: int = 25  # Maximum file size in MB
    max_files_per_agent: int = 10  # Maximum files per agent
    allowed_file_extensions: list[str] = [
        ".pdf", ".docx", ".doc", ".xlsx", ".xls",
        ".txt", ".md", ".csv",
        ".png", ".jpg", ".jpeg", ".gif", ".webp"
    ]
    # MIME type whitelist (validated against file content, not just extension)
    allowed_mime_types: list[str] = [
        # Documents
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.ms-excel",
        "text/plain",
        "text/markdown",
        "text/csv",
        # Images
        "image/png",
        "image/jpeg",
        "image/gif",
        "image/webp",
    ]


settings = Settings()
