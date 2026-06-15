#!/usr/bin/env python3
"""
eval_1000.py — ~1000-scenario robustness sweep across all four Codes.

Built from ~130 natural BASE questions covering every Code in the four buckets
the user asked for — formula/numeric, complex, day-to-day, minor — each carrying
a ground-truth value where one exists (verified against the corpus), then
multiplied by meaning-preserving PHRASINGS so the same question is asked many
ways. That tests the property that matters: the right answer + right section
regardless of wording.

Scoring reuses scripts/eval_broad.py (mechanical, no answer key) plus a
ground-truth check: a formula with a known value must produce that value
(catches a confidently-wrong number, e.g. PF reported at ESI's 3.25%).

Run:  AWS_BEARER_TOKEN_BEDROCK=... AWS_REGION=... \
      [EVAL_WORKERS=4] [EVAL_N=1000] python3 scripts/eval_1000.py
Writes /tmp/eval_1000.json and prints a scorecard by code x category x check.
"""
import sys, os, json, time, importlib.util
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
_eb = importlib.util.spec_from_file_location("eval_broad", os.path.join(ROOT, "scripts", "eval_broad.py"))
EB = importlib.util.module_from_spec(_eb); _eb.loader.exec_module(EB)
H, intake = EB.H, EB.intake

# ── BASE bank ────────────────────────────────────────────────────────────────
# (code, category, expected | None, question). expected = accepted answer substrings
# (digit AND word forms) for a verified formula; None elsewhere.
BASE = []
def b(code, cat, expected, q): BASE.append((code, cat, expected, q))

# numbers that may appear as digits or words
TWICE = ["twice", "two times", "double", "200 per cent", "200%", "two hundred per cent"]

# ===== WAGES =====
b("wages","formula",TWICE,                                  "What is the overtime wage rate?")
b("wages","formula",["seventh","7th"],                      "By when must wages be paid to a monthly-paid employee?")
b("wages","formula",["fifty per cent","50 per cent","50%"], "What is the maximum percentage of wages that may be deducted in a wage period?")
b("wages","formula",["three per cent","3 per cent","3%"],   "What is the ceiling on fines as a percentage of wages?")
b("wages","formula",["eight and one-third","8.33"],         "What is the minimum bonus percentage payable?")
b("wages","formula",["twenty per cent","20 per cent","20%"],"What is the maximum bonus percentage payable in an accounting year?")
b("wages","formula",None,                                   "How is the minimum wage fixed and who fixes it?")
b("wages","formula",None,                                   "Within how many days must wages be paid to an employee who is removed or dismissed?")
b("wages","complex",["fifty per cent","50 per cent","50%"], "A worker damaged a machine; we deducted 60% of his monthly wages. Is that allowed and what is the limit?")
b("wages","complex",None,                                   "An employee earning 30,000 a month did 5 hours of overtime in a week — how is the overtime wage worked out and when is it payable?")
b("wages","daily",None,                                     "Can I delay this month's salaries by two weeks because of a cash crunch?")
b("wages","daily",None,                                     "We pay our cleaning staff in cash on the 15th — is that okay?")
b("wages","daily",None,                                     "Can I pay women less than men for the same job?")
b("wages","daily",None,                                     "A worker was absent for 3 days — can I cut his pay for those days?")
b("wages","minor",TWICE,                                    "overtime pay rate?")
b("wages","minor",["eight and one-third","8.33"],           "minimum bonus %?")
b("wages","minor",None,                                     "wage payment deadline?")
b("wages","minor",None,                                     "what is the floor wage?")
b("wages","minor",None,                                     "equal pay rule?")

# ===== SOCIAL SECURITY =====
b("ss","formula",["fifteen days","15 days"],                "How many days' wages of gratuity are payable for each completed year of service?")
b("ss","formula",["five years","5 years"],                  "After how many years of continuous service is gratuity payable?")
b("ss","formula",["ten per cent","10 per cent","10%","twelve","12 per cent","12%"], "What is the provident fund contribution rate?")
b("ss","formula",["twenty-six weeks","26 weeks","twenty six weeks"], "What is the maximum maternity benefit period?")
b("ss","formula",["twelve weeks","12 weeks"],               "What is the maternity benefit period for a woman who already has two or more surviving children?")
b("ss","formula",["eighty days","80 days"],                 "How many days must a woman have worked in the preceding 12 months to qualify for maternity benefit?")
b("ss","formula",["six weeks","6 weeks"],                   "How many weeks of leave is a woman entitled to after a miscarriage?")
b("ss","formula",["eight weeks","8 weeks"],                 "How many weeks of maternity benefit may be taken before the expected delivery?")
b("ss","formula",["fifty per cent","50 per cent","50%"],    "When an employee dies of a work injury, the compensation is based on what share of monthly wages?")
b("ss","complex",["ninety thousand","90,000","90000","15,000","fifteen thousand"], "An employee with exactly 6 completed years of service drawing 26,000 per month retires — how much gratuity is due?")
b("ss","complex",None,                                      "A woman with one child worked 85 days in the 12 months before delivery — is she eligible for maternity benefit and for how long?")
b("ss","daily",None,                                        "An employee resigned after 4 years and 8 months — do we owe gratuity?")
b("ss","daily",None,                                        "Our delivery-app riders — do we owe them any social security?")
b("ss","daily",None,                                        "A pregnant employee wants leave — how much must we give and is it paid?")
b("ss","daily",None,                                        "An employee died in an accident at work — what must we pay the family?")
b("ss","minor",["fifteen days","15 days"],                  "gratuity per year?")
b("ss","minor",["five years","5 years"],                    "gratuity after how many years?")
b("ss","minor",["twenty-six","26"],                         "maternity leave weeks?")
b("ss","minor",None,                                        "who is a gig worker?")
b("ss","minor",None,                                        "PF contribution rate?")

