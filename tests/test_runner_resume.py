"""Runner + real HTTP client against an in-memory helpdesk: crash safety and one answer per ticket."""

import json
import re

import httpx
import pytest

from roosterly_agent.helpdesk import HelpdeskClient
from roosterly_agent.runner import Runner, related_tickets
from roosterly_agent.schemas import Decision, Ticket
from roosterly_agent.store import Store


class FakeHelpdesk:
    """Stateful stand-in for the helpdesk. Answers 409 for a second decision on the same ticket."""

    def __init__(self, ids, fail_first_post_with_503=False):
        self.tickets = {i: {"id": i, "subject": f"s{i}", "body": f"b{i}", "received_at": "t",
                            "channel": "email", "customer_plan": "Basis", "handled": None} for i in ids}
        self.posts = []
        self.conflicts = 0
        self.fail_503 = fail_first_post_with_503

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path.split("/helpdesk")[1]
        if request.method == "GET" and path == "/tickets":
            open_ = [t for t in self.tickets.values() if not t["handled"]]
            return httpx.Response(200, json={"tickets": open_, "next_cursor": None})
        if m := re.fullmatch(r"/tickets/(\w+)", path):
            return httpx.Response(200, json=self.tickets[m.group(1)])
        if m := re.fullmatch(r"/tickets/(\w+)/(reply|handoff|close)", path):
            if self.fail_503:
                self.fail_503 = False
                return httpx.Response(503, json={"error": "service_unavailable"})
            t = self.tickets[m.group(1)]
            if t["handled"]:
                self.conflicts += 1
                return httpx.Response(409, json={"error": "already_handled"})
            t["handled"] = {"action": m.group(2), **json.loads(request.content)}
            self.posts.append(m.group(1))
            return httpx.Response(200, json={"ok": True})
        return httpx.Response(404, json={"error": "not_found"})


class FakePipeline:
    def __init__(self):
        self.calls = []

    def decide(self, ticket: Ticket, related=None) -> Decision:
        self.calls.append(ticket.id)
        payload = {"language": "nl", "category": "other", "priority": "P3", "reason": "r",
                   "handoff_note": "n", "confidence": 0.9}
        return Decision(ticket_id=ticket.id, action="handoff", payload=payload)


class CrashOnce(Store):
    """Store whose mark_done (or mark_pending) blows up once for one ticket, like a process crash."""

    def __init__(self, path, ticket, where):
        super().__init__(path)
        self.ticket, self.where, self.crashed = ticket, where, False

    def _maybe_crash(self, ticket_id, where):
        if ticket_id == self.ticket and where == self.where and not self.crashed:
            self.crashed = True
            raise RuntimeError("simulated crash")

    def mark_pending(self, ticket_id, *a, **kw):
        super().mark_pending(ticket_id, *a, **kw)
        self._maybe_crash(ticket_id, "after_pending")

    def mark_done(self, ticket_id, status="sent"):
        self._maybe_crash(ticket_id, "before_done")
        super().mark_done(ticket_id, status)


def make_runner(server, store, tmp_path, pipeline=None, dry_run=False):
    client = HelpdeskClient("https://h.test/functions/v1/helpdesk", "k", "e@x.nl",
                            transport=httpx.MockTransport(server.handler), sleep=lambda s: None)
    return Runner(client, store, pipeline or FakePipeline(), tmp_path / "logs", dry_run=dry_run, console=lambda s: None)


def test_one_decision_per_ticket_and_rerun_sends_nothing(tmp_path):
    server = FakeHelpdesk(["T1", "T2", "T3"], fail_first_post_with_503=True)
    store = Store(tmp_path / "s.sqlite")
    summary = make_runner(server, store, tmp_path).run()
    assert sorted(server.posts) == ["T1", "T2", "T3"] and summary["outcomes"] == {"sent": 3}
    make_runner(server, store, tmp_path).run()
    assert len(server.posts) == 3 and server.conflicts == 0
    log = (tmp_path / "logs").glob("run-*.jsonl")
    assert sum(len(f.read_text().splitlines()) for f in log) == 3  # one line per handled ticket


def test_crash_after_post_saved_does_not_answer_twice(tmp_path):
    server = FakeHelpdesk(["T1", "T2", "T3"])
    store = CrashOnce(tmp_path / "s.sqlite", "T2", "before_done")
    with pytest.raises(RuntimeError):
        make_runner(server, store, tmp_path).run()
    assert server.posts == ["T1", "T2"]                      # T2 was saved, then we "crashed"
    assert store.get("T2")["status"] == "pending"
    make_runner(server, store, tmp_path).run()
    assert server.posts == ["T1", "T2", "T3"] and server.conflicts == 0
    assert store.get("T2")["status"] == "sent"


def test_crash_before_post_resends_same_decision_without_new_llm_call(tmp_path):
    server = FakeHelpdesk(["T1", "T2"])
    store = CrashOnce(tmp_path / "s.sqlite", "T2", "after_pending")
    with pytest.raises(RuntimeError):
        make_runner(server, store, tmp_path).run()
    assert server.posts == ["T1"]
    pipeline = FakePipeline()
    make_runner(server, store, tmp_path, pipeline=pipeline).run()
    assert server.posts == ["T1", "T2"]
    assert pipeline.calls == []                              # reused the journalled payload


def test_dry_run_sends_nothing(tmp_path):
    server = FakeHelpdesk(["T1", "T2"])
    summary = make_runner(server, Store(tmp_path / "s.sqlite"), tmp_path, dry_run=True).run()
    assert server.posts == [] and summary["outcomes"] == {"dry_run": 2}


def test_ticket_handled_elsewhere_is_skipped_not_conflicted(tmp_path):
    server = FakeHelpdesk(["T1"])
    runner = make_runner(server, Store(tmp_path / "s.sqlite"), tmp_path)
    original = runner.pipeline.decide

    def decide_while_someone_else_answers(ticket, related=None):
        server.tickets[ticket.id]["handled"] = {"action": "reply"}  # a human answered meanwhile
        return original(ticket, related)

    runner.pipeline.decide = decide_while_someone_else_answers
    summary = runner.run()
    assert summary["outcomes"] == {"skipped_already_handled": 1}
    assert server.posts == [] and server.conflicts == 0


def test_related_tickets_link_follow_ups():
    ts = [Ticket(id="T2", subject="Nachtdiensten dubbel"), Ticket(id="T13", subject="Re: Nachtdiensten dubbel"),
          Ticket(id="T5", subject="Nieuwe medewerker")]
    rel = related_tickets(ts)
    assert rel["T13"] == ["T2"] and rel["T2"] == ["T13"] and rel["T5"] == []
