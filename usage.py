"""usage.py — login / activity log for the Labour Codes Assistant.

A small SQLite event log (no external services): every login, logout, failed
sign-in and question is appended as one row, and the admin panel in app.py
reads simple aggregates back out. Kept streamlit-free so it unit-tests bare.

Storage: usage.db next to this file, overridable via the USAGE_DB env var
(app.py wires st.secrets["USAGE_DB"] through to that env var). NB on
Streamlit Community Cloud the filesystem is ephemeral — the log survives
reruns and app restarts, but a redeploy resets it; point USAGE_DB at a
mounted/persistent path if long-term history matters.
"""
import os
import sqlite3
import time
from pathlib import Path


def _db_path() -> Path:
    return Path(os.environ.get("USAGE_DB") or Path(__file__).parent / "usage.db")


def _conn() -> sqlite3.Connection:
    con = sqlite3.connect(_db_path(), timeout=10)
    con.execute(
        "CREATE TABLE IF NOT EXISTS events("
        " id INTEGER PRIMARY KEY AUTOINCREMENT,"
        " ts REAL NOT NULL,"
        " user TEXT NOT NULL,"
        " event TEXT NOT NULL,"
        " detail TEXT NOT NULL DEFAULT '')")
    return con


def log(user: str, event: str, detail: str = "") -> None:
    """Append one event. Fail-soft: usage logging must never break an answer."""
    try:
        with _conn() as con:
            con.execute("INSERT INTO events(ts, user, event, detail) VALUES(?,?,?,?)",
                        (time.time(), str(user)[:80], str(event)[:32], str(detail)[:500]))
    except Exception:
        pass


def question_count(user: str) -> int:
    try:
        with _conn() as con:
            (n,) = con.execute("SELECT COUNT(*) FROM events WHERE user=? AND event='question'",
                               (str(user),)).fetchone()
        return int(n)
    except Exception:
        return 0


def stats() -> list[dict]:
    """Per-user rollup: [{user, questions, logins, last_seen}], most questions first."""
    try:
        with _conn() as con:
            rows = con.execute(
                "SELECT user,"
                " COALESCE(SUM(event='question'), 0),"
                " COALESCE(SUM(event='login'), 0),"
                " MAX(ts)"
                " FROM events GROUP BY user"
                " ORDER BY 2 DESC, 4 DESC").fetchall()
        return [{"user": u, "questions": int(q), "logins": int(l), "last_seen": t}
                for u, q, l, t in rows]
    except Exception:
        return []


def recent(limit: int = 50) -> list[dict]:
    """Latest events, newest first: [{ts, user, event, detail}]."""
    try:
        with _conn() as con:
            rows = con.execute(
                "SELECT ts, user, event, detail FROM events ORDER BY id DESC LIMIT ?",
                (int(limit),)).fetchall()
        return [{"ts": t, "user": u, "event": e, "detail": d} for t, u, e, d in rows]
    except Exception:
        return []
