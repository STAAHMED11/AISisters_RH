# RH du futur — Groupe Orvane

**Live app:** https://sta-ahmed09--orvane-rh.us-east.modal.run (Modal, always warm) · login = the `APP_PASSWORD` from your `.env`.

> Quick links: [What it is](#1-what-the-app-is) · [How it works](#3-how-it-works-end-to-end) · [Architecture](#4-architecture) · [Backend files](#6-backend-file-by-file) · [API](#7-api-reference) · [Frontend files](#8-frontend-file-by-file) · [Where do I change X?](#13-where-do-i-change-x) · [Look and feel](#9-look-and-feel-design-system) · [Deploy](#12-deployment-modal--docker) · [Known limits](#15-known-limits-honest)

---

## 1. What the app is

A tool for Orvane's recruiters (brief: Sylvie Marchetti, 1,500 applications per offer, "I want my recruiters to read ten CVs, not 1,500"). It:

1. **reads every CV** against the job post and gives each criterion a verdict **backed by a quote that code verifies**;
2. runs a **voice (or text) pre-interview** with the candidates who fit, replacing the 15-minute pre-qualification call;
3. gives the recruiter **only the worthwhile profiles**, with a one-page synthesis and a note out of 10;
4. keeps the **human in charge**: the AI proposes, the recruiter decides, every override is logged;
5. makes sure **every candidate gets an answer** (personalised, approved before sending);
6. shows **what it costs** (per offer, per CV, per pre-interview) and keeps **a history of everything that happened** on each candidate (Historique tab).

```
Job post ─► criteria (must/nice × cv/interview, editable)
CVs ─► parse ─► hidden-text scan ─► profile + injection scan ─► anonymize ─► evaluate (quote per verdict, verified by code) ─► triage (code)
   Yes (≥ 70 %, no failed must-have) → pre-interview      Maybe → human review (1 click to invite)      No → refusal proposed, validated by the recruiter
Pre-interview (voice orb or text) ─► transcript ─► grades per criterion (verified quotes) ─► note /10 + synthesis
Recruiter: Retain / Refuse (+ comment, mandatory if contradicting the AI) ─► personalised reply drafted ─► approved ─► e-mailed ─► logged in the candidate's history
```

## 2. What was built (build log)

| Step | Delivered |
|---|---|
| Conception | Read the brief, Sylvie's call notes and the 6 CVs; found the traps (hidden prompt-injection in Paul's CV, Ana's French B1 vs "français courant indispensable", Thomas's consulting profile, English CV). Chose the stack and the work split. |
| T0 | Scaffold: Python API + SQLite + React, auth, audit log, LLM wrapper, Dockerfile, Modal script. |
| T1 | Offers and criteria: paste a job post → criteria extracted (must/nice × cv/interview) and editable. |
| T2 | CV pipeline: parse (PDF/DOCX/image), hidden-text detection, profile extraction, anonymization, injection scan, evaluation with verified quotes, triage in code, eval on the 6 CVs. |
| T3 | Candidates table, candidate page (highlighted quotes, criteria grid). |
| T4 | Pre-interview: plan from criteria + CV gaps, token links, consent, text chat, scoring + synthesis. |
| T5 | Voice: ElevenLabs agent ("Camille"), animated orb UI, transcript fetch, voice cost. |
| T6 | Decisions (override needs a comment), batch refusals, outbox with personalised replies. |
| T7 | Surprise-CV stress set, Docker verified, honest limits. |
| Stack migration | Backend **FastAPI → Flask** (Blueprints, `@login_required`, Pydantic kept for validation, a dedicated background thread pool, gunicorn). Frontend **Vite SPA → Next.js 16 App Router** (route groups, `next/navigation`, voice loaded with `next/dynamic`, `/api` proxied to Flask). One container runs both. The 36 tests were ported and pass. Ported to match AI Sisters' stack (Flask + Next.js). |
| After | Threshold 70 %; e-mail invitations with an expiry date (SMTP-ready); per-offer cost page (the all-offers cost page was later removed); per-candidate history (the standalone audit page was removed as not needed; the log itself stays); native French voice; recruiter-experience redesign (to-do list, funnel, next-action column, sticky decision bar); **deployed on Modal**. |

