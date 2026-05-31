#!/usr/bin/env python3
"""
ingest.py — one-time prep. Put the official PDFs in documents/pdfs/ and run:
    python ingest.py
Writes clean .txt per document into documents/processed/ using the names the
app expects (see corpus_config.json). Filenames are matched by keyword, so exact
names aren't needed.

The Central Rules are published as BILINGUAL Gazette notifications (English +
Hindi pages in one PDF). We extract with PyMuPDF and keep only the English pages,
so the processed text is clean English rather than a Hindi/English blend.
"""
import json
import re
import sys
from pathlib import Path

try:
    import fitz  # PyMuPDF
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

# Gazette running headers / page chrome to drop (English and Hindi forms).
_CHROME = re.compile(r"GAZETTE OF INDIA|EXTRAORDINARY|PART\s*II|भाग|राजपत्र|रािपत्र|असाधारण|खण")

# Normalise unicode punctuation to ASCII so structure markers survive (rule titles
# end in ".–"/".—" which must become ".-"); applied BEFORE stripping other non-ASCII.
_PUNCT = str.maketrans({
    "‐": "-", "‑": "-", "‒": "-", "–": "-", "—": "-", "―": "-",
    "‘": "'", "’": "'", "“": '"', "”": '"', "…": "...", " ": " ",
})


def english_pages(pdf_path):
    """Concatenate only the English pages of a (possibly bilingual) PDF, in order."""
    doc = fitz.open(str(pdf_path))
    kept = []
    for p in doc:
        t = p.get_text()
        if not t.strip():
            continue
        nonascii = sum(1 for c in t if ord(c) > 127)
        if 100 * nonascii / max(len(t), 1) < 12:   # English page (drops Hindi gazette pages)
            kept.append(t)
    return "\n".join(kept), doc.page_count


def clean(t):
    lines = []
    for line in t.splitlines():
        s = line.strip().translate(_PUNCT)       # normalise dashes/quotes to ASCII
        if not s:
            lines.append("")
            continue
        if _CHROME.search(s):                    # gazette header / footer chrome
            continue
        if re.fullmatch(r"\d{1,4}", s):          # bare page number
            continue
        s = re.sub(r"[^\x00-\x7F]+", " ", s)     # drop any remaining non-ASCII fragments
        s = re.sub(r"[ \t]+", " ", s).strip()
        if s:
            lines.append(s)
    text = "\n".join(lines)
    text = re.sub(r"-\n(\w)", r"\1", text)        # rejoin hyphenated line breaks
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def target_for(fn):
    if fn in MANUAL_MAP:
        return MANUAL_MAP[fn]
    n = fn.lower()
    for test, out in RULES:
        if test(n):
            return out
    return None


def convert(pdf_path, out_name):
    text, pages = english_pages(pdf_path)
    (OUT_DIR / out_name).write_text(clean(text), encoding="utf-8")
    return pages


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
