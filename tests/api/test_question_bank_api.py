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
    from app.routers import question_bank as qb_router

    app.include_router(qb_router.router, prefix="/v1")
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
    from app.routers import question_bank as qb_router

    monkeypatch.setattr(qb_router, "async_session_maker", lambda: DummySession())


@pytest.fixture()
def patch_daos(monkeypatch):
    from app.repositories.question_bank.question_dao import QuestionDAO, CategoryDAO

    state = {}

    async def fake_list(*, owner_id=None, offset=0, limit=100, session=None):
        return state.get("categories", [])[offset:offset + limit]

    async def fake_get(category_id: UUID, session=None):
        category = state.get("category")
        if category is None or category.id != category_id:
            from app.repositories.question_bank.exceptions import CategoryNotFound
            raise CategoryNotFound("not found")
        return category

    async def fake_create(name: str, owner_id=None, parent_id=None, session=None):
        category = SimpleNamespace(id=uuid4(), category=name, parent_id=parent_id, owner_id=owner_id)
        state["created_category"] = category
        return category

    async def fake_update(category_id: UUID, new_name=None, parent_id=None, session=None):
        category = state.get("created_category") or state.get("category")
        if category is None:
            from app.repositories.question_bank.exceptions import CategoryNotFound
            raise CategoryNotFound("not found")
        if new_name is not None:
            category.category = new_name
        category.parent_id = parent_id
        return category

    async def fake_delete(category_id: UUID, session=None):
        state["deleted_category_id"] = category_id
        return None

    async def fake_get_by_path(path, owner_id=None, session=None):
        category = state.get("category_by_path")
        if category is None:
            from app.repositories.question_bank.exceptions import CategoryNotFound
            raise CategoryNotFound("not found")
        return category

    async def fake_get_or_create_path(path, owner_id=None, session=None):
        category = state.get("category_by_path")
        if category is None:
            category = SimpleNamespace(id=uuid4(), category="path", parent_id=None, owner_id=owner_id)
        return category

    async def fake_question_get(question_id: UUID, session=None):
        question = state.get("question")
        if question is None or question.id != question_id:
            from app.repositories.question_bank.exceptions import QuestionNotFoundError
            raise QuestionNotFoundError("not found")
        return question

    async def fake_question_add(data: dict, session=None):
        question = SimpleNamespace(
            id=uuid4(),
            text=data["text"],
            answer=data["answer"],
            category_id=data["category_id"],
            teacher_id=data["teacher_id"],
            question_type=data["question_type"],
            problem=data["problem"],
            mark_out_of=data["mark_out_of"],
            penalty=data["penalty"],
            is_active=data.get("is_active", True),
        )
        state["created_question"] = question
        return question

    async def fake_question_update(question_id: UUID, data, session=None):
        question = state.get("question")
        if question is None:
            from app.repositories.question_bank.exceptions import QuestionNotFoundError
            raise QuestionNotFoundError("not found")
        for key, value in data.items():
            setattr(question, key, value)
        return question

    async def fake_question_delete(question_id: UUID, session=None):
        state["deleted_question_id"] = question_id
        return None

    async def fake_list_by_category(category_id: UUID, include_descendants: bool, session=None, teacher_id=None):
        return state.get("questions_by_category", [])

    async def fake_search(session=None, **filters):
        return state.get("questions", [])

    monkeypatch.setattr(CategoryDAO, "list", fake_list, raising=False)
    monkeypatch.setattr(CategoryDAO, "get", fake_get, raising=False)
    monkeypatch.setattr(CategoryDAO, "create", fake_create, raising=False)
    monkeypatch.setattr(CategoryDAO, "update", fake_update, raising=False)
    monkeypatch.setattr(CategoryDAO, "delete", fake_delete, raising=False)
    monkeypatch.setattr(CategoryDAO, "get_by_path", fake_get_by_path, raising=False)
    monkeypatch.setattr(CategoryDAO, "get_or_create_path", fake_get_or_create_path, raising=False)

    monkeypatch.setattr(QuestionDAO, "get", fake_question_get, raising=False)
    monkeypatch.setattr(QuestionDAO, "add_question", fake_question_add, raising=False)
    monkeypatch.setattr(QuestionDAO, "update", fake_question_update, raising=False)
    monkeypatch.setattr(QuestionDAO, "delete", fake_question_delete, raising=False)
    monkeypatch.setattr(QuestionDAO, "list_by_category", fake_list_by_category, raising=False)
    monkeypatch.setattr(QuestionDAO, "search", fake_search, raising=False)

    return state


def test_list_categories(client: TestClient, patch_session_maker, patch_daos, override_user):
    patch_daos["categories"] = [
        SimpleNamespace(id=uuid4(), category="Math", parent_id=None, owner_id=override_user),
        SimpleNamespace(id=uuid4(), category="Physics", parent_id=None, owner_id=override_user),
    ]

    res = client.get("/v1/categories")

    assert res.status_code == 200
    body = res.json()
    assert len(body) == 2
    assert body[0]["name"] == "Math"


