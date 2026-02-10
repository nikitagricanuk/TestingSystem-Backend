from datetime import datetime, timezone
from uuid import uuid4

import httpx
import pytest

from tests.e2e.helpers import (
    assert_status,
    auth_headers,
    create_category,
    create_question,
    create_test,
)


@pytest.mark.e2e
def test_tests_crud(http_client: httpx.Client, admin_credentials: dict[str, str]):
    token = admin_credentials["access_token"]
    category = create_category(http_client, f"e2e-test-cat-{uuid4()}")
    question = create_question(
        http_client,
        token,
        category_id=category["id"],
        text="What is 3 + 3?",
    )
    test_obj = create_test(
        http_client,
        token,
        name=f"e2e-test-{uuid4()}",
        question_ids=[question["id"]],
    )

    list_resp = http_client.get("/v1/tests")
    assert_status(list_resp, 200)
    ids = {item["id"] for item in list_resp.json()}
    assert test_obj["id"] in ids

    get_resp = http_client.get(f"/v1/tests/{test_obj['id']}")
    assert_status(get_resp, 200)
    assert get_resp.json()["id"] == test_obj["id"]

    update_resp = http_client.patch(
        f"/v1/tests/{test_obj['id']}",
        json={"name": "Updated test name"},
    )
    assert_status(update_resp, 200)
    assert update_resp.json()["name"] == "Updated test name"

    delete_resp = http_client.delete(f"/v1/tests/{test_obj['id']}")
    assert_status(delete_resp, 200)

    http_client.delete(f"/v1/questions/{question['id']}", headers=auth_headers(token))
    http_client.delete(f"/v1/categories/{category['id']}")


@pytest.mark.e2e
def test_test_question_crud(
    http_client: httpx.Client,
    admin_credentials: dict[str, str],
):
    token = admin_credentials["access_token"]
    category = create_category(http_client, f"e2e-test-q-cat-{uuid4()}")
    test_obj = create_test(http_client, token, f"e2e-test-{uuid4()}", [], number_required=0)
    question = None
    try:
        create_resp = http_client.post(
            f"/v1/tests/{test_obj['id']}/question/create",
            json={
                "text": "Test question",
                "answer": {"value": "4"},
                "question_type": "single",
                "problem": "2 + 2",
                "mark_out_of": 1,
                "penalty": 0,
                "is_active": True,
                "category_id": category["id"],
            },
            headers=auth_headers(token),
        )
        assert_status(create_resp, 200)
        question = create_resp.json()

        list_resp = http_client.get(f"/v1/tests/{test_obj['id']}/question/list")
        assert_status(list_resp, 200)
        ids = {item["id"] for item in list_resp.json()}
        assert question["id"] in ids

        get_resp = http_client.get(f"/v1/tests/{test_obj['id']}/question/{question['id']}")
        assert_status(get_resp, 200)

        update_resp = http_client.patch(
            f"/v1/tests/{test_obj['id']}/question/{question['id']}",
            json={"text": "Updated text"},
            headers=auth_headers(token),
        )
        assert_status(update_resp, 200)
        assert update_resp.json()["text"] == "Updated text"

        delete_resp = http_client.delete(
            f"/v1/tests/{test_obj['id']}/question/{question['id']}",
            headers=auth_headers(token),
        )
        assert_status(delete_resp, 200)

        list_resp = http_client.get(f"/v1/tests/{test_obj['id']}/question/list")
        assert_status(list_resp, 200)
        assert list_resp.json() == []
    finally:
        http_client.delete(f"/v1/tests/{test_obj['id']}")
        if question:
            http_client.delete(f"/v1/questions/{question['id']}", headers=auth_headers(token))
        http_client.delete(f"/v1/categories/{category['id']}")


