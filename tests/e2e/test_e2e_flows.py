import os
import subprocess
from pathlib import Path
from uuid import uuid4

import httpx
import pytest


def _auth_headers(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


def _dump_compose_logs(label: str) -> None:
    if os.getenv("E2E_DUMP_LOGS") != "1":
        return
    project_root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        ["docker", "compose", "logs", "--no-color", "server"],
        cwd=project_root,
        capture_output=True,
        text=True,
    )
    header = f"\n----- docker compose logs ({label}) -----\n"
    print(header + result.stdout + result.stderr)


def _assert_status(response: httpx.Response, expected: int) -> None:
    if response.status_code != expected:
        _dump_compose_logs(f"{response.request.method} {response.request.url}")
    assert response.status_code == expected, response.text


def _create_category(client: httpx.Client, name: str) -> dict:
    response = client.post("/v1/categories", json={"name": name})
    _assert_status(response, 201)
    return response.json()


def _create_question(client: httpx.Client, token: str, category_id: str, text: str) -> dict:
    payload = {
        "text": text,
        "answer": {"value": "4"},
        "question_type": "single",
        "problem": "2 + 2",
        "mark_out_of": 1,
        "penalty": 0,
        "is_active": True,
        "category_id": category_id,
    }
    response = client.post("/v1/questions", json=payload, headers=_auth_headers(token))
    _assert_status(response, 201)
    return response.json()


def _create_test(client: httpx.Client, token: str, name: str, question_ids: list[str]) -> dict:
    payload = {
        "name": name,
        "question_ids": question_ids,
        "number_of_required_questions": len(question_ids),
    }
    response = client.post("/v1/tests/create", json=payload, headers=_auth_headers(token))
    _assert_status(response, 201)
    return response.json()


@pytest.mark.e2e
def test_auth_flow(http_client: httpx.Client, admin_credentials: dict[str, str]):
    token = admin_credentials["access_token"]
    headers = _auth_headers(token)

    me_resp = http_client.get("/v1/auth/users/me", headers=headers)
    _assert_status(me_resp, 200)
    me_data = me_resp.json()
    assert me_data["email"] == admin_credentials["email"]

    logout_resp = http_client.post(
        "/v1/auth/logout",
        json={"refresh_token": admin_credentials["refresh_token"]},
    )
    _assert_status(logout_resp, 204)


@pytest.mark.e2e
def test_question_crud_flow(http_client: httpx.Client, admin_credentials: dict[str, str]):
    token = admin_credentials["access_token"]
    category = _create_category(http_client, f"e2e-cat-{uuid4()}")
    question = _create_question(
        http_client,
        token,
        category_id=category["id"],
        text="What is 2 + 2?",
    )

    list_resp = http_client.get("/v1/questions", headers=_auth_headers(token))
    _assert_status(list_resp, 200)
    ids = {item["id"] for item in list_resp.json()}
    assert question["id"] in ids

    get_resp = http_client.get(f"/v1/questions/{question['id']}", headers=_auth_headers(token))
    _assert_status(get_resp, 200)
    assert get_resp.json()["id"] == question["id"]

    update_resp = http_client.patch(
        f"/v1/questions/{question['id']}",
        json={"text": "Updated question text"},
        headers=_auth_headers(token),
    )
    _assert_status(update_resp, 200)
    assert update_resp.json()["text"] == "Updated question text"

    delete_resp = http_client.delete(
        f"/v1/questions/{question['id']}",
        headers=_auth_headers(token),
    )
    _assert_status(delete_resp, 200)

    http_client.delete(f"/v1/categories/{category['id']}")


@pytest.mark.e2e
def test_tests_crud_flow(http_client: httpx.Client, admin_credentials: dict[str, str]):
    token = admin_credentials["access_token"]
    category = _create_category(http_client, f"e2e-test-cat-{uuid4()}")
    question = _create_question(
        http_client,
        token,
        category_id=category["id"],
        text="What is 3 + 3?",
    )
    test_obj = _create_test(
        http_client,
        token,
        name=f"e2e-test-{uuid4()}",
        question_ids=[question["id"]],
    )

    list_resp = http_client.get("/v1/tests")
    _assert_status(list_resp, 200)
    ids = {item["id"] for item in list_resp.json()}
    assert test_obj["id"] in ids

    get_resp = http_client.get(f"/v1/tests/{test_obj['id']}")
    _assert_status(get_resp, 200)
    assert get_resp.json()["id"] == test_obj["id"]

    update_resp = http_client.patch(
        f"/v1/tests/{test_obj['id']}",
        json={"name": "Updated test name"},
    )
    _assert_status(update_resp, 200)
    assert update_resp.json()["name"] == "Updated test name"

    delete_resp = http_client.delete(f"/v1/tests/{test_obj['id']}")
    _assert_status(delete_resp, 200)

    http_client.delete(f"/v1/questions/{question['id']}", headers=_auth_headers(token))
    http_client.delete(f"/v1/categories/{category['id']}")


@pytest.mark.e2e
def test_session_flow(http_client: httpx.Client, admin_credentials: dict[str, str]):
    token = admin_credentials["access_token"]
    headers = _auth_headers(token)
    category = _create_category(http_client, f"e2e-session-cat-{uuid4()}")
    question = _create_question(
        http_client,
        token,
        category_id=category["id"],
        text="What is 4 + 4?",
    )
    test_obj = _create_test(
        http_client,
        token,
        name=f"e2e-session-test-{uuid4()}",
        question_ids=[question["id"]],
    )

    sid = None
    try:
        start_resp = http_client.post(f"/v1/tests/{test_obj['id']}/start", headers=headers)
        _assert_status(start_resp, 201)
        session = start_resp.json()
        sid = session["sid"]

        list_resp = http_client.get("/v1/tests/session/list", headers=headers)
        _assert_status(list_resp, 200)
        sids = {item["sid"] for item in list_resp.json()}
        assert sid in sids

        get_resp = http_client.get(f"/v1/tests/session/{sid}", headers=headers)
        _assert_status(get_resp, 200)
        assert get_resp.json()["test_id"] == test_obj["id"]

        questions_resp = http_client.get(f"/v1/tests/session/{sid}/question/list", headers=headers)
        _assert_status(questions_resp, 200)
        question_list = questions_resp.json()
        assert question_list

        question_resp = http_client.get(
            f"/v1/tests/session/{sid}/question/{question['id']}",
            headers=headers,
        )
        _assert_status(question_resp, 200)
        assert question_resp.json()["index"] == 0

        answer_resp = http_client.post(
            f"/v1/tests/session/{sid}/question/{question['id']}/answer",
            json={"answer": "8"},
            headers=headers,
        )
        _assert_status(answer_resp, 200)
    finally:
        if sid:
            http_client.delete(f"/v1/tests/session/{sid}", headers=headers)
        http_client.delete(f"/v1/tests/{test_obj['id']}")
        http_client.delete(f"/v1/questions/{question['id']}", headers=headers)
        http_client.delete(f"/v1/categories/{category['id']}")
