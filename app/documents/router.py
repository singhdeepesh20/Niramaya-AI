from datetime import date, datetime, timedelta, timezone
from pathlib import PurePosixPath
import re
from typing import Annotated, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from sqlalchemy import case, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.core.config import settings
from app.core.errors import APIError
from app.database import get_db
from app.documents.dtos import (
    DocumentPagePublic, DocumentPagesResponse, DocumentSummary, DocumentTablePublic,
    DocumentTablesResponse, DocumentType, ExtractedEntitiesResponse, ExtractedEntityPublic,
    MedicalDocumentPage, MedicalDocumentPublic, PresignedDocumentUrl, ProcessingEventPublic,
    ProcessingHistoryResponse, ProcessingStagePublic, ProcessingStatusResponse, StorageCheck,
)
from app.documents.cleanup import VectorCleanupError, cleanup_document_objects
from app.documents.processing import InvalidTransition, ProcessingState, enqueue_processing, enqueue_reprocessing, transition_document
from app.documents.models import DocumentProcessingEvent, DocumentProcessingJob, DocumentStageRun
from app.health.models import DocumentExtractedTable, DocumentPage, MedicalDocument, MedicalEntity
from app.health.repository import get_authorized_document, set_tenant_context
from app.storage.s3 import S3Storage, S3StorageError, get_s3_storage
from app.user.controller import get_current_user
from app.user.models import User

router = APIRouter(prefix="/api/v1/documents", tags=["medical documents"])

_FILE_TYPES = {
    ".pdf": ("application/pdf", b"%PDF-"),
    ".jpg": ("image/jpeg", b"\xff\xd8\xff"),
    ".jpeg": ("image/jpeg", b"\xff\xd8\xff"),
    ".png": ("image/png", b"\x89PNG\r\n\x1a\n"),
}
_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")


def _api_storage_error(error: S3StorageError) -> APIError:
    if error.category in {"missing_permissions", "invalid_credentials", "credentials_missing", "incomplete_credentials"}:
        status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    else:
        status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return APIError(status_code, error.category, error.public_message)


def _safe_filename(original: str | None) -> tuple[str, str, bytes]:
    leaf = PurePosixPath((original or "").replace("\\", "/")).name
    filename = _CONTROL_CHARS.sub("", leaf).strip().strip(".")[:255]
    if not filename:
        raise APIError(422, "invalid_filename", "Choose a file with a valid filename.")
    suffix = PurePosixPath(filename.lower()).suffix
    if suffix not in _FILE_TYPES:
        raise APIError(415, "unsupported_file_type", "Upload a PDF, JPEG, or PNG file.")
    content_type, signature = _FILE_TYPES[suffix]
    return filename, content_type, signature


def _validate_content_type(claimed: str | None, expected: str) -> None:
    if claimed and claimed.lower() not in {expected, "application/octet-stream"}:
        raise APIError(415, "content_type_mismatch", "The file contents do not match the selected file type.")


async def _validate_upload(upload: UploadFile) -> tuple[str, str, int]:
    filename, content_type, signature = _safe_filename(upload.filename)
    size = upload.size
    if size is None:
        await upload.seek(0, 2)
        size = upload.file.tell()
    await upload.seek(0)
    if size <= 0:
        raise APIError(422, "empty_file", "The selected file is empty.")
    if size > settings.S3_MAX_UPLOAD_BYTES:
        raise APIError(413, "file_too_large", "The file exceeds the configured upload size limit.")
    header = await upload.read(len(signature))
    await upload.seek(0)
    if not header.startswith(signature):
        raise APIError(415, "invalid_file_signature", "The file contents do not match a supported PDF or image.")
    _validate_content_type(upload.content_type, content_type)
    return filename, content_type, size


@router.get("/storage/check", response_model=StorageCheck)
async def check_storage(
    user: Annotated[User, Depends(get_current_user)],
    storage: Annotated[S3Storage, Depends(get_s3_storage)],
) -> StorageCheck:
    del user  # Authentication is required; no user-specific bucket settings are exposed.
    configured = bool(settings.AWS_REGION and settings.S3_BUCKET_NAME)
    if not configured:
        return StorageCheck(
            configured=False,
            region=settings.AWS_REGION,
            bucket_accessible=False,
            private_configuration_verified=False,
            checks={},
            unverified_checks=["bucket_configuration"],
            credential_source=storage.credential_source(),
        )
    try:
        result = await run_in_threadpool(storage.verify_bucket)
    except S3StorageError as exc:
        raise _api_storage_error(exc) from exc
    return StorageCheck(
        configured=True,
        region=settings.AWS_REGION,
        credential_source=storage.credential_source(),
        **result,
    )


