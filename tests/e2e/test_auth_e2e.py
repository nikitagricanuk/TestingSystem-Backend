from uuid import uuid4

import httpx
import pytest

from tests.e2e.helpers import assert_status, auth_headers, signup_student


@pytest.mark.e2e
def test_admin_me_logout(http_client: httpx.Client, admin_credentials: dict[str, str]):
    token = admin_credentials["access_token"]
    headers = auth_headers(token)

    me_resp = http_client.get("/v1/auth/users/me", headers=headers)
    assert_status(me_resp, 200)
    me_data = me_resp.json()
    assert me_data["email"] == admin_credentials["email"]

    logout_resp = http_client.post(
        "/v1/auth/logout",
        json={"refresh_token": admin_credentials["refresh_token"]},
    )
    assert_status(logout_resp, 204)


@pytest.mark.e2e
def test_student_signup_login_me(http_client: httpx.Client):
    email = f"e2e-student-{uuid4()}@example.com"
    password = "Password123!"
    user = signup_student(http_client, email, password)

    login_resp = http_client.post("/v1/auth/login", json={"email": email, "password": password})
    assert_status(login_resp, 200)
    tokens = login_resp.json()

    me_resp = http_client.get("/v1/auth/users/me", headers=auth_headers(tokens["access_token"]))
    assert_status(me_resp, 200)
    me_data = me_resp.json()
    assert me_data["email"] == email

    http_client.delete(f"/v1/auth/users/{user['id']}")


@pytest.mark.e2e
def test_login_rejects_bad_password(http_client: httpx.Client):
    email = f"e2e-student-{uuid4()}@example.com"
    password = "Password123!"
    user = signup_student(http_client, email, password)

    login_resp = http_client.post("/v1/auth/login", json={"email": email, "password": "WrongPassword1!"})
    assert_status(login_resp, 401)

    http_client.delete(f"/v1/auth/users/{user['id']}")


@pytest.mark.e2e
def test_update_me_requires_fields(
    http_client: httpx.Client,
    admin_credentials: dict[str, str],
):
    headers = auth_headers(admin_credentials["access_token"])
    update_resp = http_client.patch("/v1/auth/users/me", json={}, headers=headers)
    assert_status(update_resp, 400)
