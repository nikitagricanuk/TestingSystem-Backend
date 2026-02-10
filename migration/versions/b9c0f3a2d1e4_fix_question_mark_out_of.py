"""fix question mark_out_of column name

Revision ID: b9c0f3a2d1e4
Revises: 005abc1116c9
Create Date: 2026-02-10 19:34:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b9c0f3a2d1e4"
down_revision: Union[str, Sequence[str], None] = "005abc1116c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "questions" not in inspector.get_table_names():
        return
    columns = {col["name"] for col in inspector.get_columns("questions")}
    if "market_out_of" in columns and "mark_out_of" not in columns:
        op.alter_column("questions", "market_out_of", new_column_name="mark_out_of")


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "questions" not in inspector.get_table_names():
        return
    columns = {col["name"] for col in inspector.get_columns("questions")}
    if "mark_out_of" in columns and "market_out_of" not in columns:
        op.alter_column("questions", "mark_out_of", new_column_name="market_out_of")
