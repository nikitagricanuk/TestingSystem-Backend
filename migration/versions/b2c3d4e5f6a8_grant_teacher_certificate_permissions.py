"""grant teacher certificate permissions

Revision ID: b2c3d4e5f6a8
Revises: a1b2c3d4e5f7
Create Date: 2026-09-14 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6a8"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TEACHER_CERTIFICATE_PERMISSIONS = ["create_certificates", "read_certificates", "edit_certificates"]


def upgrade() -> None:
    # The Admin PDF shows the certificate editor as one of a *test's* own tabs
    # (Overview/Рейтинг/Аналитика/Сертификаты), reached by the test's owner —
    # a teacher. Teacher was never granted these permissions when they were
    # first seeded (only admin/admissions_committee), which would 403 the
    # exact flow the design shows; admissions_committee keeps its own grant
    # for managing the global default / any test's template.
    names_list = ", ".join(f"'{p}'" for p in TEACHER_CERTIFICATE_PERMISSIONS)
    op.execute(f"""
        INSERT INTO role2permission (role_id, permission_id)
        SELECT r.id, p.id FROM roles r, permissions p
        WHERE r.role = 'teacher' AND p.name IN ({names_list})
    """)


def downgrade() -> None:
    names_list = ", ".join(f"'{p}'" for p in TEACHER_CERTIFICATE_PERMISSIONS)
    op.execute(f"""
        DELETE FROM role2permission WHERE role_id IN (
            SELECT id FROM roles WHERE role = 'teacher'
        ) AND permission_id IN (
            SELECT id FROM permissions WHERE name IN ({names_list})
        )
    """)
