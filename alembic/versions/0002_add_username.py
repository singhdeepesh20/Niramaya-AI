"""Add unique usernames for password login.

Revision ID: 0002
Revises: 0001
"""

from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("username", sa.String(length=32), nullable=True))
    op.execute(
        """UPDATE users
           SET username = left(
               coalesce(nullif(regexp_replace(lower(split_part(email, '@', 1)), '[^a-z0-9_.-]', '', 'g'), ''), 'user'),
               greatest(1, 31 - length(id::text))
           ) || '_' || id::text"""
    )
    op.alter_column("users", "username", nullable=False)
    op.create_index("ix_users_username", "users", ["username"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_users_username", table_name="users")
    op.drop_column("users", "username")
