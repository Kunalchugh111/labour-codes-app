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
import base64
import json
import os
import sqlite3
import time
import urllib.request
from pathlib import Path


def _db_path() -> Path:
    return Path(os.environ.get("USAGE_DB") or Path(__file__).parent / "usage.db")


# ── Optional persistence: mirror the log to a GitHub branch ──────────────────
# Streamlit Cloud wipes the local disk on every redeploy, which kept erasing
# usage history. With a GITHUB_TOKEN secret the log survives: after each event
# the full log is mirrored to a JSONL file on a SIDE branch of the app repo
# (never the deploy branch, so mirror commits can't trigger redeploys), and on
# startup the local DB re-imports whatever the mirror holds. All network work
# is fail-soft — a bad token degrades to today's local-only behaviour.
_SYNC = {"token": "", "repo": "", "branch": "usage-log", "path": "usage-events.jsonl"}


def configure_sync(token: str, repo: str, branch: str = "usage-log") -> None:
    _SYNC["token"] = str(token or "").strip()
    _SYNC["repo"] = str(repo or "").strip().strip("/")
    _SYNC["branch"] = str(branch or "usage-log").strip() or "usage-log"


def sync_enabled() -> bool:
    return bool(_SYNC["token"] and _SYNC["repo"])


def _gh_api(path: str, data: dict = None, method: str = None) -> dict:
    req = urllib.request.Request(
        "https://api.github.com" + path,
        data=json.dumps(data).encode() if data is not None else None,
        method=method or ("POST" if data is not None else "GET"))
    req.add_header("Authorization", f"Bearer {_SYNC['token']}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode() or "{}")


def _remote_get() -> tuple[list[dict], str]:
    """(rows, file_sha) from the mirror branch; ([], None) when absent/unreachable."""
    try:
        j = _gh_api(f"/repos/{_SYNC['repo']}/contents/{_SYNC['path']}?ref={_SYNC['branch']}")
        txt = base64.b64decode(j.get("content", "") or "").decode("utf-8", "replace")
        rows = []
        for line in txt.splitlines():
            line = line.strip()
            if line:
                try:
                    rows.append(json.loads(line))
                except Exception:
                    pass
        return rows, j.get("sha")
    except Exception:
        return [], None


def _ensure_branch() -> bool:
    try:
        _gh_api(f"/repos/{_SYNC['repo']}/git/ref/heads/{_SYNC['branch']}")
        return True
    except Exception:
        pass
    try:
        repo = _gh_api(f"/repos/{_SYNC['repo']}")
        base = _gh_api(f"/repos/{_SYNC['repo']}/git/ref/heads/"
                       f"{repo.get('default_branch', 'main')}")
        _gh_api(f"/repos/{_SYNC['repo']}/git/refs",
                {"ref": f"refs/heads/{_SYNC['branch']}", "sha": base["object"]["sha"]})
        return True
    except Exception:
        return False


def _export_jsonl() -> str:
    return "".join(json.dumps(e, ensure_ascii=False) + "\n" for e in all_events())


def _import_rows(rows: list[dict]) -> int:
    """Insert mirrored events the local DB doesn't have (exact-tuple match); returns
    how many were imported. Idempotent — importing the same rows twice adds nothing."""
    if not rows:
        return 0
    try:
        with _conn() as con:
            have = {(float(t), u, e, d) for t, u, e, d in
                    con.execute("SELECT ts, user, event, detail FROM events")}
            n = 0
            for r in rows:
                try:
                    k = (float(r.get("ts", 0)), str(r.get("user", ""))[:80],
                         str(r.get("event", ""))[:32], str(r.get("detail", ""))[:500])
                except Exception:
                    continue
                if k[0] and k not in have:
                    con.execute("INSERT INTO events(ts, user, event, detail) VALUES(?,?,?,?)", k)
                    have.add(k)
                    n += 1
        return n
    except Exception:
        return 0


def restore_from_remote() -> int:
    """Merge the GitHub mirror into the local DB (call once at startup)."""
    if not sync_enabled():
        return 0
    rows, _ = _remote_get()
    return _import_rows(rows)


def push_to_remote() -> bool:
    """Mirror the entire local log to the branch (small file; last writer wins)."""
    if not sync_enabled():
        return False
    try:
        _, sha = _remote_get()
        if sha is None and not _ensure_branch():
            return False
        payload = {"message": "sync usage log", "branch": _SYNC["branch"],
                   "content": base64.b64encode(_export_jsonl().encode()).decode()}
        if sha:
            payload["sha"] = sha
        _gh_api(f"/repos/{_SYNC['repo']}/contents/{_SYNC['path']}", payload, method="PUT")
        return True
    except Exception:
        return False


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
    if sync_enabled():
        push_to_remote()          # mirror to GitHub so a redeploy can't erase history


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


def all_events() -> list[dict]:
    """Every event, oldest first — for the downloadable report (recent() caps at 50)."""
    try:
        with _conn() as con:
            rows = con.execute(
                "SELECT ts, user, event, detail FROM events ORDER BY id").fetchall()
        return [{"ts": t, "user": u, "event": e, "detail": d} for t, u, e, d in rows]
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
