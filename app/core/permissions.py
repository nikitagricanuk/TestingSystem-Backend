# app/security/permissions.py
from enum import Enum


class Resource(str, Enum):
    USERS = "users"
    SESSIONS = "sessions"
    # Add new resources here


class Action(str, Enum):
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    CANCEL = "cancel"
    # Add more actions if needed


class Permissions:
    class Users(str, Enum):
        CREATE = f"{Resource.USERS}:{Action.CREATE}"
        READ = f"{Resource.USERS}:{Action.READ}"
        UPDATE = f"{Resource.USERS}:{Action.UPDATE}"
        DELETE = f"{Resource.USERS}:{Action.DELETE}"

    class Sessions(str, Enum):
        CREATE = f"{Resource.SESSIONS}:{Action.CREATE}"
        READ = f"{Resource.SESSIONS}:{Action.READ}"
        CANCEL = f"{Resource.SESSIONS}:{Action.CANCEL}"

    @classmethod
    def all(cls) -> set[str]:
        items = set()
        for nested in cls.__dict__.values():
            if isinstance(nested, type) and issubclass(nested, Enum):
                items |= {e.value for e in nested}
        return items


ALL_PERMISSIONS: set[str] = Permissions.all()

