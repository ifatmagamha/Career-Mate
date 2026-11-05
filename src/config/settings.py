from __future__ import annotations

import os
from dataclasses import dataclass
from dotenv import load_dotenv


def _get_env(name: str, default: str | None = None, *, required: bool = False) -> str:
    val = os.getenv(name, default)
    if required and (val is None or str(val).strip() == ""):
        raise RuntimeError(f"Missing required env var: {name}")
    return str(val) if val is not None else ""


@dataclass(frozen=True)
class Settings:
    # Models and their API keys are configured in config/models.toml, not here.

    # PostgreSQL (Supabase in production, Docker locally)
    DATABASE_URL: str = ""
    DB_SCHEMA: str = "career"  # private schema: not exposed by Supabase's public REST API

    # Supabase Auth. Without SUPABASE_URL the API runs as a single local user (development only).
    SUPABASE_URL: str = ""
    SUPABASE_JWT_SECRET: str = ""  # only for projects still on the legacy shared HS256 secret

    # development | production (production refuses to start without auth)
    APP_ENV: str = "development"
    CORS_ORIGINS: str = "http://localhost:5173"  # comma-separated web UI origins

    # Runtime
    HTTP_TIMEOUT_S: int = 20
    LOG_LEVEL: str = "INFO"


def load_settings() -> Settings:
    load_dotenv(override=False)

    return Settings(
        DATABASE_URL=_get_env("DATABASE_URL", ""),
        DB_SCHEMA=_get_env("DB_SCHEMA", "career"),
        SUPABASE_URL=_get_env("SUPABASE_URL", "").rstrip("/"),
        SUPABASE_JWT_SECRET=_get_env("SUPABASE_JWT_SECRET", ""),
        APP_ENV=_get_env("APP_ENV", "development"),
        CORS_ORIGINS=_get_env("CORS_ORIGINS", "http://localhost:5173"),
        HTTP_TIMEOUT_S=int(_get_env("HTTP_TIMEOUT_S", "20")),
        LOG_LEVEL=_get_env("LOG_LEVEL", "INFO"),
    )


settings = load_settings()
