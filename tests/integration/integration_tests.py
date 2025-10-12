import pytest
import uuid
import json
from redis.asyncio import Redis as AsyncRedis
from app.models.redis import TestSession, QuestionRedis, SessionStatus


# Фикстура real_redis_client предоставляется из conftest.py
# и возвращает реально подключенный AsyncRedis-клиент

@pytest.mark.integration
async def test_session_indexing_and_search(real_redis_client: AsyncRedis):
    """
    Проверяет создание индекса для TestSession и поиск по полю ip_address.
    Требует RediSearch.
    """

    # 1. Установка базы данных и управление индексами
    TestSession.Meta.database = real_redis_client

    # Сброс индекса перед тестом для чистоты
    try:
        # Для удаления индекса нужно имя, которое формируется из префикса и имени класса
        await TestSession.drop_index()
    except Exception:
        pass  # Игнорируем, если индекс не существует

    # Создание индекса (требует Redis Stack)
    await TestSession.create_index()

    # 2. Создание тестовых объектов
    session1 = TestSession(
        sid=uuid.uuid4(),
        user_id=uuid.uuid4(),
        test_id=uuid.uuid4(),
        ip_address="192.168.1.10",
        status=SessionStatus.ACTIVE.value,
        question_ids=json.dumps(["q1", "q2"]),
        questions_remaining=2,
        indefinite_questions=False,
        answers=json.dumps({}),
        questions_answered=0,
        current_question_index=0
    )

    session2 = TestSession(**session1.dict(exclude={'sid'}), sid=uuid.uuid4(), ip_address="10.0.0.5")

    await session1.save()
    await session2.save()

    # 3. Поиск (требует RediSearch)
    # Ищем сессии с определенным IP
    results = await TestSession.find(TestSession.ip_address == "192.168.1.10").all()

    # 4. Проверки
    assert len(results) == 1
    assert str(results[0].pk) == str(session1.pk)
    assert results[0].ip_address == "192.168.1.10"

    # 5. Очистка после теста
    await TestSession.drop_index()
    await real_redis_client.flushdb()


@pytest.mark.integration
async def test_question_indexing_and_full_text_search(real_redis_client: AsyncRedis):
    """
    Проверяет создание индекса для QuestionRedis и полнотекстовый поиск по полю text.
    Требует RediSearch.
    """

    # 1. Установка базы данных и управление индексами
    QuestionRedis.Meta.database = real_redis_client

    try:
        await QuestionRedis.drop_index()
    except Exception:
        pass

    await QuestionRedis.create_index()

    # 2. Создание тестовых объектов
    question_math = QuestionRedis(
        question_id=uuid.uuid4(),
        content="What is the result of 2 + 2?",
        index=1,
        correct_answer="4",
        choices=json.dumps(["3", "4", "5"])
    )
    question_history = QuestionRedis(
        question_id=uuid.uuid4(),
        content="Who was the first president?",
        index=2,
        correct_answer="George Washington",
        choices=json.dumps(["Adams", "Washington", "Lincoln"])
    )

    await question_math.save()
    await question_history.save()

    # 3. Поиск (полнотекстовый поиск по слову 'result')
    # Поиск по полю 'text'
    results = await QuestionRedis.find(QuestionRedis.content == "result").all()

    # 4. Проверки
    assert len(results) == 1
    assert results[0].index == question_math.index

    # Поиск по слову 'president'
    results_history = await QuestionRedis.find(QuestionRedis.content == "president").all()
    assert len(results_history) == 1
    assert results_history[0].index == question_history.index

    # 5. Очистка после теста
    await QuestionRedis.drop_index()
    await real_redis_client.flushdb()