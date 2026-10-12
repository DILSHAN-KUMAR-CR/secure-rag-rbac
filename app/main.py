from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select

from app.admin_routes import router as admin_router
from app.audit_routes import router as audit_router
from app.auth_routes import router as auth_router
from app.database import SessionLocal, initialize_database
from app.document_routes import router as document_router
from app.models import Role
from app.retrieval_routes import router as retrieval_router
from app.rag_routes import router as rag_router
from app.seed import seed_default_roles
from app.ui_routes import router as ui_router


APP_VERSION = "1.3.0"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Prepare the database before the API accepts requests."""
    initialize_database()
    with SessionLocal() as session:
        seed_default_roles(session)
    yield


app = FastAPI(
    title="Secure RAG with RBAC",
    description=(
        "A permission-aware RAG API that enforces current role and document "
        "access before model context construction."
    ),
    version=APP_VERSION,
    lifespan=lifespan,
)

app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(audit_router)
app.include_router(document_router)
app.include_router(retrieval_router)
app.include_router(rag_router)
app.include_router(ui_router)
app.mount(
    "/ui-static",
    StaticFiles(directory=Path(__file__).resolve().parent / "static"),
    name="ui-static",
)


@app.middleware("http")
async def add_browser_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    if request.url.path.startswith(("/ui", "/ui-static")):
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; connect-src 'self'; img-src 'self' data:; "
            "style-src 'self'; script-src 'self'; object-src 'none'; "
            "base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
        )
    return response


@app.get("/")
def root() -> dict[str, str]:
    return {
        "project": "Secure RAG with RBAC",
        "message": "Application is running. Open /ui or /docs.",
    }


@app.get("/health")
def health() -> dict[str, str | int]:
    """Prove that both the web API and the database are working."""
    with SessionLocal() as session:
        role_count = session.scalar(select(func.count()).select_from(Role)) or 0

    return {
        "status": "healthy",
        "database": "connected",
        "roles": role_count,
    }
