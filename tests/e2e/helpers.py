import os
import subprocess
from pathlib import Path
from uuid import uuid4

import httpx


def auth_headers(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


def dump_compose_logs(label: str) -> None:
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


def assert_status(response: httpx.Response, expected: int) -> None:
    if response.status_code != expected:
        dump_compose_logs(f"{response.request.method} {response.request.url}")
    assert response.status_code == expected, response.text


def create_category(client: httpx.Client, name: str, parent_id: str | None = None) -> dict:
    payload: dict[str, str] = {"name": name}
    if parent_id is not None:
        payload["parent_id"] = parent_id
    response = client.post("/v1/categories", json=payload)
    assert_status(response, 201)
    return response.json()


def create_question(
    client: httpx.Client,
    token: str,
    category_id: str,
    text: str,
    answer_value: str = "4",
    *,
    mark_out_of: int = 1,
    penalty: int = 0,
    is_active: bool = True,
) -> dict:
    payload = {
        "text": text,
        "answer": {"value": answer_value},
        "question_type": "single",
        "problem": "2 + 2",
        "mark_out_of": mark_out_of,
        "penalty": penalty,
        "is_active": is_active,
        "category_id": category_id,
    }
    response = client.post("/v1/questions", json=payload, headers=auth_headers(token))
    assert_status(response, 201)
    return response.json()


def create_questions(
    client: httpx.Client,
    token: str,
    category_id: str,
    count: int,
    prefix: str,
) -> list[dict]:
    questions = []
    for idx in range(count):
        questions.append(
            create_question(
                client,
                token,
                category_id=category_id,
                text=f"{prefix} {idx + 1}",
                answer_value=str(idx + 1),
            )
        )
    return questions


def create_test(
    client: httpx.Client,
    token: str,
    name: str,
    question_ids: list[str],
    number_required: int | None = None,
    **overrides: object,
) -> dict:
    if number_required is None:
        number_required = len(question_ids)
    payload = {
        "name": name,
        "question_ids": question_ids,
        "number_of_required_questions": number_required,
    }
    payload.update(overrides)
    response = client.post("/v1/tests/create", json=payload, headers=auth_headers(token))
    assert_status(response, 201)
    return response.json()


def signup_student(client: httpx.Client, email: str, password: str) -> dict:
    payload = {
        "full_name": "E2E Student",
        "nickname": f"e2e-student-{uuid4()}",
        "age": 21,
        "email": email,
        "phone": f"+100000{uuid4().hex[:6]}",
        "password": password,
    }
    response = client.post("/v1/auth/signup", json=payload)
    assert_status(response, 200)
    return response.json()
