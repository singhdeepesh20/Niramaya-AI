"""Deterministic document pipeline orchestration for the database worker."""

from __future__ import annotations

import hashlib
from pathlib import Path
import tempfile
from typing import Protocol

from app.core.config import Settings
from app.documents.extraction import PipelineResult, PDFProcessingError, build_pipeline_result
from app.health.models import MedicalDocument


class PrivateObjectStorage(Protocol):
    def download_file(self, key: str, destination: str) -> None: ...


class DeterministicDocumentProcessor:
    """Read a private source PDF, extract it locally, and return persisted-ready data."""

    def __init__(self, storage: PrivateObjectStorage, config: Settings):
        self.storage = storage
        self.config = config

    def process_document(self, document: MedicalDocument) -> PipelineResult:
        if document.content_type not in {"application/pdf", "image/jpeg", "image/png"}:
            raise PDFProcessingError("unsupported_processing_media_type")
        with tempfile.TemporaryDirectory(prefix="niramaya-document-") as directory:
            source_path = Path(directory) / "source.upload"
            path = Path(directory) / "source.pdf"
            self.storage.download_file(document.object_key, str(source_path))
            if not source_path.is_file() or source_path.stat().st_size == 0:
                raise PDFProcessingError("source_document_empty")
            if source_path.stat().st_size > self.config.S3_MAX_UPLOAD_BYTES:
                raise PDFProcessingError("source_document_limit_exceeded")
            digest = hashlib.sha256()
            with source_path.open("rb") as source:
                for chunk in iter(lambda: source.read(1024 * 1024), b""):
                    digest.update(chunk)
            if document.content_type == "application/pdf":
                source_path.replace(path)
            else:
                self._image_to_pdf(source_path, path)
            return build_pipeline_result(str(path), self.config, digest.hexdigest())

    @staticmethod
    def _image_to_pdf(source: Path, destination: Path) -> None:
        """Wrap a bounded JPEG/PNG as one PDF page so the same local OCR runs."""
        try:
            from PIL import Image

            with Image.open(source) as image:
                if image.format not in {"JPEG", "PNG"}:
                    raise PDFProcessingError("unsupported_processing_media_type")
                if image.width * image.height > 80_000_000:
                    raise PDFProcessingError("image_pixel_limit_exceeded")
                image.convert("RGB").save(destination, format="PDF", resolution=150.0)
        except PDFProcessingError:
            raise
        except Exception as exc:
            raise PDFProcessingError("invalid_image") from exc
