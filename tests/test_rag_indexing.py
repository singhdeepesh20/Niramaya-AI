from types import SimpleNamespace
from uuid import UUID

import numpy as np
import pytest
import asyncio
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import settings
from app.health import chunking, embeddings
from app.health.vector_store import QdrantStore, VectorStoreError
from app.health.dtos import HealthQuestion
from app.health.repository import retrieve_authorized_chunks
from app.database import Base
from app.documents import models as _document_models  # noqa: F401 - register queue tables
from app.health.models import DocumentPage, MedicalChunk, MedicalDocument
from app.user.models import User


def test_chunking_empty_pages_and_page_provenance():
    doc_id = UUID("2fdc590d-d182-4f2e-8d35-495ae2e89f79")
    assert chunking.chunk_pages(doc_id, 1, [SimpleNamespace(extracted_text="", page_number=1)]) == []
    chunks = chunking.chunk_pages(doc_id, 1, [
        SimpleNamespace(extracted_text="Hemoglobin 12.4 g/dL", page_number=2),
        SimpleNamespace(extracted_text="Platelets 250 x10^9/L", page_number=3),
    ], max_chars=300, overlap=30)
    assert [chunk.page_number for chunk in chunks] == [2, 3]
    assert "12.4 g/dL" in chunks[0].content
    assert chunks[0].content_hash and len(chunks[0].content_hash) == 64


def test_chunking_ids_and_hashes_are_stable_and_overlap_preserves_context():
    doc_id = UUID("5efc5890-f176-4ea6-9f9e-9253df0f9d00")
    text = "HEMATOLOGY RESULTS\n" + ("Hemoglobin 12.4 g/dL. Reference 12-16 g/dL. " * 20)
    page = SimpleNamespace(extracted_text=text, page_number=1)
    first = chunking.chunk_pages(doc_id, 4, [page], max_chars=350, overlap=80)
    again = chunking.chunk_pages(doc_id, 4, [page], max_chars=350, overlap=80)
    assert len(first) > 1
    assert [item.id for item in first] == [item.id for item in again]
    assert [item.content_hash for item in first] == [item.content_hash for item in again]
    assert "HEMATOLOGY RESULTS" in first[0].content
    assert all(len(item.content) <= 350 for item in first)


def test_local_embedding_batch_dimensions_and_empty_input(monkeypatch):
    class FakeModel:
        def encode(self, texts, **kwargs):
            assert kwargs["normalize_embeddings"] is True
            return np.ones((len(texts), 384), dtype=np.float32)

    monkeypatch.setattr(embeddings, "_model", lambda: FakeModel())
    assert embeddings.embed_texts([]) == []
    vectors = embeddings.embed_texts(["one", "two"])
    assert len(vectors) == 2 and len(vectors[0]) == settings.EMBEDDING_DIMENSION


def test_qdrant_existing_dimension_is_verified_without_recreate(monkeypatch):
    calls = []

    class Response:
        status_code = 200
        content = b"{}"
        def json(self):
            return {"result": {"config": {"params": {"vectors": {"size": 128, "distance": "Cosine"}}}}}

    class Client:
        def __init__(self, **_): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *_): return None
        async def request(self, method, url, **kwargs):
            calls.append((method, url, kwargs))
            return Response()

    monkeypatch.setattr(settings, "QDRANT_URL", "http://localhost:6333")
    with pytest.raises(VectorStoreError, match="qdrant_dimension_mismatch"):
        import asyncio
        asyncio.run(QdrantStore(Client).ensure_collection())
    assert len(calls) == 1 and calls[0][0] == "GET"


