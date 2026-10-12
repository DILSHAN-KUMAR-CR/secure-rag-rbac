
from sqlalchemy import func, select

from app.database import SessionLocal
from app.models import (
    Document,
    DocumentChunk,
    DocumentPermission,
    Role,
)


with SessionLocal() as session:
    print("\n=== DATABASE DIAGNOSTICS ===")

    document_count = session.scalar(
        select(func.count()).select_from(Document)
    )
    chunk_count = session.scalar(
        select(func.count()).select_from(DocumentChunk)
    )
    permission_count = session.scalar(
        select(func.count()).select_from(DocumentPermission)
    )
    role_count = session.scalar(
        select(func.count()).select_from(Role)
    )

    print(f"Documents: {document_count}")
    print(f"Chunks: {chunk_count}")
    print(f"Document permissions: {permission_count}")
    print(f"Roles: {role_count}")

    print("\n=== DOCUMENT STATUS ===")
    statuses = session.execute(
        select(Document.status, func.count(Document.id))
        .group_by(Document.status)
    ).all()

    for status, count in statuses:
        print(f"{status}: {count}")

    print("\n=== DOCUMENT DETAILS ===")
    documents = session.execute(
        select(
            Document.id,
            Document.title,
            Document.status,
            Document.content_version,
        ).order_by(Document.id)
    ).all()

    for document_id, title, status, version in documents:
        chunks = session.scalar(
            select(func.count())
            .select_from(DocumentChunk)
            .where(DocumentChunk.document_id == document_id)
        )

        permissions = session.execute(
            select(Role.name)
            .join(
                DocumentPermission,
                DocumentPermission.role_id == Role.id,
            )
            .where(DocumentPermission.document_id == document_id)
        ).scalars().all()

        print(
            f"ID={document_id} | Title={title} | "
            f"Status={status} | Version={version} | "
            f"Chunks={chunks} | Roles={permissions}"
        )
