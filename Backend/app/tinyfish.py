import json
import httpx
from .config import TINYFISH_API_KEY

H = {"X-API-Key": TINYFISH_API_KEY}


async def search(query: str, location="IN", language="en") -> list[dict]:
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get("https://api.search.tinyfish.ai", headers=H,
                        params={"query": query, "location": location, "language": language})
        r.raise_for_status()
        return r.json().get("results", [])


async def fetch(urls: list[str]) -> dict:
    async with httpx.AsyncClient(timeout=90) as c:
        r = await c.post("https://api.fetch.tinyfish.ai", headers=H, json={"urls": urls})
        r.raise_for_status()
        return r.json()


async def agent_stream(url: str, goal: str):
    async with httpx.AsyncClient(timeout=None) as c:
        async with c.stream("POST", "https://agent.tinyfish.ai/v1/automation/run-sse",
                            headers=H, json={"url": url, "goal": goal}) as r:
            async for line in r.aiter_lines():
                if line.startswith("data:"):
                    try:
                        yield json.loads(line[5:].strip())
                    except json.JSONDecodeError:
                        continue