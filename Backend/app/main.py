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