@pytest.mark.e2e
def test_test_question_not_found(
    http_client: httpx.Client,
    admin_credentials: dict[str, str],
):
    token = admin_credentials["access_token"]
    category = create_category(http_client, f"e2e-test-q-miss-cat-{uuid4()}")
    question = create_question(http_client, token, category["id"], "Question")
    test_obj = create_test(http_client, token, f"e2e-test-{uuid4()}", [question["id"]])
    try:
        resp = http_client.get(f"/v1/tests/{test_obj['id']}/question/{uuid4()}")
        assert_status(resp, 404)
    finally:
        http_client.delete(f"/v1/tests/{test_obj['id']}")
        http_client.delete(f"/v1/questions/{question['id']}", headers=auth_headers(token))
        http_client.delete(f"/v1/categories/{category['id']}")


@pytest.mark.e2e
def test_create_test_rejects_duplicates(
    http_client: httpx.Client,
    admin_credentials: dict[str, str],
):
    token = admin_credentials["access_token"]
    category = create_category(http_client, f"e2e-dup-cat-{uuid4()}")
    question = create_question(http_client, token, category["id"], "Duplicate question")
    payload = {
        "name": f"e2e-test-{uuid4()}",
        "question_ids": [question["id"], question["id"]],
        "number_of_required_questions": 2,
    }
    resp = http_client.post("/v1/tests/create", json=payload, headers=auth_headers(token))
    assert_status(resp, 400)

    http_client.delete(f"/v1/questions/{question['id']}", headers=auth_headers(token))
    http_client.delete(f"/v1/categories/{category['id']}")


@pytest.mark.e2e
def test_update_test_requires_fields(
    http_client: httpx.Client,
    admin_credentials: dict[str, str],
):
    token = admin_credentials["access_token"]
    category = create_category(http_client, f"e2e-update-test-cat-{uuid4()}")
    question = create_question(http_client, token, category["id"], "Question")
    test_obj = create_test(http_client, token, f"e2e-test-{uuid4()}", [question["id"]])
    try:
        resp = http_client.patch(f"/v1/tests/{test_obj['id']}", json={})
        assert_status(resp, 400)
    finally:
        http_client.delete(f"/v1/tests/{test_obj['id']}")
        http_client.delete(f"/v1/questions/{question['id']}", headers=auth_headers(token))
        http_client.delete(f"/v1/categories/{category['id']}")


@pytest.mark.e2e
def test_update_test_rejects_invalid_dates(
    http_client: httpx.Client,
    admin_credentials: dict[str, str],
):
    token = admin_credentials["access_token"]
    category = create_category(http_client, f"e2e-date-test-cat-{uuid4()}")
    question = create_question(http_client, token, category["id"], "Question")
    test_obj = create_test(http_client, token, f"e2e-test-{uuid4()}", [question["id"]])
    try:
        payload = {
            "start_date": datetime(2030, 1, 2, tzinfo=timezone.utc).isoformat(),
            "end_date": datetime(2030, 1, 1, tzinfo=timezone.utc).isoformat(),
        }
        resp = http_client.patch(f"/v1/tests/{test_obj['id']}", json=payload)
        assert_status(resp, 400)
    finally:
        http_client.delete(f"/v1/tests/{test_obj['id']}")
        http_client.delete(f"/v1/questions/{question['id']}", headers=auth_headers(token))
        http_client.delete(f"/v1/categories/{category['id']}")


@pytest.mark.e2e
def test_update_test_rejects_required_exceeds_total(
    http_client: httpx.Client,
    admin_credentials: dict[str, str],
):
    token = admin_credentials["access_token"]
    category = create_category(http_client, f"e2e-required-test-cat-{uuid4()}")
    question = create_question(http_client, token, category["id"], "Question")
    test_obj = create_test(http_client, token, f"e2e-test-{uuid4()}", [question["id"]])
    try:
        resp = http_client.patch(
            f"/v1/tests/{test_obj['id']}",
            json={"number_of_required_questions": 2},
        )
        assert_status(resp, 400)
    finally:
        http_client.delete(f"/v1/tests/{test_obj['id']}")
        http_client.delete(f"/v1/questions/{question['id']}", headers=auth_headers(token))
        http_client.delete(f"/v1/categories/{category['id']}")
