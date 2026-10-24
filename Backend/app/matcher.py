import numpy as np
from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer

_model = None


def model():
    global _model
    if _model is None:
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


def _doc(o: dict) -> str:
    return f"{o.get('title','')} {o.get('summary','')} {o.get('eligibility','')}"


def rrf(rankings: list[list[int]], k: int = 60) -> dict[int, float]:
    scores: dict[int, float] = {}
    for ranking in rankings:
        for rank, idx in enumerate(ranking):
            scores[idx] = scores.get(idx, 0.0) + 1.0 / (k + rank + 1)
    return scores


def rank(profile_text: str, opps: list[dict], top_k: int = 20) -> list[dict]:
    if not opps:
        return []
    docs = [_doc(o) for o in opps]
    emb = model().encode([profile_text] + docs, normalize_embeddings=True)
    dense = emb[1:] @ emb[0]
    dense_rank = list(np.argsort(-dense))
    bm25 = BM25Okapi([d.lower().split() for d in docs])
    sparse = bm25.get_scores(profile_text.lower().split())
    sparse_rank = list(np.argsort(-sparse))
    fused = rrf([dense_rank, sparse_rank])
    out = []
    for idx, score in sorted(fused.items(), key=lambda x: -x[1])[:top_k]:
        o = dict(opps[idx])
        o["score"] = round(score, 4)
        o["why"] = f"Semantic match {dense[idx]:.2f}; keyword overlap with your CV and interests."
        out.append(o)
    return out