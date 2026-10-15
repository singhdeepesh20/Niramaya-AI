from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, ForeignKeyConstraint, Index, Integer, JSON, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.database import Base


class MedicalDocument(Base):
    __tablename__ = "medical_documents"
    __table_args__ = (
        Index("ix_medical_documents_owner_created", "user_id", "created_at"),
        Index("ix_medical_documents_owner_type_date", "user_id", "document_type", "document_date"),
        Index("ix_medical_documents_owner_status_created", "user_id", "upload_status", "created_at"),
        UniqueConstraint("id", "user_id", name="uq_medical_documents_id_owner"),
        CheckConstraint("file_size >= 0", name="ck_medical_documents_file_size_nonnegative"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    document_type: Mapped[str] = mapped_column(String(64), nullable=False)
    document_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    content_type: Mapped[str] = mapped_column(String(127), nullable=False, default="application/octet-stream")
    file_size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    object_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    upload_status: Mapped[str] = mapped_column(String(24), nullable=False, default="ready", server_default="ready")
    processing_state: Mapped[str] = mapped_column(String(32), nullable=False, default="uploaded", server_default="uploaded")
    processing_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    processing_generation: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    processing_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    indexing_status: Mapped[str] = mapped_column(String(24), nullable=False, default="not_started", server_default="not_started")
    indexed_chunk_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    indexing_model: Mapped[str | None] = mapped_column(String(255), nullable=True)
    indexing_dimension: Mapped[int | None] = mapped_column(Integer, nullable=True)
    indexing_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    indexing_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    indexing_error_code: Mapped[str | None] = mapped_column(String(120), nullable=True)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class MedicalEntity(Base):
    __tablename__ = "medical_entities"
    __table_args__ = (
        Index("ix_medical_entities_owner_document", "user_id", "document_id"),
        ForeignKeyConstraint(
            ["document_id", "user_id"],
            ["medical_documents.id", "medical_documents.user_id"],
            ondelete="CASCADE",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    document_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    value: Mapped[str | None] = mapped_column(String(512), nullable=True)
    normalized_value: Mapped[str | None] = mapped_column(String(512), nullable=True)
    original_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    numeric_value: Mapped[float | None] = mapped_column(Numeric(18, 6), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(80), nullable=True)
    normalized_unit: Mapped[str | None] = mapped_column(String(80), nullable=True)
    reference_range: Mapped[str | None] = mapped_column(String(160), nullable=True)
    reported_abnormal: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    qualitative_value: Mapped[str | None] = mapped_column(String(80), nullable=True)
    source_excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
    extraction_method: Mapped[str] = mapped_column(String(40), nullable=False, default="rule_based")
    rule_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    quality_score: Mapped[float | None] = mapped_column(Numeric(4, 3), nullable=True)
    warnings: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    review_status: Mapped[str] = mapped_column(String(24), nullable=False, default="not_required")
    extraction_generation: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class DocumentPage(Base):
    __tablename__ = "medical_document_pages"
    __table_args__ = (
        UniqueConstraint("document_id", "extraction_generation", "page_number", name="uq_document_page_generation"),
        ForeignKeyConstraint(
            ["document_id", "user_id"],
            ["medical_documents.id", "medical_documents.user_id"],
            ondelete="CASCADE",
        ),
        Index("ix_document_pages_owner_document", "user_id", "document_id", "page_number"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    document_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    extraction_generation: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    extracted_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    extraction_method: Mapped[str] = mapped_column(String(40), nullable=False)
    character_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ocr_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    ocr_status: Mapped[str] = mapped_column(String(24), nullable=False, default="not_required")
    warnings: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class DocumentExtractedTable(Base):
    __tablename__ = "medical_document_tables"
    __table_args__ = (
        UniqueConstraint("document_id", "extraction_generation", "page_number", "table_index", name="uq_document_table_generation"),
        ForeignKeyConstraint(
            ["document_id", "user_id"],
            ["medical_documents.id", "medical_documents.user_id"],
            ondelete="CASCADE",
        ),
        Index("ix_document_tables_owner_document", "user_id", "document_id", "page_number"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    document_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    extraction_generation: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    table_index: Mapped[int] = mapped_column(Integer, nullable=False)
    headers: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    rows: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    extraction_method: Mapped[str] = mapped_column(String(40), nullable=False, default="pymupdf")
    warnings: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class MedicalChunk(Base):
    __tablename__ = "medical_document_chunks"
    __table_args__ = (
        Index("ix_medical_chunks_owner_document", "user_id", "document_id"),
        Index("ix_medical_chunks_document_page", "document_id", "page_number"),
        UniqueConstraint("document_id", "chunk_index", name="uq_medical_chunks_document_index"),
        ForeignKeyConstraint(
            ["document_id", "user_id"],
            ["medical_documents.id", "medical_documents.user_id"],
            ondelete="CASCADE",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    document_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    section: Mapped[str | None] = mapped_column(String(100), nullable=True)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    extraction_generation: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    embedding_model: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class HealthChatMessage(Base):
    __tablename__ = "health_chat_messages"
    __table_args__ = (Index("ix_health_chat_owner_created", "user_id", "created_at"),)

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    question: Mapped[str] = mapped_column(String(1000), nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    generation_status: Mapped[str] = mapped_column(String(24), nullable=False, default="generated", server_default="generated")
    citations: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