**Problems found and fixed on the way** (useful for the oral Q&A):
- The 5.x models reject a forced `tool_choice` → switched to **native structured outputs** (`messages.parse`).
- "Schema too complex" → output schemas must have **required** fields (no defaults/nullable unions).
- **Thinking tokens count against `max_tokens`** → a response was cut mid-JSON. Fixed: thinking disabled on the cheap tier, large token floor, retry with double budget on truncation.
- Editing criteria **silently wiped candidates' evidence** (ids re-created, cascade delete) → ids are now preserved; changed criteria flag candidates as *stale*; one-click re-analysis.
- A DB auto-migration left NULLs → backfill + NULL-tolerant code.
- The voice was an English-native voice speaking French ("obviously AI") → native French voice + newer TTS model + spoken-style wording.
- Inputs lost focus on every keystroke (components defined inside components) → plain render functions.
- White text on a dark sidebar was flagged as hidden text → hidden only if no dark background behind it.
- **Double creation of the interview** (`UNIQUE constraint failed: interviews.candidate_id`): the background preparation for a pre-qualified candidate (≈ 10 s of AI) collided with a recruiter click. Now the link is created **instantly** (no AI call), the plan and the invitation draft are built **once** in the background behind per-candidate locks, and the candidate page waits for the plan only if the link is opened within those seconds. Regression tests reproduce the race.
- **Anonymization order**: replacing the name first turned `jean.dupont@school.tn` into `[CANDIDAT].[CANDIDAT]@school.tn`, which the e-mail pattern missed, leaking the domain. E-mails and links are now removed before names.

## 3. How it works, end to end

1. **Offer** — the recruiter pastes the job post (`POST /api/jobs`). Sonnet extracts criteria (`routers/jobs.extract_criteria`, prompt `CRITERIA_SYSTEM`). A fairness filter drops any criterion targeting a protected attribute (`jobs._BANNED`). Each criterion has a **kind** (`must` = blocking, `nice`) and a **source** (`cv` = scored at screening, `interview` = checked orally, never penalised at screening).
2. **Upload** — CV files are stored in the DB and processed in the background (`routers/candidates.upload_cvs` → `screening/pipeline.process_candidate`, max 4 in parallel).
3. **Parse** (`cv/parse.py`) — PDF via pdfplumber, DOCX via python-docx, images and scanned PDFs via Claude vision. **Hidden text** (white without a dark background, ≤ 3 pt, Word "vanish") is split from visible text: the evaluator never sees it; the injection scan does.
4. **Profile + injection scan in parallel** — Haiku extracts name, e-mail, phone, city, experience, education, languages… (e-mail/phone must literally exist in the CV, checked in code). A second Haiku call plus a regex flag manipulation attempts. Hidden text is shown as evidence.
5. **Anonymize** (`cv/anonymize.py`) — name, e-mail, URLs, age, address, phone, ZIP and the header city are replaced by placeholders. The evaluator only sees this version ("what the AI read" is viewable by the recruiter).
6. **Evaluate** — Sonnet gives each `cv` criterion a verdict (`met / partial / not_met / not_evidenced`) **and a quote**. `screening/verify.py` checks the quote exists in the CV (normalised + fuzzy). **No verified quote ⇒ downgraded to `not_evidenced`.** Prompts encode language-level equivalences (B2 ≈ "professionnel", native ≥ "courant"), tool equivalences (SAP WM ≈ EWM) and "no prestige bias".
7. **Triage — pure code** (`screening/triage.py`): score = weighted average (must ×3, nice ×1; met 1, partial 0.5, not_evidenced 0.3, not_met 0). **Yes** ⇔ score ≥ 70 % **and** no failed must-have **and** no injection. **Maybe** ⇔ ≥ 45 % (or blocked). **No** otherwise → refusal *proposed*. The LLM never sets a score. Thresholds: `YES_THRESHOLD` / `MAYBE_THRESHOLD`; changed thresholds are re-applied at startup (`screening/retriage.py`, no LLM call).
8. **Pre-interview** — for "Yes" candidates a plan and a unique link are prepared automatically; for others the recruiter clicks *Inviter*. `interview/service.build_plan` writes ≈ 10 questions from the criteria and the CV gaps (logistics, verify a claim, probe a gap, closing; a language check is asked *in* that language). The e-mail invitation contains the link and a **deadline** (`INTERVIEW_VALID_DAYS`, default 7); after it the link returns 410.
9. **The interview** — candidate opens `/i/<token>` (no account), consents, chooses **voice** (ElevenLabs agent, orb UI) or **text** (our own Haiku loop with the same prompt). Mic denied → text fallback. The agent has no tool except `end_call`; everything the candidate says is data, not instructions.
10. **Scoring** (`interview.service.score_interview`) — Sonnet grades each criterion 0–3 (or −1 = not covered) with a **verified quote from the candidate**, lists strengths/doubts/points to probe/logistics/blockers/CV-vs-interview discrepancies and flags manipulation. **Note /10 and global score are computed in code** (`interview_note`; global = 0.4·CV + 0.6·interview).
11. **Decision** — sticky bar on the candidate page: *Retenir* / *Refuser*. If it contradicts the AI proposal (`comms.ai_proposal`), a comment is required and the event is logged as `decision_override`. A personalised reply is drafted (Haiku) for the outbox.
12. **Replies** — the recruiter reads/edits/approves in *Courriers*; sending goes through SMTP (or is simulated if none is configured). The counter "sans réponse" shows candidates decided but not yet answered.
13. **History & costs** — every action is logged (`audit.log_event`); every LLM call and voice call is metered (`costs.py`).

