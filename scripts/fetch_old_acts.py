#!/usr/bin/env python3
"""
fetch_old_acts.py — download the official PDFs of the 29 central labour Acts that the
four Labour Codes repealed, from indiacode.nic.in (DSpace).

For each Act: search indiacode, open the best-matching item page (by title-token overlap
+ year), grab its bitstream PDF, download to documents/pdfs/old_acts/, and verify it
opens in pypdf. Writes a manifest (old_acts_manifest.json) for source spot-checking.

Usage:  python scripts/fetch_old_acts.py [N]      # N = limit (default: all 29)
"""
import json, re, subprocess, sys, time, urllib.parse
from pathlib import Path

BASE = "https://www.indiacode.nic.in"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
OUT = Path(__file__).resolve().parent.parent / "documents" / "pdfs" / "old_acts"

# (slug, canonical title for matching, year, search query)
ACTS = [
    ("payment_of_wages", "Payment of Wages Act", 1936, "Payment of Wages Act 1936"),
    ("minimum_wages", "Minimum Wages Act", 1948, "Minimum Wages Act 1948"),
    ("payment_of_bonus", "Payment of Bonus Act", 1965, "Payment of Bonus Act 1965"),
    ("equal_remuneration", "Equal Remuneration Act", 1976, "Equal Remuneration Act 1976"),
    ("trade_unions", "Trade Unions Act", 1926, "Trade Unions Act 1926"),
    ("industrial_employment_standing_orders", "Industrial Employment Standing Orders Act", 1946,
     "Industrial Employment Standing Orders Act 1946"),
    ("industrial_disputes", "Industrial Disputes Act", 1947, "Industrial Disputes Act 1947"),
    ("employees_compensation", "Workmen Employees Compensation Act", 1923,
     "Workmen Compensation Act 1923"),
    ("employees_state_insurance", "Employees State Insurance Act", 1948,
     "Employees State Insurance Act 1948"),
    ("epf_misc_provisions", "Employees Provident Funds Miscellaneous Provisions Act", 1952,
     "Employees Provident Funds Miscellaneous Provisions Act 1952"),
    ("employment_exchanges_cnv", "Employment Exchanges Compulsory Notification Vacancies Act", 1959,
     "Employment Exchanges Compulsory Notification of Vacancies Act 1959"),
    ("maternity_benefit", "Maternity Benefit Act", 1961, "Maternity Benefit Act 1961"),
    ("payment_of_gratuity", "Payment of Gratuity Act", 1972, "Payment of Gratuity Act 1972"),
    ("cine_workers_welfare_fund", "Cine Workers Welfare Fund Act", 1981,
     "Cine Workers Welfare Fund"),
    ("bocw_welfare_cess", "Building Other Construction Workers Welfare Cess Act", 1996,
     "Building and Other Construction Workers Welfare Cess Act 1996"),
    ("unorganised_workers_ss", "Unorganised Workers Social Security Act", 2008,
     "Unorganised Workers Social Security Act 2008"),
    ("factories", "Factories Act", 1948, "Factories Act 1948"),
    ("plantations_labour", "Plantations Labour Act", 1951, "Plantations Labour Act 1951"),
    ("mines", "Mines Act", 1952, "Mines Act 1952"),
    ("working_journalists_cos", "Working Journalists Newspaper Employees Conditions Service Act",
     1955, "Working Journalists Newspaper Employees Conditions of Service Act 1955"),
    ("working_journalists_wages", "Working Journalists Fixation Rates Wages Act", 1958,
     "Working Journalists Fixation of Rates of Wages Act 1958"),
    ("motor_transport_workers", "Motor Transport Workers Act", 1961,
     "Motor Transport Workers Act 1961"),
    ("beedi_cigar_workers", "Beedi Cigar Workers Conditions Employment Act", 1966,
     "Beedi and Cigar Workers Conditions of Employment Act 1966"),
    ("contract_labour", "Contract Labour Regulation Abolition Act", 1970,
     "Contract Labour Regulation and Abolition Act 1970"),
    ("sales_promotion_employees", "Sales Promotion Employees Conditions Service Act", 1976,
     "Sales Promotion Employees Conditions of Service Act 1976"),
    ("interstate_migrant_workmen", "Inter State Migrant Workmen Regulation Employment Act", 1979,
     "Inter-State Migrant Workmen Regulation of Employment Act 1979"),
    ("cine_cinema_workers", "Cine Cinema Theatre Workers Regulation Employment Act", 1981,
     "Cinema Theatre Workers Regulation of Employment Act 1981"),
    ("dock_workers_shw", "Dock Workers Safety Health Welfare Act", 1986,
     "Dock Workers Safety Health Welfare"),
    ("bocw_recs", "Building Other Construction Workers Regulation Employment Act", 1996,
     "Building and Other Construction Workers Regulation of Employment Act 1996"),
]

STOP = set("the act and of for to in a an other misc miscellaneous provisions".split())
_GENERIC = {"workers", "workmen", "employees", "employee", "act", "other"}  # too common to identify an Act


