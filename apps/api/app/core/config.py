from __future__ import annotations

from functools import lru_cache
from typing import Literal, Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="CONTEXTTRACE_",
        env_file=(".env", "../../.env"),
        extra="ignore",
    )

    database_url: str = (
        "postgresql+psycopg://contexttrace:contexttrace@localhost:5432/contexttrace"
    )
    default_api_key: str = "ctx_test"
    auto_create_dev_user: bool = True
    judge_provider: Literal["mock", "openai_compatible"] = "mock"
    openai_compatible_base_url: str = "https://api.openai.com/v1"
    openai_compatible_api_key: Optional[str] = None
    openai_compatible_model: str = "gpt-4.1-mini"


@lru_cache
def get_settings() -> Settings:
    return Settings()
