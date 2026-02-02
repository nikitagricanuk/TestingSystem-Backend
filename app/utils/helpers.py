import json
import uuid

from app.services.testing_engine.question_bank.question_bank import Question


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
