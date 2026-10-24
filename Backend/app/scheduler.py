
import logging
from datetime import date, datetime
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler

from . import db
from .notifications import notify

logger = logging.getLogger(__name__)

IST = ZoneInfo("Asia/Kolkata")
REMIND_DAYS = {14, 7, 3, 1}


def deadline_check():
    today = datetime.now(IST).date()

    for opportunity in db.all_reminders():
        deadline = opportunity.get("deadline")

        if not deadline:
            continue

        try:
            deadline_date = date.fromisoformat(deadline)
        except (ValueError, TypeError):
            logger.warning(
                "Invalid deadline for %s: %s",
                opportunity.get("title"),
                deadline,
            )
            continue

        days_left = (deadline_date - today).days

        if days_left not in REMIND_DAYS:
            continue

        title = opportunity.get("title") or "Opportunity"
        url = opportunity.get("url") or ""

        try:
            result = notify(
                f"{days_left} day(s) left: {title}",
                f"Deadline: {deadline}\n{url}",
            )
            logger.info("Reminder result for %s: %s", title, result)
        except Exception:
            logger.exception("Reminder failed for %s", title)


def start():
    scheduler = BackgroundScheduler(timezone=IST)

    scheduler.add_job(
        deadline_check,
        trigger="cron",
        hour=9,
        minute=0,
        id="deadline_check",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )

    scheduler.start()
    return scheduler

def upcoming(days: int = 30):
    """Saved opportunities whose deadline falls within the next `days` days."""
    today = datetime.now(IST).date()
    items = []

    for opportunity in db.all_reminders():
        deadline = opportunity.get("deadline")
        if not deadline:
            continue
        try:
            left = (date.fromisoformat(deadline) - today).days
        except (ValueError, TypeError):
            continue
        if 0 <= left <= days:
            items.append((left, opportunity))

    return sorted(items, key=lambda item: item[0])


def send_digest(days: int = 30) -> dict:
    """Email/Telegram one message listing every deadline in the next `days` days."""
    items = upcoming(days)

    if not items:
        return {
            "sent": False,
            "count": 0,
            "reason": f"No reminders are set with a deadline in the next {days} days. Click Remind me on a card first.",
        }

    lines = []
    for left, opportunity in items:
        when = "TODAY" if left == 0 else f"{left} day(s) left"
        title = opportunity.get("title") or "Opportunity"
        lines.append(
            f"- {title} ({opportunity['deadline']}, {when})\n  {opportunity.get('url') or ''}"
        )

    body = "Upcoming deadlines:\n\n" + "\n".join(lines) + "\n\nVerify dates on the official pages."
    result = notify(f"ScholarRadar: {len(items)} deadline(s) in the next {days} days", body)

    return {"sent": any(result.values()), "count": len(items), "channels": result}