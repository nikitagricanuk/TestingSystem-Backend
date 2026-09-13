"""add missing short_name column to schools

Revision ID: f9a0b1c2d3e5
Revises: e8f9a0b1c2d4
Create Date: 2026-09-13 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "f9a0b1c2d3e5"
down_revision: Union[str, Sequence[str], None] = "e8f9a0b1c2d4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # The School ORM model (app/models/database.py) and SchoolOut/School schemas
    # have always declared short_name, but no prior migration ever added the
    # column — any query touching it (GET /v1/schools) fails against real data.
    op.add_column(
        "schools",
        sa.Column("short_name", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("schools", "short_name")