@router.post("/upload", response_model=MedicalDocumentPublic, status_code=status.HTTP_201_CREATED)
async def upload_document(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    storage: Annotated[S3Storage, Depends(get_s3_storage)],
    file: Annotated[UploadFile, File(...)],
    document_type: Annotated[DocumentType, Form(...)],
    document_date: Annotated[date | None, Form()] = None,
) -> MedicalDocument:
    user_id = user.id
    filename, content_type, file_size = await _validate_upload(file)
    document_id = uuid4()
    object_key = f"users/{user_id}/documents/{document_id}"
    # Do not hold a database transaction open during S3 network I/O.
    await db.rollback()
    try:
        await run_in_threadpool(storage.upload_fileobj, file.file, object_key, content_type, filename)
    except S3StorageError as exc:
        raise _api_storage_error(exc) from exc
    finally:
        await file.close()

    document = MedicalDocument(
        id=document_id,
        user_id=user_id,
        name=filename,
        original_filename=filename,
        document_type=document_type,
        document_date=document_date,
        content_type=content_type,
        file_size=file_size,
        object_key=object_key,
        upload_status="ready",
        metadata_json={},
    )
    try:
        await set_tenant_context(db, user_id)
        db.add(document)
        await db.flush()
        await enqueue_processing(db, document, actor="upload_api")
        await db.commit()
        # The commit clears PostgreSQL's transaction-local RLS identity. Restore
        # it before refresh starts a new transaction, or the row is invisible.
        await set_tenant_context(db, user_id)
        await db.refresh(document)
    except SQLAlchemyError as exc:
        await db.rollback()
        try:
            await run_in_threadpool(storage.delete_object, object_key)
        except S3StorageError as cleanup_error:
            # Log only categories: object keys are user-specific and considered sensitive metadata.
            import logging

            logging.getLogger("niramaya.documents").error(
                "upload_cleanup_failed s3_category=%s db_error_type=%s",
                cleanup_error.category,
                type(exc).__name__,
            )
        raise APIError(503, "document_metadata_save_failed", "The report could not be saved. Please retry the upload.") from exc
    return document


@router.get("", response_model=MedicalDocumentPage)
async def list_documents(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    q: Annotated[str | None, Query(max_length=100)] = None,
    document_type: Annotated[DocumentType | None, Query()] = None,
    date_from: date | None = None,
    date_to: date | None = None,
    sort: Literal["newest", "oldest"] = "newest",
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0, le=100_000)] = 0,
) -> MedicalDocumentPage:
    if date_from and date_to and date_from > date_to:
        raise APIError(422, "invalid_date_range", "date_from must be on or before date_to.")
    await set_tenant_context(db, user.id)
    owner = MedicalDocument.user_id == user.id
    # Keep deletion-pending items visible so the owner can retry deletion after an outage.
    available = owner & (MedicalDocument.upload_status.in_(("ready", "deleting")))

    summary_result = await db.execute(
        select(
            func.count(MedicalDocument.id),
            func.count(case((MedicalDocument.document_type.in_(("cbc", "blood_test")), 1))),
            func.count(case((MedicalDocument.document_type.in_(("mri", "x_ray")), 1))),
            func.count(case((MedicalDocument.created_at >= datetime.now(timezone.utc) - timedelta(days=30), 1))),
        ).where(available)
    )
    total_reports, blood_tests, imaging_reports, recent_uploads = summary_result.one()
    summary = DocumentSummary(
        total_reports=total_reports,
        blood_tests=blood_tests,
        imaging_reports=imaging_reports,
        recent_uploads=recent_uploads,
    )

    statement = select(MedicalDocument).where(available)
    if q and q.strip():
        statement = statement.where(MedicalDocument.original_filename.ilike(f"%{q.strip()}%"))
    if document_type:
        statement = statement.where(MedicalDocument.document_type == document_type)
    if date_from:
        statement = statement.where(MedicalDocument.created_at >= datetime.combine(date_from, datetime.min.time(), timezone.utc))
    if date_to:
        statement = statement.where(MedicalDocument.created_at < datetime.combine(date_to + timedelta(days=1), datetime.min.time(), timezone.utc))

    count_statement = select(func.count()).select_from(statement.subquery())
    total = await db.scalar(count_statement) or 0
    order = MedicalDocument.created_at.asc() if sort == "oldest" else MedicalDocument.created_at.desc()
    result = await db.scalars(statement.order_by(order, MedicalDocument.id).limit(limit).offset(offset))
    return MedicalDocumentPage(items=list(result.all()), total=total, limit=limit, offset=offset, summary=summary)


async def _owned_document(db: AsyncSession, user: User, document_id: UUID) -> MedicalDocument:
    document = await get_authorized_document(db, user.id, document_id)
    if document is None or document.upload_status not in {"ready", "deleting"}:
        raise APIError(404, "document_not_found", "Report not found.")
    return document


