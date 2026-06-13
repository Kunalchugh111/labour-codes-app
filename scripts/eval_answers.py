#!/usr/bin/env python3
"""
eval_answers.py — graded accuracy of the LIVE answer pipeline.

Unlike eval_retrieval.py (deterministic, no model), this runs each scenario
through the *real* answer path in app.py — same SYSTEM prompt, same retrieval +
Chapter-X gating, same _converse_json + _reconcile_verdict — and grades the two
things the model is actually asked to get right:

  1. VERDICT    — was "compliant" / "partial" / "non-compliant" the right call
                  for the facts?
  2. CITATIONS  — were the cited provisions the ones that actually GOVERN the
                  case (e.g. retrenchment -> IR section 70), not real-but-
                  irrelevant sections? (Distinct from the verbatim-quote
                  guardrail, which only proves a quote is real, not relevant.)

A third column, QUOTES, reuses corpus.quote_supported as a free verbatim check.

------------------------------------------------------------------------------
GROUND TRUTH IS HUMAN-AUTHORED AND NEEDS SME REVIEW.
The expected verdicts/sections are anchored to the statutory text in the corpus
(IR s70 = retrenchment notice + compensation; SS s53 = gratuity after >=5 years;
SS s60/s62 = maternity) and to the committed retrieval gold set, but legal
ground truth ultimately wants an expert sign-off. Treat the headline % as a
signal and read the per-scenario table — it shows exactly where the model and
these labels disagree so a human can judge who is right.
------------------------------------------------------------------------------

Keyless self-test of the scoring/parsing logic (no model call):
    python scripts/eval_answers.py --demo

Real accuracy (needs Bedrock creds; temperature forced to 0 for reproducibility):
    AWS_BEARER_TOKEN_BEDROCK=...  AWS_REGION=us-east-1 \
        python scripts/eval_answers.py            # add --save to write a report
"""
import os
import re
import sys
import json
import argparse
import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import corpus  # noqa: E402  (import-safe: no Streamlit at import)

# ─────────────────────────────────────────────────────────────────────────────
# Gold set — statute-anchored, SME-review-pending (see header).
#   verdict      : expected verdict.status (compliant | partial | non-compliant)
#   sections     : provisions that GOVERN the case as (code_key, number); ALL
#                  must be cited for citation-relevance to pass.
#   sections_any : passes if ANY one is cited (used for a section cluster where
#                  the exact member is not worth pinning, e.g. Chapter-X).
#   note         : the statutory reason for the label, for the human reviewer.
# ─────────────────────────────────────────────────────────────────────────────
GOLD = [
    # ---- IR / retrenchment — s70: >=1yr service needs one month notice + comp ----
    dict(id="retr-violation",
         query=("I retrenched a worker with 4 years of continuous service in a factory "
                "of 120 workers, giving only 2 days' notice and no compensation."),
         verdict="non-compliant", sections=[("ir", "70")],
         note="s70: one month notice (or wages in lieu) + retrenchment compensation; "
              "2 days/no comp is an affirmative breach. <300 workers so no Chapter X."),
    dict(id="retr-underspecified",
         query="I retrenched a worker who had 4 years of service last week.",
         verdict="partial", sections=[("ir", "70")],
         note="s70 steps (notice, compensation, procedure) unstated -> cannot be "
              "confirmed -> 'partial' per the reconcile floor (risk, not ok)."),
    dict(id="retr-compliant",
         query=("I am retrenching a worker with 5 years' service in an establishment of "
                "150 workers. I have given one month's written notice stating the reason, "
                "will pay 15 days' average wages for each completed year of service, and "
                "have notified the appropriate Government."),
         verdict="compliant", sections=[("ir", "70")],
         note="All s70 conditions stated as done; <300 workers so no prior permission."),
    dict(id="retr-bigestab-noperm",
         query=("We employ 350 workers and retrenched 20 of them last month without "
                "applying for or obtaining prior permission from the Government."),
         verdict="non-compliant",
         sections_any=[("ir", "77"), ("ir", "78"), ("ir", "79"), ("ir", "80")],
         note=">=300 workers -> Chapter X: prior permission required; retrenching "
              "without it is a breach."),
    dict(id="retr-bigestab-unstated",
         query="We have 350 workers and plan to retrench 20 of them next month.",
         verdict="partial",
         sections_any=[("ir", "77"), ("ir", "78"), ("ir", "79"), ("ir", "80")],
         note=">=300 -> prior permission required; permission status unstated -> 'partial'."),

    # ---- SS / gratuity — s53: payable after NOT LESS THAN 5 years continuous service ----
    dict(id="grat-4yr-refused",
         query=("An employee resigned after 4 years of continuous service and we did not "
                "pay any gratuity. Was that correct?"),
         verdict="compliant", sections=[("ss", "53")],
         note="s53: gratuity payable after >=5 years; a 4-yr resignation is not eligible, "
              "so withholding it is lawful."),
    dict(id="grat-6yr-paid",
         query=("We paid gratuity to an employee who left after 6 years of continuous "
                "service, at 15 days' wages for each completed year."),
         verdict="compliant", sections=[("ss", "53")],
         note="s53 satisfied: >5 years, correct rate."),
    dict(id="grat-5yr-refused",
         query=("An employee resigned after completing 5 years of continuous service and "
                "we refused to pay gratuity."),
         verdict="non-compliant", sections=[("ss", "53")],
         note="s53: 5 years meets the threshold -> gratuity is payable; refusing breaches it."),

    # ---- SS / maternity — s60: >=80 days qualifies; 26 weeks benefit ----
    dict(id="mat-refused-eligible",
         query=("We refused maternity benefit to a woman who had worked 90 days for us in "
                "the 12 months before her expected date of delivery."),
         verdict="non-compliant", sections_any=[("ss", "60"), ("ss", "62")],
         note="s60: eligibility is >=80 days in the 12 months preceding; 90 days "
              "qualifies, so refusal is a breach."),
    dict(id="mat-short-leave",
         query="We granted a pregnant employee only 10 weeks of paid maternity leave.",
         verdict="non-compliant", sections_any=[("ss", "60"), ("ss", "62")],
         note="s60: benefit is up to 26 weeks; 10 weeks short-changes the entitlement."),
    dict(id="mat-compliant",
         query=("We granted 26 weeks of paid maternity leave to an eligible employee who "
                "had worked with us for over a year."),
         verdict="compliant", sections_any=[("ss", "60"), ("ss", "62")],
         note="s60 entitlement (26 weeks) met for an eligible employee."),
]


