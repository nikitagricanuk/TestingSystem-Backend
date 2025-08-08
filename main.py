from app.services import init_redis_connection, load_questions_from_json, create_session
import uuid

if __name__ == "__main__":
    print("Initializing Redis connection...")
    redis = init_redis_connection()
    print("Loading questions from JSON...")
    
    question_ids = load_questions_from_json('questions.json')

    if question_ids:
        print("Creating a new test session...")
        session = create_session(
            user_id=uuid.uuid4(),
            test_id=uuid.uuid4(),
            question_ids=question_ids,
            indefinite_questions=False,
            ip_address="127.0.0.1"
        )
        print(f"Session created with ID: {session.sid}")