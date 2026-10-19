"""Offline, deterministic PDF extraction and medical result parsing.

Nothing in this module calls a hosted model or a generative model. Rule scores
are parsing-quality indicators only; they are not probabilities or diagnoses.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from io import BytesIO
import re
import shutil
import time
from typing import Any

import pymupdf as fitz

from app.core.config import Settings


RULE_VERSION = "deterministic-medical-v1"
_NUMBER = r"[+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?"
_QUALITATIVE = r"negative|positive|trace|nil|none|normal|abnormal|present|absent|reactive|non-reactive"
_RANGE = re.compile(rf"(?:ref(?:erence)?(?:\s+range)?\s*[:=]?\s*)?([<>≤≥]?\s*{_NUMBER}\s*(?:-|–|—|\bto\b)\s*[<>≤≥]?\s*{_NUMBER})", re.I)
_FLAG = re.compile(r"(?<![/A-Za-z0-9])(high|low|abnormal|H|L|A)(?![A-Za-z0-9])", re.I)


class PDFProcessingError(Exception):
    def __init__(self, reason_code: str, *, retryable: bool = False):
        self.reason_code = reason_code
        self.retryable = retryable
        super().__init__(reason_code)


@dataclass
class PageResult:
    page_number: int
    extracted_text: str
    extraction_method: str
    character_count: int
    ocr_required: bool = False
    ocr_status: str = "not_required"
    warnings: list[str] = field(default_factory=list)


@dataclass
class TableResult:
    page_number: int
    table_index: int
    headers: list[str]
    rows: list[list[str]]
    extraction_method: str = "pymupdf"
    warnings: list[str] = field(default_factory=list)


@dataclass
class PDFResult:
    pages: list[PageResult]
    tables: list[TableResult]
    duration_ms: int
    page_count: int
    warnings: list[str] = field(default_factory=list)


@dataclass
class Classification:
    document_type: str
    rule_id: str
    matched_indicators: list[str]
    quality_score: float | None
    warnings: list[str] = field(default_factory=list)


@dataclass
class EntityResult:
    category: str
    name: str
    original_name: str
    value: str | None
    numeric_value: Decimal | None
    unit: str | None
    normalized_value: str | None
    normalized_unit: str | None
    reference_range: str | None
    reported_abnormal: bool | None
    qualitative_value: str | None
    page_number: int | None
    source_excerpt: str
    extraction_method: str
    rule_id: str
    quality_score: Decimal
    warnings: list[str] = field(default_factory=list)
    review_status: str = "not_required"


@dataclass
class PipelineResult:
    pdf: PDFResult
    classification: Classification
    entities: list[EntityResult]
    review_reasons: list[str]
    duration_ms: int
    checksum_sha256: str


# Exact aliases are intentionally explicit; unmatched labels are not guessed.
TEST_ALIASES: dict[str, tuple[str, ...]] = {
    "hemoglobin": ("hemoglobin", "haemoglobin", "hb", "hgb"),
    "wbc_count": ("total wbc count", "wbc count", "white blood cell count", "total leukocyte count", "tlc", "wbc"),
    "rbc_count": ("rbc count", "red blood cell count", "erythrocyte count", "rbc"),
    "hematocrit": ("hematocrit", "haematocrit", "packed cell volume", "pcv", "hct"),
    "mcv": ("mean corpuscular volume", "mcv"),
    "mch": ("mean corpuscular hemoglobin", "mean corpuscular haemoglobin", "mch"),
    "mchc": ("mean corpuscular hemoglobin concentration", "mean corpuscular haemoglobin concentration", "mchc"),
    "rdw": ("rdw-cv", "rdw", "red cell distribution width"),
    "platelet_count": ("platelet count", "platelets", "thrombocyte count"),
    "neutrophils": ("neutrophils", "neutrophil"),
    "lymphocytes": ("lymphocytes", "lymphocyte"),
    "monocytes": ("monocytes", "monocyte"),
    "eosinophils": ("eosinophils", "eosinophil"),
    "basophils": ("basophils", "basophil"),
    "total_cholesterol": ("total cholesterol", "cholesterol total", "cholesterol"),
    "hdl_cholesterol": ("hdl cholesterol", "hdl-c", "hdl"),
    "ldl_cholesterol": ("ldl cholesterol", "ldl-c", "ldl"),
    "triglycerides": ("triglycerides", "triglyceride", "tg"),
    "vldl_cholesterol": ("vldl cholesterol", "vldl"),
    "alt": ("alanine aminotransferase", "sgpt", "alt"),
    "ast": ("aspartate aminotransferase", "sgot", "ast"),
    "alp": ("alkaline phosphatase", "alp"),
    "total_bilirubin": ("total bilirubin", "bilirubin total"),
    "direct_bilirubin": ("direct bilirubin",),
    "albumin": ("albumin",),
    "total_protein": ("total protein",),
    "creatinine": ("serum creatinine", "creatinine"),
    "urea": ("blood urea nitrogen", "bun", "serum urea", "urea"),
    "uric_acid": ("uric acid",),
    "egfr": ("estimated glomerular filtration rate", "egfr", "e-gfr"),
    "fasting_glucose": ("fasting blood glucose", "fasting glucose", "fbs", "fasting plasma glucose"),
    "random_glucose": ("random blood glucose", "random glucose", "rbs"),
    "postprandial_glucose": ("postprandial glucose", "pp blood glucose", "ppbs"),
    "hba1c": ("glycated hemoglobin", "glycated haemoglobin", "hemoglobin a1c", "haemoglobin a1c", "hba1c"),
    "tsh": ("thyroid stimulating hormone", "tsh"),
    "free_t3": ("free t3", "ft3"),
    "free_t4": ("free t4", "ft4"),
    "t3": ("total t3", "t3"),
    "t4": ("total t4", "t4"),
    "urine_ph": ("urine ph", "ph"),
    "specific_gravity": ("specific gravity",),
    "urine_protein": ("urine protein", "protein"),
    "urine_glucose": ("urine glucose", "glucose"),
    "urine_ketones": ("urine ketones", "ketones", "ketone bodies"),
    "urine_blood": ("urine blood", "occult blood"),
    "urine_rbc": ("urine rbc", "rbc/hpf", "red cells"),
    "urine_wbc": ("urine wbc", "pus cells", "wbc/hpf"),
    "epithelial_cells": ("epithelial cells",),
}

_META_ALIASES: dict[str, tuple[str, ...]] = {
    "patient_name": ("patient name", "name of patient"),
    "patient_id": ("patient id", "patient no", "medical record number", "mrn"),
    "age": ("age",),
    "sex": ("sex", "gender"),
    "report_date": ("report date", "date of report"),
    "collection_date": ("collection date", "date of collection", "sample collection date"),
    "referring_doctor": ("referring doctor", "referred by", "referring physician"),
    "report_id": ("report id", "accession number", "lab number"),
    "laboratory": ("laboratory", "lab name", "diagnostic centre", "diagnostic center"),
}

_ALIASES_SORTED = sorted(
    ((alias, canonical) for canonical, aliases in TEST_ALIASES.items() for alias in aliases),
    key=lambda pair: len(pair[0]), reverse=True,
)


def _decimal(text: str) -> Decimal | None:
    try:
        value = Decimal(text.replace(",", "").strip())
        return value if value.is_finite() else None
    except (InvalidOperation, AttributeError):
        return None


def _normalize_value(name: str, value: Decimal | None, unit: str | None) -> tuple[str | None, str | None]:
    if value is None or not unit:
        return None, None
    normalized_unit = re.sub(r"\s+", "", unit).casefold()
    conversion: tuple[Decimal, str] | None = None
    if name == "hemoglobin" and normalized_unit == "g/l":
        conversion = (Decimal("0.1"), "g/dL")
    elif name in {"fasting_glucose", "random_glucose", "postprandial_glucose"} and normalized_unit == "mmol/l":
        conversion = (Decimal("18.0182"), "mg/dL")
    elif name in {"total_cholesterol", "hdl_cholesterol", "ldl_cholesterol", "vldl_cholesterol"} and normalized_unit == "mmol/l":
        conversion = (Decimal("38.67"), "mg/dL")
    elif name == "triglycerides" and normalized_unit == "mmol/l":
        conversion = (Decimal("88.57"), "mg/dL")
    if conversion is None:
        return None, None
    result = (value * conversion[0]).quantize(Decimal("0.001")).normalize()
    return format(result, "f"), conversion[1]


def _extract_lab_line(line: str, page_number: int) -> EntityResult | None:
    stripped = line.strip().replace("\t", " | ")
    if not stripped or len(stripped) > 1000:
        return None
    for alias, canonical in _ALIASES_SORTED:
        label_re = re.compile(rf"^\s*{re.escape(alias)}\s*(?::|=|\||\s)\s*(.+?)\s*$", re.I)
        match = label_re.match(stripped)
        if not match:
            continue
        tail = match.group(1).strip().strip("| ")
        result_match = re.match(rf"^({_NUMBER}|{_QUALITATIVE})(?:\b|$)", tail, re.I)
        if not result_match:
            continue
        value_text = result_match.group(1).strip()
        number = _decimal(value_text) if re.match(rf"^{_NUMBER}$", value_text) else None
        qualitative = value_text.casefold() if number is None else None
        remainder = tail[result_match.end():].strip(" |,;")
        range_match = _RANGE.search(remainder)
        reference = range_match.group(1).strip() if range_match else None
        abnormal_match = _FLAG.search(remainder)
        flag = abnormal_match.group(1).casefold() if abnormal_match else None
        if flag in {"high", "h", "abnormal"}:
            abnormal = True
        elif flag in {"low", "l"}:
            abnormal = True
        else:
            abnormal = None
        unit_text = remainder
        if range_match:
            unit_text = unit_text[:range_match.start()] + " " + unit_text[range_match.end():]
        if abnormal_match:
            unit_text = unit_text.replace(abnormal_match.group(0), " ")
        unit_text = re.sub(r"[()\[\]]|\b(ref(?:erence)?(?:\s+range)?)\b|[:=]", " ", unit_text, flags=re.I)
        unit_text = re.sub(r"\s+", " ", unit_text).strip(" |,;")
        unit = unit_text[:80] or None
        normalized, normalized_unit = _normalize_value(canonical, number, unit)
        warnings: list[str] = []
        if number is None and qualitative is None:
            continue
        if number is not None and not unit:
            warnings.append("unit_not_reported")
        score = Decimal("0.50") + (Decimal("0.20") if number is not None or qualitative else Decimal("0"))
        score += Decimal("0.15") if unit else Decimal("0")
        score += Decimal("0.15")  # exact alias and source-line provenance are required by this parser
        if warnings:
            score -= Decimal("0.10")
        return EntityResult(
            category="laboratory_result", name=canonical, original_name=alias,
            value=value_text, numeric_value=number, unit=unit, normalized_value=normalized,
            normalized_unit=normalized_unit, reference_range=reference, reported_abnormal=abnormal,
            qualitative_value=qualitative, page_number=page_number,
            source_excerpt=stripped[:600], extraction_method="rule_based", rule_id=RULE_VERSION,
            quality_score=max(Decimal("0"), min(Decimal("1"), score)).quantize(Decimal("0.001")),
            warnings=warnings,
        )
    return None


def _extract_explicit_metadata(line: str, page_number: int) -> EntityResult | None:
    for canonical, aliases in _META_ALIASES.items():
        for alias in sorted(aliases, key=len, reverse=True):
            match = re.match(rf"^\s*{re.escape(alias)}\s*[:=]\s*(\S.*)$", line.strip(), re.I)
            if match:
                value = match.group(1).strip()[:255]
                return EntityResult(
                    category="report_metadata", name=canonical, original_name=alias, value=value,
                    numeric_value=None, unit=None, normalized_value=None, normalized_unit=None,
                    reference_range=None, reported_abnormal=None, qualitative_value=None,
                    page_number=page_number, source_excerpt=line.strip()[:600],
                    extraction_method="rule_based", rule_id=f"{RULE_VERSION}:metadata",
                    quality_score=Decimal("0.800"),
                )
    return None


def classify_document(text: str) -> Classification:
    lower = text.casefold()
    rule_checks: tuple[tuple[str, tuple[str, ...], int], ...] = (
        ("cbc", ("complete blood count", "hemogram", "hemoglobin", "wbc", "rbc", "platelet"), 3),
        ("lipid_profile", ("lipid profile", "total cholesterol", "hdl", "ldl", "triglycerides"), 2),
        ("liver_function", ("liver function", "sgpt", "sgot", "alt", "ast", "bilirubin"), 2),
        ("kidney_function", ("renal function", "kidney function", "creatinine", "urea", "egfr"), 2),
        ("thyroid_function", ("thyroid profile", "tsh", "free t3", "free t4"), 1),
        ("glucose_hba1c", ("hba1c", "glycated hemoglobin", "fasting glucose", "blood glucose"), 1),
        ("urinalysis", ("urinalysis", "urine routine", "specific gravity", "pus cells"), 1),
        ("mri", ("mri", "magnetic resonance", "findings", "impression"), 2),
        ("ct_scan", ("ct scan", "computed tomography", "ct of"), 1),
        ("x_ray", ("x-ray", "x ray", "radiograph", "radiography"), 1),
        ("ultrasound", ("ultrasound", "sonography", "sonogram"), 1),
        ("ecg", ("electrocardiogram", "ecg", "ekg"), 1),
        ("prescription", ("prescription", "medication", "dosage", "frequency"), 2),
        ("discharge_summary", ("discharge summary", "date of discharge", "discharge diagnosis"), 1),
    )
    matches = []
    for rule_id, indicators, minimum in rule_checks:
        matched = [indicator for indicator in indicators if re.search(rf"\b{re.escape(indicator)}\b", lower)]
        if len(matched) >= minimum:
            matches.append((rule_id, matched, len(matched) / len(indicators)))
    if not matches:
        lab_signals = sum(bool(re.search(rf"\b{re.escape(term)}\b", lower)) for term in ("hemoglobin", "glucose", "creatinine", "cholesterol", "tsh"))
        if lab_signals:
            return Classification("general_lab", "classify.general_lab.v1", ["known_lab_test"], 0.4, ["classification_is_broad"])
        return Classification("unknown", "classify.unknown.v1", [], None, ["classification_unknown"])
    matches.sort(key=lambda item: (-item[2], item[0]))
    best = matches[0]
    if len(matches) > 1 and matches[1][2] == best[2]:
        return Classification("unknown", "classify.ambiguous.v1", sorted(set(best[1] + matches[1][1])), None, ["classification_ambiguous"])
    return Classification(best[0], f"classify.{best[0]}.v1", best[1], round(best[2], 3), [])


def extract_entities(pages: list[PageResult]) -> list[EntityResult]:
    results: list[EntityResult] = []
    for page in pages:
        lines = page.extracted_text.splitlines()
        for line in lines:
            metadata = _extract_explicit_metadata(line, page.page_number)
            if metadata:
                results.append(metadata)
            entity = _extract_lab_line(line, page.page_number)
            if entity:
                results.append(entity)
        section_names = {
            "examination": "examination", "modality": "modality", "clinical indication": "clinical_indication",
            "indication": "clinical_indication", "technique": "technique", "findings": "findings",
            "impression": "impression", "diagnosis": "diagnosis", "discharge diagnosis": "discharge_diagnosis",
            "follow up": "follow_up", "follow-up": "follow_up",
        }
        active_name: str | None = None
        active_lines: list[str] = []
        start_page = page.page_number
        sections: list[tuple[str, int, str]] = []
        for line in lines + [""]:
            stripped_line = line.strip()
            heading = re.match(r"^\s*([A-Za-z][A-Za-z /-]{1,40})\s*:\s*(.*)$", line)
            bare_heading = stripped_line.casefold() if stripped_line.casefold() in section_names else ""
            normalized_heading = heading.group(1).strip().casefold() if heading else bare_heading
            if active_name and normalized_heading in section_names:
                sections.append((active_name, start_page, "\n".join(active_lines).strip()))
                active_name, active_lines = None, []
            if normalized_heading in section_names:
                active_name = section_names[normalized_heading]
                start_page = page.page_number
                if heading and heading.group(2).strip():
                    active_lines.append(heading.group(2).strip())
            elif active_name and line.strip():
                active_lines.append(line.strip())
        if active_name:
            sections.append((active_name, start_page, "\n".join(active_lines).strip()))
        for name, source_page, value in sections:
            if not value:
                continue
            results.append(EntityResult(
                category="report_section", name=name, original_name=name.replace("_", " ").title(),
                value=value[:4000], numeric_value=None, unit=None, normalized_value=None,
                normalized_unit=None, reference_range=None, reported_abnormal=None,
                qualitative_value=None, page_number=source_page, source_excerpt=value[:600],
                extraction_method="rule_based", rule_id=f"{RULE_VERSION}:sections",
                quality_score=Decimal("0.800"),
            ))
    # Preserve duplicates and annotate conflicting candidates; never pick one silently.
    by_test: dict[tuple[int | None, str], list[EntityResult]] = {}
    for entity in results:
        if entity.category == "laboratory_result":
            by_test.setdefault((entity.page_number, entity.name), []).append(entity)
    for candidates in by_test.values():
        values = {candidate.value for candidate in candidates}
        if len(values) > 1:
            for candidate in candidates:
                candidate.warnings.append("conflicting_values_on_page")
                candidate.review_status = "required"
    return results


def extract_pdf(path: str, config: Settings) -> PDFResult:
    started = time.monotonic()
    try:
        document = fitz.open(path)
    except Exception as exc:
        raise PDFProcessingError("invalid_pdf") from exc
    with document:
        if document.needs_pass:
            raise PDFProcessingError("encrypted_pdf")
        if document.page_count < 1:
            raise PDFProcessingError("empty_pdf")
        if document.page_count > config.DOCUMENT_MAX_PAGES:
            raise PDFProcessingError("page_limit_exceeded")
        pages: list[PageResult] = []
        tables: list[TableResult] = []
        total_chars = 0
        for index, page in enumerate(document, start=1):
            warnings: list[str] = []
            text = page.get_text("text", sort=True) or ""
            method = "embedded_text"
            ocr_required = len(text.strip()) < config.OCR_MIN_TEXT_CHARS
            ocr_status = "not_required"
            if ocr_required:
                ocr_status = "disabled" if not config.OCR_ENABLED else "unavailable"
                if config.OCR_ENABLED:
                    ocr_text, ocr_error = _run_ocr(page, config)
                    if ocr_text:
                        text, method, ocr_status = ocr_text, "tesseract_ocr", "succeeded"
                    elif ocr_error:
                        warnings.append(ocr_error)
                else:
                    warnings.append("ocr_disabled")
                if not text.strip():
                    warnings.append("page_text_unavailable")
            if not text.strip():
                warnings.append("empty_page")
            total_chars += len(text)
            if total_chars > config.DOCUMENT_MAX_TEXT_CHARS:
                raise PDFProcessingError("extracted_text_limit_exceeded")
            pages.append(PageResult(index, text, method, len(text), ocr_required, ocr_status, warnings))
            try:
                find_tables = getattr(page, "find_tables", None)
                if find_tables:
                    found = find_tables()
                    for table_index, table in enumerate(found.tables or [], start=1):
                        extracted = table.extract() or []
                        if not extracted:
                            continue
                        rows = [[(cell or "").strip() for cell in row] for row in extracted]
                        headers = rows[0]
                        tables.append(TableResult(index, table_index, headers, rows[1:]))
            except Exception:
                pages[-1].warnings.append("table_extraction_failed")
    return PDFResult(pages, tables, int((time.monotonic() - started) * 1000), len(pages))


def _run_ocr(page: Any, config: Settings) -> tuple[str | None, str | None]:
    try:
        import pytesseract
        from PIL import Image, ImageOps
        binary = config.TESSERACT_CMD or shutil.which("tesseract")
        if not binary:
            return None, "ocr_executable_unavailable"
        pytesseract.pytesseract.tesseract_cmd = binary
        pixmap = page.get_pixmap(dpi=config.OCR_DPI, alpha=False)
        image = Image.open(BytesIO(pixmap.tobytes("png"))).convert("L")
        image = ImageOps.autocontrast(image)
        text = pytesseract.image_to_string(image, lang=config.OCR_LANGUAGE, timeout=config.OCR_TIMEOUT_SECONDS)
        if not text.strip():
            return None, "ocr_no_text"
        return text, None
    except Exception as exc:
        name = type(exc).__name__.casefold()
        return None, "ocr_timeout" if "timeout" in name else "ocr_failed"


def build_pipeline_result(path: str, config: Settings, checksum_sha256: str) -> PipelineResult:
    started = time.monotonic()
    pdf = extract_pdf(path, config)
    full_text = "\n".join(page.extracted_text for page in pdf.pages)
    classification = classify_document(full_text)
    entities = extract_entities(pdf.pages)
    review_reasons = list(classification.warnings)
    if any("page_text_unavailable" in page.warnings for page in pdf.pages):
        review_reasons.append("scanned_page_not_ocr_processed")
    if any("conflicting_values_on_page" in item.warnings for item in entities):
        review_reasons.append("conflicting_extracted_values")
    if any(item.review_status == "required" for item in entities):
        review_reasons.append("ambiguous_extraction_requires_review")
    if classification.document_type == "unknown":
        review_reasons.append("classification_requires_review")
    if not any(item.category == "laboratory_result" for item in entities) and classification.document_type not in {"mri", "ct_scan", "x_ray", "ultrasound", "ecg", "discharge_summary", "prescription"}:
        review_reasons.append("no_supported_structured_results")
    return PipelineResult(pdf, classification, entities, sorted(set(review_reasons)), int((time.monotonic() - started) * 1000), checksum_sha256)
