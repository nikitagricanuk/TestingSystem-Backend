import uuid
from random import randint as rint
from uuid import UUID
from pydantic import BaseModel
import json


class Question(BaseModel):
    id: uuid.UUID
    category: str
    content: str
    choices: list[str]
    correct_answer: str
    marked_out_of: int
    penalty: int

    class Config:
        allow_mutation = False
        frozen = True

def load_questions_from_json() -> list[Question]:
    with open('questions.json', 'r', encoding='utf-8') as f:
        questions_data = json.load(f)

    questions: list[Question] = []
    for q_data in questions_data:
        # Map JSON field `index` to the Question.id field
        question = Question(
            id=uuid.uuid4(),
            category=q_data["category"],
            content=q_data["content"],
            choices=q_data.get("choices", []),
            correct_answer=q_data["correct_answer"],
            marked_out_of=q_data["marked_out_of"],
            penalty=q_data["penalty"],
        )
        questions.append(question)

    return questions


class QuestionBank:
    def __init__(self):
        pass

    async def add(self, question: Question):
        pass

    @classmethod
    async def get(cls, qid: UUID) -> Question:
        """
        Mock question getter implementation.
        :param qid:
        :return:
        """
        questions = load_questions_from_json()
        return questions[rint(0, len(questions)-1)]

    async def update(self, question: Question):
        pass

    async def delete(self, question: Question):
        pass

question_bank = QuestionBank()

def get_qb():
    return question_bank