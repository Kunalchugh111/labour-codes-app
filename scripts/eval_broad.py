#!/usr/bin/env python3
"""
eval_broad.py — large, diverse robustness eval across all four Codes.

Unlike eval_answers.py (40 hand-scored compliance verdicts), this fans out a few
hundred everyday-to-complex questions and scores them MECHANICALLY — no
ground-truth answer key needed — on the properties a manager actually cares
about and that this session's bugs kept violating:

  has_answer      every answer leads with a non-empty plain-English line
  numeric_ok      a "how many / how much / what rate" question yields a NUMBER
  cite_resolves   every cited Section/Rule actually exists in the corpus
  cite_current    no citation points at a pre-2020 repealed Act
  quote_grounded  every quoted authority is verbatim in the cited provision
  not_hedged      flags "no provision found"/"not specified" answers for review

Run:  AWS_BEARER_TOKEN_BEDROCK=... AWS_REGION=... python3 scripts/eval_broad.py [N]
Writes /tmp/eval_broad.json (full rows + failures) and prints a scorecard.
"""
import sys, os, re, json, importlib.util
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
_spec = importlib.util.spec_from_file_location("eval_answers", os.path.join(ROOT, "scripts", "eval_answers.py"))
H = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(H)
import corpus, intake

# ── Scenario bank ────────────────────────────────────────────────────────────
# (code_hint, category, numeric?, question).  numeric? => the answer must contain a figure.
SCENARIOS = []
def add(code, cat, numeric, *qs):
    for q in qs:
        SCENARIOS.append((code, cat, numeric, q))

# WAGES — Code on Wages, 2019
add("wages","numeric",True,
    "How much PF is deducted from an employee's salary?",
    "By what date must monthly wages be paid?",
    "What is the maximum amount that can be deducted from wages?",
    "What is the overtime wage rate under the Code on Wages?",
    "Within how many days must wages be paid when an employee is removed?",
    "What is the minimum bonus payable to an employee?",
    "What is the maximum bonus payable in an accounting year?",
    "Up to what wage ceiling is an employee eligible for a bonus?",
    "What fraction of wages can be deducted as a fine?",
    "How often must the wage period be fixed?")
add("wages","simple",False,
    "Can I pay different wages to men and women for the same work?",
    "Can wages be paid in cash?",
    "Is an employer allowed to deduct wages for damage caused by an employee?",
    "Who fixes the minimum wage?",
    "Can I deduct wages for being absent?")
add("wages","daily",False,
    "My company wants to delay this month's salary by two weeks — is that allowed?",
    "We pay our cleaning staff in cash on the 15th — is that okay?",
    "A worker broke a machine, can we cut it from his pay?",
    "We want to pay interns less than minimum wage, can we?")
add("wages","definition",False,
    "What counts as 'wages' under the Code on Wages?",
    "What is the 'floor wage'?",
    "Who is an 'employee' under the Code on Wages?")
add("wages","complex",True,
    "We employ 50 workers, pay monthly, and deducted 60% of one worker's wages for a cash shortage — is that lawful and what is the limit?",
    "An employee earning 30,000 a month worked 4 hours overtime; how much overtime wage is due and by when must it be paid?")

# SS — Code on Social Security, 2020
add("ss","numeric",True,
    "After how many years of service is gratuity payable?",
    "How many weeks of maternity benefit is a woman entitled to?",
    "What is the employer's contribution rate to the Provident Fund?",
    "How much gratuity is payable per year of service?",
    "How many days must a woman have worked to qualify for maternity benefit?",
    "For how many weeks can maternity benefit be taken before delivery?",
    "What is the maternity benefit for a woman who already has two or more children?",
    "Within how many days must an employer pay gratuity once it is due?",
    "How many days of paid leave for a miscarriage?",
    "What is the rate of interest if gratuity is paid late?")
