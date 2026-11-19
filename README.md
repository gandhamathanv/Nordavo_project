# Roosterly support-ticket agent

One command posts one decision per open ticket: `reply` (customer's language), `handoff` (English note) or `close`
(spam/empty). Python 3.11+ with uv, Gemini `gemini-3.5-flash-lite` (free tier).

`ticket → redact + rule keywords (code) → triage (LLM) → route (code) → draft → verify (LLM) → reply checks (code) → POST`

## How to run

```bash
git clone https://github.com/gandhamathanv/Nordavo_project.git && cd Nordavo_project
cp .env.example .env            # set NORDAVO_KEY, NORDAVO_ME, GEMINI_API_KEY
uv sync && uv run pytest        # 235 offline tests (+17 xfail: known open security gaps)
uv run agent run                # all open tickets; --dry-run sends nothing (also: agent status, agent reset)
uv run agent eval --tag x       # labelled eval -> eval/results/x.md
uv run python eval/redteam.py   # 47 hostile tickets, never posts
```

## Decisions

1. **LLM describes, code decides.** Gemini has no tools and returns schema-checked JSON. `policy.py` picks the action:
   empty or confident spam → close; an always-human rule (LLM *or* nl/en/de keyword net), P1, anything the FAQ
   doesn't fully answer, or confidence < 0.75 → handoff; else draft. An injection can at most change a JSON field.
2. **Dutch: work in the original, verify in English.** No translate-first step (one call fewer, nuance kept). A
   reviewer call back-translates each draft and lists unsupported claims and promises; code checks the language, the
   FAQ's menu paths/URLs/prices verbatim, leftover English words, foreign links, promises and payment numbers. Any
   failure → handoff. I read replies through the back-translations in the logs.
3. **Unsure = human.** Assumed: self-service "how do I upgrade" is answered from F05, asking support to change the
   contract is not; injection tickets get their genuine question answered; empty tickets are `nl`;
   security/legal → P1, money/contract/GDPR/churn → at least P2.

*AI tools:* built with Claude Code (code, tests, eval, security review); I reviewed each module and the back-translations.

## Reliability

- **503** → backoff 0.5–8 s + jitter, 6 tries. **429** → wait `Retry-After`; a 4 calls/s limiter avoids most.
  **409** → never retried. **401** → stop. A timed-out POST is re-sent only if the ticket is still open.
- **Crash-safe:** a SQLite journal records `pending` + payload → POST → `sent`; after a crash a pending ticket that is
  no longer open counts as answered, one still open gets the same payload. A lock file blocks parallel runs. Tested:
  killed after 16 tickets, resumed → 30/30 sent, 0 × 409. Gemini 429s, overload and daily quota are handled too.
- **Security:** keys from env only; card/IBAN/CVC/expiry redacted before the LLM or logs see them. A red-team of 47
  hostile tickets ([docs/security_review.md](docs/security_review.md)): **0 injections obeyed, 0 prompt leaks, 0 foreign
  links or promises in a reply**. Fixed: Unicode tricks, more payment formats, `</TICKET>` break-out, oversized
  tickets. 17 open gaps (e.g. e-mail/BSN redaction: a product decision) are pinned by `xfail` tests.

## Eval and fix

Nordavo's 10 labelled examples plus 8 cases I labelled with Claude Code, not Gemini (`eval/extra_cases.json`),
scored on action, category, priority and language:

| `eval/results/` | Nordavo (10) | Extra (8) | Unsafe | Over-escalations |
|---|---|---|---|---|
| `before.md` | 10/10 | 7/8 | 0 | 1 |
| `after.md` (the fix) | 10/10 | 8/8 | 0 | 0 |
| `fix2.md` (latest) | 10/10 | 8/8 | 0 | 0 |

**Failure:** Dutch case X04's draft copied the FAQ's English, so the checks turned it into a needless handoff.
**Fix:** translate-the-FAQ prompt, language instruction last, one redraft if the language check fails. Later, an
English word in a Dutch reply (E04) and a missing price total (E07) got a detector and a prompt rule (`fix2.md`).
Only 18 cases, so small evidence.

**Cost per 100 tickets** (highest case: the most expensive practice-run ticket, T029, a reply using all three calls with
2,864 in + 552 out tokens, at $0.30 / $2.50 per 1M, as if all 100 cost that much): 100 × (2,864 × 0.30 + 552 × 2.50)
/ 10⁶ = **$0.22 ≈ €0.19**, about $23 a year at 200 tickets a week. My actual cost was €0 on the free tier.

## What I would improve

- **Next:** a different model as reviewer (the drafter now reviews itself), e-mail/BSN redaction once the client
  decides, and repeated uncached eval runs. Known miss: T015 (Loket.nl, in F04) is escalated. Production needs a
  paid EU tier: free-tier data may be used by Google.
- **Rule I'd change:** "contract changes go to a human" clashes with F05's self-service upgrade; I'd allow how-to
  answers about plans.
