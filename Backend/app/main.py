
import asyncio
import json
import logging
import re
from contextlib import asynccontextmanager
from urllib.parse import urlparse

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from . import db, extract, matcher, scheduler, tinyfish
from .cv import cv_to_text

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


async def run_discovery(query: str) -> dict:
    search_results = (await tinyfish.search(query))[:5]

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

    if refresh or not rows:
        try:
            result = await run_discovery(DEFAULT_QUERY)
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

    # Keep opportunities even if their deadline is not stated.
    ranked = await asyncio.to_thread(matcher.rank, profile_text, rows, 12)

    if not ranked:
        return []

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

    return output
