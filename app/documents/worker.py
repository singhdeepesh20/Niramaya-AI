"""Queue-compatible worker entry points; extraction adapters are injected by deployment."""
import asyncio
import logging
import signal
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import settings
from app.database import AsyncSessionLocal, engine
from app.documents.cleanup import cleanup_document_objects
from app.documents.models import DocumentProcessingJob
from app.documents.extraction import PDFProcessingError
from app.documents.pipeline import DeterministicDocumentProcessor
from app.documents.processing import (
    ProcessingStage, ProcessingState, RetryableProcessingError,
    PermanentProcessingError, ReviewRequiredError, StageProcessor, StageStatus,
    record_stage,
    required_stages, retry_available_at, transition_document,
)
from app.health.models import DocumentExtractedTable, DocumentPage, MedicalDocument, MedicalEntity
from app.health.repository import set_tenant_context
from app.storage.s3 import S3Storage
from app.user import models as user_models  # noqa: F401 - register users table for worker metadata FKs

logger = logging.getLogger("niramaya.documents.worker")


async def process_one(
    sessions: async_sessionmaker[AsyncSession], processor: StageProcessor | None = None,
    *, worker_id: str = "document-worker", lease_seconds: int = 300,
    vector_index_required: bool | None = None, storage=None,
) -> bool:
    """Claim and execute one due process job. A job is acknowledged only after a DB outcome."""
    use_deterministic_pipeline = processor is None
    processor = processor or DeterministicDocumentProcessor(storage or S3Storage(), settings)
    if vector_index_required is None:
        vector_index_required = settings.HEALTH_VECTOR_INDEX_REQUIRED
    async with sessions() as db:
        now = datetime.now(timezone.utc)
        query = select(DocumentProcessingJob).where(
            DocumentProcessingJob.status == "pending",
            DocumentProcessingJob.available_at <= now,
        ).order_by(DocumentProcessingJob.created_at).limit(1).with_for_update(skip_locked=True)
        job = (await db.scalars(query)).first()
        if job is None:
            return False
        job.status = "running"
        job.worker_id = worker_id[:120]
        job.locked_until = now + timedelta(seconds=lease_seconds)
        job.attempts += 1
        user_id, document_id, job_id, job_type = job.user_id, job.document_id, job.id, job.job_type
        if job_type == "delete":
            await db.commit()
            return await _process_delete_job(sessions, job_id, user_id, document_id, worker_id)
        if job_type == "index":
            await db.commit()
            return await _process_index_job(sessions, job_id, user_id, document_id)
        try:
            await set_tenant_context(db, user_id)
            doc = (await db.scalars(select(MedicalDocument).where(
                MedicalDocument.id == document_id, MedicalDocument.user_id == user_id
            ).with_for_update())).one_or_none()
            if doc is None:
                job.status, job.last_reason_code = "failed", "document_missing"
                await db.commit()
                return True
            await transition_document(db, user_id=user_id, document_id=document_id,
                target=ProcessingState.PROCESSING, actor=worker_id, reason_code="worker_claimed_job")
            await db.commit()
        except Exception:
            await db.rollback()
            raise

    stages = [ProcessingStage.CLASSIFICATION, ProcessingStage.TEXT_EXTRACTION,
              ProcessingStage.TABLE_EXTRACTION, ProcessingStage.ENTITY_EXTRACTION,
              ProcessingStage.NORMALIZATION, ProcessingStage.PROVENANCE,
              ProcessingStage.REVIEW_EVALUATION]
    if vector_index_required:
        stages.append(ProcessingStage.VECTOR_INDEX)
    async with sessions() as db:
        await set_tenant_context(db, user_id)
        doc = (await db.scalars(select(MedicalDocument).where(
            MedicalDocument.id == document_id, MedicalDocument.user_id == user_id
        ))).one_or_none()
    if doc is None:
        return True
    if use_deterministic_pipeline:
        try:
            result = await asyncio.to_thread(processor.process_document, doc)
            await _persist_pipeline_result(sessions, job_id, user_id, document_id, worker_id, result,
                                           vector_index_required=vector_index_required)
            from app.health.indexing import index_document
            index_outcome = await index_document(sessions, user_id, document_id)
            if index_outcome["status"] == "failed":
                await _enqueue_index_retry(sessions, user_id, document_id)
        except PDFProcessingError as exc:
            await _record_pipeline_failure(sessions, job_id, user_id, document_id, worker_id, exc.reason_code)
        except Exception as exc:
            reason = getattr(exc, "category", "processing_stage_failed")
            if getattr(exc, "retryable", False) or type(exc).__name__ == "S3StorageError":
                await _retry_or_fail(sessions, job_id, user_id, document_id, worker_id, reason)
            else:
                logger.error("document_pipeline_failed document_id=%s job_id=%s error_type=%s",
                             document_id, job_id, type(exc).__name__)
                await _record_pipeline_failure(sessions, job_id, user_id, document_id, worker_id, reason)
        return True
    try:
        done: set[ProcessingStage] = set()
        for stage in stages:
            deps = {
                ProcessingStage.CLASSIFICATION: (),
                ProcessingStage.TEXT_EXTRACTION: (ProcessingStage.CLASSIFICATION,),
                ProcessingStage.TABLE_EXTRACTION: (ProcessingStage.TEXT_EXTRACTION,),
                ProcessingStage.ENTITY_EXTRACTION: (ProcessingStage.TEXT_EXTRACTION,),
                ProcessingStage.NORMALIZATION: (ProcessingStage.ENTITY_EXTRACTION,),
                ProcessingStage.PROVENANCE: (ProcessingStage.NORMALIZATION,),
                ProcessingStage.REVIEW_EVALUATION: (ProcessingStage.PROVENANCE,),
                ProcessingStage.VECTOR_INDEX: (ProcessingStage.PROVENANCE,),
            }[stage]
            if not all(dep in done for dep in deps):
                if stage is ProcessingStage.TABLE_EXTRACTION:
                    async with sessions() as db:
                        await set_tenant_context(db, user_id)
                        await record_stage(db, user_id=user_id, document_id=document_id,
                            stage=stage, status=StageStatus.SKIPPED, generation=doc.processing_generation,
                            reason_code="optional_stage_not_required")
                        await db.commit()
                    continue
                raise PermanentProcessingError("stage_dependency_not_satisfied")
            async with sessions() as db:
                await set_tenant_context(db, user_id)
                await record_stage(db, user_id=user_id, document_id=document_id, stage=stage,
                    status=StageStatus.RUNNING, generation=doc.processing_generation)
                await db.commit()
            outcome = await _run_stage_with_lease(
                sessions, processor, stage, doc, worker_id, job_id, lease_seconds,
                f"{document_id}:{doc.processing_generation}:{stage.value}",
            )
            async with sessions() as db:
                await set_tenant_context(db, user_id)
                await record_stage(db, user_id=user_id, document_id=document_id, stage=stage,
                    status=outcome, generation=doc.processing_generation,
                    reason_code=None if outcome is StageStatus.SUCCEEDED else "stage_skipped")
                await db.commit()
            if outcome is StageStatus.SUCCEEDED:
                done.add(stage)
            elif stage in required_stages(vector_index_required=vector_index_required):
                raise ReviewRequiredError("mandatory_stage_not_completed")
        async with sessions() as db:
            await set_tenant_context(db, user_id)
            await transition_document(db, user_id=user_id, document_id=document_id,
                target=ProcessingState.COMPLETED, actor=worker_id, reason_code="mandatory_stages_succeeded",
                vector_index_required=vector_index_required)
            job = await db.get(DocumentProcessingJob, job_id)
            job.status, job.locked_until = "succeeded", None
            await db.commit()
    except ReviewRequiredError as exc:
        await _finish_job(sessions, job_id, user_id, document_id, worker_id, ProcessingState.REVIEW_REQUIRED, exc.reason_code)
    except RetryableProcessingError as exc:
        await _retry_or_fail(sessions, job_id, user_id, document_id, worker_id, exc.reason_code)
    except Exception as exc:
        reason = getattr(exc, "reason_code", "processing_stage_failed")
        await _finish_job(sessions, job_id, user_id, document_id, worker_id, ProcessingState.FAILED, reason)
    return True


