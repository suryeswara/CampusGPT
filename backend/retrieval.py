import re
from dataclasses import dataclass
from functools import lru_cache

from langchain_core.documents import Document
from rank_bm25 import BM25Okapi
from sentence_transformers import CrossEncoder

from backend import config
from backend.vectorstore import get_vectorstore


@dataclass
class Hit:
    doc: Document
    score: float


# ---------- BM25 (keyword) index ----------

def tokenize(text: str) -> list[str]:
    return re.findall(r"\w+", text.lower())


class _BM25State:
    bm25: BM25Okapi | None = None
    docs: list[Document] = []


def rebuild_bm25() -> None:
    """Rebuild the keyword index from everything stored in Chroma."""
    data = get_vectorstore().get(include=["documents", "metadatas"])
    texts = data.get("documents") or []
    metas = data.get("metadatas") or []
    _BM25State.docs = [
        Document(page_content=t, metadata=m) for t, m in zip(texts, metas)
    ]
    if _BM25State.docs:
        _BM25State.bm25 = BM25Okapi([tokenize(d.page_content) for d in _BM25State.docs])
    else:
        _BM25State.bm25 = None


# ---------- individual searches ----------

def vector_search(query, sources, k):
    """Returns [(Document, cosine_distance)], best (lowest) first."""
    flt = {"source": {"$in": sources}} if sources else None
    return get_vectorstore().similarity_search_with_score(query, k=k, filter=flt)


def bm25_search(query, sources, k):
    """Returns [(Document, bm25_score)], best (highest) first."""
    if _BM25State.bm25 is None:
        return []
    scores = _BM25State.bm25.get_scores(tokenize(query))
    order = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
    out = []
    for i in order:
        if scores[i] <= 0:
            break
        doc = _BM25State.docs[i]
        if sources and doc.metadata["source"] not in sources:
            continue
        out.append((doc, float(scores[i])))
        if len(out) >= k:
            break
    return out


# ---------- fusion and reranking ----------

def rrf(rank_lists, k: int = config.RRF_K):
    """Reciprocal Rank Fusion: merge ranked lists using ranks only (not raw scores)."""
    scores: dict[str, float] = {}
    docs: dict[str, Document] = {}
    for ranked in rank_lists:
        for rank, (doc, _) in enumerate(ranked, start=1):
            cid = doc.metadata["chunk_id"]
            docs[cid] = doc
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + rank)
    ordered = sorted(scores, key=scores.get, reverse=True)
    return [(docs[c], scores[c]) for c in ordered]


@lru_cache(maxsize=1)
def get_reranker():
    return CrossEncoder(config.RERANK_MODEL)


def rerank(query, candidates, top_k):
    if not candidates:
        return []
    pairs = [(query, doc.page_content) for doc, _ in candidates]
    scores = get_reranker().predict(pairs)
    ranked = sorted(
        zip([d for d, _ in candidates], scores), key=lambda x: x[1], reverse=True
    )
    return [Hit(d, float(s)) for d, s in ranked[:top_k]]


# ---------- main entry point ----------

def retrieve(query, sources=None, mode="hybrid_rerank", top_k=config.FINAL_K):
    """
    mode: "vector" | "hybrid" | "hybrid_rerank"
    Returns a list of Hit. Empty list means "nothing relevant" (answer: not found).
    Score meaning depends on mode: distance (lower better), RRF score, or reranker logit.
    """
    vec = vector_search(query, sources, config.FETCH_K)

    # Gate 1: if even the closest chunk is far away, the topic is not in the documents.
    if not vec or vec[0][1] > config.MAX_DISTANCE:
        return []

    if mode == "vector":
        return [Hit(d, s) for d, s in vec[:top_k]]

    fused = rrf([vec, bm25_search(query, sources, config.FETCH_K)])[: config.FETCH_K]

    if mode == "hybrid":
        return [Hit(d, s) for d, s in fused[:top_k]]

    # Gate 2: drop chunks the reranker considers irrelevant.
    return [h for h in rerank(query, fused, top_k) if h.score >= config.MIN_RERANK_SCORE]
