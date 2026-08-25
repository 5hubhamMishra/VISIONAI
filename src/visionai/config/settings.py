"""Environment-driven application settings.

Secrets (API keys, tokens) must come from environment variables or the OS
keychain, never from source or config files committed to the repository.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR"]


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables and `.env`."""

    model_config = SettingsConfigDict(
        env_prefix="VISIONAI_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    log_level: LogLevel = Field(default="INFO")
    log_dir: Path = Field(default=Path("logs"))
    data_dir: Path = Field(default=Path(".visionai"))


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings instance, loaded once and cached."""
    return Settings()
