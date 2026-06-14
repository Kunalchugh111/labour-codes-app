#!/usr/bin/env python3
"""
test_calculators.py — pin the deterministic statutory amount calculators.

These compute rupee figures that the app states AS LAW (gratuity, retrenchment,
lay-off, overtime), so a silent regression here is serious. Pure unit tests: no
model, no network, no credentials — just app._parse_tenure_wage / gratuity_estimate
/ _amount_notes against hand-checked statutory values.

Run:  python3 tests/test_calculators.py      (plain, prints PASS/FAIL, exits 1 on failure)
  or: pytest tests/test_calculators.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app  # noqa: E402


def _note(query, heading):
    """The body of the calc note with the given heading, or '' if not produced."""
    for h, b in app._amount_notes(query):
        if h == heading:
            return b
    return ""


# ── tenure + wage parsing ────────────────────────────────────────────────────
def test_parse_tenure_wage():
    assert app._parse_tenure_wage("6 completed years drawing 26000 per month") == (6, 0, 26000)
    assert app._parse_tenure_wage("4 years 8 months at 13000 per month") == (4, 8, 13000)
    assert app._parse_tenure_wage("salary of 30000 for 10 years") == (10, 0, 30000)
    assert app._parse_tenure_wage("5 years of service") is None          # no wage
    assert app._parse_tenure_wage("earning 25000 per month") is None       # no years
    assert app._parse_tenure_wage("3 years at 200 per month") is None      # wage too low


# ── gratuity (§53(2): monthly ÷ 26 × 15 per completed year) ───────────────────
def test_gratuity_amounts():
    assert app.gratuity_estimate("gratuity for 6 years at 26,000 per month")["amount"] == 90000
    assert app.gratuity_estimate("gratuity for 5 years at 20,000 per month")["amount"] == 57692
    assert app.gratuity_estimate("gratuity for 10 years salary 50000")["amount"] == 288462

def test_gratuity_part_year_rounding():
    # part-year over six months counts as a full year; exactly six months does not
    assert app.gratuity_estimate("gratuity 4 years 8 months at 13000 per month")["eff"] == 5
    assert app.gratuity_estimate("gratuity 4 years 7 months at 13000 per month")["eff"] == 5
    assert app.gratuity_estimate("gratuity 4 years 6 months at 13000 per month")["eff"] == 4

def test_gratuity_guards():
    assert app.gratuity_estimate("how much notice to retrench a worker?") is None  # not gratuity
    assert app.gratuity_estimate("what is gratuity?") is None                      # no numbers
    assert app.gratuity_estimate("gratuity after how many years?") is None          # no wage


# ── retrenchment (§70: 1 month notice + 15 days' avg pay per yr, 26-day basis) ─
def test_retrenchment_dues():
    b = _note("I am retrenching a worker with 5 years at 20,000 per month", "RETRENCHMENT DUES")
    assert "₹57,692" in b      # compensation
    assert "₹77,692" in b      # total incl. one month's wages in lieu
    b2 = _note("retrenched a worker with 10 years service salary 30000", "RETRENCHMENT DUES")
    assert "₹173,077" in b2 and "₹203,077" in b2

def test_retrenchment_part_year():
    b = _note("retrench a worker with 4 years 8 months at 13,000 per month", "RETRENCHMENT DUES")
    assert "× 5 =" in b and "₹37,500" in b      # 4y8m -> 5 effective years


# ── lay-off (§67: 50% of basic+DA per day, 26-day basis) ──────────────────────
def test_layoff_compensation():
    assert "₹3,750" in _note("we laid off a worker for 15 days; he earns 13,000 per month",
                             "LAY-OFF COMPENSATION")
    assert "₹10,000" in _note("worker laid off 20 days, salary 26000", "LAY-OFF COMPENSATION")

def test_layoff_guard():
    assert _note("can I lay off workers due to no raw material?", "LAY-OFF COMPENSATION") == ""


# ── overtime (§14 Wages / §27 OSH: twice the rate, monthly ÷ (26×8) hourly) ───
def test_overtime_pay():
    assert "₹1,442" in _note("a worker did 5 hours of overtime; salary 30,000 per month", "OVERTIME PAY")
    assert "₹2,000" in _note("overtime work of 10 hours at 20,800 per month", "OVERTIME PAY")

def test_overtime_ambiguity_guard():
    # "worked 10 hours a day" must NOT be read as 10 overtime hours
    assert _note("a worker worked 10 hours a day for 6 days at 26,000 per month", "OVERTIME PAY") == ""


# ── dispatcher hygiene ───────────────────────────────────────────────────────
def test_no_spurious_notes():
    for q in ["What is the overtime pay rate?", "When must wages be paid?",
              "What is retrenchment?", "How many weeks of maternity leave?"]:
        assert app._amount_notes(q) == [], q   # no figures without concrete inputs


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
