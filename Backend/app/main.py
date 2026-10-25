import asyncio
import json
import logging
import re
import time
from datetime import date
from contextlib import asynccontextmanager
from urllib.parse import urlparse

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from . import db, extract, matcher, scheduler, tinyfish
from .cv import cv_to_text
from .explain import assess_many

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DEFAULT_QUERY = (
    "fully funded research internship 2027 undergraduate students India"
)

INTEREST_WORDS = {
    "ml": [
        "machine learning", "artificial intelligence",
        "deep learning", "data science", "computer vision", "neural",
    ],
    "bio": [
        "biology", "biotech", "biomedical",
        "life science", "medical", "genom",
    ],
    "physics": ["physics", "quantum", "astronomy", "astrophysics"],
    "econ": ["economics", "finance", "econometrics"],
    "oss": [
        "open source", "open-source",
        "software development", "github",
    ],
    "eng": [
        "engineering", "electronics", "robotics",
        "mechanical", "electrical", "computer science",
    ],
}

STATE = {"profile": ""}


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init()

    saved_profile = db.get_profile()
    STATE["profile"] = (
        f"{saved_profile.get('interests') or ''}\n"
        f"{saved_profile.get('cv_text') or ''}"
    ).strip()

    sched = scheduler.start()
    schedule_auto_discovery(sched, asyncio.get_running_loop())

    try:
        yield
    finally:
        sched.shutdown(wait=False)


app = FastAPI(title="ScholarRadar", lifespan=lifespan)

# Include the Live Server origins used by the frontend.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5500",
        "http://127.0.0.1:5500",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    return {"ok": True}


@app.post("/api/profile")
async def upload_profile(
    cv: UploadFile = File(...),
    interests: str = Form(""),
):
    try:
        data = await cv.read()
        if len(data) > 5 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="CV must be 5 MB or smaller.")
        text = cv_to_text(data, cv.filename or "")

        STATE["profile"] = f"{interests}\n{text}".strip()
        db.save_profile(cv_text=text, interests=interests)

        return {
            "chars": len(text),
            "interests": interests,
            "message": "CV uploaded and profile saved",
        }

    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        await cv.close()


def build_queries(chosen: list[str]) -> list[str]:
    """One broad query plus topic-specific queries for each chosen interest."""
    queries = [DEFAULT_QUERY]
    for key in chosen:
        topic = INTEREST_WORDS[key][0]
        queries.append(f"{topic} research internship 2027 undergraduate students India")
        queries.append(f"{topic} scholarship fellowship 2027 students India")
    queries.append("summer research internship 2027 applications open IIT IISc IISER undergraduate")
    queries.append("fellowship for Indian undergraduate students 2027 apply deadline")
    return queries[:7]


async def run_discovery(query, per_query: int = 5) -> dict:
    queries = [query] if isinstance(query, str) else list(query)
    batches = await asyncio.gather(
        *(tinyfish.search(q) for q in queries), return_exceptions=True
    )

    search_results = []
    errors = []
    for q, batch in zip(queries, batches):
        if isinstance(batch, Exception):
            logger.warning("TinyFish search failed for %r: %s", q, batch)
            errors.append(batch)
            continue
        search_results.extend(batch[:per_query])

    if errors and not search_results:
        raise errors[0]

    urls = list(dict.fromkeys(
        result["url"]
        for result in search_results
        if result.get("url")
    ))

    if not urls:
        return {"found": 0, "added": 0}

    fetched = await tinyfish.fetch(urls)
    pages = fetched.get("results", [])

    if not isinstance(pages, list):
        raise RuntimeError(
            "Unexpected TinyFish Fetch response: results is not a list"
        )

    skip_hosts = (
        "instagram.com", "facebook.com", "youtube.com",
        "tiktok.com", "x.com", "twitter.com", "linkedin.com",
    )

    candidates = []
    for page in pages:
        url = page.get("url")
        page_text = page.get("text") or page.get("content") or ""

        if not url or not page_text.strip():
            continue

        host = urlparse(url).netloc.lower().removeprefix("www.")
        if any(host == h or host.endswith("." + h) for h in skip_hosts):
            continue

        # Skip job boards and company career portals (full-time jobs, not student programmes).
        if host.startswith(("careers.", "jobs.")) or any(
            word in host for word in ("glassdoor.", "indeed.", "greenhouse.io", "lever.co", "workday")
        ):
            continue

        candidates.append((url, page_text))

    processed = len(candidates)
    gate = asyncio.Semaphore(3)

    async def work(url, page_text):
        async with gate:
            try:
                opportunity = await asyncio.to_thread(
                    extract.extract, url, page_text
                )
                db.upsert_opportunity(opportunity, page_text)
                return 1
            except Exception:
                logger.exception("Opportunity extraction failed for %s", url)
                return 0

    results = await asyncio.gather(*(work(u, t) for u, t in candidates))
    added = sum(results)

    return {
        "found": len(urls),
        "fetched": len(pages),
        "processed": processed,
        "added": added,
    }


