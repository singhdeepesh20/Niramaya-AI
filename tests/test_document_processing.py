from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from io import BytesIO
from uuid import UUID

from sqlalchemy import select, update

from app.documents.models import DocumentProcessingEvent, DocumentProcessingJob, DocumentStageRun
from app.documents.processing import InvalidTransition, MANDATORY_STAGES, ProcessingStage, ProcessingState, RetryableProcessingError, StageStatus, record_stage, retry_delay, transition_document
from app.documents.worker import process_one, recover_stale_jobs
from app.health.models import MedicalDocument
from test_documents_api import FakeStorage, create_user
from app.storage.s3 import get_s3_storage
import pymupdf


def synthetic_pdf(text="CBC\nHemoglobin 13.5 g/dL 12-16\nWBC 7.2 10^9/L"):
    pdf = pymupdf.open()
    page = pdf.new_page()
    page.insert_text((72, 72), text)
    payload = pdf.tobytes()
    pdf.close()
    return payload


def test_upload_outbox_and_safe_unconfigured_worker(client):
    storage = FakeStorage()
    client.app.dependency_overrides[get_s3_storage] = lambda: storage
    token = create_user(client, "workerstate")
    uploaded = client.post("/api/v1/documents/upload", headers={"Authorization": f"Bearer {token}"},
        files={"file": ("lab.pdf", BytesIO(synthetic_pdf()), "application/pdf")},
        data={"document_type": "blood_test"})
    assert uploaded.status_code == 201, uploaded.text
    document_id = uploaded.json()["id"]
    factory = client.app.state.test_session_factory

    async def run():
        async with factory() as db:
            job = (await db.scalars(select(DocumentProcessingJob).where(
                DocumentProcessingJob.document_id == UUID(document_id)
            ))).one()
            assert job.status == "pending"
            assert job.idempotency_key.endswith(":0")
        assert await process_one(factory, storage=storage)
        async with factory() as db:
            document = (await db.scalars(select(MedicalDocument).where(MedicalDocument.id == UUID(document_id)))).one()
            assert document.processing_state == "review_required"
            job = (await db.scalars(select(DocumentProcessingJob).where(
                DocumentProcessingJob.document_id == UUID(document_id)
            ))).one()
            assert job.status == "succeeded"
            events = (await db.scalars(select(DocumentProcessingEvent).where(
                DocumentProcessingEvent.document_id == UUID(document_id)
            ).order_by(DocumentProcessingEvent.state_version))).all()
            assert [event.next_state for event in events] == ["queued", "processing", "review_required"]
            assert (await db.scalars(select(DocumentStageRun).where(
                DocumentStageRun.document_id == UUID(document_id),
                DocumentStageRun.status == "succeeded",
            ))).all()

    asyncio.run(run())


