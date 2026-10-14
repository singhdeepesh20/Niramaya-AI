"""Add upload metadata to existing user-scoped medical documents."""

from alembic import op
import sqlalchemy as sa

revision = "0003_s3_medical_documents"
down_revision = "0002_user_scoped_health"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("medical_documents", sa.Column("original_filename", sa.String(255), nullable=True))
    op.add_column("medical_documents", sa.Column("content_type", sa.String(127), nullable=True))
    op.add_column("medical_documents", sa.Column("file_size", sa.Integer(), nullable=True))
    op.add_column(
        "medical_documents",
        sa.Column("upload_status", sa.String(24), server_default="ready", nullable=False),
    )
    op.add_column(
        "medical_documents",
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
    )
    op.execute(
        "UPDATE medical_documents SET original_filename = name, content_type = 'application/octet-stream', "
        "file_size = 0, updated_at = created_at WHERE original_filename IS NULL"
    )
    op.alter_column("medical_documents", "original_filename", nullable=False)
    op.alter_column("medical_documents", "content_type", nullable=False)
    op.alter_column("medical_documents", "file_size", nullable=False)
    op.alter_column("medical_documents", "updated_at", nullable=False)
    op.create_check_constraint(
        "ck_medical_documents_file_size_nonnegative", "medical_documents", "file_size >= 0"
    )
    op.create_index(
        "ix_medical_documents_owner_status_created",
        "medical_documents",
        ["user_id", "upload_status", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_medical_documents_owner_status_created", table_name="medical_documents")
    op.drop_constraint("ck_medical_documents_file_size_nonnegative", "medical_documents", type_="check")
    op.drop_column("medical_documents", "updated_at")
    op.drop_column("medical_documents", "upload_status")
    op.drop_column("medical_documents", "file_size")
    op.drop_column("medical_documents", "content_type")
    op.drop_column("medical_documents", "original_filename")
