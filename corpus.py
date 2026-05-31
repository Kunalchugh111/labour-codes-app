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
    "minimum":         ["minimum wage", "minimum rate of wages", "floor wage", "fixation"],
    "floor":           ["floor wage", "minimum wage", "national floor wage"],
    "deduction":       ["deductions", "deduct", "recovery", "fines"],
    "overtime":        ["over time", "overtime wages", "extra hours", "working hours"],
    "inspector":       ["inspector-cum-facilitator", "facilitator", "inspection"],
    "facilitator":     ["inspector-cum-facilitator", "inspector", "inspection"],
    "register":        ["registers", "records", "muster roll", "wage register", "returns"],
    "return":          ["returns", "annual return", "filing"],
    "fixed":           ["fixed term", "fixed-term", "fixed term employment", "ftc"],
    "appointment":     ["letter of appointment", "appointment letter", "offer letter"],
    "gig":             ["gig worker", "platform worker", "aggregator"],
    "platform":        ["platform worker", "gig worker", "aggregator"],
    "unorganised":     ["unorganized", "unorganised worker", "informal sector"],
    "pension":         ["superannuation", "epfo", "provident fund"],
    "child":           ["child labour", "adolescent", "young person", "minor"],
    "women":           ["woman", "female", "night shift", "creche"],
    "equal":           ["equal remuneration", "equal pay", "discrimination", "gender"],
    "discrimination":  ["discriminate", "gender", "equal remuneration"],
    "accident":        ["accidents", "dangerous occurrence", "injury"],
    "canteen":         ["canteens", "welfare facility"],
    "creche":          ["crèche", "creches", "child care", "women"],
    "holiday":         ["holidays", "national holiday", "weekly off", "rest day"],
    "closure":         ["close down", "shutting down", "winding up", "lockout"],
    "registration":    ["register", "registered", "license", "licence"],
    "safety":          ["occupational safety", "health and safety", "osh", "hazardous"],
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
        cand = None
        if len(clean) >= 5 and clean not in STOP and clean not in LEGAL_VOCABULARY:
            m = get_close_matches(clean, LEGAL_VOCABULARY, n=1, cutoff=0.9)
            if m:
                w = m[0]
                # only treat as a genuine typo: same first letter, near-equal length,
                # and NOT a mere plural/singular variant of a real word
                plural = (clean.rstrip("s") == w.rstrip("s")
                          or clean + "s" == w or w + "s" == clean)
                if (w != clean and w[0] == clean[0]
                        and abs(len(w) - len(clean)) <= 2 and not plural):
                    cand = w
        if cand:
            corrections.append((token, cand))
            corrected_tokens.append(cand)
        else:
            corrected_tokens.append(token)
    return " ".join(corrected_tokens), corrections


# Provision headings. Codes/old-Acts: "N." / "NA." at a line start (captures sub-lettered
# sections like 25F). Central Rules additionally require a "N. Title.-" shape, so embedded
# numbered lists (repealed-rule lists, form fields, first-aid items) can't pose as rules.
_HEAD_CODE = re.compile(r"(?m)^\s{0,4}(\d{1,3})([A-Z]{0,2})\.\s")
_HEAD_RULE = re.compile(r"(?m)^\s{0,4}(\d{1,3})([A-Z]{0,2})\.\s+[A-Z][^\n]{0,160}?\.\s*-")
# A standalone "FORM-I" / "FORM-XXI." heading line — marks the start of the form templates.
_FORMS_TAIL = re.compile(r"(?m)^\s*FORM[ -][IVXLCDM\d]+\.?\s*$")


