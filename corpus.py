"""
corpus.py — load the processed code/rules text, split it into citable chunks
(Sections, Rules, Schedules), and retrieve only the slices relevant to a query.
"""
import json
import math
import os
import re
from dataclasses import dataclass
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
    # Normally the sequence must start at the top (≤3). But if a document's opening heading is
    # garbled/missed and the first clean one is, say, 4, requiring ≤3 would accept nothing and
    # drop the WHOLE document. Fall back to the smallest number actually present so it still splits.
    first_max = 3 if any(n <= 3 for n, _, _ in cands) else min((n for n, _, _ in cands), default=3)
    items, last, open_at, open_lbl = [], None, None, None
    for num, suf, pos in cands:
        if last is None:
            accept = num <= first_max                      # sequence must start at the top
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


# ── Extraction-artifact scrubbing ────────────────────────────────────────────
# The gazette PDFs print running page headers and side-margin notes that the text
# extractor interleaves INTO the body (e.g. "36 THE GAZETTE OF INDIA EXTRAORDINARY
# [P ART II—", a stray "67 of 1957.", and a section's marginal title split across
# lines). These pollute both the quoted statute shown to the user and the model's
# grounding, so strip them at load time.
_GAZETTE_RE = re.compile(
    r'[ \t]*(?:SEC\.\s*\d+\s*\]\s*)?(?:\d{1,4}\s+)?THE\s+GAZETTE\s+OF\s+INDIA\s+EXTRAORDINARY'
    r'(?:\s*\[\s*P\s*ART\s+[IVXLCDM]+\s*[—–-]*|\s*\d{0,4})?', re.I)
_AMEND_REF_RE = re.compile(r'(?m)^[ \t]*\d{1,3}\s+of\s+\d{4}\.?[ \t]*$')


