# RH du futur (Groupe Orvane)

My answer to the "La RH du futur" test.

*En bref : l'application lit les CV, les trie avec une preuve pour chaque verdict, fait passer un pré-entretien
(voix ou écrit) et donne une synthèse au recruteur, qui prend toutes les décisions. Le reste de ce document est en anglais.*

Sylvie's recruiters get about 1,500 CVs per job offer. This app reads the CVs for them, runs a first interview with
the candidates who match, and gives the recruiter a short summary. The recruiter makes every final decision.

**Try it:** https://sta-ahmed09--orvane-rh.us-east.modal.run (the password is sent separately)

## What you can do in the app

1. **Create an offer.** Paste the job post. The app turns it into a list of criteria that you can edit.
2. **Upload CVs** (PDF, Word, image or scan). After about 30 seconds each CV is sorted into one of three groups:
   *pré-qualifié*, *à examiner* or *non*.
3. **Open a candidate.** For each criterion you see a verdict and the sentence of the CV that justifies it,
   highlighted in the CV.
4. **Invite the candidate to the pre-interview.** They get a personal link (by e-mail or QR code) and answer when they
   want, by voice or in writing. No account needed.
5. **Read the summary** of the interview: a note out of 10, strong points, doubts, availability, salary, etc.
6. **Decide**: keep or refuse. The app writes the e-mail, you read it, then you send it.

## How a CV is judged

1. The file is read. Text that a human cannot see (white on white, tiny font) is set aside.
2. The name, e-mail, phone, age and address are removed, so the CV is judged without knowing who it is.
3. The AI checks each criterion and answers with one of four labels: met, partly met, not met, not mentioned.
   For each answer it must quote the CV.
4. **The code checks that the quote really is in the CV.** If it is not, the answer is thrown away.
5. **The code computes the score**, not the AI. Required criteria count three times more than optional ones.
   - 70 % or more, and no required criterion failed: *pré-qualifié*
   - 45 % or more: *à examiner* (a recruiter looks)
   - below: *non*, but only as a proposal that a recruiter confirms

The interview is graded the same way: one label per criterion, with a quote from what the candidate said,
checked by the code.

## Choices I made, and why

- **A quote for every verdict.** Sylvie's managers complained that they did not know why a profile was kept.
  It also stops the AI from inventing things.
- **The AI never gives a score.** A score from a model changes from one run to the next and cannot be explained.
  A formula in code gives the same result every time and can be tested.
- **Cheating is handled.** One of the test CVs hides a message telling the AI to give the maximum score.
  That text is removed before the evaluation, the attempt is shown to the recruiter, and since the AI has no
  score to give, the message has nothing to change.
- **"Not mentioned" is not "failed".** A CV that says nothing about a criterion loses a few points but is not
  eliminated. Sylvie said she prefers a few false positives over missing a good profile.
- **A failed required criterion does not reject the candidate.** It sends them to *à examiner*. Example: Ana has
  the experience but writes "French B1". She is not refused; the interview asks her a question in French.
- **Nothing is sent or decided without a recruiter.** If the recruiter disagrees with the AI's proposal,
  they must write why, and it is saved in the candidate's history.
- **Voice and text.** Voice is closer to the phone call it replaces and lets us hear the candidate's English.
  Text is always available (no microphone, noisy place, personal preference).

## Technical choices

| Part | Choice | Why |
|---|---|---|
| API | **Flask** | Simple and explicit: one file per area (offers, candidates, e-mails, costs). Runs behind gunicorn. |
| Validation | **Pydantic** | The same tool checks what the browser sends and forces the AI to answer in a fixed shape. |
| Database access | **SQLAlchemy** | The code does not depend on the database: changing it means changing one address. |
| Database | **SQLite** | Nothing to install, everything in one file, the whole app starts with one command. The slow part is the AI calls, not the database. |
| Background work | **Thread pool** | A CV takes 5 to 40 seconds to analyse. The page answers at once and the analysis runs after, 4 CVs at a time. |
| Interface | **Next.js** and **React** | One layout protects every recruiter page, while candidate pages (`/i/<link>`) need no account. Next.js also forwards `/api` to Flask, so the browser talks to a single address and the login cookie just works. |
| Types and style | **TypeScript** and **Tailwind** | The build stops on a type error. Colours are defined once. |
| Judging | **Claude Sonnet** | Evaluating a CV, writing the interview questions and grading the interview need judgement. |
| Simple tasks | **Claude Haiku** | Profile extraction, cheating detection, written interview, e-mails. About 20 times cheaper than Sonnet. |
| AI answers | **Structured outputs** | The model answers in a schema, not free text, and each verdict can only be one of four values. |
| Anonymization, quote check, score | **Plain code** | Free, same result every time, easy to test. No model involved. |
| Voice interview | **ElevenLabs** | It handles listening, turn-taking and speech. Building that live audio chain was not the point of the project. |
| Voice connection | **WebSocket** with a signed link | A call needs sound flowing both ways without interruption. The signed link keeps the API key on the server. |
| Voice agent | **Gemini Flash** inside ElevenLabs | Fast replies, which matters in a call. |
| E-mail | **SMTP** | Standard, and nothing is sent until a recruiter approves it. |
| Packaging | **Docker**, one image | The same image runs on my machine and in production. It starts Next.js and Flask together. |
| Hosting | **Modal** | Always on, HTTPS included (the microphone needs it), deployed with one command. |
| Tests | **pytest** and **GitHub Actions** | The tests need no API key and no internet. A workflow is configured to run them on every push. |
| Costs | **One line per AI call** | Each call is recorded with its cost, which gives the cost per CV and a forecast. |