def _split_numbered(text, kind="code"):
    """Split a body into (label, segment) per provision. Acceptance is monotonic with
    small-gap tolerance — a single missed/garbled heading never collapses the rest of the
    document into one giant chunk, and resets (lists that restart at 1) are ignored."""
    pat = _HEAD_RULE if kind == "rules" else _HEAD_CODE
    # Rules headings carry a "Title.-" so they're trustworthy — tolerate big gaps (some
    # rule numbers go unmatched). Code/old-Act headings are barer, so stay conservative.
    max_gap = 25 if kind == "rules" else 3
    cands = [(int(m.group(1)), m.group(2), m.start()) for m in pat.finditer(text)]
    items, last, open_at, open_lbl = [], None, None, None
    for num, suf, pos in cands:
        if last is None:
            accept = num <= 3                              # sequence must start at the top
        else:
            ln, ls = last
            accept = (num == ln and suf > ls) or (0 < num - ln <= max_gap)
        if not accept:
            continue
        if open_at is not None:
            items.append((open_lbl, text[open_at:pos]))
        open_at, open_lbl, last = pos, f"{num}{suf}", (num, suf)
    if open_at is not None:
        items.append((open_lbl, text[open_at:].strip()))
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


def _clean_title(t: str) -> str:
    return re.sub(r"\s+", " ", t).strip().strip(".,;:-").strip()


def _extract_title(seg: str, kind: str):
    """Pull a provision's marginal title from its own text. Rules read 'N. Title.-'; old
    Acts read 'N. Title <newline/(1)> body'. Returns None when there's no clean heading
    (e.g. the 2020 Codes, whose titles come from the precomputed section_titles map)."""
    head = re.sub(r"^\s*\d{1,3}[A-Z]{0,2}\.\s*", "", seg[:240], count=1).lstrip()
    if kind == "rules":
        m = re.match(r"([A-Z][^\n]{2,140}?)\.\s*-", head)
        return _clean_title(m.group(1)) if m else None
    m = re.match(r"([A-Z][A-Za-z][^\n]{2,108}?)\s*(?:\.\s*-|\n|\(1\)|$)", head)
    if not m:
        return None
    cand = _clean_title(m.group(1))
    return cand if 2 < len(cand) <= 90 else None


def parse_doc(text, kind, titles=None):
    label = "Section" if kind == "code" else "Rule"
    sched_match = re.search(r"THE\s+[A-Z]+\s+SCHEDULE", text)
    body = text[: sched_match.start()] if sched_match else text
    tail = text[sched_match.start():] if sched_match else ""
    chunks = []
    for lbl, seg in _split_numbered(body, kind):
        seg = seg.strip()
        # The final rule has no closing heading, so it can swallow the trailing FORM
        # templates. Only when a segment is implausibly long, cut it at the first
        # standalone "FORM-<id>" heading (real long rules have no such heading inside).
        if len(re.findall(r"\S+", seg)) > 4000:
            seg = _FORMS_TAIL.split(seg, 1)[0].strip()
        num = int(re.match(r"\d+", lbl).group())
        # 2020 Codes pass a precomputed margin-title map (inline would grab body prose);
        # Rules / old-Acts carry a real inline heading, so extract it from the text.
        title = titles.get(str(num)) if titles is not None else _extract_title(seg, kind)
        chunks.append({"label": f"{label} {lbl}", "num": num, "title": title,
                       "text": seg, "preview": _preview(seg)})
    for title, seg in _schedules(tail):
        chunks.append({"label": title, "num": None, "title": None,
                       "text": seg, "preview": _preview(seg)})
    return chunks


def _read(name):
    p = PROCESSED / name
    return p.read_text(encoding="utf-8") if p.exists() else None


def _section_titles():
    p = PROCESSED / "section_titles.json"
    try:
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    except Exception:
        return {}


