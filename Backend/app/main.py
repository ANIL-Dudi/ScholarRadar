import asyncio
import json
from contextlib import asynccontextmanager
from fastapi import FastAPI, File, Form, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from . import db, tinyfish, extract, matcher, scheduler
from .cv import cv_to_text


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init()
    sched = scheduler.start()
    yield
    sched.shutdown()


app = FastAPI(title="ScholarRadar", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"],
                   allow_methods=["*"], allow_headers=["*"])
STATE: dict = {"profile": ""}


@app.get("/api/health")
def health():
    return {"ok": True}


@app.post("/api/profile")
async def profile(cv: UploadFile = File(...), interests: str = Form("")):
    text = cv_to_text(await cv.read(), cv.filename)
    STATE["profile"] = f"{interests}\n{text}"
    return {"chars": len(text), "interests": interests}


@app.post("/api/discover")
async def discover(query: str = Form(...)):
    results = (await tinyfish.search(query))[:5]
    urls = [r["url"] for r in results]
    if not urls:
        return {"added": 0}
    fetched = await tinyfish.fetch(urls)
    added = 0
    for page in fetched.get("results", []):
        url, text = page.get("url"), page.get("text") or page.get("content") or ""
        if not (url and text):
            continue
        try:
            opp = await asyncio.to_thread(extract.extract, url, text)
            db.upsert_opportunity(opp, text)
            added += 1
        except Exception as e:
            print("extract failed", url, e)
    return {"added": added}


@app.get("/api/feed")
def feed():
    return matcher.rank(STATE["profile"], db.all_opportunities())


@app.get("/api/agent")
async def agent(url: str, goal: str):
    async def gen():
        async for ev in tinyfish.agent_stream(url, goal):
            yield f"data: {json.dumps(ev)}\n\n"
    return StreamingResponse(gen(), media_type="text/event-stream")

# ---- Frontend adapter: shape results the way script.js expects ----
import re
from urllib.parse import urlparse

INTEREST_WORDS = {
    "ml": ["machine learning", "artificial intelligence", "deep learning", "data science", "computer vision", "neural"],
    "bio": ["biology", "biotech", "biomedical", "life science", "medical", "genom"],
    "physics": ["physics", "quantum", "astronomy", "astrophysics"],
    "econ": ["economics", "finance", "econometrics"],
    "oss": ["open source", "open-source", "software development", "github"],
    "eng": ["engineering", "electronics", "robotics", "mechanical", "electrical", "computer science"],
}
DEFAULT_QUERY = "research internship 2027 undergraduate students India"


def _tags(o: dict) -> list[str]:
    text = f" {o.get('title','')} {o.get('summary','')} {o.get('eligibility','')} ".lower()
    return [k for k, words in INTEREST_WORDS.items() if any(w in text for w in words)]


@app.get("/api/opportunities")
async def opportunities(interests: str = "", refresh: bool = False):
    chosen = [k for k in interests.split(",") if k in INTEREST_WORDS]
    if refresh or not db.all_opportunities():
        await discover(query=DEFAULT_QUERY)
    profile = STATE["profile"] + " " + " ".join(INTEREST_WORDS[k][0] for k in chosen)
    rows = [o for o in db.all_opportunities()
            if re.fullmatch(r"\d{4}-\d{2}-\d{2}", o.get("deadline") or "")]
    ranked = matcher.rank(profile, rows, top_k=12)
    if not ranked:
        return []
    lo = min(o["score"] for o in ranked)
    hi = max(o["score"] for o in ranked)
    out = []
    for i, o in enumerate(ranked, start=1):
        base = 60 + round(30 * (o["score"] - lo) / (hi - lo)) if hi > lo else 80
        try:
            docs = json.loads(o.get("documents") or "[]")
        except ValueError:
            docs = []
        out.append({
            "id": i,
            "title": o.get("title") or "Untitled opportunity",
            "org": urlparse(o["url"]).netloc.replace("www.", ""),
            "funding": o.get("funding") or "See source page",
            "due": o["deadline"],
            "base": base,
            "tags": _tags(o),
            "why": o.get("summary") or o["why"],
            "docs": docs or ["See source page"],
            "url": o["url"],
        })
    return out