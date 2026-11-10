# RH du futur — Groupe Orvane (spec + task list)

AI proposes, recruiter decides. Every verdict is backed by a quote that code verifies. Every candidate gets a reply.

## Stack
- Backend: Python 3.11+, FastAPI, SQLAlchemy + SQLite, Pydantic v2, Anthropic SDK (Sonnet 5.5 = `smart`, Haiku 5.5 = `fast`), pdfplumber, python-docx.
- Frontend: React + Vite + TypeScript + Tailwind, built to static files and served by FastAPI (one deployable).
- Voice: ElevenLabs Agents (`@elevenlabs/react`), post-call webhook + polling fallback. Text chat is the fallback and shares plan/transcript/scoring.
- Deploy: `modal_deploy.py` (Modal, 1 container, SQLite on a Volume) and `Dockerfile` (own server).
- Secrets: `.env` (`ANTHROPIC_API_KEY`, `ELEVENLABS_API_KEY`, `ELEVENLABS_AGENT_ID`, `APP_PASSWORD`, `SECRET_KEY`, `PUBLIC_URL`).

## Pipeline (candidate state)
`uploaded → parsed → screened → {invited | in_review | reject_proposed} → interviewed → decided → replied`

1. **Parse**: pdf/docx/txt → text. Scanned PDF/image → Claude document/vision. Hidden text (white or ≤3pt) detected and reported.
2. **Profile extraction** (Haiku): name, email, phone, city, age, title, years of experience, education, languages, skills, certifications. Email/phone verified literally present in text.
3. **Anonymize**: strip name/email/phone/city/age/address from the text the evaluator sees.
4. **Evaluate** (Sonnet): per-criterion verdict `met|partial|not_met|not_evidenced` + quote. Code verifies the quote exists (downgrade to `not_evidenced` otherwise). Injection scan flags manipulation attempts; flagged text is ignored.
5. **Triage (pure code)**: weighted score (must=3, nice=1; met=1, partial=.5, not_evidenced=.3, not_met=0). Any must `not_met` ⇒ never Yes. Injection ⇒ never Yes.
   Yes ≥ 0.70 → pre-qualification passes (invite). Maybe ≥ 0.45 → human review (one-click invite). Else No → rejection proposed.
6. **Pre-interview**: unique token link, consent, voice (orb UI) or text. Question plan from job criteria + CV gaps. Agent has no tools but `end_call`.
7. **Interview scoring**: transcript graded per criterion 0–3 with verified transcript quotes; code computes note /10; one-page synthesis (strengths, doubts, points to probe, logistics, blockers).
8. **Decision**: recruiter Accept/Reject/Override + comment. Audit log append-only.
9. **Replies**: Haiku drafts per candidate (language of candidate); recruiter approves (batch possible); sending is mocked.

Criteria have `kind` (must|nice) and `source` (cv|interview). Interview-source criteria (availability, mobility, salary, shifts…) are never penalized at screening.

## Pages
Recruiter: `/login`, `/jobs`, `/jobs/:id` (criteria + CV drop zone), `/jobs/:id/candidates` (table: name, email, phone, city, title, experience, education, languages, CV score, interview note, pre-qualification), `/candidates/:id`, `/jobs/:id/outbox`, `/audit`.
Candidate: `/i/:token` (welcome + consent), `/i/:token/interview` (orb), `/i/:token/done`.

## Tasks (do in order; each must be verified before moving on)
- [x] T0 Scaffold: backend + frontend shell, DB models, LLM wrapper (+mock), auth, audit, Dockerfile, modal_deploy.py
- [x] T1 Jobs + criteria extraction/editing
- [x] T2 CV pipeline: parse, hidden text, profile, anonymize, evaluate, verify, triage + eval script on 6 CVs
- [x] T3 Candidates table + candidate detail page (highlighted quotes, criteria grid)
- [x] T4 Pre-interview: plan, token pages, consent, text mode, scoring + synthesis
- [x] T5 Voice: ElevenLabs agent, orb UI, webhook + polling
- [x] T6 Decision buttons, audit page, outbox/replies
- [x] T7 Polish, surprise-CV tests, README + Known limits, deploy

## Known limits (to state honestly in README)
LLM vendors process raw CVs (anonymization protects the evaluation from bias, not privacy); SQLite single instance; shared password auth; mocked email; interview scoring is advisory; no bias audit on real data.
