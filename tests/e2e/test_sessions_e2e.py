from uuid import uuid4

import httpx
import pytest

from tests.e2e.helpers import (
    assert_status,
    auth_headers,
    create_category,
    create_question,
    create_questions,
    create_test,
)


@pytest.mark.e2e
def test_session_flow_basic(http_client: httpx.Client, admin_credentials: dict[str, str]):
    token = admin_credentials["access_token"]
    headers = auth_headers(token)
    category = create_category(http_client, f"e2e-session-cat-{uuid4()}")
    question = create_question(
        http_client,
        token,
        category_id=category["id"],
        text="What is 4 + 4?",
    )
    test_obj = create_test(
        http_client,
        token,
        name=f"e2e-session-test-{uuid4()}",
        question_ids=[question["id"]],
    )

    sid = None
    try:
        start_resp = http_client.post(f"/v1/tests/{test_obj['id']}/start", headers=headers)
        assert_status(start_resp, 201)
        session = start_resp.json()
        sid = session["sid"]

        list_resp = http_client.get("/v1/tests/session/list", headers=headers)
        assert_status(list_resp, 200)
        sids = {item["sid"] for item in list_resp.json()}
        assert sid in sids

        get_resp = http_client.get(f"/v1/tests/session/{sid}", headers=headers)
        assert_status(get_resp, 200)
        assert get_resp.json()["test_id"] == test_obj["id"]

        questions_resp = http_client.get(f"/v1/tests/session/{sid}/question/list", headers=headers)
        assert_status(questions_resp, 200)
        question_list = questions_resp.json()
        assert question_list

        question_resp = http_client.get(
            f"/v1/tests/session/{sid}/question/{question['id']}",
            headers=headers,
        )
        assert_status(question_resp, 200)
        assert question_resp.json()["index"] == 0

        answer_resp = http_client.post(
            f"/v1/tests/session/{sid}/question/{question['id']}/answer",
            json={"answer": "8"},
            headers=headers,
        )
        assert_status(answer_resp, 200)
    finally:
        if sid:
            http_client.delete(f"/v1/tests/session/{sid}", headers=headers)
        http_client.delete(f"/v1/tests/{test_obj['id']}")
        http_client.delete(f"/v1/questions/{question['id']}", headers=headers)
        http_client.delete(f"/v1/categories/{category['id']}")


@pytest.mark.e2e
def test_session_start_invalid_test(
    http_client: httpx.Client,
    admin_credentials: dict[str, str],
):
    headers = auth_headers(admin_credentials["access_token"])
    resp = http_client.post(f"/v1/tests/{uuid4()}/start", headers=headers)
    assert_status(resp, 404)


@pytest.mark.e2e
def test_session_start_requires_questions(
    http_client: httpx.Client,
    admin_credentials: dict[str, str],
):
    token = admin_credentials["access_token"]
    test_obj = create_test(http_client, token, f"e2e-empty-test-{uuid4()}", [], number_required=0)
    try:
        resp = http_client.post(f"/v1/tests/{test_obj['id']}/start", headers=auth_headers(token))
        assert_status(resp, 400)
    finally:
        http_client.delete(f"/v1/tests/{test_obj['id']}")


@pytest.mark.e2e
def test_session_question_list_and_get(
    http_client: httpx.Client,
    admin_credentials: dict[str, str],
):
    token = admin_credentials["access_token"]
    category = create_category(http_client, f"e2e-session-cat-{uuid4()}")
    questions = create_questions(http_client, token, category["id"], 2, "Session question")
    test_obj = create_test(
        http_client,
        token,
        f"e2e-session-test-{uuid4()}",
        [q["id"] for q in questions],
    )
    sid = None
    try:
        start_resp = http_client.post(f"/v1/tests/{test_obj['id']}/start", headers=auth_headers(token))
        assert_status(start_resp, 201)
        sid = start_resp.json()["sid"]

        list_resp = http_client.get(f"/v1/tests/session/{sid}/question/list", headers=auth_headers(token))
        assert_status(list_resp, 200)
        items = list_resp.json()
        assert len(items) == 2
        assert {item["status"] for item in items} == {"unanswered"}

        get_resp = http_client.get(
            f"/v1/tests/session/{sid}/question/{questions[0]['id']}",
            headers=auth_headers(token),
        )
        assert_status(get_resp, 200)
        assert get_resp.json()["index"] == 0
    finally:
        if sid:
            http_client.delete(f"/v1/tests/session/{sid}", headers=auth_headers(token))
        http_client.delete(f"/v1/tests/{test_obj['id']}")
        for question in questions:
            http_client.delete(f"/v1/questions/{question['id']}", headers=auth_headers(token))
        http_client.delete(f"/v1/categories/{category['id']}")


