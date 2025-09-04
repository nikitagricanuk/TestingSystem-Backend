import uuid
import time
from app.services import load_questions_from_json, create_session, get_session

if __name__ == '__main__':
    # init_redis_connection() больше не нужен здесь
    print("Loading questions from JSON...")
    # Убедитесь, что путь к файлу верен
    question_ids = load_questions_from_json('questions.json')

    print("Creating a new test session...")
    session = create_session(
        user_id=uuid.uuid4(),
        test_id=uuid.uuid4(),
        question_ids=question_ids,
        indefinite_questions=False,
        ip_address="127.0.0.1"
    )
    print(f"Session created with ID: {session.sid}")

    try:
        print("Verifying data from within the application...")
        retrieved_session = get_session(session.sid)
        if retrieved_session:
            print(f"Successfully retrieved session with ID: {retrieved_session.sid}")
        else:
            print("Failed to retrieve the session.")

        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        print("Application stopped.")
    except Exception as e:
        print(f"An error occurred: {e}")