def load_corpus():
    cfg = json.loads((ROOT / "corpus_config.json").read_text())
    all_titles = _section_titles()
    corpus: dict = {}
    for c in cfg["codes"]:
        statute = _read(c["statute_file"])
        rules = _read(c["central_rules"]["file"])
        if not statute and not rules:
            continue
        entry: dict = {"meta": c, "chunks": []}
        if statute:
            for ch in parse_doc(statute, "code", titles=all_titles.get(c["statute_file"], {})):
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
    title = (ch.get("title") or "").lower()
    raw = 0.0
    for t in terms:
        c = low.count(t)
        if c:
            raw += min(c, 3)          # saturate repeated terms
            if t in prev:
                raw += 1.5            # reward early / heading mentions
        if title and t in title:
            raw += 2.5                # a hit in the provision's title is a strong topical signal
    # length-normalise so long definition/admin chunks don't dominate everything
    score = raw / (1.0 + math.log(1.0 + _wlen(ch)))
    if ch["num"] == 2 and ch["label"].startswith("Section") and not definitional:
        score *= 0.5                  # the definitions section is a noise magnet
    if definitional and ch["num"] == 2:
        score += 2.0
    if ch["num"] in explicit:
        score += 1000.0               # user named this Section/Rule explicitly
    return score


def _score_list(chunks: list[dict], query: str, boost: str = ""):
    terms = _terms(query + (" " + boost if boost else ""))
    explicit = {int(n) for n in re.findall(r"(?:section|rule)\s+(\d{1,3})", query.lower())}
    definitional = bool(re.search(r"\b(defin|meaning|means|what is|who is)\b", query.lower()))
    scored = [(_score_chunk(ch, terms, explicit, definitional), ch) for ch in chunks]
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored, definitional


def _scored(entry: dict, query: str, boost: str = ""):
    return _score_list(entry["chunks"], query, boost)


def _code_relevance(entry: dict, query: str) -> float:
    # sum of the top-3 chunk scores — a truly relevant code has several strong hits,
    # a noise code has at most one mediocre one. Routing uses the ORIGINAL query only
    # (no boost), so an LLM keyword expansion can never knock a relevant code out.
    scored, _ = _scored(entry, query)
    return sum(s for s, _ in scored[:3])


def search(entry: dict, query: str, k: int = 8, min_score: float = _MIN_SCORE,
           boost: str = "") -> list[dict]:
    scored, definitional = _scored(entry, query, boost)
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


def _kept_codes(corpus_dict: dict, query: str) -> set:
    # Codes whose best match clears the gate (best code always kept).
    tops = {cid: _code_relevance(e, query) for cid, e in corpus_dict.items()}
    best = max(tops.values(), default=0.0)
    definitional = bool(re.search(r"\b(defin|meaning|means|what is|who is)\b", query.lower()))
    gate = max(best * (_GATE_REL_DEF if definitional else _GATE_REL), _GATE_ABS)
    return {cid for cid in corpus_dict if tops[cid] >= gate or tops[cid] >= best}


def search_all(corpus_dict: dict, query: str, k: int = 8, boost: str = "") -> dict:
    # Route from the ORIGINAL query. An optional `boost` (e.g. LLM-expanded legal
    # keywords) may ADD a code the original query missed — via the union below — but can
    # never drop one, since routing on the bare query is always part of the kept set.
    keep = _kept_codes(corpus_dict, query)
    if boost:
        keep |= _kept_codes(corpus_dict, (query + " " + boost).strip())
    out = {}
    for cid, entry in corpus_dict.items():
        chunks = search(entry, query, k=k, boost=boost) if cid in keep else []
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


# ── Full-corpus index: verify quotes & resolve citations to the real provision ───
_NAME_STOP = {"the", "on", "and", "of", "for", "to", "in", "a", "an", "central", "rules", "rule"}
_FULLNORM_CACHE: dict = {}
_INDEX_CACHE: dict = {}


def _name_tokens(name: str) -> set:
    # keep 'code'/'act'/'regulations' — they distinguish a current Code from an old Act
    return {w for w in re.findall(r"[a-z]+", (name or "").lower()) if w not in _NAME_STOP}


def full_corpus_norm(corpus_dict: dict) -> str:
    """Normalised text of the ENTIRE corpus (Codes + Rules + old Acts), cached. A quote is
    'real statute' iff it appears here — used so retrieval misses don't cause false ⚠ flags."""
    key = id(corpus_dict)
    if key not in _FULLNORM_CACHE:
        parts = []
        for e in corpus_dict.values():
            parts += [ch["text"] for ch in e["chunks"]]
            for oa in e.get("old_acts", []):
                parts += [ch["text"] for ch in oa["chunks"]]
        _FULLNORM_CACHE[key] = normalize_for_match(" ".join(parts))
    return _FULLNORM_CACHE[key]


