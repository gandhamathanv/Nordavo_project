"""Shared fixtures for the AI-security audit tests (see docs/security_review.md).

`ScriptedLLM` stands in for Gemini: it returns the schema-valid but possibly *hostile* objects a test queues up,
so we can ask "what can the pipeline be made to do if the model misbehaves?" without spending any quota.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from roosterly_agent.faq import load_faq
from roosterly_agent.guards import detect_language
from roosterly_agent.pipeline import Pipeline
from roosterly_agent.schemas import Decision, Draft, Question, Ticket, Triage, Verification

FAQ = load_faq(Path(__file__).resolve().parents[1] / "docs" / "faq.md")

GOOD_BODY_NL = "Hoe voeg ik een nieuwe medewerker toe aan ons rooster? Kunnen jullie dat uitleggen, graag."
GOOD_REPLY_NL = ("Hoi, ga naar Team → Medewerker toevoegen, vul de gegevens in en klik op Uitnodigen. "
                 "Met vriendelijke groet, Team Roosterly")


def gap(sec: str, why: str):
    """Mark a test that documents a gap found by the audit. strict=True: once the gap is fixed the test
    XPASSes and fails the suite, which is the reminder to delete the marker."""
    return pytest.mark.xfail(strict=True, reason=f"{sec}: {why}")


def make_ticket(body: str = GOOD_BODY_NL, subject: str = "Medewerker toevoegen", **kw: Any) -> Ticket:
    base: dict[str, Any] = dict(id="T900", received_at="2026-11-18T09:00:00+00:00", channel="email",
                                customer_plan="Basis", subject=subject, body=body)
    base.update(kw)
    return Ticket(**base)


def make_triage(**kw: Any) -> Triage:
    base: dict[str, Any] = dict(
        language="nl", summary_en="Customer asks how to add an employee.", category="question", priority="P4",
        priority_reason="How-to question.", is_spam=False, injection_suspected=False, rule_triggers=[],
        questions=[Question(question_en="How do I add an employee?", faq_ids=["F02"], covered_by_faq=True)],
        handoff_note_en="Customer asks how to add an employee.", confidence=0.9)
    base.update(kw)
    return Triage(**base)


def make_draft(reply: str = GOOD_REPLY_NL, ids: list[str] | None = None) -> Draft:
    return Draft(reply=reply, used_faq_ids=ids if ids is not None else ["F02"])


def make_verification(**kw: Any) -> Verification:
    base: dict[str, Any] = dict(back_translation_en="Go to Team → Medewerker toevoegen ...", answers_all_questions=True,
                                unsupported_claims=[], promises_or_commitments=[], reply_language="nl",
                                verdict="pass", explanation="ok")
    base.update(kw)
    return Verification(**base)


class ScriptedLLM:
    """Implements pipeline.LLM. Records every prompt it is given."""

    def __init__(self, triage: Triage, draft: Draft | None = None, verification: Verification | None = None,
                 redraft: Draft | None = None):
        self.responses: dict[str, Any] = {"triage": triage, "draft": draft, "redraft": redraft or draft,
                                          "verify": verification}
        self.calls: list[dict[str, str]] = []

    def generate(self, *, system: str, user: str, schema: type, purpose: str):
        self.calls.append({"purpose": purpose, "system": system, "user": user})
        obj = self.responses[purpose]
        if isinstance(obj, list):            # a queue: one answer per call, the last one repeats
            obj = obj.pop(0) if len(obj) > 1 else obj[0]
        if obj is None:
            raise AssertionError(f"pipeline made an unexpected '{purpose}' LLM call")
        assert isinstance(obj, schema)
        return obj, {"llm_calls": 1}

    @property
    def purposes(self) -> list[str]:
        return [c["purpose"] for c in self.calls]


def decide(ticket: Ticket, triage: Triage, draft: Draft | None = None,
           verification: Verification | None = None) -> tuple[Decision, ScriptedLLM]:
    """Run one ticket through the real Pipeline with a scripted model. A passing draft/verification is queued
    by default so a test only has to describe what it wants to make hostile."""
    llm = ScriptedLLM(triage, draft or make_draft(), verification or make_verification())
    return Pipeline(FAQ, llm).decide(ticket), llm

