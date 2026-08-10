#!/usr/bin/env python3
"""
test_usage.py — pin the sign-in check and the login/usage event log.

Pure unit tests: a temp SQLite file via the USAGE_DB env var (set BEFORE the
modules load), no model, no network.

Run:  python3 tests/test_usage.py      (plain, prints PASS/FAIL, exits 1 on failure)
  or: pytest tests/test_usage.py
"""
import hashlib
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_TMP = tempfile.mkdtemp()
os.environ["USAGE_DB"] = os.path.join(_TMP, "usage_test.db")

import usage  # noqa: E402
import app    # noqa: E402


def _reset_db():
    p = usage._db_path()
    if p.exists():
        p.unlink()


# ── password check ────────────────────────────────────────────────────────────
def test_password_plaintext():
    assert app._password_ok("secret-pw", "secret-pw")
    assert not app._password_ok("secret-pw", "wrong")
    assert not app._password_ok("secret-pw", "")
    assert not app._password_ok("", "")          # a blank stored password never matches


def test_password_sha256():
    h = hashlib.sha256(b"secret-pw").hexdigest()
    assert app._password_ok(h, "secret-pw")
    assert app._password_ok(h.upper(), "secret-pw")
    assert not app._password_ok(h, "wrong")
    # a 64-hex password stored in plaintext form must be treated as a hash,
    # so the literal hex string itself must NOT authenticate
    assert not app._password_ok(h, h)


def test_password_ironclad_paste_junk():
    # numeric password stored WITHOUT quotes parses as a TOML int — must still work
    assert app._password_ok(123456, "123456")
    assert app._password_ok(123456, " 123456 ")
    # trailing/leading whitespace on either side (chat/Word paste)
    assert app._password_ok(" pw-1 ", "pw-1")
    assert app._password_ok("pw-1", "  pw-1  ")
    # non-breaking space and zero-width characters (WhatsApp/Word paste)
    assert app._password_ok("pw-1 ", "pw-1")
    assert app._password_ok("pw-1", "​pw-1﻿")
    # phone-keyboard smart quotes vs straight quotes inside the password
    assert app._password_ok("it's-pw", "it’s-pw")
    assert app._password_ok("it’s-pw", "it's-pw")
    # user pastes the whole TOML value including its quotes
    assert app._password_ok("invite-pw-1", '"invite-pw-1"')
    assert app._password_ok("invite-pw-1", "'invite-pw-1'")
    # …but a wrong password wrapped in quotes still fails
    assert not app._password_ok("invite-pw-1", '"wrong"')
    # sha256 stored hash still matches a quote-wrapped correct password
    h = hashlib.sha256(b"secret-pw").hexdigest()
    assert app._password_ok(h, '"secret-pw"')


def test_auth_users_keeps_scalars():
    # mimic _auth_users' filter: scalars (incl. unquoted numeric passwords) kept,
    # tables/lists (unquoted-email damage) dropped
    raw = {"rohit": 123456, "ok": "pw", "flag": True,
           "a": {"b@c": {"com": "pw"}}, "l": ["x"]}
    filtered = {str(k): v for k, v in raw.items()
                if isinstance(v, (str, int, float, bool))}
    assert set(filtered) == {"rohit", "ok", "flag"}
    assert app._password_ok(filtered["rohit"], "123456")


def test_resolve_user_paste_junk():
    users = {"rohit": "pw", "priya@gmail.com": "pw2"}
    assert app._resolve_user("​rohit ", users) == "rohit"
    assert app._resolve_user("PRIYA@GMAIL.COM﻿", users) == "priya@gmail.com"


# ── login-identifier resolution (username OR email, forgivingly typed) ────────
def test_resolve_user():
    users = {"rohit": "pw", "priya@gmail.com": "pw2"}
    assert app._resolve_user("rohit", users) == "rohit"
    assert app._resolve_user("  rohit  ", users) == "rohit"          # stray spaces
    assert app._resolve_user("Priya@Gmail.COM", users) == "priya@gmail.com"   # email case
    assert app._resolve_user("ROHIT", users) == "rohit"
    assert app._resolve_user("nobody", users) is None
    assert app._resolve_user("", users) is None
    assert app._resolve_user(None, users) is None