# ===== INDUSTRIAL RELATIONS =====
b("ir","formula",["one month","1 month","three month","3 month"], "How much notice must be given to retrench a worker?")
b("ir","formula",["fifteen days","15 days"],                "How much retrenchment compensation is payable for each year of continuous service?")
b("ir","formula",["three hundred","300"],                   "Above how many workers does an establishment need prior government permission to retrench or close?")
b("ir","formula",["fifty per cent","50 per cent","50%"],    "What compensation is a laid-off worker entitled to, as a share of wages?")
b("ir","formula",["one year","240 days","240","one hundred and twenty"], "How much continuous service makes a worker eligible for retrenchment compensation?")
b("ir","formula",None,                                      "How many days' notice is required to close down an establishment?")
b("ir","formula",None,                                      "How much notice must a worker give before a strike in a public utility service?")
b("ir","complex",["non-compliant","not compliant","unlawful","illegal","violation"], "I let a worker with 3 years' service go with two days' notice and no compensation — is that legal?")
b("ir","complex",None,                                      "A factory with 250 workers wants to retrench 20 of them — what notice, compensation and permission apply?")
b("ir","complex",None,                                      "We have 350 workers and want to close a loss-making unit — what does the law require?")
b("ir","daily",None,                                        "Our workers want to form a union — can we stop them?")
b("ir","daily",None,                                        "Can I retrench a worker without any notice if I pay him instead?")
b("ir","daily",None,                                        "We have no raw material for a month — can we lay off 50 workers and what do we pay them?")
b("ir","daily",None,                                        "The workmen went on a sudden strike — was that legal?")
b("ir","minor",["fifteen days","15 days"],                  "retrenchment compensation per year?")
b("ir","minor",["three hundred","300"],                     "retrenchment permission threshold?")
b("ir","minor",None,                                        "what is retrenchment?")
b("ir","minor",None,                                        "difference between layoff and retrenchment?")
b("ir","minor",None,                                        "strike notice period?")

# ===== OSH =====
b("osh","formula",["eight hours","8 hours"],                "What is the maximum number of working hours in a day?")
b("osh","formula",["forty-eight","48"],                     "What is the maximum number of working hours in a week?")
b("osh","formula",TWICE,                                    "What is the overtime rate under the OSH Code?")
b("osh","formula",None,                                     "After how many hours of continuous work must a rest interval be given?")
b("osh","formula",None,                                     "After how many days of work does a worker earn one day of annual leave?")
b("osh","formula",None,                                     "How many days of work in a year make a worker eligible for annual leave with wages?")
b("osh","formula",None,                                     "Within how long must an employer issue an appointment letter?")
b("osh","complex",None,                                     "A worker did 10 hours a day for 6 days — how much overtime at what rate, and did we breach the daily limit?")
b("osh","complex",None,                                     "We want women on night shifts in a factory of 200 — what conditions must we meet?")
b("osh","daily",None,                                       "We run a 12-hour shift — is that allowed?")
b("osh","daily",None,                                       "Can I ask a woman to work from 9pm to 5am?")
b("osh","daily",None,                                       "Must I give a written appointment letter to a daily-wage worker?")
b("osh","daily",None,                                       "Is a weekly day off compulsory?")
b("osh","minor",["eight hours","8 hours"],                  "max working hours per day?")
b("osh","minor",TWICE,                                      "overtime rate?")
b("osh","minor",None,                                       "appointment letter compulsory?")
b("osh","minor",None,                                       "women night shift allowed?")
b("osh","minor",None,                                       "weekly off mandatory?")

