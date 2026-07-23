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
    r"\bemployees?\b|\bworkers?\b|\bworkmen\b|\bstaff\b", re.I)
_NOT_SCENARIO = re.compile(
    r"what is\b|what are\b|defin|meaning of|how is .* defined|what changed|"
    r"difference between|compared? to|\bvs\b", re.I)

# ── Detect facts already stated in the query, so we never ask twice ────────────
# Days count as tenure only in a service/worked context — "laid off for 15 days" or
# "5 hours overtime over 3 days" is NOT length of service, and treating it as such made
# screen() skip the tenure question while facts_from_query() extracted nothing.
_TENURE_DAYS = (r"(?:worked|served|service\s+(?:of|for))\s*(?:for\s*)?(\d[\d,]*)\s*days?|"
                r"(\d[\d,]*)\s*days?(?:'|s)?\s*(?:of\s+)?(?:continuous\s+)?(?:service|employment)")
_TENURE_RE = re.compile(r"\d+\s*(?:\+|plus)?\s*(?:year|yr|month)|probation|" + _TENURE_DAYS, re.I)
# "N or fewer" is band-ambiguous above 50 (could be <50 or 50–299), so only a 1–2-digit
# count (necessarily ≤ 99 → resolvable) counts as a stated size; bigger "or fewer" phrasings
# fall through to the size question.
_SIZE_RE = re.compile(r"(?:\b\d{1,2}\s*or fewer|\d[\d,]*\s*(?:\+|or more)?)\s*"
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
    # Mirror _SIZE_RE exactly: every phrasing that stops screen() from asking the size
    # question must also yield a size band here, or applicability() goes silent on it.
    m = (re.search(r"(?:\b(\d{1,2})\s*or fewer|(\d[\d,]*)\s*(?:\+|or more)?)\s*"
                   r"(?:worker|workmen|workman|employee|staff|people|persons?|head)", ql)
         or re.search(r"(?:establishment|factory|company|unit|firm|office) of (\d[\d,]*)", ql))
    if m:
        n = int(next(g for g in m.groups() if g).replace(",", ""))
        fewer = "or fewer" in m.group(0)
        got["size"] = ("in an establishment employing fewer than 50 workers"
                       if (n < 50 or (fewer and n <= 50))
                       else "in an establishment employing 300 or more workers"
                       if (n >= 300 and not fewer)
                       else "in an establishment employing 50 to 299 workers")
    m = re.search(r"(\d+)\s*(?:\+|plus)?\s*(?:year|yr)", ql)
    if m:
        y = int(m.group(1))
        got["tenure"] = ("with 5 or more years of continuous service" if y >= 5
                         else "with 1 to 5 years of continuous service" if y >= 1
                         else "with under one year of continuous service")
    elif (mm := re.search(r"(\d+)\s*months?", ql)):
        mo = int(mm.group(1))                       # 60 months IS 5 years — bucket by years
        got["tenure"] = ("with 5 or more years of continuous service" if mo >= 60
                         else "with 1 to 5 years of continuous service" if mo >= 12
                         else "with under one year of continuous service")
    elif (dm := re.search(_TENURE_DAYS, ql)):
        # IR Code §66 Expl. 1: 240 days actually worked in the preceding 12 months is
        # deemed ONE YEAR of continuous service — so 240+ days crosses the §70 threshold.
        d = int(next(g for g in dm.groups() if g).replace(",", ""))
        got["tenure"] = ("with 5 or more years of continuous service" if d >= 1825
                         else "with 1 to 5 years of continuous service" if d >= 240
                         else "with under one year of continuous service")
    elif "probation" in ql:
        got["tenure"] = "with under one year of continuous service"
    # Concrete misconduct species map to the misconduct band — but do NOT append the chip's
    # "after an inquiry" tail: the manager never said an inquiry happened, and handing the
    # model a fabricated inquiry flips the verdict. applicability() matches on the
    # "being misconduct" stem, which both phrasings share.
    if re.search(r"(?<!not )(?:misconduct|theft|abscond|insubordinat|disciplin)", ql):
        got["reason"] = "the reason being misconduct"
    elif re.search(r"fixed[\s-]?term", ql):
        got["reason"] = "because a fixed-term contract has come to an end"
    elif re.search(r"redundan|cost[\s-]?cut|restructur|downsiz", ql):
        got["reason"] = "the reason being redundancy or cost-cutting (not misconduct)"
    elif re.search(r"(?:poor|bad|under)[\s-]?perform|performance", ql):
        got["reason"] = "the reason being poor performance"
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
            notes.append("**50–299 workers** — only the general safeguards apply: §70 retrenchment "
                         "notice + compensation and §§67–69 lay-off compensation. The Chapter X "
                         "prior-Government-permission duties (§77, §79) do **not** apply here — they "
                         "begin at 300 workers.")
        elif "fewer than 50" in size:
            notes.append("**Under 50 workers** — lay-off compensation (§§67–69) does **not** apply "
                         "(IR Code §65); §70 retrenchment notice + compensation still apply where the "
                         "worker has a year or more of continuous service. The Chapter X permission "
                         "duties (§77, §79) do **not** apply.")
    if topic_name == "retrench":
        if "under one year" in tenure:
            notes.append("**Under 1 year of service** — the §70 retrenchment safeguards (one month's "
                         "notice + compensation) generally require **one year** of continuous service, "
                         "so they may not be triggered here.")
        if "being misconduct" in reason:            # not the redundancy chip's "(not misconduct)"
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


# ── Related provisions to also check ───────────────────────────────────────────
# Each entry: (chip label, query to submit, code key, provision label it must reach).
# The queries are phrased so the right Code survives routing (distinctive content) and the
# right provision is pinned (explicit Section/Rule where that doesn't hand routing to another
# Code that happens to share the number). cross_ref_checks() gates every one of these in the
# eval, so a corpus change can't silently make a chip point nowhere useful.
_CROSS = {
    "retrench": [
        ("Procedure for retrenchment",
         "Under the Industrial Relations Code, what is the procedure for retrenchment of workers in Section 71?",
         "ir", "Section 71"),
        ("Re-employment of retrenched workers",
         "Must a retrenched worker be given preference for re-employment when the employer hires again, under the Industrial Relations Code?",
         "ir", "Section 72"),
        ("Worker re-skilling fund",
         "Under the Industrial Relations Code, what is the worker re-skilling fund in Section 83?",
         "ir", "Section 83"),
        ("Notice of retrenchment to the Government",
         "Under the Industrial Relations Central Rules, the notice of intended retrenchment to the Government in Rule 33?",
         "ir", "Rule 33"),
    ],
    "closure": [
        ("Notice and process for closure",
         "Under the Industrial Relations Code, the notice and compensation required to close an establishment (Rule 29)?",
         "ir", "Rule 29"),
    ],
    "gratuity": [
        ("Payment & calculation of gratuity",
         "Under the Code on Social Security, the payment of gratuity to an employee under Section 53?",
         "ss", "Section 53"),
    ],
    "maternity": [
        ("Right to maternity benefit",
         "When is a woman entitled to maternity benefit and for what maximum period under the Code on Social Security?",
         "ss", "Section 60"),
        ("Claiming maternity benefit",
         "Under the Code on Social Security, the notice of claim for maternity benefit under Section 62?",
         "ss", "Section 62"),
    ],
}


def cross_refs(topic_name: str):
    """Related provisions for a topic as (label, query) pairs for the UI, or []."""
    return [(lbl, q) for (lbl, q, _c, _s) in _CROSS.get(topic_name, [])]


def cross_ref_checks():
    """(label, query, code_key, provision_label) for every chip — for the routing gate."""
    return [(lbl, q, code, prov)
            for items in _CROSS.values() for (lbl, q, code, prov) in items]
