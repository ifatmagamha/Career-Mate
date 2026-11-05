# src/llm/port.py
"""
LLMPort: the only way app code talks to a model (spec v0.1, D3).

One OpenAI-compatible adapter covers Gemini, the Hugging Face router, vLLM/SGLang,
llama.cpp and Ollama. Which model serves which role lives in config/models.toml.
Every HTTP call (retries included) is logged to the llm_calls table.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
import tomllib
from contextvars import ContextVar
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Type, TypeVar

import requests
from pydantic import BaseModel, ValidationError

from src.config.logging import logger

T = TypeVar("T", bound=BaseModel)

CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "models.toml"

# Who the current request is for (set by the API's auth dependency), so llm_calls rows carry the user
current_user: ContextVar[Optional[str]] = ContextVar("current_user", default=None)


def _db_log(call: Dict[str, Any]) -> None:
    from src.storage import db
    call = {**call, "user_id": current_user.get(), "offer_id": db._id(call.get("offer_id"))}
    with db.connection() as conn:
        db.log_llm_call(conn, call)
MAX_ATTEMPTS = 3
BACKOFF_S = (2, 6)
MAX_RETRY_AFTER_S = 60  # never wait longer than this on a provider's Retry-After


class LLMError(RuntimeError):
    pass


class QuotaExhausted(LLMError):
    """Daily quota hit: retrying today is pointless."""


class StructuredOutputError(LLMError):
    """The model did not return JSON matching the schema, even after one repair."""


def prompt_version(template: str) -> str:
    """Short content hash of a prompt template: changes whenever the prompt changes."""
    return hashlib.sha1(template.encode("utf-8")).hexdigest()[:8]


def extract_json(text: str) -> Dict[str, Any]:
    """First JSON object in a model answer (handles ```json fences and extra text)."""
    text = (text or "").strip()
    fence = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, flags=re.DOTALL)
    if fence:
        text = fence.group(1)
    try:
        return json.loads(text)
    except ValueError:
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end > start:
            return json.loads(text[start : end + 1])
        raise ValueError("No JSON object found in model output")


@dataclass
class RoleConfig:
    role: str
    provider: str
    model: str
    base_url: str
    api_key: str
    structured: str
    params: Dict[str, Any] = field(default_factory=dict)
    price_in: Optional[float] = None
    price_out: Optional[float] = None


def load_role(role: str, config_path: Path = CONFIG_PATH) -> RoleConfig:
    """Resolution order: LLM_<ROLE>_* env > [roles.<role>] > LLM_DEFAULT_* env > [defaults]."""
    cfg = tomllib.loads(config_path.read_text(encoding="utf-8"))
    if role not in cfg["roles"]:
        raise LLMError(f"Unknown role '{role}' in {config_path.name}")
    r, d = cfg["roles"][role], cfg.get("defaults", {})
    provider = (os.getenv(f"LLM_{role.upper()}_PROVIDER") or r.get("provider")
                or os.getenv("LLM_DEFAULT_PROVIDER") or d.get("provider"))
    model = (os.getenv(f"LLM_{role.upper()}_MODEL") or r.get("model")
             or os.getenv("LLM_DEFAULT_MODEL") or d.get("model"))
    if not provider or not model:
        raise LLMError(f"Role '{role}' has no provider/model: set them in [defaults] or [roles.{role}]")
    if provider not in cfg["providers"]:
        raise LLMError(f"Role '{role}' uses unknown provider '{provider}' (known: {', '.join(cfg['providers'])})")
    p = cfg["providers"][provider]
    price = cfg.get("prices", {}).get(model, {})
    key_envs = p.get("api_key_env") or []
    key_envs = [key_envs] if isinstance(key_envs, str) else key_envs
    api_key = next((os.environ[k] for k in key_envs if os.getenv(k)), "")
    if key_envs and not api_key:
        raise LLMError(f"Provider '{provider}' needs an API key: set one of {', '.join(key_envs)}")
    return RoleConfig(
        role=role, provider=provider, model=model, base_url=p["base_url"].rstrip("/"),
        api_key=api_key,
        structured=p.get("structured", "prompt"), params=dict(r.get("params", {})),
        price_in=price.get("input"), price_out=price.get("output"),
    )


def _as_messages(prompt: str | List[Dict[str, str]]) -> List[Dict[str, str]]:
    return [{"role": "user", "content": prompt}] if isinstance(prompt, str) else list(prompt)


def _content_text(message: Dict[str, Any]) -> str:
    content = message.get("content") or ""
    if isinstance(content, list):  # some providers return content blocks
        return "".join(part.get("text", "") for part in content if isinstance(part, dict))
    return content


class LLMPort:
    def __init__(self, post: Callable[..., requests.Response] = requests.post,
                 log: Callable[[Dict[str, Any]], None] = _db_log, config_path: Path = CONFIG_PATH):
        self._post = post
        self._log_call = log
        self._config_path = config_path

    def config(self, role: str) -> RoleConfig:
        return load_role(role, self._config_path)

    # --- public API -------------------------------------------------------

    def complete(self, prompt: str | List[Dict[str, str]], *, role: str, prompt_version: str | None = None,
                 offer_id: str | None = None, **params: Any) -> str:
        return _content_text(self.respond(prompt, role=role, prompt_version=prompt_version, offer_id=offer_id, **params))

    def respond(self, prompt: str | List[Dict[str, Any]], *, role: str, tools: List[Dict[str, Any]] | None = None,
                prompt_version: str | None = None, offer_id: str | None = None, **params: Any) -> Dict[str, Any]:
        """Full assistant message (content + tool_calls), for tool loops. tools use the OpenAI function format."""
        cfg = self.config(role)
        body = {"model": cfg.model, "messages": _as_messages(prompt), **cfg.params, **params}
        if tools:
            body["tools"] = tools
        data = self._request(cfg, "/chat/completions", body, prompt_version, offer_id)
        return data["choices"][0]["message"]

    def structured(self, prompt: str | List[Dict[str, str]], schema: Type[T], *, role: str,
                   prompt_version: str | None = None, offer_id: str | None = None, **params: Any) -> T:
        cfg = self.config(role)
        messages = _as_messages(prompt)
        json_schema = schema.model_json_schema()
        if cfg.structured == "json_schema":
            params["response_format"] = {"type": "json_schema", "json_schema": {"name": schema.__name__, "schema": json_schema}}
        else:
            if cfg.structured == "json_object":
                params["response_format"] = {"type": "json_object"}
            messages = messages + [{"role": "user", "content": "Return ONLY a JSON object matching this JSON schema:\n"
                                    + json.dumps(json_schema)}]

        text = self.complete(messages, role=role, prompt_version=prompt_version, offer_id=offer_id, **params)
        try:
            return schema.model_validate(extract_json(text))
        except (ValueError, ValidationError) as e:
            logger.warning(f"[llm] {role}: invalid structured output, one repair attempt ({str(e)[:200]})")
            repair = messages + [
                {"role": "assistant", "content": text},
                {"role": "user", "content": f"That output was invalid: {str(e)[:1000]}\nReturn ONLY the corrected JSON object."},
            ]
            text = self.complete(repair, role=role, prompt_version=prompt_version, offer_id=offer_id, **params)
            try:
                return schema.model_validate(extract_json(text))
            except (ValueError, ValidationError) as e2:
                raise StructuredOutputError(f"{cfg.model}: {e2}") from e2

    def embed(self, texts: List[str], *, role: str = "embed") -> List[List[float]]:
        cfg = self.config(role)
        data = self._request(cfg, "/embeddings", {"model": cfg.model, "input": texts}, None, None)
        # Gemini omits "index"; sorted() is stable, so input order is kept when it is missing
        return [d["embedding"] for d in sorted(data["data"], key=lambda d: d.get("index", 0))]

    # --- transport ----------------------------------------------------------

    def _request(self, cfg: RoleConfig, path: str, body: Dict[str, Any], prompt_version: str | None,
                 offer_id: str | None) -> Dict[str, Any]:
        headers = {"Authorization": f"Bearer {cfg.api_key}"} if cfg.api_key else {}
        last_err = ""
        for attempt in range(1, MAX_ATTEMPTS + 1):
            start = time.monotonic()
            status, data, err, retry_after = None, None, None, None
            try:
                resp = self._post(cfg.base_url + path, json=body, headers=headers, timeout=120)
                status = resp.status_code
                if status < 400:
                    data = resp.json()
                else:
                    err = resp.text[:2000]
                    retry_after = (getattr(resp, "headers", None) or {}).get("retry-after")
            except requests.RequestException as e:
                err = f"{type(e).__name__}: {e}"
            self._log(cfg, body, prompt_version, offer_id, status, data, err, time.monotonic() - start)

            if data is not None:
                return data
            last_err = f"HTTP {status}: {err}" if status else err
            if status == 429 and re.search(r"per ?day", err or "", re.IGNORECASE):
                raise QuotaExhausted(f"{cfg.provider}/{cfg.model} daily quota exhausted")
            retryable = status is None or status == 429 or status >= 500
            if not retryable or attempt == MAX_ATTEMPTS:
                break
            delay = BACKOFF_S[attempt - 1]
            try:  # the provider knows when its per-minute window frees up (Groq: tokens per minute)
                delay = min(float(retry_after) + 0.5, MAX_RETRY_AFTER_S) if retry_after else delay
            except ValueError:  # HTTP-date form: keep the backoff
                pass
            logger.warning(f"[llm] {cfg.role} {cfg.model}: {last_err[:120]} -> retry in {delay}s ({attempt}/{MAX_ATTEMPTS})")
            time.sleep(delay)
        raise LLMError(f"{cfg.provider}/{cfg.model} failed: {last_err[:500]}")

    def _log(self, cfg: RoleConfig, body: Dict[str, Any], prompt_version: str | None, offer_id: str | None,
             status: Optional[int], data: Optional[Dict[str, Any]], err: Optional[str], elapsed_s: float) -> None:
        usage = (data or {}).get("usage") or {}
        tin, tout = usage.get("prompt_tokens"), usage.get("completion_tokens")
        cost = None
        if cfg.price_in is not None and tin is not None:
            cost = (tin * cfg.price_in + (tout or 0) * (cfg.price_out or 0)) / 1_000_000
        response = None
        if data and "choices" in data:
            message = data["choices"][0]["message"]
            response = _content_text(message) or (json.dumps(message["tool_calls"]) if message.get("tool_calls") else "")
        try:
            self._log_call({
                "role": cfg.role, "provider": cfg.provider, "model": cfg.model,
                "prompt_version": prompt_version, "offer_id": offer_id,
                "status": "ok" if data is not None else "error", "http_status": status,
                "input_tokens": tin, "output_tokens": tout, "latency_ms": int(elapsed_s * 1000),
                "cost_usd": cost, "error": err,
                # embeddings: log the input size, not the vectors
                "request": json.dumps(body.get("messages") or {"inputs": len(body.get("input", []))}, ensure_ascii=False),
                "response": response,
            })
        except Exception as e:  # logging must never break a call
            logger.warning(f"[llm] could not log call: {e}")


llm = LLMPort()


if __name__ == "__main__":
    import tempfile

    class FakeResp:
        def __init__(self, status: int, payload: Any, headers: Dict[str, str] | None = None):
            self.status_code, self._payload = status, payload
            self.text = json.dumps(payload)
            self.headers = headers or {}

        def json(self):
            return self._payload

    def chat(content: str) -> FakeResp:
        return FakeResp(200, {"choices": [{"message": {"content": content}}],
                              "usage": {"prompt_tokens": 10, "completion_tokens": 5}})

    class Sheet(BaseModel):
        title: str
        skills: List[str]

    with tempfile.TemporaryDirectory() as d:
        logged: List[Dict[str, Any]] = []
        cfg_path = Path(d) / "models.toml"
        cfg_path.write_text(
            '[providers.p]\nbase_url = "http://x/v1"\napi_key_env = ""\nstructured = "json_schema"\n'
            '[providers.q]\nbase_url = "http://y/v1"\napi_key_env = ""\nstructured = "prompt"\n'
            '[roles.extract]\nprovider = "p"\nmodel = "m1"\nparams = { temperature = 0.1 }\n'
            '[roles.write]\nprovider = "q"\nmodel = "m2"\n'
            '[prices."m1"]\ninput = 1.0\noutput = 2.0\n', encoding="utf-8")
        BACKOFF_S = (0, 0)

        def calls():
            return logged

        # 1. structured with json_schema, valid on first try; cost from prices
        sent: List[Dict[str, Any]] = []
        port = LLMPort(post=lambda url, json, **kw: (sent.append(json), chat('{"title":"DE","skills":["SQL"]}'))[1],
                       log=logged.append, config_path=cfg_path)
        s = port.structured("x", Sheet, role="extract", prompt_version="v1", offer_id="o1")
        assert s.title == "DE" and sent[0]["response_format"]["type"] == "json_schema" and sent[0]["temperature"] == 0.1
        row = calls()[-1]
        assert (row["status"], row["input_tokens"], row["prompt_version"], row["offer_id"]) == ("ok", 10, "v1", "o1")
        assert abs(row["cost_usd"] - (10 * 1.0 + 5 * 2.0) / 1e6) < 1e-12

        # 2. prompt mode: schema goes in the prompt; invalid JSON then one successful repair
        answers = iter(["not json", '```json\n{"title":"X","skills":[]}\n```'])
        sent.clear()
        port = LLMPort(post=lambda url, json, **kw: (sent.append(json), chat(next(answers)))[1], log=logged.append, config_path=cfg_path)
        assert port.structured("x", Sheet, role="write").title == "X"
        assert "response_format" not in sent[0] and "JSON schema" in sent[0]["messages"][-1]["content"]
        assert sent[1]["messages"][-2] == {"role": "assistant", "content": "not json"}

        # 3. two bad answers -> StructuredOutputError
        port = LLMPort(post=lambda *a, **kw: chat("nope"), log=logged.append, config_path=cfg_path)
        try:
            port.structured("x", Sheet, role="extract")
            raise AssertionError("expected StructuredOutputError")
        except StructuredOutputError:
            pass

        # 4. 503 then OK: retried, both attempts logged
        seq = iter([FakeResp(503, {"error": "busy"}), chat("hi")])
        n = len(calls())
        port = LLMPort(post=lambda *a, **kw: next(seq), log=logged.append, config_path=cfg_path)
        assert port.complete("x", role="extract") == "hi"
        assert [r["status"] for r in calls()[n:]] == ["error", "ok"]

        # 4b. 429 with Retry-After: wait what the provider says, not the fixed backoff
        slept = []
        _real_sleep, time.sleep = time.sleep, slept.append
        seq = iter([FakeResp(429, {"error": "tokens per minute"}, {"retry-after": "2.5"}), chat("hi")])
        port = LLMPort(post=lambda *a, **kw: next(seq), log=logged.append, config_path=cfg_path)
        assert port.complete("x", role="extract") == "hi" and slept == [3.0], slept
        time.sleep = _real_sleep

        # 5. daily quota: no retry
        tries = []
        port = LLMPort(post=lambda *a, **kw: (tries.append(1), FakeResp(429, {"error": "GenerateRequestsPerDayPerProjectPerModel"}))[1],
                       log=logged.append, config_path=cfg_path)
        try:
            port.complete("x", role="extract")
            raise AssertionError("expected QuotaExhausted")
        except QuotaExhausted:
            assert len(tries) == 1

        # 6. env override + content blocks
        os.environ["LLM_EXTRACT_MODEL"] = "m9"
        port = LLMPort(post=lambda url, json, **kw: FakeResp(200, {"choices": [{"message": {"content": [{"type": "text", "text": "a"}, {"type": "text", "text": "b"}]}}]}),
                       log=logged.append, config_path=cfg_path)
        assert port.config("extract").model == "m9" and port.complete("x", role="extract") == "ab"
        del os.environ["LLM_EXTRACT_MODEL"]

        # 7. api key: first env var set wins; a provider needing a key fails clearly without one
        cfg_path.write_text(cfg_path.read_text().replace('[providers.p]\nbase_url = "http://x/v1"\napi_key_env = ""',
                            '[providers.p]\nbase_url = "http://x/v1"\napi_key_env = ["PORT_TEST_A", "PORT_TEST_B"]'))
        os.environ["PORT_TEST_B"] = "kb"
        assert port.config("extract").api_key == "kb"
        del os.environ["PORT_TEST_B"]
        try:
            port.config("extract")
            raise AssertionError("expected LLMError")
        except LLMError as e:
            assert "PORT_TEST_A" in str(e)

        # 7b. respond(): tools are sent, tool calls come back and are logged
        sent.clear()
        call = {"id": "c1", "type": "function", "function": {"name": "python", "arguments": '{"code": "1+1"}'}}
        port = LLMPort(post=lambda url, json, **kw: (sent.append(json), FakeResp(200, {"choices": [{"message": {"role": "assistant", "content": None, "tool_calls": [call]}}]}))[1],
                       log=logged.append, config_path=cfg_path)
        os.environ["PORT_TEST_A"] = "ka"
        msg = port.respond("x", role="extract", tools=[{"type": "function", "function": {"name": "python"}}])
        del os.environ["PORT_TEST_A"]
        assert msg["tool_calls"][0]["id"] == "c1" and sent[0]["tools"][0]["function"]["name"] == "python"
        assert '"c1"' in calls()[-1]["response"]

        # 8. [defaults]: roles without provider/model inherit them; a pinned role keeps its own
        d_path = Path(d) / "defaults.toml"
        d_path.write_text(
            '[defaults]\nprovider = "p"\nmodel = "dm"\n'
            '[providers.p]\nbase_url = "http://x/v1"\napi_key_env = ""\n'
            '[providers.q]\nbase_url = "http://y/v1"\napi_key_env = ""\n'
            '[roles.chat]\nparams = { temperature = 0.3 }\n'
            '[roles.embed]\nprovider = "q"\nmodel = "em"\n', encoding="utf-8")
        p8 = LLMPort(config_path=d_path, log=logged.append)
        assert (p8.config("chat").provider, p8.config("chat").model, p8.config("chat").params) == ("p", "dm", {"temperature": 0.3})
        assert (p8.config("embed").provider, p8.config("embed").model) == ("q", "em")
        os.environ["LLM_DEFAULT_MODEL"] = "env-dm"  # env default beats [defaults], not a pinned role
        assert p8.config("chat").model == "env-dm" and p8.config("embed").model == "em"
        del os.environ["LLM_DEFAULT_MODEL"]
        os.environ["LLM_CHAT_PROVIDER"] = "nope"
        try:
            p8.config("chat")
            raise AssertionError("expected LLMError")
        except LLMError as e:
            assert "unknown provider 'nope'" in str(e)
        del os.environ["LLM_CHAT_PROVIDER"]

        assert prompt_version("abc") == prompt_version("abc") != prompt_version("abd")
    print("port ok")
