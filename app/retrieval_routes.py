from typing import Annotated
from time import perf_counter

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.audit_service import record_audit_event
from app.database import get_database_session
from app.dependencies import get_current_user
from app.models import User
from app.rag_service import access_still_authorized
from app.retrieval_service import retrieve_authorized_chunks
from app.retrieval_cache import CacheKey, semantic_retrieval_cache
from app.schemas import RetrievalRequest, RetrievalResponse
from app.vector_service import get_authorized_document_fingerprint, semantic_search


router = APIRouter(prefix="/retrieval", tags=["Retrieval"])


@router.post("/search", response_model=RetrievalResponse)
def search_documents(
    request: RetrievalRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_database_session)],
) -> RetrievalResponse:
    started_at = perf_counter()
    role_name = current_user.role.name
    permission_version = current_user.permission_version
    results = retrieve_authorized_chunks(
        session=session,
        query=request.query,
        role_name=role_name,
        top_k=request.top_k,
    )
    if results and not access_still_authorized(
        session,
        current_user.id,
        role_name,
        permission_version,
        (int(result["chunk_id"]) for result in results),
    ):
        results = []
    document_ids = sorted({int(result["document_id"]) for result in results})
    record_audit_event(
        session,
        action="keyword_retrieval",
        decision="allowed" if results else "no_accessible_source",
        response_status="results_returned" if results else "empty",
        user=current_user,
        resource_type="document_chunks",
        query=request.query,
        retrieved_document_ids=document_ids,
        duration_ms=(perf_counter() - started_at) * 1000,
    )
    return RetrievalResponse(
        query=request.query,
        user_role=role_name,
        results=results,
    )


@router.post("/semantic-search", response_model=RetrievalResponse)
def semantic_search_documents(
    request: RetrievalRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_database_session)],
) -> RetrievalResponse:
    started_at = perf_counter()
    role_name = current_user.role.name
    permission_version = current_user.permission_version
    authorized_documents = get_authorized_document_fingerprint(session, role_name)
    key = CacheKey(
        user_id=current_user.id,
        permission_version=permission_version,
        role_name=role_name,
        authorized_documents=authorized_documents,
        query=request.query,
        top_k=request.top_k,
    )
    cached_results = semantic_retrieval_cache.get(key)
    cache_hit = cached_results is not None
    results = cached_results
    if results is None:
        results = semantic_search(
            session=session,
            query=request.query,
            role_name=role_name,
            top_k=request.top_k,
            authorized_document_ids=[document_id for document_id, _ in authorized_documents],
        )
    if results and not access_still_authorized(
        session,
        current_user.id,
        role_name,
        permission_version,
        (int(result["chunk_id"]) for result in results),
    ):
        results = []
        cache_hit = False
    elif not cache_hit:
        semantic_retrieval_cache.put(key, results)
    document_ids = sorted({int(result["document_id"]) for result in results})
    record_audit_event(
        session,
        action="semantic_retrieval",
        decision="allowed" if results else "no_accessible_source",
        response_status="cache_hit" if cache_hit else ("results_returned" if results else "empty"),
        user=current_user,
        resource_type="document_chunks",
        query=request.query,
        retrieved_document_ids=document_ids,
        duration_ms=(perf_counter() - started_at) * 1000,
    )
    return RetrievalResponse(
        query=request.query,
        user_role=role_name,
        results=results,
        cache_hit=cache_hit,
    )
