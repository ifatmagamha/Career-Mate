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
    # Google Custom Search (legacy search collector only; checked when a search runs)
    # Models and their API keys are configured in config/models.toml, not here.
    GOOGLE_API_KEY: str = ""
    GOOGLE_CSE_ID: str = ""

    # Paths
    PROJECT_ROOT: str = ""
    DATA_DIR: str = "data"
    GENERATED_DIR: str = "data/generated"

    # Runtime
    HTTP_TIMEOUT_S: int = 20
    LOG_LEVEL: str = "INFO"


def load_settings() -> Settings:
    load_dotenv(override=False)

    project_root = os.getcwd()

    return Settings(
        GOOGLE_API_KEY=_get_env("GOOGLE_API_KEY", ""),
        GOOGLE_CSE_ID=_get_env("GOOGLE_CSE_ID", ""),
        PROJECT_ROOT=project_root,
        DATA_DIR=_get_env("DATA_DIR", "data"),
        GENERATED_DIR=_get_env("GENERATED_DIR", "data/generated"),
        HTTP_TIMEOUT_S=int(_get_env("HTTP_TIMEOUT_S", "20")),
        LOG_LEVEL=_get_env("LOG_LEVEL", "INFO"),
    )


settings = load_settings()
