# ScholarRadar

**An AI agent that finds, verifies and ranks student opportunities, and alerts you before every deadline.**

Built for HackIIITD (Final Round) by Anil Dudi and Venkateshwar Singh, University of Delhi.

> Never miss the opportunity that fits you.

---

## The problem

Programmes, internships, scholarships and competitive exams are scattered across many sites and PDFs, each in its own format. Eligibility and deadlines are buried in long pages, and public listings often disagree. For GATE 2027, for example, listings showed four different closing dates. Students at smaller colleges have little guidance and no personal reminders.

## What ScholarRadar does

1. **Profile:** upload a CV and pick your interests. We extract your education level, field, skills, CGPA and experience. You review and correct it.
2. **Discover:** TinyFish Search finds candidate pages, Fetch renders them, and Agent handles pages with filters and tables.
3. **Verify:** an LLM extracts a fixed JSON schema (deadline, eligibility, documents, funding). A rule-based date reader cross-checks it, and conflicts go to you.
4. **Match and alert:** each opportunity gets a fit score with reasons, a priority weighted by urgency, and Telegram reminders with a link to the source.

**Human in the loop:** ScholarRadar never submits an application for you, and every result links back to its source page.

## How ranking works

- **Fit (0-100)** = 40% interest match + 30% eligibility stage + 30% field and CV evidence.
- **Hard rules** cap the score: class-12-only exams, minimum experience, category-only schemes.
- **Urgency (0-1)** rises as the deadline nears (1.0 within 3 days, 0.2 beyond 120 days or with no date).
- **Priority = Fit x (0.35 + 0.65 x Urgency).** The 0.35 floor keeps strong matches with distant deadlines visible. The weights are tunable, not learned.
- Candidates are shortlisted with embeddings and RRF fusion, then rules score and explain each match.

## Confidence levels

Every date shows how much to trust it:

| Level | Meaning |
|---|---|
| Official | Read from the organiser's own page |
| Reported | News sites agree, not yet on the official page |
| Expected | Exam announced, registration window not published |
| Unverified | Single third-party listing |

## Telegram alerts

- Reminders before each deadline, sent once per threshold and retried if Telegram is down.
- The countdown restarts if the organiser changes the date.
- Link previews and a reminder confirmation in chat.
- Bot commands: `/start`, `/top`, `/soon`, `/scan`, `/help`.

## Tech stack

| Layer | Tools |
|---|---|
| Frontend | React |
| Backend | Python, FastAPI |
| Web data | TinyFish Search, Fetch and Agent APIs |
| Extraction | LLM to fixed JSON schema |
| Matching | sentence-transformers embeddings, RRF fusion, rule scoring |
| Storage | SQLite (Postgres + pgvector to scale) |
| Scheduler | Periodic discovery and page checks |
| Alerts | Telegram Bot API |

## Project structure

```
ScholarRadar/
  backend/      FastAPI app: API, crawling, extraction, matcher, scheduler, alerts
  frontend/     React dashboard: CV upload, interests, ranked feed, deadline calendar
  README.md
```

## Getting started

### Prerequisites

- Python 3.10+
- Node.js 18+
- A TinyFish API key
- A Telegram bot token from [@BotFather](https://t.me/BotFather)
- An LLM API key for extraction

### 1. Clone

```bash
git clone <your-repo-url>
cd ScholarRadar
```

### 2. Configure

Create `backend/.env`:

```env
TINYFISH_API_KEY=your_key
LLM_API_KEY=your_key
TELEGRAM_BOT_TOKEN=your_bot_token
DATABASE_URL=sqlite:///./scholarradar.db
```

Never commit `.env`. Make sure it is in `.gitignore`.

### 3. Run the backend

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate    macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### 4. Run the frontend

```bash
cd frontend
npm install
npm run dev
```

Open the URL printed by the dev server (usually http://localhost:5173).

### 5. Connect Telegram

Open your bot in Telegram and send `/start`. The bot links to your chat and confirms.

## Usage

1. Upload your CV (PDF or DOCX) and review the detected profile.
2. Select your interests.
3. Browse the ranked feed. Each card shows fit, reasons, deadline and confidence.
4. Receive Telegram reminders before deadlines.

## Roadmap

- **Now:** 5 portals, the OIST research internship workflow end to end, CV to Telegram alert.
- **Next:** 50 portals, per-site extraction templates, document checklist, email alerts.
- **Then:** per-college deployment with placement cells as admins and one shared feed.

## Limitations

- Dates from aggregator sites can be wrong. Always confirm on the official page before applying.
- CV parsing is heuristic, so please review your detected profile.
- Deadlines marked Expected are not confirmed by the organiser.

## Team

Anil Dudi and Venkateshwar Singh, University of Delhi.

## License

Add your license here (for example MIT).