async def _persist_pipeline_result(sessions, job_id, user_id, document_id, worker_id, result,
                                   *, vector_index_required: bool) -> None:
    """Persist one extraction generation and its truthful stage outcomes atomically."""
    from app.documents.processing import record_stage

    async with sessions() as db:
        await set_tenant_context(db, user_id)
        document = (await db.scalars(select(MedicalDocument).where(
            MedicalDocument.id == document_id, MedicalDocument.user_id == user_id
        ).with_for_update())).one_or_none()
        job = await db.get(DocumentProcessingJob, job_id)
        if document is None or document.processing_state == ProcessingState.DELETION_PENDING.value:
            job.status, job.locked_until, job.last_reason_code = "cancelled", None, "document_deletion_requested"
            await db.commit()
            return
        generation = document.processing_generation
        for model in (MedicalEntity, DocumentPage, DocumentExtractedTable):
            await db.execute(delete(model).where(
                model.document_id == document_id,
                model.user_id == user_id,
                model.extraction_generation == generation,
            ))
        document.document_type = result.classification.document_type
        metadata = dict(document.metadata_json or {})
        metadata["processing"] = {
            "pipeline": "deterministic-medical-v1",
            "classification": {
                "type": result.classification.document_type,
                "rule_id": result.classification.rule_id,
                "matched_indicators": result.classification.matched_indicators,
                "quality_score": result.classification.quality_score,
                "warnings": result.classification.warnings,
            },
            "checksum_sha256": result.checksum_sha256,
            "page_count": result.pdf.page_count,
            "ocr_page_count": sum(page.ocr_status == "succeeded" for page in result.pdf.pages),
            "entity_count": len(result.entities),
            "table_count": len(result.pdf.tables),
            "duration_ms": result.duration_ms,
            "review_reasons": result.review_reasons,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }
        document.metadata_json = metadata
        for page in result.pdf.pages:
            db.add(DocumentPage(
                document_id=document_id, user_id=user_id, extraction_generation=generation,
                page_number=page.page_number, extracted_text=page.extracted_text,
                extraction_method=page.extraction_method, character_count=page.character_count,
                ocr_required=page.ocr_required, ocr_status=page.ocr_status, warnings=page.warnings,
            ))
        for table in result.pdf.tables:
            db.add(DocumentExtractedTable(
                document_id=document_id, user_id=user_id, extraction_generation=generation,
                page_number=table.page_number, table_index=table.table_index,
                headers=table.headers, rows=table.rows, extraction_method=table.extraction_method,
                warnings=table.warnings,
            ))
        for entity in result.entities:
            entity_warnings = list(entity.warnings)
            value = entity.value
            if value is not None and len(value) > 512:
                value = value[:512]
                entity_warnings.append("value_truncated_source_preserved_in_page_text")
            db.add(MedicalEntity(
                document_id=document_id, user_id=user_id, extraction_generation=generation,
                category=entity.category, name=entity.name, original_name=entity.original_name,
                value=value, numeric_value=entity.numeric_value, unit=entity.unit,
                normalized_value=entity.normalized_value, normalized_unit=entity.normalized_unit,
                reference_range=entity.reference_range, reported_abnormal=entity.reported_abnormal,
                qualitative_value=entity.qualitative_value, page_number=entity.page_number,
                source_excerpt=entity.source_excerpt, extraction_method=entity.extraction_method,
                rule_id=entity.rule_id, quality_score=entity.quality_score,
                warnings=entity_warnings,
                review_status="required" if entity.review_status == "required" or entity_warnings else "not_required",
                metadata_json={"extraction_generation": generation},
            ))
        outcomes = (
            (ProcessingStage.CLASSIFICATION, StageStatus.SUCCEEDED, None),
            (ProcessingStage.TEXT_EXTRACTION, StageStatus.SUCCEEDED, None),
            (ProcessingStage.TABLE_EXTRACTION,
             StageStatus.SUCCEEDED if result.pdf.tables else StageStatus.SKIPPED,
             None if result.pdf.tables else "no_detected_tables"),
            (ProcessingStage.ENTITY_EXTRACTION, StageStatus.SUCCEEDED, None),
            (ProcessingStage.NORMALIZATION, StageStatus.SUCCEEDED, None),
            (ProcessingStage.PROVENANCE, StageStatus.SUCCEEDED, None),
            (ProcessingStage.REVIEW_EVALUATION, StageStatus.SUCCEEDED,
             ",".join(result.review_reasons)[:120] or None),
        )
        for stage, stage_status, reason in outcomes:
            await record_stage(db, user_id=user_id, document_id=document_id, generation=generation,
                               stage=stage, status=stage_status, reason_code=reason)
        if vector_index_required:
            await record_stage(db, user_id=user_id, document_id=document_id, generation=generation,
                               stage=ProcessingStage.VECTOR_INDEX, status=StageStatus.SKIPPED,
                               reason_code="indexing_runs_as_an_independent_stage")
        # Extraction truth is independent of vector service availability. The RAG
        # index status is stored separately and is never used to falsify extraction.
        target = ProcessingState.REVIEW_REQUIRED if result.review_reasons else ProcessingState.COMPLETED
        reason = result.review_reasons[0] if result.review_reasons else "deterministic_extraction_complete"
        await transition_document(db, user_id=user_id, document_id=document_id, target=target,
                                  actor=worker_id, reason_code=reason)
        job.status, job.locked_until = "succeeded", None
        job.last_reason_code = reason if target is ProcessingState.REVIEW_REQUIRED else None
        await db.commit()
    logger.info("document_pipeline_completed document_id=%s job_id=%s pages=%s ocr_pages=%s entities=%s tables=%s duration_ms=%s state=%s",
                document_id, job_id, result.pdf.page_count,
                sum(page.ocr_status == "succeeded" for page in result.pdf.pages),
                len(result.entities), len(result.pdf.tables), result.duration_ms, target.value)


