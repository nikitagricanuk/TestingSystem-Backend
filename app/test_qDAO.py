import sys
sys.path.append("/app")
import asyncio
from app.models.database import User
from uuid import uuid4
from app.repositories.question_bank.question_dao import QuestionDAO, CategoryDAO
from app.repositories.question_bank.models import Question, Category
from app.repositories.question_bank.exceptions import QuestionNotFoundError

async def main():
    category = await CategoryDAO.create("Math")
    print("Category created:", category.id, category.category)

    question_data = {
        "id": uuid4(),
        "text": "What is 2+2?",
        "teacher_id": "c89d3f2f-0a29-4f43-8968-f3ec7b79ff2f",
        "category_id": "7400af66-47af-4872-bece-8d64a1b8bb04",
        "question_type": "text",
        "problem": "Solve 2+2",
        "answer": {"answer": "4"},
        "market_out_of": 10,
        "penalty": 2,
        "is_active": True
    }

    question = await QuestionDAO().add_question(question_data)
    print("Question added:", question.id, question.text)

    q = await QuestionDAO().get(question.id)
    print("Question retrieved:", q.id, q.text)

    updated = await QuestionDAO().update(question.id, {"text": "Updated: What is 2+2?"})
    print("Question updated:", updated.id, updated.text)

    questions = await QuestionDAO().list()
    print("All questions:", [q.text for q in questions])

    await QuestionDAO().delete(question.id)
    print("Question deleted")

    try:
        await QuestionDAO().get(question.id)
    except QuestionNotFoundError:
        print("Question not found (as expected)")

asyncio.run(main())