def _get(url, timeout=40):
    r = subprocess.run(
        ["curl", "-sS", "-L", "-A", UA,
         "-H", "Accept: text/html,application/xhtml+xml",
         "-H", "Accept-Language: en-US,en;q=0.9",
         "--max-time", str(timeout), "--retry", "3", "--retry-delay", "3", url],
        capture_output=True)
    if r.returncode != 0:
        raise RuntimeError(f"curl rc={r.returncode}: {r.stderr.decode()[:100]}")
    return r.stdout


def _toks(s):
    return set(w for w in re.findall(r"[a-z]+", s.lower()) if w not in STOP and len(w) > 2)


def _strip(html):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).strip()


def _search_results(query, n=10):
    """Parse the JSPUI results table → [(handle, result_title)] for act-like hits."""
    query = re.sub(r"[^\w\s]", " ", query)   # indiacode search chokes on apostrophes/hyphens/commas
    html = _get(BASE + "/simple-search?" + urllib.parse.urlencode({"query": query})).decode("utf-8", "ignore")
    out, seen = [], set()
    for row in re.split(r"<tr", html)[1:]:
        hm = re.search(r'href="/?handle/123456789/(\d+)', row)        # row's item handle
        tm = re.search(r'headers="t3"[^>]*>(.*?)</td>', row, re.S)    # title cell
        if not hm or not tm:
            continue
        h, title = hm.group(1), _strip(tm.group(1))
        if h in seen or "act" not in title.lower():
            continue
        seen.add(h)
        out.append((h, title))
        if len(out) >= n:
            break
    return out


def _item_pdfs(handle):
    html = _get(f"{BASE}/handle/123456789/{handle}").decode("utf-8", "ignore")
    return re.findall(r"(bitstream/123456789/\d+/\d+/[^\"']+\.pdf)", html)


def _resolve(query, canonical, year, min_match=2):
    results = _search_results(query)
    if not results:
        return None
    target = _toks(canonical)
    # the Act's lead identifying word (e.g. "dock", "cine", "factories") must appear in the title
    key = next((w for w in re.findall(r"[a-z]+", canonical.lower())
                if len(w) > 2 and w not in STOP and w not in _GENERIC), None)
    ranked = sorted(
        ((len(target & _toks(txt)) + (3 if str(year) in txt else 0), h, txt) for h, txt in results),
        reverse=True)
    for sc, h, txt in ranked[:4]:
        if sc < min_match or (key and key not in _toks(txt)):
            continue
        try:
            pdfs = _item_pdfs(h)
        except Exception:
            pdfs = []
        if pdfs:
            return (sc, h, pdfs[0], txt)
        time.sleep(1.2)
    return None


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else len(ACTS)
    mpath = OUT / "old_acts_manifest.json"
    existing = {e["slug"]: e for e in json.loads(mpath.read_text())} if mpath.exists() else {}
    manifest, report = [], []
    for slug, title, year, query in ACTS[:limit]:
        status, detail, kb, url = "NO-MATCH", "", 0, ""
        dest = OUT / f"old_{slug}_{year}.pdf"
        if dest.exists() and dest.stat().st_size >= 15360 and dest.open("rb").read(5) == b"%PDF-":
            kb = dest.stat().st_size // 1024
            if slug in existing:
                manifest.append(existing[slug])
            print(f"  {'KEEP':8} {slug:38} {year}  {kb:>5}KB already present")
            report.append(("KEEP", slug, year, kb, "already present"))
            continue
        try:
            b = _resolve(query, title, year)
            if b:
                score, h, pdf, ptitle = b
                url = f"{BASE}/{pdf}"
                data = _get(url)
                dest.write_bytes(data)
                kb = len(data) // 1024
                is_pdf = data[:5] == b"%PDF-"
                status = "OK" if (is_pdf and kb >= 15) else ("THIN" if is_pdf else "NOT-PDF")
                detail = f"h{h} sc{score} «{ptitle[:46]}»"
                manifest.append({"slug": slug, "title": title, "year": year,
                                 "url": url, "file": dest.name, "size_kb": kb,
                                 "matched_title": ptitle, "status": status})
        except Exception as e:
            status, detail = "FAIL", f"{type(e).__name__}: {str(e)[:80]}"
        report.append((status, slug, year, kb, detail))
        print(f"  {status:8} {slug:38} {year}  {kb:>5}KB {detail}")
        time.sleep(1.2)

    (OUT / "old_acts_manifest.json").write_text(json.dumps(manifest, indent=2))
    ok = sum(1 for r in report if r[0] == "OK")
    print(f"\n=== {ok}/{len(report)} OK ===")
    bad = [r for r in report if r[0] != "OK"]
    if bad:
        print("Needs manual sourcing / check:")
        for r in bad:
            print(f"   {r[0]:8} {r[1]} ({r[2]})  {r[4]}")


if __name__ == "__main__":
    main()
