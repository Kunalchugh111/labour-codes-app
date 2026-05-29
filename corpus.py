"""
corpus.py — load the processed code/rules text, split it into citable chunks
(Sections, Rules, Schedules), and retrieve only the slices relevant to a query.
"""
import json
import math
import re
from difflib import get_close_matches
from pathlib import Path

ROOT = Path(__file__).parent
PROCESSED = ROOT / "documents" / "processed"

STOP = set("""a an the of to in for on and or by with as is are be this that any such
which under section sub clause shall means may not no it its his he him under into
from per cent rupees within where when been being under code act rules rule""".split())

SYNONYMS: dict[str, list[str]] = {
    "retrench":        ["retrenchment", "retrenched", "retrenching", "layoff", "lay-off"],
    "retrenchment":    ["retrench", "retrenched", "retrenching", "layoff", "lay-off"],
    "terminate":       ["termination", "terminated", "dismissal", "dismiss", "removal", "discharge"],
    "termination":     ["terminate", "terminated", "dismissal", "dismiss", "removal", "discharge"],
    "wage":            ["wages", "remuneration", "salary", "pay", "payment", "earnings"],
    "wages":           ["wage", "remuneration", "salary", "pay", "payment", "earnings"],
    "employee":        ["employees", "worker", "workers", "workman", "workmen", "labourer"],
    "employees":       ["employee", "worker", "workers", "workman", "workmen", "labourer"],
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
    "layoff":          ["lay-off", "lay off", "retrenchment", "retrench"],
    "dismiss":         ["dismissal", "dismissed", "termination", "terminate", "discharge"],
    "salary":          ["wages", "wage", "remuneration", "pay", "payment"],
    "workman":         ["workmen", "worker", "workers", "employee", "employees"],
    "apprentice":      ["apprenticeship", "trainee", "training"],
    "hazardous":       ["dangerous", "safety", "health risk"],
    "penalty":         ["fine", "punishment", "offence", "contravention"],
}

LEGAL_VOCABULARY = [
    "retrenchment", "termination", "dismissal", "resignation", "discharge",
    "wages", "salary", "remuneration", "earnings", "payment",
    "gratuity", "bonus", "provident", "insurance", "compensation",
    "strike", "lockout", "dispute", "conciliation", "arbitration",
    "overtime", "maternity", "paternity", "leave", "holiday",
    "notice", "contractor", "contract", "outsourcing",
    "union", "collective", "bargaining", "negotiation",
    "welfare", "migrant", "factory", "establishment",
    "standing", "order", "apprentice", "hazardous", "safety",
    "health", "inspection", "penalty", "registration", "license",
    "workman", "employee", "employer", "layoff", "closure",
    "definition", "obligation", "compliance", "procedure",
]


def correct_query(q: str) -> tuple[str, list[tuple[str, str]]]:
    tokens = q.split()
    corrections: list[tuple[str, str]] = []
    corrected_tokens: list[str] = []
    for token in tokens:
        clean = re.sub(r"[^a-z]", "", token.lower())
        if len(clean) >= 5 and clean not in STOP and clean not in LEGAL_VOCABULARY:
            matches = get_close_matches(clean, LEGAL_VOCABULARY, n=1, cutoff=0.72)
            if matches and matches[0] != clean:
                corrections.append((token, matches[0]))
                corrected_tokens.append(matches[0])
                continue
        corrected_tokens.append(token)
    return " ".join(corrected_tokens), corrections


def _split_numbered(text):
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
        # repealed Acts this Code subsumed (for "what changed" comparisons)
        entry["old_acts"] = []
        for oa in c.get("old_acts", []):
            txt = _read(oa["file"])
            if not txt:
                continue
            chunks = parse_doc(txt, "code")
            for ch in chunks:
                ch["source"] = oa["title"]
            if chunks:
                entry["old_acts"].append({"meta": oa, "chunks": chunks})
        corpus[c["id"]] = entry
    return cfg, corpus