def test_get_category_not_found(client: TestClient, patch_session_maker, patch_daos, override_user):
    res = client.get(f"/v1/categories/{uuid4()}")

    assert res.status_code == 404


def test_create_category_with_parent(client: TestClient, patch_session_maker, patch_daos, override_user):
    parent_id = uuid4()

    res = client.post("/v1/categories", json={"name": "Biology", "parent_id": str(parent_id)})

    assert res.status_code == 201
    body = res.json()
    assert body["name"] == "Biology"
    assert body["parent_id"] == str(parent_id)


def test_update_category_empty_payload(client: TestClient, patch_session_maker, override_user):
    res = client.patch(f"/v1/categories/{uuid4()}", json={})

    assert res.status_code == 400
    assert res.json()["detail"] == "No updatable fields provided"


def test_update_category_forbidden_for_other_owner(client: TestClient, patch_session_maker, patch_daos, override_user):
    category_id = uuid4()
    patch_daos["category"] = SimpleNamespace(id=category_id, category="History", parent_id=None, owner_id=uuid4())

    res = client.patch(f"/v1/categories/{category_id}", json={"name": "New name"})

    assert res.status_code == 403


def test_delete_category_returns_category(client: TestClient, patch_session_maker, patch_daos, override_user):
    category_id = uuid4()
    patch_daos["category"] = SimpleNamespace(id=category_id, category="History", parent_id=None, owner_id=override_user)

    res = client.delete(f"/v1/categories/{category_id}")

    assert res.status_code == 200
    body = res.json()
    assert body["id"] == str(category_id)
    assert patch_daos["deleted_category_id"] == category_id


def test_delete_category_forbidden_for_other_owner(client: TestClient, patch_session_maker, patch_daos, override_user):
    category_id = uuid4()
    patch_daos["category"] = SimpleNamespace(id=category_id, category="History", parent_id=None, owner_id=uuid4())

    res = client.delete(f"/v1/categories/{category_id}")

    assert res.status_code == 403


def test_list_questions_filters_by_category_path(client: TestClient, patch_session_maker, patch_daos, override_user):
    category = SimpleNamespace(id=uuid4(), category="Science", parent_id=None)
    patch_daos["category_by_path"] = category
    patch_daos["questions_by_category"] = [
        SimpleNamespace(
            id=uuid4(),
            text="Q1",
            answer={"correct": "A"},
            category_id=category.id,
            teacher_id=override_user,
            question_type="text",
            problem="P1",
            mark_out_of=5,
            penalty=0,
            is_active=True,
        )
    ]

    res = client.get("/v1/questions", params={"category_path": ["Science"], "include_descendants": "true"})

    assert res.status_code == 200
    body = res.json()
    assert len(body) == 1
    assert body[0]["text"] == "Q1"


def test_get_question_forbidden(client: TestClient, patch_session_maker, patch_daos, override_user):
    other_user_id = uuid4()
    question_id = uuid4()
    patch_daos["question"] = SimpleNamespace(
        id=question_id,
        text="Q1",
        answer={"correct": "A"},
        category_id=uuid4(),
        teacher_id=other_user_id,
        question_type="text",
        problem="P1",
        mark_out_of=5,
        penalty=0,
        is_active=True,
    )

    res = client.get(f"/v1/questions/{question_id}")

    assert res.status_code == 403


def test_create_question_with_category_path(client: TestClient, patch_session_maker, patch_daos, override_user):
    category = SimpleNamespace(id=uuid4(), category="Path", parent_id=None)
    patch_daos["category_by_path"] = category

    res = client.post(
        "/v1/questions",
        json={
            "text": "Q",
            "answer": {"correct": "A"},
            "category_path": ["Path"],
            "question_type": "text",
            "problem": "P",
            "mark_out_of": 5,
            "penalty": 0,
            "is_active": True,
        },
    )

    assert res.status_code == 201
    body = res.json()
    assert body["category_id"] == str(category.id)
    assert body["teacher_id"] == str(override_user)


def test_update_question_success(client: TestClient, patch_session_maker, patch_daos, override_user):
    question_id = uuid4()
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

    res = client.patch(f"/v1/questions/{question_id}", json={"text": "New"})

    assert res.status_code == 200
    body = res.json()
    assert body["text"] == "New"


def test_delete_question_success(client: TestClient, patch_session_maker, patch_daos, override_user):
    question_id = uuid4()
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

    res = client.delete(f"/v1/questions/{question_id}")

    assert res.status_code == 200
    body = res.json()
    assert body["id"] == str(question_id)
    assert patch_daos["deleted_question_id"] == question_id
