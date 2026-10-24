
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

    for opportunity in db.all_opportunities():
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