```
Browser ──► Next.js ──/api──► Flask ──► Claude, ElevenLabs, SMTP
                                └────► SQLite
```

The code is in two folders:

- `backend/app/`: the API. The important files are `screening/pipeline.py` (the steps of a CV),
  `screening/verify.py` (quote check), `screening/triage.py` (score), `cv/anonymize.py`, `interview/service.py`
  and `prompts.py` (all the prompts).
- `frontend/src/`: the interface. `app/` holds the routes, `views/` the screens.

## Run it on your machine

```bash
cp .env.example .env      # add ANTHROPIC_API_KEY, APP_PASSWORD and SECRET_KEY
docker compose up -d --build
```

Then open http://localhost:3000. Without ElevenLabs keys the interview works in text mode. Without SMTP
settings the e-mails are not really sent (the app says so).

**Demo data.** `fixtures/` holds the job post and the 6 CVs of the test. You can upload them by hand, or create
the offer and screen the 6 CVs in one go (real AI calls, needs the Python setup from the Tests section below):

```bash
.venv/bin/python scripts/seed_demo.py
```

**Voice interview.** Add `ELEVENLABS_API_KEY` to `.env`, then create the voice agent once. The script writes
`ELEVENLABS_AGENT_ID` into `.env`:

```bash
.venv/bin/python scripts/setup_agent.py
```

## Deploy

The online version runs on Modal, from the same Dockerfile:

```bash
pip install modal && modal setup
modal secret create orvane-secrets --from-dotenv .env
modal deploy modal_deploy.py      # prints the URL of the app
```

Then put that URL in `PUBLIC_URL` (it is used in the interview links), update the secret and deploy again.

## Tests

```bash
python -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
(cd frontend && npm ci)
scripts/check.sh
```

This runs the linters, 58 tests and the frontend build. The GitHub Actions workflow (`.github/workflows/ci.yml`)
is configured to run the same checks on every push. The tests need no API key and no internet. They cover the
score, the quote check, the anonymization, the cheating detection, the decisions, the e-mails and a complete
journey from the offer to the final e-mail.

`evals/` holds a second kind of test that uses the real AI: the 6 CVs of the test and 8 trap CVs I made
(scan, hidden message, a cooking recipe, an empty file...), each with the result I expect.

```bash
.venv/bin/python -m evals.run_eval              # the 6 CVs of the test
.venv/bin/python -m evals.run_eval --surprise   # the 8 trap CVs
```

## How I used an AI assistant

I built this with Claude Code. I gave it precise instructions and checked its work with the tests. I also ran a
critical review of the code, which found bugs that I then fixed.

## What is missing

This is a pilot, not a finished product. Before giving it to the six recruiters I would do this first:

- **Login.** There is one shared password. Each recruiter needs their own account (Entra ID), so we know who decided what.
- **Volume.** SQLite and one server are fine for a pilot, not for 1,500 CVs at once. Next step: PostgreSQL and a job queue.
- **Calibration.** The 70 % threshold is my judgement. It should be tuned on a few hundred CVs sorted by the recruiters.
- **Voice.** Not yet tested with real accents and background noise.
- **Anonymization.** French job titles still show gender ("Cheffe", "Adjointe").
- **Personal data.** No retention period or deletion on request yet, and the hosting is in the US.
- **Reminders.** A candidate who does not take the interview gets no reminder.
- **Automatic deploy.** The checks are automated (`scripts/check.sh` and the GitHub Actions workflow), but I still
  deploy by hand. The deploy should start by itself once the checks pass.
