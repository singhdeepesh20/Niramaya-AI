from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

DocumentType = Literal["cbc", "blood_test", "mri", "prescription", "discharge_summary", "x_ray", "other"]


class MedicalDocumentPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    original_filename: str
    document_type: str
    content_type: str
    file_size: int
    upload_status: str
    processing_state: str = "uploaded"
    processing_version: int = 0
    created_at: datetime
    updated_at: datetime


class DocumentSummary(BaseModel):
    total_reports: int
    blood_tests: int
    imaging_reports: int
    recent_uploads: int


class MedicalDocumentPage(BaseModel):
    items: list[MedicalDocumentPublic]
    total: int
    limit: int
    offset: int
    summary: DocumentSummary


class PresignedDocumentUrl(BaseModel):
    url: str
    expires_in: int


class StorageCheck(BaseModel):
    configured: bool
    region: str
    bucket_accessible: bool
    private_configuration_verified: bool
    checks: dict[str, bool | None]
    unverified_checks: list[str]
    credential_source: str | None


class ExtractedEntityPublic(BaseModel):
    id: UUID
    category: str
    name: str
    original_name: str | None
    value: str | None
    numeric_value: float | None
    unit: str | None
    normalized_value: str | None
    normalized_unit: str | None
    reference_range: str | None
    reported_abnormal: bool | None
    qualitative_value: str | None
    page_number: int | None
    source_excerpt: str | None
    extraction_method: str
    rule_id: str | None
    quality_score: float | None
    warnings: list[str]
    review_status: str


class ExtractedEntitiesResponse(BaseModel):
    document_id: UUID
    generation: int
    items: list[ExtractedEntityPublic]


class DocumentPagePublic(BaseModel):
    page_number: int
    extracted_text: str
    extraction_method: str
    character_count: int
    ocr_required: bool
    ocr_status: str
    warnings: list[str]


class DocumentPagesResponse(BaseModel):
    document_id: UUID
    generation: int
    total: int
    limit: int
    offset: int
    items: list[DocumentPagePublic]


class DocumentTablePublic(BaseModel):
    page_number: int
    table_index: int
    headers: list[str]
    rows: list[list[str]]
    extraction_method: str
    warnings: list[str]


class DocumentTablesResponse(BaseModel):
    document_id: UUID
    generation: int
    items: list[DocumentTablePublic]


class ProcessingEventPublic(BaseModel):
    previous_state: str
    next_state: str
    processing_stage: str | None
    actor: str
    reason_code: str
    state_version: int
    created_at: datetime


class ProcessingStagePublic(BaseModel):
    stage: str
    status: str
    attempts: int
    reason_code: str | None
    started_at: datetime | None
    finished_at: datetime | None


class ProcessingHistoryResponse(BaseModel):
    document_id: UUID
    generation: int
    events: list[ProcessingEventPublic]
    stages: list[ProcessingStagePublic]
    job_status: str | None
    error_code: str | None


class ProcessingStatusResponse(BaseModel):
    document_id: UUID
    document_type: str
    processing_state: str
    processing_version: int
    processing_generation: int
    processing_updated_at: datetime
    processing: dict
    stages: list[ProcessingStagePublic]
