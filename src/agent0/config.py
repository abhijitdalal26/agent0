from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="AGENT0_", extra="ignore")

    env: Literal["local", "cloud"] = "local"
    database_url: str = "postgresql://agent0:agent0@localhost:5432/agent0"
    orchestrator: Literal["local", "temporal"] = "local"
    temporal_address: str = "localhost:7233"
    temporal_namespace: str = "default"
    task_queue: str = "agent0"
    sandbox: Literal["docker", "local", "e2b"] = "docker"
    sandbox_image: str = "python:3.13-slim"
    workspace_root: Path = Path(".agent0/workspaces")
    config_dir: Path = Path("config")
    skills_dirs: list[Path] = [Path("skills"), Path.home() / ".agent0" / "skills"]
    plugins_dirs: list[Path] = [Path("plugins"), Path.home() / ".agent0" / "plugins"]
    api_key: str = "dev-key"
    cors_origins: list[str] = ["http://localhost:3000"]
    secret_key: str | None = None
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    telegram_bot_token: str | None = None
    telegram_allowed_users: list[str] = []


@lru_cache
def get_settings() -> Settings:
    return Settings()
