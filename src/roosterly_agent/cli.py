"""Command line: `agent run`, `agent status`, `agent reset`, `agent eval`."""

from __future__ import annotations

import argparse
import json
import sys

from .config import ConfigError, Settings, load_settings
from .faq import load_faq
from .helpdesk import FatalError, HelpdeskClient
from .llm import GeminiLLM
from .pipeline import Pipeline
from .store import Store, single_instance


def _helpdesk(s: Settings) -> HelpdeskClient:
    return HelpdeskClient(s.helpdesk_url, s.helpdesk_key, s.candidate_email, s.candidate_name)


def _pipeline(s: Settings, cache: Store | None) -> Pipeline:
    assert s.gemini_api_key
    llm = GeminiLLM(s.gemini_api_key, s.gemini_model, cache, rpm=s.llm_rpm, thinking_budget=s.gemini_thinking_budget)
    return Pipeline(load_faq(s.faq_path), llm)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="agent", description="Roosterly support-ticket agent")
    sub = parser.add_subparsers(dest="cmd", required=True)
    run = sub.add_parser("run", help="handle all open tickets (one decision each)")
    run.add_argument("--dry-run", action="store_true", help="decide and log, but send nothing")
    run.add_argument("--limit", type=int, help="only the first N open tickets")
    run.add_argument("--ticket", action="append", help="only this ticket id (repeatable)")
    run.add_argument("--no-cache", action="store_true", help="always call the model, ignore cached responses")
    sub.add_parser("status", help="show helpdesk mode and open/handled counts")
    sub.add_parser("reset", help="POST /practice/reset: re-open all practice tickets")
    ev = sub.add_parser("eval", help="evaluate on the labelled examples (nothing is sent)")
    ev.add_argument("--tag", default="latest", help="name of the result files in eval/results/")
    ev.add_argument("--no-cache", action="store_true", help="always call the model, ignore cached responses")
    args = parser.parse_args(argv)

    try:
        s = load_settings(require_llm=args.cmd in ("run", "eval"))
    except ConfigError as exc:
        print(f"Config error: {exc}", file=sys.stderr)
        return 2

    helpdesk = _helpdesk(s)
    try:
        if args.cmd == "status":
            print(json.dumps({k: v for k, v in helpdesk.status().items() if k != "endpoints"}, indent=2))
            return 0

        if args.cmd == "reset":
            print(json.dumps(helpdesk.reset(), indent=2))
            Store(s.state_dir / "agent.sqlite").clear_journal()
            print("Local journal cleared.")
            return 0

        if args.cmd == "eval":
            from .evaluate import run_eval
            store = Store(s.state_dir / "agent.sqlite")
            result = run_eval(helpdesk, _pipeline(s, None if args.no_cache else store), s.eval_dir, args.tag,
                              s.gemini_model, (s.price_input_per_m, s.price_output_per_m),
                              extra_path=s.root / "eval" / "extra_cases.json")
            print(json.dumps(result["metrics"], indent=2))
            print(f"Report: {s.eval_dir / (args.tag + '.md')}")
            return 0

        # run
        from .runner import Runner
        with single_instance(s.state_dir / "agent.lock"):
            store = Store(s.state_dir / "agent.sqlite")
            runner = Runner(helpdesk, store, _pipeline(s, None if args.no_cache else store), s.logs_dir,
                            dry_run=args.dry_run,
                            prices=(s.price_input_per_m, s.price_output_per_m))
            summary = runner.run(limit=args.limit, only=args.ticket)
            print(json.dumps(summary, indent=2))
            left_open = sum(v for k, v in summary["outcomes"].items() if k.startswith(("left_open", "validation")))
            if left_open:
                print(f"{left_open} ticket(s) were not handled. Re-run `agent run` to continue.", file=sys.stderr)
                return 1
            return 0
    except FatalError as exc:
        print(f"Helpdesk refused the request (check NORDAVO_KEY / NORDAVO_ME): {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("Interrupted. Safe to re-run: the journal resumes where it stopped.", file=sys.stderr)
        return 130
    finally:
        helpdesk.close()


if __name__ == "__main__":
    sys.exit(main())
