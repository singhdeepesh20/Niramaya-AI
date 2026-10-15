"""Persist whether a chat response was generated or evidence-only."""

from alembic import op
import sqlalchemy as sa

revision = "0007_chat_generation_status"
down_revision = "0006_rag_indexing"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("health_chat_messages", sa.Column(
        "generation_status", sa.String(24), server_default="generated", nullable=False
    ))


def downgrade() -> None:
    op.drop_column("health_chat_messages", "generation_status")