async def _record_pipeline_failure(sessions, job_id, user_id, document_id, worker_id, reason_code: str) -> None:
    async with sessions() as db:
        await set_tenant_context(db, user_id)
        document = (await db.scalars(select(MedicalDocument).where(
            MedicalDocument.id == document_id, MedicalDocument.user_id == user_id
        ).with_for_update())).one_or_none()
        job = await db.get(DocumentProcessingJob, job_id)
        if document is None or document.processing_state == ProcessingState.DELETION_PENDING.value:
            job.status, job.locked_until = "cancelled", None
        else:
            from app.documents.processing import record_stage
            await record_stage(db, user_id=user_id, document_id=document_id,
                               generation=document.processing_generation,
                               stage=ProcessingStage.TEXT_EXTRACTION, status=StageStatus.FAILED,
                               reason_code=reason_code[:120])
            metadata = dict(document.metadata_json or {})
            metadata["processing"] = {**dict(metadata.get("processing") or {}),
                                      "last_error_code": reason_code[:120]}
            document.metadata_json = metadata
            await transition_document(db, user_id=user_id, document_id=document_id,
                                      target=ProcessingState.FAILED, actor=worker_id,
                                      reason_code=reason_code[:120])
            job.status, job.last_reason_code, job.locked_until = "failed", reason_code[:120], None
        await db.commit()
    logger.warning("document_pipeline_failed document_id=%s job_id=%s error_code=%s",
                   document_id, job_id, reason_code[:120])


