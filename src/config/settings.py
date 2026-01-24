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
    # Google Custom Search (Collector)
    GOOGLE_API_KEY: str
    GOOGLE_CSE_ID: str

    # Gemini (Analyzer/Writer/Matcher explanations)
    GEMINI_API_KEY: str
    GEMINI_MODEL: str = "gemini-2.0-flash"
    GEMINI_MODEL_FAST: str = "gemini-2.0-flash"
    GEMINI_MODEL_SMART: str = "gemini-2.0-flash"

    # Paths
    PROJECT_ROOT: str = ""
    DATA_DIR: str = "data"
    GENERATED_DIR: str = "data/generated"

    # Runtime
    HTTP_TIMEOUT_S: int = 20
    LOG_LEVEL: str = "INFO"


def load_settings() -> Settings:
    # charge .env depuis la racine si présent
    load_dotenv(override=False)

    project_root = os.getcwd()

    return Settings(
        GOOGLE_API_KEY=_get_env("GOOGLE_API_KEY", required=True),
        GOOGLE_CSE_ID=_get_env("GOOGLE_CSE_ID", required=True),
        GEMINI_API_KEY=_get_env("GEMINI_API_KEY", os.getenv("GOOGLE_API_KEY", ""), required=True),
        GEMINI_MODEL=_get_env("GEMINI_MODEL", "gemini-2.0-flash"),
        GEMINI_MODEL_FAST=_get_env("GEMINI_MODEL_FAST", "gemini-2.0-flash"),
        GEMINI_MODEL_SMART=_get_env("GEMINI_MODEL_SMART", "gemini-2.0-flash"),
        PROJECT_ROOT=project_root,
        DATA_DIR=_get_env("DATA_DIR", "data"),
        GENERATED_DIR=_get_env("GENERATED_DIR", "data/generated"),
        HTTP_TIMEOUT_S=int(_get_env("HTTP_TIMEOUT_S", "20")),
        LOG_LEVEL=_get_env("LOG_LEVEL", "INFO"),
    )


settings = load_settings()