def test_auth_users_would_skip_unquoted_email_tables():
    # An unquoted email key parses as a nested table {"a": {"b@c": {"com": "pw"}}} —
    # _auth_users keeps only string values, so such an entry is dropped, not fatal.
    # (Exercise the same filter _auth_users applies, without needing st.secrets.)
    raw = {"rohit": "pw", "a": {"b@c": {"com": "pw"}}}
    filtered = {str(k): v for k, v in raw.items() if isinstance(v, str)}
    assert filtered == {"rohit": "pw"}
    assert app._resolve_user("a", filtered) is None


# ── event log ─────────────────────────────────────────────────────────────────
def test_log_and_question_count():
    _reset_db()
    usage.log("rohit", "login")
    usage.log("rohit", "question", "when is gratuity payable?")
    usage.log("rohit", "question", "what changed from old laws")
    usage.log("priya", "question", "overtime pay?")
    usage.log("rohit", "logout")
    assert usage.question_count("rohit") == 2
    assert usage.question_count("priya") == 1
    assert usage.question_count("nobody") == 0


def test_stats_rollup():
    _reset_db()
    usage.log("a", "login")
    usage.log("a", "question", "q1")
    usage.log("a", "question", "q2")
    usage.log("a", "login")
    usage.log("b", "login")
    usage.log("b", "question", "q3")
    s = {r["user"]: r for r in usage.stats()}
    assert s["a"]["questions"] == 2 and s["a"]["logins"] == 2
    assert s["b"]["questions"] == 1 and s["b"]["logins"] == 1
    assert s["a"]["last_seen"] >= s["a"]["questions"] > 0   # last_seen populated
    # ordered most-questions-first
    assert [r["user"] for r in usage.stats()][0] == "a"


def test_recent_newest_first():
    _reset_db()
    for i in range(5):
        usage.log("u", "question", f"q{i}")
    ev = usage.recent(3)
    assert len(ev) == 3
    assert [e["detail"] for e in ev] == ["q4", "q3", "q2"]


def test_all_events_complete_and_oldest_first():
    _reset_db()
    for i in range(60):                              # beyond recent()'s 50-row cap
        usage.log("u", "question", f"q{i}")
    ev = usage.all_events()
    assert len(ev) == 60
    assert ev[0]["detail"] == "q0" and ev[-1]["detail"] == "q59"


def test_usage_csvs():
    _reset_db()
    usage.log("priya@gmail.com", "login")
    usage.log("priya@gmail.com", "question", "when is gratuity payable?")
    summary, activity = app._usage_csvs()
    assert summary.splitlines()[0] == "user,questions,logins,last_activity"
    assert "priya@gmail.com,1,1," in summary
    assert activity.splitlines()[0] == "when,user,event,question"
    assert "when is gratuity payable?" in activity
    assert activity.count("priya@gmail.com") == 2    # one row per event


def test_log_truncates_and_never_raises():
    _reset_db()
    usage.log("u" * 500, "e" * 500, "d" * 5000)      # oversized fields are clipped
    e = usage.recent(1)[0]
    assert len(e["user"]) == 80 and len(e["event"]) == 32 and len(e["detail"]) == 500
    # unwritable path → every call degrades to a no-op instead of raising
    old = os.environ["USAGE_DB"]
    os.environ["USAGE_DB"] = "/nonexistent-dir/usage.db"
    try:
        usage.log("u", "question")
        assert usage.question_count("u") == 0
        assert usage.stats() == []
        assert usage.recent() == []
    finally:
        os.environ["USAGE_DB"] = old



