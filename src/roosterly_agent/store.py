"""Local state in `.state/agent.sqlite`: a write-ahead journal of decisions and an LLM response cache.

Journal protocol (one row per ticket):
    1. before the POST:  status = "pending", with the exact payload we are about to send
    2. after the POST:   status = "sent" (or "already_handled" on a 409)
If the process dies between 1 and 2, the next run finds the "pending" row, asks the helpdesk whether the
ticket is handled, and either marks it sent or re-sends the same payload. The helpdesk itself stays the
source of truth: only tickets it reports as open are ever acted on.

Every write is committed immediately (sqlite autocommit, synchronous=FULL), so a row exists on disk
before the network call it protects.
"""

from __future__ import annotations

import fcntl
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Store:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(path, isolation_level=None)  # autocommit
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA synchronous=FULL")
        self._db.executescript(
            """
            CREATE TABLE IF NOT EXISTS journal (
                ticket_id    TEXT PRIMARY KEY,
                content_hash TEXT NOT NULL,
                action       TEXT NOT NULL,
                payload      TEXT NOT NULL,
                status       TEXT NOT NULL,   -- pending | sent | already_handled
                updated_at   TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS llm_cache (
                key        TEXT PRIMARY KEY,
                response   TEXT NOT NULL,
                usage      TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )

    # ------------------------------------------------------------------ journal

    def mark_pending(self, ticket_id: str, content_hash: str, action: str, payload: dict[str, Any]) -> None:
        self._db.execute(
            "INSERT INTO journal VALUES (?, ?, ?, ?, 'pending', ?) "
            "ON CONFLICT(ticket_id) DO UPDATE SET content_hash=excluded.content_hash, action=excluded.action, "
            "payload=excluded.payload, status='pending', updated_at=excluded.updated_at",
            (ticket_id, content_hash, action, json.dumps(payload, ensure_ascii=False), _now()),
        )

    def mark_done(self, ticket_id: str, status: str = "sent") -> None:
        self._db.execute("UPDATE journal SET status=?, updated_at=? WHERE ticket_id=?", (status, _now(), ticket_id))

    def get(self, ticket_id: str) -> dict[str, Any] | None:
        row = self._db.execute("SELECT * FROM journal WHERE ticket_id=?", (ticket_id,)).fetchone()
        if row is None:
            return None
        out = dict(row)
        out["payload"] = json.loads(out["payload"])
        return out

    def pending(self) -> list[dict[str, Any]]:
        rows = self._db.execute("SELECT ticket_id FROM journal WHERE status='pending'").fetchall()
        return [self.get(r["ticket_id"]) for r in rows]  # type: ignore[misc]

    def clear_journal(self) -> None:
        self._db.execute("DELETE FROM journal")

    # ---------------------------------------------------------------- LLM cache

    def cache_get(self, key: str) -> tuple[str, dict[str, Any]] | None:
        row = self._db.execute("SELECT response, usage FROM llm_cache WHERE key=?", (key,)).fetchone()
        return (row["response"], json.loads(row["usage"])) if row else None

    def cache_put(self, key: str, response: str, usage: dict[str, Any]) -> None:
        self._db.execute(
            "INSERT OR REPLACE INTO llm_cache VALUES (?, ?, ?, ?)", (key, response, json.dumps(usage), _now())
        )


@contextmanager
def single_instance(lock_path: Path) -> Iterator[None]:
    """Refuse to start if another run holds the lock (two runs could both answer one ticket)."""
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with open(lock_path, "w") as fh:
        try:
            fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SystemExit("Another agent run is already active (lock: .state/agent.lock). Exiting.")
        try:
            yield
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)