@app.post("/api/discover")
async def discover(query: str = Form(...)):
    try:
        return await run_discovery(query)
    except Exception as exc:
        logger.exception("Discovery failed")
        raise HTTPException(
            status_code=502,
            detail=f"Opportunity discovery failed: {exc}",
        ) from exc


@app.get("/api/feed")
def feed():
    return matcher.rank(
        STATE["profile"],
        db.all_opportunities(),
    )


@app.get("/api/agent")
async def agent(url: str, goal: str):
    async def generate():
        async for event in tinyfish.agent_stream(url, goal):
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
    )


def _tags(opportunity: dict) -> list[str]:
    text = " ".join(
        str(opportunity.get(key) or "")
        for key in ("title", "summary", "eligibility")
    ).lower()

    return [
        key
        for key, words in INTEREST_WORDS.items()
        if any(word in text for word in words)
    ]


@app.get("/api/opportunities")
async def opportunities(
    interests: str = "",
    refresh: bool = False,
):
    rows = db.all_opportunities()

    chosen = [
        key for key in interests.split(",")
        if key in INTEREST_WORDS
    ]

    recently_searched = (time.time() - STATE.get("last_discovery", 0)) < 600

    if (refresh and not recently_searched) or not rows:
        try:
            STATE["last_discovery"] = time.time()
            result = await run_discovery(build_queries(chosen))
            logger.info("Discovery result: %s", result)
        except Exception:
            logger.exception("Automatic discovery failed")

            # Keep serving previously collected data if available.
            if not rows:
                raise HTTPException(
                    status_code=502,
                    detail=(
                        "Live discovery failed and no cached opportunities "
                        "are available. Check the backend terminal."
                    ),
                )

        rows = db.all_opportunities()

    chosen = [
        key for key in interests.split(",")
        if key in INTEREST_WORDS
    ]

    saved_profile = db.get_profile()
    profile_text = (
        STATE["profile"]
        + " "
        + " ".join(INTEREST_WORDS[key][0] for key in chosen)
        + " "
        + (saved_profile.get("interests") or "")
    ).strip()

    if not profile_text:
        # Permit discovery without a CV, using selected interests.
        profile_text = " ".join(
            INTEREST_WORDS[key][0] for key in chosen
        )

    # Show only opportunities that have a stated deadline.
    rows = [r for r in rows if r.get("deadline")]

    if not rows:
        return []

    ranked = await asyncio.to_thread(matcher.rank, profile_text, rows, 30)

    if not ranked:
        return []

    # Drop expired / old-edition items first so LLM calls are only spent on live ones.
    today = date.today().isoformat()
    ranked = [
        o for o in ranked
        if not (o.get("deadline") and o["deadline"] < today)
        and not (
            not o.get("deadline")
            and any(y in (o.get("title") or "") for y in ("2024", "2025", "2026"))
        )
    ][:12]

    if not ranked:
        return []

    # LLM eligibility check against the CV; items clearly not open to this student are dropped.
    verdicts = await assess_many(profile_text, ranked)
    kept = [
        (o, v) for o, v in zip(ranked, verdicts)
        if not (v and v.get("fit") == "not_eligible")
    ]
    if kept:  # if everything was rejected, show all rather than an empty feed
        ranked = [o for o, _ in kept]
        verdicts = [v for _, v in kept]

    scores = [item["score"] for item in ranked]
    low_score = min(scores)
    high_score = max(scores)

    output = []

    for index, opportunity in enumerate(ranked, start=1):
        score = opportunity["score"]

        base_score = (
            60 + round(
                30 * (score - low_score) / (high_score - low_score)
            )
            if high_score > low_score
            else 80
        )

        try:
            documents = json.loads(
                opportunity.get("documents") or "[]"
            )
        except (ValueError, TypeError):
            documents = []

        url = opportunity.get("url") or ""
        organization = urlparse(url).netloc.replace("www.", "")

        due = opportunity.get("deadline")
        title_text = opportunity.get("title") or ""
        if due and due < date.today().isoformat():
            continue  # deadline already passed
        if not due and any(year in title_text for year in ("2024", "2025", "2026")):
            continue  # old edition with no future deadline

        output.append({
            "id": index,
            "title": opportunity.get("title") or "Untitled opportunity",
            "org": organization or "Organization not identified",
            "funding": opportunity.get("funding") or "See source page",
            "due": opportunity.get("deadline") or None,
            "base": base_score,
            "tags": _tags(opportunity),
            "why": (
                opportunity.get("summary")
                or opportunity.get("why")
                or "Ranked using semantic and keyword matching."
            ),
            "docs": documents or ["See source page"],
            "url": url,
        })

    return output[:12]

