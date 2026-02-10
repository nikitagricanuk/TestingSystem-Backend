from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.schemas.users import UserFull
from app.services.auth.routers.auth import get_current_user


class DummySession:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def commit(self):
        return None

    async def rollback(self):
        return None


def _make_user(user_id: UUID) -> UserFull:
    now = datetime.now(timezone.utc)
    return UserFull(
        id=user_id,
        nickname="tester",
        email="tester@example.com",
        is_active=True,
        role="teacher",
        created_at=now,
        created_at_unix=int(now.timestamp()),
        updated_at=None,
        updated_at_unix=None,
        full_name="Test User",
        age=None,
        phone=None,
        school=None,
        permissions=[],
    )


@pytest.fixture()
def app():
    app = FastAPI()
    from app.routers import tests as tests_router

    app.include_router(tests_router.router, prefix="/v1")
    return app


@pytest.fixture()
def client(app: FastAPI):
    return TestClient(app)


@pytest.fixture()
def override_user(app: FastAPI):
    user_id = uuid4()

    async def _override():
        return _make_user(user_id)

    app.dependency_overrides[get_current_user] = _override
    return user_id


@pytest.fixture()
def patch_session_maker(monkeypatch):
    from app.routers import tests as tests_router

    monkeypatch.setattr(tests_router, "async_session_maker", lambda: DummySession())


@pytest.fixture()
def patch_daos(monkeypatch):
    from app.repositories.dao.testdao import TestDAO
    from app.repositories.question_bank.question_dao import QuestionDAO

    state = {}

    async def fake_list_tests(*, offset=0, limit=100, session=None):
        return state.get("tests", [])[offset:offset + limit]

    async def fake_get_test(test_id: UUID, session=None):
        return state.get("test_by_id")

    async def fake_create_test(data: dict, session=None):
        test = SimpleNamespace(id=uuid4(), **data, created_at=None, updated_at=None)
        state["created_test"] = test
        return test

    async def fake_update_test(test_id: UUID, data: dict, session=None):
        test = state.get("test_by_id")
        if not test:
            return None
        for key, value in data.items():
            setattr(test, key, value)
        return test

    async def fake_delete_test(test_id: UUID, session=None):
        state["deleted_test_id"] = test_id
        return True

    async def fake_add_questions(test_id: UUID, question_ids, session=None):
        state["added_questions"] = list(question_ids)
        return None

    async def fake_list_questions(test_id: UUID, session=None):
        return state.get("test_questions", [])

    async def fake_get_test_question(test_id: UUID, question_id: UUID, session=None):
        return state.get("test_question")

    async def fake_remove_test_question(test_id: UUID, question_id: UUID, session=None):
        state["removed_question_id"] = question_id
        return True

    async def fake_get_question(question_id: UUID, session=None):
        question = state.get("question")
        if question is None or question.id != question_id:
            from app.repositories.question_bank.exceptions import QuestionNotFoundError
            raise QuestionNotFoundError("not found")
        return question

    async def fake_add_question(data: dict, session=None):
        question = SimpleNamespace(id=uuid4(), **data)
        state["created_question"] = question
        return question

    async def fake_update_question(question_id: UUID, data: dict, session=None):
        question = state.get("question")
        for key, value in data.items():
            setattr(question, key, value)
        return question

    async def fake_delete_question(question_id: UUID, session=None):
        state["deleted_question_id"] = question_id
        return None

    monkeypatch.setattr(TestDAO, "list", fake_list_tests, raising=False)
    monkeypatch.setattr(TestDAO, "get", fake_get_test, raising=False)
    monkeypatch.setattr(TestDAO, "create", fake_create_test, raising=False)
    monkeypatch.setattr(TestDAO, "update", fake_update_test, raising=False)
    monkeypatch.setattr(TestDAO, "delete", fake_delete_test, raising=False)
    monkeypatch.setattr(TestDAO, "add_questions", fake_add_questions, raising=False)
    monkeypatch.setattr(TestDAO, "list_questions", fake_list_questions, raising=False)
    monkeypatch.setattr(TestDAO, "get_question", fake_get_test_question, raising=False)
    monkeypatch.setattr(TestDAO, "remove_question", fake_remove_test_question, raising=False)

    monkeypatch.setattr(QuestionDAO, "get", fake_get_question, raising=False)
    monkeypatch.setattr(QuestionDAO, "add_question", fake_add_question, raising=False)
    monkeypatch.setattr(QuestionDAO, "update", fake_update_question, raising=False)
    monkeypatch.setattr(QuestionDAO, "delete", fake_delete_question, raising=False)

    return state


def test_list_tests_returns_payload(client: TestClient, patch_session_maker, patch_daos):
    patch_daos["tests"] = [
        SimpleNamespace(id=uuid4(), name="T1", description=None, shuffle=True, navigation_method="free"),
        SimpleNamespace(id=uuid4(), name="T2", description=None, shuffle=True, navigation_method="free"),
    ]
    patch_daos["test_questions"] = []

    res = client.get("/v1/tests")

    assert res.status_code == 200
    body = res.json()
    assert len(body) == 2
    assert body[0]["name"] == "T1"