def test_indexing_persists_stable_chunks_and_retries_are_idempotent(monkeypatch):
    async def scenario():
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        owner, doc_id = uuid4(), uuid4()
        async with sessions() as db:
            db.add(User(id=owner, username="rag-user", email="rag-user@example.com", hashed_password="unused"))
            db.add(MedicalDocument(id=doc_id, user_id=owner, name="Synthetic lab", original_filename="lab.pdf",
                document_type="blood_test", content_type="application/pdf", file_size=10,
                object_key="private/test.pdf", processing_state="completed", processing_generation=2))
            db.add(DocumentPage(document_id=doc_id, user_id=owner, extraction_generation=2,
                page_number=4, extracted_text="Hemoglobin 12.4 g/dL", extraction_method="test", character_count=20))
            await db.commit()

        class FakeStore:
            points = []
            async def ensure_collection(self): pass
            async def upsert(self, points): self.points.extend(points)
            async def delete_obsolete(self, user, document, current):
                self.deleted_scope = (user, document, current)

        store = FakeStore()
        monkeypatch.setattr(settings, "QDRANT_URL", "http://qdrant.test")
        monkeypatch.setattr(settings, "QDRANT_COLLECTION", "isolated-test")
        monkeypatch.setattr("app.health.indexing.QdrantStore", lambda: store)
        monkeypatch.setattr("app.health.indexing.embed_texts", lambda texts: [[0.01] * 384 for _ in texts])
        from app.health.indexing import index_document
        first = await index_document(sessions, owner, doc_id)
        ids_after_first = [point["id"] for point in store.points]
        second = await index_document(sessions, owner, doc_id)
        async with sessions() as db:
            rows = list((await db.scalars(select(MedicalChunk))).all())
            saved_doc = await db.get(MedicalDocument, doc_id)
        assert first["status"] == second["status"] == "completed"
        assert len(rows) == 1 and rows[0].page_number == 4 and "12.4 g/dL" in rows[0].content
        assert rows[0].content_hash and rows[0].extraction_generation == 2
        assert saved_doc.indexing_status == "completed" and saved_doc.indexed_chunk_count == 1
        assert ids_after_first[0] == store.points[-1]["id"]
        assert store.deleted_scope == (str(owner), str(doc_id), ids_after_first)
        await engine.dispose()

    asyncio.run(scenario())


@pytest.mark.parametrize("failure_stage", ["embedding", "qdrant"])
def test_vector_index_failure_keeps_chunks_available_for_keyword_search(monkeypatch, failure_stage):
    async def scenario():
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        owner, doc_id = uuid4(), uuid4()
        async with sessions() as db:
            db.add(User(id=owner, username="fallback-user", email="fallback-user@example.com", hashed_password="unused"))
            db.add(MedicalDocument(
                id=doc_id, user_id=owner, name="Synthetic lab", original_filename="synthetic.pdf",
                document_type="blood_test", content_type="application/pdf", file_size=10,
                object_key="private/synthetic.pdf", processing_state="completed", processing_generation=3,
            ))
            db.add(DocumentPage(
                document_id=doc_id, user_id=owner, extraction_generation=3, page_number=2,
                extracted_text="Hemoglobin 13.5 g/dL", extraction_method="synthetic_test", character_count=21,
            ))
            await db.commit()

        monkeypatch.setattr(settings, "QDRANT_URL", "http://qdrant.test")
        monkeypatch.setattr(settings, "QDRANT_COLLECTION", "isolated-test")
        if failure_stage == "embedding":
            def fail_embedding(_texts):
                raise embeddings.EmbeddingUnavailable("embedding_model_unavailable")
            monkeypatch.setattr("app.health.indexing.embed_texts", fail_embedding)
        else:
            monkeypatch.setattr("app.health.indexing.embed_texts", lambda texts: [[0.01] * 384 for _ in texts])

            class UnavailableStore:
                async def ensure_collection(self):
                    raise VectorStoreError("qdrant_unavailable")

            monkeypatch.setattr("app.health.indexing.QdrantStore", UnavailableStore)

        from app.health.indexing import index_document
        outcome = await index_document(sessions, owner, doc_id)
        async with sessions() as db:
            rows = list((await db.scalars(select(MedicalChunk).where(
                MedicalChunk.user_id == owner, MedicalChunk.document_id == doc_id,
            ))).all())
            document = await db.get(MedicalDocument, doc_id)
            found = await retrieve_authorized_chunks(
                db, owner, HealthQuestion(question="hemoglobin"), [], limit=5,
            )
        assert outcome["status"] == "failed"
        assert outcome["chunk_count"] == 0  # No vector points were indexed.
        assert len(rows) == 1 and "Hemoglobin 13.5 g/dL" in rows[0].content
        assert len(found) == 1 and found[0][0].user_id == owner
        assert document.indexing_status == "failed"
        assert document.indexing_error_code in {"embedding_model_unavailable", "qdrant_unavailable"}
        await engine.dispose()

    asyncio.run(scenario())
