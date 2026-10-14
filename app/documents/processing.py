"""Typed document processing lifecycle, queue contract, and guarded transitions."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from enum import StrEnum
from typing import Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIError
from app.documents.models import DocumentProcessingEvent, DocumentProcessingJob, DocumentStageRun
from app.health.models import MedicalDocument
from app.health.repository import set_tenant_context


class ProcessingState(StrEnum):
    UPLOADED = "uploaded"
    QUEUED = "queued"
    PROCESSING = "processing"
    REVIEW_REQUIRED = "review_required"
    COMPLETED = "completed"
    FAILED = "failed"
    DELETION_PENDING = "deletion_pending"


class ProcessingStage(StrEnum):
    CLASSIFICATION = "classification"
    TEXT_EXTRACTION = "text_extraction"
    TABLE_EXTRACTION = "table_extraction"
    ENTITY_EXTRACTION = "entity_extraction"
    NORMALIZATION = "normalization"
    PROVENANCE = "provenance"
    REVIEW_EVALUATION = "review_evaluation"
    VECTOR_INDEX = "vector_index"


class StageStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"


# Order is a DAG's valid execution order. Table extraction is optional; vector
# indexing is optional unless HEALTH_VECTOR_INDEX_REQUIRED is enabled.
STAGE_DEPENDENCIES: dict[ProcessingStage, tuple[ProcessingStage, ...]] = {
    ProcessingStage.CLASSIFICATION: (),
    ProcessingStage.TEXT_EXTRACTION: (ProcessingStage.CLASSIFICATION,),
    ProcessingStage.TABLE_EXTRACTION: (ProcessingStage.TEXT_EXTRACTION,),
    ProcessingStage.ENTITY_EXTRACTION: (ProcessingStage.TEXT_EXTRACTION,),
    ProcessingStage.NORMALIZATION: (ProcessingStage.ENTITY_EXTRACTION,),
    ProcessingStage.PROVENANCE: (ProcessingStage.NORMALIZATION,),
    ProcessingStage.REVIEW_EVALUATION: (ProcessingStage.PROVENANCE,),
    ProcessingStage.VECTOR_INDEX: (ProcessingStage.PROVENANCE,),
}
MANDATORY_STAGES = (
    ProcessingStage.CLASSIFICATION,
    ProcessingStage.TEXT_EXTRACTION,
    ProcessingStage.ENTITY_EXTRACTION,
    ProcessingStage.NORMALIZATION,
    ProcessingStage.PROVENANCE,
    ProcessingStage.REVIEW_EVALUATION,
)

ALLOWED_TRANSITIONS: dict[ProcessingState, frozenset[ProcessingState]] = {
    ProcessingState.UPLOADED: frozenset({ProcessingState.QUEUED, ProcessingState.DELETION_PENDING}),
    ProcessingState.QUEUED: frozenset({ProcessingState.PROCESSING, ProcessingState.DELETION_PENDING}),
    ProcessingState.PROCESSING: frozenset({ProcessingState.QUEUED, ProcessingState.REVIEW_REQUIRED, ProcessingState.COMPLETED, ProcessingState.FAILED, ProcessingState.DELETION_PENDING}),
    ProcessingState.REVIEW_REQUIRED: frozenset({ProcessingState.COMPLETED, ProcessingState.QUEUED, ProcessingState.DELETION_PENDING}),
    ProcessingState.COMPLETED: frozenset({ProcessingState.QUEUED, ProcessingState.DELETION_PENDING}),
    ProcessingState.FAILED: frozenset({ProcessingState.QUEUED, ProcessingState.DELETION_PENDING}),
    ProcessingState.DELETION_PENDING: frozenset(),
}


class InvalidTransition(ValueError):
    pass


class RetryableProcessingError(Exception):
    def __init__(self, reason_code: str):
        self.reason_code = reason_code


class PermanentProcessingError(Exception):
    def __init__(self, reason_code: str):
        self.reason_code = reason_code


class ReviewRequiredError(Exception):
    def __init__(self, reason_code: str):
        self.reason_code = reason_code


class StageProcessor(Protocol):
    async def run_stage(
        self,
        stage: ProcessingStage,
        document: MedicalDocument,
        idempotency_key: str,
    ) -> StageStatus: ...


class UnconfiguredStageProcessor:
    """Safe default: absent extraction adapters request review, never fake completion."""

    async def run_stage(self, stage: ProcessingStage, document: MedicalDocument, idempotency_key: str) -> StageStatus:
        del stage, document, idempotency_key
        raise ReviewRequiredError("processing_adapter_not_configured")


def required_stages(*, vector_index_required: bool) -> tuple[ProcessingStage, ...]:
    if vector_index_required:
        return (*MANDATORY_STAGES, ProcessingStage.VECTOR_INDEX)
    return MANDATORY_STAGES


async def transition_document(
    db: AsyncSession,
    *,
    user_id: UUID,
    document_id: UUID,
    target: ProcessingState,
    actor: str,
    reason_code: str,
    stage: ProcessingStage | None = None,
    expected_version: int | None = None,
    vector_index_required: bool = False,
) -> MedicalDocument:
    """Lock, validate, persist, and audit one owner-scoped state transition."""
    await set_tenant_context(db, user_id)
    result = await db.execute(
        select(MedicalDocument)
        .where(MedicalDocument.id == document_id, MedicalDocument.user_id == user_id)
        .with_for_update()
    )
    document = result.scalar_one_or_none()
    if document is None:
        raise APIError(404, "document_not_found", "Report not found.")
    try:
        current = ProcessingState(document.processing_state)
    except ValueError as exc:
        raise InvalidTransition("stored document processing state is invalid") from exc
    if expected_version is not None and document.processing_version != expected_version:
        raise InvalidTransition("document processing version changed")
    if target not in ALLOWED_TRANSITIONS[current]:
        raise InvalidTransition(f"transition {current.value} -> {target.value} is not allowed")
    if target is ProcessingState.COMPLETED:
        rows = await db.scalars(
            select(DocumentStageRun.stage).where(
                DocumentStageRun.document_id == document_id,
                DocumentStageRun.user_id == user_id,
                DocumentStageRun.generation == document.processing_generation,
                DocumentStageRun.status == StageStatus.SUCCEEDED.value,
            )
        )
        completed = {ProcessingStage(value) for value in rows.all()}
        missing = set(required_stages(vector_index_required=vector_index_required)) - completed
        if missing:
            raise InvalidTransition("mandatory processing stages have not succeeded")
    previous = current
    document.processing_state = target.value
    document.processing_version += 1
    document.processing_updated_at = datetime.now(timezone.utc)
    db.add(
        DocumentProcessingEvent(
            document_id=document.id,
            user_id=user_id,
            previous_state=previous.value,
            next_state=target.value,
            processing_stage=stage.value if stage else None,
            actor=actor[:120],
            reason_code=reason_code[:120],
            state_version=document.processing_version,
        )
    )
    return document


async def enqueue_processing(db: AsyncSession, document: MedicalDocument, *, actor: str = "api") -> DocumentProcessingJob:
    """Transition UPLOADED -> QUEUED and create durable work in the same transaction."""
    await transition_document(
        db,
        user_id=document.user_id,
        document_id=document.id,
        target=ProcessingState.QUEUED,
        actor=actor,
        reason_code="upload_validated_and_stored",
    )
    job = DocumentProcessingJob(
        user_id=document.user_id,
        document_id=document.id,
        job_type="process",
        status="pending",
        idempotency_key=f"process:{document.id}:{document.processing_generation}",
    )
    db.add(job)
    await db.flush()
    return job


async def enqueue_reprocessing(db: AsyncSession, *, user_id: UUID, document_id: UUID, actor: str) -> DocumentProcessingJob:
    document = await transition_document(
        db,
        user_id=user_id,
        document_id=document_id,
        target=ProcessingState.QUEUED,
        actor=actor,
        reason_code="authorized_reprocessing",
    )
    document.processing_generation += 1
    return await enqueue_existing_queued(db, document, actor)


async def enqueue_existing_queued(db: AsyncSession, document: MedicalDocument, actor: str) -> DocumentProcessingJob:
    job = DocumentProcessingJob(
        user_id=document.user_id,
        document_id=document.id,
        job_type="process",
        status="pending",
        idempotency_key=f"process:{document.id}:{document.processing_generation}",
    )
    db.add(job)
    await db.flush()
    return job


async def record_stage(
    db: AsyncSession,
    *,
    user_id: UUID,
    document_id: UUID,
    stage: ProcessingStage,
    status: StageStatus,
    generation: int = 0,
    reason_code: str | None = None,
) -> DocumentStageRun:
    """Idempotently upsert the per-document stage ledger using its natural key."""
    await set_tenant_context(db, user_id)
    result = await db.execute(
        select(DocumentStageRun)
        .where(DocumentStageRun.document_id == document_id, DocumentStageRun.user_id == user_id,
               DocumentStageRun.generation == generation, DocumentStageRun.stage == stage.value)
        .with_for_update()
    )
    run = result.scalar_one_or_none()
    now = datetime.now(timezone.utc)
    if run is None:
        run = DocumentStageRun(document_id=document_id, user_id=user_id, generation=generation,
            stage=stage.value, status=status.value, attempts=1)
        db.add(run)
    else:
        run.status = status.value
        run.attempts += 1
    if status is StageStatus.RUNNING:
        run.started_at = now
    if status in {StageStatus.SUCCEEDED, StageStatus.FAILED, StageStatus.SKIPPED}:
        run.finished_at = now
    run.reason_code = reason_code[:120] if reason_code else None
    return run


def retry_delay(attempt: int, *, base_seconds: int = 5, max_seconds: int = 3600) -> int:
    """Bounded exponential backoff, with attempt 1 receiving the base delay."""
    if attempt < 1:
        raise ValueError("attempt must be at least one")
    return min(max_seconds, base_seconds * (2 ** (attempt - 1)))


def retry_available_at(attempt: int, now: datetime | None = None) -> datetime:
    return (now or datetime.now(timezone.utc)) + timedelta(seconds=retry_delay(attempt))
