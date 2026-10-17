from __future__ import annotations

from io import BytesIO
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import settings
from app.storage.s3 import S3StorageError, get_s3_storage


class FakeStorage:
    def __init__(self):
        self.objects: dict[str, bytes] = {}
        self.fail_upload = False
        self.fail_delete = False

    def credential_source(self):
        return "test_mock"

    def upload_fileobj(self, source, key, content_type, filename):
        if self.fail_upload:
            raise S3StorageError("missing_permissions", "AWS denied access; check the IAM policy and bucket permissions.")
        self.objects[key] = source.read()

    def delete_object(self, key):
        if self.fail_delete:
            raise S3StorageError("missing_permissions", "AWS denied access; check the IAM policy and bucket permissions.")
        self.objects.pop(key, None)

    def download_file(self, key, destination):
        if key not in self.objects:
            raise S3StorageError("object_not_found", "The requested report is unavailable.")
        with open(destination, "wb") as target:
            target.write(self.objects[key])

    def presigned_url(self, key, filename, content_type, inline):
        assert key in self.objects
        return f"https://private.example/{key}?inline={str(inline).lower()}"

    def verify_bucket(self):
        return {
            "bucket_accessible": True,
            "private_configuration_verified": True,
            "checks": {"block_public_acls": True, "ignore_public_acls": True, "block_public_policy": True,
                       "restrict_public_buckets": True, "policy_is_public": False, "public_acl_grant_found": False},
            "unverified_checks": [],
        }


@pytest.fixture
def storage_client(client: TestClient):
    storage = FakeStorage()
    client.app.dependency_overrides[get_s3_storage] = lambda: storage
    return client, storage


def create_user(client: TestClient, username: str) -> str:
    result = client.post("/api/v1/users/register", json={
        "username": username,
        "email": f"{username}@example.com",
        "password": "A-strong-test-password-123!",
    })
    assert result.status_code == 201, result.text
    login = client.post("/api/v1/users/login", json={"username": username, "password": "A-strong-test-password-123!"})
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]
    client.cookies.clear()
    return token


def upload(client: TestClient, token: str, name: str = "lab.pdf", document_type: str = "blood_test"):
    return client.post(
        "/api/v1/documents/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": (name, BytesIO(b"%PDF-1.7 example report"), "application/pdf")},
        data={"document_type": document_type},
    )


def test_upload_listing_and_empty_pagination_are_user_scoped(storage_client):
    client, _storage = storage_client
    token_a = create_user(client, "alice")
    token_b = create_user(client, "bob")
    uploaded_a = upload(client, token_a)
    uploaded_b = upload(client, token_b, "scan.pdf", "mri")
    assert uploaded_a.status_code == 201, uploaded_a.text
    assert uploaded_b.status_code == 201, uploaded_b.text
    assert UUID(uploaded_a.json()["id"])
    assert uploaded_a.json()["processing_state"] == "queued"
    assert uploaded_a.json()["processing_version"] == 1

    page_a = client.get("/api/v1/documents?limit=1", headers={"Authorization": f"Bearer {token_a}"})
    assert page_a.status_code == 200
    assert page_a.json()["total"] == 1
    assert page_a.json()["summary"]["total_reports"] == 1
    assert page_a.json()["items"][0]["original_filename"] == "lab.pdf"
    assert client.get("/api/v1/documents?offset=100", headers={"Authorization": f"Bearer {token_a}"}).json()["items"] == []


def test_unauthenticated_and_invalid_uploads_are_rejected(storage_client, monkeypatch):
    client, _storage = storage_client
    token = create_user(client, "uploaduser")
    assert client.get("/api/v1/documents").status_code == 401
    assert client.post("/api/v1/documents/upload").status_code == 401
    unsupported = client.post("/api/v1/documents/upload", headers={"Authorization": f"Bearer {token}"}, files={"file": ("notes.txt", b"text", "text/plain")}, data={"document_type": "other"})
    assert unsupported.status_code == 415
    monkeypatch.setattr("app.documents.router.settings.S3_MAX_UPLOAD_BYTES", 8)
    oversized = upload(client, token)
    assert oversized.status_code == 413


