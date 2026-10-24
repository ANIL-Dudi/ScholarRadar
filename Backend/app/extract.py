import json
import logging
import re
from datetime import date

from tinyfish import RunStatus, TinyFish

from .config import TINYFISH_API_KEY

logger = logging.getLogger(__name__)

GOAL = """Read this page about a research internship, scholarship or programme.
Extract the main opportunity described and return ONLY a JSON object with exactly these keys:
- "title": string
- "deadline": the application deadline as YYYY-MM-DD, or null if the page does not state one
- "eligibility": short string describing who can apply
- "documents": list of strings naming required application documents, or an empty list if not stated
- "funding": string describing stipend or funding, or null if not stated
- "summary": one sentence describing the opportunity
Never invent a deadline or funding amount. If the page is not about a specific opportunity,
return {"title": null}."""


def _as_dict(value) -> dict:
    if isinstance(value, str):
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", value.strip())
        value = json.loads(cleaned)
    if isinstance(value, dict) and "title" not in value:
        for inner in value.values():
            if isinstance(inner, dict) and "title" in inner:
                return inner
    if not isinstance(value, dict):
        raise ValueError("TinyFish did not return a JSON object.")
    return value


def extract(url: str, text: str = "") -> dict:
    if not TINYFISH_API_KEY:
        raise RuntimeError("TINYFISH_API_KEY is missing. Check Backend/.env")

    client = TinyFish()
    run = client.agent.run(url=url, goal=GOAL)

    if run.status != RunStatus.COMPLETED:
        raise ValueError(f"TinyFish run did not complete ({run.status}).")

    data = _as_dict(run.result)

    if not data.get("title"):
        raise ValueError("No specific opportunity found on this page.")

    deadline = data.get("deadline")
    if deadline is not None:
        try:
            deadline = date.fromisoformat(str(deadline)).isoformat()
        except ValueError:
            deadline = None

    documents = data.get("documents")
    if not isinstance(documents, list):
        documents = []

    return {
        "url": url,
        "title": str(data.get("title")),
        "deadline": deadline,
        "eligibility": str(data.get("eligibility") or "Not stated"),
        "documents": [str(d) for d in documents],
        "funding": data.get("funding"),
        "summary": str(data.get("summary") or ""),
    }