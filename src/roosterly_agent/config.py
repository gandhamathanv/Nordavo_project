"""Settings, read from environment variables (and `.env` in the working directory).

Secrets never leave this module except as HTTP headers / SDK arguments, and are hidden from repr().
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv


class ConfigError(RuntimeError):
    pass


DEFAULT_MODEL = "gemini-3.5-flash-lite"

# Paid-tier Standard prices, USD per 1M tokens (input, output incl. thinking), used only to report cost.
# Source: https://ai.google.dev/gemini-api/docs/pricing, read 2026-11-17. The free tier costs nothing.
KNOWN_PRICES = {"gemini-3.5-flash-lite": (0.30, 2.50)}


@dataclass(frozen=True)
class Settings:
    helpdesk_url: str
    helpdesk_key: str = field(repr=False)
    candidate_email: str = field(repr=False)
    candidate_name: str | None
    gemini_api_key: str | None = field(repr=False)
    gemini_model: str
    gemini_thinking_budget: int | None
    llm_rpm: int
    price_input_per_m: float | None
    price_output_per_m: float | None
    root: Path
    faq_path: Path
    state_dir: Path
    logs_dir: Path
    eval_dir: Path


def _optional_float(name: str) -> float | None:
    raw = os.getenv(name, "").strip()
    return float(raw) if raw else None


def load_settings(*, require_llm: bool = True, root: Path | None = None) -> Settings:
    root = (root or Path(os.getenv("AGENT_ROOT", Path.cwd()))).resolve()
    load_dotenv(root / ".env", override=False)

    missing = [n for n in ("NORDAVO_HELPDESK", "NORDAVO_KEY", "NORDAVO_ME") if not os.getenv(n)]
    if require_llm and not os.getenv("GEMINI_API_KEY"):
        missing.append("GEMINI_API_KEY")
    if missing:
        raise ConfigError(
            f"Missing environment variables: {', '.join(missing)}. Copy .env.example to .env and fill them in."
        )

    faq_path = Path(os.getenv("FAQ_PATH", root / "docs" / "faq.md"))
    if not faq_path.exists():
        raise ConfigError(f"Help-centre file not found: {faq_path}. Run the agent from the repo root.")

    return Settings(
        helpdesk_url=os.environ["NORDAVO_HELPDESK"].rstrip("/"),
        helpdesk_key=os.environ["NORDAVO_KEY"],
        candidate_email=os.environ["NORDAVO_ME"],
        candidate_name=os.getenv("NORDAVO_NAME") or None,
        gemini_api_key=os.getenv("GEMINI_API_KEY") or None,
        gemini_model=(model := os.getenv("GEMINI_MODEL", DEFAULT_MODEL)),
        gemini_thinking_budget=int(tb) if (tb := os.getenv("GEMINI_THINKING_BUDGET", "").strip()) else None,
        llm_rpm=int(os.getenv("LLM_RPM", "10")),
        price_input_per_m=_optional_float("PRICE_INPUT_PER_M") or KNOWN_PRICES.get(model, (None, None))[0],
        price_output_per_m=_optional_float("PRICE_OUTPUT_PER_M") or KNOWN_PRICES.get(model, (None, None))[1],
        root=root,
        faq_path=faq_path,
        state_dir=root / ".state",
        logs_dir=root / "logs",
        eval_dir=root / "eval" / "results",
    )