async def _process_delete_job(sessions, job_id: UUID, user_id: UUID, document_id: UUID, worker_id: str) -> bool:
    async with sessions() as db:
        await set_tenant_context(db, user_id)
        document = (await db.scalars(select(MedicalDocument).where(
            MedicalDocument.id == document_id, MedicalDocument.user_id == user_id,
            MedicalDocument.processing_state == ProcessingState.DELETION_PENDING.value,
        ))).one_or_none()
        if document is None:
            job = await db.get(DocumentProcessingJob, job_id)
            job.status, job.last_reason_code, job.locked_until = "cancelled", "document_missing_or_not_deleting", None
            await db.commit()
            return True
        object_key = document.object_key
    try:
        await cleanup_document_objects(S3Storage(), object_key=object_key, user_id=user_id, document_id=document_id)
    except Exception as exc:
        async with sessions() as db:
            job = await db.get(DocumentProcessingJob, job_id)
            if job.attempts < job.max_attempts:
                job.status, job.available_at = "pending", retry_available_at(job.attempts)
            else:
                job.status = "failed"
            job.last_reason_code = getattr(exc, "category", "vector_cleanup_unavailable" if type(exc).__name__ == "VectorCleanupError" else "storage_cleanup_failed")
            job.locked_until = None
            await db.commit()
        return True
    async with sessions() as db:
        await set_tenant_context(db, user_id)
        document = (await db.scalars(select(MedicalDocument).where(
            MedicalDocument.id == document_id, MedicalDocument.user_id == user_id,
            MedicalDocument.processing_state == ProcessingState.DELETION_PENDING.value,
        ).with_for_update())).one_or_none()
        job = await db.get(DocumentProcessingJob, job_id)
        if document is not None:
            await db.delete(document)  # Chunks and entities cascade with the owner/document FK.
        job.status, job.last_reason_code, job.locked_until = "succeeded", "external_cleanup_complete", None
        await db.commit()
    return True


