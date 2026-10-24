import json
import anthropic
from .config import LLM_MODEL

client = anthropic.Anthropic()

PROMPT = """Extract opportunity details from the page text. Reply with ONLY JSON:
{"title": str, "deadline": "YYYY-MM-DD or null", "eligibility": str, "documents": [str],
 "funding": str or null, "summary": "one sentence"}
Use null when not stated. Never invent a deadline."""


def extract(url: str, text: str) -> dict:
    msg = client.messages.create(
        model=LLM_MODEL, max_tokens=1000, system=PROMPT,
        messages=[{"role": "user", "content": text[:15000]}],
    )
    raw = msg.content[0].text.strip().removeprefix("```json").removesuffix("```").strip()
    data = json.loads(raw)
    data["url"] = url
    return data