def _terms(q: str) -> list[str]:
    base = [w for w in re.findall(r"[a-z]{3,}", q.lower()) if w not in STOP]
    expanded: set[str] = set(base)
    for term in base:
        if term in SYNONYMS:
            expanded.update(SYNONYMS[term])
        for canonical, syns in SYNONYMS.items():
            if term in syns:
                expanded.add(canonical)
                expanded.update(syns)
        if len(term) >= 5:
            for vocab_word in LEGAL_VOCABULARY:
                if vocab_word.startswith(term) and vocab_word != term:
                    expanded.add(vocab_word)
                    if vocab_word in SYNONYMS:
                        expanded.update(SYNONYMS[vocab_word])
    return list(expanded)


_MIN_SCORE = 0.45      # floor on the length-normalised score
_GATE_REL  = 0.8       # a code must reach this fraction of the best code's relevance…
_GATE_REL_DEF = 0.5    # …relaxed for definitional queries (cross-code comparison is wanted)
_GATE_ABS  = 1.5       # …and this absolute relevance, to be included (best code always kept)


def _wlen(ch: dict) -> int:
    w = ch.get("_wlen")
    if w is None:
        w = len(re.findall(r"\S+", ch["text"])) or 1
        ch["_wlen"] = w
    return w


def _score_chunk(ch: dict, terms: list[str], explicit: set[int], definitional: bool) -> float:
    low = ch["text"].lower()
    prev = ch["preview"].lower()
    raw = 0.0
    for t in terms:
        c = low.count(t)
        if c:
            raw += min(c, 3)          # saturate repeated terms
            if t in prev:
                raw += 1.5            # reward early / heading mentions
    # length-normalise so long definition/admin chunks don't dominate everything
    score = raw / (1.0 + math.log(1.0 + _wlen(ch)))
    if ch["num"] == 2 and ch["label"].startswith("Section") and not definitional:
        score *= 0.5                  # the definitions section is a noise magnet
    if definitional and ch["num"] == 2:
        score += 2.0
    if ch["num"] in explicit:
        score += 1000.0               # user named this Section/Rule explicitly
    return score


def _score_list(chunks: list[dict], query: str):
    terms = _terms(query)
    explicit = {int(n) for n in re.findall(r"(?:section|rule)\s+(\d{1,3})", query.lower())}
    definitional = bool(re.search(r"\b(defin|meaning|means|what is|who is)\b", query.lower()))
    scored = [(_score_chunk(ch, terms, explicit, definitional), ch) for ch in chunks]
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored, definitional


def _scored(entry: dict, query: str):
    return _score_list(entry["chunks"], query)


def _code_relevance(entry: dict, query: str) -> float:
    # sum of the top-3 chunk scores — a truly relevant code has several strong hits,
    # a noise code has at most one mediocre one.
    scored, _ = _scored(entry, query)
    return sum(s for s, _ in scored[:3])


def search(entry: dict, query: str, k: int = 8, min_score: float = _MIN_SCORE) -> list[dict]:
    scored, definitional = _scored(entry, query)
    scored = [(s, c) for s, c in scored if s >= min_score]
    picks = scored[:k]

    # reserve up to 2 slots for Rules that are genuinely relevant (not noise) so the
    # procedural Rule surfaces alongside its Section
    n_rules = sum(1 for _, c in picks if c["label"].startswith("Rule"))
    if n_rules < 2 and picks:
        floor = 0.45 * picks[0][0]
        chosen = {id(c) for _, c in picks}
        extra = [(s, c) for s, c in scored
                 if c["label"].startswith("Rule") and id(c) not in chosen
                 and s >= floor][:2 - n_rules]
        if extra:
            slots = [i for i, (_, c) in enumerate(picks) if not c["label"].startswith("Rule")]
            for pair in extra:
                if slots:
                    picks[slots.pop()] = pair        # replace lowest-scoring Section
                else:
                    picks.append(pair)
            picks.sort(key=lambda x: x[0], reverse=True)
            picks = picks[:k]

    result = [c for _, c in picks]

    # always include the definitions Section for "what is X" queries
    if definitional and not any(c["num"] == 2 and c["label"].startswith("Section") for c in result):
        d = next((c for c in entry["chunks"]
                  if c["num"] == 2 and c["label"].startswith("Section")), None)
        if d:
            result = [d] + result[:k - 1]
    return result[:k]


