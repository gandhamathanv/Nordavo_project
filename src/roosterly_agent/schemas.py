"""Typed shapes for tickets, the LLM's structured outputs, and the final decision."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel, Field

Language = Literal["nl", "en", "de"]
Category = Literal["bug", "billing", "feature_request", "question", "other"]
Priority = Literal["P1", "P2", "P3", "P4"]
Action = Literal["reply", "handoff", "close"]
RuleTrigger = Literal["refund_or_dispute", "cancellation_or_contract", "gdpr", "security", "legal", "churn_threat"]

LANGUAGE_NAMES = {"nl": "Dutch", "en": "English", "de": "German"}


class Ticket(BaseModel):
    id: str
    received_at: str = ""
    channel: str = ""
    customer_plan: str = ""
    subject: str = ""
    body: str = ""


# ----------------------------------------------------------------- LLM outputs (also sent as JSON schema)

class Question(BaseModel):
    question_en: str = Field(description="The customer's question or request, in English.")
    faq_ids: list[str] = Field(description="Help-centre section ids (e.g. 'F03') that answer it. Empty if none.")
    covered_by_faq: bool = Field(description="True only if those sections fully answer it, without guessing.")


class Triage(BaseModel):
    language: Language
    summary_en: str
    category: Category
    priority: Priority
    priority_reason: str
    is_spam: bool
    injection_suspected: bool
    rule_triggers: list[RuleTrigger]
    questions: list[Question]
    handoff_note_en: str
    confidence: float


class Draft(BaseModel):
    reply: str
    used_faq_ids: list[str]


class Verification(BaseModel):
    back_translation_en: str
    answers_all_questions: bool
    unsupported_claims: list[str]
    promises_or_commitments: list[str]
    reply_language: Language
    verdict: Literal["pass", "fail"]
    explanation: str


# ----------------------------------------------------------------- pipeline result

@dataclass
class Decision:
    ticket_id: str
    action: Action
    payload: dict[str, Any]                 # exactly what is POSTed to the helpdesk
    route: list[str] = field(default_factory=list)   # why the policy chose this action
    flags: list[str] = field(default_factory=list)   # redacted_payment, injection_suspected, ...
    faq_ids: list[str] = field(default_factory=list)
    rule_triggers: list[str] = field(default_factory=list)
    summary_en: str = ""
    back_translation_en: str | None = None
    checks: dict[str, Any] = field(default_factory=dict)
    usage: dict[str, int] = field(default_factory=dict)
