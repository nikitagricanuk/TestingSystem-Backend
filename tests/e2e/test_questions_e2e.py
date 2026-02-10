from uuid import uuid4

import httpx
import pytest

from tests.e2e.helpers import assert_status, auth_headers, create_category, create_question


@pytest.mark.e2e
def test_question_crud(http_client: httpx.Client, admin_credentials: dict[str, str]):
    token = admin_credentials["access_token"]
    category = create_category(http_client, f"e2e-cat-{uuid4()}")
    question = create_question(
        http_client,
        token,
        category_id=category["id"],
        text="What is 2 + 2?",
    )

    list_resp = http_client.get("/v1/questions", headers=auth_headers(token))
    assert_status(list_resp, 200)
    ids = {item["id"] for item in list_resp.json()}
    assert question["id"] in ids

    get_resp = http_client.get(f"/v1/questions/{question['id']}", headers=auth_headers(token))
    assert_status(get_resp, 200)
    assert get_resp.json()["id"] == question["id"]

    update_resp = http_client.patch(
        f"/v1/questions/{question['id']}",
        json={"text": "Updated question text"},
        headers=auth_headers(token),
    )
    assert_status(update_resp, 200)
    assert update_resp.json()["text"] == "Updated question text"

    delete_resp = http_client.delete(
        f"/v1/questions/{question['id']}",
        headers=auth_headers(token),
    )
    assert_status(delete_resp, 200)

    http_client.delete(f"/v1/categories/{category['id']}")


@pytest.mark.e2e
def test_questions_filter_descendants(
    http_client: httpx.Client,
    admin_credentials: dict[str, str],
):
    token = admin_credentials["access_token"]
    parent = create_category(http_client, f"e2e-parent-{uuid4()}")
    child = create_category(http_client, f"e2e-child-{uuid4()}", parent_id=parent["id"])
    parent_question = create_question(http_client, token, parent["id"], "Parent question")
    child_question = create_question(http_client, token, child["id"], "Child question")

    params = {"category_path": [parent["name"]], "include_descendants": True}
    list_resp = http_client.get("/v1/questions", headers=auth_headers(token), params=params)
    assert_status(list_resp, 200)
    ids = {item["id"] for item in list_resp.json()}
    assert parent_question["id"] in ids
    assert child_question["id"] in ids

    list_resp = http_client.get(
        "/v1/questions",
        headers=auth_headers(token),
        params={"category_path": [parent["name"]], "include_descendants": False},
    )
    assert_status(list_resp, 200)
    ids = {item["id"] for item in list_resp.json()}
    assert parent_question["id"] in ids
    assert child_question["id"] not in ids

    http_client.delete(f"/v1/questions/{parent_question['id']}", headers=auth_headers(token))
    http_client.delete(f"/v1/questions/{child_question['id']}", headers=auth_headers(token))
    http_client.delete(f"/v1/categories/{child['id']}")
    http_client.delete(f"/v1/categories/{parent['id']}")


@pytest.mark.e2e
def test_questions_filter_active_and_mark(
    http_client: httpx.Client,
    admin_credentials: dict[str, str],
):
    token = admin_credentials["access_token"]
    category = create_category(http_client, f"e2e-filter-cat-{uuid4()}")
    active_question = create_question(
        http_client,
        token,
        category_id=category["id"],
        text="Active question",
        mark_out_of=1,
        is_active=True,
    )
    inactive_question = create_question(
        http_client,
        token,
        category_id=category["id"],
        text="Inactive question",
        mark_out_of=2,
        is_active=False,
    )

    params = {"mark_out_of": 1, "is_active": True, "category_id": category["id"]}
    list_resp = http_client.get("/v1/questions", headers=auth_headers(token), params=params)
    assert_status(list_resp, 200)
    ids = {item["id"] for item in list_resp.json()}
    assert active_question["id"] in ids
    assert inactive_question["id"] not in ids

    http_client.delete(f"/v1/questions/{active_question['id']}", headers=auth_headers(token))
    http_client.delete(f"/v1/questions/{inactive_question['id']}", headers=auth_headers(token))
    http_client.delete(f"/v1/categories/{category['id']}")


@pytest.mark.e2e
def test_create_question_requires_category(
    http_client: httpx.Client,
    admin_credentials: dict[str, str],
):
    payload = {
        "text": "Missing category",
        "answer": {"value": "4"},
        "question_type": "single",
        "problem": "2 + 2",
        "mark_out_of": 1,
        "penalty": 0,
        "is_active": True,
    }
    resp = http_client.post("/v1/questions", json=payload, headers=auth_headers(admin_credentials["access_token"]))
    assert_status(resp, 400)
