from __future__ import annotations

from io import BytesIO
from types import SimpleNamespace

from PIL import Image

import app.documents.extraction as extraction
from app.core.config import settings
from app.documents.pipeline import DeterministicDocumentProcessor


class ImageStorage:
    def __init__(self, payload: bytes):
        self.payload = payload

    def download_file(self, _key: str, destination: str) -> None:
        with open(destination, "wb") as target:
            target.write(self.payload)


def test_png_uses_same_local_ocr_and_rule_pipeline(monkeypatch):
    image = Image.new("RGB", (600, 300), "white")
    payload_io = BytesIO()
    image.save(payload_io, format="PNG")
    image.close()
    monkeypatch.setattr(extraction, "_run_ocr", lambda _page, _config: (
        "COMPLETE BLOOD COUNT\nHemoglobin 13.5 g/dL\nWBC 7,200 cells/cumm", None
    ))
    document = SimpleNamespace(content_type="image/png", object_key="opaque-server-key")
    result = DeterministicDocumentProcessor(
        ImageStorage(payload_io.getvalue()), settings.model_copy(update={"OCR_ENABLED": True})
    ).process_document(document)
    assert result.pdf.page_count == 1
    assert result.pdf.pages[0].extraction_method == "tesseract_ocr"
    assert result.pdf.pages[0].ocr_status == "succeeded"
    assert {entity.name for entity in result.entities} >= {"hemoglobin", "wbc_count"}
    assert len(result.checksum_sha256) == 64


def test_image_ocr_unavailable_requests_review_instead_of_failing(monkeypatch):
    image = Image.new("RGB", (400, 200), "white")
    payload_io = BytesIO()
    image.save(payload_io, format="PNG")
    image.close()
    monkeypatch.setattr(extraction, "_run_ocr", lambda _page, _config: (None, "ocr_executable_unavailable"))
    result = DeterministicDocumentProcessor(
        ImageStorage(payload_io.getvalue()), settings.model_copy(update={"OCR_ENABLED": True})
    ).process_document(SimpleNamespace(content_type="image/png", object_key="opaque-server-key"))
    assert "scanned_page_not_ocr_processed" in result.review_reasons
    assert "page_text_unavailable" in result.pdf.pages[0].warnings
