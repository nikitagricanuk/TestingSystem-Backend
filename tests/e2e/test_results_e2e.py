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
def test_results_for_active_session(
    http_client: httpx.Client,
    admin_credentials: dict[str, str],
):
    token = admin_credentials["access_token"]
    category = create_category(http_client, f"e2e-result-cat-{uuid4()}")
    question = create_question(http_client, token, category["id"], "Result question")
    test_obj = create_test(http_client, token, f"e2e-result-test-{uuid4()}", [question["id"]])
    sid = None
    try:
        start_resp = http_client.post(f"/v1/tests/{test_obj['id']}/start", headers=auth_headers(token))
        assert_status(start_resp, 201)
        sid = start_resp.json()["sid"]

        me_resp = http_client.get("/v1/auth/users/me", headers=auth_headers(token))
        assert_status(me_resp, 200)
        user_id = me_resp.json()["id"]

        result_resp = http_client.get(f"/v1/tests/result/{sid}", headers=auth_headers(token))
        assert_status(result_resp, 200)
        result_data = result_resp.json()
        assert result_data["test_id"] == test_obj["id"]
        assert result_data["user_id"] == user_id
    finally:
        if sid:
            http_client.delete(f"/v1/tests/session/{sid}", headers=auth_headers(token))
        http_client.delete(f"/v1/tests/{test_obj['id']}")
        http_client.delete(f"/v1/questions/{question['id']}", headers=auth_headers(token))
        http_client.delete(f"/v1/categories/{category['id']}")


@pytest.mark.e2e
def test_leaderboard_returns_list(
    http_client: httpx.Client,
    admin_credentials: dict[str, str],
):
    resp = http_client.get("/v1/tests/leaderboard", headers=auth_headers(admin_credentials["access_token"]))
    assert_status(resp, 200)
    assert isinstance(resp.json(), list)