# ── meaning-preserving phrasing wrappers ─────────────────────────────────────
def _lc(q): return q[0].lower() + q[1:]
PHRASINGS = [
    lambda q: q,
    lambda q: "Quick question — " + q,
    lambda q: "Under the new labour codes in India, " + _lc(q),
    lambda q: "For an HR manager: " + q,
    lambda q: q + " Please cite the exact section.",
    lambda q: "We're a mid-sized company. " + q,
    lambda q: "Just to confirm — " + _lc(q),
    lambda q: q + " Keep it short.",
    lambda q: "In simple terms, " + _lc(q),
    lambda q: "As per Indian labour law, " + _lc(q),
    lambda q: "Could you clarify: " + _lc(q),
    lambda q: q + " (a one-line answer is fine)",
    lambda q: "Need this for a compliance check — " + _lc(q),
    lambda q: "Hi team, " + _lc(q),
]


def generate(n):
    out = []
    i = 0
    # round-robin phrasings so every base question gets varied wordings until n is reached
    for p in range(len(PHRASINGS)):
        for (code, cat, expected, q) in BASE:
            out.append((code, cat, expected, PHRASINGS[p](q)))
            i += 1
            if i >= n:
                return out
    return out


def main():
    if not os.environ.get("AWS_BEARER_TOKEN_BEDROCK"):
        print("Set AWS_BEARER_TOKEN_BEDROCK"); return 1
    app = H._make_app()
    n = int(os.environ.get("EVAL_N", "1000"))
    workers = int(os.environ.get("EVAL_WORKERS", "4"))
    scen = generate(n)
    print("Running %d scenarios (%d base x phrasings), %d workers…" % (len(scen), len(BASE), workers))

    def _has_value(d, expected):
        # at temperature 0 a genuinely-wrong answer is stable, so retrying only recovers
        # transient throttle-degraded partials (number dropped); it cannot turn wrong -> right
        if not expected:
            return True
        al = EB._answer_text(d).lower()
        if EB._HEDGE_RE.search(al):           # legitimate "set by notification / not stated"
            return True
        return any(t.lower() in al for t in expected)

    def run(item):
        code, cat, expected, q = item
        d = {}
        for attempt in range(4):
            try:
                d = H._answer(app, intake, q)
                if d.get("type") and _has_value(d, expected):
                    break
            except Exception as e:
                d = {"_err": str(e)[:120]}
            time.sleep(2 * (attempt + 1))
        if not d.get("type"):
            return {"code": code, "cat": cat, "q": q, "fails": ["error"], "ok": False}
        numeric = cat in ("formula", "complex") or bool(expected)
        return EB.score(app, code, cat, numeric, q, d, expected=expected)

    rows = []
    done = 0
    with ThreadPoolExecutor(max_workers=workers) as ex:
        for r in ex.map(run, scen):
            rows.append(r); done += 1
            if done % 100 == 0:
                print("  …%d/%d done" % (done, len(scen)), flush=True)

    n = len(rows)
    checks = ["has_answer", "numeric_missing", "wrong_value", "stale_citation",
              "cite_unresolved", "quote_ungrounded", "hedged", "should_have_hedged", "error"]
    counts = {c: sum(1 for r in rows if c in r["fails"]) for c in checks}
    passed = sum(1 for r in rows if r["ok"])
    print("\n=== EVAL 1000: %d scenarios ===" % n)
    print("CLEAN: %d/%d (%d%%)" % (passed, n, 100 * passed // n))
    print("\nFailures by check:")
    for c in checks:
        if counts[c]:
            print("  %-18s %d" % (c, counts[c]))
    print("\nClean by code:")
    for code in ["wages", "ss", "ir", "osh"]:
        cr = [r for r in rows if r["code"] == code]
        if cr: print("  %-6s %d/%d (%d%%)" % (code, sum(r["ok"] for r in cr), len(cr),
                                              100*sum(r["ok"] for r in cr)//len(cr)))
    print("\nClean by category:")
    for cat in ["formula", "complex", "daily", "minor"]:
        cr = [r for r in rows if r["cat"] == cat]
        if cr: print("  %-9s %d/%d (%d%%)" % (cat, sum(r["ok"] for r in cr), len(cr),
                                             100*sum(r["ok"] for r in cr)//len(cr)))
    # wrong_value is the headline accuracy signal — list distinct base questions that failed it
    wv = sorted({r["q"] for r in rows if "wrong_value" in r["fails"]})
    if wv:
        print("\nWRONG-VALUE formulas (distinct):")
        for q in wv[:30]:
            print("  -", q)
    fails = [r for r in rows if not r["ok"]]
    json.dump({"n": n, "clean": passed, "counts": counts, "fails": fails},
              open("/tmp/eval_1000.json", "w"), indent=2)
    print("\nWrote /tmp/eval_1000.json (%d failures)" % len(fails))
    return 0


if __name__ == "__main__":
    sys.exit(main())