@app.post("/api/alerts/digest")
def alerts_digest(days: int = 30):
    """Email/Telegram a digest of deadlines in the next `days` days."""
    return scheduler.send_digest(days)


from fastapi import BackgroundTasks
from pydantic import BaseModel


class ReminderIn(BaseModel):
    url: str
    title: str = ""
    deadline: str


@app.get("/api/reminders")
def list_reminders():
    return db.all_reminders()


@app.post("/api/reminders")
def create_reminder(reminder: ReminderIn, background: BackgroundTasks):
    from datetime import date

    try:
        due = date.fromisoformat(reminder.deadline)
    except ValueError:
        raise HTTPException(status_code=400, detail="Deadline must be YYYY-MM-DD.")

    if not reminder.url.lower().startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="A valid opportunity URL is required.")

    db.add_reminder(reminder.url, reminder.title[:300], due.isoformat())

    background.add_task(
        scheduler.notify,
        "Reminder set: " + (reminder.title or "Opportunity"),
        "ScholarRadar will email you 14, 7, 3 and 1 days before the deadline ("
        + due.isoformat() + ").\n" + reminder.url,
    )
    return {"ok": True, "deadline": due.isoformat()}


@app.delete("/api/reminders")
def delete_reminder(url: str):
    db.remove_reminder(url)
    return {"ok": True}


from fastapi import BackgroundTasks

DISCOVERY = {"running": False, "added": 0, "queries_done": 0, "total": 0, "error": None}

LIVE_QUERIES = [
    "research internship 2027 application deadline undergraduate India",
    "summer research fellowship 2027 last date to apply Indian students",
]


async def _discover_all(queries):
    try:
        for query in queries:
            try:
                result = await run_discovery(query)
                DISCOVERY["added"] += result.get("added", 0)
            except Exception as exc:
                logger.exception("Live discovery failed for %s", query)
                DISCOVERY["error"] = str(exc)[:200]
            DISCOVERY["queries_done"] += 1
    finally:
        DISCOVERY["running"] = False


@app.post("/api/discover/live")
async def discover_live(background: BackgroundTasks, interests: str = ""):
    if DISCOVERY["running"]:
        return {"started": False, "reason": "A search is already running."}

    queries = list(LIVE_QUERIES)
    chosen = [k for k in interests.split(",") if k in INTEREST_WORDS]
    if chosen:
        queries.append(
            INTEREST_WORDS[chosen[0]][0] + " internship 2027 application deadline India"
        )

    DISCOVERY.update(
        running=True, added=0, queries_done=0, total=len(queries), error=None
    )
    background.add_task(_discover_all, queries)
    return {"started": True, "queries": len(queries)}


@app.get("/api/discover/status")
def discover_status():
    return DISCOVERY


# ============================================================
# Automatic discovery: searches the web on its own, on a schedule
# ============================================================

AUTO_QUERIES = [
    # internships
    "research internship 2027 applications open undergraduate India",
    "summer internship 2027 engineering students India apply last date",
    "machine learning internship 2027 India students apply deadline",
    # scholarships and fellowships
    "scholarship 2027 undergraduate engineering students India last date",
    "fellowship 2027 undergraduate students apply deadline",
    "fully funded scholarship 2027 Indian students apply",
    # jobs
    "entry level graduate engineer jobs India 2027 apply last date",
    "fresher software engineer job openings India 2027 apply",
]


async def auto_discover():
    """Search the next 3 queries from AUTO_QUERIES (rotating) and save what TinyFish finds."""
    if DISCOVERY["running"]:
        return

    start = STATE.get("auto_i", 0)
    batch = [AUTO_QUERIES[(start + k) % len(AUTO_QUERIES)] for k in range(3)]
    STATE["auto_i"] = (start + 3) % len(AUTO_QUERIES)

    DISCOVERY.update(running=True, added=0, queries_done=0, total=len(batch), error=None)
    logger.info("Auto discovery started: %s", batch)

    await _discover_all(batch)
    logger.info("Auto discovery finished: %s opportunities saved", DISCOVERY["added"])


def schedule_auto_discovery(sched, loop, hours: int = 6, first_run_seconds: int = 60):
    """Run auto_discover shortly after startup, then every `hours` hours."""
    import os
    from datetime import datetime, timedelta

    if os.getenv("AUTO_DISCOVERY", "on").strip().lower() == "off":
        logger.info("Auto discovery is off (AUTO_DISCOVERY=off).")
        return

    sched.add_job(
        lambda: asyncio.run_coroutine_threadsafe(auto_discover(), loop),
        trigger="interval",
        hours=hours,
        next_run_time=datetime.now(scheduler.IST) + timedelta(seconds=first_run_seconds),
        id="auto_discover",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    logger.info("Auto discovery scheduled: first run in %ss, then every %sh.", first_run_seconds, hours)