from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import APIError
from app.core.rate_limit import LoginRateLimiter
from app.database import get_db
from app.health.assistant import HealthAssistant
from app.health.dtos import ChatHistoryItem, Citation, EvidenceItem, HealthAnswer, HealthQuestion
from app.health.repository import (
    get_authorized_document,
    list_chat_history,
    retrieve_authorized_chunks,
    save_chat_message,
)
from app.user.controller import get_current_user
from app.user.models import User

router = APIRouter(prefix="/api/v1/health", tags=["health assistant"])


def get_health_assistant() -> HealthAssistant:
    return HealthAssistant()


async def enforce_health_rate_limit(request: Request) -> None:
    client_ip = request.client.host if request.client else "unknown"
    await request.app.state.health_rate_limiter.check(client_ip)


@router.post("/ask", response_model=HealthAnswer, dependencies=[Depends(enforce_health_rate_limit)])
async def ask_health_question(
    payload: HealthQuestion,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    assistant: Annotated[HealthAssistant, Depends(get_health_assistant)],
) -> HealthAnswer:
    authenticated_user_id = user.id
    if payload.document_ids == []:
        answer = "No authorized records matched the document filter."
        await save_chat_message(db, authenticated_user_id, payload.question, answer, [], "insufficient_evidence")
        return HealthAnswer(answer=answer, citations=[], evidence=[], generation_status="insufficient_evidence")

    # Release the user lookup transaction before waiting on remote embedding/vector services.
    await db.rollback()
    vector_ids = await assistant.vector_chunk_ids(authenticated_user_id, payload)
    rows = await retrieve_authorized_chunks(
        db, authenticated_user_id, payload, vector_ids, settings.RAG_TOP_K
    )
    if not rows:
        answer = "I couldn't find this information in the medical records available to your account."
        await save_chat_message(db, authenticated_user_id, payload.question, answer, [], "insufficient_evidence")
        return HealthAnswer(answer=answer, citations=[], evidence=[], generation_status="insufficient_evidence")

    evidence_data: list[dict] = []
    citations: list[Citation] = []
    evidence: list[EvidenceItem] = []
    seen_citations: set[tuple[UUID, int | None]] = set()
    context_chars = 0
    for index, (chunk, document) in enumerate(rows, start=1):
        remaining = settings.RAG_MAX_CONTEXT_CHARS - context_chars
        if remaining <= 0:
            break
        excerpt_text = chunk.content[:min(4000, remaining)]
        context_chars += len(excerpt_text)
        citation = Citation(
            document_id=document.id,
            document_name=document.name,
            page_number=chunk.page_number,
        )
        evidence_data.append(
            {
                "evidence_id": f"E{index}",
                "document_id": str(document.id),
                "document_name": document.name,
                "page_number": chunk.page_number,
                "text": excerpt_text,
            }
        )
        evidence.append(EvidenceItem(**citation.model_dump(), excerpt=excerpt_text[:700]))
        citation_key = (document.id, chunk.page_number)
        if citation_key not in seen_citations:
            citations.append(citation)
            seen_citations.add(citation_key)

    generation_enabled = getattr(assistant, "generation_enabled", True)
    answer = await assistant.answer(payload.question, evidence_data)
    generation_status = "generated" if generation_enabled else "evidence_only"
    await save_chat_message(
        db,
        authenticated_user_id,
        payload.question,
        answer,
        [citation.model_dump(mode="json") for citation in citations],
        generation_status,
    )
    return HealthAnswer(answer=answer, citations=citations, evidence=evidence,
                        generation_status=generation_status)

@router.get("/history", response_model=list[ChatHistoryItem])
async def read_chat_history(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[ChatHistoryItem]:
    messages = await list_chat_history(db, user.id)
    return [ChatHistoryItem.model_validate(message) for message in messages]


@router.get("/documents/{document_id}")
async def read_document_metadata(
    document_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    document = await get_authorized_document(db, user.id, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return {
        "id": str(document.id),
        "name": document.name,
        "document_type": document.document_type,
        "document_date": document.document_date.isoformat() if document.document_date else None,
    }
