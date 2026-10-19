"""User-scoped document chunk embedding and Qdrant indexing lifecycle."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import settings
from app.health.chunking import chunk_pages
from app.health.embeddings import EmbeddingUnavailable, embed_texts
from app.health.models import DocumentExtractedTable, DocumentPage, MedicalChunk, MedicalDocument, MedicalEntity
from app.health.repository import set_tenant_context
from app.health.vector_store import QdrantStore, VectorStoreError

logger = logging.getLogger("niramaya.rag.indexing")


async def index_document(sessions: async_sessionmaker[AsyncSession], user_id: UUID, document_id: UUID) -> dict:
    """Index one persisted extraction; PostgreSQL is committed before obsolete points are removed."""
    async with sessions() as db:
        await set_tenant_context(db, user_id)
        doc = (await db.scalars(select(MedicalDocument).where(
            MedicalDocument.id == document_id, MedicalDocument.user_id == user_id
        ).with_for_update())).one_or_none()
        if doc is None or doc.processing_state == "deletion_pending":
            return {"status": "cancelled", "chunk_count": 0}
        pages = list((await db.scalars(select(DocumentPage).where(
            DocumentPage.user_id == user_id, DocumentPage.document_id == document_id,
            DocumentPage.extraction_generation == doc.processing_generation,
        ).order_by(DocumentPage.page_number))).all())
        tables = list((await db.scalars(select(DocumentExtractedTable).where(
            DocumentExtractedTable.user_id == user_id, DocumentExtractedTable.document_id == document_id,
            DocumentExtractedTable.extraction_generation == doc.processing_generation,
        ).order_by(DocumentExtractedTable.page_number, DocumentExtractedTable.table_index))).all())
        entities = list((await db.scalars(select(MedicalEntity).where(
            MedicalEntity.user_id == user_id, MedicalEntity.document_id == document_id,
            MedicalEntity.extraction_generation == doc.processing_generation,
        ).order_by(MedicalEntity.page_number, MedicalEntity.name))).all())
        generation = doc.processing_generation
        document_type = doc.document_type
        document_date = doc.document_date
        doc.indexing_status = "indexing"
        doc.indexing_attempts += 1
        doc.indexing_error_code = None
        await db.commit()

    table_text: dict[int, list[str]] = {}
    for table in tables:
        headers = [str(value) for value in (table.headers or [])]
        rows = [[str(value) for value in row] for row in (table.rows or [])]
        lines = ["Extracted table: " + " | ".join(headers)]
        lines.extend(" | ".join(row) for row in rows)
        table_text.setdefault(table.page_number, []).append("\n".join(lines))
    entity_text: dict[int, list[str]] = {}
    for entity in entities:
        if entity.page_number is None:
            continue
        value = entity.value or entity.normalized_value or entity.qualitative_value
        label = entity.original_name or entity.name
        if not value:
            continue
        detail = f"Extracted finding: {label}: {value}"
        if entity.unit:
            detail += f" {entity.unit}"
        if entity.reference_range:
            detail += f" (reported reference range: {entity.reference_range})"
        if entity.source_excerpt:
            detail += f". Source text: {entity.source_excerpt}"
        entity_text.setdefault(entity.page_number, []).append(detail)
    source_pages = [SimpleNamespace(
        page_number=page.page_number,
        extracted_text="\n".join(filter(None, [page.extracted_text, *table_text.get(page.page_number, []),
                                                   *entity_text.get(page.page_number, [])])),
    ) for page in pages]
    chunks = chunk_pages(document_id, generation, source_pages,
                         max_chars=settings.CHUNK_SIZE_CHARS,
                         overlap=settings.CHUNK_OVERLAP_CHARS)
    if not chunks:
        store = QdrantStore() if settings.QDRANT_URL else None
        if store:
            try:
                await store.ensure_collection()
            except VectorStoreError as exc:
                return await _record_failure(sessions, user_id, document_id, exc.category)
        return await _persist_chunks(sessions, user_id, document_id, generation, chunks, store, [])
    if not settings.QDRANT_URL:
        return await _persist_chunks(sessions, user_id, document_id, generation, chunks, None, [])
    try:
        embeddings = await asyncio.to_thread(embed_texts, [chunk.content for chunk in chunks])
        if len(embeddings) != len(chunks) or any(len(vector) != settings.EMBEDDING_DIMENSION for vector in embeddings):
            raise EmbeddingUnavailable("embedding_dimension_mismatch")
        store = QdrantStore()
        await store.ensure_collection()
        points = []
        for chunk, vector in zip(chunks, embeddings, strict=True):
            points.append({"id": str(chunk.id), "vector": vector, "payload": {
                "chunk_id": str(chunk.id), "user_id": str(user_id), "document_id": str(document_id),
                "document_type": document_type,
                "document_date_epoch": int(datetime.combine(document_date, datetime.min.time(), tzinfo=timezone.utc).timestamp()) if document_date else None,
                "page_number": chunk.page_number, "section": chunk.section,
                "content_hash": chunk.content_hash, "extraction_generation": generation,
                "embedding_model": f"{settings.EMBEDDING_MODEL_NAME}@{settings.EMBEDDING_MODEL_REVISION}",
            }})
        await store.upsert(points)
        return await _persist_chunks(sessions, user_id, document_id, generation, chunks, store,
                                     [str(chunk.id) for chunk in chunks])
    except (EmbeddingUnavailable, VectorStoreError) as exc:
        code = exc.args[0] if exc.args else "indexing_failed"
        # Preserve PostgreSQL chunks so owner-scoped keyword retrieval remains available
        # while the model or vector service is repaired and indexing is retried.
        return await _persist_chunks(
            sessions, user_id, document_id, generation, chunks, None, [],
            indexing_status="failed", indexing_error_code=code,
        )
    except Exception as exc:
        logger.warning("document_indexing_failed document_id=%s error_type=%s", document_id, type(exc).__name__)
        return await _persist_chunks(
            sessions, user_id, document_id, generation, chunks, None, [],
            indexing_status="failed", indexing_error_code="indexing_failed",
        )


async def _persist_chunks(
    sessions, user_id, document_id, generation, chunks, store, new_ids,
    *, indexing_status: str | None = None, indexing_error_code: str | None = None,
):
    async with sessions() as db:
        await set_tenant_context(db, user_id)
        doc = (await db.scalars(select(MedicalDocument).where(
            MedicalDocument.id == document_id, MedicalDocument.user_id == user_id
        ).with_for_update())).one_or_none()
        if doc is None or doc.processing_state == "deletion_pending" or doc.processing_generation != generation:
            await db.rollback()
            if store:
                await store.delete_obsolete(str(user_id), str(document_id), [])
            return {"status": "cancelled", "chunk_count": 0}
        await db.execute(delete(MedicalChunk).where(
            MedicalChunk.user_id == user_id, MedicalChunk.document_id == document_id
        ))
        for chunk in chunks:
            db.add(MedicalChunk(id=chunk.id, user_id=user_id, document_id=document_id,
                page_number=chunk.page_number, section=chunk.section, chunk_index=chunk.index,
                content=chunk.content, content_hash=chunk.content_hash,
                extraction_generation=generation,
                embedding_model=f"{settings.EMBEDDING_MODEL_NAME}@{settings.EMBEDDING_MODEL_REVISION}" if store else None))
        status = indexing_status or ("completed" if store else "not_configured")
        doc.indexing_status = status
        doc.indexed_chunk_count = len(chunks) if store else 0
        model = f"{settings.EMBEDDING_MODEL_NAME}@{settings.EMBEDDING_MODEL_REVISION}"
        has_index_configuration = store is not None or indexing_status == "failed"
        doc.indexing_model = model if has_index_configuration else None
        doc.indexing_dimension = settings.EMBEDDING_DIMENSION if has_index_configuration else None
        doc.indexing_updated_at = datetime.now(timezone.utc)
        doc.indexing_error_code = indexing_error_code if indexing_status == "failed" else (None if store else "qdrant_not_configured")
        await db.commit()
    if store:
        await store.delete_obsolete(str(user_id), str(document_id), new_ids)
    logger.info("document_indexing_finished document_id=%s chunks=%s status=%s", document_id, len(chunks), status)
    return {"status": status, "chunk_count": len(chunks) if store else 0}


async def _record_failure(sessions, user_id, document_id, reason, status="failed"):
    async with sessions() as db:
        await set_tenant_context(db, user_id)
        doc = (await db.scalars(select(MedicalDocument).where(
            MedicalDocument.id == document_id, MedicalDocument.user_id == user_id
        ).with_for_update())).one_or_none()
        if doc is None:
            return {"status": "cancelled", "chunk_count": 0}
        doc.indexing_status = status
        doc.indexing_error_code = reason[:120]
        doc.indexing_updated_at = datetime.now(timezone.utc)
        doc.indexing_model = f"{settings.EMBEDDING_MODEL_NAME}@{settings.EMBEDDING_MODEL_REVISION}"
        doc.indexing_dimension = settings.EMBEDDING_DIMENSION
        await db.commit()
        count = await db.scalar(select(MedicalChunk.id).where(
            MedicalChunk.user_id == user_id, MedicalChunk.document_id == document_id
        ).limit(1000))
        # Existing rows remain available to lexical search; Qdrant is never treated as truth.
        return {"status": status, "chunk_count": 0 if count is None else doc.indexed_chunk_count}
