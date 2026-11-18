"""One ticket in, one Decision out. Talks to the LLM, never to the helpdesk.

    pre-checks (code) -> triage (LLM) -> policy (code) -> [draft (LLM) -> verify (LLM + code)] -> decision
"""

from __future__ import annotations

from typing import Any, Protocol, TypeVar

from pydantic import BaseModel

from . import prompts
from .faq import Faq, anchors_present
from .guards import (contact_details, contains_payment_details, detect_language, foreign_contact_details, redact,
                     reply_commitments, rule_keyword_hits)
from .llm import add_usage
from .policy import MAX_BODY_CHARS, PreCheck, Route, precheck, route
from .schemas import LANGUAGE_NAMES, Decision, Draft, Ticket, Triage, Verification

T = TypeVar("T", bound=BaseModel)


class LLM(Protocol):
    def generate(self, *, system: str, user: str, schema: type[T], purpose: str) -> tuple[T, dict[str, int]]: ...


def _payload(language: str, category: str, priority: str, reason: str, confidence: float) -> dict[str, Any]:
    if not 0.0 <= confidence <= 1.0:      # NaN, inf or out of range: report "unknown", never a made-up 1.0
        confidence = 0.0
    return {"language": language, "category": category, "priority": priority,
            "reason": reason, "confidence": round(max(0.0, min(1.0, confidence)), 2)}


