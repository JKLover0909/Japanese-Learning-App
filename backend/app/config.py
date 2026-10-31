"""Application settings, read from ``JP_*`` environment variables."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="JP_", extra="ignore")

    database_url: str = f"sqlite:///{REPO_ROOT / 'data' / 'app.db'}"
    allow_registration: bool = False
    registration_code: str = ""
    admin_username: str = ""
    admin_password_hash: str = ""
    session_days: int = Field(default=30, ge=1, le=365)
    cookie_secure: Literal["auto", "true", "false"] = "auto"
    content_dir: Path = BACKEND_DIR / "app" / "content" / "lessons"
    frontend_dist: Path = REPO_ROOT / "frontend" / "dist"
    auto_migrate: bool = True
    session_size: int = Field(default=20, ge=1, le=200)
    focus_size: int = Field(default=5, ge=0, le=200)

    @property
    def sqlite_path(self) -> Path | None:
        """Filesystem path of a file-based SQLite database, otherwise ``None``."""
        url = make_url(self.database_url)
        if url.get_backend_name() != "sqlite":
            return None
        database = url.database or ""
        if not database or database == ":memory:" or database.startswith("file:"):
            return None
        return Path(database)

    def ensure_data_dir(self) -> None:
        path = self.sqlite_path
        if path is not None:
            path.parent.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    return Settings()
