# Roosterly support-ticket agent

Posts one decision per open ticket: `reply` (customer's language), `handoff` (English note) or `close` (spam/empty).
Python 3.13 + uv, Gemini `gemini-3.5-flash-lite` (free tier).

## How to run

```bash
cp .env.example .env       # set NORDAVO_KEY, NORDAVO_ME, GEMINI_API_KEY
uv sync && uv run pytest   # 54 offline tests (503/429/409, crash recovery, guards, policy)
uv run agent run           # all open tickets; --dry-run sends nothing
uv run agent eval --tag x  # -> eval/results/x.md   (also: agent status, agent reset)
```

## Decisions

1. **LLM describes, code decides.** Gemini has no tools and returns schema-checked JSON only. `policy.py` picks the
   action: empty → close; confident spam → close; any always-human rule (LLM *or* nl/en/de keyword net), P1, any
   part the FAQ doesn't fully answer, or confidence < 0.75 → handoff; otherwise draft a reply. Ticket text is
   untrusted data, so an injection (T007, T030) can at most change a JSON field.
2. **Dutch: work in the original, verify in English.** No translate-first step (one call fewer, nuance kept). A
   separate reviewer call back-translates each draft and lists unsupported claims and promises. Code adds a
   stopword language check, requires the FAQ's menu paths, URLs and prices verbatim, and blocks payment numbers.
   Any failure → handoff. I read replies through the back-translations in the logs and eval reports.
3. **Unsure = human.** Assumptions where the brief is open: a self-service "how do I upgrade" question is answered
   from F05, but a request for support to change the contract is not; injection tickets get their genuine question
   answered; empty tickets are `nl`; security/legal → P1, money/contract/GDPR/churn → at least P2.

*AI tools:* built with Claude Code (plan, code, tests, eval tooling); I reviewed each module and the back-translations.

## Reliability

- **503** → backoff 0.5–8 s + jitter, 6 tries. **429** → wait `Retry-After`; a 4 calls/s limiter prevents most 429s.
  **409** → never retried. **422** → logged with `problems`. **401** → stop. A timed-out POST is re-sent only
  if `GET /tickets/{id}` still shows the ticket open.
- **Crash-safe:** only open tickets are processed, each is re-checked just before its POST, and a sqlite
  write-ahead journal records `pending` + payload → POST → `sent`. After a crash, a pending ticket that is no longer
  open counts as answered; one still open gets the same payload again. A lock file blocks parallel runs. Tested:
  killed after 16 tickets, resumed → 30/30 sent, 0 × 409; a re-run sent nothing.
- **Gemini free tier:** honours `retryDelay` on 429, backs off up to 60 s on overload, stops cleanly when the daily
  quota is used up, and caches responses by prompt hash.
- **Security:** keys only from env. Card, IBAN, CVC and expiry are redacted *before* the LLM, the logs or a note
  sees them. `logs/` has one JSON line per ticket, with no raw body.

## Eval and fix

Nordavo's 10 labelled examples, plus 8 hand-labelled cases I wrote with Claude Code (not Gemini) after a dry run
(`eval/extra_cases.json`), scored separately. **Before:** Nordavo 10/10 on action, category, priority and
language, 0 unsafe; extra 7/8. **Failure:** for Dutch case X04 the drafter copied the FAQ's English sentences; the
checks rejected it, so it became a needless handoff. **Fix:** the prompt says the FAQ must be translated, the
language instruction goes last, and there is one redraft if the language check fails. **After:** 10/10 and 8/8,
0 unsafe, 0 over-escalations (redraft never needed). I also made the detector the language tiebreaker after
English T006 came back as `nl` (`final.md`, scores unchanged). Only 18 cases, so small evidence.

**Cost per 100 tickets** (practice run: 1.77 calls, 2,016 in + 308 out tokens per ticket, at $0.30 / $2.50 per 1M):
100 × (2,016 × 0.30 + 308 × 2.50) / 10⁶ = **$0.14 ≈ €0.12**. My actual cost was €0 on the free tier.

## What I would improve

- **Next:** human-labelled real tickets, repeated uncached eval runs for variance, and a different reviewer model
  (today the drafter reviews itself). Known miss: T015 (Loket.nl, in F04) was escalated. For production, use a
  paid EU tier: free-tier data may be used by Google.
- **Rule I'd change:** "contract changes go to a human" clashes with F05's self-service upgrade. I'd ask the client
  to say that how-to questions about plans may be answered.
