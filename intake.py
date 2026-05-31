"""Case-aware intake for compliance questions.

Three deterministic jobs, all grounded in the corpus so they work without the model:
  • screen()        – spot the decisive facts a scenario is missing (tenure, head-count, reason)
  • applicability() – verified establishment-size rules for the answer
  • cross_refs()     – related provisions the manager should also check

Thresholds are taken straight from the statute:
  IR Code §65  – lay-off compensation (§§67–69) does not apply below 50 workers
  IR Code §70  – retrenchment notice + compensation (≥1 year continuous service)
  IR Code §77/§79 – prior Government permission for lay-off/retrenchment/closure at 300+ workers
  SS Code  §53 – gratuity needs 5 years' continuous service (waived on death/disablement)
"""
import re

# ── Facts we may ask for: key, question, and chips of (button label, clause appended to query) ──
TENURE = {
    "key": "tenure",
    "q": "How long have they worked there?",
    "opts": [("Under 1 year", "with under one year of continuous service"),
             ("1–5 years", "with 1 to 5 years of continuous service"),
             ("5 years or more", "with 5 or more years of continuous service")],
}
SIZE = {
    "key": "size",
    "q": "How many workers does the establishment employ?",
    "opts": [("Under 50", "in an establishment employing fewer than 50 workers"),
             ("50–299", "in an establishment employing 50 to 299 workers"),
             ("300 or more", "in an establishment employing 300 or more workers")],
}
REASON = {
    "key": "reason",
    "q": "Why is the employment ending?",
    "opts": [("Redundancy / cost", "the reason being redundancy or cost-cutting (not misconduct)"),
             ("Misconduct", "the reason being misconduct, after an inquiry"),
             ("Poor performance", "the reason being poor performance"),
             ("End of fixed term", "because a fixed-term contract has come to an end")],
}

# ── Topic detection (first match wins) ─────────────────────────────────────────
_TOPICS = [
    ("retrench", r"retrench|lay[\s-]?off|laid off|terminat|dismiss|fire[sd]?\b|fired|let \w+ go|"
                 r"sack|remov\w* from service|end(?:ing)? (?:his|her|their|the) (?:service|employment)"),
    ("closure",  r"clos(?:e|ing|ure)\b|shut(?:ting)? down|wind(?:ing)? up"),
    ("gratuity", r"gratuity"),
    ("maternity", r"maternity|pregnan|childbirth|maternal"),
    ("bonus",    r"\bbonus(?:es)?\b"),
    ("wages",    r"\bwages?\b|salary|minimum wage|deduction"),
]


def topic(q: str):
    ql = q.lower()
    for name, pat in _TOPICS:
        if re.search(pat, ql):
            return name
    return None


# ── Is this a first-person compliance scenario (vs a definition/comparison/info question)? ──
_SCENARIO = re.compile(
    r"\b(i|we|my|our|us)\b|can i|did i|is it (?:legal|ok|okay|fine|allowed|valid|lawful)|"
    r"want to|planning to|going to|need to|how do i|do i (?:have|need)|should i|am i|"
    r"\bemployee\b|\bworker\b|\bstaff\b", re.I)
_NOT_SCENARIO = re.compile(
    r"what is\b|what are\b|defin|meaning of|how is .* defined|what changed|"
    r"difference between|compared? to|\bvs\b", re.I)

# ── Detect facts already stated in the query, so we never ask twice ────────────
_TENURE_RE = re.compile(r"\d+\s*(?:\+|plus)?\s*(?:year|yr|month|day)|probation", re.I)
_SIZE_RE = re.compile(r"\d[\d,]*\s*(?:\+|or more|or fewer)?\s*"
                      r"(?:worker|workmen|workman|employee|staff|people|persons?|head)|"
                      r"(?:establishment|factory|company|unit|firm|office) of \d", re.I)
_REASON_RE = re.compile(r"misconduct|redundan|performance|theft|abscond|fixed[\s-]?term|"
                        r"cost[\s-]?cut|restructur|discipline|insubordinat|attendance", re.I)
_PRESENT = {"tenure": _TENURE_RE.search, "size": _SIZE_RE.search, "reason": _REASON_RE.search}


def _decisive(topic_name: str, ql: str):
    """The facts that change the answer for this topic. For retrenchment the reason only matters
    when the verb is ambiguous (terminate/fire/dismiss) — an explicit 'retrench'/'lay-off' already
    fixes it as a non-punitive exit."""
    if topic_name == "retrench":
        explicit = re.search(r"retrench|lay[\s-]?off|laid off", ql)
        return [TENURE, SIZE] if explicit else [REASON, TENURE, SIZE]
    return {"closure": [SIZE], "gratuity": [TENURE]}.get(topic_name, [])


def screen(q: str, max_q: int = 2):
    """Decisive facts (≤ max_q) the query is missing. [] for non-scenario / general questions."""
    ql = q.lower()
    if _NOT_SCENARIO.search(ql) and not _SCENARIO.search(ql):
        return []
    t = topic(q)
    if not t or not _SCENARIO.search(ql):
        return []
    missing = [f for f in _decisive(t, ql) if not _PRESENT[f["key"]](ql)]
    return missing[:max_q]


