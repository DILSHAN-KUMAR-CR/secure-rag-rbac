from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse


router = APIRouter(tags=["Web interface"])
UI_DIRECTORY = Path(__file__).resolve().parent / "ui"


@router.get("/ui", include_in_schema=False)
def login_page() -> FileResponse:
    return FileResponse(UI_DIRECTORY / "login.html")


@router.get("/ui/chat", include_in_schema=False)
def chat_page() -> FileResponse:
    return FileResponse(UI_DIRECTORY / "chat.html")


@router.get("/ui/admin", include_in_schema=False)
def admin_page() -> FileResponse:
    return FileResponse(UI_DIRECTORY / "admin.html")
