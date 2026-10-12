
"""Evaluate keyword, semantic, and hybrid retrieval quality."""

import json
from pathlib import Path
from statistics import mean

from app.database import SessionLocal
from app.rag_service import hybrid_search_for_rag
from app.retrieval_service import retrieve_authorized_chunks
from app.vector_service import semantic_search


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATASET_PATH = PROJECT_ROOT / "evaluation" / "retrieval_cases.json"
TOP_K = 5


def precision_at_k(
    retrieved_ids: list[int],
    relevant_ids: set[int],
    k: int,
) -> float:
    top_ids = retrieved_ids[:k]
    relevant_count = sum(chunk_id in relevant_ids for chunk_id in top_ids)
    return relevant_count / k if k else 0.0


def recall_at_k(
    retrieved_ids: list[int],
    relevant_ids: set[int],
    k: int,
) -> float:
    if not relevant_ids:
        return 0.0

    relevant_count = sum(
        chunk_id in relevant_ids for chunk_id in retrieved_ids[:k]
    )
    return relevant_count / len(relevant_ids)


def reciprocal_rank(
    retrieved_ids: list[int],
    relevant_ids: set[int],
    k: int,
) -> float:
    for rank, chunk_id in enumerate(retrieved_ids[:k], start=1):
        if chunk_id in relevant_ids:
            return 1.0 / rank

    return 0.0


def evaluate_method(
    cases: list[dict],
    search_function,
    session,
    k: int,
) -> dict[str, float]:
    precisions = []
    recalls = []
    reciprocal_ranks = []

    for case in cases:
        results = search_function(
            session=session,
            query=case["query"],
            role_name=case["role_name"],
            top_k=k,
        )

        retrieved_ids = [
            int(result["chunk_id"]) for result in results
        ]
        relevant_ids = {
            int(chunk_id)
            for chunk_id in case["relevant_chunk_ids"]
        }

        precisions.append(
            precision_at_k(retrieved_ids, relevant_ids, k)
        )
        recalls.append(
            recall_at_k(retrieved_ids, relevant_ids, k)
        )
        reciprocal_ranks.append(
            reciprocal_rank(retrieved_ids, relevant_ids, k)
        )

    return {
        "precision": mean(precisions),
        "recall": mean(recalls),
        "mrr": mean(reciprocal_ranks),
    }


def main() -> None:
    if not DATASET_PATH.exists():
        raise FileNotFoundError(
            f"Evaluation dataset not found: {DATASET_PATH}"
        )

    with DATASET_PATH.open("r", encoding="utf-8") as file:
        cases = json.load(file)

    if not isinstance(cases, list) or not cases:
        raise ValueError(
            "Add at least one labeled query to retrieval_cases.json."
        )

    for index, case in enumerate(cases, start=1):
        if not all(
            key in case
            for key in ("query", "role_name", "relevant_chunk_ids")
        ):
            raise ValueError(
                f"Evaluation case {index} is missing a required field."
            )

        if not case["relevant_chunk_ids"]:
            raise ValueError(
                f"Evaluation case {index} needs at least one relevant chunk ID."
            )

    methods = {
        "Keyword": retrieve_authorized_chunks,
        "Semantic": semantic_search,
        "Hybrid RRF": hybrid_search_for_rag,
    }

    with SessionLocal() as session:
        print(f"\nRetrieval evaluation: {len(cases)} queries")
        print(f"Metrics calculated at K={TOP_K}\n")
        print(
            f"{'Method':<15}"
            f"{'Precision@K':>15}"
            f"{'Recall@K':>13}"
            f"{'MRR@K':>12}"
        )
        print("-" * 55)

        for name, search_function in methods.items():
            metrics = evaluate_method(
                cases=cases,
                search_function=search_function,
                session=session,
                k=TOP_K,
            )

            print(
                f"{name:<15}"
                f"{metrics['precision']:>14.3f}"
                f"{metrics['recall']:>13.3f}"
                f"{metrics['mrr']:>12.3f}"
            )


if __name__ == "__main__":
    main()
