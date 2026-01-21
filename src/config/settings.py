from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()  # charge .env automatiquement


@dataclass(frozen=True)
class Settings:
    google_api_key: str = os.getenv("GOOGLE_API_KEY", "")
    google_cse_id: str = os.getenv("GOOGLE_CSE_ID", "")
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")

    data_dir: str = os.getenv("DATA_DIR", "data")
    tracking_path: str = os.getenv("TRACKING_PATH", "data/tracking/applications.json")

    def validate(self) -> None:
        missing = []
        if not self.google_api_key: missing.append("GOOGLE_API_KEY")
        if not self.google_cse_id: missing.append("GOOGLE_CSE_ID")
        if not self.gemini_api_key: missing.append("GEMINI_API_KEY")
        if missing:
            raise ValueError(f"Missing env vars in .env: {', '.join(missing)}")


settings = Settings()
