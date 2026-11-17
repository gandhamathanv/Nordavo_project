"""Client for the Roosterly helpdesk API (see docs/api_reference.md).

How errors are handled:
- 503  temporary failure, nothing was saved  -> retry with exponential backoff + jitter.
- 429  more than 5 calls/second              -> sleep `Retry-After` seconds, retry.
- 409  ticket already handled                -> never retried; raised as AlreadyHandled.
- 422  our request body is invalid           -> raised with `problems`; not retried (it is our bug).
- 400/401  bad key / missing email header    -> FatalError; the run stops.
- network error / timeout
    on a GET  -> retried like a 503.
    on a POST -> the decision may or may not have reached the server, so we never blindly re-send:
                 we ask the helpdesk whether the ticket is handled first (see send_decision).

A client-side limiter keeps us at 4 calls/second so we rarely see a 429 at all.
"""

from __future__ import annotations

import random
import threading
import time
from collections import Counter
from typing import Any, Callable

import httpx

ACTIONS = ("reply", "handoff", "close")


class HelpdeskError(Exception):
    def __init__(self, status: int, code: str, message: str = "", problems: list[str] | None = None):
        self.status = status
        self.code = code
        self.problems = problems or []
        detail = f"HTTP {status} {code}: {message}".strip()
        if self.problems:
            detail += " | " + "; ".join(self.problems)
        super().__init__(detail)


class AlreadyHandled(HelpdeskError):
    """409: the ticket already has a decision. A customer must never get two answers."""


class ValidationFailed(HelpdeskError):
    """422: a field is missing or invalid."""


class NotFound(HelpdeskError):
    """404: unknown endpoint or ticket id."""


class FatalError(HelpdeskError):
    """400/401: configuration problem (key, email header). Stop the run."""


class Unavailable(HelpdeskError):
    """Retries exhausted (503s, 429s or network errors)."""


class _DeliveryUnknown(Exception):
    """A POST failed at the network level: it may or may not have been saved."""


class RateLimiter:
    """Spaces calls at least 1/per_second seconds apart. Thread-safe."""

    def __init__(self, per_second: float, clock: Callable[[], float] = time.monotonic,
                 sleep: Callable[[float], None] = time.sleep):
        self.interval = 1.0 / per_second
        self._clock = clock
        self._sleep = sleep
        self._next = 0.0
        self._lock = threading.Lock()

    def wait(self) -> None:
        with self._lock:
            now = self._clock()
            if now < self._next:
                self._sleep(self._next - now)
                now = self._next
            self._next = now + self.interval


def is_handled(ticket: dict[str, Any]) -> bool:
    return bool(ticket.get("handled"))


