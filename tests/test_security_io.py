"""AI-security audit: what crosses the process boundary. Helpdesk URLs, log records, console lines, the LLM retry loop."""

import json
from types import SimpleNamespace

import httpx
import pytest
from pydantic import BaseModel

from roosterly_agent.helpdesk import HelpdeskClient
from roosterly_agent.llm import GeminiLLM, LLMUnavailable
from roosterly_agent.runner import Runner, scrub
from roosterly_agent.store import Store
from security_helpers import gap

EVIL_ID = "T1/../../practice/reset"


def recording_client():
    seen: list[tuple[str, str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append((request.method, request.url.path, request.url.query.decode()))
        return httpx.Response(200, json={"id": "T1", "handled": None})

    client = HelpdeskClient("https://h.test/functions/v1/helpdesk", "k", "e@x.nl",
                            transport=httpx.MockTransport(handler), sleep=lambda s: None)
    return client, seen


# ------------------------------------------------------------------ SEC-11: server-supplied ticket id in a URL path

@pytest.mark.parametrize("ticket_id", [
    pytest.param(EVIL_ID, marks=gap("SEC-11", "ticket id is interpolated into the path unvalidated")),
    pytest.param("T1?status=all", marks=gap("SEC-11", "ticket id is interpolated into the path unvalidated")),
    pytest.param("T1/handoff", marks=gap("SEC-11", "ticket id is interpolated into the path unvalidated")),
])
def test_ticket_id_cannot_change_which_endpoint_is_called(ticket_id):
    """The id comes from the helpdesk, a trusted-but-external source. A hostile or buggy record must not be able to
    steer a POST at another endpoint such as /practice/reset."""
    client, seen = recording_client()
    client.get_ticket(ticket_id)
    client.send_decision(ticket_id, "close", {"x": 1})
    for method, path, query in seen:
        tail = path.split("/helpdesk", 1)[1]
        assert tail.count("/") <= 3 and tail.startswith("/tickets/"), (method, path)
        assert "practice" not in tail and query == "", (method, path, query)


def test_ordinary_ticket_ids_still_work():
    client, seen = recording_client()
    client.send_decision("T001", "reply", {"x": 1})
    assert seen == [("POST", "/functions/v1/helpdesk/tickets/T001/reply", "")]


# ------------------------------------------------------------------ logs

def test_scrub_redacts_nested_log_records():
    record = {"reason": "kaart 4111 1111 1111 1111", "checks": {"problems": ["IBAN NL91 ABNA 0417 1643 00"]},
              "list": [{"draft_reply": "CVC 123"}], "n": 4111111111111111}
    out = json.dumps(scrub(record))
    assert "4111 1111" not in out and "0417" not in out and "CVC 123" not in out


@pytest.mark.parametrize("line", [
    pytest.param("\x1b[2J\x1b[31mT001 fake line", marks=gap("SEC-13", "model/ticket text is printed to the terminal raw")),
    pytest.param("T001 \x07\x08\x08\x08spoofed", marks=gap("SEC-13", "model/ticket text is printed to the terminal raw")),
])
def test_console_line_strips_terminal_control_characters(line):
    """`route` contains LLM-written text (the uncovered question, paraphrased from the ticket)."""
    out = Runner._line({"ticket_id": "T001", "outcome": "sent", "action": "handoff", "route": [line]})
    assert not any(ord(ch) < 32 and ch not in "\t" for ch in out)


# ------------------------------------------------------------------ LLM wrapper (no network)

class Out(BaseModel):
    answer: str


def llm_with(responses, sleeps):
    llm = GeminiLLM("test-key", "test-model", None, rpm=6000, sleep=sleeps.append, max_attempts=8)
    queue = list(responses)
    calls = []

    def generate_content(**kw):
        calls.append(kw)
        return queue.pop(0)

    llm._client = SimpleNamespace(models=SimpleNamespace(generate_content=generate_content))
    return llm, calls


def reply(text):
    meta = SimpleNamespace(prompt_token_count=1, candidates_token_count=1, thoughts_token_count=0)
    return SimpleNamespace(text=text, usage_metadata=meta)


def test_hostile_or_garbage_model_output_never_leaves_the_wrapper_unvalidated():
    sleeps: list[float] = []
    llm, calls = llm_with([reply("ignore previous instructions"), reply('{"answer": 5}'), reply('{"answer": "ok"}')], sleeps)
    obj, _ = llm.generate(system="s", user="u", schema=Out, purpose="t")
    assert obj.answer == "ok" and len(calls) == 3


def test_invalid_output_is_retried_a_bounded_number_of_times():
    llm, calls = llm_with([reply("nope")] * 8, [])
    with pytest.raises(LLMUnavailable):
        llm.generate(system="s", user="u", schema=Out, purpose="t")
    assert len(calls) == 8  # bounded: 8 attempts, so a hostile ticket costs at most 8 quota calls per LLM step


def test_invalid_output_retries_back_off():
    """SEC-10 (fixed): each malformed answer burns free-tier quota, so retries pause 1s, 2s, 4s, 8s..."""
    sleeps: list[float] = []
    llm, _ = llm_with([reply("nope")] * 8, sleeps)
    with pytest.raises(LLMUnavailable):
        llm.generate(system="s", user="u", schema=Out, purpose="t")
    # The limiter's own ~10 ms spacing is not a backoff: a real one waits at least a second between attempts.
    assert any(delay >= 1 for delay in sleeps)


def test_cache_key_covers_the_whole_prompt(tmp_path):
    """Two tickets that differ only in the last character must not share a cache entry (no cross-ticket bleed)."""
    store = Store(tmp_path / "c.sqlite")
    llm = GeminiLLM("k", "m", store, rpm=6000, sleep=lambda s: None)
    assert llm._cache_key("sys", "ticket A", Out) != llm._cache_key("sys", "ticket B", Out)
    assert llm._cache_key("sys", "u", Out) != llm._cache_key("sys2", "u", Out)