## 4. Architecture

```
 Browser ──► Next.js 16 (App Router, React 19, :3000) ── rewrites /api/* ──► Flask (:8000, internal)
   ├─ Recruiter app  /jobs /jobs/:id /jobs/:id/candidates /candidates/:id /jobs/:id/outbox /costs
   └─ Candidate app  /i/:token  →  /interview (voice orb | text chat)  →  /done           (no login)
            │ JSON over /api            │ WebSocket (voice, signed URL)
            ▼                           ▼
 Flask (Python, gunicorn) ─────────►  ElevenLabs Agents  (STT + Gemini Flash LLM + TTS "Camille")
   routers ─ services ─ pipeline          ▲ transcript + cost fetched by polling after the call
   │   │
   │   └──► Anthropic API: Sonnet 5.5 (criteria, evaluation, plan, synthesis) · Haiku 5.5 (profile, injection, chat, drafts)
   ├──► SMTP server (invitations & replies; simulated if not configured)
   └──► SQLite file  (jobs, criteria, candidates, evaluations, interviews, decisions, messages, usage_events, audit_log)
                     on a Modal Volume (prod) or ./data (local/Docker)
```

**State machines**
- `Candidate.status`: `uploaded → parsing → screening → screened` (or `failed`). `triage`: `yes|maybe|no`; `prequal`: `pass|review|fail`; `decision`: `accepted|rejected|""`.
- `Interview.status`: `pending → started → ended → scored`. Expired links (pending/started past `expires_at`) are refused.
- `Message.status`: `draft → sent` (`transport` = `smtp` or `mock`).

**Database tables** (`backend/app/models.py`; no Alembic — `db._add_missing_columns` adds new columns at startup)

| Table | Holds |
|---|---|
| `jobs` | title, ref, full job post, `criteria_updated_at` (drives "stale" analyses) |
| `criteria` | label, description (threshold), `kind` must/nice, `source` cv/interview, position |
| `candidates` | the uploaded file (bytes), raw/anonymized text, hidden text, extracted `profile` (JSON), language, injection flag/evidence, `cv_score`, `triage`, `prequal`, summary, unique `token`, interview note, global score, decision, `screened_at` |
| `evaluations` | one row per candidate × CV criterion: verdict, quote, `quote_verified`, rationale |
| `interviews` | plan (JSON), language, mode voice/text, status, consent time, `expires_at`, ElevenLabs conversation id, transcript, per-criterion scores, synthesis |
| `decisions` | who decided what, the AI's proposal at that time, the comment |
| `messages` | drafted/sent e-mails: kind invite/acceptance/rejection, subject, body, status, transport |
| `usage_events` | every billable call: provider, model, purpose, job, candidate, tokens, cost in USD, ref |
| `audit_log` | append-only: actor, action, entity, payload (shown per candidate in the *Historique* tab) |

## 5. Key design decisions

