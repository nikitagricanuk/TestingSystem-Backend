class QuestionDAOError(Exception):
    """The basic exception for QuestionDAO"""
    pass

class QuestionNotFoundError(QuestionDAOError):
    """The issue with the specified ID was not found"""
    pass

class QuestionCreateError(QuestionDAOError):
    """Error when creating a question"""
    pass

class QuestionUpdateError(QuestionDAOError):
    """Error updating the question"""
    pass

class QuestionDeleteError(QuestionDAOError):
    """Error deleting a question"""
    pass

class DAOException(Exception):
    """Общая ошибка DAO."""
    pass

class CategoryNotFound(DAOException):
    """Категория не найдена."""
    pass

class QuestionNotFound(DAOException):
    """Вопрос не найден."""
    pass
