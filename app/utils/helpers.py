import json
import uuid
from redis import Redis

from app.models.redis import QuestionRedis


def load_questions_from_json(file_path: str, redis_client: Redis):
    # Явно устанавливаем базу данных перед использованием модели
    QuestionRedis.Meta.database = redis_client
    with open(file_path, 'r', encoding='utf-8') as f:
        questions_data = json.load(f)

    question_ids = []
    print("Starting to save questions.")
    for q_data in questions_data:
        q_data['choices'] = json.dumps(q_data.get('choices', []))
        q_data['question_id'] = str(q_data.get('question_id', uuid.uuid4()))
        question_obj = QuestionRedis(**q_data)
        question_obj.save()
        question_ids.append(question_obj.question_id)

    print(f"Loaded {len(question_ids)} questions into Redis.")
    return question_ids