# ─────────────────────────────────────────────────────────────────────────────
# Citation parsing — pull (code_key, number) out of citation strings such as
# "Section 70 / Rule 27 — Industrial Relations Code, 2020".
# ─────────────────────────────────────────────────────────────────────────────
_CODE_NEEDLES = [
    ("ir",    ("industrial relations",)),
    ("ss",    ("social security",)),
    ("wages", ("code on wages", "wages")),
    ("osh",   ("occupational safety", "osh")),
]


def _code_of(citation: str):
    c = citation.lower()
    for key, needles in _CODE_NEEDLES:
        if any(n in c for n in needles):
            return key
    return None


def _cited_pairs(data: dict) -> set:
    """Every (code_key, section_number) cited anywhere in the answer."""
    pairs = set()
    blocks = list(data.get("analysis") or []) + list(data.get("authorities") or [])
    for b in blocks:
        if not isinstance(b, dict):
            continue
        cit = str(b.get("citation", ""))
        code = _code_of(cit)
        for num in re.findall(r"[Ss]ection[s]?\s+([0-9]+[A-Za-z]*)", cit):
            pairs.add((code, num))
    return pairs


def _verdict_of(data: dict):
    if not isinstance(data, dict):
        return None
    v = data.get("verdict")
    if isinstance(v, dict):
        return (v.get("status") or "").strip().lower() or None
    return None


def _score_citations(expected, expected_any, cited_pairs):
    """relevant_ok requires every `expected` section to be cited AND at least
    one of `expected_any` (when given). Returns (ok|None, detail)."""
    by_code = {}
    for code, num in cited_pairs:
        by_code.setdefault(code, set()).add(num)

    def is_cited(code, num):
        if num in by_code.get(code, set()):
            return True
        # tolerate a citation whose Code we could not classify
        return any(num in nums for c, nums in by_code.items() if c is None)

    missing = [f"{c} s{n}" for (c, n) in expected if not is_cited(c, n)]
    any_ok, any_note = True, ""
    if expected_any:
        any_ok = any(is_cited(c, n) for (c, n) in expected_any)
        if not any_ok:
            any_note = " | none of " + "/".join(f"{c}s{n}" for c, n in expected_any)
    expected_codes = {c for c, _ in expected} | {c for c, _ in expected_any}
    extras = sorted({f"{c}s{n}" for (c, n) in cited_pairs
                     if c is not None and c not in expected_codes})
    detail = ("all governing cited" if not missing else "missing " + ", ".join(missing))
    detail += any_note
    if extras:
        detail += " | extra: " + ", ".join(extras)
    return (not missing) and any_ok, detail


