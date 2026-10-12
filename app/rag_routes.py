from typing import Annotated
from time import perf_counter

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.audit_service import record_audit_event
from app.database import get_database_session
from app.dependencies import get_current_user
from app.gemini_provider import (
    GeminiAnswerProvider,
    GeminiConfigurationError,
    GeminiGenerationError,
)
from app.models import User
from app.rag_service import (
    access_still_authorized,
    generate_grounded_answer,
    prepare_authorized_context,
)
from app.schemas import ContextPreviewResponse, RAGAnswerResponse, RAGTimings, RetrievalRequest


router = APIRouter(prefix="/rag", tags=["RAG preparation"])


@router.post("/context-preview", response_model=ContextPreviewResponse)
def preview_llm_context(
    request: RetrievalRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_database_session)],
) -> ContextPreviewResponse:
    """Show what an LLM could receive; no LLM is called by this endpoint."""
    started_at = perf_counter()
    request_role = current_user.role.name
    context = prepare_authorized_context(
        session=session,
        query=request.query,
        role_name=request_role,
        top_k=request.top_k,
    )
    if context.citations and not access_still_authorized(
        session,
        current_user.id,
        request_role,
        current_user.permission_version,
        (citation.chunk_id for citation in context.citations),
    ):
        context = type(context)(text="", citations=[])
    document_ids = sorted({citation.document_id for citation in context.citations})
    record_audit_event(
        session,
        action="context_preview",
        decision="allowed" if context.citations else "no_accessible_source",
        response_status="ready" if context.citations else "empty",
        user=current_user,
        resource_type="llm_context",
        query=request.query,
        retrieved_document_ids=document_ids,
        gemini_called=False,
        duration_ms=(perf_counter() - started_at) * 1000,
    )
    return ContextPreviewResponse(
        query=request.query,
        user_role=request_role,
        status="ready" if context.citations else "no_accessible_source",
        context=context.text,
        citations=context.citations,
    )


@router.post("/ask", response_model=RAGAnswerResponse)
def ask_gemini(
    request: RetrievalRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_database_session)],
) -> RAGAnswerResponse:
    """Generate an answer only from chunks currently permitted to this user."""
    started_at = perf_counter()
    request_role = current_user.role.name
    permission_version = current_user.permission_version
    try:
        result = generate_grounded_answer(
            session=session,
            query=request.query,
            role_name=request_role,
            top_k=request.top_k,
            provider=GeminiAnswerProvider(),
            user_id=current_user.id,
            permission_version=permission_version,
        )
    except GeminiConfigurationError as exc:
        record_audit_event(
            session,
            action="rag_query",
            decision="error",
            response_status="gemini_not_configured",
            user=current_user,
            resource_type="rag_answer",
            query=request.query,
            gemini_called=False,
            duration_ms=(perf_counter() - started_at) * 1000,
        )
        raise HTTPException(
            status_code=503,
            detail="Gemini is not configured on the server.",
        ) from exc
    except GeminiGenerationError as exc:
        if exc.provider_status is not None:
            detail = f"Gemini rejected the request (provider HTTP {exc.provider_status})."
        elif exc.category == "connection_error":
            detail = "Could not connect to Gemini. Check the server's internet connection."
        elif exc.category == "empty_response":
            detail = "Gemini returned no text answer."
        else:
            detail = "Gemini returned a response the server could not read."
        record_audit_event(
            session,
            action="rag_query",
            decision="error",
            response_status=exc.category,
            user=current_user,
            resource_type="rag_answer",
            query=request.query,
            gemini_called=True,
            duration_ms=(perf_counter() - started_at) * 1000,
        )
        raise HTTPException(
            status_code=502,
            detail=detail,
        ) from exc

    document_ids = sorted({citation.document_id for citation in result.citations})
    record_audit_event(
        session,
        action="rag_query",
        decision="allowed" if result.citations else "no_accessible_source",
        response_status="answered" if result.citations else "empty",
        user=current_user,
        resource_type="rag_answer",
        query=request.query,
        retrieved_document_ids=document_ids,
        gemini_called=result.gemini_generation_ms > 0,
        duration_ms=(perf_counter() - started_at) * 1000,
    )
    return RAGAnswerResponse(
        query=request.query,
        user_role=request_role,
        status="answered" if result.citations else "no_accessible_source",
        answer=result.answer,
        citations=result.citations,
        timings_ms=RAGTimings(
            context_preparation=result.context_preparation_ms,
            gemini_generation=result.gemini_generation_ms,
        ),
    )