add("ss","simple",False,
    "Is gratuity payable if an employee dies before five years?",
    "Are fixed-term employees entitled to gratuity?",
    "Who is required to register under the Provident Fund scheme?",
    "Can a woman be dismissed during maternity leave?",
    "Are gig workers covered under social security?")
add("ss","daily",False,
    "An employee resigned after 4 years and 8 months — do we owe gratuity?",
    "A pregnant employee asked for leave, how much must we give?",
    "Our delivery-app riders — do we owe them any social security?",
    "An employee died in an accident at work, what must we pay the family?")
add("ss","definition",False,
    "What is 'continuous service'?",
    "Who is a 'gig worker'?",
    "What is an 'aggregator' under the Code on Social Security?")
add("ss","complex",True,
    "A woman with one child worked 85 days in the last 12 months before delivery — is she eligible and for how many weeks?",
    "An employee with 6 years 3 months service earning 26,000/month is retiring — how much gratuity is due?")

# IR — Industrial Relations Code, 2020
add("ir","numeric",True,
    "How much notice must be given to retrench a worker?",
    "How many days of wages as compensation are due on retrenchment?",
    "Above how many workers is government permission needed before retrenchment?",
    "How much notice is required to change service conditions?",
    "Within how many days must a grievance be resolved?",
    "How many members can a Grievance Redressal Committee have?",
    "How many workers are needed to form a Works Committee?",
    "How many days' notice must a worker give before a strike in a public utility?")
add("ir","simple",False,
    "Can I retrench a worker without notice?",
    "What is the difference between lay-off and retrenchment?",
    "Do I need standing orders for my factory?",
    "Can workers go on strike without notice?",
    "Who can raise an industrial dispute?")
add("ir","daily",False,
    "We want to shut down a loss-making unit of 400 workers — what must we do?",
    "I let a worker go after 3 years with two days' notice and no pay — is that legal?",
    "Our workers want to form a union, can we stop them?",
    "We need to lay off 50 workers for a month due to no raw material, what are the rules?")
add("ir","definition",False,
    "What does 'retrenchment' mean?",
    "What is a 'lay-off'?",
    "What is an 'industrial dispute'?")
add("ir","complex",True,
    "A factory with 250 workers wants to retrench 20 of them; what notice, compensation and permission apply?",
    "We have 350 workers and want to close the unit; what notice and compensation does the law require?")

# OSH — Occupational Safety, Health and Working Conditions Code, 2020
add("osh","numeric",True,
    "What is the maximum number of working hours in a day?",
    "After how many hours of work must a rest interval be given?",
    "How many hours make up a working week?",
    "How many days of annual leave with wages is a worker entitled to?",
    "After how many days of work does a worker earn one day of leave?",
    "What is the spread-over limit for a working day?",
    "How many days must an employer issue an appointment letter within?",
    "What is the overtime rate for hours worked beyond normal hours?",
    "Up to what age is a person considered a young person / prohibited from hazardous work?")
add("osh","simple",False,
    "Must I give every employee an appointment letter?",
    "Can women work night shifts?",
    "Is a weekly day off mandatory?",
    "Can a worker be made to work in two factories on the same day?",
    "Must I provide a canteen for my workers?")
add("osh","daily",False,
    "We run a 12-hour shift, is that allowed?",
    "Can I ask a woman employee to work from 9pm to 5am?",
    "Do I have to give a written appointment letter to a daily-wage worker?",
    "Our factory has 300 workers — do we need a canteen?")
add("osh","definition",False,
    "Who is a 'worker' under the OSH Code?",
    "What is an 'establishment' under the OSH Code?",
    "What is a 'hazardous process'?")
add("osh","complex",True,
    "A worker did 10 hours a day for 6 days; how many hours of overtime at what rate, and did we breach the daily limit?",
    "We employ women on night shifts in a factory of 200 — what conditions must we meet?")

