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
