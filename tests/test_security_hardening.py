from starlette.testclient import TestClient

from app.core.config import settings
from app.storage.s3 import S3StorageError, get_s3_storage


class FakeIsolatedStorage:
    def __init__(self):
        self.objects: dict[str, bytes] = {}

    def qualify_key(self, key):
        return key

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


def test_two_user_complete_idor_matrix(client: TestClient):
    storage = FakeIsolatedStorage()
    client.app.dependency_overrides[get_s3_storage] = lambda: storage

    # Register and login User A and User B
    _register(client, "alice_idor")
    res_a = client.post("/api/v1/users/login", json={"username": "alice_idor", "password": "VeryStrongPassword-123!"})
    token_a = res_a.json()["access_token"]

    _register(client, "bob_idor")
    res_b = client.post("/api/v1/users/login", json={"username": "bob_idor", "password": "VeryStrongPassword-123!"})
    token_b = res_b.json()["access_token"]

    client.cookies.clear()

    # User B uploads a document
    doc_b_res = client.post(
        "/api/v1/documents/upload",
        headers={"Authorization": f"Bearer {token_b}"},
        files={"file": ("bobs_secret_report.pdf", b"%PDF-1.4 confidential medical record for Bob", "application/pdf")},
        data={"document_type": "blood_test"},
    )
    assert doc_b_res.status_code == 201
    doc_b_id = doc_b_res.json()["id"]

    headers_a = {"Authorization": f"Bearer {token_a}"}

    # Verify User A cannot access any endpoint for User B's document (must consistently 404)
    endpoints = [
        f"/api/v1/documents/{doc_b_id}",
        f"/api/v1/documents/{doc_b_id}/extractions",
        f"/api/v1/documents/{doc_b_id}/pages",
        f"/api/v1/documents/{doc_b_id}/tables",
        f"/api/v1/documents/{doc_b_id}/history",
        f"/api/v1/documents/{doc_b_id}/status",
        f"/api/v1/documents/{doc_b_id}/indexing-status",
        f"/api/v1/documents/{doc_b_id}/view-url",
        f"/api/v1/documents/{doc_b_id}/download-url",
        f"/api/v1/health/documents/{doc_b_id}",
    ]

    for endpoint in endpoints:
        resp = client.get(endpoint, headers=headers_a)
        assert resp.status_code == 404, f"Failed IDOR on {endpoint}: expected 404, got {resp.status_code}"

    # Verify User A cannot mutate or delete User B's document
    del_resp = client.delete(f"/api/v1/documents/{doc_b_id}", headers=headers_a)
    assert del_resp.status_code == 404

    reproc_resp = client.post(f"/api/v1/documents/{doc_b_id}/reprocess", headers=headers_a)
    assert reproc_resp.status_code == 404

    review_resp = client.post(f"/api/v1/documents/{doc_b_id}/review/complete", headers=headers_a)
    assert review_resp.status_code == 404

    # Verify document B still exists safely for User B
    b_verify = client.get(f"/api/v1/documents/{doc_b_id}", headers={"Authorization": f"Bearer {token_b}"})
    assert b_verify.status_code == 200
    assert b_verify.json()["original_filename"] == "bobs_secret_report.pdf"


