
import json
import sqlite3
from pathlib import Path

from .config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS profiles (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    name TEXT,
    interests TEXT,
    cv_text TEXT,
    profile_json TEXT
);

CREATE TABLE IF NOT EXISTS opportunities (
    url TEXT PRIMARY KEY,
    title TEXT,
    deadline TEXT,
    eligibility TEXT,
    documents TEXT,
    funding TEXT,
    summary TEXT,
    raw_text TEXT,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""


def conn():
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(DB_PATH, timeout=30)
    connection.row_factory = sqlite3.Row
    return connection


def init():
    with conn() as connection:
        connection.executescript(SCHEMA)


def save_profile(cv_text: str, interests: str = "", name: str = ""):
    profile_json = json.dumps({
        "name": name,
        "interests": interests,
    })

    with conn() as connection:
        connection.execute(
            """
            INSERT INTO profiles
                (id, name, interests, cv_text, profile_json)
            VALUES (1, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name = excluded.name,
                interests = excluded.interests,
                cv_text = excluded.cv_text,
                profile_json = excluded.profile_json
            """,
            (name, interests, cv_text, profile_json),
        )


def get_profile() -> dict:
    with conn() as connection:
        row = connection.execute(
            "SELECT * FROM profiles WHERE id = 1"
        ).fetchone()

    return dict(row) if row else {}


def upsert_opportunity(o: dict, raw_text: str):
    url = o.get("url")
    if not url:
        raise ValueError("Opportunity URL is required.")

    with conn() as connection:
        connection.execute(
            """
            INSERT INTO opportunities
                (url, title, deadline, eligibility, documents,
                 funding, summary, raw_text)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(url) DO UPDATE SET
                title = excluded.title,
                deadline = excluded.deadline,
                eligibility = excluded.eligibility,
                documents = excluded.documents,
                funding = excluded.funding,
                summary = excluded.summary,
                raw_text = excluded.raw_text,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                url,
                o.get("title"),
                o.get("deadline"),
                o.get("eligibility"),
                json.dumps(o.get("documents", [])),
                o.get("funding"),
                o.get("summary"),
                raw_text[:20000],
            ),
        )


def all_opportunities():
    with conn() as connection:
        rows = connection.execute(
            "SELECT * FROM opportunities ORDER BY updated_at DESC"
        ).fetchall()

    return [dict(row) for row in rows]