# ─────────────────────────────────────────────────────────────────────────────
# Live pipeline — mirror app.py's non-comparison answer path (app.py:1821-1877).
# ─────────────────────────────────────────────────────────────────────────────
def _make_app():
    """Import app.py and rewire its three Streamlit-coupled shims so the real
    pipeline runs headlessly off environment-variable credentials."""
    import boto3
    import app

    region = os.environ.get("AWS_REGION", "us-east-1")
    app.get_bedrock_client = lambda: boto3.client("bedrock-runtime", region_name=region)
    app._has_key = lambda: bool(os.environ.get("AWS_BEARER_TOKEN_BEDROCK"))
    app._model_id = lambda: os.environ.get("BEDROCK_MODEL_ID", app.MODEL_ID)
    # Exercise the real hybrid (keyword + semantic) retrieval path when an index/key is
    # present; the @st.cache_resource startup hook may not fire under bare import.
    try:
        import embeddings
        embeddings.enable(app.LOADED)
    except Exception:
        pass
    return app


def _answer(app, intake, query: str) -> dict:
    """Real retrieval + gating + prompt + model + reconcile, at temperature 0.
    Equivalent to app.generate_answer() but deterministic."""
    corrected_q = corpus.correct_query(query)[0]
    extra_terms = app.analyze_query(query)                       # boost; "" on error
    all_results = corpus.search_all(app.LOADED, corrected_q, k=8, boost=extra_terms)

    topic = intake.topic(corrected_q)
    got = intake.facts_from_query(corrected_q)
    notes = intake.applicability(topic, got or {}) if topic else []

    # Chapter-X gating: below 300, keep prior-permission Sections out of grounding.
    excl = app._excluded_ir_sections(topic, got or {})
    rfp = all_results
    ir = all_results.get("ir")
    if excl and ir and ir.get("found"):
        rfp = {**all_results,
               "ir": {**ir, "chunks": [c for c in ir["chunks"]
                                       if c.get("num") not in excl]}}

    user_msg = app.build_prompt(query, rfp, applicability=notes)
    return app._reconcile_verdict(app._converse_json(app.SYSTEM, user_msg, temperature=0.0))


# ─────────────────────────────────────────────────────────────────────────────
# Reporting
# ─────────────────────────────────────────────────────────────────────────────
def _format(rows):
    n = len(rows)
    v_ok = sum(1 for r in rows if r["verdict_ok"])
    scored = [r for r in rows if r["cite_ok"] is not None]
    c_ok = sum(1 for r in scored if r["cite_ok"])
    both = sum(1 for r in rows if r["verdict_ok"] and r["cite_ok"] is not False)
    out = []
    out.append("")
    out.append(f"{'id':<22} {'verdict (exp -> got)':<32} {'citations':<42} quotes")
    out.append("-" * 104)
    for r in rows:
        vmark = "ok " if r["verdict_ok"] else "XX "
        vcol = f"{vmark}{r['expected_verdict']} -> {r['got_verdict']}"
        cmark = "--" if r["cite_ok"] is None else ("ok" if r["cite_ok"] else "XX")
        out.append(f"{r['id']:<22} {vcol:<32} {cmark+' '+r['cite_detail']:<42} {r['quotes']}")
    out.append("-" * 104)
    pct = lambda a, b: f"{(100 * a // b) if b else 0}%"
    out.append(f"Verdict accuracy  : {v_ok}/{n} ({pct(v_ok, n)})")
    out.append(f"Citation relevance: {c_ok}/{len(scored)} ({pct(c_ok, len(scored))})"
               f"   [scored where governing sections are labelled]")
    out.append(f"Both correct      : {both}/{n} ({pct(both, n)})")
    return "\n".join(out)


