#!/usr/bin/env python3
"""
test_calculators_new.py — pin the NEW deterministic statutory notes (bonus range,
annual leave, final-wages deadline, gratuity payment deadline, maternity branches)
and the intake.py fact-extraction fixes. Same conventions as test_calculators.py:
pure unit tests, no model, no network.

Run:  python3 tests/test_calculators_new.py
  or: pytest tests/test_calculators_new.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app     # noqa: E402
import intake  # noqa: E402


def _note(query, heading):
    for h, b in app._amount_notes(query):
        if h == heading:
            return b
    return ""


# ── annual bonus (Wages Code §26(1): min 8⅓% or ₹100; §26(3)/(5): max 20%) ────
def test_bonus_range():
    b = _note("how much annual bonus must I pay a worker earning 20,000 per month?",
              "ANNUAL BONUS RANGE")
    assert "₹20,000" in b        # minimum = 8⅓% of 2,40,000 = one month's wage
    assert "₹48,000" in b        # maximum = 20% of 2,40,000
    assert "8 months" in b       # §39(1) payment deadline rides along
    assert "notification" in b   # eligibility/calculation ceilings are delegated — disclosed

def test_bonus_guards():
    assert _note("what is the minimum bonus percentage?", "ANNUAL BONUS RANGE") == ""  # no wage
    assert _note("can I recover the joining bonus of 50,000 per month hire?",
                 "ANNUAL BONUS RANGE") == ""                       # joining bonus ≠ §26 bonus


# ── annual leave (OSH §32(1): 180-day gate, 1 day per 20 days worked) ─────────
def test_leave_accrual():
    b = _note("a worker worked 240 days this year; how much annual leave has he earned?",
              "ANNUAL LEAVE ENTITLEMENT")
    assert "12 days" in b and "20 days" in b
    b2 = _note("leave entitlement for a worker who worked 300 days", "ANNUAL LEAVE ENTITLEMENT")
    assert "15 days" in b2

def test_leave_180_day_gate():
    b = _note("he worked 100 days; is he entitled to annual leave?", "ANNUAL LEAVE ENTITLEMENT")
    assert "NOT" in b and "180" in b     # below the §32(1)(i) threshold — say so
    # mid-year joiners' one-fourth exception must be disclosed, not silently dropped
    assert "one-fourth" in b

def test_leave_guards():
    assert _note("how is annual leave calculated?", "ANNUAL LEAVE ENTITLEMENT") == ""  # no days
    assert _note("worked 240 days, maternity leave query", "ANNUAL LEAVE ENTITLEMENT") == ""


# ── final wages (Wages Code §17(2): two working days after termination) ───────
def test_final_wages_deadline():
    b = _note("when must I pay the final wages of a worker I dismissed?", "FINAL WAGES DEADLINE")
    assert "TWO WORKING DAYS" in b
    assert "FINAL WAGES DEADLINE" == [h for h, _ in app._amount_notes(
        "a worker resigned; what is the time limit for full and final settlement?")][0]

def test_final_wages_guards():
    # bare wage-timing question with no termination event must NOT fire (§17(1) territory)
    assert _note("When must wages be paid?", "FINAL WAGES DEADLINE") == ""
    assert _note("What is retrenchment?", "FINAL WAGES DEADLINE") == ""


# ── gratuity deadline (SS §56(3): 30 days; §56(4): interest, rate notified) ───
def test_gratuity_deadline():
    b = _note("gratuity has not been paid 3 months after retirement — what now?",
              "GRATUITY PAYMENT DEADLINE")
    assert "THIRTY DAYS" in b and "interest" in b
    assert _note("how is gratuity calculated?", "GRATUITY PAYMENT DEADLINE") == ""


# ── maternity branches (SS §60(3) provisos, §60(4), §60(2) 80-day gate) ───────
def test_maternity_two_children_branch():
    b = _note("our employee is pregnant and already has two children; how many weeks off?",
              "MATERNITY BENEFIT PERIOD")
    assert "TWELVE" in b and "26" in b      # states 12, and warns off the general 26

def test_maternity_adoption_branch():
    b = _note("an employee is adopting a two-month-old baby; what leave does she get?",
              "MATERNITY BENEFIT PERIOD")
    assert "TWELVE" in b and "three months" in b and "handed over" in b

def test_maternity_80_day_gate():
    hi = _note("she is pregnant and worked 120 days in the last year — maternity benefit?",
               "MATERNITY ELIGIBILITY (80 DAYS)")
    lo = _note("she is pregnant but worked only 60 days with us — maternity benefit?",
               "MATERNITY ELIGIBILITY (80 DAYS)")
    assert "crosses" in hi and "does NOT cross" in lo

def test_maternity_no_spurious():
    # the general 26-week question must stay note-free (retrieval handles it)
    assert app._amount_notes("How many weeks of maternity leave?") == []


# ── intake.py fact extraction: recognized ⇒ extracted, correct buckets ────────
def test_months_bucketing():
    assert "5 or more" in intake.facts_from_query("worked 60 months")["tenure"]
    assert "5 or more" in intake.facts_from_query("worked 72 months")["tenure"]
    assert "1 to 5"    in intake.facts_from_query("worked 59 months")["tenure"]
    assert "under one" in intake.facts_from_query("worked 6 months")["tenure"]

def test_days_tenure():
    # IR Code §66 Expl.1: 240 days deemed one year of continuous service
    assert "1 to 5"    in intake.facts_from_query("retrench after 240 days of service")["tenure"]
    assert "under one" in intake.facts_from_query("he worked 200 days")["tenure"]
    # "laid off for 15 days" is NOT tenure — screen() must still ask
    assert "tenure" not in intake.facts_from_query("laid off a worker for 15 days")
    assert not intake._TENURE_RE.search("laid off a worker for 15 days")

def test_size_phrasings():
    f = intake.facts_from_query
    assert "300 or more"   in f("we are a factory of 400 and want to retrench")["size"]
    assert "50 to 299"     in f("retrench in a unit of 220 due to losses")["size"]
    assert "300 or more"   in f("we have 400 head and want to retrench")["size"]
    assert "fewer than 50" in f("we employ 40 or fewer workers")["size"]
    # "300 or fewer" is band-ambiguous: neither recognized nor extracted -> screen() asks
    assert "size" not in f("we employ 300 or fewer workers")
    assert not intake._SIZE_RE.search("we employ 300 or fewer workers")

def test_reason_phrasings():
    f = intake.facts_from_query
    assert "misconduct"  in f("dismissed him for theft, is that legal")["reason"]
    assert "after an inquiry" not in f("dismissed him for theft, is that legal")["reason"]
    assert "misconduct"  in f("terminate for absconding, we employ 100 workers")["reason"]
    assert "redundancy"  in f("terminate for redundancy, we employ 100 workers")["reason"]
    assert "performance" in f("terminate for poor performance, 100 workers")["reason"]
    assert "reason" not in f("it was redundancy, not misconduct") or \
           "redundancy" in f("it was redundancy, not misconduct")["reason"]

def test_recognized_implies_extracted():
    """Every phrasing _PRESENT treats as 'fact already stated' must yield a band, so
    applicability() never goes silent on a fact screen() declined to ask about."""
    cases = [("tenure", "worked 60 months"), ("tenure", "500 days of service"),
             ("size", "a factory of 400"), ("size", "we have 400 head, retrenching"),
             ("size", "employ 40 or fewer workers"),
             ("reason", "dismissed for theft"), ("reason", "poor performance dismissal")]
    for key, q in cases:
        if intake._PRESENT[key](q.lower()):
            assert key in intake.facts_from_query(q), (key, q)

def test_applicability_wiring():
    # the extracted bands must drive the downstream notes verbatim
    got = intake.facts_from_query("retrench a worker of 60 months in a factory of 400")
    notes = " ".join(intake.applicability("retrench", got))
    assert "300+ workers" in notes and "§77" in notes


def _main():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = failed = 0
    for fn in fns:
        try:
            fn(); passed += 1; print("ok   %s" % fn.__name__)
        except AssertionError as e:
            failed += 1; print("FAIL %s  %s" % (fn.__name__, e))
        except Exception as e:
            failed += 1; print("ERR  %s  %r" % (fn.__name__, e))
    print("\n%d passed, %d failed" % (passed, failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(_main())
