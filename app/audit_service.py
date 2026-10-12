"""Create and query security audit records without storing sensitive content."""

import hashlib
import json

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.models import AuditLog, User


def hash_query(query: str) -> str:
    """Return a stable digest without retaining the user's raw question."""
    normalized = " ".join(query.casefold().split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def record_audit_event(
    session: Session,
    *,
    action: str,
    decision: str,
    response_status: str,
    user: User | None = None,
    username: str | None = None,
    role_name: str | None = None,
    resource_type: str | None = None,
    resource_id: int | None = None,
    query: str | None = None,
    retrieved_document_ids: list[int] | None = None,
    gemini_called: bool = False,
    duration_ms: float | None = None,
) -> AuditLog:
    """Persist safe event metadata; never accept prompts, answers, or document text."""
    event = AuditLog(
        user_id=user.id if user is not None else None,
        username_snapshot=(user.username if user is not None else username),
        role_snapshot=(user.role.name if user is not None else role_name),
        action=action,
        decision=decision,
        resource_type=resource_type,
        resource_id=resource_id,
        query_hash=hash_query(query) if query is not None else None,
        retrieved_document_ids_json=json.dumps(
            sorted(set(retrieved_document_ids or [])),
            separators=(",", ":"),
        ),
        gemini_called=gemini_called,
        response_status=response_status,
        duration_ms=round(duration_ms, 2) if duration_ms is not None else None,
    )
    session.add(event)
    session.commit()
    session.refresh(event)
    return event


def list_audit_events(
    session: Session,
    *,
    action: str | None = None,
    decision: str | None = None,
    user_id: int | None = None,
    limit: int = 100,
) -> list[AuditLog]:
    statement: Select[tuple[AuditLog]] = select(AuditLog)
    if action is not None:
        statement = statement.where(AuditLog.action == action)
    if decision is not None:
        statement = statement.where(AuditLog.decision == decision)
    if user_id is not None:
        statement = statement.where(AuditLog.user_id == user_id)
    statement = statement.order_by(AuditLog.id.desc()).limit(limit)
    return list(session.scalars(statement).all())


def decoded_document_ids(event: AuditLog) -> list[int]:
    """Convert the compact database representation into the API list format."""
    values = json.loads(event.retrieved_document_ids_json)
    return [int(value) for value in values]