def _run_live(save: bool) -> int:
    if not os.environ.get("AWS_BEARER_TOKEN_BEDROCK"):
        print("No Bedrock credentials found.\n"
              "Set AWS_BEARER_TOKEN_BEDROCK and AWS_REGION to produce a real number:\n"
              "  AWS_BEARER_TOKEN_BEDROCK=... AWS_REGION=us-east-1 python scripts/eval_answers.py\n"
              "Or run the keyless scoring self-test:  python scripts/eval_answers.py --demo")
        return 2

    app = _make_app()
    import intake
    full_norm = corpus.full_corpus_norm(app.LOADED)
    rows = []
    for sc in GOLD:
        data = _answer(app, intake, sc["query"])
        got = _verdict_of(data)
        expected, expected_any = sc.get("sections", []), sc.get("sections_any", [])
        if expected or expected_any:
            cite_ok, cite_detail = _score_citations(expected, expected_any, _cited_pairs(data))
        else:
            cite_ok, cite_detail = None, "n/a"
        quotes = [a.get("quote", "") for a in (data.get("authorities") or [])
                  if isinstance(a, dict)]
        q_ok = sum(1 for q in quotes if q and corpus.quote_supported(q, full_norm))
        rows.append(dict(id=sc["id"], expected_verdict=sc["verdict"],
                         got_verdict=got or "(none)", verdict_ok=(got == sc["verdict"]),
                         cite_ok=cite_ok, cite_detail=cite_detail,
                         quotes=(f"{q_ok}/{len(quotes)}" if quotes else "0/0")))

    report = _format(rows)
    print(report)
    if save:
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        os.makedirs("eval_results", exist_ok=True)
        path = f"eval_results/answers_{stamp}"
        open(path + ".md", "w").write("# Answer accuracy " + stamp + "\n\n```\n" + report + "\n```\n")
        json.dump(rows, open(path + ".json", "w"), indent=2, default=str)
        print(f"\nWrote {path}.md (+ .json)")
    return 0


# ─────────────────────────────────────────────────────────────────────────────
# Keyless self-test of the scoring/parsing logic (no model call).
# ─────────────────────────────────────────────────────────────────────────────
def _run_demo() -> int:
    fixtures = [
        ("compliance non-compliant w/ IR70", {
            "type": "compliance", "verdict": {"status": "non-compliant"},
            "analysis": [{"status": "violation",
                          "citation": "Section 70 — Industrial Relations Code, 2020"}],
            "authorities": [{"citation": "Section 70 — Industrial Relations Code, 2020",
                             "quote": "x"}]}),
        ("compliance compliant w/ SS53", {
            "type": "compliance", "verdict": {"status": "compliant"},
            "analysis": [{"status": "ok",
                          "citation": "Section 53 — Code on Social Security, 2020"}],
            "authorities": []}),
        ("info (verdict null)", {"type": "info", "verdict": None, "analysis": []}),
    ]
    ok = True
    print("\nDEMO — keyless scoring/parsing self-test (no model call)")
    print("-" * 72)
    for label, d in fixtures:
        v = _verdict_of(d)
        pairs = sorted(f"{c}s{n}" for c, n in _cited_pairs(d))
        good = (v is not None) if d.get("type") == "compliance" else (v is None)
        ok &= good
        print(f"  [{'ok' if good else 'XX'}] {label:<34} verdict={v}  cited={pairs}")
    c1, d1 = _score_citations([("ir", "70")], [], {("ir", "70")})
    c2, _ = _score_citations([("ir", "70")], [], {("ss", "53")})       # should miss
    c3, _ = _score_citations([], [("ss", "60"), ("ss", "62")], {("ss", "62")})  # any-ok
    print(f"  [{'ok' if c1 else 'XX'}] scorer: expect IR70, cited IR70 -> pass ({d1})")
    print(f"  [{'ok' if not c2 else 'XX'}] scorer: expect IR70, cited SS53 -> miss")
    print(f"  [{'ok' if c3 else 'XX'}] scorer: any of SS60/62, cited SS62 -> pass")
    ok &= c1 and (not c2) and c3
    print("-" * 72)
    print("DEMO PASS" if ok else "DEMO FAIL")
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--demo", action="store_true",
                    help="keyless self-test of scoring/parsing (no model call)")
    ap.add_argument("--save", action="store_true",
                    help="write a timestamped report under eval_results/")
    args = ap.parse_args()
    sys.exit(_run_demo() if args.demo else _run_live(args.save))


if __name__ == "__main__":
    main()
