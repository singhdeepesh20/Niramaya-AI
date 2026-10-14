from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pymupdf
import pytest

from app.core.config import settings
from app.documents.extraction import (
    PageResult, PDFProcessingError, _normalize_value, classify_document,
    extract_entities, extract_pdf,
)


def write_pdf(path: Path, pages: list[str]) -> None:
    document = pymupdf.open()
    for text in pages:
        page = document.new_page()
        if text:
            page.insert_textbox(pymupdf.Rect(50, 50, 550, 780), text)
    document.save(path)
    document.close()


def test_pdf_pages_preserve_boundaries_and_methods(tmp_path):
    path = tmp_path / "synthetic.pdf"
    write_pdf(path, ["CBC\nHemoglobin 13.5 g/dL", "WBC 7,200 cells/cumm", ""])
    result = extract_pdf(str(path), settings.model_copy(update={"OCR_ENABLED": False}))
    assert result.page_count == 3
    assert [page.page_number for page in result.pages] == [1, 2, 3]
    assert "Hemoglobin" in result.pages[0].extracted_text
    assert result.pages[0].extraction_method == "embedded_text"
    assert result.pages[2].warnings == ["ocr_disabled", "page_text_unavailable", "empty_page"]


def test_classification_registry_known_and_unknown_types():
    assert classify_document("COMPLETE BLOOD COUNT\nHemoglobin WBC RBC platelets").document_type == "cbc"
    assert classify_document("Lipid profile total cholesterol HDL LDL").document_type == "lipid_profile"
    assert classify_document("MRI brain\nFindings: signal\nImpression: normal").document_type == "mri"
    assert classify_document("random unrelated notes").document_type == "unknown"


def test_numeric_qualitative_provenance_and_supported_normalization():
    page = PageResult(2, "Hemoglobin: 135 g/L\nGlucose: Negative\nTSH 3.2 mIU/L", "embedded_text", 64)
    entities = extract_entities([page])
    hemoglobin = next(item for item in entities if item.name == "hemoglobin")
    glucose = next(item for item in entities if item.name == "urine_glucose")
    tsh = next(item for item in entities if item.name == "tsh")
    assert hemoglobin.value == "135" and hemoglobin.numeric_value == Decimal("135")
    assert hemoglobin.unit == "g/L" and hemoglobin.normalized_value == "13.5"
    assert hemoglobin.normalized_unit == "g/dL" and hemoglobin.page_number == 2
    assert "Hemoglobin: 135 g/L" in hemoglobin.source_excerpt
    assert glucose.qualitative_value == "negative"
    assert tsh.numeric_value == Decimal("3.2") and tsh.normalized_value is None
    assert _normalize_value("hemoglobin", Decimal("13.5"), "g/dL") == (None, None)


def test_imaging_sections_accept_plain_heading_lines():
    page = PageResult(1, "MRI BRAIN\nExamination\nMRI brain\nFindings\nSmall synthetic finding.\nImpression\nNo acute finding.", "embedded_text", 100)
    entities = extract_entities([page])
    sections = {item.name: item.value for item in entities if item.category == "report_section"}
    assert sections["examination"] == "MRI brain"
    assert sections["findings"] == "Small synthetic finding."
    assert sections["impression"] == "No acute finding."


def test_corrupt_and_encrypted_pdfs_fail_with_safe_codes(tmp_path):
    corrupt = tmp_path / "bad.pdf"
    corrupt.write_bytes(b"not a pdf")
    with pytest.raises(PDFProcessingError, match="invalid_pdf"):
        extract_pdf(str(corrupt), settings)
    encrypted = tmp_path / "encrypted.pdf"
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 72), "synthetic")
    doc.save(encrypted, encryption=pymupdf.PDF_ENCRYPT_AES_256, owner_pw="owner", user_pw="reader")
    doc.close()
    with pytest.raises(PDFProcessingError, match="encrypted_pdf"):
        extract_pdf(str(encrypted), settings)


def test_missing_tesseract_is_reported_without_losing_page(tmp_path, monkeypatch):
    import shutil
    monkeypatch.setattr(shutil, "which", lambda _name: None)
    path = tmp_path / "scanned.pdf"
    doc = pymupdf.open()
    doc.new_page()
    doc.save(path)
    doc.close()
    config = settings.model_copy(update={"OCR_ENABLED": True, "TESSERACT_CMD": ""})
    result = extract_pdf(str(path), config)
    assert result.page_count == 1
    assert result.pages[0].ocr_required is True
    assert result.pages[0].ocr_status == "unavailable"
    assert "ocr_executable_unavailable" in result.pages[0].warnings
    assert "page_text_unavailable" in result.pages[0].warnings
