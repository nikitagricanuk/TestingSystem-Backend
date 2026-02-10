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
        self._questions: dict[UUID, Question] = {}

    async def add(self, question: Question):
        self._questions[question.id] = question

    @classmethod
    async def get(cls, qid: UUID) -> Question:
        """
        Mock question getter implementation.
        :param qid:
        :return:
        """
        instance = get_qb()
        cached = instance._questions.get(qid)
        if cached:
            return cached
        questions = load_questions_from_json()
        for question in questions:
            if question.id == qid:
                return question
        if not questions:
            raise ValueError("No questions available")
        return questions[rint(0, len(questions)-1)]

    async def get_question(self, qid: UUID) -> Question:
        return await self.get(qid)

    async def update(self, question: Question):
        if question.id not in self._questions:
            raise KeyError(f"Question {question.id} not found")
        self._questions[question.id] = question

    async def delete(self, question: Question):
        if question.id not in self._questions:
            raise KeyError(f"Question {question.id} not found")
        del self._questions[question.id]

question_bank = QuestionBank()

def get_qb():
    return question_bank
