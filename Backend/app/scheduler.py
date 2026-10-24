from datetime import date, datetime
from apscheduler.schedulers.background import BackgroundScheduler
from . import db
from .alerts import notify

REMIND_DAYS = {14, 7, 3, 1}


def deadline_check():
    for o in db.all_opportunities():
        if not o["deadline"]:
            continue
        try:
            d = datetime.strptime(o["deadline"], "%Y-%m-%d").date()
        except ValueError:
            continue
        left = (d - date.today()).days
        if left in REMIND_DAYS:
            notify(f"{left} day(s) left: {o['title']}", f"Deadline {o['deadline']}\n{o['url']}")


def start():
    s = BackgroundScheduler()
    s.add_job(deadline_check, "cron", hour=9)
    s.start()
    return s