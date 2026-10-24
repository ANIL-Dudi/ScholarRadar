
import numpy as np
from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer

_model = None


def model():
    global _model

    if _model is None:
        _model = SentenceTransformer("all-MiniLM-L6-v2")

    return _model


def _doc(opportunity: dict) -> str:
    return " ".join(
        str(opportunity.get(field) or "")
        for field in ("title", "summary", "eligibility")
    ).strip()


def rrf(rankings: list[list[int]], k: int = 60) -> dict[int, float]:
    scores: dict[int, float] = {}

    for ranking in rankings:
        for rank_position, index in enumerate(ranking):
            scores[index] = (
                scores.get(index, 0.0)
                + 1.0 / (k + rank_position + 1)
            )

    return scores


def rank(
    profile_text: str,
    opps: list[dict],
    top_k: int = 20,
) -> list[dict]:
    if not opps or not profile_text.strip():
        return []

    valid = [
        (index, _doc(opportunity))
        for index, opportunity in enumerate(opps)
        if _doc(opportunity)
    ]

    if not valid:
        return []

    original_indices = [index for index, _ in valid]
    docs = [doc for _, doc in valid]

    embeddings = model().encode(
        [profile_text] + docs,
        normalize_embeddings=True,
    )

    dense_scores = embeddings[1:] @ embeddings[0]
    dense_rank = list(np.argsort(-dense_scores))

    tokens = [doc.lower().split() for doc in docs]
    bm25 = BM25Okapi(tokens)
    sparse_scores = bm25.get_scores(profile_text.lower().split())
    sparse_rank = list(np.argsort(-sparse_scores))

    fused_scores = rrf([dense_rank, sparse_rank])

    ranked = sorted(
        fused_scores.items(),
        key=lambda item: item[1],
        reverse=True,
    )[:max(0, top_k)]

    output = []

    for local_index, score in ranked:
        original_index = original_indices[local_index]
        opportunity = dict(opps[original_index])

        opportunity["score"] = round(float(score), 4)
        opportunity["semantic_similarity"] = round(
            float(dense_scores[local_index]), 4
        )
        opportunity["why"] = (
            "Ranked using semantic similarity and keyword retrieval. "
            "Confirm eligibility and deadline on the official page."
        )

        output.append(opportunity)

    return output