class Pipeline:
    def __init__(self, faq: Faq, llm: LLM):
        self.faq = faq
        self.llm = llm
        self.valid_ids = set(faq.sections)

    def decide(self, ticket: Ticket, related: list[str] | None = None) -> Decision:
        pre = precheck(ticket)
        flags = (["payment_details_redacted"] if pre.redactions else []) + \
                (["injection_pattern"] if pre.injection else []) + \
                (["input_truncated"] if pre.truncated else [])
        usage: dict[str, int] = {}

        if pre.empty:
            language = detect_language(ticket.subject)[0] or "nl"  # nothing to detect: most customers write Dutch
            payload = _payload(language, "other", "P4", "Empty ticket with no message to answer (P4). Close: empty.", 1.0)
            return Decision(ticket.id, "close", payload, route=["empty"], flags=flags)

        triage, u = self.llm.generate(system=prompts.triage_system(self.faq),
                                      user=prompts.triage_user(ticket, pre.text), schema=Triage, purpose="triage")
        add_usage(usage, u)
        if triage.injection_suspected and "injection_suspected" not in flags:
            flags.append("injection_suspected")
        if pre.body_language and pre.body_language != triage.language:
            # The stopword detector is confident and disagrees: trust it for the `language` field. (A reply is
            # never drafted in this case: policy.route() hands disagreements to a human.)
            flags.append(f"language_corrected_{triage.language}_to_{pre.body_language}")
        r = route(triage, pre, self.valid_ids)
        language = pre.body_language or triage.language
        faq_ids = sorted({f for q in triage.questions for f in q.faq_ids if f in self.valid_ids})
        base = dict(ticket_id=ticket.id, flags=flags, faq_ids=faq_ids, rule_triggers=r.rules,
                    summary_en=triage.summary_en, usage=usage)

        if r.action == "close":
            payload = _payload(language, "other", "P4", self._reason(triage, r), triage.confidence)
            return Decision(action="close", payload=payload, route=[r.reason], **base)

        if r.action == "handoff":
            return self._handoff(triage, r, pre, related, base, extra=None, language=language)

        # r.action == "draft": write a reply, then try to reject it.
        draft_system = prompts.draft_system(self.faq, faq_ids, triage.language)
        draft, u = self.llm.generate(system=draft_system, user=prompts.draft_user(ticket, pre.text, triage.language),
                                     schema=Draft, purpose="draft")
        add_usage(usage, u)
        detected = detect_language(draft.reply)[0]
        if detected != triage.language:
            # One redraft when the reply drifted into another language (usually the FAQ's English).
            note = (f"Your previous draft was written in {detected or 'mixed languages'}, not in "
                    f"{LANGUAGE_NAMES[triage.language]}. Write it again, entirely in {LANGUAGE_NAMES[triage.language]}.")
            draft, u = self.llm.generate(system=draft_system, schema=Draft, purpose="redraft",
                                         user=prompts.draft_user(ticket, pre.text, triage.language, note))
            add_usage(usage, u)
            flags.append("redrafted_for_language")
        verification, u = self.llm.generate(system=prompts.verify_system(self.faq, faq_ids, triage.language),
                                            user=prompts.verify_user(ticket, pre.text, draft.reply),
                                            schema=Verification, purpose="verify")
        add_usage(usage, u)
        problems, checks = self._check_draft(draft, verification, triage.language, faq_ids)
        base.update(back_translation_en=verification.back_translation_en, checks=checks)

        if problems:
            r.reason = "Handoff: auto-reply rejected by verification."
            return self._handoff(triage, r, pre, related, base, extra="Auto-reply rejected: " + "; ".join(problems),
                                 language=language)

        payload = _payload(triage.language, triage.category, r.priority, self._reason(triage, r), triage.confidence)
        payload["draft_reply"] = draft.reply.strip()
        return Decision(action="reply", payload=payload, route=[r.reason], **base)

    # ------------------------------------------------------------------ helpers

    def _check_draft(self, draft: Draft, v: Verification, language: str,
                     faq_ids: list[str]) -> tuple[list[str], dict[str, Any]]:
        """Checks a non-Dutch reader can trust: each is either code or a separate reviewer call."""
        problems: list[str] = []
        if v.verdict != "pass":
            problems.append(f"reviewer: {v.explanation}")
        if not v.answers_all_questions:
            problems.append("does not answer every question")
        if v.unsupported_claims:
            problems.append("unsupported claims: " + "; ".join(v.unsupported_claims)[:200])
        if v.promises_or_commitments:
            problems.append("promises: " + "; ".join(v.promises_or_commitments)[:200])
        if v.reply_language != language:
            problems.append(f"reviewer says reply is in {v.reply_language}")
        detected, scores = detect_language(draft.reply)
        if detected != language:
            problems.append(f"language check detected {detected} instead of {language}")
        outside = sorted(set(draft.used_faq_ids) - set(faq_ids))
        if outside:
            problems.append(f"used sections the triage did not cite: {outside}")
        used = [f for f in draft.used_faq_ids if f in faq_ids] or faq_ids
        hits, missing = anchors_present(draft.reply, self.faq, used)
        if missing:
            problems.append(f"no verbatim help-centre details from {missing}")
        if contains_payment_details(draft.reply):
            problems.append("reply contains payment details")
        # Deterministic net behind the reviewer (same model as the drafter): links, addresses and numbers must come
        # from the cited help-centre sections, and a reply may not touch an always-human topic or make a promise.
        foreign = foreign_contact_details(draft.reply, contact_details(self.faq.render(faq_ids)))
        if foreign:
            problems.append(f"contact details outside the cited help-centre sections: {foreign}")
        rules_in_reply = rule_keyword_hits(draft.reply)
        if rules_in_reply:
            problems.append(f"reply touches an always-human topic: {rules_in_reply}")
        commitments = reply_commitments(draft.reply)
        if commitments:
            problems.append("reply makes a commitment: " + "; ".join(commitments)[:200])
        checks = {"verdict": v.verdict, "language_detected": detected, "language_scores": scores,
                  "anchors_found": hits, "foreign_contacts": foreign, "rules_in_reply": rules_in_reply,
                  "commitments": commitments, "problems": problems}
        return problems, checks

    def _handoff(self, triage: Triage, r: Route, pre: PreCheck, related: list[str] | None,
                 base: dict[str, Any], extra: str | None, language: str) -> Decision:
        parts = [triage.handoff_note_en.strip()]
        if r.rules:
            parts.append("Client rule: " + ", ".join(r.rules) + ".")
        if extra:
            parts.append(extra)
        if pre.redactions:
            parts.append("Payment details in the ticket were redacted by the agent.")
        if pre.truncated:
            parts.append(f"The ticket is very long: the agent read only its first {MAX_BODY_CHARS} characters.")
        if "injection_suspected" in base["flags"] or "injection_pattern" in base["flags"]:
            parts.append("Warning: the ticket contains text that tries to instruct an AI; it was ignored.")
        if related:
            parts.append("Related ticket(s): " + ", ".join(related) + ".")
        note, _ = redact(" ".join(p for p in parts if p))
        payload = _payload(language, triage.category, r.priority, self._reason(triage, r), triage.confidence)
        payload["handoff_note"] = note
        return Decision(action="handoff", payload=payload, route=[r.reason], **base)

    @staticmethod
    def _reason(triage: Triage, r: Route) -> str:
        priority = r.priority
        if r.priority_raised_by:
            priority += f", raised from {triage.priority} by client rule"
        reason = f"{triage.priority_reason.strip().rstrip('.')} ({priority}). {r.reason}"
        return redact(reason)[0][:400]