@pytest.mark.e2e
def test_session_navigation_next_prev(
    http_client: httpx.Client,
    admin_credentials: dict[str, str],
):
    token = admin_credentials["access_token"]
    category = create_category(http_client, f"e2e-nav-cat-{uuid4()}")
    questions = create_questions(http_client, token, category["id"], 2, "Nav question")
    test_obj = create_test(
        http_client,
        token,
        f"e2e-nav-test-{uuid4()}",
        [q["id"] for q in questions],
    )
    sid = None
    try:
        start_resp = http_client.post(f"/v1/tests/{test_obj['id']}/start", headers=auth_headers(token))
        assert_status(start_resp, 201)
        sid = start_resp.json()["sid"]

        next_resp = http_client.get(f"/v1/tests/session/{sid}/question/next", headers=auth_headers(token))
        assert_status(next_resp, 200)
        assert next_resp.json()["index"] == 1

        prev_resp = http_client.get(f"/v1/tests/session/{sid}/question/prev", headers=auth_headers(token))
        assert_status(prev_resp, 200)
        assert prev_resp.json()["index"] == 0
    finally:
        if sid:
            http_client.delete(f"/v1/tests/session/{sid}", headers=auth_headers(token))
        http_client.delete(f"/v1/tests/{test_obj['id']}")
        for question in questions:
            http_client.delete(f"/v1/questions/{question['id']}", headers=auth_headers(token))
        http_client.delete(f"/v1/categories/{category['id']}")


@pytest.mark.e2e
def test_session_prev_at_start(
    http_client: httpx.Client,
    admin_credentials: dict[str, str],
):
    token = admin_credentials["access_token"]
    category = create_category(http_client, f"e2e-prev-cat-{uuid4()}")
    question = create_question(http_client, token, category["id"], "Prev question")
    test_obj = create_test(http_client, token, f"e2e-prev-test-{uuid4()}", [question["id"]])
    sid = None
    try:
        start_resp = http_client.post(f"/v1/tests/{test_obj['id']}/start", headers=auth_headers(token))
        assert_status(start_resp, 201)
        sid = start_resp.json()["sid"]

        prev_resp = http_client.get(f"/v1/tests/session/{sid}/question/prev", headers=auth_headers(token))
        assert_status(prev_resp, 404)
    finally:
        if sid:
            http_client.delete(f"/v1/tests/session/{sid}", headers=auth_headers(token))
        http_client.delete(f"/v1/tests/{test_obj['id']}")
        http_client.delete(f"/v1/questions/{question['id']}", headers=auth_headers(token))
        http_client.delete(f"/v1/categories/{category['id']}")


@pytest.mark.e2e
def test_session_next_at_end(
    http_client: httpx.Client,
    admin_credentials: dict[str, str],
):
    token = admin_credentials["access_token"]
    category = create_category(http_client, f"e2e-next-cat-{uuid4()}")
    question = create_question(http_client, token, category["id"], "Next question")
    test_obj = create_test(http_client, token, f"e2e-next-test-{uuid4()}", [question["id"]])
    sid = None
    try:
        start_resp = http_client.post(f"/v1/tests/{test_obj['id']}/start", headers=auth_headers(token))
        assert_status(start_resp, 201)
        sid = start_resp.json()["sid"]

        next_resp = http_client.get(f"/v1/tests/session/{sid}/question/next", headers=auth_headers(token))
        assert_status(next_resp, 404)
    finally:
        if sid:
            http_client.delete(f"/v1/tests/session/{sid}", headers=auth_headers(token))
        http_client.delete(f"/v1/tests/{test_obj['id']}")
        http_client.delete(f"/v1/questions/{question['id']}", headers=auth_headers(token))
        http_client.delete(f"/v1/categories/{category['id']}")


