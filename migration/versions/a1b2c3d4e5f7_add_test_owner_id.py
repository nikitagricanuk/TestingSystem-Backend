"""add owner_id to tests

Revision ID: a1b2c3d4e5f7
Revises: f9a0b1c2d3e5
Create Date: 2026-09-14 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f7"
down_revision: Union[str, Sequence[str], None] = "f9a0b1c2d3e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Test had no owner at all — any authenticated user could list, edit, or
    # delete any test, and there was no way to build a "Мои тесты" (my tests)
    # view for a teacher. Nullable so pre-existing tests aren't orphaned by
    # the migration; the app treats owner_id IS NULL as a legacy/unowned test
    # any teacher may manage.
    op.add_column(
        "tests",
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "tests_owner_id_fkey", "tests", "users", ["owner_id"], ["id"]
    )


def downgrade() -> None:
    op.drop_constraint("tests_owner_id_fkey", "tests", type_="foreignkey")
    op.drop_column("tests", "owner_id")
