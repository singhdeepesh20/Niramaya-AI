"""Idempotent external cleanup shared by synchronous API deletion and worker retries."""
from uuid import UUID

import httpx
from starlette.concurrency import run_in_threadpool

from app.core.config import settings
from app.storage.s3 import S3Storage


class VectorCleanupError(Exception):
    """Safe category-only failure; exception text may contain service details."""


async def cleanup_document_objects(storage: S3Storage, *, object_key: str, user_id: UUID, document_id: UUID) -> None:
    await run_in_threadpool(storage.delete_object, object_key)
    if not settings.QDRANT_URL:
        return
    headers = {"Content-Type": "application/json"}
    if settings.QDRANT_API_KEY:
        headers["api-key"] = settings.QDRANT_API_KEY.get_secret_value()
    body = {"filter": {"must": [
        {"key": "user_id", "match": {"value": str(user_id)}},
        {"key": "document_id", "match": {"value": str(document_id)}},
    ]}}
    url = f"{settings.QDRANT_URL}/collections/{settings.QDRANT_COLLECTION}/points/delete?wait=true"
    try:
        async with httpx.AsyncClient(timeout=settings.LLM_TIMEOUT_SECONDS) as client:
            response = await client.post(url, headers=headers, json=body)
            response.raise_for_status()
    except httpx.HTTPError as exc:
        raise VectorCleanupError("vector_cleanup_unavailable") from exc
