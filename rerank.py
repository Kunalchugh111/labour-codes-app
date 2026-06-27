"""
rerank.py — optional cross-encoder reranking via Cohere Rerank on Bedrock.

Used only when corpus.RetrievalConfig.mode == "rerank": corpus retrieves a candidate set
(by fusion) and this module reorders it with a true query×document cross-encoder, which
ranks the governing provision higher than a merely keyword/topic-similar one.

Fail-soft like embeddings.py: any missing key, model error, or unexpected payload returns
None, and the caller falls back to its base (fusion) ranking — so enabling rerank can never
crash the app or empty the results. Confirmed available: cohere.rerank-v3-5:0 in us-east-1,
body {"query","documents","top_n","api_version":2} -> {"results":[{"index","relevance_score"}]}.
"""
import os
import json
import threading

MODEL_ID = os.environ.get("BEDROCK_RERANK_MODEL", "cohere.rerank-v3-5:0")
_MAX_DOC_CHARS = 4000          # cap each candidate's text sent to the reranker
_local = threading.local()
_CACHE: dict = {}              # (query, chunk-keys, top_n) -> [(index, score)]
_CACHE_MAX = 512               # bound so a long-running server doesn't leak one entry per query


def _has_key() -> bool:
    return bool(os.environ.get("AWS_BEARER_TOKEN_BEDROCK"))


def _client():
    """One bedrock-runtime client per thread (safe for parallel eval harnesses)."""
    c = getattr(_local, "client", None)
    if c is None:
        import boto3
        c = boto3.client("bedrock-runtime",
                         region_name=os.environ.get("AWS_REGION", "us-east-1"))
        _local.client = c
    return c


def _doc_text(ch: dict) -> str:
    """What the reranker scores: title + body, so the marginal heading (often the most
    query-like phrase) informs relevance — same text shape we embed (embeddings._embed_text_for)."""
    title = ch.get("title") or ""
    body = ch.get("text", "")
    return ((title + ". " + body) if title else body)[:_MAX_DOC_CHARS]


def rerank(query: str, chunks: list, top_n: int | None = None):
    """Reorder `chunks` by Cohere relevance to `query`. Returns [(chunk, relevance_score)]
    best-first, or None on any failure (caller then keeps its base ranking). Cached by
    (query, chunk-keys) so the per-code calls and repeated eval queries don't re-hit the API."""
    if not query or not chunks or not _has_key():
        return None
    try:
        import embeddings
        keys = tuple(embeddings._chunk_key(ch) for ch in chunks)
    except Exception:
        keys = tuple(f'{ch.get("source","")}|{ch.get("label","")}' for ch in chunks)
    n = top_n or len(chunks)
    ck = (query, keys, n)
    idx = _CACHE.get(ck)
    if idx is None:
        docs = [_doc_text(ch) for ch in chunks]
        try:
            body = {"query": query, "documents": docs, "top_n": n, "api_version": 2}
            r = _client().invoke_model(modelId=MODEL_ID, body=json.dumps(body))
            results = json.loads(r["body"].read())["results"]
            idx = [(int(res["index"]), float(res["relevance_score"])) for res in results]
            if len(_CACHE) >= _CACHE_MAX:
                _CACHE.clear()
            _CACHE[ck] = idx
        except Exception:
            return None
    return [(chunks[i], s) for i, s in idx if 0 <= i < len(chunks)]