def clause(got: dict) -> str:
    """Fold collected fact-clauses into a parenthetical appended to the query."""
    parts = [v for v in got.values() if v]
    return (" (" + "; ".join(parts) + ")") if parts else ""


def facts_from_query(q: str) -> dict:
    """Best-effort size/tenure/reason bands parsed from free text, so applicability works even
    when the manager typed the numbers instead of using the chips."""
    ql, got = q.lower(), {}
    m = re.search(r"(\d[\d,]*)\s*(?:\+|or more)?\s*"
                  r"(?:worker|workmen|workman|employee|staff|people|persons?)", ql)
    if m:
        n = int(m.group(1).replace(",", ""))
        got["size"] = ("in an establishment employing 300 or more workers" if n >= 300
                       else "in an establishment employing 50 to 299 workers" if n >= 50
                       else "in an establishment employing fewer than 50 workers")
    m = re.search(r"(\d+)\s*(?:\+|plus)?\s*(?:year|yr)", ql)
    if m:
        y = int(m.group(1))
        got["tenure"] = ("with 5 or more years of continuous service" if y >= 5
                         else "with 1 to 5 years of continuous service" if y >= 1
                         else "with under one year of continuous service")
    if re.search(r"misconduct", ql):
        got["reason"] = "the reason being misconduct, after an inquiry"
    elif re.search(r"fixed[\s-]?term", ql):
        got["reason"] = "because a fixed-term contract has come to an end"
    return got


# ── Verified establishment-size / tenure applicability for the answer ──────────
def applicability(topic_name: str, got: dict):
    """Corpus-grounded notes on what applies given the gathered facts. Each cites its provision."""
    notes, size, tenure, reason = [], got.get("size", ""), got.get("tenure", ""), got.get("reason", "")
    if topic_name in ("retrench", "closure"):
        if "300 or more" in size:
            notes.append("**300+ workers** — Chapter X applies: prior permission of the appropriate "
                         "Government is a *condition precedent* to lay-off, retrenchment or closure "
                         "(IR Code §77, §79).")
        elif "50 to 299" in size:
            notes.append("**50–299 workers** — retrenchment notice + compensation (§70) and lay-off "
                         "compensation (§§67–69) apply; prior Government permission is **not** required "
                         "(that begins at 300 workers, §77).")
        elif "fewer than 50" in size:
            notes.append("**Under 50 workers** — lay-off compensation (§§67–69) does **not** apply "
                         "(IR Code §65); retrenchment notice and compensation under §70 still apply "
                         "where the worker has a year or more of continuous service.")
    if topic_name == "retrench":
        if "under one year" in tenure:
            notes.append("**Under 1 year of service** — the §70 retrenchment safeguards (one month's "
                         "notice + compensation) generally require **one year** of continuous service, "
                         "so they may not be triggered here.")
        if "misconduct" in reason:
            notes.append("**Misconduct dismissal** — a punitive dismissal for misconduct (after due "
                         "inquiry) is **not** 'retrenchment', so the notice/compensation rules do not "
                         "apply; the standing-orders disciplinary procedure governs instead.")
        if "fixed-term" in reason:
            notes.append("**End of fixed term** — non-renewal of a fixed-term contract on its expiry "
                         "is excluded from 'retrenchment'; but a fixed-term worker is entitled to "
                         "gratuity on a *pro rata* basis (SS Code §53).")
    if topic_name == "gratuity" and ("under one year" in tenure or "1 to 5 years" in tenure):
        notes.append("**Gratuity** needs **5 years** of continuous service (waived on death or "
                     "disablement); fixed-term employees are paid *pro rata* even under five years "
                     "(SS Code §53).")
    return notes


# ── Related provisions to also check (verified to exist in the corpus) ─────────
# Each entry: (chip label, query to submit when clicked).
_CROSS = {
    "retrench": [
        ("Procedure for retrenchment", "Explain Section 71 of the Industrial Relations Code"),
        ("Re-employment of retrenched worker", "Explain Section 72 of the Industrial Relations Code"),
        ("Worker re-skilling fund", "Explain Section 83 of the Industrial Relations Code"),
        ("Notice of retrenchment to the Government", "What does Rule 33 of the Industrial Relations Central Rules require for notice of retrenchment?"),
    ],
    "closure": [
        ("Conditions for closure", "What are the conditions and notice required for closure under the Industrial Relations Code?"),
        ("Notice of intended closure", "What does Rule 29 of the Industrial Relations Central Rules require for notice of closure?"),
    ],
    "gratuity": [
        ("Payment of gratuity", "Explain Section 53 of the Code on Social Security"),
        ("Continuous service", "How is continuous service defined for gratuity under the Code on Social Security?"),
    ],
    "maternity": [
        ("Right to maternity benefit", "Explain Section 60 of the Code on Social Security"),
        ("Notice of claim for maternity benefit", "Explain Section 62 of the Code on Social Security"),
    ],
}


def cross_refs(topic_name: str):
    """Related provisions for a topic as (label, query) pairs, or []."""
    return _CROSS.get(topic_name, [])
