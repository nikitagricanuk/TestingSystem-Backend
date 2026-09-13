"""add teacher and admissions_committee roles and permissions

Revision ID: f3a4b5c6d7e8
Revises: d7e8f9a0b1c2
Create Date: 2026-09-12 00:00:00.000000

"""
import uuid
from typing import Sequence, Union

from alembic import op
from sqlalchemy import table, column, String, Text, UUID

# revision identifiers, used by Alembic.
revision: str = "f3a4b5c6d7e8"
down_revision: Union[str, Sequence[str], None] = "d7e8f9a0b1c2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

permissions_table = table(
    "permissions",
    column("id", UUID),
    column("name", String),
    column("description", Text),
)

roles_table = table(
    "roles",
    column("id", UUID),
    column("role", String),
)

NEW_PERMISSIONS = [
    ("create_questions", "Can create questions in own question bank"),
    ("read_questions", "Can read questions"),
    ("edit_questions", "Can edit own questions"),
    ("delete_questions", "Can delete own questions"),
    ("create_categories", "Can create question bank categories"),
    ("read_categories", "Can read question bank categories"),
    ("edit_categories", "Can edit question bank categories"),
    ("delete_categories", "Can delete question bank categories"),
    ("create_tests", "Can create tests"),
    ("read_tests", "Can read tests"),
    ("edit_tests", "Can edit own tests"),
    ("delete_tests", "Can delete own tests"),
    ("read_test_analysis", "Can read test discriminativity/item analysis"),
    ("create_certificates", "Can create certificate templates"),
    ("read_certificates", "Can read/download certificates"),
    ("edit_certificates", "Can edit certificate templates"),
    ("read_applicant_contacts", "Can read applicant contact info and call status"),
    ("edit_applicant_contacts", "Can edit applicant call status/tags"),
]

TEACHER_PERMISSIONS = [
    "create_questions", "read_questions", "edit_questions", "delete_questions",
    "create_categories", "read_categories", "edit_categories", "delete_categories",
    "create_tests", "read_tests", "edit_tests", "delete_tests",
    "read_test_analysis", "read_any_sessions",
]

ADMISSIONS_COMMITTEE_PERMISSIONS = [
    "read_users", "read_tests", "read_any_sessions",
    "create_certificates", "read_certificates", "edit_certificates",
    "read_applicant_contacts", "edit_applicant_contacts",
]


def upgrade() -> None:
    op.bulk_insert(
        permissions_table,
        [{"id": str(uuid.uuid4()), "name": name, "description": description} for name, description in NEW_PERMISSIONS],
    )

    op.bulk_insert(
        roles_table,
        [
            {"id": str(uuid.uuid4()), "role": "teacher"},
            {"id": str(uuid.uuid4()), "role": "admissions_committee"},
        ],
    )

    # `admin` was granted "all permissions" as a one-time INSERT...SELECT back in
    # migration a1b2c3d4e5f6, before these permissions existed — it does not
    # automatically pick up new rows, so grant the new ones explicitly here too.
    new_names_list = ", ".join(f"'{name}'" for name, _ in NEW_PERMISSIONS)
    op.execute(f"""
        INSERT INTO role2permission (role_id, permission_id)
        SELECT r.id, p.id FROM roles r, permissions p
        WHERE r.role = 'admin' AND p.name IN ({new_names_list})
    """)

    teacher_list = ", ".join(f"'{p}'" for p in TEACHER_PERMISSIONS)
    op.execute(f"""
        INSERT INTO role2permission (role_id, permission_id)
        SELECT r.id, p.id FROM roles r, permissions p
        WHERE r.role = 'teacher' AND p.name IN ({teacher_list})
    """)

    admissions_list = ", ".join(f"'{p}'" for p in ADMISSIONS_COMMITTEE_PERMISSIONS)
    op.execute(f"""
        INSERT INTO role2permission (role_id, permission_id)
        SELECT r.id, p.id FROM roles r, permissions p
        WHERE r.role = 'admissions_committee' AND p.name IN ({admissions_list})
    """)


def downgrade() -> None:
    new_names = ", ".join(f"'{name}'" for name, _ in NEW_PERMISSIONS)
    op.execute("""
        DELETE FROM role2permission WHERE role_id IN (
            SELECT id FROM roles WHERE role IN ('teacher', 'admissions_committee')
        )
    """)
    op.execute("DELETE FROM roles WHERE role IN ('teacher', 'admissions_committee')")
    # Also remove admin's grants of the new permissions before deleting the rows themselves.
    op.execute(f"""
        DELETE FROM role2permission WHERE permission_id IN (
            SELECT id FROM permissions WHERE name IN ({new_names})
        )
    """)
    op.execute(f"DELETE FROM permissions WHERE name IN ({new_names})")