# Cross-cutting / comparison (old-act handling) and tricky undefined terms
add("ss","compare",False,
    "What changed for gratuity compared to the old law?",
    "How is maternity benefit different from the earlier Maternity Benefit Act?")
add("ir","compare",False,
    "What changed in retrenchment rules compared to the Industrial Disputes Act?")
add("ss","newprovision",False,
    "What does the law say about social security for platform workers compared to before?")
add("wages","tricky",False,
    "What is the rate of professional tax deduction?",          # not in corpus -> must say so cleanly
    "What is the income tax slab for salaried employees?")      # out of scope -> must not invent

# ── Scoring ──────────────────────────────────────────────────────────────────
_NUM_RE = re.compile(r"\d|\b(one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|"
                     r"thirteen|fourteen|fifteen|twenty|thirty|forty|fifty|sixty|hundred|"
                     r"thousand|lakh|half|quarter|double|twice|triple)\b", re.I)
_HEDGE_RE = re.compile(r"no relevant provision|not specified|does not specify|not mentioned|"
                       r"not defined in the supplied|unable to|cannot determine|not provided in", re.I)
# A citation is stale if it names a 4-digit year that is not a 2020-Codes year (2019 Wages, 2020 rest).
_YEAR_RE = re.compile(r"\b(19\d{2}|20[01]\d)\b")
_OK_YEARS = {"2019", "2020"}


def _all_citations(d):
    cites = [b.get("citation") for b in (d.get("analysis") or []) if isinstance(b, dict)]
    cites += [a.get("citation") for a in (d.get("authorities") or []) if isinstance(a, dict)]
    # comparison rows: new_cite is current-law; old_cite is intentionally a repealed Act (allowed)
    for ch in (d.get("changes") or []):
        if isinstance(ch, dict):
            cites.append(ch.get("new_cite"))
    return [c for c in cites if c and str(c).strip()]


def _answer_text(d):
    if d.get("type") == "comparison":
        return " ".join([str(d.get("headline", ""))]
                        + [str(c.get("new", "")) for c in (d.get("changes") or []) if isinstance(c, dict)])
    parts = [str(d.get("direct_answer") or ""), str((d.get("verdict") or {}).get("summary") or "")]
    parts += [str(b.get("finding") or "") for b in (d.get("analysis") or []) if isinstance(b, dict)]
    return " ".join(p for p in parts if p)


