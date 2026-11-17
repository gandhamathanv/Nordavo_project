"""LLM wrapper without network: free-tier 429s, overload, daily quota, invalid JSON, cache."""

from types import SimpleNamespace

import pytest
from google.genai import errors
from pydantic import BaseModel

from roosterly_agent.llm import GeminiLLM, LLMQuotaExhausted, LLMUnavailable
from roosterly_agent.store import Store


class Out(BaseModel):
    answer: str


def api_error(code, status, details=None):
    return errors.APIError(code, {"error": {"code": code, "message": status, "status": status, "details": details or []}})


def ok(text='{"answer": "ja"}'):
    meta = SimpleNamespace(prompt_token_count=100, candidates_token_count=10, thoughts_token_count=0)
    return SimpleNamespace(text=text, usage_metadata=meta)


def make_llm(responses, tmp_path=None):
    sleeps = []
    llm = GeminiLLM("test-key", "test-model", Store(tmp_path / "c.sqlite") if tmp_path else None,
                    rpm=6000, sleep=sleeps.append)
    queue = list(responses)
    calls = []

    def generate_content(**kw):
        calls.append(kw)
        item = queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    llm._client = SimpleNamespace(models=SimpleNamespace(generate_content=generate_content))
    return llm, calls, sleeps


def gen(llm):
    return llm.generate(system="s", user="u", schema=Out, purpose="test")


def test_per_minute_429_waits_retry_delay_then_succeeds():
    retry = [{"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "7s"}]
    llm, calls, sleeps = make_llm([api_error(429, "RESOURCE_EXHAUSTED", retry), ok()])
    obj, usage = gen(llm)
    assert obj.answer == "ja" and usage["input_tokens"] == 100
    assert any(7.9 < s < 8.1 for s in sleeps)


def test_overloaded_model_backs_off_and_retries():
    llm, calls, sleeps = make_llm([api_error(503, "UNAVAILABLE"), api_error(504, "DEADLINE_EXCEEDED"), ok()])
    assert gen(llm)[0].answer == "ja" and len(calls) == 3


def test_daily_quota_stops_immediately():
    quota = [{"@type": "type.googleapis.com/google.rpc.QuotaFailure",
              "violations": [{"quotaId": "GenerateRequestsPerDayPerProjectPerModel-FreeTier"}]}]
    llm, calls, _ = make_llm([api_error(429, "RESOURCE_EXHAUSTED", quota)])
    with pytest.raises(LLMQuotaExhausted):
        gen(llm)
    assert len(calls) == 1


def test_non_retryable_error_is_raised():
    llm, calls, _ = make_llm([api_error(400, "INVALID_ARGUMENT")])
    with pytest.raises(LLMUnavailable):
        gen(llm)
    assert len(calls) == 1


def test_invalid_json_is_asked_again():
    llm, calls, _ = make_llm([ok("not json"), ok()])
    assert gen(llm)[0].answer == "ja" and len(calls) == 2


def test_gives_up_after_max_attempts():
    llm, _, _ = make_llm([api_error(503, "UNAVAILABLE")] * 8)
    with pytest.raises(LLMUnavailable):
        gen(llm)


def test_cache_hit_skips_the_model(tmp_path):
    llm, calls, _ = make_llm([ok()], tmp_path)
    gen(llm)
    obj, usage = gen(llm)
    assert obj.answer == "ja" and len(calls) == 1 and usage["cache_hits"] == 1
