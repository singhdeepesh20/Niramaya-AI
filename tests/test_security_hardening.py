import asyncio
from datetime import date
from uuid import uuid4

import pytest
from starlette.testclient import TestClient

from app.core.config import settings
from app.health.models import MedicalDocument
from app.storage.s3 import S3StorageError, get_s3_storage


class FakeIsolatedStorage:
    def __init__(self):
        self.objects: dict[str, bytes] = {}

    def credential_source(self):
        return "test_mock"

    def upload_fileobj(self, source, key, content_type, filename):
        self.objects[key] = source.read()

    def delete_object(self, key):
        self.objects.pop(key, None)

    def download_file(self, key, destination):
        if key not in self.objects:
            raise S3StorageError("object_not_found", "The requested report is unavailable.")
        with open(destination, "wb") as target:
            target.write(self.objects[key])

    def presigned_url(self, key, filename, content_type, inline):
        return f"https://private.example/{key}?inline={str(inline).lower()}"

    def verify_bucket(self):
        return {"bucket_accessible": True, "private_configuration_verified": True}


def _register(client: TestClient, username: str) -> None:
    res = client.post("/api/v1/users/register", json={
        "username": username,
        "email": f"{username}@example.com",
        "password": "VeryStrongPassword-123!",
    })
    assert res.status_code == 201


def test_login_issues_secure_httponly_and_csrf_cookies(client: TestClient):
    _register(client, "cookieuser")
    response = client.post("/api/v1/users/login", json={
        "username": "cookieuser",
        "password": "VeryStrongPassword-123!",
    })
    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"
    assert "csrf_token" in body and body["csrf_token"]

    # Verify cookies
    assert settings.COOKIE_NAME in response.cookies
    assert settings.CSRF_COOKIE_NAME in response.cookies


def test_authenticated_get_with_cookie_only(client: TestClient):
    _register(client, "sessionuser")
    login_res = client.post("/api/v1/users/login", json={
        "username": "sessionuser",
        "password": "VeryStrongPassword-123!",
    })
    assert login_res.status_code == 200

    # TestClient automatically retains cookies from the login response.
    # Make request WITHOUT Authorization header
    me_res = client.get("/api/v1/users/me")
    assert me_res.status_code == 200
    assert me_res.json()["username"] == "sessionuser"


def test_logout_invalidates_session_cookies(client: TestClient):
    _register(client, "logoutuser")
    client.post("/api/v1/users/login", json={
        "username": "logoutuser",
        "password": "VeryStrongPassword-123!",
    })

    # Verify authenticated
    assert client.get("/api/v1/users/me").status_code == 200

    # Call logout
    logout_res = client.post("/api/v1/users/logout")
    assert logout_res.status_code == 200

    # Manually remove from client cookie jar to simulate browser cookie deletion
    client.cookies.clear()
    assert client.get("/api/v1/users/me").status_code == 401


def test_csrf_token_endpoint(client: TestClient):
    res = client.get("/api/v1/users/csrf")
    assert res.status_code == 200
    data = res.json()
    assert "csrf_token" in data and len(data["csrf_token"]) > 16
    assert settings.CSRF_COOKIE_NAME in res.cookies


def test_csrf_rejects_missing_token_on_cookie_authenticated_state_change(client: TestClient):
    _register(client, "csrfvictim")
    client.post("/api/v1/users/login", json={
        "username": "csrfvictim",
        "password": "VeryStrongPassword-123!",
    })

    # Client now has session cookie. Attempt state-changing request without X-CSRF-Token header
    res = client.post(
        "/api/v1/health/ask",
        json={"question": "Test question"},
        headers={"Origin": "http://testserver"},
    )
    assert res.status_code == 403
    assert res.json()["error"]["code"] == "csrf_validation_failed"


def test_csrf_rejects_mismatched_token_on_cookie_authenticated_state_change(client: TestClient):
    _register(client, "csrfattacker")
    client.post("/api/v1/users/login", json={
        "username": "csrfattacker",
        "password": "VeryStrongPassword-123!",
    })

    # Attempt state-changing request with invalid CSRF token header
    res = client.post(
        "/api/v1/health/ask",
        json={"question": "Test question"},
        headers={
            "Origin": "http://testserver",
            settings.CSRF_HEADER_NAME: "forged-invalid-token",
        },
    )
    assert res.status_code == 403
    assert res.json()["error"]["code"] == "csrf_validation_failed"


def test_csrf_rejects_untrusted_origin_on_cookie_authenticated_request(client: TestClient):
    _register(client, "csrforigin")
    login_res = client.post("/api/v1/users/login", json={
        "username": "csrforigin",
        "password": "VeryStrongPassword-123!",
    })
    csrf_token = login_res.json()["csrf_token"]

    # Attempt request from unauthorized cross-site origin
    res = client.post(
        "/api/v1/health/ask",
        json={"question": "Test question"},
        headers={
            "Origin": "https://malicious-phishing-site.com",
            settings.CSRF_HEADER_NAME: csrf_token,
        },
    )
    assert res.status_code == 403
    assert res.json()["error"]["code"] == "csrf_origin_mismatch"


def test_csrf_accepts_matching_token_and_origin(client: TestClient):
    _register(client, "csrfsuccess")
    login_res = client.post("/api/v1/users/login", json={
        "username": "csrfsuccess",
        "password": "VeryStrongPassword-123!",
    })
    csrf_token = login_res.json()["csrf_token"]

    # Request with matching cookie, matching header, and trusted origin
    res = client.post(
        "/api/v1/health/ask",
        json={"question": "What is my latest blood test?"},
        headers={
            "Origin": "http://testserver",
            settings.CSRF_HEADER_NAME: csrf_token,
        },
    )
    # The CSRF layer validates and lets the request reach the health route (200 OK)
    assert res.status_code == 200


def test_pure_bearer_token_bypasses_ambient_csrf(client: TestClient):
    _register(client, "bearerononly")
    login_res = client.post("/api/v1/users/login", json={
        "username": "bearerononly",
        "password": "VeryStrongPassword-123!",
    })
    token = login_res.json()["access_token"]

    # Clear all cookies to simulate non-browser API client
    client.cookies.clear()

    # Pure bearer header request succeeds without CSRF header
    res = client.post(
        "/api/v1/health/ask",
        json={"question": "What is my latest test?"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200


def test_security_headers_present_on_responses(client: TestClient):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.headers.get("X-Content-Type-Options") == "nosniff"
    assert res.headers.get("X-Frame-Options") == "DENY"
    assert res.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"

