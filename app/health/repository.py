import re
from collections import defaultdict
from datetime import date, datetime, time, timezone
from uuid import UUID

from sqlalchemy import case, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.health.dtos import HealthQuestion
from app.health.models import HealthChatMessage, MedicalChunk, MedicalDocument

async def set_tenant_context(db: AsyncSession, user_id: UUID) -> None:
    """Set transaction-local PostgreSQL RLS identity; application filters remain mandatory too."""
    if db.bind is not None and db.bind.dialect.name == "postgresql":
        await db.execute(text("SELECT set_config('app.current_user_id', :user_id, true)"), {"user_id": str(user_id)})


def _date_epoch(value: date, end: bool = False) -> int:
    boundary = datetime.combine(value, time.max if end else time.min, tzinfo=timezone.utc)
    return int(boundary.timestamp())


def qdrant_filter(user_id: UUID, filters: HealthQuestion) -> dict:
    """Server-owned Qdrant conditions. Never accept these values from an LLM or client user_id."""
    must: list[dict] = [{"key": "user_id", "match": {"value": str(user_id)}}]
    if filters.document_types:
        must.append({"key": "document_type", "match": {"any": filters.document_types}})
    if filters.document_ids is not None:
        must.append({"key": "document_id", "match": {"any": [str(value) for value in filters.document_ids]}})
    if filters.date_from:
        must.append({"key": "document_date_epoch", "range": {"gte": _date_epoch(filters.date_from)}})
    if filters.date_to:
        must.append({"key": "document_date_epoch", "range": {"lte": _date_epoch(filters.date_to, end=True)}})
    return {"must": must}


def _apply_document_filters(statement, user_id: UUID, filters: HealthQuestion):
    statement = statement.where(
        MedicalChunk.user_id == user_id, MedicalDocument.user_id == user_id,
        MedicalChunk.extraction_generation == MedicalDocument.processing_generation,
        MedicalDocument.upload_status == "ready",
        MedicalDocument.processing_state != "deletion_pending",
    )
    if filters.document_types:
        statement = statement.where(func.lower(MedicalDocument.document_type).in_(filters.document_types))
    if filters.date_from:
        statement = statement.where(MedicalDocument.document_date >= filters.date_from)
    if filters.date_to:
        statement = statement.where(MedicalDocument.document_date <= filters.date_to)
    if filters.document_ids is not None:
        # An empty list deliberately means no matches.
        statement = statement.where(MedicalDocument.id.in_(filters.document_ids))
    return statement


async def retrieve_authorized_chunks(
    db: AsyncSession,
    user_id: UUID,
    filters: HealthQuestion,
    vector_chunk_ids: list[UUID],
    limit: int,
) -> list[tuple[MedicalChunk, MedicalDocument]]:
    """Hybrid retrieval with mandatory owner checks before any text is returned to the LLM."""
    await set_tenant_context(db, user_id)
    base = select(MedicalChunk, MedicalDocument).join(
        MedicalDocument, MedicalDocument.id == MedicalChunk.document_id
    )
    base = _apply_document_filters(base, user_id, filters)

    vector_rows: list[tuple[MedicalChunk, MedicalDocument]] = []
    if vector_chunk_ids:
        # A Qdrant result is only an untrusted identifier. Re-resolve every chunk from PostgreSQL
        # under the authenticated owner and requested metadata filters before using its content.
        vector_result = await db.execute(base.where(MedicalChunk.id.in_(vector_chunk_ids)))
        found = {chunk.id: (chunk, document) for chunk, document in vector_result.all()}
        vector_rows = [found[chunk_id] for chunk_id in vector_chunk_ids if chunk_id in found]

    stopwords = {"what", "was", "my", "the", "a", "an", "is", "are", "of", "for", "me", "in", "on", "latest", "most", "recent", "newest", "level", "value", "result", "show", "tell"}
    tokens = list(dict.fromkeys(token.lower() for token in re.findall(r"[\w]+", filters.question) if len(token) > 1 and token.lower() not in stopwords))
    keyword_rows: list[tuple[MedicalChunk, MedicalDocument]] = []
    if tokens:
        if db.bind is not None and db.bind.dialect.name == "postgresql":
            document_text = func.to_tsvector("simple", MedicalChunk.content)
            token_queries = [func.plainto_tsquery("simple", token) for token in tokens]
            predicates = [document_text.op("@@")(query) for query in token_queries]
            rank = sum(case((predicate, func.ts_rank_cd(document_text, query)), else_=0.0) for predicate, query in zip(predicates, token_queries, strict=True))
            order = [rank.desc()]
            if re.search(r"\b(latest|most recent|newest)\b", filters.question, re.IGNORECASE):
                order.insert(0, MedicalDocument.document_date.desc().nulls_last())
            keyword_statement = base.where(or_(*predicates)).order_by(*order).limit(limit)
        else:
            predicates = [MedicalChunk.content.ilike(f"%{token}%") for token in tokens]
            rank = sum(case((predicate, 1), else_=0) for predicate in predicates)
            order = [rank.desc()]
            if re.search(r"\b(latest|most recent|newest)\b", filters.question, re.IGNORECASE):
                order.insert(0, MedicalDocument.document_date.desc().nulls_last())
            keyword_statement = base.where(or_(*predicates)).order_by(*order).limit(limit)
        keyword_result = await db.execute(keyword_statement)
        keyword_rows = list(keyword_result.all())

    # Reciprocal rank fusion combines semantic and lexical candidates without trusting scores
    # from a remote vector service as an authorization signal.
    scores: dict[UUID, float] = defaultdict(float)
    records: dict[UUID, tuple[MedicalChunk, MedicalDocument]] = {}
    for ranked in (vector_rows, keyword_rows):
        for rank, row in enumerate(ranked, start=1):
            chunk, _document = row
            scores[chunk.id] += 1.0 / (60 + rank)
            records[chunk.id] = row
    ordered_ids = sorted(scores, key=scores.get, reverse=True)[:limit]
    return [records[chunk_id] for chunk_id in ordered_ids]


async def get_authorized_document(db: AsyncSession, user_id: UUID, document_id: UUID) -> MedicalDocument | None:
    await set_tenant_context(db, user_id)
    result = await db.execute(
        select(MedicalDocument).where(MedicalDocument.id == document_id, MedicalDocument.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def save_chat_message(
    db: AsyncSession, user_id: UUID, question: str, answer: str, citations: list[dict],
    generation_status: str = "generated",
) -> HealthChatMessage:
    await set_tenant_context(db, user_id)
    message = HealthChatMessage(user_id=user_id, question=question, answer=answer,
                                citations=citations, generation_status=generation_status)
    db.add(message)
    await db.commit()
    return message


async def list_chat_history(db: AsyncSession, user_id: UUID, limit: int = 50) -> list[HealthChatMessage]:
    await set_tenant_context(db, user_id)
    result = await db.execute(
        select(HealthChatMessage)
        .where(HealthChatMessage.user_id == user_id)
        .order_by(HealthChatMessage.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())
