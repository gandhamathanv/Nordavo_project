"""Eval on the 10 labelled examples from GET /examples, plus hand-labelled extra cases. Nothing is posted.

- "nordavo": labels come only from Nordavo (the `label` object). The gold help-centre sections are the F-ids
  that Nordavo's human-written `reason` mentions (e.g. "FAQ F12 covers it").
- "extra": eval/extra_cases.json, written by the developer to target failures seen in practice dry runs.
  A null label field is not scored. Both sets are reported separately.
The model under test writes no labels.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .guards import detect_language
from .helpdesk import HelpdeskClient
from .llm import LLMUnavailable, add_usage
from .pipeline import Pipeline
from .schemas import Ticket

FIELDS = ("action", "category", "priority", "language")


def _pct(n: int, d: int) -> str:
    return f"{n}/{d} ({100 * n / d:.0f}%)" if d else "n/a"


def load_cases(helpdesk: HelpdeskClient, extra_path: Path | None) -> list[tuple[str, dict[str, Any]]]:
    cases = [("nordavo", ex) for ex in helpdesk.examples()]
    if extra_path and extra_path.exists():
        cases += [("extra", c) for c in json.loads(extra_path.read_text(encoding="utf-8"))["cases"]]
    return cases


def run_eval(helpdesk: HelpdeskClient, pipeline: Pipeline, out_dir: Path, tag: str, model: str,
             prices: tuple[float | None, float | None] = (None, None),
             extra_path: Path | None = None) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    usage: dict[str, int] = {}
    for source, ex in load_cases(helpdesk, extra_path):
        gold = ex["label"]
        ticket = Ticket(**{k: ex.get(k) or "" for k in Ticket.model_fields})
        row: dict[str, Any] = {"id": ex["id"], "source": source, "subject": ex.get("subject", ""),
                               "body": ex.get("body", ""), "gloss": ex.get("gloss"), "gold": gold,
                               "gold_faq": re.findall(r"\bF\d{2}\b", gold.get("reason", ""))}
        try:
            d = pipeline.decide(ticket)
        except LLMUnavailable as exc:
            row.update(error=str(exc), pred=None)
            rows.append(row)
            continue
        add_usage(usage, d.usage)
        pred = {"action": d.action, **{k: d.payload[k] for k in ("language", "category", "priority", "confidence")}}
        row["pred"] = pred
        row["match"] = {f: pred[f] == gold[f] for f in FIELDS if gold.get(f) is not None}
        row["unsafe"] = (d.action == "reply" and gold["action"] != "reply") or \
                        (d.action == "close" and gold["action"] != "close")
        row["over_escalated"] = d.action == "handoff" and gold["action"] != "handoff"
        row.update(route=d.route, faq_ids=d.faq_ids, rule_triggers=d.rule_triggers, flags=d.flags,
                   reason=d.payload["reason"], draft_reply=d.payload.get("draft_reply"),
                   handoff_note=d.payload.get("handoff_note"), back_translation_en=d.back_translation_en,
                   checks=d.checks, usage=d.usage)
        if gold["action"] == "reply" and d.action == "reply":
            row["reply_checks"] = {
                "faq_match": set(row["gold_faq"]) <= set(d.faq_ids),
                "language_ok": detect_language(d.payload["draft_reply"])[0] == gold["language"],
            }
        rows.append(row)

    metrics: dict[str, Any] = {}
    for source in ("nordavo", "extra"):
        subset = [r for r in rows if r["source"] == source]
        if subset:
            metrics[source] = _metrics(subset)
    n = sum(1 for r in rows if r.get("pred"))
    if n:
        metrics["avg_tokens_per_ticket"] = {k: round(v / n) for k, v in usage.items() if k.endswith("_tokens")}
        metrics["llm_calls_per_ticket"] = round(usage.get("llm_calls", 0) / n, 2)
    if all(prices) and n:
        pin, pout = prices
        cost = (usage.get("input_tokens", 0) * pin
                + (usage.get("output_tokens", 0) + usage.get("thinking_tokens", 0)) * pout) / 1e6
        metrics["cost_per_100_tickets_usd"] = round(cost * 100 / n, 4)

    result = {"tag": tag, "model": model, "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "metrics": metrics, "rows": rows}
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{tag}.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / f"{tag}.md").write_text(_markdown(result), encoding="utf-8")
    return result


def _metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    scored = [r for r in rows if r.get("pred")]

    def acc(field: str) -> str:
        judged = [r for r in scored if field in r["match"]]
        return _pct(sum(r["match"][field] for r in judged), len(judged))

    good_replies = [r for r in scored if "reply_checks" in r]
    return {
        **{f"{f}_accuracy": acc(f) for f in FIELDS},
        "all_scored_fields_correct": _pct(sum(all(r["match"].values()) for r in scored), len(scored)),
        "unsafe_decisions": sum(r["unsafe"] for r in scored),
        "over_escalations": sum(r["over_escalated"] for r in scored),
        "expected_replies_sent": _pct(len(good_replies), sum(r["gold"]["action"] == "reply" for r in scored)),
        "reply_faq_match": _pct(sum(r["reply_checks"]["faq_match"] for r in good_replies), len(good_replies)),
        "reply_language_ok": _pct(sum(r["reply_checks"]["language_ok"] for r in good_replies), len(good_replies)),
        "errors": len(rows) - len(scored),
    }


def _markdown(result: dict[str, Any]) -> str:
    m = result["metrics"]
    lines = [f"# Eval: {result['tag']}", "", f"Model `{result['model']}`, {result['created_at']}.", "",
             "| metric | nordavo (10 labelled examples) | extra (hand-labelled) |", "|---|---|---|"]
    for k in m.get("nordavo", {}):
        lines.append(f"| {k} | {m['nordavo'][k]} | {m.get('extra', {}).get(k, '')} |")
    lines += ["", f"Tokens per ticket: {m.get('avg_tokens_per_ticket')}, LLM calls per ticket: "
              f"{m.get('llm_calls_per_ticket')}, cost per 100 tickets (paid tier): ${m.get('cost_per_100_tickets_usd')}"]
    lines += ["", "| id | gold (action / cat / prio / lang) | predicted | wrong fields | notes |", "|---|---|---|---|---|"]
    for r in result["rows"]:
        g = r["gold"]
        gold = f"{g['action']} / {g['category']} / {g['priority']} / {g['language']}"
        if not r.get("pred"):
            lines.append(f"| {r['id']} | {gold} | ERROR | | {r.get('error', '')[:80]} |")
            continue
        p = r["pred"]
        pred = f"{p['action']} / {p['category']} / {p['priority']} / {p['language']}"
        wrong = ", ".join(f for f, ok in r["match"].items() if not ok) or "-"
        note = "**UNSAFE**" if r["unsafe"] else ("over-escalated" if r["over_escalated"] else "")
        lines.append(f"| {r['id']} | {gold} | {pred} | {wrong} | {note} |")
    lines += ["", "## Per ticket", ""]
    for r in result["rows"]:
        if not r.get("pred"):
            continue
        lines += [f"### {r['id']}: {r['subject']}", "", f"- Ticket: {r['body']}"]
        if r.get("gloss"):
            lines.append(f"- English gloss: {r['gloss']}")
        lines += [f"- Gold reason: {r['gold']['reason']}", f"- Agent reason: {r['reason']}"]
        if r.get("draft_reply"):
            lines += [f"- Reply sent: {r['draft_reply']!r}", f"- Back-translation (EN): {r['back_translation_en']}",
                      f"- Checks: {r.get('reply_checks', {})}, anchors {r['checks'].get('anchors_found')}"]
        if r.get("handoff_note"):
            lines.append(f"- Handoff note: {r['handoff_note']}")
            if r.get("back_translation_en"):
                lines.append(f"- Rejected draft (EN): {r['back_translation_en']}")
                lines.append(f"- Rejection: {r['checks'].get('problems')}")
        lines.append("")
    return "\n".join(lines)
