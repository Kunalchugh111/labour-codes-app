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

# ── Synonym expansion for better recall ──────────────────────────────────────
# Maps a canonical term to a list of related words that should expand the search.
SYNONYMS: dict[str, list[str]] = {
    "retrench":        ["retrenchment", "retrenched", "retrenching", "layoff", "lay-off"],
    "terminate":       ["termination", "terminated", "dismissal", "dismiss", "removal", "discharge"],
    "wage":            ["wages", "remuneration", "salary", "pay", "payment", "earnings"],
    "employee":        ["employees", "worker", "workers", "workman", "workmen", "labourer"],
    "employer":        ["employers", "principal employer", "management", "establishment"],
    "bonus":           ["bonuses", "incentive", "ex-gratia", "performance pay"],
    "gratuity":        ["gratuities", "terminal benefit", "long service"],
    "strike":          ["strikes", "striking", "walkout", "work stoppage", "cessation of work"],
    "lockout":         ["lock-out", "lock out", "closure"],
    "union":           ["unions", "trade union", "collective bargaining", "negotiating union"],
    "contract":        ["contractor", "contractual", "outsourced", "contract labour"],
    "maternity":       ["maternal", "maternity benefit", "childbirth", "pregnancy"],
    "provident":       ["provident fund", "pf", "epf", "employees provident fund"],
    "insurance":       ["esi", "state insurance", "employees state insurance"],
    "dispute":         ["disputes", "industrial dispute", "grievance", "conciliation"],
    "compensation":    ["compensate", "damages", "liability", "compensation"],
    "notice":          ["notice period", "notification", "intimation"],
    "hours":           ["working hours", "overtime", "shift", "rest interval"],
    "leave":           ["annual leave", "sick leave", "casual leave", "earned leave"],
    "standing order":  ["certified standing orders", "service conditions"],
    "factory":         ["factories", "manufacturing", "industrial premises"],
    "welfare":         ["welfare officer", "canteen", "crèche", "facilities"],
    "migrant":         ["inter-state migrant", "migrant worker", "migrant workman"],
}


# ── Parsing helpers ───────────────────────────────────────────────────────────
def _split_numbered(text):
    """Split a block into strictly-increasing top-level numbered items."""
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
    """kind: 'code' → 'Section N'; 'rules' → 'Rule N'."""
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


# ── Loading ───────────────────────────────────────────────────────────────────
def _read(name):
    p = PROCESSED / name
    return p.read_text(encoding="utf-8") if p.exists() else None


def load_corpus():
    cfg = json.loads((ROOT / "corpus_config.json").read_text())
    corpus: dict = {}
    for c in cfg["codes"]:
        statute = _read(c["statute_file"])
        rules = _read(c["central_rules"]["file"])
        if not statute and not rules:
            continue
        entry: dict = {"meta": c, "chunks": []}
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


# ── Retrieval ─────────────────────────────────────────────────────────────────
def _terms(q: str) -> list[str]:
    """Tokenise query and expand with synonyms for better recall."""
    base = [w for w in re.findall(r"[a-z]{3,}", q.lower()) if w not in STOP]
    expanded: set[str] = set(base)
    for term in base:
        for canonical, syns in SYNONYMS.items():
            if term == canonical or term in syns:
                expanded.add(canonical)
                expanded.update(syns)
    return list(expanded)


def search(entry: dict, query: str, k: int = 12) -> list[dict]:
    """Return up to k chunks from one code+rules most relevant to the query."""
    terms = _terms(query)
    explicit = {int(n) for n in re.findall(r"(?:section|rule)\s+(\d{1,3})", query.lower())}
    definitional = bool(re.search(r"\b(defin|meaning|means|what is|who is)\b", query.lower()))

    scored: list[tuple[int, dict]] = []
    for ch in entry["chunks"]:
        low = ch["text"].lower()
        score = sum(low.count(t) for t in terms)
        score += 3 * sum(1 for t in terms if t in ch["preview"].lower())
        if ch["num"] in explicit:
            score += 100
        if definitional and ch["num"] == 2:
            score += 8
        if score:
            scored.append((score, ch))
    scored.sort(key=lambda x: x[0], reverse=True)
    picks = [ch for _, ch in scored[:k]]
    if definitional and not any(c["num"] == 2 for c in picks):
        d = next((c for c in entry["chunks"] if c["num"] == 2), None)
        if d:
            picks.insert(0, d)
    return picks


def search_all(corpus_dict: dict, query: str, k: int = 10) -> dict:
    """
    Search every loaded code simultaneously.

    Returns:
        dict: { code_id -> {"chunks": [...], "found": bool, "meta": {...}} }
    """
    return {
        cid: {"chunks": chunks, "found": bool(chunks), "meta": entry["meta"]}
        for cid, entry in corpus_dict.items()
        for chunks in [search(entry, query, k=k)]
    }


def render_chunks(picks: list[dict]) -> str:
    return "\n\n".join(
        f"===== {c['source']} — {c['label']} =====\n{c['text']}" for c in picks
    )


def render_all_results(all_results: dict) -> str:
    """
    Build the grounding text sent to the LLM:
    - Codes with hits → their chunks, grouped under a clear heading.
    - Codes with no hits → omitted from grounding (noted separately via no_provision list).
    """
    parts = []
    for cid, res in all_results.items():
        if res["found"]:
            chunks_text = render_chunks(res["chunks"])
            sep = "=" * 64
            parts.append(f"{sep}\nCODE: {res['meta']['title']}\n{sep}\n{chunks_text}")
    return "\n\n".join(parts)


def toc_line(c: dict) -> str:
    return f"{c['label']}: {c['preview']}"
