"""Deterministic decision rules. The LLM describes the ticket; this module decides what may happen.

Order matters: the first matching rule wins, and every rule except the last ends in close or handoff.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .guards import detect_language, injection_signals, redact, rule_keyword_hits
from .schemas import Ticket, Triage

CONFIDENCE_MIN = 0.75        # below this the agent counts itself unsure -> human
SPAM_CONFIDENCE_MIN = 0.80   # closing a real customer's ticket is costly, so spam needs more certainty

# Input bounds. A real ticket is a few hundred characters; longer ones (quoted mail threads) still fit.
MAX_BODY_CHARS = 8000        # what the model reads of a ticket; a longer ticket always goes to a human
MAX_SUBJECT_CHARS = 300
MAX_SCAN_CHARS = 50_000      # what the regex guards scan, so a multi-megabyte ticket cannot stall them

# Minimum priority per client rule, straight from the brief's priority table:
# P1 = "a security or legal risk", P2 = "money or the contract is involved".
PRIORITY_FLOOR = {
    "security": "P1",
    "legal": "P1",
    "refund_or_dispute": "P2",
    "cancellation_or_contract": "P2",
    "churn_threat": "P2",
    "gdpr": "P2",
}

RULE_TEXT = {
    "refund_or_dispute": "refunds and disputed charges always go to a human",
    "cancellation_or_contract": "cancellations and contract changes always go to a human",
    "gdpr": "personal data (GDPR/AVG) requests always go to a human",
    "security": "possible security incidents always go to a human",
    "legal": "legal threats always go to a human",
    "churn_threat": "customers threatening to leave always go to a human",
}

_TRIVIAL_SUBJECT = re.compile(r"^\s*((re|fw|fwd|aw|wg)\s*:\s*)*(\(?geen onderwerp\)?|no subject)?\s*$", re.I)


@dataclass
class PreCheck:
    text: str                       # subject + body with payment details removed
    redactions: list[str]
    injection: list[str]
    keyword_rules: list[str]
    empty: bool
    body_language: str | None
    truncated: bool = False         # subject or body was cut before the model saw it


def is_empty(ticket: Ticket) -> bool:
    has_body = bool(re.search(r"[^\W\d_]", ticket.body or ""))
    return not has_body and bool(_TRIVIAL_SUBJECT.match(ticket.subject or ""))


def precheck(ticket: Ticket) -> PreCheck:
    raw_subject, raw_body = ticket.subject or "", ticket.body or ""
    subject, r1 = redact(raw_subject[:MAX_SCAN_CHARS])
    body, r2 = redact(raw_body[:MAX_SCAN_CHARS])
    scanned = f"{subject}\n{body}"     # rules and injection are looked for in everything that was scanned...
    truncated = len(raw_subject) > MAX_SUBJECT_CHARS or len(raw_body) > MAX_BODY_CHARS
    shown_body = body[:MAX_BODY_CHARS]
    text = f"{subject[:MAX_SUBJECT_CHARS]}\n{shown_body}" + ("\n[... truncated ...]" if truncated else "")
    return PreCheck(                     # ...but the model only reads `text`
        text=text,
        redactions=r1 + r2,
        injection=injection_signals(scanned),
        keyword_rules=rule_keyword_hits(scanned),
        empty=is_empty(ticket),
        body_language=detect_language(shown_body)[0],
        truncated=truncated,
    )


def raise_priority(priority: str, rules: list[str]) -> tuple[str, str | None]:
    """Apply the floors above. Returns (priority, rule that raised it or None)."""
    best, raised_by = priority, None
    for rule in rules:
        floor = PRIORITY_FLOOR.get(rule)
        if floor and floor < best:  # "P1" < "P2": lower number = more urgent
            best, raised_by = floor, rule
    return best, raised_by


@dataclass
class Route:
    action: str                     # close | handoff | draft
    reason: str                     # one sentence, for the API `reason` and the logs
    priority: str
    priority_raised_by: str | None
    rules: list[str] = field(default_factory=list)


def route(triage: Triage, pre: PreCheck, valid_faq_ids: set[str]) -> Route:
    rules = sorted(set(triage.rule_triggers) | set(pre.keyword_rules))
    priority, raised_by = raise_priority(triage.priority, rules)

    def out(action: str, reason: str) -> Route:
        return Route(action, reason, priority, raised_by, rules)

    if not 0.0 <= triage.confidence <= 1.0:   # False for NaN too. 87 (a percentage), 5.0, inf, -1: malformed output
        return out("handoff", "Handoff: the model reported an invalid confidence value, so none of its answer is trusted.")
    if pre.truncated and not rules:
        return out("handoff", f"Handoff: ticket too long to read in full (the agent read the first {MAX_BODY_CHARS} characters).")
    if triage.is_spam and triage.confidence >= SPAM_CONFIDENCE_MIN and not rules:
        return out("close", "Close: spam, not a customer request.")
    if rules:
        return out("handoff", "Handoff: client rule, " + "; ".join(RULE_TEXT[r] for r in rules) + ".")
    if priority == "P1":
        return out("handoff", "Handoff: P1, needs a human right away.")
    if triage.is_spam:
        return out("handoff", "Handoff: possibly spam, but not sure enough to close.")
    if not triage.questions:
        return out("handoff", "Handoff: no question the help centre can answer.")
    uncovered = [q.question_en for q in triage.questions
                 if not q.covered_by_faq or not (set(q.faq_ids) & valid_faq_ids)]
    if uncovered:
        return out("handoff", "Handoff: not covered by the help centre: " + "; ".join(uncovered)[:200] + ".")
    if triage.confidence < CONFIDENCE_MIN:
        return out("handoff", f"Handoff: agent unsure (confidence {triage.confidence:.2f}).")
    if pre.body_language and pre.body_language != triage.language:
        return out("handoff", f"Handoff: language unclear ({pre.body_language} vs {triage.language}).")
    faq_ids = sorted({f for q in triage.questions for f in q.faq_ids if f in valid_faq_ids})
    return out("draft", "Reply: answered by help centre " + ", ".join(faq_ids) + ".")
