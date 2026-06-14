#!/usr/bin/env python3
"""
eval_retrieval_ab.py — multi-mode retrieval benchmark / scoreboard.

Runs the SAME deterministic cases as eval_retrieval.py (imported, not duplicated) under
each retrieval mode and prints a per-mode scoreboard plus a per-case win/loss diff vs the
`lexical` baseline. This is the engine behind "benchmark, then decide": it makes every mode
choice and patch retirement a measured comparison rather than a guess.

Modes: lexical | embeddings_primary | fusion | rerank  (corpus.RetrievalConfig).
The prebuilt embeddings.npz holds CHUNK vectors, but the QUERY vector is embedded live, so
every non-lexical mode needs a Bedrock key (AWS_BEARER_TOKEN_BEDROCK + AWS_REGION); they are
skipped with a note when the key is absent. `rerank` additionally calls Cohere Rerank.

Metrics per mode:
  routing   — expected code is kept (GOLD + cross-ref cases)
  recall@k  — expected sections present in the code's hits (k = 8, 5, 3)
  MRR       — reciprocal rank of the first expected section in the code's ranked hits (@8)
  xref      — expected provision label present (cross-ref chips)
  cmp       — old-Act comparison routing + keyword grounding
It also reports _vec coverage and warns when the index looks stale (rebuild needed).

Run:  [AWS_BEARER_TOKEN_BEDROCK=... AWS_REGION=...] python scripts/eval_retrieval_ab.py
      python scripts/eval_retrieval_ab.py --modes lexical,fusion,rerank
"""
import os
import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import corpus
import intake
from eval_retrieval import GOLD, COMPARISON

try:
    from eval_cases_hard import HARD
except Exception:
    HARD = []

try:
    import embeddings
except Exception:
    embeddings = None

ALL_MODES = ["lexical", "embeddings_primary", "fusion", "rerank"]


def _rank_of_section(chunks, sec):
    """1-based rank of the first chunk whose num == sec in the ranked list, else 0."""
    for i, ch in enumerate(chunks, 1):
        if ch.get("num") == sec:
            return i
    return 0


def run_mode(c, mode):
    corpus.set_config(corpus.RetrievalConfig(mode=mode))
    route_hits = route_tot = 0
    recall = {8: 0, 5: 0, 3: 0}
    recall_tot = 0
    mrr_sum = 0.0
    mrr_tot = 0
    xref_hits = xref_tot = 0
    cmp_hits = cmp_tot = 0
    per_case = {}                      # (kind, id) -> bool pass, for the win/loss diff

    # ROUTING + SECTION RECALL + MRR
    for q, code, secs in GOLD:
        res = corpus.search_all(c, q, k=8)
        kept = [cid for cid, r in res.items() if r["found"]]
        chunks = res.get(code, {}).get("chunks", [])
        nums = {ch["num"] for ch in chunks}
        route_ok = code in kept
        route_hits += int(route_ok)
        route_tot += 1
        ok = route_ok
        for sec in secs:
            recall_tot += 1
            for k in (8, 5, 3):
                if sec in {ch["num"] for ch in chunks[:k]}:
                    recall[k] += 1
            mrr_tot += 1
            r = _rank_of_section(chunks, sec)
            mrr_sum += (1.0 / r) if r else 0.0
            if sec not in nums:
                ok = False
        per_case[("gold", q)] = ok

    # CROSS-REFERENCE CHIPS
    for lbl, q, code, prov in intake.cross_ref_checks():
        res = corpus.search_all(c, q, k=8)
        kept = [cid for cid, r in res.items() if r["found"]]
        labels = [ch["label"] for ch in res.get(code, {}).get("chunks", [])]
        route_ok = code in kept
        route_hits += int(route_ok)
        route_tot += 1
        pin = route_ok and prov in labels
        xref_hits += int(pin)
        xref_tot += 1
        per_case[("xref", lbl)] = pin

    # OLD-ACT COMPARISON
    for q, code, kw in COMPARISON:
        res = corpus.search_all(c, q, k=6)
        old = corpus.search_old(c[code], q, k=5) if code in c else []
        sources = " ".join(o["source"] for o in old)
        ok = (code in [cid for cid, r in res.items() if r["found"]]) and (kw.lower() in sources.lower())
        cmp_hits += int(ok)
        cmp_tot += 1
        per_case[("cmp", q)] = ok

    # HARD paraphrase / deep-clause cases — each has one governing Section (the discriminating set)
    hard_recall = {8: 0, 5: 0, 3: 0}
    hard_tot = 0
    hard_mrr = 0.0
    for q, code, num in HARD:
        res = corpus.search_all(c, q, k=8)
        kept = [cid for cid, r in res.items() if r["found"]]
        chunks = res.get(code, {}).get("chunks", [])
        hard_tot += 1
        for k in (8, 5, 3):
            if num in {ch["num"] for ch in chunks[:k]}:
                hard_recall[k] += 1
        r = _rank_of_section(chunks, num)
        hard_mrr += (1.0 / r) if r else 0.0
        per_case[("hard", q)] = (code in kept) and (num in {ch["num"] for ch in chunks[:8]})

    return {
        "routing": (route_hits, route_tot),
        "recall": {k: (recall[k], recall_tot) for k in (8, 5, 3)},
        "mrr": (mrr_sum, mrr_tot),
        "xref": (xref_hits, xref_tot),
        "cmp": (cmp_hits, cmp_tot),
        "hard_recall": {k: (hard_recall[k], hard_tot) for k in (8, 5, 3)},
        "hard_mrr": (hard_mrr, hard_tot),
        "per_case": per_case,
    }


