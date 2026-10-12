from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.audit_service import record_audit_event
from app.auth_service import (
    SESSION_LIFETIME,
    authenticate_user,
    change_user_password,
    create_auth_session,
    revoke_access_token,
    revoke_all_user_sessions,
)
from app.database import get_database_session
from app.dependencies import get_bearer_credentials, get_current_user
from app.models import User
from app.schemas import (
    CurrentUserResponse,
    LoginRequest,
    PasswordChangeRequest,
    SessionRevocationResponse,
    TokenResponse,
)


router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=TokenResponse)
def login(
    login_data: LoginRequest,
    session: Annotated[Session, Depends(get_database_session)],
) -> TokenResponse:
    user = authenticate_user(session, login_data.username, login_data.password)
    if user is None:
        record_audit_event(
            session,
            action="login",
            decision="denied",
            response_status="invalid_credentials",
            username=login_data.username.strip().lower(),
            resource_type="auth_session",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token, _auth_session = create_auth_session(session, user)
    record_audit_event(
        session,
        action="login",
        decision="allowed",
        response_status="session_created",
        user=user,
        resource_type="auth_session",
        resource_id=_auth_session.id,
    )
    return TokenResponse(
        access_token=access_token,
        expires_in_seconds=int(SESSION_LIFETIME.total_seconds()),
    )


@router.get("/me", response_model=CurrentUserResponse)
def read_current_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> CurrentUserResponse:
    return CurrentUserResponse(
        id=current_user.id,
        username=current_user.username,
        role=current_user.role.name,
        is_active=current_user.is_active,
        permission_version=current_user.permission_version,
    )


@router.post("/logout", response_model=SessionRevocationResponse)
def logout(
    credentials: Annotated[
        HTTPAuthorizationCredentials,
        Depends(get_bearer_credentials),
    ],
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_database_session)],
) -> SessionRevocationResponse:
    """Revoke only the session represented by the current Bearer token."""
    revoked = revoke_access_token(session, credentials.credentials)
    record_audit_event(
        session,
        action="logout",
        decision="allowed",
        response_status="session_revoked",
        user=current_user,
        resource_type="auth_session",
    )
    return SessionRevocationResponse(
        message="Current session was logged out.",
        revoked_sessions=1 if revoked else 0,
    )


@router.post("/logout-all", response_model=SessionRevocationResponse)
def logout_all(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_database_session)],
) -> SessionRevocationResponse:
    """Revoke every session belonging to the current user."""
    revoked_count = revoke_all_user_sessions(session, current_user.id)
    record_audit_event(
        session,
        action="logout_all",
        decision="allowed",
        response_status="sessions_revoked",
        user=current_user,
        resource_type="auth_session",
    )
    return SessionRevocationResponse(
        message="All sessions were logged out.",
        revoked_sessions=revoked_count,
    )


@router.patch("/password", response_model=SessionRevocationResponse)
def update_password(
    update: PasswordChangeRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_database_session)],
) -> SessionRevocationResponse:
    """Change the current password and invalidate every existing session."""
    try:
        revoked_count = change_user_password(
            session,
            current_user,
            update.current_password,
            update.new_password,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error

    record_audit_event(
        session,
        action="password_changed",
        decision="allowed",
        response_status="sessions_revoked",
        user=current_user,
        resource_type="user",
        resource_id=current_user.id,
    )
    return SessionRevocationResponse(
        message="Password changed. Log in again with the new password.",
        revoked_sessions=revoked_count,
    )
