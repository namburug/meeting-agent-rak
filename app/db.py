"""
Plain sqlite3 storage layer. No ORM — kept deliberately simple so the whole
app runs with zero external services beyond the LLM and (optionally) Slack.
"""
import hashlib
import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

from app.config import DATABASE_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS meetings (
    id TEXT PRIMARY KEY,
    filename TEXT,
    meeting_date TEXT,
    transcript_hash TEXT UNIQUE,
    executive_summary TEXT,
    decisions_json TEXT,
    open_questions_json TEXT,
    risks_json TEXT,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS action_items (
    id TEXT PRIMARY KEY,
    meeting_id TEXT,
    text TEXT,
    owner_raw TEXT,
    owner_name TEXT,
    owner_email TEXT,
    owner_slack_id TEXT,
    owner_matched INTEGER,
    due_date_raw TEXT,
    due_date_resolved TEXT,
    priority TEXT,
    confidence REAL,
    evidence TEXT,
    status TEXT DEFAULT 'pending',      -- pending | approved | rejected
    external_ref TEXT,                  -- set once a side effect has created something for this item
    created_at TEXT,
    FOREIGN KEY(meeting_id) REFERENCES meetings(id)
);

CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    meeting_id TEXT,
    item_id TEXT,
    action TEXT,
    payload_json TEXT,
    actor TEXT,
    timestamp TEXT
);
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def hash_transcript(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def init_db():
    os.makedirs(os.path.dirname(DATABASE_PATH) or ".", exist_ok=True)
    with get_conn() as conn:
        conn.executescript(SCHEMA)


@contextmanager
def get_conn():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def find_meeting_by_hash(transcript_hash: str):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM meetings WHERE transcript_hash = ?", (transcript_hash,)).fetchone()
        return dict(row) if row else None


def insert_meeting(meeting_id, filename, meeting_date, transcript_hash, record):
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO meetings (id, filename, meeting_date, transcript_hash, executive_summary,
               decisions_json, open_questions_json, risks_json, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                meeting_id, filename, meeting_date, transcript_hash, record.get("executive_summary", ""),
                json.dumps(record.get("decisions", [])), json.dumps(record.get("open_questions", [])),
                json.dumps(record.get("risks", [])), now(),
            ),
        )


def insert_action_item(item_id, meeting_id, item: dict):
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO action_items (id, meeting_id, text, owner_raw, owner_name, owner_email,
               owner_slack_id, owner_matched, due_date_raw, due_date_resolved, priority, confidence,
               evidence, status, external_ref, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', NULL, ?)""",
            (
                item_id, meeting_id, item["text"], item.get("owner_raw"), item.get("owner_name"),
                item.get("owner_email"), item.get("owner_slack_id"), int(item.get("owner_matched", False)),
                item.get("due_date_raw"), item.get("due_date_resolved"), item.get("priority", "medium"),
                item.get("confidence", 0.5), item.get("evidence", ""), now(),
            ),
        )


def get_meeting(meeting_id: str):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM meetings WHERE id = ?", (meeting_id,)).fetchone()
        return dict(row) if row else None


def list_meetings():
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM meetings ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]


def get_items_for_meeting(meeting_id: str):
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM action_items WHERE meeting_id = ? ORDER BY created_at", (meeting_id,)).fetchall()
        return [dict(r) for r in rows]


def get_item(item_id: str):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM action_items WHERE id = ?", (item_id,)).fetchone()
        return dict(row) if row else None


def update_item(item_id: str, fields: dict):
    if not fields:
        return
    cols = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [item_id]
    with get_conn() as conn:
        conn.execute(f"UPDATE action_items SET {cols} WHERE id = ?", values)


def log_audit(meeting_id: str, action: str, payload: dict, actor: str, item_id: str = None):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO audit_log (meeting_id, item_id, action, payload_json, actor, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
            (meeting_id, item_id, action, json.dumps(payload), actor, now()),
        )


def get_audit_log(meeting_id: str):
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM audit_log WHERE meeting_id = ? ORDER BY id", (meeting_id,)).fetchall()
        return [dict(r) for r in rows]
