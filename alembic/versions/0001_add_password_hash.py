"""Add a nullable password hash to support authenticated accounts.

Revision ID: 0001
Revises:
"""

from alembic import op
from sqlalchemy import inspect
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    inspector = inspect(connection)
    if "users" not in inspector.get_table_names():
        op.create_table(
            "users",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.String(length=120), nullable=False),
            sa.Column("email", sa.String(length=320), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("password_hash", sa.String(length=255), nullable=True),
        )
        op.create_index("ix_users_email", "users", ["email"], unique=True)
    elif "password_hash" not in {column["name"] for column in inspector.get_columns("users")}:
        op.add_column("users", sa.Column("password_hash", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "password_hash")
