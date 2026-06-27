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
        # Count Devanagari specifically, not all non-ASCII: a genuine English wages/gazette page
        # is dense with ₹, em-dashes and curly quotes (all >127), which under an all-non-ASCII
        # test could push it over the threshold and wrongly drop it. Hindi pages are ~40-90%
        # Devanagari, so they stay well above the bar.
        devanagari = sum(1 for c in t if "ऀ" <= c <= "ॿ")
        if 100 * devanagari / max(len(t), 1) < 12:   # English page (drops Hindi gazette pages)
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


_ACTREF = re.compile(r"^\d+\s+of\s+\d{4}")


def code_titles(pdf_path):
    """Map section number -> margin title for a gazette Code PDF. Gazette Acts print the
    section title in the right margin at a smaller font (the 2020 Codes have no separate
    'Arrangement of Sections' page). Walk each page top-to-bottom, track the current section
    from the left-column 'N.', and attach the right-margin fragments beside it to that
    section. Returns only clean titles (Act-reference margin notes like '18 of 2013' dropped)."""
    doc = fitz.open(str(pdf_path))
    titles = {}
    for page in doc:
        margin_x = page.rect.width * 0.72
        lines = []
        for b in page.get_text("dict")["blocks"]:
            for ln in b.get("lines", []):
                sp = ln.get("spans", [])
                if not sp:
                    continue
                txt = "".join(s["text"] for s in sp).strip()
                if not txt:
                    continue
                x0 = min(s["bbox"][0] for s in sp)
                sz = max(s["size"] for s in sp)
                y0 = min(s["bbox"][1] for s in sp)
                lines.append((round(y0), round(x0), round(sz, 1), txt))
        lines.sort()
        cur, buf = None, []
        for _y, x, sz, t in lines:
            m = re.match(r"^(\d{1,3})\.(?:\s|\(|$)", t)
            if x < 210 and sz >= 9.5 and m:                          # left-column section start
                if cur and buf:
                    titles.setdefault(cur, " ".join(buf))
                cur, buf = int(m.group(1)), []
            elif x > margin_x and sz <= 9.0 and cur is not None and re.search(r"[A-Za-z]", t) \
                    and not _ACTREF.match(t):                        # right-margin title fragment
                buf.append(t)
        if cur and buf:
            titles.setdefault(cur, " ".join(buf))
    out = {}
    for n, v in titles.items():
        v = re.sub(r"\s+", " ", v).strip().rstrip(".")
        if 2 < len(v) < 95 and sum(c.isdigit() for c in v) <= len(v) * 0.3:
            out[str(n)] = v
    return out


def convert(pdf_path, out_name):
    text, pages = english_pages(pdf_path)
    (OUT_DIR / out_name).write_text(clean(text), encoding="utf-8")
    return pages


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    pdfs = sorted(PDF_DIR.glob("*.pdf"))
    if not pdfs:
        sys.exit(f"No PDFs in {PDF_DIR}. Drop the code/rules PDFs there first.")
    done, skipped, titles_map = [], [], {}
    for pdf in pdfs:
        out = target_for(pdf.name)
        if not out:
            skipped.append(pdf.name)
            continue
        pages = convert(pdf, out)
        if out.endswith("_code.txt"):                 # mine section titles from Code PDFs
            try:
                t = code_titles(pdf)
                if t:
                    titles_map[out] = t
                else:
                    print(f"warn: no section titles mined from {pdf.name} -> {out}")
            except Exception as e:
                # Don't fail the whole ingest, but surface it: a missing title map silently
                # degrades marginal titles, retrieval title-bonuses, and citations downstream.
                print(f"warn: code_titles failed for {pdf.name}: {e}")
        done.append(f"{pdf.name} ({pages}pp) -> {out}")
    if titles_map:
        (OUT_DIR / "section_titles.json").write_text(
            json.dumps(titles_map, ensure_ascii=False, indent=0), encoding="utf-8")
        print(f"Section titles: {sum(len(v) for v in titles_map.values())} across {len(titles_map)} codes -> section_titles.json")
    print("Converted:\n  " + "\n  ".join(done) if done else "Nothing converted.")
    if skipped:
        print("\nCould not auto-match (rename or add to MANUAL_MAP):\n  " + "\n  ".join(skipped))


if __name__ == "__main__":
    main()