def _norm_title(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", (s or "").lower())).strip()


def _strip_marginal_titles(text: str, titles_norm: set) -> str:
    """Drop runs of lines that exactly reconstruct a known section title — those are
    side-margin notes the extractor dumped mid-body, never real sentence text."""
    if not titles_norm:
        return text
    lines = text.split("\n")
    out, i = [], 0
    while i < len(lines):
        span = 0
        for k in range(min(6, len(lines) - i), 0, -1):       # greedy: longest run first
            joined = " ".join(l.strip() for l in lines[i:i + k] if l.strip())
            if _norm_title(joined) in titles_norm:
                span = k
                break
        if span:
            i += span
        else:
            out.append(lines[i])
            i += 1
    return "\n".join(out)


def _scrub_chunks(chunks: list[dict]) -> None:
    """In-place: remove gazette headers, stray amendment refs, and misplaced marginal
    titles from every chunk's text, then refresh its preview."""
    titles_norm = {t for ch in chunks if (t := _norm_title(ch.get("title")))
                   and len(t.split()) >= 2 and len(t) >= 10}
    for ch in chunks:
        txt = _GAZETTE_RE.sub(" ", ch["text"])
        txt = _AMEND_REF_RE.sub("", txt)
        txt = _strip_marginal_titles(txt, titles_norm)
        txt = re.sub(r"[ \t]+\n", "\n", txt)
        txt = re.sub(r"\n{3,}", "\n\n", txt).strip()
        ch["text"], ch["preview"] = txt, _preview(txt)


_AMEND_LIST_RE = re.compile(r"LIST OF AMENDING ACTS", re.I)
_ENACT_RE = re.compile(r"BE\s+it\s+enacted\b[^\n]*", re.I)
# A gazette amendment-footnote LINE: starts with "N." and carries amendment/citation language
# ("Subs. by", "Ins. by", "omitted by Act …", "(w.e.f. …)"). These blocks sit at page
# boundaries and their numbers continue the real section sequence, so _split_numbered's
# small-gap rule otherwise accepts them as Sections (EPF §3–§6 were such footnotes). Real
# section headings ("1. Short title, extent and application.—") carry none of these tokens.
_FOOTNOTE_RE = re.compile(
    r"(?m)^\s*\d{1,3}\.\s+.*\b(?:Subs\.|Ins\.|ibid|w\.e\.f\.|by Act\s+\d|by Reg\.|"
    r"omitted|substituted|inserted|re-lettered|re-numbered|The words|The proviso|"
    r"The figures|The brackets|The Explanation|s\.\s*\d+,\s*for).*$")


def _strip_preamble(text: str) -> str:
    """Cut an old-Act gazette's front matter (title page, numbered 'LIST OF AMENDING ACTS',
    abbreviations, 'ARRANGEMENT OF SECTIONS' TOC) by jumping to the enacting clause — so
    `_split_numbered` doesn't read those numbered lines as Sections 1..N (EPF 1952's §1–15 were
    amendment-list entries). Scoped to the 'LIST OF AMENDING ACTS' marker (EPF, Industrial
    Disputes); returns the text unchanged otherwise."""
    if not _AMEND_LIST_RE.search(text):
        return text
    m = _ENACT_RE.search(text)
    return text[m.end():] if m else text


def parse_doc(text, kind, titles=None, is_old=False):
    # Old repealed-Act gazette texts carry amendment FOOTNOTES interleaved through the body
    # ('N. Subs./Ins. by Act … (w.e.f. …)', 'The words … omitted'); their numbers continue the
    # section sequence, so _split_numbered otherwise mis-reads them as Sections (and prefixes real
    # titles with footnote text). Strip them — and the amending-acts preamble — for OLD Acts only.
    # The 2020 Codes/Rules are clean and stay byte-identical (they feed the embedding index); old
    # Acts are never embedded, so this needs no index rebuild.
    if is_old:
        text = _FOOTNOTE_RE.sub("", _strip_preamble(text))
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
    _scrub_chunks(chunks)
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
            chunks = parse_doc(txt, "code", is_old=True)
            for ch in chunks:
                ch["source"] = oa["title"]
            if chunks:
                entry["old_acts"].append({"meta": oa, "chunks": chunks})
        corpus[c["id"]] = entry
    return cfg, corpus


# Real 2-letter legal abbreviations (e.g. "pf" = provident fund) drawn from SYNONYMS. The
# {3,} token floor below would otherwise drop them — and with them their whole synonym
# expansion — so "pf deduction" got zero PF signal in lexical scoring. Whitelist these so a
# 2-char token is kept only when it's a known term, not for arbitrary junk.
_SHORT_TERMS = {w for k, vs in SYNONYMS.items() for w in ([k] + list(vs)) if len(w) == 2}

def _terms(q: str) -> list[str]:
    base = [w for w in re.findall(r"[a-z]{2,}", q.lower())
            if w not in STOP and (len(w) >= 3 or w in _SHORT_TERMS)]
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


# ── Definition extraction ──────────────────────────────────────────────────
# A code's Section 2 is one long alphabetical list of '(x) "term" means …' clauses
# (13k–46k chars). For a "what is X" query we must surface the ONE clause the user
# asked about — dumping-then-truncating the whole list buries the answer past the
# excerpt cap, which made the model report a real definition as "not defined".
# '(x) "term" means …' — tolerate an interposed parenthetical such as
# '"lay-off" (with its grammatical variations …) means …' between the term and the verb.
_DEFN_CLAUSE = re.compile(
    r'\(\s*[a-z0-9]{1,4}\s*\)\s*[“"]([^”"]{2,60})[”"]\s*(?:\([^)]{0,80}\)\s*)?(means|includes|shall)',
    re.I)
# A query is "definitional" when it asks what a term means. NB the prefix 'defin' must NOT be
# followed by \b — 'define'/'definition' have letters after it, so a trailing boundary (the old
# bug) made this never fire for those words; the phrase triggers keep their boundary.
_DEFINITIONAL_RE = re.compile(r"\bdefin|\b(?:meaning|means|what is|what does|who is)\b")


def _split_definitions(section2_text: str) -> list[tuple[str, str]]:
    """Split a Section 2 body into [(term, clause_text)]. Each clause runs from its
    own '(x) "term" means' marker up to the next clause marker."""
    marks = list(_DEFN_CLAUSE.finditer(section2_text))
    out = []
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(section2_text)
        term = re.sub(r"\s+", " ", m.group(1)).strip().lower()
        clause = re.sub(r"\s+", " ", section2_text[m.start():end]).strip()
        out.append((term, clause))
    return out


def _definition_terms(query: str) -> list[str]:
    """The term(s) a definitional query is asking about — the quoted phrase if any,
    else the content words after 'define/what is/meaning of'."""
    ql = query.lower()
    quoted = re.findall(r"[“\"']([a-z][a-z &/\-]{1,40})[”\"']", ql)
    if quoted:
        return [q.strip() for q in quoted]
    m = re.search(r"(?:define|definition of|meaning of|what is|what does|who is)\s+"
                  r"(?:an?\s+|the\s+)?([a-z][a-z &/\-]{1,40}?)"
                  r"(?:\s+(?:mean|defined|under|in|as per|according)\b|[?.,]|$)", ql)
    if m:
        return [m.group(1).strip()]
    return [w for w in re.findall(r"[a-z]{4,}", ql) if w not in STOP][:3]


def define_chunk(entry: dict, query: str):
    """If `query` asks for a definition this Code's Section 2 actually carries, return a
    focused synthetic chunk with just the matching clause(s) — else None. The result
    looks like a normal chunk so it renders/cites as 'Section 2'."""
    s2 = next((c for c in entry["chunks"]
               if c.get("num") == 2 and c["label"].startswith("Section")), None)
    if not s2:
        return None
    defs = _split_definitions(s2["text"])
    if not defs:
        return None
    wanted = _definition_terms(query)
    hits = []
    for w in wanted:
        exact = [(t, c) for t, c in defs if t == w]
        partial = [(t, c) for t, c in defs if w in t or t in w]
        for t, c in (exact or partial):
            if (t, c) not in hits:
                hits.append((t, c))
    if not hits:
        return None
    lead = re.match(r"\s*\d+\.\s*(?:\(1\)\s*)?In this Code[^()]*?—", s2["text"])
    text = ((lead.group(0).strip() + "\n") if lead else "") + \
        "\n".join(c for _, c in hits[:4])
    terms_str = ", ".join(f'"{t}"' for t, _ in hits[:4])
    return {**s2, "text": text, "preview": _preview(text),
            "title": (s2.get("title") or "Definitions") + f" — {terms_str}",
            "_definition": True}


_MIN_SCORE = 0.45      # floor on the length-normalised score
_GATE_REL  = 0.8       # a code must reach this fraction of the best code's relevance…
_GATE_REL_DEF = 0.5    # …relaxed for definitional queries (cross-code comparison is wanted)
_GATE_ABS  = 1.5       # …and this absolute relevance, to be included (best code always kept)
_SEM_ROUTE_GATE = 0.40 # non-lexical modes: keep any code whose best sub-section cosine clears this
_SEM_ROUTE_FLOOR = 0.25 # …and always the single best-semantic code above this floor (≤1 extra code)


def _wlen(ch: dict) -> int:
    w = ch.get("_wlen")
    if w is None:
        w = len(re.findall(r"\S+", ch["text"])) or 1
        ch["_wlen"] = w
    return w


# Optional semantic-similarity hook, installed by embeddings.enable(); None ⇒ pure
# keyword search. Signature: (chunk, query) -> cosine in roughly [0, 0.5].
_SEMANTIC = None
# Pooled variant (max over whole + sub-section vectors), also installed by embeddings.enable().
# Used by the embeddings_primary / fusion modes and by semantic routing; lexical mode and the
# routing _combined_score deliberately keep the plain whole-chunk _SEMANTIC, so lexical is
# byte-identical regardless of multi-vector indexing.
_SEMANTIC_POOLED = None
# Weight on the semantic bonus. Titan cosines for a real topical match run ~0.1–0.3
# while the length-normalised keyword score tops out near ~2–3, so this scale brings
# a strong semantic hit to a comparable magnitude without letting it dominate an
# explicit keyword/title match.
_SEMANTIC_WEIGHT = 6.0


# ── Retrieval mode & tunables ────────────────────────────────────────────────
# A single switch so the SAME pipeline can run different ranking strategies and be
# A/B-benchmarked (scripts/eval_retrieval_ab.py). The DEFAULT `lexical` mode is
# byte-identical to the historical behaviour: score = lexical + 6.0*cosine, with
# every legacy patch (the §2 penalty, _CODE_ANCHORS routing, the Rules-slot
# reservation) on. The per-crutch flags let the benchmark retire a patch by flipping
# a bool rather than editing scoring logic.
@dataclass
class RetrievalConfig:
    mode: str = "lexical"            # lexical | embeddings_primary | fusion | rerank
    candidate_n: int = 30            # top-N candidates kept before fusion/rerank truncation
    semantic_weight: float = _SEMANTIC_WEIGHT   # lexical-mode cosine weight (today's 6.0)
    rrf_k: int = 20                  # Reciprocal Rank Fusion constant (fusion mode)
    embed_lex_weight: float = 0.05   # weight on lexical as a tie-breaker in embeddings_primary
    use_s2_penalty: bool = True      # §2 (definitions) ×0.5 noise penalty
    use_code_anchors: bool = True    # _CODE_ANCHORS force-keep in routing
    reserve_rules: bool = True       # reserve ≥2 slots for relevant Rules

    @classmethod
    def from_env(cls) -> "RetrievalConfig":
        return cls(mode=os.environ.get("RETRIEVAL_MODE", "lexical").strip().lower() or "lexical")


_CFG = RetrievalConfig.from_env()


def set_config(cfg: RetrievalConfig) -> None:
    """Swap the active retrieval config (used by the A/B benchmark to sweep modes)."""
    global _CFG
    _CFG = cfg


def get_config() -> RetrievalConfig:
    return _CFG


def _lexical_score(ch: dict, terms: list[str]) -> float:
    """Length-normalised keyword score: saturated term counts, plus bonuses for a hit in
    the preview (early/heading mention) and in the provision's marginal title."""
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
    return raw / (1.0 + math.log(1.0 + _wlen(ch)))


def _semantic_score(ch: dict, query: str) -> float:
    """Cosine(query, WHOLE chunk) via the embeddings hook; 0.0 when no index is loaded.
    Used by lexical mode and routing — unaffected by multi-vector indexing."""
    return _SEMANTIC(ch, query) if (_SEMANTIC is not None and query) else 0.0


def _semantic_pooled_score(ch: dict, query: str) -> float:
    """Max-pooled semantic score (whole + sub-section vectors), so a paraphrase matching one
    clause of a long Section scores on that clause. Falls back to the whole-chunk score when
    multi-vector isn't installed. Used by the embeddings_primary / fusion modes."""
    if _SEMANTIC_POOLED is not None and query:
        return _SEMANTIC_POOLED(ch, query)
    return _semantic_score(ch, query)


def _structural_adjust(score: float, ch: dict, explicit: set[int], definitional: bool) -> float:
    """Legal-structure score adjustments shared by every mode: the §2 noise penalty
    (a retirable crutch, flag-gated), the definitional §2 boost, and the explicit
    'Section N' override (always on — it honours an explicit user request)."""
    if ch["num"] == 2 and ch["label"].startswith("Section") and not definitional:
        if _CFG.use_s2_penalty:
            score *= 0.5              # the definitions section is a noise magnet
    if definitional and ch["num"] == 2:
        score += 2.0
    if ch["num"] in explicit:
        score += 1000.0              # user named this Section/Rule explicitly
    return score


def _combined_score(ch: dict, terms: list[str], explicit: set[int], definitional: bool,
                    query: str = "") -> float:
    """Historical lexical-mode score: length-normalised keyword score + semantic bonus, with
    structural adjustments. Used directly for routing and old-Act comparison so those stay on a
    stable, lexically-calibrated signal regardless of _CFG.mode."""
    base = _lexical_score(ch, terms) + _CFG.semantic_weight * _semantic_score(ch, query)
    return _structural_adjust(base, ch, explicit, definitional)


def _score_chunk(ch: dict, terms: list[str], explicit: set[int], definitional: bool,
                 query: str = "") -> float:
    if _CFG.mode == "embeddings_primary":
        base = _semantic_pooled_score(ch, query) + _CFG.embed_lex_weight * _lexical_score(ch, terms)
        return _structural_adjust(base, ch, explicit, definitional)
    # lexical (default — byte-identical to history); fusion/rerank reuse this combined score as
    # their base candidate ranking and re-order it in `search` (see _score_list dispatch).
    return _combined_score(ch, terms, explicit, definitional, query)


def _fusion_rank(chunks, terms, query, explicit, definitional):
    """Reciprocal Rank Fusion of a lexical ranking and a semantic ranking. RRF is rank-based,
    so it sidesteps the lexical/semantic score-scale mismatch that lexical mode hand-tunes with
    _SEMANTIC_WEIGHT. Structural adjustments (explicit override, §2 penalty) apply to the fused
    score so they keep dominating regardless of scale."""
    k = _CFG.rrf_k
    lex_order = sorted(chunks, key=lambda ch: _lexical_score(ch, terms), reverse=True)
    sem_order = sorted(chunks, key=lambda ch: _semantic_pooled_score(ch, query), reverse=True)
    lex_rank = {id(ch): i for i, ch in enumerate(lex_order, 1)}
    sem_rank = {id(ch): i for i, ch in enumerate(sem_order, 1)}
    out = []
    for ch in chunks:
        rrf = 1.0 / (k + lex_rank[id(ch)]) + 1.0 / (k + sem_rank[id(ch)])
        out.append((_structural_adjust(rrf, ch, explicit, definitional), ch))
    return out


def _rerank_rank(chunks, terms, query, explicit, definitional):
    """Base-rank by fusion, take the top candidate_n, reorder with the cross-encoder reranker
    (rerank.rerank, fail-soft), then apply structural adjustments. Falls back to the fusion
    ranking when the reranker is unavailable, so rerank mode never crashes or empties results."""
    fused = sorted(_fusion_rank(chunks, terms, query, explicit, definitional),
                   key=lambda x: x[0], reverse=True)
    cand = [ch for _, ch in fused[:_CFG.candidate_n]]
    order = None
    try:
        import rerank as _rr
        order = _rr.rerank(query, cand)            # [(chunk, relevance_score)] or None
    except Exception:
        order = None
    if not order:
        return fused                                # fail-soft → fusion ranking
    out = [(_structural_adjust(score, ch, explicit, definitional), ch) for ch, score in order]
    ranked = {id(ch) for _, ch in out}
    tail = [(s * 1e-6, ch) for s, ch in fused if id(ch) not in ranked]   # keep a full list
    return out + tail


def _score_list(chunks: list[dict], query: str, boost: str = "", definitional=None):
    terms = _terms(query + (" " + boost if boost else ""))
    explicit = {int(n) for n in re.findall(r"(?:section|rule)\s+(\d{1,3})", query.lower())}
    if definitional is None:                       # callers (e.g. old-Act comparison) can override
        definitional = bool(_DEFINITIONAL_RE.search(query.lower()))
    if _CFG.mode == "fusion":
        scored = _fusion_rank(chunks, terms, query, explicit, definitional)
    elif _CFG.mode == "rerank":
        scored = _rerank_rank(chunks, terms, query, explicit, definitional)
    else:                                          # lexical, embeddings_primary
        scored = [(_score_chunk(ch, terms, explicit, definitional, query), ch) for ch in chunks]
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored, definitional


def _scored(entry: dict, query: str, boost: str = ""):
    return _score_list(entry["chunks"], query, boost)


def _code_relevance(entry: dict, query: str) -> float:
    # sum of the top-3 chunk scores — a truly relevant code has several strong hits,
    # a noise code has at most one mediocre one. Routing uses the ORIGINAL query only
    # (no boost), so an LLM keyword expansion can never knock a relevant code out.
    # Routing always scores on the LEXICAL signal (lexical + semantic bonus), independent of
    # _CFG.mode, so the routing gates (_GATE_ABS and the relative gate) stay calibrated to the
    # magnitudes they were tuned for. The mode only changes WITHIN-code ranking (see `search`).
    terms = _terms(query)
    definitional = bool(_DEFINITIONAL_RE.search(query.lower()))
    explicit = {int(n) for n in re.findall(r"(?:section|rule)\s+(\d{1,3})", query.lower())}
    scored = sorted((_combined_score(ch, terms, explicit, definitional, query)
                     for ch in entry["chunks"]), reverse=True)
    return sum(scored[:3])


def search(entry: dict, query: str, k: int = 8, min_score: float = _MIN_SCORE,
           boost: str = "") -> list[dict]:
    scored, definitional = _scored(entry, query, boost)
    # The 0.45 floor is calibrated to lexical magnitudes; the semantic/fusion/rerank rankings live
    # on different scales and routing already decided this code is relevant, so only lexical mode
    # applies the absolute floor (other modes keep their top candidates).
    floor = min_score if _CFG.mode == "lexical" else 0.0
    scored = [(s, c) for s, c in scored if s >= floor]
    picks = scored[:k]

    # reserve up to 2 slots for Rules that are genuinely relevant (not noise) so the
    # procedural Rule surfaces alongside its Section
    n_rules = sum(1 for _, c in picks if c["label"].startswith("Rule"))
    if _CFG.reserve_rules and n_rules < 2 and picks:
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

    # For "what is X" queries, lead with the definition. Prefer a FOCUSED chunk holding
    # just the asked-for clause (so it isn't buried past the excerpt cap); fall back to
    # the full Section 2 when we can't pinpoint the term.
    if definitional:
        focused = define_chunk(entry, query)
        if focused is not None:
            result = [focused] + [c for c in result
                                  if not (c["num"] == 2 and c["label"].startswith("Section"))]
        elif not any(c["num"] == 2 and c["label"].startswith("Section") for c in result):
            d = next((c for c in entry["chunks"]
                      if c["num"] == 2 and c["label"].startswith("Section")), None)
            if d:
                result = [d] + result[:k - 1]

    # Industrial Relations Chapter X: the prior-permission duties to lay off / retrench /
    # close (§§78–83) only apply at 300+ workers, and THAT threshold lives in a separate
    # section — §77 "Application of this Chapter". Co-include §77 whenever a Chapter X duty
    # is surfaced, so "how many workers need permission" is answerable (the same stitch as
    # PF's rate-and-deduction). Harmless when size gating excludes the duty: §77 just states
    # the 300 cutoff, which supports a correct "below 300, no permission" answer.
    if "industrial relations" in (entry["meta"].get("short", "").lower()):
        if (any(c.get("num") in {78, 79, 80, 81, 82, 83} and c["label"].startswith("Section")
                for c in result)
                and not any(c.get("num") == 77 and c["label"].startswith("Section") for c in result)):
            s77 = next((c for c in entry["chunks"]
                        if c.get("num") == 77 and c["label"].startswith("Section")), None)
            if s77:
                result = result[:k - 1] + [s77]
        # Unfair labour practices: the prohibition (§84) and the LIST (Second Schedule) are a
        # formal pair that cite each other. When either surfaces the query is about unfair
        # labour practices, so PROMOTE both to the front — otherwise a neighbouring trade-union
        # section (e.g. §22 dispute adjudication) outranks them and gets miscited for
        # "can we stop workers forming a union".
        has_84 = any(c.get("num") == 84 and c["label"].startswith("Section") for c in result)
        has_sch2 = any("second schedule" in c.get("label", "").lower() for c in result)
        if has_84 or has_sch2:
            s84 = next((c for c in entry["chunks"]
                        if c.get("num") == 84 and c["label"].startswith("Section")), None)
            sch = next((c for c in entry["chunks"]
                        if "second schedule" in c.get("label", "").lower()), None)
            lead = [c for c in (s84, sch) if c is not None]
            rest = [c for c in result if c is not s84 and c is not sch]
            result = lead + rest
    return result[:k]


# Topical anchors — a concept that lives in ONE specific Code, so the Code must be kept
# even when generic words (deduct, pay, wages) make another Code dominate routing. This is
# the fix for "how much PF deduction" returning Wages alone: the RATE is in Social Security
# §16, but "deduct…from wages" scores Wages so high the relative gate drops Social Security.
# Deliberately narrow: only distinctive, single-Code terms (never generic ones).
_CODE_ANCHORS = [
    ("ss",    re.compile(r"\b(provident fund|pf\b|epf|gratuity|maternity benefit|"
                         r"esi\b|employees['’]? state insurance|pension|"
                         r"employees['’]? compensation|compensation|dependant|disablement|"
                         r"died|death|fatal|injur)\b", re.I)),
    ("wages", re.compile(r"\b(minimum wage|floor wage|bonus|equal remuneration)\b", re.I)),
    ("ir",    re.compile(r"\b(retrench|lay[\s-]?off|trade union|standing orders?|strike|lock[\s-]?out)\b", re.I)),
    ("osh",   re.compile(r"\b(overtime|appointment letter|annual leave|working hours|welfare officer)\b", re.I)),
]


def _anchored_codes(query: str) -> set:
    return {cid for cid, pat in _CODE_ANCHORS if pat.search(query)}


def _kept_codes(corpus_dict: dict, query: str) -> set:
    # Codes whose best match clears the gate (best code always kept).
    tops = {cid: _code_relevance(e, query) for cid, e in corpus_dict.items()}
    best = max(tops.values(), default=0.0)
    definitional = bool(_DEFINITIONAL_RE.search(query.lower()))
    gate = max(best * (_GATE_REL_DEF if definitional else _GATE_REL), _GATE_ABS)
    kept = {cid for cid in corpus_dict if tops[cid] >= gate or tops[cid] >= best}
    # Always keep a Code a distinctive concept points to (if it has any real signal),
    # so a dominant generic Code can't crowd out the one that actually governs the benefit.
    if _CFG.use_code_anchors:
        kept |= {cid for cid in _anchored_codes(query)
                 if cid in corpus_dict and tops.get(cid, 0.0) >= _GATE_ABS}
    # Semantic routing (non-lexical modes only): so a paraphrase with no statutory keyword still
    # reaches the right Code (e.g. "salary set aside for retirement" → Social Security). Keep any
    # Code with a CONFIDENT sub-section match, plus the SINGLE best semantic match above a low
    # floor (adds at most one Code, so an oblique paraphrase routes without over-routing on
    # near-ties). Lexical mode is untouched.
    if _CFG.mode != "lexical" and _SEMANTIC_POOLED is not None:
        sem = {cid: max((_semantic_pooled_score(ch, query) for ch in e["chunks"]), default=0.0)
               for cid, e in corpus_dict.items()}
        kept |= {cid for cid, s in sem.items() if s >= _SEM_ROUTE_GATE}
        best = max(sem, key=sem.get, default=None)
        if best is not None and sem[best] >= _SEM_ROUTE_FLOOR:
            kept.add(best)
    return kept


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
    # A comparison wants the SUBSTANTIVE old provision, never the definitions clause — so score
    # as non-definitional even when the query reads like "what is X" (which would otherwise
    # surface the old Act's Section 2 and bury the real change). Old Acts are never embedded and
    # comparison is a lexical-grounding task, so score on the combined (lexical) signal regardless
    # of _CFG.mode — keeping the 0.45 floor calibrated.
    terms = _terms(query)
    explicit = {int(n) for n in re.findall(r"(?:section|rule)\s+(\d{1,3})", query.lower())}
    scored = sorted(((_combined_score(ch, terms, explicit, False, query), ch) for ch in chunks),
                    key=lambda x: x[0], reverse=True)
    return [c for s, c in scored[:k] if s >= min_score]


# ── Verbatim-quote verification ──────────────────────────────────────────────
# Guardrail: confirm a cited "quote" is actually present in the statutory text we
# supplied to the model — so a fabricated/paraphrased quote can never pass as law.

def normalize_for_match(s: str) -> str:
    """Lowercase; collapse every run of non-alphanumerics to ONE space — for tolerant
    substring matching. Done in a single pass so punctuation and whitespace normalise
    identically (otherwise 'of—(a)' and 'of— (a)' yield different space counts and a
    verbatim quote fails the substring test)."""
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


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
    'Rule 50 — Industrial Relations Code' to an index key (best, kind, num).
    A lettered section (e.g. '25G', '25FF' in the repealed Acts) resolves to None: our index
    keys sections by integer, so we can't show that exact provision verbatim — and collapsing
    '25G'->§25 used to display the WRONG provision while still passing the 'verified' badge."""
    if not citation:
        return None
    m = re.search(r"\b(section|rule|regulation)\s+(\d{1,3})-?([a-z]{1,3})?", citation.lower())
    if not m:
        return None
    if m.group(3):                       # lettered section (25G/25H/25FF…) — see docstring
        return None
    kind = "rule" if m.group(1) in ("rule", "regulation") else "section"
    num = int(m.group(2))
    # Match the Code/Act name on the WHOLE citation, not just the part after the dash —
    # the model sometimes emits "Industrial Relations Code, 2020 — Section 70" (name first),
    # and a name-after-dash assumption left those citations unresolved (no source text shown).
    qt = _name_tokens(citation)
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


def _trim(text: str, query: str = "") -> str:
    """Cap a chunk at _MAX_CHUNK_CHARS. A blind head-cut buries the answer when the
    relevant passage sits deep in a long Section (definitions, §50, §13…), so when a
    query is given we keep the WINDOW around the best cluster of query terms instead."""
    if len(text) <= _MAX_CHUNK_CHARS:
        return text
    terms = [t for t in _terms(query) if len(t) >= 4] if query else []
    low = text.lower()
    hits = sorted({low.find(t) for t in terms if low.find(t) != -1})
    if hits and hits[0] >= _MAX_CHUNK_CHARS:        # relevant text is past a plain head-cut
        centre = hits[len(hits) // 2]
        half = _MAX_CHUNK_CHARS // 2
        start = max(0, centre - half)
        start = max(0, text.rfind(". ", 0, start) + 1) or start
        window = text[start:start + _MAX_CHUNK_CHARS]
        last_stop = window.rfind(". ")
        if last_stop > _MAX_CHUNK_CHARS // 2:
            window = window[:last_stop + 1]
        return "[…] " + window.strip() + " […]"
    cut = text[:_MAX_CHUNK_CHARS]
    last_stop = max(cut.rfind(". "), cut.rfind(".\n"))
    return (cut[:last_stop + 1] if last_stop > _MAX_CHUNK_CHARS // 2 else cut) + " [...]"


def _hdr(c: dict) -> str:
    t = c.get("title")
    return f"{c['source']} — {c['label']}" + (f": {t}" if t else "")


def render_chunks(picks: list[dict], query: str = "") -> str:
    # A focused definition chunk is already pinpointed — never window-trim it.
    return "\n\n".join(
        f"===== {_hdr(c)} =====\n{c['text'] if c.get('_definition') else _trim(c['text'], query)}"
        for c in picks)


def render_all_results(all_results: dict, query: str = "") -> str:
    parts = []
    for cid, res in all_results.items():
        if res["found"]:
            chunks_text = render_chunks(res["chunks"], query)
            sep = "=" * 64
            parts.append(f"{sep}\nCODE: {res['meta']['title']}\n{sep}\n{chunks_text}")
    return "\n\n".join(parts)


def toc_line(c: dict) -> str:
    t = c.get("title")
    return f"{c['label']}" + (f" — {t}" if t else "") + f": {c['preview']}"
