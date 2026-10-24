
import json
import logging
import re

import anthropic

from .config import ANTHROPIC_API_KEY, LLM_MODEL

logger = logging.getLogger(__name__)

PROMPT = """
Extract opportunity details from the supplied webpage text.
Return ONLY a valid JSON object with these fields:
{
  "title": "string",
  "deadline": "YYYY-MM-DD or null",
  "eligibility": "string",
  "documents": ["string"],
  "funding": "string or null",
  "summary": "one-sentence summary"
}

Rules:
- Never invent a deadline, eligibility condition, or funding amount.
- Use null for an unstated deadline or funding.
- Use an empty list if documents are not specified.
- Do not treat the current date as the deadline.
"""


def extract(url: str, text: str) -> dict:
    if not ANTHROPIC_API_KEY:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is missing. Check Backend/.env"
        )

    if not text or not text.strip():
        raise ValueError("Cannot extract an opportunity from empty text.")

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    response = client.messages.create(
        model=LLM_MODEL,
        max_tokens=1200,
        system=PROMPT,
        messages=[
            {
                "role": "user",
                "content": f"Source URL: {url}\n\nPage text:\n{text[:15000]}",
            }
        ],
    )

    raw = "".join(
        block.text
        for block in response.content
        if getattr(block, "type", None) == "text"
    ).strip()

    # Accommodate models that wrap JSON in a Markdown code fence.
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.error("LLM returned invalid JSON for %s", url)
        raise ValueError("Opportunity extraction returned invalid JSON.") from exc

    if not isinstance(data, dict):
        raise ValueError("Opportunity extraction did not return an object.")

    deadline = data.get("deadline")
    if deadline is not None:
        try:
            from datetime import date
            date.fromisoformat(deadline)
        except (ValueError, TypeError):
            deadline = None

    documents = data.get("documents")
    if not isinstance(documents, list):
        documents = []

    return {
        "url": url,
        "title": str(data.get("title") or "Untitled opportunity"),
        "deadline": deadline,
        "eligibility": str(data.get("eligibility") or "Not stated"),
        "documents": documents,
        "funding": data.get("funding"),
        "summary": str(data.get("summary") or ""),
    }