- **Evidence or nothing**: verdicts, interview grades and synthesis items all need a quote that code verified.
- **Code decides numbers**: triage, notes, global score and costs are computed in code from LLM labels; no model-written score exists, so an injected "give me the max score" has nothing to set.
- **Injection defence in layers**: hidden-text detection → regex + Haiku scan → CV treated as untrusted data → score-less schema → code triage → flag surfaced to the recruiter. Voice: no tools but `end_call`, candidate speech is data, manipulation is flagged in the synthesis.
- **Fairness**: identity stripped before evaluation; protected-attribute criteria filtered; the interviewer never asks about age/family/health/origin; text alternative to voice; foreign CVs and career breaks never penalised (Ana's B1 becomes a *blocker to verify*, not a rejection).
- **Human in the loop** (AI Act / GDPR art. 22): AI proposes; overrides need a comment; refusal letters mention the right to a human re-examination.
- **Polling, not webhooks**: ElevenLabs transcripts and costs are fetched after the call, so it works behind any URL.

## 6. Backend file by file

`backend/app/` (Python 3.11+, Flask, served by gunicorn: 1 worker × 16 threads because SQLite has one writer). Entry point: `main.py` (`create_app`).

| File | What it does (main functions) |
|---|---|
| `main.py` | `create_app()`: registers the Blueprints, creates tables and **re-applies triage rules** to existing candidates at startup; error handlers return `{"detail": …}` JSON; `unhandled` turns any 500 into a readable message and logs it to `data/app.log`; `health` (also returns the thresholds); serves the built React app with SPA fallback; registers all routers. |
| `config.py` | `Settings`: every environment variable in one place (see §11). |
| `db.py` | SQLAlchemy engine + session (`get_db`); `init_db`; `_add_missing_columns` (tiny auto-migration with backfill); `PRAGMA journal_mode` configurable (`WAL` locally, `DELETE` on Modal's network volume). |
| `models.py` | The tables above (`Job, Criterion, Candidate, Evaluation, Interview, Decision, Message, UsageEvent, AuditLog`). |
| `schemas.py` | Pydantic models: API inputs and, importantly, the **LLM output schemas** (`CriteriaExtraction, Profile, InjectionScan, CVEvaluation, InterviewPlan, Synthesis, Draft`). LLM schemas must stay *fully required* (no defaults). |
| `llm.py` | `LLM.structured(tier, system, user, schema, usage=…)` (native structured outputs, retry with bigger budget, records usage) and `LLM.chat(...)`. Tiers: `smart` = Sonnet, `fast` = Haiku (thinking disabled). Swap provider/model here or via `MODEL_SMART/MODEL_FAST`. |
| `prompts.py` | **All prompts**, versioned by `PROMPT_VERSION`: `CRITERIA_SYSTEM`, `PROFILE_SYSTEM`, `INJECTION_SYSTEM`, `EVAL_SYSTEM` (verdict rules, equivalences), `PLAN_SYSTEM`, `AGENT_PROMPT_TEMPLATE` (Camille, shared by voice and text), `SCORE_SYSTEM`, `DRAFT_SYSTEM`, `FAIRNESS_RULES`. |
| `auth.py` | Shared-password login; signed cookie (`current_user` dependency protects recruiter routes); `secure` cookie flag when `PUBLIC_URL` is https. |
| `audit.py` | `log_event(db, actor, action, entity, id, **payload)` — one line to log anything (feeds each candidate's *Historique* tab). |
| `costs.py` | `PRICING` table, `llm_cost`, `record_llm` (called by `llm.py`), `record_voice` (uses ElevenLabs' own `cost_fiat`, deduplicated), `summarize` / `candidate_costs` for the dashboard, `PURPOSES` (call type → group + French label). |
| `comms.py` | `draft_message` (Haiku drafts invite/acceptance/rejection; **guarantees** the link and the deadline are in invitations), `ai_proposal`, `mark_sent` (HTML + text via `mailer`), `send_pending_invite` (used by `AUTO_SEND_INVITES`). |
| `mailer.py` | `send_email` (multipart text + HTML): real SMTP if `SMTP_HOST` is set, otherwise logged and flagged `mock`; `status()` (safe to show in the UI: never the user or password). `MailError` carries readable errors. |
| `emailtpl.py` | `build_html`: the HTML version of every e-mail (branded header, a real button to the pre-interview, the deadline note). The plain text is always sent too. |
| `util.py` | `aware` (timezone-safe datetimes), `format_date` (French/English dates). |

`backend/app/cv/`

| File | What it does |
|---|---|
| `parse.py` | `parse_cv` → `Parsed(text, hidden, needs_vision)`. `_parse_pdf` uses character colour/size and filled rectangles (white-on-dark is *not* hidden); `_parse_docx` uses run colour/size/vanish and shading. Scanned/short PDFs and images set `needs_vision`. |
| `anonymize.py` | `anonymize(text, profile)`: placeholders for name, e-mail, URL, age, address, phone, ZIP, header city (never employers/schools). |

`backend/app/screening/`

| File | What it does |
|---|---|
| `pipeline.py` | `process_candidate` (thread-limited) → `_process`: parse → vision transcription if needed → profile ‖ injection scan → anonymize → evaluate → verify quotes → triage → stamp `screened_at` → auto-prepare the interview for "Yes". `_scan_injection`, `_u` (usage context). |
| `verify.py` | `verify_quote`: normalises quotes/dashes/spaces, handles `…` segments, fuzzy fallback; returns the span used for highlighting. |
| `triage.py` | `cv_score` and `triage` — the whole scoring rule (weights, thresholds, gates) in 28 lines. |
| `retriage.py` | `retriage_all/candidate`: re-applies the rules to stored verdicts (instant). |

`backend/app/interview/`

| File | What it does |
|---|---|
| `service.py` | `build_plan`, `create_interview` (instant: row, token, deadline, no AI), `ensure_plan` / `ensure_invite_draft` / `prepare_assets` (built once, behind per-candidate locks), `ensure_interview` (all of it, used by the pipeline), `agent_variables` / `render_agent_prompt` (fill the `{{variables}}` of Camille's prompt), `first_message`, `agent_turn` (text mode), `score_interview` (grades with verified quotes, synthesis, `interview_note`, global score). |
| `elevenlabs.py` | `signed_url` (private agent), `fetch_conversation`, `to_transcript`, `fetch_and_score` (polls until the call is processed, stores transcript, records the real voice cost, scores). |

`backend/app/routers/` — see the API table below: `jobs.py` (offers, criteria, overview/to-do, rescreen), `candidates.py` (upload, list, detail + history, invite, send invitation, rescore), `public.py` (candidate-facing, token-based), `outbox.py` (decisions, batch refusals, e-mails, mail status and test), `costs.py`.

## 7. API reference

Recruiter routes need the login cookie; `/api/public/...` needs only the interview token.

| Method & path | Purpose |
|---|---|
| `POST /api/login`, `/logout`, `GET /api/me`, `/api/health` | session, status |
| `GET /api/jobs` · `POST /api/jobs` | list (with `todo_count`) · create from a job post |
| `GET /api/jobs/{id}` · `DELETE` | detail (criteria, stale count, cost) · delete |
| `GET /api/jobs/{id}/overview` | funnel + to-do list |
| `PUT /api/jobs/{id}/criteria` | edit criteria (ids preserved) |
| `POST /api/jobs/{id}/rescreen` · `/re-extract` | re-analyse CVs · re-extract criteria from the post |
| `POST /api/jobs/{id}/candidates` · `GET` | upload CVs · ranked list |
| `GET /api/candidates/{id}` | full dossier (evaluations with spans, interview, costs, decisions, **history**) |
| `POST /api/candidates/{id}/reprocess` · `/rescore` | retry analysis / interview scoring |
| `POST /api/candidates/{id}/invite` · `/invite/send` | **instant** link (plan built in the background) · e-mail the link (`extend` renews the deadline) |
| `POST /api/candidates/{id}/decision` | retain/refuse (+ comment; mandatory if contradicting the AI) |
| `POST /api/jobs/{id}/reject-batch` | validate all AI-proposed refusals |
| `GET /api/jobs/{id}/outbox` · `POST …/outbox/send-all` | e-mails + counters · approve & send all |
| `PUT/POST/DELETE /api/messages/{id}` (`/send`) | edit · approve & send · delete a draft |
| `GET /api/mail-status` · `POST /api/mail-test` | SMTP state (no secrets) · send a test e-mail to an address you choose |
| `GET /api/costs/jobs/{id}` | cost of one offer (per CV, per interview, per candidate, forecast) |
| `GET /api/public/interview/{token}` | candidate: info, expiry |
| `POST …/{token}/consent` · `/start` · `/message` · `/finish` | text interview |
| `GET …/{token}/voice-session` · `POST …/voice-ended` | voice: signed URL + dynamic variables · end of call |

## 8. Frontend file by file

`frontend/src/` (Next.js 16 App Router + React 19 + TypeScript + Tailwind v4). `next.config.ts` proxies `/api/*` to Flask (same origin, so the session cookie just works) and builds a `standalone` server for Docker.

| File | Role |
|---|---|
| `app/layout.tsx`, `app/(recruiter)/layout.tsx`, `app/i/[token]/…` | Root layout (fonts, `UIProvider`); the `(recruiter)` route group is the **auth gate** (`/api/me` → login screen or app shell, loads thresholds from `/api/health`); `/i/[token]` = candidate app (no login). Each `page.tsx` is a thin wrapper around a view in `views/`. |
| `lib/nav.ts` | `useSetParams()`: update the query string (filters, tabs) — Next's `useSearchParams` is read-only. |
| `api.ts` | `fetch` wrapper that surfaces the server's readable error message. |
| `index.css` | Tailwind theme + shared classes (`btn-primary`, `card`, `badge`…); brand colours live in `@theme`. |
| `views/Login.tsx`, `Jobs.tsx` | Login · offers list with "N à traiter" and a **delete** button per offer (confirmation dialog; deletes its candidates, interviews and e-mails). |
| `views/JobDetail.tsx` | **Offer page**: drop zone, funnel, "À faire" list, collapsible criteria editor (inline, floating save bar), job post. |
| `views/Candidates.tsx` | Table: filter tabs with counts, **next-action column** (`nextAction()`), batch refusals. |
| `views/CandidateDetail.tsx` | Dossier with three tabs — *Synthèse* (AI summary, interview, decision history), *Critères et CV* (verdicts with quotes, highlighted CV), *Historique* (this candidate's timeline) — plus injection banner and sticky decision bar. |
| `views/Outbox.tsx` | **E-mail status card** (real SMTP or simulated, auto-send flag, *send a test e-mail*), review/edit/approve messages, delivery state, "no reply yet" counters. |
| `views/CostJob.tsx` | Cost of one offer (*Coût de l'offre* in the side rail): total and split, cost per CV and per pre-interview, voice minutes, tokens, and the forecast calculator. |
| `views/candidate/Welcome.tsx` | Consent, FR/EN, voice or text, deadline, expired page. |
| `views/candidate/Interview.tsx`, `VoiceInterview.tsx`, `TextInterview.tsx`, `Done.tsx`, `Shell.tsx` | Interview screens: ElevenLabs session + orb + captions + mic-denied fallback; chat; thank-you; dark layout. |
| `components/InterviewPanel.tsx` | Recruiter side of the interview: invitation bar (send/renew), QR + link, plan, synthesis, grades, transcript. |
| `components/DecisionBar.tsx`, `DecisionPanel.tsx` | Sticky decision bar · decision history/changes. |
| `components/Orb.tsx` | Canvas orb that reacts to mic/voice volume. |
| `components/CostBar.tsx` | Cost chart pieces (palette validated for colour-blindness, light mode). |
| `components/ui.tsx` | Shared pieces: verdict/triage badges, **lane colours**, score bar with the threshold tick, avatar, page header, skeletons, empty state. |
| `components/Layout.tsx` | App shell: dark side rail with a contextual « Offre en cours » group. |
| `lib/ui.tsx` | `UIProvider`: `confirm()` dialog and toasts (replaces the browser's `alert/confirm`). `lib/events.tsx`: turns stored events into sentences for the history tab. |
| `lib/i18n.ts`, `lib/money.ts` | Candidate-facing FR/EN strings · USD formatting. |

## 9. Look and feel (design system)

Idea taken from the warehouse itself — **sorting lanes, dock signage, shipping tags, a marker pen** — so the interface says what the product does.
- **Colour** (tokens in `frontend/src/index.css`, `@theme`): concrete canvas `#F2F3EF`, ink `#0F1B24`, **petrol blue** `#0B4F6C` as brand, **highlighter yellow** `#FFE45C` used only for quoted evidence (and the active marker in the side rail). Status colours stay semantic (green = pre-qualified, amber = to examine, rose = refused). Tailwind's `slate` and `indigo` scales are redefined there, so every utility inherits the palette.
- **Type**: *Barlow Condensed* (road/transport signage) for titles and big numbers, *IBM Plex Sans* for text. Labels are sentence case, no tracked all-caps.
- **Structure carries information**: a coloured **lane stripe** on each candidate row (triage outcome); the funnel is one **shipping tag** with dashed perforations; the score bar carries a **tick at the pre-qualification threshold**; the login screen enlarges the three lanes of the logo.
- **Elevation only for floating things** (sticky decision bar, dialogs, toasts); content surfaces are flat and bordered.
- **Candidate side** (phone first): dark petrol page, same fonts, orb colours changing with the call state (teal = listening, amber = speaking).
- **Behaviour**: proper dialogs and toasts instead of browser pop-ups, skeleton loaders, empty states that say what to do, visible keyboard focus, reduced-motion respected.
- To restyle: change the tokens in `index.css`; component classes (`btn-primary`, `card`, `badge`, `input`) are defined there too.

## 10. Scripts, evals and tests

| What | Command |
|---|---|
| Unit/API tests (36, hermetic: `conftest.py` blanks every API key and the SMTP settings, so a test can never call a paid API or send a real e-mail) | `.venv/bin/python -m pytest backend/tests` |
| **CI/CD** (GitHub Actions, `.github/workflows/ci.yml`) | On every push / PR: pytest · Next.js lint + typecheck + build · Docker build. On `main`, once all are green: `modal deploy` + health check of the live URL. Needs the repo secrets `MODAL_TOKEN_ID` / `MODAL_TOKEN_SECRET` (without them the deploy job is skipped). |
| Eval on the 6 given CVs vs expected outcomes (real LLM) | `.venv/bin/python -m evals.run_eval` |
| 8 generated "surprise" CVs (sidebar PDF, hidden injection, scanned PNG, English, off-topic, recipe, empty…) | `python -m evals.make_surprise && python -m evals.run_eval --surprise` |
| Simulated candidate (honest / jailbreak / off-topic / terse) against a running server | `python -m evals.sim_interview --base URL --password … --candidate ID [--persona jailbreak]` |
| Create/update the ElevenLabs agent (voice, model, prompt) | `.venv/bin/python scripts/setup_agent.py [--voice ID] [--tts-model …]` |
| Compare voices by ear | `.venv/bin/python scripts/voice_samples.py` → `docs/voice-samples/*.mp3` |
| Agent smoke test over text (no mic) | `scripts/test_agent_text.py <candidate_id>` |
| Demo data (job post + the 6 CVs, screened) | `.venv/bin/python scripts/seed_demo.py` |
| Test the e-mail sending end to end | upload `test-cvs/CV test - Ahmed Sta.docx` (git-ignored; contains the owner's real address), then *Envoyer l'invitation par e-mail* |

Last results: **6/6** and **8/8** on the evals (run after the 70 % threshold change), 36/36 tests. Re-run the evals before the demo: LLM output varies.

## 11. Configuration (`.env`)

| Variable | Meaning |
|---|---|
| `ANTHROPIC_API_KEY`, `MODEL_SMART`, `MODEL_FAST`, `LLM_TIMEOUT` | LLM access and models (defaults `claude-sonnet-5-5` / `claude-haiku-5-5`). |
| `ELEVENLABS_API_KEY`, `ELEVENLABS_AGENT_ID` | Voice (the agent id is written by `setup_agent.py`). `ELEVENLABS_WEBHOOK_SECRET` is reserved and unused (polling is used). |
| `APP_PASSWORD`, `SECRET_KEY` | Recruiter password · cookie-signing secret (use a long random value). |
| `PUBLIC_URL` | **Public address, used in invitation links.** Must be the real https URL in production. |
| `YES_THRESHOLD` (0.70), `MAYBE_THRESHOLD` (0.45) | Triage thresholds. |
| `INTERVIEW_VALID_DAYS` (7) | Validity of interview links. |
| `AUTO_SEND_INVITES` (0) | `1` = e-mail the pre-interview link to pre-qualified (Yes) candidates automatically, without a click. Off by default: sending stays a recruiter action. Needs `SMTP_HOST`. |
| `SMTP_HOST`, `SMTP_PORT` (587), `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`, `SMTP_TLS` | E-mail. Empty `SMTP_HOST` ⇒ sending is simulated. |
| `DATA_DIR`, `DB_JOURNAL` | Where the SQLite file lives; journal mode (Modal sets `DELETE`). |

## 12. Deployment (Modal & Docker)

**Currently deployed on Modal**: app `orvane-rh`, URL `https://sta-ahmed09--orvane-rh.us-east.modal.run`. One container built from the `Dockerfile` (Next.js + Flask), always warm (`min_containers=1`), 2 CPU / 2 GB, SQLite on the Volume `orvane-data` (committed every 5 s), secrets in the Modal secret `orvane-secrets`. HTTPS comes with Modal — required for the microphone.

```bash
modal profile activate sta-ahmed09            # the workspace that hosts the app (once per machine)
# change code, then:
modal deploy modal_deploy.py              # builds the Dockerfile (Next.js + Flask) and redeploys

# change a setting / secret (e.g. password, SMTP):
#   edit .env, then
modal secret create orvane-secrets --from-dotenv .env PUBLIC_URL=https://sta-ahmed09--orvane-rh.us-east.modal.run --force
modal deploy modal_deploy.py              # restarts the container with the new secret
modal app logs orvane-rh                  # live logs
```
Data survives redeploys (Volume). The app log is also in the volume (`/data/app.log`).

**Linking the e-mail** (the *Courriers* page shows « Envoi simulé » until then, and has a *Tester l'envoi* button to validate the credentials): add to `.env`
```
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=you@gmail.com
SMTP_PASSWORD=<Google app password>         # or Resend: smtp.resend.com, port 465, user "resend", password = API key
SMTP_FROM=Recrutement Orvane <you@gmail.com>
```
then run the two `modal` commands above. Sending is then real: each invitation is a branded HTML e-mail (with a text fallback) containing a button to the pre-interview and its deadline. Optional: `AUTO_SEND_INVITES=1` sends the invitation automatically to pre-qualified candidates.

**Docker / your own server**: `docker compose up -d --build`, then open http://localhost:3000. One image, two processes (`start.sh`): Next.js on :3000 (public) and Flask/gunicorn on :8000 (internal). Data in a named volume; put it behind HTTPS (e.g. Caddy) for the microphone.

**Local development** (two terminals):
```bash
cp .env.example .env
python3 -m venv .venv && .venv/bin/pip install -r backend/requirements.txt
.venv/bin/python scripts/setup_agent.py                                   # ElevenLabs agent (once)
.venv/bin/flask --app backend.app.main:app run --port 8000 --debug        # API
(cd frontend && npm ci && npm run dev)                                    # UI with hot reload → http://localhost:3000
```

## 13. Where do I change X?

| I want to… | Change |
|---|---|
| Make pre-qualification stricter/looser | `YES_THRESHOLD` in `.env` (restart: candidates are re-labelled). Weights/verdict values: `screening/triage.py` (`KIND_WEIGHT`, `VERDICT_VALUE`). |
| Change how a CV is judged (rules, equivalences, strictness) | `prompts.py` → `EVAL_SYSTEM`; bump `PROMPT_VERSION`; re-run `evals.run_eval`. |
| Change what the interview asks | `prompts.py` → `PLAN_SYSTEM` (question kinds, count, language checks). |
| Change Camille's personality / rules / tone | `prompts.py` → `AGENT_PROMPT_TEMPLATE`, then `python scripts/setup_agent.py` to push it to ElevenLabs. Greeting: `interview/service.first_message`. |
| Change the voice or TTS model | `python scripts/setup_agent.py --voice <id> --tts-model <id>` (compare with `voice_samples.py`). |
| Change the e-mail wording | `prompts.py` → `DRAFT_SYSTEM`; guaranteed link/deadline lines: `comms.draft_message`. |
| Change link validity | `INTERVIEW_VALID_DAYS`. |
| Add/replace the mail provider | `mailer.py` (`send_email`) + `SMTP_*`. |
| Change models | `MODEL_SMART` / `MODEL_FAST`; add their prices to `costs.PRICING`. |
| Track a new kind of call in the per-offer cost page | pass `usage={"job_id":…, "candidate_id":…, "purpose":"x"}` to `llm.structured/chat`; add `x` to `costs.PURPOSES`. |
| Change anonymization | `cv/anonymize.py`. Hidden-text rules: `cv/parse.py`. Banned criteria words: `routers/jobs._BANNED`. |
| Add a field to criteria/candidates | `models.py` (new columns are added automatically) → `schemas.py` → the router → the page. |
| Change the to-do list rules | `routers/jobs.job_overview`. Row "next action": `views/Candidates.nextAction`. |
| Reword the history events | `lib/events.tsx` (`describeEvent`). Cost colours/labels: `components/CostBar.tsx`. |
| Edit candidate-facing text / add a language | `lib/i18n.ts` (+ `interview/service.LANG_NAMES`). |
| Change brand colours / fonts | `frontend/src/index.css` (`@theme`, Google Fonts link in `index.html`). Orb colours: `components/Orb.tsx`. Lane colours: `components/ui.tsx` (`laneClass`). |
| Change the e-mail look | `emailtpl.py` (HTML) · wording in `prompts.py` (`DRAFT_SYSTEM`). |
| Change the login | `APP_PASSWORD` (single shared password) — real SSO would replace `auth.py`. |
| Give the server more power / keep it warm | `modal_deploy.py` (`cpu`, `memory`, `min_containers`). |

## 14. Troubleshooting

- **"Erreur serveur …" / 500** → the message is shown in the UI; details in `data/app.log` (local) or `modal app logs orvane-rh` / `/data/app.log` (Modal).
- **Zero tokens in the Anthropic console** → the calls are real (check the request ids in the logs/`usage_events`); make sure you look at the right organization/workspace for that API key.
- **Voice silent / not starting** → needs https or localhost and mic permission; mic denied falls back to text. Check `ELEVENLABS_AGENT_ID`.
- **Invitation link points to localhost** → `PUBLIC_URL` is wrong in the Modal secret (it must include the region, e.g. `….us-east.modal.run`).
- **« Envoi simulé » on the Courriers page** → fill `SMTP_*` (see §12).
- **Verdicts look out of date** → criteria changed: use "Ré-analyser" on the offer page.

## 15. Known limits (honest)

- **Voice was verified end to end with a synthetic audio stream** (connect, agent speaks, orb states, captions, end call, transcript and cost fetch, scoring) and the logic over text. **Not verified with a real human voice**: accents, noise, barge-in and ASR quality on non-native speakers. Rehearse on the demo device.
- **Evals are small and calibrated on their own data** (6 + 8 CVs; no test CV scores between 70 and 75 %, so 70 % rests on judgement and Sylvie's "I prefer a few false positives"). LLM output varies between runs; borderline cases (e.g. Thomas) flip between Maybe and No. No bias audit on real candidates.
- **Anonymization protects the evaluation from bias, not privacy**: the raw CV still goes to the LLM vendor for profile extraction. Production needs a DPA/EU region, a retention policy and erasure/export tooling (none implemented).
- **Single shared password**, SQLite on one container, no rate limiting on public endpoints, no automatic data deletion.
- **Scale**: 4 CVs in parallel in-process (6–8 CVs ≈ 25–40 s). 1,500 CVs would need a queue, a cheap pre-filter and measured costs (the per-offer cost page gives them).
- **Parsing**: exotic multi-column PDFs can interleave text; scanned CVs use vision (tested on one PNG); hidden text detection covers colour/size, not off-page text.
- **Costs**: Anthropic prices are a static table (`costs.PRICING`); ElevenLabs cost is theirs (plan credits not modelled); the forecast is only as good as its sample.
- Interview scoring is advisory (0–3 rubric over ~10 minutes).

**Before putting it in every recruiter's hands**: SSO + roles, Postgres and a job queue, consent/retention/erasure and a DPIA, a bias audit and calibration on a few hundred labelled CVs, ElevenLabs webhook + alerting, real e-mail with human re-examination, per-call cost alerts, a TalentBox connector.
