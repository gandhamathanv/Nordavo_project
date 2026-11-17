"""Helpdesk client: retries on 503, waits on 429, never retries 409, careful with lost POST responses."""

import httpx
import pytest

from roosterly_agent.helpdesk import (
    AlreadyHandled,
    FatalError,
    HelpdeskClient,
    RateLimiter,
    Unavailable,
    ValidationFailed,
)

PAYLOAD = {"language": "nl", "category": "question", "priority": "P4", "reason": "r", "draft_reply": "x"}


def make_client(responses, sleeps=None, **kw):
    """responses: list of httpx.Response or Exception, consumed in order. Records requests."""
    seen = []
    queue = list(responses)

    def handler(request: httpx.Request):
        seen.append((request.method, request.url.path))
        item = queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    sleeps = sleeps if sleeps is not None else []
    client = HelpdeskClient(
        "https://helpdesk.test/functions/v1/helpdesk", "key", "me@example.com",
        transport=httpx.MockTransport(handler), sleep=sleeps.append, **kw,
    )
    return client, seen, sleeps


def err(status, code, **extra):
    return httpx.Response(status, json={"error": code, "message": code, **extra})


def test_503_is_retried_then_succeeds():
    client, seen, sleeps = make_client([err(503, "service_unavailable"), err(503, "service_unavailable"),
                                        httpx.Response(200, json={"ok": True})])
    assert client.send_decision("T001", "reply", PAYLOAD) == "sent"
    assert len([s for s in seen if s[0] == "POST"]) == 3
    assert client.stats["503"] == 2
    assert len([s for s in sleeps if s > 0.4]) >= 2  # backoff sleeps happened


def test_503_gives_up_after_max_attempts():
    client, _, _ = make_client([err(503, "service_unavailable")] * 3, max_attempts=3)
    with pytest.raises(Unavailable):
        client.status()


def test_429_waits_retry_after():
    limited = httpx.Response(429, headers={"Retry-After": "2"}, json={"error": "rate_limited"})
    client, _, sleeps = make_client([limited, httpx.Response(200, json={"mode": "practice"})])
    assert client.status()["mode"] == "practice"
    assert any(1.9 < s < 2.5 for s in sleeps)


def test_409_is_never_retried():
    client, seen, _ = make_client([err(409, "already_handled")])
    with pytest.raises(AlreadyHandled):
        client.send_decision("T001", "reply", PAYLOAD)
    assert len(seen) == 1


def test_422_carries_problems():
    client, _, _ = make_client([err(422, "validation_failed", problems=["reason is required"])])
    with pytest.raises(ValidationFailed) as exc:
        client.send_decision("T001", "reply", PAYLOAD)
    assert "reason is required" in str(exc.value)


def test_401_is_fatal():
    client, _, _ = make_client([err(401, "unauthorized")])
    with pytest.raises(FatalError):
        client.status()


def test_lost_post_response_is_not_resent_when_ticket_is_handled():
    """Connection drops after the server saved the reply: we must not send a second answer."""
    client, seen, _ = make_client([
        httpx.ReadTimeout("timeout"),
        httpx.Response(200, json={"id": "T001", "handled": {"action": "reply"}}),
    ])
    assert client.send_decision("T001", "reply", PAYLOAD) == "sent_unconfirmed_response"
    assert seen == [("POST", "/functions/v1/helpdesk/tickets/T001/reply"),
                    ("GET", "/functions/v1/helpdesk/tickets/T001")]


def test_lost_post_is_resent_when_ticket_still_open():
    client, seen, _ = make_client([
        httpx.ConnectError("reset"),
        httpx.Response(200, json={"id": "T001", "handled": None}),
        httpx.Response(200, json={"ok": True}),
    ])
    assert client.send_decision("T001", "reply", PAYLOAD) == "sent"
    assert [m for m, _ in seen] == ["POST", "GET", "POST"]


def test_pagination_follows_cursor():
    client, seen, _ = make_client([
        httpx.Response(200, json={"tickets": [{"id": "T001"}, {"id": "T002"}], "next_cursor": "T002"}),
        httpx.Response(200, json={"tickets": [{"id": "T003"}], "next_cursor": None}),
    ])
    assert [t["id"] for t in client.list_tickets()] == ["T001", "T002", "T003"]
    assert len(seen) == 2


def test_rate_limiter_spaces_calls():
    now = [0.0]
    slept = []

    def sleep(s):
        slept.append(s)
        now[0] += s

    limiter = RateLimiter(4, clock=lambda: now[0], sleep=sleep)
    for _ in range(5):
        limiter.wait()
    assert now[0] == pytest.approx(1.0)  # 5 calls take 1s at 4/s -> never more than 5 in a second
