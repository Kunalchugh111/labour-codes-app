#!/usr/bin/env python3
"""
build_old_acts.py — turn the downloaded old-Act PDFs into the searchable corpus.

For every Act in OLD_ACTS: extract text from documents/pdfs/old_acts/old_<slug>_<year>.pdf
into documents/processed/old_<slug>.txt (same cleaning as ingest.py), and register the Act
under its repealing Code's "old_acts" list in corpus_config.json. Acts whose PDF is missing
are still registered (so they load automatically once the PDF is added).

Run after adding/replacing any old-Act PDF:   python scripts/build_old_acts.py
"""
import json
import re
from pathlib import Path

try:
    import fitz  # PyMuPDF
except ImportError:
    raise SystemExit("pip install pymupdf")

ROOT = Path(__file__).resolve().parent.parent
PDF_DIR = ROOT / "documents" / "pdfs" / "old_acts"
OUT_DIR = ROOT / "documents" / "processed"
CFG = ROOT / "corpus_config.json"

# slug -> (display title, year, repealing code id)
OLD_ACTS = {
    "payment_of_wages": ("The Payment of Wages Act, 1936", 1936, "wages"),
    "minimum_wages": ("The Minimum Wages Act, 1948", 1948, "wages"),
    "payment_of_bonus": ("The Payment of Bonus Act, 1965", 1965, "wages"),
    "equal_remuneration": ("The Equal Remuneration Act, 1976", 1976, "wages"),
    "trade_unions": ("The Trade Unions Act, 1926", 1926, "ir"),
    "industrial_employment_standing_orders":
        ("The Industrial Employment (Standing Orders) Act, 1946", 1946, "ir"),
    "industrial_disputes": ("The Industrial Disputes Act, 1947", 1947, "ir"),
    "employees_compensation": ("The Employee's Compensation Act, 1923", 1923, "ss"),
    "employees_state_insurance": ("The Employees' State Insurance Act, 1948", 1948, "ss"),
    "epf_misc_provisions":
        ("The Employees' Provident Funds and Miscellaneous Provisions Act, 1952", 1952, "ss"),
    "employment_exchanges_cnv":
        ("The Employment Exchanges (Compulsory Notification of Vacancies) Act, 1959", 1959, "ss"),
    "maternity_benefit": ("The Maternity Benefit Act, 1961", 1961, "ss"),
    "payment_of_gratuity": ("The Payment of Gratuity Act, 1972", 1972, "ss"),
    "cine_workers_welfare_fund": ("The Cine-Workers Welfare Fund Act, 1981", 1981, "ss"),
    "bocw_welfare_cess":
        ("The Building and Other Construction Workers' Welfare Cess Act, 1996", 1996, "ss"),
    "unorganised_workers_ss": ("The Unorganised Workers' Social Security Act, 2008", 2008, "ss"),
    "factories": ("The Factories Act, 1948", 1948, "osh"),
    "plantations_labour": ("The Plantations Labour Act, 1951", 1951, "osh"),
    "mines": ("The Mines Act, 1952", 1952, "osh"),
    "working_journalists_cos":
        ("The Working Journalists and other Newspaper Employees (Conditions of Service) "
         "and Miscellaneous Provisions Act, 1955", 1955, "osh"),
    "working_journalists_wages":
        ("The Working Journalists (Fixation of Rates of Wages) Act, 1958", 1958, "osh"),
    "motor_transport_workers": ("The Motor Transport Workers Act, 1961", 1961, "osh"),
    "beedi_cigar_workers":
        ("The Beedi and Cigar Workers (Conditions of Employment) Act, 1966", 1966, "osh"),
    "contract_labour":
        ("The Contract Labour (Regulation and Abolition) Act, 1970", 1970, "osh"),
    "sales_promotion_employees":
        ("The Sales Promotion Employees (Conditions of Service) Act, 1976", 1976, "osh"),
    "interstate_migrant_workmen":
        ("The Inter-State Migrant Workmen (Regulation of Employment and Conditions of "
         "Service) Act, 1979", 1979, "osh"),
    "cine_cinema_workers":
        ("The Cine-Workers and Cinema Theatre Workers (Regulation of Employment) Act, 1981",
         1981, "osh"),
    "dock_workers_shw":
        ("The Dock Workers (Safety, Health and Welfare) Act, 1986", 1986, "osh"),
    "bocw_recs":
        ("The Building and Other Construction Workers (Regulation of Employment and "
         "Conditions of Service) Act, 1996", 1996, "osh"),
}


def clean(t: str) -> str:
    t = re.sub(r"-\n(\w)", r"\1", t)
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    cfg = json.loads(CFG.read_text())
    by_code: dict[str, list] = {}
    done, missing = [], []
    for slug, (title, year, code) in OLD_ACTS.items():
        fname = f"old_{slug}.txt"
        by_code.setdefault(code, []).append(
            {"slug": slug, "title": title, "year": year, "file": fname})
        pdf = PDF_DIR / f"old_{slug}_{year}.pdf"
        if not pdf.exists():
            missing.append(slug)
            continue
        doc = fitz.open(str(pdf))
        text = clean("\n".join(p.get_text() for p in doc))
        (OUT_DIR / fname).write_text(text, encoding="utf-8")
        done.append((slug, doc.page_count, len(text)))

    for c in cfg["codes"]:
        c.pop("replaced_acts", None)            # superseded by the richer old_acts list
        c["old_acts"] = by_code.get(c["id"], [])
    CFG.write_text(json.dumps(cfg, indent=2, ensure_ascii=False) + "\n")

    print(f"extracted {len(done)} acts -> documents/processed/")
    for slug, pp, n in done:
        print(f"  {slug:38} {pp:>3}pp  {n:>7} chars")
    if missing:
        print(f"\nPDF missing (registered but not extracted): {', '.join(missing)}")


if __name__ == "__main__":
    main()
