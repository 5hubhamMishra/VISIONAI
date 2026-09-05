"""Environment-driven application settings.

Secrets (API keys, tokens) must come from environment variables or the OS
keychain, never from source or config files committed to the repository.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR"]
SttDevice = Literal["cpu", "cuda"]
SttComputeType = Literal["int8", "float16", "float32"]
LlmProvider = Literal["none", "anthropic"]


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
    stt_model_size: str = Field(default="base.en", min_length=1)
    stt_device: SttDevice = Field(default="cpu")
    stt_compute_type: SttComputeType = Field(default="int8")
    min_transcript_confidence: float = Field(default=0.7, gt=0.0, le=1.0)
    llm_provider: LlmProvider = Field(default="none")
    llm_model: str = Field(default="claude-opus-5", min_length=1)
    anthropic_api_key: SecretStr | None = Field(default=None)


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings instance, loaded once and cached."""
    return Settings()
