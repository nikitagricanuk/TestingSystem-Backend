"""create certificate_templates

Revision ID: e8f9a0b1c2d4
Revises: d7e8f9a0b1c3
Create Date: 2026-09-12 00:25:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "e8f9a0b1c2d4"
down_revision: Union[str, Sequence[str], None] = "d7e8f9a0b1c3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    kind_enum = sa.Enum("base", "advanced", name="certificate_kind_enum")
    op.create_table(
        "certificate_templates",
        sa.Column("test_id", sa.UUID(), nullable=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("kind", kind_enum, nullable=False, server_default="base"),
        sa.Column("asset_path", sa.String(), nullable=False),
        sa.Column("fields", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("signature_asset_path", sa.String(), nullable=True),
        sa.Column("signature_position", sa.JSON(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["test_id"], ["tests.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("certificate_templates")
    kind_enum = sa.Enum(name="certificate_kind_enum")
    kind_enum.drop(op.get_bind(), checkfirst=True)
