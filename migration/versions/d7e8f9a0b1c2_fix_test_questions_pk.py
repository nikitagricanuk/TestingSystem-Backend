"""fix test_questions primary key and add base columns

Revision ID: d7e8f9a0b1c2
Revises: c2d3e4f5a6b7
Create Date: 2026-02-10 19:41:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d7e8f9a0b1c2"
down_revision: Union[str, Sequence[str], None] = "c2d3e4f5a6b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "test_questions" not in inspector.get_table_names():
        return

    columns = {col["name"] for col in inspector.get_columns("test_questions")}
    if "id" not in columns:
        op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
        op.add_column(
            "test_questions",
            sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        )
    if "created_at" not in columns:
        op.add_column(
            "test_questions",
            sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        )
    if "updated_at" not in columns:
        op.add_column(
            "test_questions",
            sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        )

    pk = inspector.get_pk_constraint("test_questions")
    pk_name = pk.get("name")
    if pk_name and pk.get("constrained_columns") != ["id"]:
        op.drop_constraint(pk_name, "test_questions", type_="primary")
        op.create_primary_key("test_questions_pkey", "test_questions", ["id"])


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "test_questions" not in inspector.get_table_names():
        return

    pk = inspector.get_pk_constraint("test_questions")
    pk_name = pk.get("name")
    if pk_name and pk.get("constrained_columns") == ["id"]:
        op.drop_constraint(pk_name, "test_questions", type_="primary")
        op.create_primary_key("test_questions_pkey", "test_questions", ["test_id", "question_id"])

    columns = {col["name"] for col in inspector.get_columns("test_questions")}
    if "updated_at" in columns:
        op.drop_column("test_questions", "updated_at")
    if "created_at" in columns:
        op.drop_column("test_questions", "created_at")
    if "id" in columns:
        op.drop_column("test_questions", "id")
