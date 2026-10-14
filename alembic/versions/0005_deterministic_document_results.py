"""Persist deterministic PDF extraction results and provenance."""

from alembic import op
import sqlalchemy as sa

revision = "0005_deterministic_results"
down_revision = "0004_document_processing"
branch_labels = None
depends_on = None


def upgrade() -> None:
    entity_columns = (
        sa.Column("original_name", sa.String(255), nullable=True),
        sa.Column("numeric_value", sa.Numeric(18, 6), nullable=True),
        sa.Column("unit", sa.String(80), nullable=True),
        sa.Column("normalized_unit", sa.String(80), nullable=True),
        sa.Column("reference_range", sa.String(160), nullable=True),
        sa.Column("reported_abnormal", sa.Boolean(), nullable=True),
        sa.Column("qualitative_value", sa.String(80), nullable=True),
        sa.Column("source_excerpt", sa.Text(), nullable=True),
        sa.Column("extraction_method", sa.String(40), server_default="rule_based", nullable=False),
        sa.Column("rule_id", sa.String(100), nullable=True),
        sa.Column("quality_score", sa.Numeric(4, 3), nullable=True),
        sa.Column("warnings", sa.JSON(), server_default=sa.text("'[]'"), nullable=False),
        sa.Column("review_status", sa.String(24), server_default="not_required", nullable=False),
        sa.Column("extraction_generation", sa.Integer(), server_default="0", nullable=False),
    )
    for column in entity_columns:
        op.add_column("medical_entities", column)
    op.create_index(
        "ix_medical_entities_owner_generation",
        "medical_entities",
        ["user_id", "document_id", "extraction_generation"],
    )

    op.create_table(
        "medical_document_pages",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("document_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("extraction_generation", sa.Integer(), server_default="0", nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("extracted_text", sa.Text(), nullable=False),
        sa.Column("extraction_method", sa.String(40), nullable=False),
        sa.Column("character_count", sa.Integer(), nullable=False),
        sa.Column("ocr_required", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("ocr_status", sa.String(24), server_default="not_required", nullable=False),
        sa.Column("warnings", sa.JSON(), server_default=sa.text("'[]'"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["document_id", "user_id"],
            ["medical_documents.id", "medical_documents.user_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id", "extraction_generation", "page_number", name="uq_document_page_generation"),
    )
    op.create_index("ix_document_pages_owner_document", "medical_document_pages", ["user_id", "document_id", "page_number"])

    op.create_table(
        "medical_document_tables",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("document_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("extraction_generation", sa.Integer(), server_default="0", nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("table_index", sa.Integer(), nullable=False),
        sa.Column("headers", sa.JSON(), nullable=False),
        sa.Column("rows", sa.JSON(), nullable=False),
        sa.Column("extraction_method", sa.String(40), server_default="pymupdf", nullable=False),
        sa.Column("warnings", sa.JSON(), server_default=sa.text("'[]'"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["document_id", "user_id"],
            ["medical_documents.id", "medical_documents.user_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id", "extraction_generation", "page_number", "table_index", name="uq_document_table_generation"),
    )
    op.create_index("ix_document_tables_owner_document", "medical_document_tables", ["user_id", "document_id", "page_number"])

    for table in ("medical_document_pages", "medical_document_tables"):
        op.execute(sa.text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
        op.execute(sa.text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY"))
        op.execute(sa.text(
            f"CREATE POLICY {table}_user_isolation ON {table} "
            "USING (user_id = NULLIF(current_setting('app.current_user_id', true), '')::uuid) "
            "WITH CHECK (user_id = NULLIF(current_setting('app.current_user_id', true), '')::uuid)"
        ))


def downgrade() -> None:
    for table in ("medical_document_tables", "medical_document_pages"):
        op.execute(sa.text(f"DROP POLICY IF EXISTS {table}_user_isolation ON {table}"))
        op.drop_table(table)
    op.drop_index("ix_medical_entities_owner_generation", table_name="medical_entities")
    for column in (
        "extraction_generation", "review_status", "warnings", "quality_score", "rule_id",
        "extraction_method", "source_excerpt", "qualitative_value", "reported_abnormal",
        "reference_range", "normalized_unit", "unit", "numeric_value", "original_name",
    ):
        op.drop_column("medical_entities", column)
