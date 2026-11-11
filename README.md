# RH du futur — Groupe Orvane

Screening tool for a recruitment team that receives ~1,500 applications per offer.
It reads every CV against the job post, runs a pre-interview (voice or text) with the candidates who fit,
and hands the recruiter a short, evidence-backed synthesis. **The AI proposes, the recruiter decides, and every
candidate gets an answer.**

**Live:** https://sta-ahmed09--orvane-rh.us-east.modal.run (password: `APP_PASSWORD`)

```
Job post ─► criteria (must / nice × checked on the CV / checked at the interview), editable
CV ─► parse ─► hidden-text scan ─► profile ‖ injection scan ─► anonymize ─► evaluate (one quote per verdict)
   ─► quote verification (code) ─► triage (code)
      pre-qualified → pre-interview link prepared      to review → one-click invite      no → rejection proposed
Pre-interview (voice or text) ─► transcript ─► grades with verified quotes ─► note /10 + one-minute synthesis
Recruiter decision (comment required when overriding the AI) ─► personalised reply ─► approved ─► sent by e-mail
```

## Contents
1. [Quick start](#quick-start)
2. [How it works](#how-it-works)
3. [Design decisions](#design-decisions)
4. [Architecture](#architecture)
5. [Project layout](#project-layout)
6. [Configuration](#configuration)
7. [Tests and evaluations](#tests-and-evaluations)
8. [Deployment](#deployment)
9. [Known limits and next steps](#known-limits-and-next-steps)

## Quick start

**Docker (one command):**
```bash
cp .env.example .env        # fill ANTHROPIC_API_KEY, APP_PASSWORD, SECRET_KEY (ElevenLabs and SMTP are optional)
docker compose up -d --build
# → http://localhost:3000
```

**Local development (two terminals):**
```bash
python3 -m venv .venv && .venv/bin/pip install -r backend/requirements.txt
.venv/bin/flask --app backend.app.main:app run --port 8000 --debug     # API
cd frontend && npm ci && npm run dev                                   # UI → http://localhost:3000
```
Optional: `.venv/bin/python scripts/setup_agent.py` creates the ElevenLabs voice agent and stores its id in `.env`;
`scripts/seed_demo.py` loads the job post and the six sample CVs from `fixtures/`.

## How it works

1. **Offer.** The recruiter pastes a job post. Sonnet extracts 6–10 criteria, each with a *kind* (`must` = blocking,
   `nice`) and a *source* (`cv` = scored at screening, `interview` = checked orally and never penalised at screening:
   availability, mobility, salary, shifts). A hard-coded filter drops any criterion on a protected attribute.
   Criteria are editable; editing keeps the existing evidence and flags analyses as out of date.
2. **Parsing** (`cv/parse.py`). PDF (pdfplumber), DOCX (python-docx), images and scanned PDFs (Claude vision).
   Text that a human cannot see (white on white, ≤ 3 pt, Word "hidden") is split off: the evaluator never reads it,
   the injection scan does.
3. **Profile and injection scan**, in parallel (Haiku). Contact details must literally exist in the CV. A regex
   catches phrases addressed to the screening system; the LLM scan catches the rest.
4. **Anonymization** (`cv/anonymize.py`). Name, e-mail, links, phone, address, and in the header only: age,
   postcode and city. Dates, durations, volumes, employers and schools stay: they are the evidence.
5. **Evaluation** (Sonnet). For every CV criterion: `met / partial / not_met / not_evidenced`, a quote and a short
   rationale. `screening/verify.py` checks that the quote exists in the CV (normalised, tolerant to typography).
   **No verified quote, no verdict:** the verdict is downgraded to `not_evidenced`.
6. **Triage** (`screening/triage.py`, pure code). Weighted score: must ×3, nice ×1; met 1, partial 0.5,
   not evidenced 0.3, not met 0. *Pre-qualified* ⇔ score ≥ 70 %, no failed must-have, no injection.
   *To review* ⇔ ≥ 45 %. Otherwise a rejection is *proposed*. The model never writes a score.
7. **Pre-interview.** Pre-qualified candidates get a plan (~8–10 questions built from the criteria and the CV's
   gaps) and a personal link valid 7 days. The candidate consents, then talks to Camille (ElevenLabs voice agent)
   or types (same prompt, Haiku). Language levels are checked *in* that language.
8. **Scoring.** Sonnet grades each criterion 0–3 with a quote from the candidate's own words (verified in code;
   unverified = not assessed). The note /10 and the global score (0.4 × CV + 0.6 × interview) are computed in code.
   The synthesis lists strengths, doubts, points to probe, logistics, blockers and CV/interview discrepancies.
9. **Decision.** Retain / Refuse. Contradicting the AI requires a comment, enforced server-side and logged as an
   override. A personalised reply is drafted (Haiku); the recruiter edits and approves it; it is sent over SMTP.
10. **Traceability and cost.** Every action goes to an append-only audit log (the candidate's *History* tab).
    Every LLM and voice call is metered; each offer has a cost page with a forecast for 1,500 applications.

## Design decisions

- **Evidence or nothing.** Verdicts, interview grades and synthesis items all carry a quote checked by code.
  A hallucination becomes "not evidenced", never a false fact, and the recruiter sees the quote highlighted in the CV.
- **Code decides the numbers.** The LLM labels; triage, notes and costs are computed in code. Deterministic,
  testable, and a prompt injection has no score field to fill.
- **Layered injection defence.** Hidden text removed before evaluation → regex + LLM scan → CV treated as data in
  every prompt → score-less schema → code triage blocks "pre-qualified" → evidence shown to the recruiter.
  In the interview the agent has no tool except ending the call, and manipulation attempts are flagged.
- **Prefer false positives** (the recruiter's explicit wish). "Not evidenced" is worth 0.3, not 0; only a failed
  must-have blocks, and it sends the candidate to human review rather than to a rejection. A must-have the model
  judged "not met" without a verifiable quote also blocks the automatic "yes".
- **Fairness.** Identity removed before evaluation; no criterion on protected attributes; the interviewer never asks
  about age, family, health or origin; foreign CVs, career breaks and career changes are not penalised.
- **Human in the loop** (recruitment is a high-risk use case under the AI Act; GDPR art. 22). Nothing is decided
  or sent automatically by default; rejections mention the right to ask for a human re-examination.
- **Two model tiers.** Sonnet for judgement (criteria, evaluation, plan, scoring), Haiku for volume (profile,
  injection scan, text interview, e-mails). Native structured outputs validated by Pydantic.
- **Polling, not webhooks**, for voice transcripts: works behind any URL, nothing extra to expose.

## Architecture

```
Browser ──► Next.js 16 (App Router, :3000) ── /api/* rewrite ──► Flask API (:8000, internal)
                  │                                                  ├─► Anthropic (Sonnet, Haiku)
                  └─ WebSocket (signed URL) ─► ElevenLabs Agents      ├─► SMTP
                                                                     └─► SQLite (SQLAlchemy)
```
- **Backend:** Flask (Blueprints), SQLAlchemy 2, Pydantic v2, gunicorn (1 worker × 16 threads: SQLite has a single
  writer). Long AI jobs run after the response in a dedicated thread pool, so they never hold HTTP threads.
- **Frontend:** Next.js 16 App Router, React 19, TypeScript, Tailwind. The `(recruiter)` route group is the auth
  gate; `/i/[token]` is the candidate side (no account). The browser only talks to Next, which proxies `/api` to Flask,
  so the session cookie is same-origin.
- **One image, two processes** (`start.sh`), deployed on Modal or anywhere Docker runs.

**Data model** (`backend/app/models.py`): `jobs`, `criteria`, `candidates`, `evaluations`, `interviews`, `decisions`,
`messages`, `usage_events` (cost of every call), `audit_log`. New columns are added at startup (`db._add_missing_columns`).

## Project layout

```
backend/app/
  main.py            Flask app factory, error handlers, health
  web.py             request session, @login_required, JSON validation, background tasks
  auth.py            shared-password login, signed HttpOnly cookie
  config.py          every setting, from the environment
  llm.py             the only place that calls the LLM (structured outputs, retries, cost metering)
  prompts.py         all prompts, versioned by PROMPT_VERSION (logged with each verdict)
  cv/                parse.py (text + hidden text), anonymize.py
  screening/         pipeline.py, verify.py (quotes), triage.py (scoring rule), retriage.py
  interview/         service.py (plan, text interview, scoring), elevenlabs.py (voice session, transcript)
  routers/           jobs, candidates, public (candidate side), outbox (decisions, e-mails), costs
  comms.py · mailer.py · emailtpl.py   reply drafts, SMTP sending, HTML e-mail
  costs.py · audit.py
frontend/src/
  app/               routes (App Router): (recruiter)/…, i/[token]/…
  views/             screens: Jobs, JobDetail, Candidates, CandidateDetail, Outbox, CostJob, candidate/*
  components/ · lib/ shared UI, dialogs and toasts, i18n, query-string helper
evals/               eval on the six sample CVs, generated "surprise" CVs, simulated candidates
scripts/             voice agent setup, demo seed, voice comparison, text smoke test
```

## Configuration

`.env` (see `.env.example`):

| Variable | Meaning |
|---|---|
| `ANTHROPIC_API_KEY`, `MODEL_SMART`, `MODEL_FAST` | LLM access and models |
| `ELEVENLABS_API_KEY`, `ELEVENLABS_AGENT_ID` | Voice interview (without them, only the text interview is offered) |
| `APP_PASSWORD`, `SECRET_KEY` | Recruiter password, cookie-signing key |
| `PUBLIC_URL` | Public https address, used in invitation links |
| `YES_THRESHOLD` (0.70), `MAYBE_THRESHOLD` (0.45) | Triage thresholds (re-applied at startup without any LLM call) |
| `INTERVIEW_VALID_DAYS` (7) | Validity of interview links |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` | E-mail. Without `SMTP_HOST`, sending is simulated and labelled as such |
| `AUTO_SEND_INVITES` (0) | 1 = e-mail the link to pre-qualified candidates without a click |
| `DATA_DIR`, `DB_JOURNAL` | SQLite location and journal mode |

## Tests and evaluations

**All checks in one command** (offline and free: no LLM call, no e-mail):
```bash
pip install -r requirements-dev.txt
scripts/check.sh              # ruff + pytest + oxlint + Next.js type check and build
scripts/check.sh --docker     # … + Docker image build
scripts/check.sh --live       # … + read-only checks of the deployed app (scripts/smoke_live.py [URL])
```

**pytest (57 tests, hermetic).** `conftest.py` blanks every API key and SMTP setting and blocks any network access,
so a test can never call a paid API or send a real e-mail.

| File | Covers |
|---|---|
| `test_cv_pipeline.py` | triage rules and threshold, quote verification, anonymization (identity removed, dates/durations/volumes kept, accents), hidden text, injection net (attacks vs honest phrases), Canva-style PDFs, interview note (unverified quote, coverage, manipulation) |
| `test_api_journey.py` | the whole journey through the HTTP API with the LLM stubbed: offer → CVs → screening → invitation → consent → interview → note → decision → reply → costs → deletion, plus error paths |
| `test_contract.py` | every API call written in the frontend hits an existing Flask route |
| `test_sample_cvs.py` | the six brief CVs and eight trap CVs: no name or contact leak after anonymization, the injection net flags exactly the two trap CVs, every file parses |
| `test_invite_email.py` | invitation e-mail (link + deadline), SMTP vs simulated, expired links, race between background preparation and a recruiter click |
| `test_decisions.py`, `test_jobs.py`, `test_costs.py`, `test_smoke.py` | override comment, funnel and to-do list, criteria editing, costs, auth, background tasks dropped on errors |

**Evals with the real models** (cost a few cents):
```bash
.venv/bin/python -m evals.run_eval                          # the six sample CVs vs expected outcomes
.venv/bin/python -m evals.make_surprise && .venv/bin/python -m evals.run_eval --surprise   # 8 trap CVs
.venv/bin/python -m evals.sim_interview --base URL --password … --candidate ID --persona jailbreak
```
They check triage, injection detection, language and zero unverified quotes. Trap CVs: two-column PDF with a dark
sidebar, 1-pt hidden injection, scanned PNG in English, off-topic profile, recipe, empty file, equivalent tools,
adjacent profile. Simulated candidates: honest, jailbreak, off-topic, terse.

## Deployment

**Modal** (current): one always-warm container built from the `Dockerfile`, SQLite on the `orvane-data` volume,
secrets in `orvane-secrets`, HTTPS included (needed for the microphone).
```bash
modal profile activate sta-ahmed09
modal secret create orvane-secrets --from-dotenv .env PUBLIC_URL=https://sta-ahmed09--orvane-rh.us-east.modal.run --force
modal deploy modal_deploy.py
modal app logs orvane-rh
```
A secret change alone does not restart the container: `modal container list`, then `modal container stop <id> --yes`.

**Any server:** `docker compose up -d --build` behind an HTTPS reverse proxy.

## Known limits and next steps

- **Authentication:** one shared password and a typed name, so the audit trail is not attributable. Next: Entra ID
  (OIDC code flow + PKCE in Flask, tokens kept server-side, app roles Recruiter / Regional HR / Admin, audit actor =
  token `oid`). Everything goes through `current_user` / `@login_required`.
- **Scale:** SQLite, one container, in-process background work (4 CVs in parallel). For 1,500–3,000 CVs per offer:
  PostgreSQL, a job queue with workers, the Batch API for screening, files in blob storage.
- **Evaluation:** small eval sets calibrated on their own data; the 70 % threshold is a judgement call. Next: a few
  hundred CVs labelled by recruiters, several runs per prompt change, recruiter/AI disagreement as a live metric.
- **Voice:** verified end to end with a synthetic audio stream, not yet with real accents and noisy rooms.
- **Fairness and privacy:** anonymization protects the evaluation, not privacy (raw CVs reach the LLM provider);
  grammatical gender in French job titles is not neutralised. Needed before production: DPIA, retention policy,
  export and erasure, a bias audit with paired CVs.
- **Operations:** no rate limiting on candidate endpoints, no tracing yet (OpenTelemetry), no automatic recovery of
  CVs whose processing was interrupted by a restart, no reminder e-mail for candidates who have not taken the interview.
