"""Rename cities -> settlements; add 'type' column (backfilled)

Revision ID: 67211c47cbfe
Revises: a1b2c3d4e5f6
Create Date: 2025-10-10 09:56:36.578938
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "67211c47cbfe"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: rename table and add new column safely."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())

    # 1) Rename the table IN-PLACE (preserves data, indexes, FKs).
    #    If you use a schema (e.g., "public"), pass schema="public".
    if "cities" in table_names and "settlements" not in table_names:
        op.rename_table("cities", "settlements")

    # 2) Add the new column as nullable first (to avoid failing on existing rows).
    #    Note: 'type' is allowed as a column name in Postgres, but if you prefer,
    #    you can use 'settlement_type' instead in your ORM & here.
    settlement_columns = {col["name"] for col in inspector.get_columns("settlements")}
    if "type" not in settlement_columns:
        op.add_column(
            "settlements",
            sa.Column("type", sa.String(length=50), nullable=True),
        )

    # 3) Backfill existing rows. Adjust default value as you wish.
    op.execute("UPDATE settlements SET type = 'city' WHERE type IS NULL")

    # 4) Make the column NOT NULL (now that data is populated).
    op.alter_column(
        "settlements",
        "type",
        existing_type=sa.String(length=50),
        nullable=False,
    )

    # NOTE about foreign keys:
    # Renaming a table in Postgres updates FK *targets* automatically.
    # No need to drop/recreate schools.city_id FK unless you want to rename the *constraint name* for aesthetics.
    # If you DO want to rename the FK constraint to match naming conventions, do it with op.execute(...)
    # but it's optional and not functionally required.


def downgrade() -> None:
    """Downgrade schema: drop added column and rename table back."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())

    # 1) Relax by dropping the added column.
    if "settlements" in table_names:
        settlement_columns = {col["name"] for col in inspector.get_columns("settlements")}
        if "type" in settlement_columns:
            op.drop_column("settlements", "type")

    # 2) Rename table back.
    if "settlements" in table_names and "cities" not in table_names:
        op.rename_table("settlements", "cities")
