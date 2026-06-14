"""
embeddings.py — optional semantic-retrieval layer for the corpus.

Pure keyword search (corpus._score_chunk) misses questions phrased differently
from the statute — e.g. "what happens when a company lets workers go to cut
costs" shares no words with "retrenchment means termination … of a worker". This
module adds a Bedrock Titan embedding for every chunk and blends cosine
similarity into the existing lexical score (HYBRID — it augments, never
replaces, keyword search).

It is strictly optional and fail-soft: with no Bedrock credentials, no numpy, or
any error, enable() is a no-op and the app falls back to the keyword path
unchanged. The chunk index is cached to documents/processed/embeddings.npz keyed
by a hash of each chunk's text, so it is built once and only re-embeds chunks
whose text actually changed.

Wiring (done in app.py at startup, and by the eval harness):
    import embeddings; embeddings.enable(LOADED)
That attaches a vector to each chunk and installs corpus._SEMANTIC so the scorer
can add the semantic bonus; search_all/search are otherwise untouched.
"""
import os
import re
import json
import hashlib
import threading
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).parent
INDEX_PATH = ROOT / "documents" / "processed" / "embeddings.npz"
MODEL_ID = os.environ.get("BEDROCK_EMBED_MODEL", "amazon.titan-embed-text-v2:0")
_MAX_INPUT_CHARS = 28000          # Titan v2 input ceiling (~8192 tokens)
_DIM = 1024                        # Titan v2 embedding dimension

# Multi-vector granularity: a long Section's single vector is "diluted" (one 1024-d point
# for 3k+ chars), so a paraphrase matching ONE sub-clause scores low. For chunks above this
# size we additionally embed each sub-section and max-pool at query time, so the best-matching
# clause drives the score. Whole-chunk vectors are unchanged, so lexical mode is unaffected.
_SEG_MIN_CHARS = 1200             # only sub-segment chunks longer than this
_SEG_MAX = 12                     # cap sub-vectors per chunk (cost control)
_SUBSEC_RE = re.compile(r"(?:^|\s)\(\s*\d{1,2}\s*\)\s")   # "(1) ", "(2) " sub-section markers

_local = threading.local()


def _has_key() -> bool:
    return bool(os.environ.get("AWS_BEARER_TOKEN_BEDROCK"))


def _client():
    """One bedrock-runtime client per thread (safe for the parallel index build)."""
    c = getattr(_local, "client", None)
    if c is None:
        import boto3
        c = boto3.client("bedrock-runtime",
                         region_name=os.environ.get("AWS_REGION", "us-east-1"))
        _local.client = c
    return c


def _embed_one(text: str):
    """Return a Titan embedding (list[float]) for one text, or None on failure."""
    try:
        r = _client().invoke_model(
            modelId=MODEL_ID,
            body=json.dumps({"inputText": text[:_MAX_INPUT_CHARS]}))
        return json.loads(r["body"].read())["embedding"]
    except Exception:
        return None


def _chunk_key(ch: dict) -> str:
    h = hashlib.sha1(ch["text"].encode("utf-8")).hexdigest()[:16]
    return f'{ch.get("source","")}|{ch.get("label","")}|{h}'


def _embed_text_for(ch: dict) -> str:
    """What we embed for a chunk: its title + body, so the marginal heading
    (often the most query-like phrase) contributes to the vector."""
    title = ch.get("title") or ""
    return (title + ". " + ch["text"]) if title else ch["text"]


def _segments(ch: dict) -> list[str]:
    """Sub-section texts to embed for a long chunk (each prefixed with the chunk's title for
    context), or [] for short chunks. Splits on '(1)/(2)/(3)' sub-section markers; falls back
    to fixed overlapping windows when a long chunk has no such structure."""
    text = ch["text"]
    if len(text) < _SEG_MIN_CHARS:
        return []
    title = ch.get("title") or ""
    marks = [m.start() for m in _SUBSEC_RE.finditer(text)]
    segs = []
    if len(marks) >= 2:
        bounds = marks + [len(text)]
        segs = [text[a:b].strip() for a, b in zip(bounds, bounds[1:]) if len(text[a:b].strip()) >= 200]
    if len(segs) < 2:                                  # no clear sub-section structure → windows
        segs = [text[i:i + 1500].strip() for i in range(0, len(text), 1200)]
    return [((title + ". " + s) if title else s) for s in segs[:_SEG_MAX]]


# ── query embedding (cached so search_all's 4 per-code calls embed once) ──────
@lru_cache(maxsize=512)
def embed_query(query: str):
    import numpy as np
    v = _embed_one(query)
    return None if v is None else np.asarray(v, dtype="float32")


def _units(chunks: list[dict]) -> list[tuple]:
    """Every embedding unit as (key, text): each chunk's whole text, plus its sub-section
    segments for long chunks. Sub-segment keys are '<chunk_key>#s<i>'."""
    units = []
    for ch in chunks:
        k = _chunk_key(ch)
        units.append((k, _embed_text_for(ch)))
        for i, seg in enumerate(_segments(ch)):
            units.append((f"{k}#s{i}", seg))
    return units


