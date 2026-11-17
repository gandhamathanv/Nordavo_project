"""Thin wrapper around Gemini: structured JSON output, rate limiting, retries, caching, token accounting.

The model gets no tools and cannot call the helpdesk. It can only return JSON matching a pydantic schema,
which is validated here before any code looks at it.
"""

from __future__ import annotations

import hashlib
import json
import random
import re
import time
from typing import Any, Callable, TypeVar

from google import genai
from google.genai import errors, types
from pydantic import BaseModel, ValidationError

from .helpdesk import RateLimiter
from .store import Store

T = TypeVar("T", bound=BaseModel)

RETRYABLE = {408, 429, 500, 502, 503, 504}


class LLMUnavailable(RuntimeError):
    """The model could not be reached or kept returning invalid output. The ticket stays open."""


class LLMQuotaExhausted(LLMUnavailable):
    """The free tier's daily request quota is used up. Retrying today is pointless: stop the run."""


class GeminiLLM:
    def __init__(self, api_key: str, model: str, store: Store | None, *, rpm: int = 10,
                 thinking_budget: int | None = None, max_attempts: int = 8, timeout_s: int = 60,
                 sleep: Callable[[float], None] = time.sleep):
        # The SDK's own retries are switched off: retrying happens below, in one visible place,
        # with free-tier aware delays. A timeout stops one slow call from hanging the run.
        self._client = genai.Client(api_key=api_key, http_options=types.HttpOptions(
            timeout=timeout_s * 1000, retry_options=types.HttpRetryOptions(attempts=1)))
        self.model = model
        self._store = store
        self._limiter = RateLimiter(rpm / 60.0, sleep=sleep)
        self._thinking_budget = thinking_budget
        self._max_attempts = max_attempts
        self._sleep = sleep

    def generate(self, *, system: str, user: str, schema: type[T], purpose: str) -> tuple[T, dict[str, int]]:
        """Return (validated object, token usage). Raises LLMUnavailable after retries."""
        key = self._cache_key(system, user, schema)
        if self._store and (hit := self._store.cache_get(key)):
            text, usage = hit
            return schema.model_validate_json(text), {**usage, "cache_hits": 1}

        config = types.GenerateContentConfig(
            system_instruction=system,
            temperature=0,
            response_mime_type="application/json",
            response_schema=schema,
            thinking_config=(types.ThinkingConfig(thinking_budget=self._thinking_budget)
                             if self._thinking_budget is not None else None),
        )
        last_error = ""
        for attempt in range(1, self._max_attempts + 1):
            self._limiter.wait()
            try:
                resp = self._client.models.generate_content(model=self.model, contents=user, config=config)
                obj = schema.model_validate_json(resp.text or "")
            except errors.APIError as exc:
                last_error = f"{exc.code} {exc.status}"
                if exc.code == 429 and "perday" in str(exc.details or exc).lower().replace("_", ""):
                    raise LLMQuotaExhausted(f"{purpose}: Gemini daily quota used up ({exc.message})") from exc
                if exc.code not in RETRYABLE:
                    raise LLMUnavailable(f"{purpose}: Gemini error {last_error}: {exc.message}") from exc
                self._sleep(self._retry_delay(exc, attempt))
                continue
            except (ValidationError, ValueError) as exc:  # malformed JSON: ask again
                last_error = f"invalid output: {str(exc)[:120]}"
                continue
            except Exception as exc:  # network errors from the SDK's HTTP layer
                last_error = f"{type(exc).__name__}: {str(exc)[:120]}"
                self._sleep(min(2 ** attempt, 30))
                continue

            meta = resp.usage_metadata
            usage = {
                "llm_calls": 1,
                "input_tokens": (meta.prompt_token_count or 0) if meta else 0,
                "output_tokens": (meta.candidates_token_count or 0) if meta else 0,
                "thinking_tokens": (meta.thoughts_token_count or 0) if meta else 0,
            }
            if self._store:
                self._store.cache_put(key, obj.model_dump_json(), usage)
            return obj, usage
        raise LLMUnavailable(f"{purpose}: gave up after {self._max_attempts} attempts ({last_error})")

    def _cache_key(self, system: str, user: str, schema: type[BaseModel]) -> str:
        blob = json.dumps([self.model, self._thinking_budget, system, user, schema.model_json_schema()],
                          ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(blob.encode()).hexdigest()

    @staticmethod
    def _retry_delay(exc: errors.APIError, attempt: int) -> float:
        """429: wait as long as the server's retryDelay says (per-minute quota), else 15s.
        5xx / timeouts (model overloaded): exponential backoff 2s, 4s, 8s ... capped at 60s, with jitter."""
        m = re.search(r"retryDelay['\"]?\s*[:=]\s*['\"]?(\d+(?:\.\d+)?)s", str(exc.details or exc))
        if m:
            return float(m.group(1)) + 1
        if exc.code == 429:
            return 15.0 + random.random() * 5
        return min(2 ** attempt, 60) * (1 + random.random() / 2)


def add_usage(total: dict[str, int], usage: dict[str, Any]) -> None:
    for k, v in usage.items():
        if isinstance(v, int):
            total[k] = total.get(k, 0) + v
