import hashlib

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.audit_service import record_audit_event
from app.database import Base, get_database_session
from app.main import app
from app.models import AuditLog
from app.rag_service import GroundedAnswer, NO_ACCESSIBLE_SOURCE_ANSWER
from app.seed import seed_default_roles
from app.user_service import create_initial_admin, create_user


@pytest.fixture
def audit_test_app():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        seed_default_roles(session)
        create_initial_admin(session, "admin", "Admin-password-123")
        create_user(session, "alice", "Alice-password-123", "Employee")

        def override_database_session():
            yield session

        app.dependency_overrides[get_database_session] = override_database_session
        with TestClient(app) as client:
            yield client, session
        app.dependency_overrides.clear()

    Base.metadata.drop_all(engine)
    engine.dispose()


def login(client: TestClient, username: str, password: str) -> str:
    response = client.post(
        "/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def test_login_events_are_audited_without_credentials(audit_test_app) -> None:
    client, session = audit_test_app

    denied = client.post(
        "/auth/login",
        json={"username": "alice", "password": "wrong-secret-value"},
    )
    admin_token = login(client, "admin", "Admin-password-123")

    assert denied.status_code == 401
    response = client.get(
        "/admin/audit-logs?action=login",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    events = response.json()
    assert {event["decision"] for event in events} == {"allowed", "denied"}

    serialized = str(events)
    assert "Admin-password-123" not in serialized
    assert "wrong-secret-value" not in serialized
    assert admin_token not in serialized
    assert session.scalar(select(AuditLog)) is not None


def test_audit_endpoint_is_admin_only(audit_test_app) -> None:
    client, _session = audit_test_app
    employee_token = login(client, "alice", "Alice-password-123")

    response = client.get(
        "/admin/audit-logs",
        headers={"Authorization": f"Bearer {employee_token}"},
    )

    assert response.status_code == 403


def test_query_is_hashed_and_sensitive_content_is_not_stored(audit_test_app) -> None:
    _client, session = audit_test_app
    admin = create_user(session, "second-admin", "Another-admin-123", "Admin")
    query = "What is Alice's confidential salary?"

    event = record_audit_event(
        session,
        action="rag_query",
        decision="no_accessible_source",
        response_status="empty",
        user=admin,
        query=query,
        retrieved_document_ids=[],
    )

    normalized = " ".join(query.casefold().split())
    assert event.query_hash == hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    assert query not in repr(event.__dict__)
    assert event.retrieved_document_ids_json == "[]"


def test_rag_no_source_records_no_gemini_call(audit_test_app, monkeypatch) -> None:
    client, _session = audit_test_app
    employee_token = login(client, "alice", "Alice-password-123")

    monkeypatch.setattr(
        "app.rag_routes.generate_grounded_answer",
        lambda **_kwargs: GroundedAnswer(
            answer=NO_ACCESSIBLE_SOURCE_ANSWER,
            citations=[],
            context_preparation_ms=3.5,
            gemini_generation_ms=0.0,
        ),
    )

    response = client.post(
        "/rag/ask",
        headers={"Authorization": f"Bearer {employee_token}"},
        json={"query": "What is Alice's compensation?", "top_k": 3},
    )
    assert response.status_code == 200

    with _session.no_autoflush:
        event = _session.scalar(
            select(AuditLog)
            .where(AuditLog.action == "rag_query")
            .order_by(AuditLog.id.desc())
        )
    assert event is not None
    assert event.decision == "no_accessible_source"
    assert event.gemini_called is False
    assert event.query_hash is not None
    assert "compensation" not in repr(event.__dict__)
