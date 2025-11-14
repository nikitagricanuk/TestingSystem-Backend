import uuid

from sqlalchemy import table, column, String, Text, UUID
from alembic import op

revision = 'a1b2c3d4e5f6'
down_revision = '35772328bea3'  # or previous revision ID

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

def upgrade():
    # Insert permissions
    op.bulk_insert(
        permissions_table,
        [
            {"id": str(uuid.uuid4()), "name": "create_users", "description": "Can create new users"},
            {"id": str(uuid.uuid4()), "name": "read_users", "description": "Can read user data"},
            {"id": str(uuid.uuid4()), "name": "edit_users", "description": "Can edit user data"},
            {"id": str(uuid.uuid4()), "name": "delete_users", "description": "Can delete users"},
            {"id": str(uuid.uuid4()), "name": "create_roles", "description": "Can create user roles"},
            {"id": str(uuid.uuid4()), "name": "read_roles", "description": "Can read user roles"},
            {"id": str(uuid.uuid4()), "name": "edit_roles", "description": "Can edit user roles"},
            {"id": str(uuid.uuid4()), "name": "delete_roles", "description": "Can delete user roles"},
            {"id": str(uuid.uuid4()), "name": "create_own_session", "description": "User can create their own session"},
            {"id": str(uuid.uuid4()), "name": "read_own_sessions", "description": "User can view their own session"},
            {"id": str(uuid.uuid4()), "name": "answer_own_session_questions", "description": "User can answer questions in their own session"},
            {"id": str(uuid.uuid4()), "name": "cancel_own_session", "description": "User can finish their own session"},
            {"id": str(uuid.uuid4()), "name": "read_any_sessions", "description": "Admin can view any session"},
            {"id": str(uuid.uuid4()), "name": "cancel_any_session", "description": "Admin can delete any session"},
        ]
    )

    # Insert roles
    op.bulk_insert(
        roles_table,
        [
            {"id": str(uuid.uuid4()), "role": "admin"},
            {"id": str(uuid.uuid4()), "role": "student"},
        ]
    )

    # Assign permissions to roles using raw SQL (since Alembic bulk_insert can't handle relationships)
    # Admin gets all permissions
    op.execute("""
        INSERT INTO role2permission (role_id, permission_id)
        SELECT r.id, p.id FROM roles r, permissions p WHERE r.role = 'admin'
    """)
    # Student gets only session-related permissions
    op.execute("""
        INSERT INTO role2permission (role_id, permission_id)
        SELECT r.id, p.id FROM roles r, permissions p
        WHERE r.role = 'student'
        AND p.name IN (
            'create_own_session',
            'read_own_sessions',
            'answer_own_session_questions',
            'cancel_own_session'
        )
    """)

def downgrade():
    op.execute(
        "DELETE FROM role2permission WHERE role_id IN (SELECT id FROM roles WHERE role IN ('admin', 'student'))"
    )
    op.execute("DELETE FROM roles WHERE role IN ('admin', 'student')")
    op.execute(
        "DELETE FROM permissions WHERE name IN ("
        "'create_users', 'read_users', 'edit_users', 'delete_users', "
        "'create_roles', 'read_roles', 'edit_roles', 'delete_roles', "
        "'create_own_session', 'read_own_sessions', 'answer_own_session_questions', 'cancel_own_session', "
        "'read_any_sessions', 'cancel_any_session'"
        ")"
    )