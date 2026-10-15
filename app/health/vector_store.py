"""Qdrant REST operations with non-destructive collection compatibility checks."""
from __future__ import annotations

import httpx

from app.core.config import settings


class VectorStoreError(RuntimeError):
    def __init__(self, category: str):
        self.category = category
        super().__init__(category)


class QdrantStore:
    def __init__(self, client_factory=httpx.AsyncClient):
        self.client_factory = client_factory

    def _headers(self):
        headers = {"Content-Type": "application/json"}
        if settings.QDRANT_API_KEY:
            headers["api-key"] = settings.QDRANT_API_KEY.get_secret_value()
        return headers

    async def _request(self, method: str, path: str, **kwargs):
        if not settings.QDRANT_URL:
            raise VectorStoreError("qdrant_not_configured")
        try:
            async with self.client_factory(timeout=settings.LLM_TIMEOUT_SECONDS) as client:
                response = await client.request(method, f"{settings.QDRANT_URL}{path}",
                                                headers=self._headers(), **kwargs)
                if response.status_code >= 400:
                    if response.status_code == 404:
                        raise VectorStoreError("qdrant_collection_missing")
                    raise VectorStoreError("qdrant_request_failed")
                return response.json() if response.content else {}
        except VectorStoreError:
            raise
        except (httpx.HTTPError, ValueError, TypeError) as exc:
            raise VectorStoreError("qdrant_unavailable") from exc

    async def ensure_collection(self):
        path = f"/collections/{settings.QDRANT_COLLECTION}"
        try:
            info = await self._request("GET", path)
        except VectorStoreError as exc:
            if exc.category != "qdrant_collection_missing":
                raise
            await self._request("PUT", path, json={"vectors": {"size": settings.EMBEDDING_DIMENSION,
                                                                  "distance": "Cosine"}})
            return
        vectors = info.get("result", {}).get("config", {}).get("params", {}).get("vectors", {})
        if isinstance(vectors, dict) and "size" in vectors:
            size = vectors.get("size")
        elif isinstance(vectors, dict):
            config = vectors.get("", {}) or next(iter(vectors.values()), {})
            size = config.get("size") if isinstance(config, dict) else None
        else:
            size = None
        if size != settings.EMBEDDING_DIMENSION:
            raise VectorStoreError("qdrant_dimension_mismatch")

    async def upsert(self, points: list[dict]):
        if not points:
            return
        await self._request("PUT", f"/collections/{settings.QDRANT_COLLECTION}/points?wait=true",
                            json={"points": points})

    async def delete_obsolete(self, user_id: str, document_id: str, current_ids: list[str]):
        """Delete only obsolete points for this owner/document, after Postgres commit."""
        scoped_filter = {"must": [
            {"key": "user_id", "match": {"value": user_id}},
            {"key": "document_id", "match": {"value": document_id}},
        ]}
        if current_ids:
            scoped_filter["must_not"] = [{"has_id": current_ids}]
        await self._request("POST", f"/collections/{settings.QDRANT_COLLECTION}/points/delete?wait=true",
                            json={"filter": scoped_filter})

    async def query(self, vector: list[float], query_filter: dict, limit: int):
        payload = await self._request("POST", f"/collections/{settings.QDRANT_COLLECTION}/points/query",
            json={"query": vector, "filter": query_filter, "limit": limit,
                  "with_payload": ["chunk_id"], "with_vector": False})
        return payload.get("result", {}).get("points", [])
