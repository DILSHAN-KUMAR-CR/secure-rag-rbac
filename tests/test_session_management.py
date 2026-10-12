import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base, get_database_session
from app.main import app
from app.models import AuditLog, AuthSession
from app.seed import seed_default_roles
from app.user_service import create_initial_admin, create_user


@pytest.fixture
def session_test_app():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        admin = None
        employee = None
        seed_default_roles(session)
        admin = create_initial_admin(session, "admin", "Admin-password-123")
        employee = create_user(
            session,
            "alice",
            "Employee-password-123",
            "Employee",
        )

        def override_database_session():
            yield session

        app.dependency_overrides[get_database_session] = override_database_session
        with TestClient(app) as client:
            yield client, session, admin, employee
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


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_logout_revokes_only_the_current_session(session_test_app) -> None:
    client, _session, _admin, _employee = session_test_app
    first_token = login(client, "alice", "Employee-password-123")
    second_token = login(client, "alice", "Employee-password-123")

    response = client.post("/auth/logout", headers=bearer(first_token))

    assert response.status_code == 200
    assert response.json()["revoked_sessions"] == 1
    assert client.get("/auth/me", headers=bearer(first_token)).status_code == 401
    assert client.get("/auth/me", headers=bearer(second_token)).status_code == 200


def test_logout_all_revokes_every_user_session(session_test_app) -> None:
    client, _session, _admin, _employee = session_test_app
    first_token = login(client, "alice", "Employee-password-123")
    second_token = login(client, "alice", "Employee-password-123")

    response = client.post("/auth/logout-all", headers=bearer(first_token))

    assert response.status_code == 200
    assert response.json()["revoked_sessions"] == 2
    assert client.get("/auth/me", headers=bearer(first_token)).status_code == 401
    assert client.get("/auth/me", headers=bearer(second_token)).status_code == 401


def test_password_change_rehashes_password_and_revokes_sessions(
    session_test_app,
) -> None:
    client, session, _admin, employee = session_test_app
    token = login(client, "alice", "Employee-password-123")
    old_hash = employee.password_hash

    response = client.patch(
        "/auth/password",
        headers=bearer(token),
        json={
            "current_password": "Employee-password-123",
            "new_password": "New-employee-password-456",
        },
    )

    session.refresh(employee)
    assert response.status_code == 200
    assert response.json()["revoked_sessions"] == 1
    assert employee.password_hash != old_hash
    assert client.get("/auth/me", headers=bearer(token)).status_code == 401
    assert client.post(
        "/auth/login",
        json={"username": "alice", "password": "Employee-password-123"},
    ).status_code == 401
    assert client.post(
        "/auth/login",
        json={"username": "alice", "password": "New-employee-password-456"},
    ).status_code == 200

    audit_event = session.scalar(
        select(AuditLog).where(AuditLog.action == "password_changed")
    )
    assert audit_event is not None


def test_wrong_current_password_does_not_revoke_session(session_test_app) -> None:
    client, _session, _admin, _employee = session_test_app
    token = login(client, "alice", "Employee-password-123")

    response = client.patch(
        "/auth/password",
        headers=bearer(token),
        json={
            "current_password": "incorrect-password",
            "new_password": "New-employee-password-456",
        },
    )

    assert response.status_code == 400
    assert client.get("/auth/me", headers=bearer(token)).status_code == 200


def test_admin_can_revoke_user_sessions_and_employee_cannot(
    session_test_app,
) -> None:
    client, session, _admin, employee = session_test_app
    admin_token = login(client, "admin", "Admin-password-123")
    employee_token = login(client, "alice", "Employee-password-123")

    response = client.post(
        f"/admin/users/{employee.id}/revoke-sessions",
        headers=bearer(admin_token),
    )

    assert response.status_code == 200
    assert response.json()["revoked_sessions"] == 1
    assert client.get("/auth/me", headers=bearer(employee_token)).status_code == 401
    assert all(
        auth_session.revoked_at is not None
        for auth_session in session.scalars(
            select(AuthSession).where(AuthSession.user_id == employee.id)
        )
    )

    new_employee_token = login(client, "alice", "Employee-password-123")
    forbidden = client.post(
        f"/admin/users/{employee.id}/revoke-sessions",
        headers=bearer(new_employee_token),
    )
    assert forbidden.status_code == 403