async def _process_index_job(sessions, job_id: UUID, user_id: UUID, document_id: UUID) -> bool:
    """Retry only the index stage; extracted PostgreSQL content remains canonical."""
    from app.health.indexing import index_document
    outcome = await index_document(sessions, user_id, document_id)
    async with sessions() as db:
        await set_tenant_context(db, user_id)
        job = await db.get(DocumentProcessingJob, job_id)
        if job is None:
            return True
        if outcome["status"] == "failed" and job.attempts < job.max_attempts:
            job.status = "pending"
            job.available_at = retry_available_at(job.attempts)
        else:
            job.status = "succeeded" if outcome["status"] in {"completed", "not_configured"} else "failed"
        job.last_reason_code = None if job.status == "succeeded" else outcome["status"]
        job.locked_until = None
        await db.commit()
    return True


async def _enqueue_index_retry(sessions, user_id: UUID, document_id: UUID) -> None:
    """Add one bounded retry without changing extraction state or re-running OCR."""
    from uuid import uuid4
    async with sessions() as db:
        await set_tenant_context(db, user_id)
        pending = await db.scalar(select(DocumentProcessingJob.id).where(
            DocumentProcessingJob.document_id == document_id,
            DocumentProcessingJob.user_id == user_id,
            DocumentProcessingJob.job_type == "index",
            DocumentProcessingJob.status.in_(("pending", "running")),
        ).limit(1))
        if pending is None:
            db.add(DocumentProcessingJob(
                user_id=user_id, document_id=document_id, job_type="index", status="pending",
                idempotency_key=f"index:{document_id}:{uuid4()}",
            ))
            await db.commit()


async def _finish_job(sessions, job_id: UUID, user_id: UUID, document_id: UUID, worker_id: str,
                      state: ProcessingState, reason: str) -> None:
    async with sessions() as db:
        await set_tenant_context(db, user_id)
        current = (await db.scalars(select(MedicalDocument).where(
            MedicalDocument.id == document_id, MedicalDocument.user_id == user_id
        ).with_for_update())).one_or_none()
        job = await db.get(DocumentProcessingJob, job_id)
        if current is None or current.processing_state == ProcessingState.DELETION_PENDING.value:
            job.status, job.last_reason_code, job.locked_until = "cancelled", "document_deletion_requested", None
            await db.commit()
            return
        await transition_document(db, user_id=user_id, document_id=document_id, target=state,
            actor=worker_id, reason_code=reason)
        job.status, job.last_reason_code, job.locked_until = "succeeded" if state is ProcessingState.REVIEW_REQUIRED else "failed", reason, None
        await db.commit()


async def _run_stage_with_lease(sessions, processor, stage, document, worker_id, job_id, lease_seconds, key):
    """Renew the DB lease during long adapters so recovery cannot start a duplicate worker."""
    task = asyncio.create_task(processor.run_stage(stage, document, key))
    interval = max(1.0, lease_seconds / 3)
    try:
        while True:
            try:
                return await asyncio.wait_for(asyncio.shield(task), timeout=interval)
            except TimeoutError:
                async with sessions() as db:
                    result = await db.execute(update(DocumentProcessingJob).where(
                        DocumentProcessingJob.id == job_id,
                        DocumentProcessingJob.status == "running",
                        DocumentProcessingJob.worker_id == worker_id,
                    ).values(locked_until=datetime.now(timezone.utc) + timedelta(seconds=lease_seconds)))
                    await db.commit()
                if result.rowcount != 1:
                    task.cancel()
                    raise RetryableProcessingError("worker_lease_lost")
    finally:
        if not task.done():
            task.cancel()