def test_owner_only_metadata_presigned_urls_and_delete(storage_client):
    client, storage = storage_client
    token_a = create_user(client, "owner")
    token_b = create_user(client, "visitor")
    created = upload(client, token_a)
    document_id = created.json()["id"]

    assert client.get(f"/api/v1/documents/{document_id}", headers={"Authorization": f"Bearer {token_b}"}).status_code == 404
    assert client.get(f"/api/v1/documents/{document_id}/view-url", headers={"Authorization": f"Bearer {token_b}"}).status_code == 404
    assert client.get(f"/api/v1/documents/{document_id}/download-url", headers={"Authorization": f"Bearer {token_b}"}).status_code == 404
    assert client.delete(f"/api/v1/documents/{document_id}", headers={"Authorization": f"Bearer {token_b}"}).status_code == 404

    view = client.get(f"/api/v1/documents/{document_id}/view-url", headers={"Authorization": f"Bearer {token_a}"})
    download = client.get(f"/api/v1/documents/{document_id}/download-url", headers={"Authorization": f"Bearer {token_a}"})
    assert view.status_code == 200 and "inline=true" in view.json()["url"]
    assert download.status_code == 200 and "inline=false" in download.json()["url"]
    assert client.delete(f"/api/v1/documents/{document_id}", headers={"Authorization": f"Bearer {token_a}"}).status_code == 204
    assert not storage.objects


def test_s3_errors_and_storage_check_are_safe(storage_client, monkeypatch):
    client, storage = storage_client
    token = create_user(client, "storageuser")
    storage.fail_upload = True
    response = upload(client, token)
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "missing_permissions"
    assert "AWS_ACCESS_KEY_ID" not in response.text
    storage.fail_upload = False
    monkeypatch.setattr(settings, "S3_BUCKET_NAME", "nirmayaai01-514917275055-eu-north-1-an")
    check = client.get("/api/v1/documents/storage/check", headers={"Authorization": f"Bearer {token}"})
    assert check.status_code == 200
    assert check.json()["private_configuration_verified"] is True


def test_storage_check_without_bucket_configuration(storage_client, monkeypatch):
    client, _storage = storage_client
    token = create_user(client, "configuser")
    monkeypatch.setattr(settings, "S3_BUCKET_NAME", None)
    result = client.get("/api/v1/documents/storage/check", headers={"Authorization": f"Bearer {token}"})
    assert result.status_code == 200
    assert result.json()["configured"] is False
    assert "bucket_configuration" in result.json()["unverified_checks"]


def test_failed_s3_delete_remains_pending_for_retry(storage_client):
    client, storage = storage_client
    token = create_user(client, "retrydelete")
    created = upload(client, token)
    document_id = created.json()["id"]
    storage.fail_delete = True

    failed = client.delete(f"/api/v1/documents/{document_id}", headers={"Authorization": f"Bearer {token}"})
    assert failed.status_code == 503
    listed = client.get("/api/v1/documents", headers={"Authorization": f"Bearer {token}"})
    assert listed.status_code == 200
    assert listed.json()["items"][0]["upload_status"] == "deleting"
    assert listed.json()["items"][0]["processing_state"] == "deletion_pending"


def test_database_failure_after_s3_upload_attempts_object_cleanup(storage_client, monkeypatch):
    client, storage = storage_client
    token = create_user(client, "dbfailure")

    async def fail_tenant_setup(_db, _user_id):
        raise SQLAlchemyError("database details must not leak")

    monkeypatch.setattr("app.documents.router.set_tenant_context", fail_tenant_setup)
    response = upload(client, token)
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "document_metadata_save_failed"
    assert not storage.objects
    assert "database details" not in response.text