def _index(corpus_dict: dict):
    """Build (provisions, resolvers): provisions[(key, kind, num)] -> text;
    resolvers = [(key, name_token_set)] for matching a citation's Code/Act name."""
    key = id(corpus_dict)
    if key in _INDEX_CACHE:
        return _INDEX_CACHE[key]
    provisions, resolvers, titles = {}, [], {}

    def add(k, name, chunks):
        resolvers.append((k, _name_tokens(name)))
        for ch in chunks:
            if ch.get("num") is not None:
                kind = "rule" if ch["label"].lower().startswith("rule") else "section"
                provisions.setdefault((k, kind, ch["num"]), ch["text"])
                if ch.get("title"):
                    titles.setdefault((k, kind, ch["num"]), ch["title"])

    for cid, e in corpus_dict.items():
        m = e["meta"]
        add(cid, f'{m["title"]} {m["short"]}', e["chunks"])
        for oa in e.get("old_acts", []):
            add("old:" + oa["meta"]["slug"], oa["meta"]["title"], oa["chunks"])
    _INDEX_CACHE[key] = (provisions, resolvers, titles)
    return provisions, resolvers, titles


def _resolve(corpus_dict: dict, citation: str):
    """Resolve a citation like 'Section 62 — The Code on Social Security, 2020' /
    'Rule 50 — Industrial Relations Code' to an index key (best, kind, num). ('25N'->§25.)"""
    if not citation:
        return None
    m = re.search(r"\b(section|rule|regulation)\s+(\d{1,3})", citation.lower())
    if not m:
        return None
    kind = "rule" if m.group(1) in ("rule", "regulation") else "section"
    num = int(m.group(2))
    name = re.split(r"[—–-]", citation, 1)
    qt = _name_tokens(name[1] if len(name) > 1 else citation)
    _, resolvers, _ = _index(corpus_dict)
    best, score = None, 0
    for k, toks in resolvers:
        s = len(qt & toks)
        if s > score:
            best, score = k, s
    return (best, kind, num) if best is not None and score >= 1 else None


def lookup_citation(corpus_dict: dict, citation: str):
    """The actual statutory text for a citation, or None if it can't be resolved."""
    r = _resolve(corpus_dict, citation)
    return _index(corpus_dict)[0].get(r) if r else None


def lookup_title(corpus_dict: dict, citation: str):
    """The provision's marginal title for a citation (e.g. 'Floor wage'), or None."""
    r = _resolve(corpus_dict, citation)
    return _index(corpus_dict)[2].get(r) if r else None


_MAX_CHUNK_CHARS = 3000


def _trim(text: str) -> str:
    if len(text) <= _MAX_CHUNK_CHARS:
        return text
    cut = text[:_MAX_CHUNK_CHARS]
    last_stop = max(cut.rfind(". "), cut.rfind(".\n"))
    return (cut[:last_stop + 1] if last_stop > _MAX_CHUNK_CHARS // 2 else cut) + " [...]"


def _hdr(c: dict) -> str:
    t = c.get("title")
    return f"{c['source']} — {c['label']}" + (f": {t}" if t else "")


def render_chunks(picks: list[dict]) -> str:
    return "\n\n".join(f"===== {_hdr(c)} =====\n{_trim(c['text'])}" for c in picks)


def render_all_results(all_results: dict) -> str:
    parts = []
    for cid, res in all_results.items():
        if res["found"]:
            chunks_text = render_chunks(res["chunks"])
            sep = "=" * 64
            parts.append(f"{sep}\nCODE: {res['meta']['title']}\n{sep}\n{chunks_text}")
    return "\n\n".join(parts)


def toc_line(c: dict) -> str:
    t = c.get("title")
    return f"{c['label']}" + (f" — {t}" if t else "") + f": {c['preview']}"
