"""LLM eligibility check: does this opportunity fit this student?"""
import asyncio
import json
import logging
import re

from .config import ANTHROPIC_API_KEY, LLM_MODEL

logger = logging.getLogger(__name__)

_cache: dict = {}
_warned = False

SYSTEM = (
    "You judge whether a student can realistically apply to an opportunity. "
    "Use ONLY the student profile and opportunity text provided. Never invent "
    "requirements, deadlines or facts. Reply with JSON only."
)

PROMPT = """STUDENT PROFILE (from CV and selected interests):
{profile}

OPPORTUNITY:
Title: {title}
Eligibility text: {eligibility}
Summary: {summary}
Funding: {funding}
Deadline: {deadline}

Return ONLY this JSON object:
{{"fit": "eligible" | "maybe" | "not_eligible", "why": "<at most 2 sentences>"}}

Rules:
- "not_eligible" ONLY if the text clearly excludes this student, e.g. PhD or postdoc only,
  a full-time job, graduates only, a citizenship or country restriction that excludes an
  Indian student, or a completely unrelated field.
- "maybe" if eligibility is not stated or is unclear.
- "eligible" if the stated criteria match the student's level, country and field.
- In "why", name concrete things from the CV (projects, skills, year of study) and any gap.
  No flattery, no guessing."""


def _client():
    from anthropic import Anthropic
    return Anthropic(api_key=ANTHROPIC_API_KEY, timeout=40)


def assess(profile_text: str, opp: dict):
    """Return {"fit", "why"} or None when the LLM is unavailable or fails."""
    global _warned
    if not ANTHROPIC_API_KEY:
        if not _warned:
            logger.warning("ANTHROPIC_API_KEY missing: skipping eligibility check.")
            _warned = True
        return None
    if not profile_text.strip():
        return None

    key = (opp.get("url"), hash(profile_text))
    if key in _cache:
        return _cache[key]

    prompt = PROMPT.format(
        profile=profile_text[:4000],
        title=opp.get("title"),
        eligibility=opp.get("eligibility") or "Not stated",
        summary=opp.get("summary") or "",
        funding=opp.get("funding") or "Not stated",
        deadline=opp.get("deadline") or "Not stated",
    )

    try:
        msg = _client().messages.create(
            model=LLM_MODEL,
            max_tokens=300,
            system=SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
        match = re.search(r"\{.*\}", text, re.S)
        data = json.loads(match.group(0))
        fit = data.get("fit")
        if fit not in ("eligible", "maybe", "not_eligible"):
            return None
        result = {"fit": fit, "why": str(data.get("why") or "").strip()}
        _cache[key] = result
        return result
    except Exception:
        logger.exception("Eligibility check failed for %s", opp.get("url"))
        return None


async def assess_many(profile_text: str, opps: list[dict], workers: int = 4) -> list:
    gate = asyncio.Semaphore(workers)

    async def one(opp):
        async with gate:
            return await asyncio.to_thread(assess, profile_text, opp)

    return await asyncio.gather(*(one(o) for o in opps))