class HelpdeskClient:
    def __init__(
        self,
        base_url: str,
        key: str,
        email: str,
        name: str | None = None,
        *,
        per_second: float = 4.0,
        max_attempts: int = 6,
        max_rate_limited: int = 10,
        timeout: float = 20.0,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ):
        headers = {"Authorization": f"Bearer {key}", "X-Candidate-Email": email, "Accept": "application/json"}
        if name:
            headers["X-Candidate-Name"] = name
        self._http = httpx.Client(base_url=base_url, headers=headers, timeout=timeout, transport=transport)
        self._limiter = RateLimiter(per_second, clock=clock, sleep=sleep)
        self._sleep = sleep
        self.max_attempts = max_attempts
        self.max_rate_limited = max_rate_limited
        self.stats: Counter[str] = Counter()  # calls, 503, 429, network_error, retries... (read by the runner)

    def close(self) -> None:
        self._http.close()

    # ---------------------------------------------------------------- endpoints

    def status(self) -> dict[str, Any]:
        return self._request("GET", "/status")

    def examples(self) -> list[dict[str, Any]]:
        return self._request("GET", "/examples")["examples"]

    def list_tickets(self, status: str = "open") -> list[dict[str, Any]]:
        """All tickets in the current set, following next_cursor until it is null."""
        tickets: list[dict[str, Any]] = []
        cursor: str | None = None
        while True:
            params = {"limit": 10, "status": status}
            if cursor:
                params["cursor"] = cursor
            page = self._request("GET", "/tickets", params=params)
            tickets.extend(page.get("tickets", []))
            cursor = page.get("next_cursor")
            if not cursor:
                return tickets

    def get_ticket(self, ticket_id: str) -> dict[str, Any]:
        return self._request("GET", f"/tickets/{ticket_id}")

    def reset(self) -> dict[str, Any]:
        return self._request("POST", "/practice/reset", retry_network=True)

    def send_decision(self, ticket_id: str, action: str, payload: dict[str, Any]) -> str:
        """POST one decision. Returns "sent", or "sent_unconfirmed_response" when the
        response was lost but the helpdesk confirms the ticket is now handled.

        Raises AlreadyHandled (409) without retrying.
        """
        if action not in ACTIONS:
            raise ValueError(f"unknown action {action!r}")
        for _ in range(self.max_attempts):
            try:
                self._request("POST", f"/tickets/{ticket_id}/{action}", body=payload, retry_network=False)
                return "sent"
            except _DeliveryUnknown:
                # The request may have been saved before the connection dropped.
                # Only send again if the helpdesk says the ticket is still open.
                if is_handled(self.get_ticket(ticket_id)):
                    return "sent_unconfirmed_response"
                self.stats["retries"] += 1
        raise Unavailable(0, "network_error", f"could not deliver decision for {ticket_id}")

    # ---------------------------------------------------------------- transport

    def _request(self, method: str, path: str, *, params: dict | None = None,
                 body: dict | None = None, retry_network: bool = True) -> Any:
        failures = 0       # 503s and network errors
        rate_limited = 0   # 429s
        while True:
            self._limiter.wait()
            self.stats["calls"] += 1
            try:
                resp = self._http.request(method, path, params=params, json=body)
            except httpx.TransportError as exc:  # includes timeouts and dropped connections
                self.stats["network_error"] += 1
                if not retry_network:
                    raise _DeliveryUnknown(str(exc)) from exc
                failures += 1
                if failures >= self.max_attempts:
                    raise Unavailable(0, "network_error", str(exc)) from exc
                self._backoff(failures)
                continue

            code = resp.status_code
            if code == 503:
                self.stats["503"] += 1
                failures += 1
                if failures >= self.max_attempts:
                    raise self._error(resp, Unavailable)
                self._backoff(failures)
                continue
            if code == 429:
                self.stats["429"] += 1
                rate_limited += 1
                if rate_limited > self.max_rate_limited:
                    raise self._error(resp, Unavailable)
                self.stats["retries"] += 1
                self._sleep(self._retry_after(resp))
                continue
            if 200 <= code < 300:
                return resp.json() if resp.content else {}
            raise self._error(resp)

    def _backoff(self, failures: int) -> None:
        """0.5s, 1s, 2s, 4s, 8s (capped) plus up to 50% jitter."""
        self.stats["retries"] += 1
        base = min(0.5 * 2 ** (failures - 1), 8.0)
        self._sleep(base * (1 + random.random() / 2))

    @staticmethod
    def _retry_after(resp: httpx.Response) -> float:
        try:
            return max(float(resp.headers.get("Retry-After", "1")), 0.0) + 0.1
        except ValueError:
            return 1.1

    @staticmethod
    def _error(resp: httpx.Response, cls: type[HelpdeskError] | None = None) -> HelpdeskError:
        try:
            data = resp.json()
        except ValueError:
            data = {}
        code = data.get("error", "unknown")
        message = data.get("message", resp.text[:200])
        problems = data.get("problems")
        if cls is None:
            cls = {409: AlreadyHandled, 422: ValidationFailed, 404: NotFound,
                   400: FatalError, 401: FatalError}.get(resp.status_code, HelpdeskError)
        return cls(resp.status_code, code, message, problems)