async def _retry_or_fail(sessions, job_id: UUID, user_id: UUID, document_id: UUID,
                         worker_id: str, reason: str) -> None:
    async with sessions() as db:
        await set_tenant_context(db, user_id)
        job = await db.get(DocumentProcessingJob, job_id)
        current = (await db.scalars(select(MedicalDocument).where(
            MedicalDocument.id == document_id, MedicalDocument.user_id == user_id
        ).with_for_update())).one_or_none()
        if current is None or current.processing_state == ProcessingState.DELETION_PENDING.value:
            job.status, job.last_reason_code, job.locked_until = "cancelled", "document_deletion_requested", None
            await db.commit()
            return
        if job.attempts < job.max_attempts:
            await transition_document(db, user_id=user_id, document_id=document_id,
                target=ProcessingState.QUEUED, actor=worker_id, reason_code="retryable_processing_error")
            job.status, job.available_at = "pending", retry_available_at(job.attempts)
        else:
            await transition_document(db, user_id=user_id, document_id=document_id,
                target=ProcessingState.FAILED, actor=worker_id, reason_code="retry_limit_exhausted")
            job.status = "failed"
        job.last_reason_code, job.locked_until = reason, None
        await db.commit()


async def recover_stale_jobs(sessions: async_sessionmaker[AsyncSession], *, worker_id: str = "recovery") -> int:
    """Requeue expired worker leases; failed leases stop at the bounded attempt limit."""
    recovered = 0
    async with sessions() as db:
        now = datetime.now(timezone.utc)
        jobs = list((await db.scalars(select(DocumentProcessingJob).where(
            DocumentProcessingJob.status == "running", DocumentProcessingJob.locked_until < now
        ).with_for_update(skip_locked=True))).all())
        for job in jobs:
            await set_tenant_context(db, job.user_id)
            document = (await db.scalars(select(MedicalDocument).where(
                MedicalDocument.id == job.document_id, MedicalDocument.user_id == job.user_id
            ).with_for_update())).one_or_none()
            if document is None or document.processing_state == ProcessingState.DELETION_PENDING.value:
                job.status, job.locked_until = "cancelled", None
                job.last_reason_code = "document_deletion_requested"
                recovered += 1
                continue
            if job.job_type == "index":
                job.status = "pending" if job.attempts < job.max_attempts else "failed"
                job.available_at, job.locked_until = now, None
                job.last_reason_code = "stale_index_lease_recovered"
                recovered += 1
                continue
            target = ProcessingState.QUEUED if job.attempts < job.max_attempts else ProcessingState.FAILED
            await transition_document(db, user_id=job.user_id, document_id=job.document_id,
                target=target, actor=worker_id, reason_code="stale_worker_lease_recovered")
            job.status = "pending" if target is ProcessingState.QUEUED else "failed"
            job.available_at, job.locked_until = now, None
            job.last_reason_code = "stale_worker_lease_recovered"
            recovered += 1
        await db.commit()
    return recovered


async def run_worker(
    *, worker_id: str = "document-worker", poll_seconds: float = 2.0,
    stop_event: asyncio.Event | None = None,
) -> None:
    """Minimal standalone polling worker; deployments inject real adapters in their runner."""
    stop_event = stop_event or asyncio.Event()
    last_recovery = 0.0
    while not stop_event.is_set():
        try:
            if asyncio.get_running_loop().time() - last_recovery >= 30:
                await recover_stale_jobs(AsyncSessionLocal, worker_id=f"{worker_id}-recovery")
                last_recovery = asyncio.get_running_loop().time()
            worked = await process_one(AsyncSessionLocal, worker_id=worker_id)
            if not worked:
                try:
                    await asyncio.wait_for(stop_event.wait(), timeout=poll_seconds)
                except TimeoutError:
                    pass
        except asyncio.CancelledError:
            raise
        except Exception:
            # Do not log exception text; it may contain SQL or provider data.
            import logging
            import sys
            error = sys.exc_info()[1]
            logging.getLogger("niramaya.documents.worker").error(
                "document_worker_iteration_failed error_type=%s", type(error).__name__
            )
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=poll_seconds)
            except TimeoutError:
                pass


async def _run_standalone_worker() -> None:
    """Convert container stop signals to a clean loop exit and dispose DB resources."""
    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()
    loop.add_signal_handler(signal.SIGTERM, stop_event.set)
    loop.add_signal_handler(signal.SIGINT, stop_event.set)
    try:
        await run_worker(stop_event=stop_event)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(_run_standalone_worker())
