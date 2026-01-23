from __future__ import annotations

import json
import re
import time
from typing import Any, Dict, Type, TypeVar

from pydantic import BaseModel, ValidationError

from src.config.logging import logger
from src.config.settings import settings


from google import genai
from google.genai import types

T = TypeVar("T", bound=BaseModel)

def extract_json_dict(text: str) -> Dict[str, Any]:
    """
    Extract the first JSON object found in text.
    Handles ```json ...``` and extra text.
    """
    text = (text or "").strip()

    fence_match = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, flags=re.DOTALL)
    if fence_match:
        text = fence_match.group(1).strip()

    try:
        return json.loads(text)
    except Exception:
        pass

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return json.loads(text[start : end + 1])

    raise ValueError("No JSON object found in LLM output")


class GeminiClient:
    def __init__(self, api_key: str, model: str):

        self.client = genai.Client(api_key=api_key)
        self.model_name = model

    def _try_generate(self, model: str, prompt: str, temperature: float, max_output_tokens: int) -> str:
        # New SDK usage
        response = self.client.models.generate_content(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=temperature,
                max_output_tokens=max_output_tokens
            )
        )
        return response.text or ""

    def _fallback_model(self) -> str:
        try:
            # Listing might be different in new SDK, keeping it simple or skipping fallback logic if complex
            # For now, just return a safe default if list fails
            return "gemini-2.0-flash" 
        except Exception as e:
            logger.warning(f"[gemini] fallback list error: {e}")
            return self.model_name

    def generate_text(
        self,
        prompt: str,
        *,
        temperature: float = 0.2,
        max_output_tokens: int = 1024,
        retries: int = 3,
    ) -> str:
        # try configured model with retry/backoff on 429
        backoff = 1.2
        last_err: Exception | None = None

        for attempt in range(1, retries + 1):
            try:
                return self._try_generate(self.model_name, prompt, temperature, max_output_tokens)
            except Exception as e:
                last_err = e
                msg = str(e).lower()

                # Model unavailable -> fallback once
                if "not found" in msg or "is not supported" in msg or "404" in msg:
                    fb = self._fallback_model()
                    logger.warning(f"[gemini] model '{self.model_name}' unavailable -> fallback to '{fb}'")
                    self.model_name = fb
                    continue

                # Quota/rate limit -> backoff
                if "429" in msg or "resource_exhausted" in msg:
                    logger.warning(f"[gemini] 429 rate limit -> backoff {backoff:.1f}s (attempt {attempt}/{retries})")
                    time.sleep(backoff)
                    backoff *= 2
                    continue

                # Other errors: no special handling
                logger.warning(f"[gemini] generation failed (attempt {attempt}/{retries}) err={e}")

        raise RuntimeError(f"Gemini text generation failed: {last_err}")

    def generate_json(
        self,
        prompt: str,
        schema: Type[T],
        *,
        temperature: float = 0.2,
        max_output_tokens: int = 1024,
        retries: int = 2,
    ) -> T:
        last_err: Exception | None = None
        base_prompt = prompt.strip()

        for attempt in range(1, retries + 2):
            try:
                text = self.generate_text(
                    base_prompt,
                    temperature=temperature,
                    max_output_tokens=max_output_tokens,
                )
                data = extract_json_dict(text)
                return schema.model_validate(data)
            except (ValueError, ValidationError) as e:
                last_err = e
                logger.warning(f"[gemini] JSON parse/validation failed (attempt {attempt}) err={e}")
                schema_keys = list(schema.model_fields.keys())
                base_prompt = (
                    "Return ONLY a valid JSON object. No markdown. No extra text.\n"
                    f"JSON must match these keys: {schema_keys}\n"
                    "Use ONLY allowed enum values for contract_type and seniority.\n"
                    "If data is missing, use 'unknown' or empty arrays.\n"
                )
            except Exception as e:
                last_err = e
                logger.warning(f"[gemini] generation failed (attempt {attempt}) err={e}")

        raise RuntimeError(f"Gemini JSON generation failed: {last_err}")


_default_model = settings.GEMINI_MODEL
if not _default_model.startswith("models/"):
    _default_model = f"models/{_default_model}"

llm = GeminiClient(api_key=settings.GEMINI_API_KEY, model=_default_model)
