# app/core/permissions.py
#
# Permission name strings here MUST match the `permissions.name` rows seeded by the
# alembic migrations (see migration/versions/a1b2c3d4e5f6_add_permissions.py and
# migration/versions/*_add_teacher_and_admissions_roles.py) and checked against via
# UserDAO.check_permission_by_id/check_permission_by_email and require_permissions()
# in app/services/auth/routers/auth.py. These are plain snake_case verb_noun strings,
# not "resource:action" pairs — keep new entries consistent with that convention.
from enum import Enum


class Permissions:
    class Users(str, Enum):
        CREATE = "create_users"
        READ = "read_users"
        UPDATE = "edit_users"
        DELETE = "delete_users"

    class Roles(str, Enum):
        CREATE = "create_roles"
        READ = "read_roles"
        UPDATE = "edit_roles"
        DELETE = "delete_roles"

    class Sessions(str, Enum):
        CREATE = "create_own_session"
        READ = "read_own_sessions"
        ANSWER = "answer_own_session_questions"
        CANCEL = "cancel_own_session"
        READ_ANY = "read_any_sessions"
        CANCEL_ANY = "cancel_any_session"

    class Questions(str, Enum):
        CREATE = "create_questions"
        READ = "read_questions"
        UPDATE = "edit_questions"
        DELETE = "delete_questions"

    class Categories(str, Enum):
        CREATE = "create_categories"
        READ = "read_categories"
        UPDATE = "edit_categories"
        DELETE = "delete_categories"

    class Tests(str, Enum):
        CREATE = "create_tests"
        READ = "read_tests"
        UPDATE = "edit_tests"
        DELETE = "delete_tests"
        READ_ANALYSIS = "read_test_analysis"

    class Certificates(str, Enum):
        CREATE = "create_certificates"
        READ = "read_certificates"
        UPDATE = "edit_certificates"

    class ApplicantContacts(str, Enum):
        READ = "read_applicant_contacts"
        UPDATE = "edit_applicant_contacts"

    @classmethod
    def all(cls) -> set[str]:
        items: set[str] = set()
        for nested in cls.__dict__.values():
            if isinstance(nested, type) and issubclass(nested, Enum):
                items |= {e.value for e in nested}
        return items


ALL_PERMISSIONS: set[str] = Permissions.all()
