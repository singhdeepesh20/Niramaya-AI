"""Lazy local CPU/GPU embedding provider, independent of answer generation."""
from __future__ import annotations

from functools import lru_cache

import numpy as np

from app.core.config import settings


class EmbeddingUnavailable(RuntimeError):
    pass


@lru_cache(maxsize=1)
def _model():
    try:
        from sentence_transformers import SentenceTransformer
        name = settings.EMBEDDING_MODEL_PATH or settings.EMBEDDING_MODEL_NAME
        return SentenceTransformer(name, revision=settings.EMBEDDING_MODEL_REVISION,
                                  device=settings.EMBEDDING_DEVICE,
                                  local_files_only=not settings.EMBEDDING_ALLOW_DOWNLOAD)
    except Exception as exc:
        raise EmbeddingUnavailable("embedding_model_unavailable") from exc


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    try:
        vectors = _model().encode(texts, batch_size=settings.EMBEDDING_BATCH_SIZE,
                                  normalize_embeddings=True, convert_to_numpy=True,
                                  show_progress_bar=False)
        matrix = np.asarray(vectors, dtype=np.float32)
        if matrix.ndim != 2 or matrix.shape != (len(texts), settings.EMBEDDING_DIMENSION):
            raise EmbeddingUnavailable("embedding_dimension_mismatch")
        if not np.isfinite(matrix).all():
            raise EmbeddingUnavailable("invalid_embedding_values")
        return matrix.tolist()
    except EmbeddingUnavailable:
        raise
    except Exception as exc:
        raise EmbeddingUnavailable("embedding_generation_failed") from exc
