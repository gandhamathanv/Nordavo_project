"""The agent loop: read open tickets, decide, send exactly one decision per ticket, log one line per ticket.

No-double-answer guarantees, in layers:
  1. Only tickets the helpdesk lists as open are processed.
  2. Right before each POST the ticket is fetched again; if it is already handled we skip it.
  3. A write-ahead journal row ("pending" + payload) is committed before the POST and marked "sent" after.
     After a crash, a pending ticket that is no longer open was answered: mark it sent, do nothing.
     A pending ticket that is still open never got its answer: re-send the same payload.
  4. A 409 from the helpdesk is recorded and never retried.
  5. A file lock prevents two runs at the same time (see cli.py).
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from .guards import redact
from .helpdesk import AlreadyHandled, FatalError, HelpdeskClient, HelpdeskError, Unavailable, ValidationFailed, is_handled
from .llm import LLMQuotaExhausted, LLMUnavailable, add_usage
from .pipeline import Pipeline
from .schemas import Decision, Ticket
from .store import Store


def content_hash(ticket: Ticket) -> str:
    return hashlib.sha256(f"{ticket.received_at}\n{ticket.subject}\n{ticket.body}".encode()).hexdigest()[:16]


def _base_subject(subject: str) -> str:
    return re.sub(r"^\s*((re|fw|fwd|aw)\s*:\s*)+", "", subject or "", flags=re.I).strip().lower()


def related_tickets(tickets: list[Ticket]) -> dict[str, list[str]]:
    """Link replies ("Re: X") to the ticket with subject X, in both directions."""
    by_subject: dict[str, list[str]] = {}
    for t in tickets:
        if (base := _base_subject(t.subject)):
            by_subject.setdefault(base, []).append(t.id)
    return {t.id: [o for o in by_subject.get(_base_subject(t.subject), []) if o != t.id] for t in tickets}


def scrub(value: Any) -> Any:
    """Remove payment details from every string in a log record."""
    if isinstance(value, str):
        return redact(value)[0]
    if isinstance(value, dict):
        return {k: scrub(v) for k, v in value.items()}
    if isinstance(value, list):
        return [scrub(v) for v in value]
    return value


class Runner:
    def __init__(self, helpdesk: HelpdeskClient, store: Store, pipeline: Pipeline, logs_dir: Path, *,
                 dry_run: bool = False, console: Callable[[str], None] = print,
                 prices: tuple[float | None, float | None] = (None, None)):
        self.helpdesk = helpdesk
        self.store = store
        self.pipeline = pipeline
        self.dry_run = dry_run
        self.console = console
        self.prices = prices
        self.run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        logs_dir.mkdir(parents=True, exist_ok=True)
        self.log_path = logs_dir / f"{'dryrun' if dry_run else 'run'}-{self.run_id}.jsonl"

    def run(self, *, limit: int | None = None, only: list[str] | None = None) -> dict[str, Any]:
        tickets = [Ticket(**t) for t in self.helpdesk.list_tickets("open")]
        self._reconcile({t.id for t in tickets})
        related = related_tickets(tickets)
        if only:
            tickets = [t for t in tickets if t.id in only]
        if limit is not None:
            tickets = tickets[:limit]

        self.console(f"{len(tickets)} open ticket(s) to process ({'dry run, nothing is sent' if self.dry_run else 'live'}).")
        outcomes: Counter[str] = Counter()
        actions: Counter[str] = Counter()
        usage: dict[str, int] = {}
        stopped_early = None
        for ticket in tickets:
            record = self._process(ticket, related.get(ticket.id, []))
            if record["outcome"] == "left_open_llm_quota":
                stopped_early = "LLM daily quota used up; remaining tickets stay open. Re-run when it resets."
                self.console(stopped_early)
                outcomes[record["outcome"]] += 1
                break
            outcomes[record["outcome"]] += 1
            if record["outcome"] in ("sent", "sent_unconfirmed_response", "dry_run"):
                actions[record["action"]] += 1
            add_usage(usage, record.get("llm", {}))

        summary = {"run_id": self.run_id, "log": str(self.log_path), "processed": len(tickets),
                   "actions": dict(actions), "outcomes": dict(outcomes), "llm_usage": usage}
        if stopped_early:
            summary["stopped_early"] = stopped_early
        if all(self.prices) and tickets:
            pin, pout = self.prices
            cost = (usage.get("input_tokens", 0) * pin
                    + (usage.get("output_tokens", 0) + usage.get("thinking_tokens", 0)) * pout) / 1e6
            summary["estimated_cost_usd"] = round(cost, 4)
            summary["estimated_cost_per_100_tickets_usd"] = round(cost * 100 / len(tickets), 4)
        return summary

    # ------------------------------------------------------------------ internals

    def _reconcile(self, open_ids: set[str]) -> None:
        """Finish what a crashed run left half-done (journal rows still 'pending')."""
        for row in self.store.pending():
            if row["ticket_id"] not in open_ids:
                # The helpdesk no longer lists it as open, so the POST before the crash was saved.
                self.store.mark_done(row["ticket_id"], "sent")
                self.console(f"{row['ticket_id']}: recovered after crash, decision had been delivered.")
            # Still open: the POST never landed. _process() re-sends the journalled payload.

    def _process(self, ticket: Ticket, related: list[str]) -> dict[str, Any]:
        started = time.monotonic()
        http_before = Counter(self.helpdesk.stats)
        chash = content_hash(ticket)
        journal = self.store.get(ticket.id)
        record: dict[str, Any] = {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                                  "run_id": self.run_id, "mode": "dry_run" if self.dry_run else "live",
                                  "ticket_id": ticket.id}
        try:
            if journal and journal["status"] == "pending" and journal["content_hash"] == chash:
                # Resume after a crash: send exactly what we decided before, no new LLM call.
                action, payload = journal["action"], journal["payload"]
                record.update(action=action, resumed_from_journal=True, **self._payload_fields(payload))
            else:
                decision = self.pipeline.decide(ticket, related)
                action, payload = decision.action, decision.payload
                record.update(self._decision_fields(decision))

            if self.dry_run:
                record["outcome"] = "dry_run"
            elif is_handled(self.helpdesk.get_ticket(ticket.id)):
                self.store.mark_done(ticket.id, "already_handled")
                record["outcome"] = "skipped_already_handled"
            else:
                self.store.mark_pending(ticket.id, chash, action, payload)
                record["outcome"] = self.helpdesk.send_decision(ticket.id, action, payload)
                self.store.mark_done(ticket.id, "sent")
        except AlreadyHandled as exc:
            self.store.mark_done(ticket.id, "already_handled")
            record.update(outcome="already_handled_409", error=str(exc))
        except ValidationFailed as exc:
            self.store.mark_done(ticket.id, "failed")  # nothing was saved; next run decides afresh
            record.update(outcome="validation_failed", error=str(exc))
        except LLMQuotaExhausted as exc:
            record.update(outcome="left_open_llm_quota", error=str(exc))
        except LLMUnavailable as exc:
            record.update(outcome="left_open_llm_unavailable", error=str(exc))
        except Unavailable as exc:
            record.update(outcome="left_open_helpdesk_unavailable", error=str(exc))
        except FatalError:
            raise
        except HelpdeskError as exc:
            record.update(outcome="left_open_helpdesk_error", error=str(exc))

        http = Counter(self.helpdesk.stats)
        http.subtract(http_before)
        record["http"] = {k: v for k, v in http.items() if v}
        record["duration_s"] = round(time.monotonic() - started, 2)
        record = scrub(record)
        with self.log_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        self.console(self._line(record))
        return record

    @staticmethod
    def _payload_fields(payload: dict[str, Any]) -> dict[str, Any]:
        keys = ("language", "category", "priority", "confidence", "reason", "draft_reply", "handoff_note")
        return {k: payload[k] for k in keys if k in payload}

    def _decision_fields(self, d: Decision) -> dict[str, Any]:
        out = {"action": d.action, **self._payload_fields(d.payload), "route": d.route, "faq_ids": d.faq_ids,
               "rule_triggers": d.rule_triggers, "flags": d.flags, "summary_en": d.summary_en, "llm": d.usage}
        if d.back_translation_en:
            out["back_translation_en"] = d.back_translation_en
        if d.checks:
            out["checks"] = d.checks
        return out

    @staticmethod
    def _line(r: dict[str, Any]) -> str:
        route = (r.get("route") or [""])[0]
        return (f"{r['ticket_id']}  {r.get('action', '-'):7} {r.get('language', '--')} {r.get('category', '-'):15} "
                f"{r.get('priority', '--')}  {r['outcome']:24} {route[:70]}")
