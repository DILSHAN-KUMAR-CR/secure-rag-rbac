from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.audit_service import decoded_document_ids, list_audit_events
from app.database import get_database_session
from app.dependencies import require_admin
from app.models import AuditLog, User
from app.schemas import AuditLogResponse


router = APIRouter(prefix="/admin/audit-logs", tags=["Audit"])


def to_audit_response(event: AuditLog) -> AuditLogResponse:
    return AuditLogResponse(
        id=event.id,
        created_at=event.created_at,
        user_id=event.user_id,
        username=event.username_snapshot,
        role=event.role_snapshot,
        action=event.action,
        decision=event.decision,
        resource_type=event.resource_type,
        resource_id=event.resource_id,
        query_hash=event.query_hash,
        retrieved_document_ids=decoded_document_ids(event),
        gemini_called=event.gemini_called,
        response_status=event.response_status,
        duration_ms=event.duration_ms,
    )


@router.get("", response_model=list[AuditLogResponse])
def read_audit_logs(
    _admin: Annotated[User, Depends(require_admin)],
    session: Annotated[Session, Depends(get_database_session)],
    action: Annotated[str | None, Query(max_length=80)] = None,
    decision: Annotated[str | None, Query(max_length=30)] = None,
    user_id: Annotated[int | None, Query(ge=1)] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[AuditLogResponse]:
    """Return recent safe audit metadata to administrators only."""
    return [
        to_audit_response(event)
        for event in list_audit_events(
            session,
            action=action,
            decision=decision,
            user_id=user_id,
            limit=limit,
        )
    ]
