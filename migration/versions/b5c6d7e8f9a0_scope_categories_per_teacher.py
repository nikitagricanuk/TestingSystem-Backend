"""scope question bank categories per teacher

Revision ID: b5c6d7e8f9a0
Revises: a4b5c6d7e8f9
Create Date: 2026-09-12 00:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "b5c6d7e8f9a0"
down_revision: Union[str, Sequence[str], None] = "a4b5c6d7e8f9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {col["name"] for col in inspector.get_columns("categories")}

    if "owner_id" not in columns:
        op.add_column("categories", sa.Column("owner_id", sa.UUID(), nullable=True))
        op.create_foreign_key(
            "categories_owner_id_fkey", "categories", "users", ["owner_id"], ["id"]
        )

    # Existing categories were global (unique by name only); pre-existing rows keep
    # owner_id = NULL. Going forward the API always assigns an owner, and uniqueness
    # is scoped per (owner_id, parent_id, category) instead of globally per name.
    for constraint in inspector.get_unique_constraints("categories"):
        if constraint["column_names"] == ["category"]:
            op.drop_constraint(constraint["name"], "categories", type_="unique")

    existing_composite = {
        tuple(c["column_names"])
        for c in inspector.get_unique_constraints("categories")
    }
    if ("owner_id", "parent_id", "category") not in existing_composite:
        op.create_unique_constraint(
            "categories_owner_parent_name_key",
            "categories",
            ["owner_id", "parent_id", "category"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    for constraint in inspector.get_unique_constraints("categories"):
        if constraint["column_names"] == ["owner_id", "parent_id", "category"]:
            op.drop_constraint(constraint["name"], "categories", type_="unique")

    op.create_unique_constraint("categories_category_key", "categories", ["category"])

    columns = {col["name"] for col in inspector.get_columns("categories")}
    if "owner_id" in columns:
        op.drop_constraint("categories_owner_id_fkey", "categories", type_="foreignkey")
        op.drop_column("categories", "owner_id")
