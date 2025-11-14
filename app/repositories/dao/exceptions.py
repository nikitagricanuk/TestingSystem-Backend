class SchoolNotFoundError(Exception):
    """Exception raised when a school is not found in the database."""
    pass

class UserAlreadyExistsError(Exception):
    """Exception raised when attempting to create a user that already exists."""
    pass

class RoleNotFoundError(Exception):
    """Exception raised when a specified role is not found in the database."""
    pass

