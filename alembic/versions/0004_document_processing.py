"""Add durable document processing state machine and job outbox."""
from alembic import op
import sqlalchemy as sa

revision = "0004_document_processing"
down_revision = "0003_s3_medical_documents"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("medical_documents", sa.Column("processing_state", sa.String(32), server_default="uploaded", nullable=False))
    op.add_column("medical_documents", sa.Column("processing_version", sa.Integer(), server_default="0", nullable=False))
    op.add_column("medical_documents", sa.Column("processing_generation", sa.Integer(), server_default="0", nullable=False))
    op.add_column("medical_documents", sa.Column("processing_updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_table(
        "document_processing_events",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("document_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("previous_state", sa.String(32), nullable=False),
        sa.Column("next_state", sa.String(32), nullable=False),
        sa.Column("processing_stage", sa.String(48)),
        sa.Column("actor", sa.String(120), nullable=False),
        sa.Column("reason_code", sa.String(120), nullable=False),
        sa.Column("state_version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", "document_id", "state_version", name="uq_doc_processing_event_version"),
    )
    op.create_index("ix_doc_processing_events_owner_document", "document_processing_events", ["user_id", "document_id", "created_at"])
    op.create_table(
        "document_stage_runs",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("document_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("generation", sa.Integer(), server_default="0", nullable=False),
        sa.Column("stage", sa.String(48), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("reason_code", sa.String(120)),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["document_id", "user_id"], ["medical_documents.id", "medical_documents.user_id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "document_id", "generation", "stage", name="uq_doc_stage_run_owner_document_generation_stage"),
    )
    op.create_index("ix_doc_stage_runs_owner_document", "document_stage_runs", ["user_id", "document_id"])
    op.create_table(
        "document_processing_jobs",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("document_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("job_type", sa.String(24), server_default="process", nullable=False),
        sa.Column("status", sa.String(24), server_default="pending", nullable=False),
        sa.Column("idempotency_key", sa.String(255), nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("max_attempts", sa.Integer(), server_default="5", nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("locked_until", sa.DateTime(timezone=True)),
        sa.Column("worker_id", sa.String(120)),
        sa.Column("last_reason_code", sa.String(120)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("idempotency_key", name="uq_doc_processing_job_idempotency"),
    )
    op.create_index("ix_doc_processing_jobs_claim", "document_processing_jobs", ["status", "available_at", "locked_until"])
    op.create_index("ix_doc_processing_jobs_owner_document", "document_processing_jobs", ["user_id", "document_id"])
    # Worker queue is intentionally not RLS protected: it must claim jobs across tenants.
    # Every worker document read/write remains explicitly scoped by the job's user_id.
    for table in ("document_processing_events", "document_stage_runs"):
        op.execute(sa.text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
        op.execute(sa.text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY"))
        op.execute(sa.text(
            f"CREATE POLICY {table}_user_isolation ON {table} "
            "USING (user_id = NULLIF(current_setting('app.current_user_id', true), '')::uuid) "
            "WITH CHECK (user_id = NULLIF(current_setting('app.current_user_id', true), '')::uuid)"
        ))
    op.create_unique_constraint("uq_medical_chunks_document_index", "medical_document_chunks", ["document_id", "chunk_index"])


def downgrade() -> None:
    op.drop_constraint("uq_medical_chunks_document_index", "medical_document_chunks", type_="unique")
    for table in ("document_processing_events", "document_stage_runs"):
        op.execute(sa.text(f"DROP POLICY IF EXISTS {table}_user_isolation ON {table}"))
    op.drop_index("ix_doc_processing_jobs_owner_document", table_name="document_processing_jobs")
    op.drop_index("ix_doc_processing_jobs_claim", table_name="document_processing_jobs")
    op.drop_table("document_processing_jobs")
    op.drop_index("ix_doc_stage_runs_owner_document", table_name="document_stage_runs")
    op.drop_table("document_stage_runs")
    op.drop_index("ix_doc_processing_events_owner_document", table_name="document_processing_events")
    op.drop_table("document_processing_events")
    for column in ("processing_updated_at", "processing_generation", "processing_version", "processing_state"):
        op.drop_column("medical_documents", column)
