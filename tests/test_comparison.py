#!/usr/bin/env python3
"""
test_comparison.py — pin the old-law comparison routing and the broad-question
("what changed from the old laws?") overview grounding.

The failure this guards against: a generic comparison question has no topical
keywords, so raw retrieval grounded the model on unrelated Sections and the
comparison came back empty ("blank answers"). Generic comparisons must take the
curated overview path, and every pinned overview provision must exist in the
corpus with BOTH its old and new side.

Run:  python3 tests/test_comparison.py      (plain, prints PASS/FAIL, exits 1 on failure)
  or: pytest tests/test_comparison.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app     # noqa: E402
import corpus  # noqa: E402


# ── comparison-intent detection ───────────────────────────────────────────────
def test_is_comparison():
    for q in [
        "what has changed from old laws",
        "what has changes from old laws",             # common typo phrasing
        "What changed for retrenchment from the old Industrial Disputes Act?",
        "how has gratuity changed from the old law",
        "maternity benefit old law vs new code",
    ]:
        assert app._is_comparison(q), q
    for q in ["When is gratuity payable and how is it calculated?",
              "We employ 120 workers and want to close a unit — what's the lawful process?"]:
        assert not app._is_comparison(q), q


# ── generic (no-topic) comparison detection ───────────────────────────────────
def test_generic_comparison_detection():
    for q in [
        "what has changed from old laws",
        "what has changed from the old laws?",
        "what changed in the new labour codes compared to old laws",
        "What has changed for employers under the new codes?",
        "how are the new laws different from the old ones",
    ]:
        assert app._is_generic_comparison(q), q
    for q in [
        "how has gratuity changed from the old law",
        "What changed for retrenchment from the old Industrial Disputes Act?",
        "what changed about overtime pay",
        "maternity benefit old law vs new code",
    ]:
        assert not app._is_generic_comparison(q), q


# ── every pinned overview provision must exist, on both sides ─────────────────
def test_overview_topics_pinned_provisions_exist():
    for label, cid, new_lbls, old_map in app._OVERVIEW_TOPICS:
        entry = app.LOADED[cid]
        got_new = {c["label"] for c in app._pick_chunks(entry["chunks"], new_lbls)}
        assert got_new == set(new_lbls), f"{label}: missing new {set(new_lbls) - got_new}"
        for slug, want in old_map.items():
            oa = next((o for o in entry["old_acts"] if o["meta"]["slug"] == slug), None)
            assert oa is not None, f"{label}: old Act {slug} not loaded"
            got_old = {c["label"] for c in app._pick_chunks(oa["chunks"], want)}
            assert got_old == set(want), f"{label}: missing old {set(want) - got_old}"


# ── the overview prompt pairs aligned old/new text per topic ──────────────────
def test_overview_prompt_grounding():
    prompt, sources = app.build_overview_comparison_prompt("what has changed from old laws")
    assert len(sources) == 4, sources                 # all four Codes contribute
    blocks = [b for b in prompt.split("### TOPIC:") if "--- CURRENT LAW" in b]
    assert len(blocks) == len(app._OVERVIEW_TOPICS), len(blocks)
    for b in blocks:                                  # every topic carries BOTH sides
        assert "--- CURRENT LAW (in force) ---" in b
        assert "--- PREVIOUS LAW (repealed Act) ---" in b
    # spot-check the aligned pairs the headline changes rest on
    for needle in [
        "The Industrial Relations Code, 2020 — Section 77",   # 300-worker permission threshold
        "The Industrial Disputes Act, 1947 — Section 25K",    # …was 100 workers
        "The Code on Social Security, 2020 — Section 53",     # gratuity now
        "The Payment of Gratuity Act, 1972 — Section 4",      # gratuity then
        "The Code on Wages, 2019 — Section 9",                # floor wage
        "The Minimum Wages Act, 1948 — Section 3",
    ]:
        assert needle in prompt, needle
    assert prompt.rstrip().endswith("what has changed from old laws")


# ── every old Act must parse into SUBSTANTIVE provisions, not TOC lines ───────
# The bug this pins: gazette front matter ('ARRANGEMENT OF SECTIONS' TOCs, amending-act
# lists) mimics section headings, so 12 of 29 repealed Acts were chunked into bare
# title lines ('4. Payment of gratuity.' — 23 chars) with the real body discarded, and
# every comparison against them was grounded on nothing.
def test_old_acts_parse_substantively():
    import statistics
    for cid, e in app.LOADED.items():
        for oa in e["old_acts"]:
            lens = [len(c["text"]) for c in oa["chunks"]]
            slug = oa["meta"]["slug"]
            assert lens, f"{slug}: no chunks parsed"
            med = statistics.median(lens)
            assert med >= 200, f"{slug}: median chunk {med} chars — TOC-chunked?"
            assert max(lens) < 60_000, f"{slug}: {max(lens)}-char chunk — body swallowed whole"


def test_old_act_key_provisions_carry_statute():
    import re
    checks = [  # (code, old-act slug, provision, text it must contain)
        ("ss", "payment_of_gratuity", "Section 4", "fifteen days"),
        ("ir", "industrial_disputes", "Section 25F", "one month"),
        ("ir", "industrial_disputes", "Section 25K", "one hundred"),   # old 100-worker gate
        ("ir", "industrial_disputes", "Section 25N", "prior permission"),
        ("ir", "industrial_disputes", "Section 22", "six weeks"),
        # the consolidated (as-amended-2017) print: 26 weeks / 80 days, NOT the as-enacted
        # 1961 figures (12 weeks / 160 days) — comparing against the pre-amendment print
        # falsely credited the 2017 changes to the Codes
        ("ss", "maternity_benefit", "Section 5", "twenty-six weeks"),
        ("ss", "maternity_benefit", "Section 5", "eighty days"),
        ("wages", "payment_of_bonus", "Section 10", "8.33"),
        ("wages", "minimum_wages", "Section 3", "minimum rates of wages"),
        ("osh", "factories", "Section 59", "twice"),
        ("osh", "factories", "Section 79", "leave with wages"),
        ("ss", "unorganised_workers_ss", "Section 3", "welfare"),
        ("ss", "epf_misc_provisions", "Section 6", "contribution"),
    ]
    for cid, slug, lbl, kw in checks:
        oa = next(o for o in app.LOADED[cid]["old_acts"] if o["meta"]["slug"] == slug)
        c = next((c for c in oa["chunks"] if c["label"] == lbl), None)
        assert c is not None, f"{slug} {lbl} missing"
        assert re.search(kw, c["text"], re.I), f"{slug} {lbl}: {kw!r} not in text"


# ── topical comparisons must carry the topic's CORE provision on both sides ───
def test_topical_prompt_pins_core_provisions():
    cases = [  # (query, must-appear-in-PREVIOUS-half, must-appear-anywhere)
        ("how has maternity benefit changed from the old law",
         "twenty-six weeks", "Section 60"),                     # old §5 (as amended) + new §60
        ("how has gratuity changed from the old law",
         "The Payment of Gratuity Act, 1972 — Section 4", "Section 53"),
        ("What changed for retrenchment from the old Industrial Disputes Act?",
         "The Industrial Disputes Act, 1947 — Section 25N", "Section 77"),
    ]
    for q, old_needle, new_needle in cases:
        prompt = app.build_comparison_prompt(q, corpus.search_all(app.LOADED, q, k=8))
        old_half = prompt[prompt.find("=== PREVIOUS LAW"):]
        assert old_needle in old_half, f"{q!r}: {old_needle!r} missing from previous-law half"
        assert new_needle in prompt, f"{q!r}: {new_needle!r} missing"


# ── a generic comparison must not depend on raw-query retrieval ───────────────
def test_overview_prompt_is_bounded():
    prompt, _ = app.build_overview_comparison_prompt("what has changed from old laws")
    # keep the grounding within a sane budget so the model call can't hit max_tokens
    # on input bloat (each chunk is _trim-capped; 7 topics of a few provisions each)
    assert 5_000 < len(prompt) < 120_000, len(prompt)


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
