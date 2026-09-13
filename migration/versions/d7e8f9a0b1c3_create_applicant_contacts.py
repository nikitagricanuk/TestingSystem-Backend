"""create applicant_contacts (admissions-committee call status/tags)

Revision ID: d7e8f9a0b1c3
Revises: c6d7e8f9a0b1
Create Date: 2026-09-12 00:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "d7e8f9a0b1c3"
down_revision: Union[str, Sequence[str], None] = "c6d7e8f9a0b1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    status_enum = sa.Enum("called", "not_called", "custom", name="applicant_contact_status_enum")
    op.create_table(
        "applicant_contacts",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("status", status_enum, nullable=False, server_default="not_called"),
        sa.Column("custom_tag", sa.String(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )


def downgrade() -> None:
    op.drop_table("applicant_contacts")
    status_enum = sa.Enum(name="applicant_contact_status_enum")
    status_enum.drop(op.get_bind(), checkfirst=True)
