from __future__ import annotations

import os
from dataclasses import dataclass

from google import genai


@dataclass
class GeminiClient:
    api_key: str | None = None

    def __post_init__(self):
        key = self.api_key or os.getenv("GEMINI_API_KEY")
        if not key:
            raise ValueError("Missing GEMINI_API_KEY (env or passed to GeminiClient)")
        self._client = genai.Client(api_key=key)

    def generate(self, *, model: str, prompt: str) -> str:
        resp = self._client.models.generate_content(
            model=model,
            contents=prompt,
        )
        return resp.text or ""
