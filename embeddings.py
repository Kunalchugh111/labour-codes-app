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


# ── query embedding (cached so search_all's 4 per-code calls embed once) ──────
@lru_cache(maxsize=512)
def embed_query(query: str):
    import numpy as np
    v = _embed_one(query)
    return None if v is None else np.asarray(v, dtype="float32")


def _build_index(corpus_dict: dict, save: bool = True):
    """Embed every chunk (reusing cached vectors by text-hash), attach ch['_vec'],
    persist to npz. Returns the number of chunks with a vector."""
    import numpy as np
    chunks = [ch for e in corpus_dict.values() for ch in e["chunks"]]
    keys = [_chunk_key(ch) for ch in chunks]

    cached: dict = {}
    if INDEX_PATH.exists():
        try:
            data = np.load(INDEX_PATH, allow_pickle=True)
            cached = {k: data["vecs"][i] for i, k in enumerate(data["keys"])}
        except Exception:
            cached = {}

    todo = [(i, ch) for i, (ch, k) in enumerate(zip(chunks, keys)) if k not in cached]
    if todo:
        def work(pair):
            i, ch = pair
            return i, _embed_one(_embed_text_for(ch))
        with ThreadPoolExecutor(max_workers=8) as ex:
            for i, vec in ex.map(work, todo):
                if vec is not None:
                    cached[keys[i]] = np.asarray(vec, dtype="float32")

    n = 0
    vecs = []
    for ch, k in zip(chunks, keys):
        v = cached.get(k)
        if v is not None:
            ch["_vec"] = np.asarray(v, dtype="float32")
            vecs.append((k, ch["_vec"]))
            n += 1
    if save and vecs:
        try:
            INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
            np.savez(INDEX_PATH,
                     keys=np.array([k for k, _ in vecs]),
                     vecs=np.stack([v for _, v in vecs]))
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
    n = 0
    for e in corpus_dict.values():
        for ch in e["chunks"]:
            v = cached.get(_chunk_key(ch))
            if v is not None:
                ch["_vec"] = np.asarray(v, dtype="float32")
                n += 1
    return n


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
    _ENABLED = True
    return True


def _semantic_bonus(ch: dict, query: str) -> float:
    """Cosine(query, chunk) in [0,1]-ish (Titan cosines run low). Returns 0.0 when
    either vector is missing — the scorer then sees a pure keyword score."""
    import numpy as np
    cv = ch.get("_vec")
    if cv is None:
        return 0.0
    qv = embed_query(query)
    if qv is None:
        return 0.0
    denom = float(np.linalg.norm(qv) * np.linalg.norm(cv)) or 1.0
    return max(0.0, float(np.dot(qv, cv)) / denom)