def _attach(chunks: list[dict], cached: dict) -> int:
    """Attach ch['_vec'] (whole) and ch['_subvecs'] (sub-sections) from a key->vector map.
    Returns the number of chunks given a whole vector."""
    import numpy as np
    n = 0
    for ch in chunks:
        k = _chunk_key(ch)
        v = cached.get(k)
        if v is not None:
            ch["_vec"] = np.asarray(v, dtype="float32")
            n += 1
        subs, i = [], 0
        while (sv := cached.get(f"{k}#s{i}")) is not None:
            subs.append(np.asarray(sv, dtype="float32"))
            i += 1
        if subs:
            ch["_subvecs"] = subs
    return n


def _build_index(corpus_dict: dict, save: bool = True):
    """Embed every unit (whole chunks + sub-sections), reusing cached vectors by key, attach
    ch['_vec']/ch['_subvecs'], persist to npz. Returns the number of chunks with a whole vector."""
    import numpy as np
    chunks = [ch for e in corpus_dict.values() for ch in e["chunks"]]
    units = _units(chunks)

    cached: dict = {}
    if INDEX_PATH.exists():
        try:
            data = np.load(INDEX_PATH, allow_pickle=True)
            cached = {k: data["vecs"][i] for i, k in enumerate(data["keys"])}
        except Exception:
            cached = {}

    todo = [(k, t) for k, t in units if k not in cached]
    if todo:
        def work(pair):
            k, t = pair
            return k, _embed_one(t)
        with ThreadPoolExecutor(max_workers=8) as ex:
            for k, vec in ex.map(work, todo):
                if vec is not None:
                    cached[k] = np.asarray(vec, dtype="float32")

    n = _attach(chunks, cached)
    if save:
        keep = [(k, cached[k]) for k, _ in units if k in cached]
        if keep:
            try:
                INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
                np.savez(INDEX_PATH,
                         keys=np.array([k for k, _ in keep]),
                         vecs=np.stack([v for _, v in keep]))
            except Exception:
                pass
    return n


def _load_index(corpus_dict: dict) -> int:
    """Attach cached vectors to chunks from the prebuilt npz WITHOUT embedding
    anything (so it works with no credentials). Returns chunks matched."""
    import numpy as np
    if not INDEX_PATH.exists():
        return 0
    try:
        data = np.load(INDEX_PATH, allow_pickle=True)
        cached = {k: data["vecs"][i] for i, k in enumerate(data["keys"])}
    except Exception:
        return 0
    chunks = [ch for e in corpus_dict.values() for ch in e["chunks"]]
    return _attach(chunks, cached)


_ENABLED = False


def enable(corpus_dict: dict, force_build: bool = False) -> bool:
    """Attach embeddings and install the semantic hook in corpus. Idempotent and
    fail-soft: returns False (leaving pure keyword search) if unavailable.

    Loads a prebuilt index from disk when present (no credentials needed); only
    builds — which needs a Bedrock key — when the index is missing or stale."""
    global _ENABLED
    if _ENABLED and not force_build:
        return True
    try:
        import numpy as np  # noqa: F401
        import corpus
    except Exception:
        return False

    n = 0 if force_build else _load_index(corpus_dict)
    if n == 0:                       # no usable prebuilt index — build if we can
        if not _has_key():
            return False
        n = _build_index(corpus_dict, save=True)
    if n == 0:
        return False
    corpus._SEMANTIC = _semantic_bonus
    corpus._SEMANTIC_POOLED = _semantic_pooled
    _ENABLED = True
    return True


def _semantic_bonus(ch: dict, query: str) -> float:
    """Cosine(query, WHOLE chunk) in [0,1]-ish (Titan cosines run low). Returns 0.0 when
    either vector is missing — the scorer then sees a pure keyword score. This is the signal
    lexical mode and routing use, so their behaviour is unchanged by multi-vector indexing."""
    import numpy as np
    cv = ch.get("_vec")
    if cv is None:
        return 0.0
    qv = embed_query(query)
    if qv is None:
        return 0.0
    denom = float(np.linalg.norm(qv) * np.linalg.norm(cv)) or 1.0
    return max(0.0, float(np.dot(qv, cv)) / denom)


def _semantic_pooled(ch: dict, query: str) -> float:
    """Max cosine over the chunk's whole vector AND its sub-section vectors — so a paraphrase
    matching one clause of a long Section scores on that clause, not the diluted whole. Used by
    the embeddings_primary / fusion modes; lexical mode keeps the whole-chunk signal above."""
    import numpy as np
    qv = embed_query(query)
    if qv is None:
        return 0.0
    qn = float(np.linalg.norm(qv)) or 1.0
    cands = ch.get("_subvecs", [])
    if ch.get("_vec") is not None:
        cands = [ch["_vec"], *cands]
    best = 0.0
    for cv in cands:
        d = float(np.dot(qv, cv)) / (qn * (float(np.linalg.norm(cv)) or 1.0))
        if d > best:
            best = d
    return max(0.0, best)
