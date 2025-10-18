"""Updated schools, added full_name and short_name

Revision ID: 033282907fb3
Revises: 67211c47cbfe
Create Date: 2025-10-14 01:31:09.577578
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "033282907fb3"
down_revision: Union[str, Sequence[str], None] = "67211c47cbfe"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1) Add full_name as NULLable so we can backfill
    op.add_column("schools", sa.Column("full_name", sa.String(), nullable=True))

    # 2) Backfill full_name from the old column
    #    (We still have the old name 'school' at this point)
    op.execute("UPDATE schools SET full_name = school")

    # 3) Rename 'school' -> 'short_name' (use one of the following depending on Alembic/SQLA versions)
    # Preferred and backend-agnostic where supported:
    op.alter_column("schools", "school", new_column_name="short_name")
    # If your Alembic version doesn't support new_column_name, use:
    # op.rename_column("schools", "school", "short_name")

    # 4) Make full_name NOT NULL after data is present
    op.alter_column("schools", "full_name", nullable=False)


def downgrade() -> None:
    # Reverse the rename: short_name -> school
    op.alter_column("schools", "short_name", new_column_name="school")
    # If needed:
    # op.rename_column("schools", "short_name", "school")

    # Drop full_name
    op.drop_column("schools", "full_name")