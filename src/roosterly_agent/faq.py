"""Loads the client's help centre (docs/faq.md) at runtime.

Nothing from the FAQ is copied into code. Besides the section texts we extract "anchors" from each section:
the concrete strings a correct reply should repeat verbatim (menu paths, quoted button labels, URLs,
prices/numbers, upper-case names). They are the same in Dutch, English and German, so code can check that a
Dutch draft actually carries the FAQ's instructions without anyone reading Dutch.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

_SECTION = re.compile(r"^## (F\d{2}) · (.+)$", re.M)
_PARENS = re.compile(r"\([^)]*\)")
_PATH = re.compile(r"[A-Z]\w*(?: [a-z]\w*)*(?: → [A-Z]\w*(?: [a-z]\w*)*)+")
_QUOTED = re.compile(r'"([^"]{3,})"')
_DOMAIN = re.compile(r"\b[\w-]+(?:\.[\w-]+)*\.(?:nl|com|eu)(?:/[\w/-]*)?")
_MONEY = re.compile(r"€\s?\d+")
_NUMBER_WITH_UNIT = re.compile(r"\b(?:iOS|Android) \d+\b")
_ACRONYM = re.compile(r"\b[A-Z]{2,}\b")


@dataclass
class FaqSection:
    id: str
    title: str
    text: str
    anchors: list[str] = field(default_factory=list)


@dataclass
class Faq:
    raw: str
    sections: dict[str, FaqSection]
    rules: str

    def render(self, ids: list[str] | None = None) -> str:
        """The FAQ as markdown: all sections, or only the given ids."""
        chosen = [self.sections[i] for i in (ids or self.sections) if i in self.sections]
        return "\n\n".join(f"## {s.id} · {s.title}\n{s.text}" for s in chosen)


def extract_anchors(text: str) -> list[str]:
    plain = _PARENS.sub("", text)  # drop the English translations in brackets
    found: list[str] = []
    found += [m.group(0) for m in _PATH.finditer(plain)]
    found += _QUOTED.findall(text)
    found += [m.group(0).rstrip("/.") for m in _DOMAIN.finditer(text)]
    found += [m.group(0).replace(" ", "") for m in _MONEY.finditer(text)]
    found += _NUMBER_WITH_UNIT.findall(text)
    found += [a for a in _ACRONYM.findall(plain) if a not in {"VAT"}]  # VAT is "btw" in Dutch
    return list(dict.fromkeys(found))  # dedupe, keep order


def load_faq(path: Path) -> Faq:
    raw = path.read_text(encoding="utf-8")
    body, _, rules_part = raw.partition("## The client's rules for the support team")
    matches = list(_SECTION.finditer(body))
    sections: dict[str, FaqSection] = {}
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        text = body[m.end():end].strip().removesuffix("---").strip()
        sections[m.group(1)] = FaqSection(m.group(1), m.group(2).strip(), text, extract_anchors(text))
    if not sections or not rules_part.strip():
        raise ValueError(f"Could not parse help centre sections/rules from {path}")
    return Faq(raw=raw, sections=sections, rules=rules_part.strip())


def normalise(text: str) -> str:
    """For verbatim checks: unify arrows, quotes, euro spacing, case and whitespace."""
    text = text.replace("->", "→").replace(" > ", " → ").replace("“", '"').replace("”", '"')
    text = re.sub(r"€\s+(\d)", r"€\1", text)
    return re.sub(r"\s+", " ", text).lower()


def anchors_present(draft: str, faq: Faq, faq_ids: list[str]) -> tuple[list[str], list[str]]:
    """Which anchors of the cited sections appear verbatim in the draft, and which cited sections have
    anchors but none of them appear."""
    norm = normalise(draft)
    hits: list[str] = []
    sections_without_hit: list[str] = []
    for fid in faq_ids:
        section = faq.sections.get(fid)
        if not section or not section.anchors:
            continue
        section_hits = [a for a in section.anchors if normalise(a) in norm]
        hits += section_hits
        if not section_hits:
            sections_without_hit.append(fid)
    return hits, sections_without_hit
