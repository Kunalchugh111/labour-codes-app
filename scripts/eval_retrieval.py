#!/usr/bin/env python3
"""
eval_retrieval.py — deterministic quality gate for the assistant's grounding.

Checks, with no LLM call:
  1. ROUTING — each HR question reaches the right Code(s).
  2. SECTION RECALL — known operative Sections are actually retrieved.
  3. GUARDRAIL — the verbatim-quote checker accepts real statute and rejects fabrications.

Run:  python scripts/eval_retrieval.py        (exit code 0 = all passed)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import corpus

# (query, expected_code, [section numbers that should appear in that code's hits])
GOLD = [
    ("I retrenched an employee with two days notice", "ir", [70]),
    ("conditions and procedure for retrenchment", "ir", [70]),
    ("notice period before a lawful strike", "ir", []),
    ("registration of a trade union", "ir", []),
    ("when is gratuity payable and how is it calculated", "ss", [53]),
    ("maternity leave entitlement and duration", "ss", []),
    ("provident fund contribution rate", "ss", []),
    ("employees state insurance medical benefit", "ss", []),
    ("minimum wages fixing for an employment", "wages", []),
    ("bonus eligibility and minimum bonus percentage", "wages", []),
    ("equal remuneration for men and women", "wages", []),
    ("deductions that can be made from wages", "wages", []),
    ("maximum daily working hours and overtime", "osh", []),
    ("can women be required to work night shifts in a factory", "osh", []),
    ("contract labour regulation and abolition", "osh", []),
    ("welfare facilities like canteen and creche", "osh", []),
    ("when can i strike", "ir", []),                 # regression: was mis-routed to Wages/OSH
    ("notice for a strike or lock-out", "ir", []),
]

COMPARISON = [   # (query, expected_code, old-Act keyword that should appear in old hits)
    ("what changed in retrenchment rules from the old act", "ir", "Industrial Disputes"),
    ("how has gratuity changed from the old law", "ss", "Gratuity"),
    ("maternity benefit old law vs new code", "ss", "Maternity"),
]


def main():
    cfg, c = corpus.load_corpus()
    passed = failed = 0
    fails = []

    print("── ROUTING + SECTION RECALL ──")
    for q, code, secs in GOLD:
        res = corpus.search_all(c, q, k=8)
        kept = [cid for cid, r in res.items() if r["found"]]
        nums = {ch["num"] for ch in res.get(code, {}).get("chunks", [])}
        ok_route = code in kept
        ok_secs = all(s in nums for s in secs)
        ok = ok_route and ok_secs
        passed, failed = (passed + 1, failed) if ok else (passed, failed + 1)
        flag = "ok " if ok else "FAIL"
        detail = "" if ok else f"  (route={kept}" + (f", want §{secs} got {sorted(n for n in nums if n)}" if not ok_secs else "") + ")"
        if not ok:
            fails.append(f"{q!r} -> expected {code}{detail}")
        print(f"  [{flag}] {code:5} ← {q}{detail}")

    print("\n── COMPARISON (old-Act grounding) ──")
    for q, code, kw in COMPARISON:
        res = corpus.search_all(c, q, k=6)
        old = corpus.search_old(c[code], q, k=5) if code in c else []
        sources = " ".join(o["source"] for o in old)
        ok = (code in [cid for cid, r in res.items() if r["found"]]) and (kw.lower() in sources.lower())
        passed, failed = (passed + 1, failed) if ok else (passed, failed + 1)
        if not ok:
            fails.append(f"{q!r} -> wanted old '{kw}' in {code}")
        print(f"  [{'ok ' if ok else 'FAIL'}] {code:5} ← {q}  (old: {kw if ok else sources[:60]})")

    print("\n── CROSS-REFERENCE CHIPS (related-provision routing) ──")
    import intake
    for lbl, q, code, prov in intake.cross_ref_checks():
        res = corpus.search_all(c, q, k=8)
        kept = [cid for cid, r in res.items() if r["found"]]
        labels = [ch["label"] for ch in res.get(code, {}).get("chunks", [])]
        ok = code in kept and prov in labels
        passed, failed = (passed + 1, failed) if ok else (passed, failed + 1)
        if not ok:
            fails.append(f"cross-ref {lbl!r} -> expected {code}/{prov} (route={kept})")
        print(f"  [{'ok ' if ok else 'FAIL'}] {code:5} {prov:11} ← {lbl}")

    print("\n── GUARDRAIL (verbatim-quote checker) ──")
    sample = next(ch for ch in c["wages"]["chunks"] if len(ch["text"]) > 300)
    text = sample["text"]
    hay = corpus.normalize_for_match(text)
    real = text[40:160]                                   # a genuine verbatim slice
    elided = text[40:90] + " ... " + text[110:170]        # genuine slices with an elision
    fake = "The employer shall pay a unicorn welfare bonus of ninety-nine per cent each fortnight."
    cases = [
        ("accepts verbatim quote", corpus.quote_supported(real, hay) is True),
        ("accepts elided verbatim quote", corpus.quote_supported(elided, hay) is True),
        ("rejects fabricated quote", corpus.quote_supported(fake, hay) is False),
        ("rejects quote from a different chunk",
         corpus.quote_supported(c["osh"]["chunks"][5]["text"][50:170], hay) is False),
    ]
    for name, ok in cases:
        passed, failed = (passed + 1, failed) if ok else (passed, failed + 1)
        if not ok:
            fails.append(f"guardrail: {name}")
        print(f"  [{'ok ' if ok else 'FAIL'}] {name}")

    print("\n── REGRESSIONS (real-use bugs) ──")
    full = corpus.full_corpus_norm(c)
    reg = [
        ("spell-corrector leaves 'working conditions' intact",
         corpus.correct_query("working conditions")[0] == "working conditions"),
        ("spell-corrector leaves 'obligations' intact",
         "obligations" in corpus.correct_query("my obligations")[0]),
        ("'when can i strike' top code is IR",
         max(c, key=lambda cid: corpus._code_relevance(c[cid], "when can i strike")) == "ir"),
        ("'pf' expands to provident-fund terms (2-char abbrev not dropped)",
         "provident fund" in corpus._terms("pf") and "epf" in corpus._terms("pf")),
        ("'pf contribution' surfaces the SS provident-fund provision",
         any("provident" in ((ch.get("title") or "") + ch.get("text", "")).lower()
             for ch in corpus.search_all(c, "pf contribution", k=4).get("ss", {}).get("chunks", []))),
        ("citation lookup returns the real §62 text",
         "maternity benefit" in (corpus.lookup_citation(
             c, "Section 62 — The Code on Social Security, 2020") or "").lower()),
        ("citation lookup resolves an old-Act citation (Industrial Disputes §25)",
         bool(corpus.lookup_citation(c, "Section 25 — The Industrial Disputes Act, 1947"))),
        ("full-corpus guardrail accepts a real §62 quote",
         corpus.quote_supported(
             "Any woman employed in an establishment and entitled to maternity benefit under "
             "the provisions of this Chapter may give notice in writing", full) is True),
        ("guardrail still rejects a fabricated quote",
         corpus.quote_supported(
             "The employer shall grant a unicorn allowance of fifty per cent each fortnight", full) is False),
    ]
    for name, ok in reg:
        passed, failed = (passed + 1, failed) if ok else (passed, failed + 1)
        if not ok:
            fails.append(f"regression: {name}")
        print(f"  [{'ok ' if ok else 'FAIL'}] {name}")

    print(f"\n=== {passed} passed, {failed} failed ===")
    if fails:
        print("FAILURES:")
        for f in fails:
            print("  -", f)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