def search_all(corpus_dict: dict, query: str, k: int = 8) -> dict:
    # Route: only include codes whose best match clears the gate (best code always kept).
    tops = {cid: _code_relevance(e, query) for cid, e in corpus_dict.items()}
    best = max(tops.values(), default=0.0)
    definitional = bool(re.search(r"\b(defin|meaning|means|what is|who is)\b", query.lower()))
    gate = max(best * (_GATE_REL_DEF if definitional else _GATE_REL), _GATE_ABS)
    out = {}
    for cid, entry in corpus_dict.items():
        keep = tops[cid] >= gate or tops[cid] >= best
        chunks = search(entry, query, k=k) if keep else []
        out[cid] = {"chunks": chunks, "found": bool(chunks), "meta": entry["meta"]}
    return out


def search_old(entry: dict, query: str, k: int = 6, min_score: float = _MIN_SCORE) -> list[dict]:
    """Top provisions from the repealed Acts this Code subsumed, relevant to the query.
    Used to ground 'what changed vs the old Act' comparisons."""
    chunks = [ch for oa in entry.get("old_acts", []) for ch in oa["chunks"]]
    if not chunks:
        return []
    scored, _ = _score_list(chunks, query)
    return [c for s, c in scored[:k] if s >= min_score]


# ── Verbatim-quote verification ──────────────────────────────────────────────
# Guardrail: confirm a cited "quote" is actually present in the statutory text we
# supplied to the model — so a fabricated/paraphrased quote can never pass as law.

def normalize_for_match(s: str) -> str:
    """Lowercase, drop punctuation, collapse whitespace — for tolerant substring matching."""
    return re.sub(r"[^a-z0-9 ]", " ", re.sub(r"\s+", " ", (s or "").lower())).strip()


def quote_supported(quote: str, grounding_norm: str) -> bool:
    """True if `quote` appears in the (already-normalised) grounding text. Tolerates
    '...' elisions: every substantial fragment between elisions must be found."""
    frags = [normalize_for_match(f)
             for f in re.split(r"\.\.\.+|…|\[\s*\.\.\.\s*\]", quote or "")]
    frags = [f for f in frags if len(f) >= 25]          # ignore trivially short fragments
    if not frags:
        f = normalize_for_match(quote)
        return len(f) >= 12 and f in grounding_norm
    return all(f in grounding_norm for f in frags)


_MAX_CHUNK_CHARS = 3000


def _trim(text: str) -> str:
    if len(text) <= _MAX_CHUNK_CHARS:
        return text
    cut = text[:_MAX_CHUNK_CHARS]
    last_stop = max(cut.rfind(". "), cut.rfind(".\n"))
    return (cut[:last_stop + 1] if last_stop > _MAX_CHUNK_CHARS // 2 else cut) + " [...]"


def render_chunks(picks: list[dict]) -> str:
    return "\n\n".join(
        f"===== {c['source']} — {c['label']} =====\n{_trim(c['text'])}" for c in picks
    )


def render_all_results(all_results: dict) -> str:
    parts = []
    for cid, res in all_results.items():
        if res["found"]:
            chunks_text = render_chunks(res["chunks"])
            sep = "=" * 64
            parts.append(f"{sep}\nCODE: {res['meta']['title']}\n{sep}\n{chunks_text}")
    return "\n\n".join(parts)


def toc_line(c: dict) -> str:
    return f"{c['label']}: {c['preview']}"
