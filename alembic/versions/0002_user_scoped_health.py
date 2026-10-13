"""Add user-scoped medical records, chunks, entities, and chat history."""

from alembic import op
import sqlalchemy as sa

revision = "0002_user_scoped_health"
down_revision = "0001_create_users"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "medical_documents",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("document_type", sa.String(length=64), nullable=False),
        sa.Column("document_date", sa.Date(), nullable=True),
        sa.Column("object_key", sa.String(length=1024), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "user_id", name="uq_medical_documents_id_owner"),
    )
    op.create_index("ix_medical_documents_owner_created", "medical_documents", ["user_id", "created_at"])
    op.create_index("ix_medical_documents_owner_type_date", "medical_documents", ["user_id", "document_type", "document_date"])

    op.create_table(
        "medical_entities",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("document_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("value", sa.String(length=512), nullable=True),
        sa.Column("normalized_value", sa.String(length=512), nullable=True),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["document_id", "user_id"],
            ["medical_documents.id", "medical_documents.user_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_medical_entities_owner_document", "medical_entities", ["user_id", "document_id"])

    op.create_table(
        "medical_document_chunks",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("document_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["document_id", "user_id"],
            ["medical_documents.id", "medical_documents.user_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_medical_chunks_owner_document", "medical_document_chunks", ["user_id", "document_id"])
    op.create_index("ix_medical_chunks_document_page", "medical_document_chunks", ["document_id", "page_number"])
    op.create_index(
        "ix_medical_chunks_fts",
        "medical_document_chunks",
        [sa.text("to_tsvector('simple', content)")],
        postgresql_using="gin",
    )

    op.create_table(
        "health_chat_messages",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("question", sa.String(length=1000), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("citations", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_health_chat_owner_created", "health_chat_messages", ["user_id", "created_at"])

    # Defense in depth. Runtime roles must not be PostgreSQL superusers or BYPASSRLS roles.
    for table in ("medical_documents", "medical_entities", "medical_document_chunks", "health_chat_messages"):
        op.execute(sa.text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
        op.execute(sa.text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY"))
        op.execute(sa.text(
            f"CREATE POLICY {table}_user_isolation ON {table} "
            "USING (user_id = NULLIF(current_setting('app.current_user_id', true), '')::uuid) "
            "WITH CHECK (user_id = NULLIF(current_setting('app.current_user_id', true), '')::uuid)"
        ))


def downgrade() -> None:
    for table in ("health_chat_messages", "medical_document_chunks", "medical_entities", "medical_documents"):
        op.execute(sa.text(f"DROP POLICY IF EXISTS {table}_user_isolation ON {table}"))
        if table == "medical_document_chunks":
            op.drop_index("ix_medical_chunks_fts", table_name=table)
        op.drop_table(table)
