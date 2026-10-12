from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models import AuthSession, User
from app.security import (
    generate_access_token,
    hash_access_token,
    hash_password,
    verify_password,
)


SESSION_LIFETIME = timedelta(minutes=30)
DUMMY_PASSWORD_HASH = hash_password("not-a-real-user-password")


def authenticate_user(session: Session, username: str, password: str) -> User | None:
    """Return an active user when the supplied credentials are valid."""
    clean_username = username.strip().lower()
    user = session.scalar(select(User).where(User.username == clean_username))

    if user is None:
        # Performing one hash check also for missing users makes username guessing harder.
        verify_password(password, DUMMY_PASSWORD_HASH)
        return None

    if not user.is_active or not verify_password(password, user.password_hash):
        return None

    return user


def create_auth_session(session: Session, user: User) -> tuple[str, AuthSession]:
    """Issue a raw token to the user while storing only its hash."""
    access_token = generate_access_token()
    auth_session = AuthSession(
        token_hash=hash_access_token(access_token),
        user_id=user.id,
        expires_at=datetime.now(timezone.utc) + SESSION_LIFETIME,
    )
    session.add(auth_session)
    session.commit()
    session.refresh(auth_session)
    return access_token, auth_session


def get_user_for_access_token(session: Session, access_token: str) -> User | None:
    """Validate a token and load the user's current database role."""
    now = datetime.now(timezone.utc)
    auth_session = session.scalar(
        select(AuthSession)
        .options(joinedload(AuthSession.user).joinedload(User.role))
        .where(
            AuthSession.token_hash == hash_access_token(access_token),
            AuthSession.revoked_at.is_(None),
            AuthSession.expires_at > now,
        )
    )

    if auth_session is None or not auth_session.user.is_active:
        return None

    return auth_session.user


def revoke_access_token(session: Session, access_token: str) -> bool:
    """Revoke one session identified by its raw token without storing that token."""
    auth_session = session.scalar(
        select(AuthSession).where(
            AuthSession.token_hash == hash_access_token(access_token),
            AuthSession.revoked_at.is_(None),
        )
    )
    if auth_session is None:
        return False
    auth_session.revoked_at = datetime.now(timezone.utc)
    session.commit()
    return True


def revoke_all_user_sessions(
    session: Session,
    user_id: int,
    *,
    commit: bool = True,
) -> int:
    """Revoke every non-revoked session for a user and return the number changed."""
    now = datetime.now(timezone.utc)
    active_sessions = list(
        session.scalars(
            select(AuthSession).where(
                AuthSession.user_id == user_id,
                AuthSession.revoked_at.is_(None),
            )
        ).all()
    )
    for auth_session in active_sessions:
        auth_session.revoked_at = now
    if commit:
        session.commit()
    return len(active_sessions)


def change_user_password(
    session: Session,
    user: User,
    current_password: str,
    new_password: str,
) -> int:
    """Replace a verified password and revoke all previously issued sessions."""
    if not verify_password(current_password, user.password_hash):
        raise ValueError("Current password is incorrect.")
    if verify_password(new_password, user.password_hash):
        raise ValueError("New password must be different from the current password.")

    user.password_hash = hash_password(new_password)
    revoked_count = revoke_all_user_sessions(session, user.id, commit=False)
    session.commit()
    return revoked_count
