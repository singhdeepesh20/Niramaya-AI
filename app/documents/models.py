"""Durable document-processing ledger and outbox models."""
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, ForeignKeyConstraint, Index, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.database import Base


class DocumentProcessingEvent(Base):
    __tablename__ = "document_processing_events"
    __table_args__ = (
        UniqueConstraint("user_id", "document_id", "state_version", name="uq_doc_processing_event_version"),
        Index("ix_doc_processing_events_owner_document", "user_id", "document_id", "created_at"),
    )
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    document_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    previous_state: Mapped[str] = mapped_column(String(32), nullable=False)
    next_state: Mapped[str] = mapped_column(String(32), nullable=False)
    processing_stage: Mapped[str | None] = mapped_column(String(48))
    actor: Mapped[str] = mapped_column(String(120), nullable=False)
    reason_code: Mapped[str] = mapped_column(String(120), nullable=False)
    state_version: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class DocumentStageRun(Base):
    __tablename__ = "document_stage_runs"
    __table_args__ = (
        UniqueConstraint("user_id", "document_id", "generation", "stage", name="uq_doc_stage_run_owner_document_generation_stage"),
        ForeignKeyConstraint(["document_id", "user_id"], ["medical_documents.id", "medical_documents.user_id"], ondelete="CASCADE"),
        Index("ix_doc_stage_runs_owner_document", "user_id", "document_id"),
    )
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    document_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    generation: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    stage: Mapped[str] = mapped_column(String(48), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reason_code: Mapped[str | None] = mapped_column(String(120))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class DocumentProcessingJob(Base):
    __tablename__ = "document_processing_jobs"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_doc_processing_job_idempotency"),
        Index("ix_doc_processing_jobs_claim", "status", "available_at", "locked_until"),
        Index("ix_doc_processing_jobs_owner_document", "user_id", "document_id"),
    )
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    document_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    job_type: Mapped[str] = mapped_column(String(24), nullable=False, default="process")
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="pending")
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    worker_id: Mapped[str | None] = mapped_column(String(120))
    last_reason_code: Mapped[str | None] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