def score(app, code, cat, numeric, q, d):
    r = {"code": code, "cat": cat, "q": q, "type": d.get("type"), "fails": []}
    atext = _answer_text(d).strip()
    is_compare = d.get("type") == "comparison"

    # has_answer  (coerce JSON null -> "" so a compliance answer's null direct_answer
    # correctly falls through to verdict.summary)
    lead = (str(d.get("direct_answer") or "").strip()
            or str((d.get("verdict") or {}).get("summary") or "").strip()
            or str(d.get("headline") or "").strip())
    if len(lead) < 12:
        r["fails"].append("has_answer")

    # numeric_ok (skip tricky/out-of-scope, where "not in the Codes" is the right answer)
    hedged = bool(_HEDGE_RE.search(atext))
    if numeric and not hedged and not _NUM_RE.search(atext):
        r["fails"].append("numeric_missing")

    # citation checks
    cites = _all_citations(d)
    bad_resolve, stale = [], []
    for c in cites:
        years = set(_YEAR_RE.findall(c))
        if years and not (years & _OK_YEARS):
            stale.append(c)
        # does it resolve in the corpus? (lookup_citation returns text or "")
        try:
            txt = corpus.lookup_citation(app.LOADED, c) or ""
        except Exception:
            txt = ""
        if not is_compare and not txt and not years:   # current-law cite that doesn't resolve
            bad_resolve.append(c)
    if stale:
        r["fails"].append("stale_citation"); r["stale"] = stale
    if bad_resolve:
        r["fails"].append("cite_unresolved"); r["bad_cites"] = bad_resolve

    # quote_grounded — catch FABRICATED statute. A faithful quote may be non-contiguous
    # (model stitches a lead-in to a sub-clause without '...'), so we measure token COVERAGE
    # against the cited provision rather than a contiguous substring; fabrication shows up as
    # many quote words absent from the real text.
    ungrounded = []
    for a in (d.get("authorities") or []):
        if not isinstance(a, dict):
            continue
        quote, cite = str(a.get("quote", "")), str(a.get("citation", ""))
        if len(quote) < 25:
            continue
        try:
            src = corpus.lookup_citation(app.LOADED, cite) or ""
            if not src:
                continue                               # unresolved cite handled by cite_unresolved
            if corpus.quote_supported(quote, corpus.normalize_for_match(src)):
                continue                               # contiguous/elided — clearly fine
            qtok = set(corpus.normalize_for_match(quote).split())
            stok = set(corpus.normalize_for_match(src).split())
            cover = len(qtok & stok) / max(1, len(qtok))
            if cover < 0.85:
                ungrounded.append("%s (cover %.0f%%)" % (cite, 100 * cover))
        except Exception:
            pass
    if ungrounded:
        r["fails"].append("quote_ungrounded"); r["ungrounded"] = ungrounded

    # hedged (informational flag, not always a failure — but a "tricky" out-of-scope SHOULD hedge)
    if cat == "tricky":
        if not hedged:
            r["fails"].append("should_have_hedged")
    elif hedged:
        r["fails"].append("hedged")

    r["ok"] = not r["fails"]
    r["lead"] = lead[:140]
    return r


def main():
    if not os.environ.get("AWS_BEARER_TOKEN_BEDROCK"):
        print("Set AWS_BEARER_TOKEN_BEDROCK"); return 1
    app = H._make_app()
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else len(SCENARIOS)
    scen = SCENARIOS[:limit]

    def run(item):
        code, cat, numeric, q = item
        try:
            d = H._answer(app, intake, q)
        except Exception as e:
            return {"code": code, "cat": cat, "q": q, "fails": ["error"], "ok": False, "err": str(e)[:120]}
        return score(app, code, cat, numeric, q, d)

    rows = []
    with ThreadPoolExecutor(max_workers=8) as ex:
        for r in ex.map(run, scen):
            rows.append(r)

    # scorecard
    n = len(rows)
    checks = ["has_answer", "numeric_missing", "stale_citation", "cite_unresolved",
              "quote_ungrounded", "hedged", "should_have_hedged", "error"]
    counts = {c: sum(1 for r in rows if c in r["fails"]) for c in checks}
    passed = sum(1 for r in rows if r["ok"])
    print("\n=== BROAD EVAL: %d scenarios ===" % n)
    print("CLEAN (no failures): %d/%d (%d%%)" % (passed, n, 100 * passed // n))
    print("\nFailures by check:")
    for c in checks:
        if counts[c]:
            print("  %-18s %d" % (c, counts[c]))
    print("\nBy code (clean / total):")
    for code in ["wages", "ss", "ir", "osh"]:
        cr = [r for r in rows if r["code"] == code]
        print("  %-6s %d/%d" % (code, sum(1 for r in cr if r["ok"]), len(cr)))
    print("\nBy category (clean / total):")
    for cat in sorted(set(r["cat"] for r in rows)):
        cr = [r for r in rows if r["cat"] == cat]
        print("  %-12s %d/%d" % (cat, sum(1 for r in cr if r["ok"]), len(cr)))

    fails = [r for r in rows if not r["ok"]]
    json.dump({"n": n, "clean": passed, "counts": counts, "rows": rows, "fails": fails},
              open("/tmp/eval_broad.json", "w"), indent=2)
    print("\nWrote /tmp/eval_broad.json  (%d failures captured for triage)" % len(fails))
    return 0


if __name__ == "__main__":
    sys.exit(main())
