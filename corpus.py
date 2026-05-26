"""
corpus.py — load the processed code/rules text, split it into citable chunks
(Sections, Rules, Schedules), and retrieve only the slices relevant to a query.

Why chunk + retrieve: the full corpus is ~hundreds of pages. We never send all of
it to the model. We send the handful of sections a question actually touches, so
every answer stays small, fast, and cheap, and the model cites from real text.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).parent
PROCESSED = ROOT / "documents" / "processed"

STOP = set("""a an the of to in for on and or by with as is are be this that any such
which under section sub clause shall means may not no it its his he him under into
from per cent rupees within where when been being under code act rules rule""".split())


# ----------------------------------------------------------------- parsing
def _split_numbered(text):
    """Split a block into strictly-increasing top-level numbered items (1., 2., 3.).
    Strictly-increasing filtering ignores stray '12.' cross-references and list noise."""
    cands = [(int(m.group(1)), m.start()) for m in re.finditer(r"(?m)^\s{0,4}(\d{1,3})\.\s", text)]
    items, expected, open_at, open_num = [], 1, None, None
    for num, pos in cands:
        if num == expected:
            if open_at is not None:
                items.append((open_num, text[open_at:pos]))
            open_at, open_num, expected = pos, num, num + 1
    if open_at is not None:
        items.append((open_num, text[open_at:].strip()))
    return items


def _schedules(text):
    out = []
    parts = re.split(r"(THE\s+[A-Z]+\s+SCHEDULE)", text)
    for i in range(1, len(parts), 2):
        title = parts[i].strip().title()
        body = parts[i + 1] if i + 1 < len(parts) else ""
        out.append((title, (parts[i] + body).strip()))
    return out


def _preview(s, n=150):
    s = re.sub(r"\s+", " ", s).strip()
    return s[:n]


def parse_doc(text, kind):
    """kind: 'code' uses 'Section N'; 'rules' uses 'Rule N'."""
    label = "Section" if kind == "code" else "Rule"
    sched_match = re.search(r"THE\s+[A-Z]+\s+SCHEDULE", text)
    body = text[: sched_match.start()] if sched_match else text
    tail = text[sched_match.start():] if sched_match else ""
    chunks = []
    for num, seg in _split_numbered(body):
        chunks.append({"label": f"{label} {num}", "num": num, "text": seg.strip(),
                       "preview": _preview(seg)})
    for title, seg in _schedules(tail):
        chunks.append({"label": title, "num": None, "text": seg, "preview": _preview(seg)})
    return chunks


# ----------------------------------------------------------------- loading
def _read(name):
    p = PROCESSED / name
    return p.read_text(encoding="utf-8") if p.exists() else None


def load_corpus():
    cfg = json.loads((ROOT / "corpus_config.json").read_text())
    corpus = {}
    for c in cfg["codes"]:
        statute = _read(c["statute_file"])
        rules = _read(c["central_rules"]["file"])
        if not statute and not rules:
            continue
        entry = {"meta": c, "chunks": []}
        if statute:
            for ch in parse_doc(statute, "code"):
                ch["source"] = c["title"]
                entry["chunks"].append(ch)
        if rules:
            for ch in parse_doc(rules, "rules"):
                ch["source"] = c["central_rules"]["title"]
                entry["chunks"].append(ch)
        corpus[c["id"]] = entry
    return cfg, corpus


# ----------------------------------------------------------------- retrieval
def _terms(q):
    return [w for w in re.findall(r"[a-z]{3,}", q.lower()) if w not in STOP]


def search(entry, query, k=12):
    """Return up to k chunks from one code+rules most relevant to the query."""
    terms = _terms(query)
    explicit = set(int(n) for n in re.findall(r"(?:section|rule)\s+(\d{1,3})", query.lower()))
    definitional = bool(re.search(r"\b(defin|meaning|means|what is|who is)\b", query.lower()))

    scored = []
    for ch in entry["chunks"]:
        low = ch["text"].lower()
        score = sum(low.count(t) for t in terms)
        score += 3 * sum(1 for t in terms if t in ch["preview"].lower())  # title/opening boost
        if ch["num"] in explicit:
            score += 100
        if definitional and ch["num"] == 2:           # definitions live in Section/Rule 2
            score += 8
        if score:
            scored.append((score, ch))
    scored.sort(key=lambda x: x[0], reverse=True)
    picks = [ch for _, ch in scored[:k]]
    # always include the definitions section if nothing else surfaced it
    if definitional and not any(c["num"] == 2 for c in picks):
        d = next((c for c in entry["chunks"] if c["num"] == 2), None)
        if d:
            picks.insert(0, d)
    return picks


def render_chunks(picks):
    return "\n\n".join(f"===== {c['source']} — {c['label']} =====\n{c['text']}" for c in picks)


def toc_line(c):
    return f"{c['label']}: {c['preview']}"
