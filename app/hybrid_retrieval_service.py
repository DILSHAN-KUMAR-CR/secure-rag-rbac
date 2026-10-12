
from app.retrieval_service import retrieve_authorized_chunks
from app.vector_service import (
    get_authorized_document_fingerprint,
    semantic_search,
)


RRF_K = 60
MAX_CANDIDATES = 100


def hybrid_search(
    session,
    query: str,
    role_name: str,
    top_k: int,
) -> list[dict[str, object]]:
    """Combine authorized keyword and semantic rankings using RRF."""
    if top_k <= 0:
        return []

    candidate_k = min(top_k * 3, MAX_CANDIDATES)

    authorized_documents = get_authorized_document_fingerprint(
        session, role_name
    )
    authorized_ids = [
        document_id for document_id, _version in authorized_documents
    ]

    if not authorized_ids:
        return []

    keyword_results = retrieve_authorized_chunks(
        session=session,
        query=query,
        role_name=role_name,
        top_k=candidate_k,
    )

    semantic_results = semantic_search(
        session=session,
        query=query,
        role_name=role_name,
        top_k=candidate_k,
        authorized_document_ids=authorized_ids,
    )

    fused: dict[int, dict[str, object]] = {}
    rrf_scores: dict[int, float] = {}

    for results in (keyword_results, semantic_results):
        seen_in_ranking: set[int] = set()

        for rank, result in enumerate(results, start=1):
            chunk_id = int(result["chunk_id"])

            if chunk_id in seen_in_ranking:
                continue
            seen_in_ranking.add(chunk_id)

            rrf_scores[chunk_id] = (
                rrf_scores.get(chunk_id, 0.0)
                + 1.0 / (RRF_K + rank)
            )

            if chunk_id not in fused:
                fused[chunk_id] = dict(result)

    ranked_results = []

    for chunk_id, result in fused.items():
        result["score"] = round(rrf_scores[chunk_id], 6)
        ranked_results.append(result)

    ranked_results.sort(
        key=lambda result: (
            -float(result["score"]),
            int(result["chunk_id"]),
        )
    )

    return ranked_results[:top_k]