@router.get("/{document_id}", response_model=MedicalDocumentPublic)
async def read_document(
    document_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MedicalDocument:
    document = await _owned_document(db, user, document_id)
    if document.upload_status != "ready":
        raise APIError(404, "document_not_found", "Report not found.")
    return document


@router.get("/{document_id}/status", response_model=ProcessingStatusResponse)
async def get_document_processing_status(
    document_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ProcessingStatusResponse:
    document = await _owned_document(db, user, document_id)
    generation = document.processing_generation
    runs = (await db.scalars(select(DocumentStageRun).where(
        DocumentStageRun.document_id == document_id,
        DocumentStageRun.user_id == user.id,
        DocumentStageRun.generation == generation,
    ).order_by(DocumentStageRun.id))).all()
    processing = dict(document.metadata_json or {}).get("processing", {})
    return ProcessingStatusResponse(
        document_id=document.id, document_type=document.document_type,
        processing_state=document.processing_state, processing_version=document.processing_version,
        processing_generation=generation, processing_updated_at=document.processing_updated_at,
        processing=processing, stages=[ProcessingStagePublic.model_validate(run, from_attributes=True) for run in runs],
    )


@router.get("/{document_id}/extractions", response_model=ExtractedEntitiesResponse)
async def get_document_extractions(
    document_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ExtractedEntitiesResponse:
    document = await _owned_document(db, user, document_id)
    rows = (await db.scalars(select(MedicalEntity).where(
        MedicalEntity.document_id == document_id,
        MedicalEntity.user_id == user.id,
        MedicalEntity.extraction_generation == document.processing_generation,
    ).order_by(MedicalEntity.page_number, MedicalEntity.category, MedicalEntity.name, MedicalEntity.id))).all()
    return ExtractedEntitiesResponse(
        document_id=document_id, generation=document.processing_generation,
        items=[ExtractedEntityPublic.model_validate(row, from_attributes=True) for row in rows],
    )


@router.get("/{document_id}/tables", response_model=DocumentTablesResponse)
async def get_document_tables(
    document_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DocumentTablesResponse:
    document = await _owned_document(db, user, document_id)
    rows = (await db.scalars(select(DocumentExtractedTable).where(
        DocumentExtractedTable.document_id == document_id,
        DocumentExtractedTable.user_id == user.id,
        DocumentExtractedTable.extraction_generation == document.processing_generation,
    ).order_by(DocumentExtractedTable.page_number, DocumentExtractedTable.table_index))).all()
    return DocumentTablesResponse(
        document_id=document_id, generation=document.processing_generation,
        items=[DocumentTablePublic.model_validate(row, from_attributes=True) for row in rows],
    )


@router.get("/{document_id}/pages", response_model=DocumentPagesResponse)
async def get_document_pages(
    document_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
    offset: Annotated[int, Query(ge=0, le=5000)] = 0,
) -> DocumentPagesResponse:
    document = await _owned_document(db, user, document_id)
    statement = select(DocumentPage).where(
        DocumentPage.document_id == document_id,
        DocumentPage.user_id == user.id,
        DocumentPage.extraction_generation == document.processing_generation,
    )
    total = await db.scalar(select(func.count()).select_from(statement.subquery())) or 0
    rows = (await db.scalars(statement.order_by(DocumentPage.page_number).limit(limit).offset(offset))).all()
    return DocumentPagesResponse(
        document_id=document_id, generation=document.processing_generation, total=total,
        limit=limit, offset=offset,
        items=[DocumentPagePublic.model_validate(row, from_attributes=True) for row in rows],
    )


@router.get("/{document_id}/history", response_model=ProcessingHistoryResponse)
async def get_document_history(
    document_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ProcessingHistoryResponse:
    document = await _owned_document(db, user, document_id)
    events = (await db.scalars(select(DocumentProcessingEvent).where(
        DocumentProcessingEvent.document_id == document_id,
        DocumentProcessingEvent.user_id == user.id,
    ).order_by(DocumentProcessingEvent.state_version))).all()
    runs = (await db.scalars(select(DocumentStageRun).where(
        DocumentStageRun.document_id == document_id,
        DocumentStageRun.user_id == user.id,
        DocumentStageRun.generation == document.processing_generation,
    ).order_by(DocumentStageRun.started_at, DocumentStageRun.id))).all()
    job = await db.scalar(select(DocumentProcessingJob).where(
        DocumentProcessingJob.document_id == document_id,
        DocumentProcessingJob.user_id == user.id,
        DocumentProcessingJob.job_type == "process",
        DocumentProcessingJob.idempotency_key == f"process:{document_id}:{document.processing_generation}",
    ))
    processing = dict(document.metadata_json or {}).get("processing", {})
    return ProcessingHistoryResponse(
        document_id=document_id, generation=document.processing_generation,
        events=[ProcessingEventPublic.model_validate(event, from_attributes=True) for event in events],
        stages=[ProcessingStagePublic.model_validate(run, from_attributes=True) for run in runs],
        job_status=job.status if job else None,
        error_code=processing.get("last_error_code") or (job.last_reason_code if job and job.status == "failed" else None),
    )


async def _presigned_url(document_id: UUID, user: User, db: AsyncSession, storage: S3Storage, inline: bool) -> PresignedDocumentUrl:
    document = await _owned_document(db, user, document_id)
    if document.upload_status != "ready":
        raise APIError(404, "document_not_found", "Report not found.")
    try:
        url = await run_in_threadpool(
            storage.presigned_url,
            document.object_key,
            document.original_filename,
            document.content_type,
            inline,
        )
    except S3StorageError as exc:
        raise _api_storage_error(exc) from exc
    return PresignedDocumentUrl(url=url, expires_in=settings.S3_PRESIGNED_URL_EXPIRES_SECONDS)


@router.get("/{document_id}/view-url", response_model=PresignedDocumentUrl)
async def create_view_url(
    document_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    storage: Annotated[S3Storage, Depends(get_s3_storage)],
) -> PresignedDocumentUrl:
    return await _presigned_url(document_id, user, db, storage, True)


@router.get("/{document_id}/download-url", response_model=PresignedDocumentUrl)
async def create_download_url(
    document_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    storage: Annotated[S3Storage, Depends(get_s3_storage)],
) -> PresignedDocumentUrl:
    return await _presigned_url(document_id, user, db, storage, False)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    storage: Annotated[S3Storage, Depends(get_s3_storage)],
) -> None:
    document = await _owned_document(db, user, document_id)
    if document.processing_state != ProcessingState.DELETION_PENDING.value:
        await transition_document(
            db, user_id=user.id, document_id=document_id,
            target=ProcessingState.DELETION_PENDING, actor="document_owner",
            reason_code="owner_requested_deletion",
        )
        document.upload_status = "deleting"
        db.add(DocumentProcessingJob(
            user_id=user.id, document_id=document_id, job_type="delete", status="pending",
            idempotency_key=f"delete:{document_id}",
        ))
        await db.commit()
    else:
        await db.rollback()
    try:
        await cleanup_document_objects(storage, object_key=document.object_key, user_id=user.id, document_id=document_id)
    except S3StorageError as exc:
        # Keep DELETION_PENDING and the durable delete job so cleanup can retry.
        await db.rollback()
        raise _api_storage_error(exc) from exc
    except VectorCleanupError as exc:
        await db.rollback()
        raise APIError(503, "vector_cleanup_unavailable", "Report cleanup is pending and will be retried.") from exc
    try:
        await set_tenant_context(db, user.id)
        await db.execute(
            DocumentProcessingJob.__table__.update()
            .where(DocumentProcessingJob.document_id == document_id, DocumentProcessingJob.user_id == user.id,
                   DocumentProcessingJob.job_type == "delete")
            .values(status="succeeded")
        )
        await db.delete(document)
        await db.commit()
    except SQLAlchemyError as exc:
        await db.rollback()
        raise APIError(503, "document_delete_pending", "The report is no longer available and deletion will be retried.") from exc


@router.post("/{document_id}/reprocess", response_model=MedicalDocumentPublic, status_code=status.HTTP_202_ACCEPTED)
async def reprocess_document(
    document_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MedicalDocument:
    """Owner-authorized reprocessing; identity always comes from the JWT."""
    try:
        await enqueue_reprocessing(db, user_id=user.id, document_id=document_id, actor="document_owner")
        await db.commit()
    except APIError:
        await db.rollback()
        raise
    except InvalidTransition as exc:
        await db.rollback()
        raise APIError(409, "invalid_processing_transition", "This report cannot be reprocessed in its current state.") from exc
    document = await get_authorized_document(db, user.id, document_id)
    if document is None:
        raise APIError(404, "document_not_found", "Report not found.")
    return document


@router.post("/{document_id}/review/complete", response_model=MedicalDocumentPublic)
async def complete_document_review(
    document_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MedicalDocument:
    """Record an authenticated owner review after backend validation stages succeeded."""
    try:
        document = await transition_document(db, user_id=user.id, document_id=document_id,
            target=ProcessingState.COMPLETED, actor="document_owner", reason_code="owner_review_acknowledged")
        await db.commit()
        await db.refresh(document)
        return document
    except APIError:
        await db.rollback()
        raise
    except InvalidTransition as exc:
        await db.rollback()
        raise APIError(409, "review_not_ready", "Required processing stages have not passed review.") from exc
