
import json
import logging

import httpx

from .config import TINYFISH_API_KEY

logger = logging.getLogger(__name__)

SEARCH_URL = "https://api.search.tinyfish.ai"
FETCH_URL = "https://api.fetch.tinyfish.ai"
AGENT_URL = "https://agent.tinyfish.ai/v1/automation/run-sse"


def _headers() -> dict:
    if not TINYFISH_API_KEY:
        raise RuntimeError(
            "TINYFISH_API_KEY is missing. Check Backend/.env"
        )
    return {"X-API-Key": TINYFISH_API_KEY}


async def search(
    query: str,
    location: str = "IN",
    language: str = "en",
) -> list[dict]:
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(
            SEARCH_URL,
            headers=_headers(),
            params={
                "query": query,
                "location": location,
                "language": language,
            },
        )
        response.raise_for_status()
        data = response.json()

    results = data.get("results", [])
    if not isinstance(results, list):
        raise RuntimeError(
            "Unexpected TinyFish Search response: 'results' is not a list"
        )

    return results


async def fetch(urls: list[str]) -> dict:
    if not urls:
        return {"results": []}

    async with httpx.AsyncClient(timeout=90) as client:
        response = await client.post(
            FETCH_URL,
            headers=_headers(),
            json={"urls": urls},
        )
        response.raise_for_status()
        data = response.json()

    if not isinstance(data, dict):
        raise RuntimeError("Unexpected TinyFish Fetch response")

    return data


async def agent_stream(url: str, goal: str):
    async with httpx.AsyncClient(timeout=None) as client:
        async with client.stream(
            "POST",
            AGENT_URL,
            headers=_headers(),
            json={"url": url, "goal": goal},
        ) as response:
            response.raise_for_status()

            async for line in response.aiter_lines():
                if not line.startswith("data:"):
                    continue

                payload = line[5:].strip()

                if not payload or payload == "[DONE]":
                    continue

                try:
                    yield json.loads(payload)
                except json.JSONDecodeError:
                    logger.warning(
                        "Skipping invalid TinyFish SSE event"
                    )
