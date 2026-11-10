from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Literal

ROOT = Path(__file__).resolve().parents[4]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(ROOT / ".env", Path.cwd() / ".env"), extra="ignore")
    sqlite_path: str = str(ROOT / "data" / "acadza.sqlite3")
    admin_review_token: str = ""
    cors_origins: str = "http://localhost:3000"
    llm_provider: Literal["openai", "gemini", "openrouter"] = "openai"
    openai_api_key: str = ""
    gemini_api_key: str = ""
    openrouter_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    llm_cheap_model: str = ""
    llm_strong_model: str = ""
    llm_concurrency: int = 4
    llm_timeout_seconds: int = 50

    @property
    def db_file(self) -> Path:
        path = Path(self.sqlite_path).expanduser()
        return (path if path.is_absolute() else ROOT / path).resolve()


@lru_cache
def settings() -> Settings:
    return Settings()