def test_owner_only_reprocessing_and_premature_review_rejected(client):
    storage = FakeStorage()
    client.app.dependency_overrides[get_s3_storage] = lambda: storage
    owner = create_user(client, "reprocessowner")
    stranger = create_user(client, "reprocessstranger")
    uploaded = client.post("/api/v1/documents/upload", headers={"Authorization": f"Bearer {owner}"},
        files={"file": ("lab.pdf", BytesIO(synthetic_pdf()), "application/pdf")},
        data={"document_type": "blood_test"})
    doc_id = uploaded.json()["id"]
    assert client.post(f"/api/v1/documents/{doc_id}/reprocess", headers={"Authorization": f"Bearer {stranger}"}).status_code == 404
    assert client.post(f"/api/v1/documents/{doc_id}/review/complete", headers={"Authorization": f"Bearer {owner}"}).status_code == 409
    factory = client.app.state.test_session_factory
    owner_id = UUID(client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {owner}"}).json()["id"])

    async def mark_old_generation_complete():
        async with factory() as db:
            for stage in MANDATORY_STAGES:
                await record_stage(db, user_id=owner_id, document_id=UUID(doc_id), generation=0,
                    stage=stage, status=StageStatus.SUCCEEDED)
            await db.commit()

    asyncio.run(process_one(factory, storage=storage))
    asyncio.run(mark_old_generation_complete())
    current = client.get(f"/api/v1/documents/{doc_id}", headers={"Authorization": f"Bearer {owner}"})
    assert current.status_code == 200, current.text
    assert current.json()["processing_state"] in {"review_required", "completed", "failed"}, current.json()
    reprocessed = client.post(f"/api/v1/documents/{doc_id}/reprocess", headers={"Authorization": f"Bearer {owner}"})
    assert reprocessed.status_code == 202, reprocessed.text
    assert reprocessed.json()["processing_state"] == "queued"
    assert reprocessed.json()["processing_version"] == 4
    assert client.post(f"/api/v1/documents/{doc_id}/review/complete", headers={"Authorization": f"Bearer {owner}"}).status_code == 409


def test_synthetic_pdf_processing_results_and_document_isolation(client):
    storage = FakeStorage()
    client.app.dependency_overrides[get_s3_storage] = lambda: storage
    owner = create_user(client, "pipelineowner")
    stranger = create_user(client, "pipelinestranger")
    upload = client.post("/api/v1/documents/upload", headers={"Authorization": f"Bearer {owner}"},
        files={"file": ("synthetic-cbc.pdf", BytesIO(synthetic_pdf()), "application/pdf")},
        data={"document_type": "other"})
    assert upload.status_code == 201, upload.text
    document_id = upload.json()["id"]
    factory = client.app.state.test_session_factory
    assert asyncio.run(process_one(factory, storage=storage))

    owner_headers = {"Authorization": f"Bearer {owner}"}
    stranger_headers = {"Authorization": f"Bearer {stranger}"}
    entities = client.get(f"/api/v1/documents/{document_id}/extractions", headers=owner_headers)
    assert entities.status_code == 200, entities.text
    assert {item["name"] for item in entities.json()["items"]} >= {"hemoglobin", "wbc_count"}
    hemoglobin = next(item for item in entities.json()["items"] if item["name"] == "hemoglobin")
    assert hemoglobin["value"] == "13.5"
    assert hemoglobin["reference_range"] == "12-16"
    assert hemoglobin["page_number"] == 1
    assert "Hemoglobin 13.5" in hemoglobin["source_excerpt"]
    page_result = client.get(f"/api/v1/documents/{document_id}/pages", headers=owner_headers)
    assert page_result.status_code == 200
    assert "Hemoglobin 13.5" in page_result.json()["items"][0]["extracted_text"]
    status_result = client.get(f"/api/v1/documents/{document_id}/status", headers=owner_headers)
    assert status_result.status_code == 200
    assert status_result.json()["processing"]["pipeline"] == "deterministic-medical-v1"
    assert client.get(f"/api/v1/documents/{document_id}/history", headers=owner_headers).json()["events"]
    assert client.get(f"/api/v1/documents/{document_id}/extractions", headers=stranger_headers).status_code == 404
    assert client.get(f"/api/v1/documents/{document_id}/pages", headers=stranger_headers).status_code == 404
    assert client.get(f"/api/v1/documents/{document_id}/history", headers=stranger_headers).status_code == 404


def test_invalid_transition_table_is_enforced(client):
    client.app.dependency_overrides[get_s3_storage] = lambda: FakeStorage()
    token = create_user(client, "transitionuser")
    created = client.post("/api/v1/documents/upload", headers={"Authorization": f"Bearer {token}"},
        files={"file": ("lab.pdf", BytesIO(b"%PDF-1.7 report"), "application/pdf")},
        data={"document_type": "blood_test"})
    doc_id = created.json()["id"]
    user_id = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"}).json()["id"]
    factory = client.app.state.test_session_factory

    async def run():
        async with factory() as db:
            try:
                await transition_document(db, user_id=UUID(user_id),
                    document_id=UUID(doc_id), target=ProcessingState.COMPLETED,
                    actor="test", reason_code="test")
            except InvalidTransition:
                await db.rollback()
            else:
                raise AssertionError("queued documents must not transition directly to completed")

    asyncio.run(run())


def test_stale_worker_lease_recovers_to_queue(client):
    client.app.dependency_overrides[get_s3_storage] = lambda: FakeStorage()
    token = create_user(client, "stalelease")
    created = client.post("/api/v1/documents/upload", headers={"Authorization": f"Bearer {token}"},
        files={"file": ("lab.pdf", BytesIO(b"%PDF-1.7 report"), "application/pdf")},
        data={"document_type": "blood_test"})
    doc_id = UUID(created.json()["id"])
    factory = client.app.state.test_session_factory

    async def run():
        async with factory() as db:
            await db.execute(update(MedicalDocument).where(MedicalDocument.id == doc_id).values(
                processing_state="processing", processing_version=2))
            await db.execute(update(DocumentProcessingJob).where(DocumentProcessingJob.document_id == doc_id).values(
                status="running", attempts=1, locked_until=datetime.now(timezone.utc) - timedelta(minutes=1)))
            await db.commit()
        assert await recover_stale_jobs(factory) == 1
        async with factory() as db:
            document = (await db.scalars(select(MedicalDocument).where(MedicalDocument.id == doc_id))).one()
            job = (await db.scalars(select(DocumentProcessingJob).where(DocumentProcessingJob.document_id == doc_id))).one()
            assert document.processing_state == "queued"
            assert job.status == "pending"

    asyncio.run(run())
    assert retry_delay(1) == 5
    assert retry_delay(100) == 3600


def test_transient_stage_error_requeues_with_backoff(client):
    client.app.dependency_overrides[get_s3_storage] = lambda: FakeStorage()
    token = create_user(client, "transientstage")
    created = client.post("/api/v1/documents/upload", headers={"Authorization": f"Bearer {token}"},
        files={"file": ("lab.pdf", BytesIO(b"%PDF-1.7 report"), "application/pdf")},
        data={"document_type": "blood_test"})
    doc_id = UUID(created.json()["id"])
    factory = client.app.state.test_session_factory

    class TemporaryFailure:
        async def run_stage(self, stage, document, idempotency_key):
            raise RetryableProcessingError("provider_temporarily_unavailable")

    async def run():
        assert await process_one(factory, TemporaryFailure())
        async with factory() as db:
            document = (await db.scalars(select(MedicalDocument).where(MedicalDocument.id == doc_id))).one()
            job = (await db.scalars(select(DocumentProcessingJob).where(DocumentProcessingJob.document_id == doc_id))).one()
            assert document.processing_state == "queued"
            assert job.status == "pending" and job.attempts == 1
            available_at = job.available_at.replace(tzinfo=timezone.utc)
            assert available_at > datetime.now(timezone.utc)

    asyncio.run(run())