# ── the login-screen setup check (masked, password-free) ──────────────────────
def test_mask_id():
    assert app._mask_id("rohit") == "r\u2022\u2022\u2022t"
    assert app._mask_id("ab") == "ab"                       # too short to mask — kept
    m = app._mask_id("priya@gmail.com")
    assert m.startswith("p") and m.endswith(".com") and "\u2022" in m
    assert "riya" not in m and "gmai" not in m              # the middle is hidden


def test_setup_rows_health_report():
    import hashlib
    top = {"AWS_REGION": "us-east-1", "admins": ["rohit"], "users": {},
           "stray@user.com": "oops-above-users-line"}
    users = {"rohit": "pw123", "numpass": 987654,
             "hash": hashlib.sha256(b"x").hexdigest(),
             "broken": {"unquoted": {"email": "pw"}}}
    rows = app._setup_rows(top, users, ["rohit", "ghost"])
    text = " | ".join(m for _, m in rows)
    warns = [m for lvl, m in rows if lvl == "warn"]
    # healthy accounts described with password SHAPE, never the value
    assert app._mask_id("rohit") in text and "text, 5 characters" in text
    assert "pw123" not in text and "987654" not in text
    assert "sha256 hash" in text
    # broken (unquoted-email) entry flagged
    assert any("missing its quotes" in m for m in warns)
    # account line pasted above [users] flagged
    assert any("ABOVE the `[users]` line" in m for m in warns)
    # admin with no matching account flagged; existing admin not flagged
    ghost = app._mask_id("ghost")
    assert any(ghost in m and "no matching account" in m for m in warns)
    assert not any("no matching account" in m and app._mask_id("rohit") in m for m in warns)


def test_setup_rows_empty_users():
    rows = app._setup_rows({}, {}, [])
    assert any("No **[users]** table" in m for _, m in rows)
    assert any("No **admins** list" in m for _, m in rows)



# ── access-code sign-in (the simple mode) ─────────────────────────────────────
def test_parse_codes():
    assert app._parse_codes("rohit-731, priya-410, vendor-527") == \
        ["rohit-731", "priya-410", "vendor-527"]
    # newlines / semicolons / extra spaces / duplicates / case all tolerated
    assert app._parse_codes(" ROHIT-731 ;\npriya-410,, priya-410 ") == \
        ["rohit-731", "priya-410"]
    assert app._parse_codes(["Rohit-731", "priya-410"]) == ["rohit-731", "priya-410"]
    assert app._parse_codes(None) == []
    assert app._parse_codes("") == []


def test_norm_code_forgiving():
    assert app._norm_code("  ROHIT - 731 ") == "rohit-731"
    assert app._norm_code("\u200brohit-731\ufeff") == "rohit-731"   # zero-width paste junk
    assert app._norm_code("rohit\u00a0-\u00a0731") == "rohit-731"   # non-breaking spaces
    assert app._norm_code("rohit-731") == "rohit-731"


def test_setup_rows_codes():
    rows = app._setup_rows_codes(["rohit-731", "priya-410"], ["rohit-731"], True)
    text = " | ".join(m for _, m in rows)
    assert "2 code(s) loaded" in text
    assert app._mask_id("rohit-731") in text
    assert "rohit-731" not in text.replace(app._mask_id("rohit-731"), "")  # masked only
    assert "IGNORED" in text                       # [users] present but codes mode wins
    rows = app._setup_rows_codes(["x-1"], [], False)
    assert any(lvl == "warn" and "ADMIN_CODES" in m for lvl, m in rows)


def test_is_admin_covers_both_systems():
    # code-mode admin check is normalising and case-insensitive
    import types
    assert app._norm_code(" ROHIT-731 ") in app._parse_codes("rohit-731")


def _main():
    fails = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"ok   {name}")
            except AssertionError as e:
                fails += 1
                print(f"FAIL {name}: {e}")
    print(f"\n{sum(1 for n in globals() if n.startswith('test_')) - fails} passed, {fails} failed")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    _main()
