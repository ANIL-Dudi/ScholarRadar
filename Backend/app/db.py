import json
import sqlite3
from .config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS profiles (
  id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, interests TEXT, cv_text TEXT, profile_json TEXT);
CREATE TABLE IF NOT EXISTS opportunities (
  url TEXT PRIMARY KEY, title TEXT, deadline TEXT, eligibility TEXT, documents TEXT,
  funding TEXT, summary TEXT, raw_text TEXT, updated_at TEXT DEFAULT CURRENT_TIMESTAMP);
"""


def conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def init():
    with conn() as c:
        c.executescript(SCHEMA)


def upsert_opportunity(o: dict, raw_text: str):
    with conn() as c:
        c.execute(
            """INSERT INTO opportunities (url,title,deadline,eligibility,documents,funding,summary,raw_text)
               VALUES (?,?,?,?,?,?,?,?)
               ON CONFLICT(url) DO UPDATE SET title=excluded.title, deadline=excluded.deadline,
               eligibility=excluded.eligibility, documents=excluded.documents, funding=excluded.funding,
               summary=excluded.summary, raw_text=excluded.raw_text, updated_at=CURRENT_TIMESTAMP""",
            (o["url"], o.get("title"), o.get("deadline"), o.get("eligibility"),
             json.dumps(o.get("documents", [])), o.get("funding"), o.get("summary"), raw_text[:20000]),
        )


def all_opportunities():
    with conn() as c:
        return [dict(r) for r in c.execute("SELECT * FROM opportunities")]