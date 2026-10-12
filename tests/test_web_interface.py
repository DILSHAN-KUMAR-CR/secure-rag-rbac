from fastapi.testclient import TestClient

from app.main import app


def test_web_interface_pages_are_available() -> None:
    with TestClient(app) as client:
        login = client.get("/ui")
        chat = client.get("/ui/chat")
        admin = client.get("/ui/admin")

    assert login.status_code == 200
    assert "Sign in to continue" in login.text
    assert chat.status_code == 200
    assert "Ask your organization" in chat.text
    assert admin.status_code == 200
    assert "Access and knowledge controls" in admin.text


def test_ui_responses_include_browser_security_headers() -> None:
    with TestClient(app) as client:
        response = client.get("/ui/chat")

    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "no-referrer"
    policy = response.headers["content-security-policy"]
    assert "default-src 'self'" in policy
    assert "object-src 'none'" in policy
    assert "frame-ancestors 'none'" in policy


def test_ui_static_assets_are_served() -> None:
    with TestClient(app) as client:
        stylesheet = client.get("/ui-static/styles.css")
        common_script = client.get("/ui-static/common.js")

    assert stylesheet.status_code == 200
    assert "--brand:" in stylesheet.text
    assert common_script.status_code == 200
    assert "sessionStorage" in common_script.text


def test_admin_page_does_not_embed_private_runtime_data() -> None:
    with TestClient(app) as client:
        response = client.get("/ui/admin")

    assert "GEMINI_API_KEY" not in response.text
    assert "access_token" not in response.text
    assert "password_hash" not in response.text
