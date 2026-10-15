"""Persist RAG indexing state and chunk provenance without storing vectors."""

from alembic import op
import sqlalchemy as sa

revision = "0006_rag_indexing"
down_revision = "0005_deterministic_results"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for column in (
        sa.Column("indexing_status", sa.String(24), server_default="not_started", nullable=False),
        sa.Column("indexed_chunk_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("indexing_model", sa.String(255), nullable=True),
        sa.Column("indexing_dimension", sa.Integer(), nullable=True),
        sa.Column("indexing_attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("indexing_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("indexing_error_code", sa.String(120), nullable=True),
    ):
        op.add_column("medical_documents", column)
    for column in (
        sa.Column("section", sa.String(100), nullable=True),
        sa.Column("content_hash", sa.String(64), server_default="", nullable=False),
        sa.Column("extraction_generation", sa.Integer(), server_default="0", nullable=False),
        sa.Column("embedding_model", sa.String(255), nullable=True),
    ):
        op.add_column("medical_document_chunks", column)


def downgrade() -> None:
    for column in ("embedding_model", "extraction_generation", "content_hash", "section"):
        op.drop_column("medical_document_chunks", column)
    for column in ("indexing_error_code", "indexing_updated_at", "indexing_attempts",
                   "indexing_dimension", "indexing_model", "indexed_chunk_count", "indexing_status"):
        op.drop_column("medical_documents", column)