def _pct(a, b):
    return f"{a}/{b} ({100 * a // b if b else 0}%)"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--modes", default=",".join(ALL_MODES),
                    help="comma-separated subset of: " + ",".join(ALL_MODES))
    args = ap.parse_args()
    modes = [m.strip() for m in args.modes.split(",") if m.strip()]

    cfg, c = corpus.load_corpus()

    has_key = bool(os.environ.get("AWS_BEARER_TOKEN_BEDROCK"))
    if embeddings is not None:
        on = embeddings.enable(c)
        chunks = [ch for e in c.values() for ch in e["chunks"]]
        n_vec = sum(1 for ch in chunks if ch.get("_vec") is not None)
        cov = (n_vec / len(chunks)) if chunks else 0.0
        print(f"embeddings: {'ON' if on else 'OFF'} | _vec coverage {n_vec}/{len(chunks)} ({100 * cov:.0f}%)"
              f" | query-key: {'present' if has_key else 'ABSENT'}")
        if on and cov < 0.99:
            print("  ⚠ stale index — rebuild embeddings (enable force_build=True) before trusting "
                  "embeddings/fusion/rerank modes")
    else:
        print("embeddings: module unavailable (lexical only)")

    results = {}
    for m in modes:
        if m != "lexical" and not has_key:
            print(f"[{m}] skipped — needs a Bedrock key for the live query embedding")
            continue
        results[m] = run_mode(c, m)
    corpus.set_config(corpus.RetrievalConfig())   # restore default

    print("\n=== SCOREBOARD ===")
    hdr = (f"{'mode':<20}{'routing':>14}{'recall@8':>12}{'recall@5':>12}"
           f"{'recall@3':>12}{'MRR@8':>8}{'xref':>11}{'cmp':>9}")
    print(hdr)
    print("-" * len(hdr))
    for m in modes:
        if m not in results:
            continue
        r = results[m]
        mrr = r["mrr"][0] / r["mrr"][1] if r["mrr"][1] else 0.0
        print(f"{m:<20}{_pct(*r['routing']):>14}{_pct(*r['recall'][8]):>12}"
              f"{_pct(*r['recall'][5]):>12}{_pct(*r['recall'][3]):>12}"
              f"{mrr:>8.3f}{_pct(*r['xref']):>11}{_pct(*r['cmp']):>9}")

    if HARD:
        print("\n=== HARD CASES (paraphrase / deep-clause; the discriminating set) ===")
        hdr2 = f"{'mode':<20}{'recall@8':>12}{'recall@5':>12}{'recall@3':>12}{'MRR@8':>8}"
        print(hdr2)
        print("-" * len(hdr2))
        for m in modes:
            if m not in results:
                continue
            r = results[m]
            hmrr = r["hard_mrr"][0] / r["hard_mrr"][1] if r["hard_mrr"][1] else 0.0
            print(f"{m:<20}{_pct(*r['hard_recall'][8]):>12}{_pct(*r['hard_recall'][5]):>12}"
                  f"{_pct(*r['hard_recall'][3]):>12}{hmrr:>8.3f}")

    if "lexical" in results:
        base = results["lexical"]["per_case"]
        for m in modes:
            if m == "lexical" or m not in results:
                continue
            cur = results[m]["per_case"]
            wins = sorted(k for k in base if cur.get(k) and not base[k])
            losses = sorted(k for k in base if base[k] and not cur.get(k))
            print(f"\n[{m} vs lexical]  +{len(wins)} wins  -{len(losses)} losses")
            for k in losses:
                print(f"   LOSS {k[0]:<5} {k[1]}")
            for k in wins:
                print(f"   WIN  {k[0]:<5} {k[1]}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