@pytest.mark.e2e
def test_session_answer_updates_counts(
    http_client: httpx.Client,
    admin_credentials: dict[str, str],
):
    token = admin_credentials["access_token"]
    category = create_category(http_client, f"e2e-answer-cat-{uuid4()}")
    questions = create_questions(http_client, token, category["id"], 2, "Answer question")
    test_obj = create_test(
        http_client,
        token,
        f"e2e-answer-test-{uuid4()}",
        [q["id"] for q in questions],
    )
    sid = None
    try:
        start_resp = http_client.post(f"/v1/tests/{test_obj['id']}/start", headers=auth_headers(token))
        assert_status(start_resp, 201)
        sid = start_resp.json()["sid"]

        answer_resp = http_client.post(
            f"/v1/tests/session/{sid}/question/{questions[0]['id']}/answer",
            json={"answer": "1"},
            headers=auth_headers(token),
        )
        assert_status(answer_resp, 200)

        session_resp = http_client.get(f"/v1/tests/session/{sid}", headers=auth_headers(token))
        assert_status(session_resp, 200)
        session_data = session_resp.json()
        assert session_data["questions_answered"] == 1
        assert session_data["questions_remaining"] == 1
        assert session_data["current_question_index"] == 1
    finally:
        if sid:
            http_client.delete(f"/v1/tests/session/{sid}", headers=auth_headers(token))
        http_client.delete(f"/v1/tests/{test_obj['id']}")
        for question in questions:
            http_client.delete(f"/v1/questions/{question['id']}", headers=auth_headers(token))
        http_client.delete(f"/v1/categories/{category['id']}")


@pytest.mark.e2e
def test_session_answer_idempotent(
    http_client: httpx.Client,
    admin_credentials: dict[str, str],
):
    token = admin_credentials["access_token"]
    category = create_category(http_client, f"e2e-repeat-cat-{uuid4()}")
    question = create_question(http_client, token, category["id"], "Repeat question")
    test_obj = create_test(http_client, token, f"e2e-repeat-test-{uuid4()}", [question["id"]])
    sid = None
    try:
        start_resp = http_client.post(f"/v1/tests/{test_obj['id']}/start", headers=auth_headers(token))
        assert_status(start_resp, 201)
        sid = start_resp.json()["sid"]

        for _ in range(2):
            answer_resp = http_client.post(
                f"/v1/tests/session/{sid}/question/{question['id']}/answer",
                json={"answer": "1"},
                headers=auth_headers(token),
            )
            assert_status(answer_resp, 200)

        session_resp = http_client.get(f"/v1/tests/session/{sid}", headers=auth_headers(token))
        assert_status(session_resp, 200)
        session_data = session_resp.json()
        assert session_data["questions_answered"] == 1
        assert session_data["questions_remaining"] == 0
    finally:
        if sid:
            http_client.delete(f"/v1/tests/session/{sid}", headers=auth_headers(token))
        http_client.delete(f"/v1/tests/{test_obj['id']}")
        http_client.delete(f"/v1/questions/{question['id']}", headers=auth_headers(token))
        http_client.delete(f"/v1/categories/{category['id']}")


@pytest.mark.e2e
def test_session_question_status_after_answer(
    http_client: httpx.Client,
    admin_credentials: dict[str, str],
):
    token = admin_credentials["access_token"]
    category = create_category(http_client, f"e2e-status-cat-{uuid4()}")
    questions = create_questions(http_client, token, category["id"], 2, "Status question")
    test_obj = create_test(
        http_client,
        token,
        f"e2e-status-test-{uuid4()}",
        [q["id"] for q in questions],
    )
    sid = None
    try:
        start_resp = http_client.post(f"/v1/tests/{test_obj['id']}/start", headers=auth_headers(token))
        assert_status(start_resp, 201)
        sid = start_resp.json()["sid"]

        answer_resp = http_client.post(
            f"/v1/tests/session/{sid}/question/{questions[0]['id']}/answer",
            json={"answer": "1"},
            headers=auth_headers(token),
        )
        assert_status(answer_resp, 200)

        list_resp = http_client.get(f"/v1/tests/session/{sid}/question/list", headers=auth_headers(token))
        assert_status(list_resp, 200)
        status_map = {item["index"]: item["status"] for item in list_resp.json()}
        assert status_map[0] == "answered"
        assert status_map[1] == "unanswered"
    finally:
        if sid:
            http_client.delete(f"/v1/tests/session/{sid}", headers=auth_headers(token))
        http_client.delete(f"/v1/tests/{test_obj['id']}")
        for question in questions:
            http_client.delete(f"/v1/questions/{question['id']}", headers=auth_headers(token))
        http_client.delete(f"/v1/categories/{category['id']}")
