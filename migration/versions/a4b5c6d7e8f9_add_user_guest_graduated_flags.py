"""add is_guest and is_graduated flags to users, make age nullable

Revision ID: a4b5c6d7e8f9
Revises: f3a4b5c6d7e8
Create Date: 2026-09-12 00:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "a4b5c6d7e8f9"
down_revision: Union[str, Sequence[str], None] = "f3a4b5c6d7e8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("is_guest", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "users",
        sa.Column("is_graduated", sa.Boolean(), nullable=True),
    )
    # Guest accounts (created via POST /v1/auth/guest) don't collect age at signup.
    op.alter_column("users", "age", nullable=True)


def downgrade() -> None:
    op.alter_column("users", "age", nullable=False)
    op.drop_column("users", "is_graduated")
    op.drop_column("users", "is_guest")
