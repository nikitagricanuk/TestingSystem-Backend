"""create tests tables

Revision ID: c2d3e4f5a6b7
Revises: b9c0f3a2d1e4
Create Date: 2026-02-10 19:37:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c2d3e4f5a6b7"
down_revision: Union[str, Sequence[str], None] = "b9c0f3a2d1e4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())

    if "tests" not in table_names:
        nav_enum = sa.Enum("free", "linear", name="navigation_method_enum", create_type=False)
        op.create_table(
            "tests",
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("start_date", sa.DateTime(), nullable=True),
            sa.Column("end_date", sa.DateTime(), nullable=True),
            sa.Column("number_of_required_questions", sa.Integer(), nullable=True),
            sa.Column("shuffle", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("navigation_method", nav_enum, nullable=False, server_default="free"),
            sa.Column("can_be_reviewed", sa.Boolean(), nullable=True),
            sa.Column("welcome_message", sa.Text(), nullable=True),
            sa.Column("config", sa.JSON(), nullable=True),
            sa.Column("id", sa.UUID(), nullable=False),
            sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )

    if "test_questions" not in table_names:
        op.create_table(
            "test_questions",
            sa.Column("test_id", sa.UUID(), nullable=False),
            sa.Column("question_id", sa.UUID(), nullable=False),
            sa.Column("position_in_test", sa.Integer(), nullable=False),
            sa.Column("id", sa.UUID(), nullable=False),
            sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["test_id"], ["tests.id"]),
            sa.ForeignKeyConstraint(["question_id"], ["questions.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("test_id", "question_id"),
            sa.UniqueConstraint("test_id", "position_in_test"),
        )


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())

    if "test_questions" in table_names:
        op.drop_table("test_questions")
    if "tests" in table_names:
        op.drop_table("tests")

    nav_enum = sa.Enum("free", "linear", name="navigation_method_enum", create_type=False)
    nav_enum.drop(bind, checkfirst=True)
