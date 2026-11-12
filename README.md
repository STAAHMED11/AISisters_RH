# RH du futur (Groupe Orvane)

My answer to the "La RH du futur" test.

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

## Tech

| Part | Tool |
|---|---|
| API | Python, Flask, SQLAlchemy, Pydantic |
| Interface | Next.js, React, TypeScript, Tailwind |
| Database | SQLite (one file) |
| AI | Claude Sonnet for judging, Claude Haiku for simple tasks (cheaper) |
| Voice interview | ElevenLabs |
| E-mail | SMTP (Gmail) |
| Hosting | One Docker image on Modal |

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

## Tests

```bash
pip install -r requirements-dev.txt
scripts/check.sh
```

This runs the linters, 57 tests and the frontend build. GitHub Actions runs the same script on every push. The tests need no API key and no internet. They cover the
score, the quote check, the anonymization, the cheating detection, the decisions, the e-mails and a complete
journey from the offer to the final e-mail.

`evals/` holds a second kind of test that uses the real AI: the 6 CVs of the test and 8 trap CVs I made
(scan, hidden message, a cooking recipe, an empty file...), each with the result I expect.

## What is missing

This is a pilot, not a finished product. Before giving it to the six recruiters I would do this first:

- **Login.** There is one shared password. Each recruiter needs their own account (Entra ID), so we know who decided what.
- **Volume.** SQLite and one server are fine for a pilot, not for 1,500 CVs at once. Next step: PostgreSQL and a job queue.
- **Calibration.** The 70 % threshold is my judgement. It should be tuned on a few hundred CVs sorted by the recruiters.
- **Voice.** Not yet tested with real accents and background noise.
- **Anonymization.** French job titles still show gender ("Cheffe", "Adjointe").
- **Personal data.** No retention period or deletion on request yet, and the hosting is in the US.
- **Reminders.** A candidate who does not take the interview gets no reminder.
- **Automatic deploy.** GitHub Actions runs the checks on every push (`.github/workflows/ci.yml`), but I still
  deploy by hand. The deploy should start by itself once the checks pass.
