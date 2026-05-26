#!/usr/bin/env python3
"""
ingest.py — one-time prep. Put the official PDFs in documents/pdfs/ and run:
    python ingest.py
Writes clean .txt per document into documents/processed/ using the names the
app expects (see corpus_config.json). Filenames are matched by keyword, so exact
names aren't needed.
"""
import json
import re
import sys
from pathlib import Path

try:
    from pypdf import PdfReader
except ImportError:
    sys.exit("Run:  pip install -r requirements.txt")

ROOT = Path(__file__).parent
PDF_DIR = ROOT / "documents" / "pdfs"
OUT_DIR = ROOT / "documents" / "processed"

RULES = [
    (lambda n: "wage" in n and "rule" in n, "wages_rules.txt"),
    (lambda n: "wage" in n, "wages_code.txt"),
    (lambda n: ("industrial" in n or "relations" in n) and "rule" in n, "ir_rules.txt"),
    (lambda n: "industrial" in n or "relations" in n, "ir_code.txt"),
    (lambda n: ("social" in n or "security" in n) and "rule" in n, "ss_rules.txt"),
    (lambda n: "social" in n or "security" in n, "ss_code.txt"),
    (lambda n: ("occupational" in n or "osh" in n or "safety" in n) and "rule" in n, "osh_rules.txt"),
    (lambda n: "occupational" in n or "osh" in n or "safety" in n, "osh_code.txt"),
]
MANUAL_MAP = {}  # "exact_file.pdf": "target.txt"


def clean(t):
    t = re.sub(r"-\n(\w)", r"\1", t)
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


def target_for(fn):
    if fn in MANUAL_MAP:
        return MANUAL_MAP[fn]
    n = fn.lower()
    for test, out in RULES:
        if test(n):
            return out
    return None


def convert(pdf_path, out_name):
    reader = PdfReader(str(pdf_path))
    text = "\n".join((p.extract_text() or "") for p in reader.pages)
    (OUT_DIR / out_name).write_text(clean(text), encoding="utf-8")
    return len(reader.pages)


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    pdfs = sorted(PDF_DIR.glob("*.pdf"))
    if not pdfs:
        sys.exit(f"No PDFs in {PDF_DIR}. Drop the code/rules PDFs there first.")
    done, skipped = [], []
    for pdf in pdfs:
        out = target_for(pdf.name)
        if not out:
            skipped.append(pdf.name)
            continue
        pages = convert(pdf, out)
        done.append(f"{pdf.name} ({pages}pp) -> {out}")
    print("Converted:\n  " + "\n  ".join(done) if done else "Nothing converted.")
    if skipped:
        print("\nCould not auto-match (rename or add to MANUAL_MAP):\n  " + "\n  ".join(skipped))


if __name__ == "__main__":
    main()
