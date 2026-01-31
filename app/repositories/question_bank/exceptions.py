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

class CategoryDAOError(Exception):
    """The basic exception for CategoryDAO"""
    pass

class CategoryCreateError(CategoryDAOError):
    """Error when creating a category"""
    pass

class CategoryUpdateError(CategoryDAOError):
    """Error updating the category"""
    pass

class CategoryDeleteError(CategoryDAOError):
    """Error deleting a category"""
    pass

class CategoryNotFound(CategoryDAOError):
    """The issue with the specified ID was not found"""
    pass