def test_create_test_validates_duplicates(client: TestClient, patch_session_maker, patch_daos, override_user):
    question_id = str(uuid4())
    patch_daos["question"] = SimpleNamespace(
        id=UUID(question_id),
        text="Q",
        answer={"correct": "A"},
        category_id=uuid4(),
        teacher_id=override_user,
        question_type="text",
        problem="P",
        mark_out_of=5,
        penalty=0,
        is_active=True,
    )

    res = client.post(
        "/v1/tests/create",
        json={
            "name": "Test",
            "question_ids": [question_id, question_id],
        },
    )

    assert res.status_code == 400
    assert res.json()["detail"] == "Duplicate question_ids are not allowed"


def test_create_test_success(client: TestClient, patch_session_maker, patch_daos, override_user):
    question_id = uuid4()
    patch_daos["question"] = SimpleNamespace(
        id=question_id,
        text="Q",
        answer={"correct": "A"},
        category_id=uuid4(),
        teacher_id=override_user,
        question_type="text",
        problem="P",
        mark_out_of=5,
        penalty=0,
        is_active=True,
    )

    res = client.post(
        "/v1/tests/create",
        json={
            "name": "Test",
            "question_ids": [str(question_id)],
        },
    )

    assert res.status_code == 201
    body = res.json()
    assert body["name"] == "Test"
    assert patch_daos["added_questions"] == [question_id]


def test_update_test_empty_payload(client: TestClient, patch_session_maker):
    res = client.patch(f"/v1/tests/{uuid4()}", json={})

    assert res.status_code == 400
    assert res.json()["detail"] == "No updatable fields provided"


def test_delete_test_success(client: TestClient, patch_session_maker, patch_daos):
    test_id = uuid4()
    patch_daos["test_by_id"] = SimpleNamespace(id=test_id, name="DeleteMe")

    res = client.delete(f"/v1/tests/{test_id}")

    assert res.status_code == 200
    body = res.json()
    assert body["id"] == str(test_id)


def test_list_test_questions(client: TestClient, patch_session_maker, patch_daos):
    test_id = uuid4()
    patch_daos["test_by_id"] = SimpleNamespace(id=test_id)
    question_id = uuid4()
    patch_daos["test_questions"] = [SimpleNamespace(question_id=question_id)]
    patch_daos["question"] = SimpleNamespace(
        id=question_id,
        text="Q",
        answer={"correct": "A"},
        category_id=uuid4(),
        teacher_id=uuid4(),
        question_type="text",
        problem="P",
        mark_out_of=5,
        penalty=0,
        is_active=True,
    )

    res = client.get(f"/v1/tests/{test_id}/question/list")

    assert res.status_code == 200
    body = res.json()
    assert len(body) == 1
    assert body[0]["id"] == str(question_id)


def test_create_test_question(client: TestClient, patch_session_maker, patch_daos, override_user):
    test_id = uuid4()
    patch_daos["test_by_id"] = SimpleNamespace(id=test_id)

    res = client.post(
        f"/v1/tests/{test_id}/question/create",
        json={
            "text": "Q",
            "answer": {"correct": "A"},
            "category_id": str(uuid4()),
            "question_type": "text",
            "problem": "P",
            "mark_out_of": 5,
            "penalty": 0,
            "is_active": True,
        },
    )

    assert res.status_code == 200
    body = res.json()
    assert body["teacher_id"] == str(override_user)


def test_update_test_question(client: TestClient, patch_session_maker, patch_daos, override_user):
    test_id = uuid4()
    question_id = uuid4()
    patch_daos["test_question"] = SimpleNamespace(test_id=test_id, question_id=question_id)
    patch_daos["question"] = SimpleNamespace(
        id=question_id,
        text="Old",
        answer={"correct": "A"},
        category_id=uuid4(),
        teacher_id=override_user,
        question_type="text",
        problem="P",
        mark_out_of=5,
        penalty=0,
        is_active=True,
    )

    res = client.patch(f"/v1/tests/{test_id}/question/{question_id}", json={"text": "New"})

    assert res.status_code == 200
    body = res.json()
    assert body["text"] == "New"


def test_delete_test_question(client: TestClient, patch_session_maker, patch_daos, override_user):
    test_id = uuid4()
    question_id = uuid4()
    patch_daos["test_question"] = SimpleNamespace(test_id=test_id, question_id=question_id)
    patch_daos["question"] = SimpleNamespace(
        id=question_id,
        text="Del",
        answer={"correct": "A"},
        category_id=uuid4(),
        teacher_id=override_user,
        question_type="text",
        problem="P",
        mark_out_of=5,
        penalty=0,
        is_active=True,
    )

    res = client.delete(f"/v1/tests/{test_id}/question/{question_id}")

    assert res.status_code == 200
    body = res.json()
    assert body["id"] == str(question_id)
    assert patch_daos["removed_question_id"] == question_id
