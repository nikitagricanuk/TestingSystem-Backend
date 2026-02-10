import os
import subprocess
import time
from pathlib import Path
from uuid import uuid4

import httpx
import pytest


E2E_RUN_ENV = "E2E_RUN"
E2E_BASE_URL_ENV = "E2E_BASE_URL"


def _required_env() -> str | None:
    if os.getenv(E2E_RUN_ENV) == "1":
        return None
    return f"Set {E2E_RUN_ENV}=1 to run e2e tests."


skip_reason = _required_env()
if skip_reason:
    pytest.skip(skip_reason, allow_module_level=True)


@pytest.fixture(scope="session")
def base_url() -> str:
    base = os.getenv(E2E_BASE_URL_ENV, "http://localhost:8000")
    return base.rstrip("/")


@pytest.fixture(scope="session")
def http_client(base_url: str):
    timeout = httpx.Timeout(10.0, connect=10.0)
    with httpx.Client(base_url=base_url, timeout=timeout) as client:
        yield client


@pytest.fixture(scope="session", autouse=True)
def run_migrations_if_requested():
    if os.getenv("E2E_RUN_MIGRATIONS") != "1":
        return
    project_root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        ["docker", "compose", "exec", "-T", "server", "alembic", "upgrade", "head"],
        cwd=project_root,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            "Failed to run migrations via docker compose.\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )


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


@pytest.fixture(scope="session", autouse=True)
def wait_for_ready(http_client: httpx.Client):
    deadline = time.time() + 90
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            response = http_client.get("/ready")
            if response.status_code == 200:
                return
        except Exception as exc:
            last_error = exc
        time.sleep(2)
    if last_error:
        raise RuntimeError("Service did not become ready in time.") from last_error
    raise RuntimeError("Service did not become ready in time.")


@pytest.fixture(scope="session")
def admin_credentials(http_client: httpx.Client) -> dict[str, str]:
    email = f"e2e-admin-{uuid4()}@example.com"
    password = "Password123!"
    payload = {
        "full_name": "E2E Admin",
        "nickname": "e2e-admin",
        "age": 30,
        "email": email,
        "phone": f"+100000{uuid4().hex[:6]}",
        "password": password,
        "role": "ADMIN",
    }
    create_resp = http_client.post("/v1/auth/users/create", json=payload)
    if create_resp.status_code != 200:
        _dump_compose_logs("user_create_failed")
    assert create_resp.status_code == 200, create_resp.text

    login_resp = http_client.post("/v1/auth/login", json={"email": email, "password": password})
    assert login_resp.status_code == 200, login_resp.text
    data = login_resp.json()
    return {
        "email": email,
        "password": password,
        "access_token": data["access_token"],
        "refresh_token": data["refresh_token"],
    }
