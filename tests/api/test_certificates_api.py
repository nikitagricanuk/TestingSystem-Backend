from datetime import datetime, timezone
from io import BytesIO
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image
from pypdf import PdfReader
from reportlab.pdfgen import canvas as rl_canvas

from app.schemas.users import UserFull
from app.services.auth.routers.auth import get_current_user
from app.services.testing_engine.models.redis import SessionStatus


def _make_user(role: str, permissions: list[str], user_id=None, is_guest: bool = False) -> UserFull:
    now = datetime.now(timezone.utc)
    return UserFull(
        id=user_id or uuid4(), nickname="tester", email="t@example.com", is_active=True, role=role,
        created_at=now, created_at_unix=int(now.timestamp()), updated_at=None, updated_at_unix=None,
        full_name="Test User", age=None, phone=None, school=None, permissions=permissions, is_guest=is_guest,
    )


def _sample_pdf_bytes() -> bytes:
    buffer = BytesIO()
    canvas = rl_canvas.Canvas(buffer, pagesize=(600, 400))
    canvas.showPage()
    canvas.save()
    return buffer.getvalue()


def _sample_png_bytes() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (600, 400), color="white").save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.fixture()
def app(tmp_path, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "certificate_storage_path", str(tmp_path))
    app = FastAPI()
    from app.routers import certificates as certificates_router

    app.include_router(certificates_router.router, prefix="/v1")
    return app


@pytest.fixture()
def client(app: FastAPI):
    return TestClient(app)


def _override(app: FastAPI, role: str, permissions: list[str], user_id=None, is_guest: bool = False):
    async def _fn():
        return _make_user(role, permissions, user_id=user_id, is_guest=is_guest)

    app.dependency_overrides[get_current_user] = _fn


def test_upload_template_rejects_bad_content_type(client: TestClient, app: FastAPI, monkeypatch):
    from app.repositories.dao.certificatedao import CertificateTemplateDAO

    _override(app, "admissions_committee", ["create_certificates"])
    res = client.post(
        "/v1/certificates/templates",
        params={"name": "Default"},
        files={"file": ("t.txt", b"not a pdf", "text/plain")},
    )
    assert res.status_code == 400


def test_upload_pdf_template_success(client: TestClient, app: FastAPI, monkeypatch):
    from app.repositories.dao.certificatedao import CertificateTemplateDAO

    created = {}

    async def fake_create(*, name, kind, asset_path, test_id=None, fields=None):
        template = SimpleNamespace(
            id=uuid4(), test_id=test_id, name=name, kind=kind, fields=[], signature_asset_path=None,
            signature_position=None,
        )
        created["template"] = template
        created["asset_path"] = asset_path
        return template

    _override(app, "admissions_committee", ["create_certificates"])
    monkeypatch.setattr(CertificateTemplateDAO, "create", fake_create, raising=False)

    res = client.post(
        "/v1/certificates/templates",
        params={"name": "Base template", "kind": "base"},
        files={"file": ("t.pdf", _sample_pdf_bytes(), "application/pdf")},
    )

    assert res.status_code == 201
    body = res.json()
    assert body["name"] == "Base template"
    assert body["kind"] == "base"


def test_upload_image_template_is_wrapped_into_pdf(client: TestClient, app: FastAPI, monkeypatch, tmp_path):
    from app.repositories.dao.certificatedao import CertificateTemplateDAO

    saved_paths = []

    async def fake_create(*, name, kind, asset_path, test_id=None, fields=None):
        saved_paths.append(asset_path)
        return SimpleNamespace(
            id=uuid4(), test_id=test_id, name=name, kind=kind, fields=[], signature_asset_path=None,
            signature_position=None,
        )

    _override(app, "admin", ["create_certificates"])
    monkeypatch.setattr(CertificateTemplateDAO, "create", fake_create, raising=False)

    res = client.post(
        "/v1/certificates/templates",
        params={"name": "Image template"},
        files={"file": ("t.png", _sample_png_bytes(), "image/png")},
    )

    assert res.status_code == 201
    saved_file = tmp_path / saved_paths[0]
    assert saved_file.exists()
    reader = PdfReader(str(saved_file))
    assert len(reader.pages) == 1


def test_list_templates_forbidden_without_permission(client: TestClient, app: FastAPI):
    _override(app, "student", [])
    res = client.get("/v1/certificates/templates")
    assert res.status_code == 403


def test_download_certificate_forbidden_for_unrelated_student(client: TestClient, app: FastAPI, monkeypatch):
    from app.routers import certificates as certificates_router

    session = SimpleNamespace(sid=str(uuid4()), user_id=uuid4(), test_id=uuid4(), status=SessionStatus.FINISHED)

    async def fake_load_session(rid):
        return session

    _override(app, "student", [])  # different user_id than the session's owner
    monkeypatch.setattr(certificates_router, "_load_session", fake_load_session)

    res = client.get(f"/v1/results/{uuid4()}/certificate")
    assert res.status_code == 403


def test_download_certificate_forbidden_for_guest_even_as_owner(client: TestClient, app: FastAPI, monkeypatch):
    from app.routers import certificates as certificates_router

    user_id = uuid4()
    session = SimpleNamespace(sid=str(uuid4()), user_id=user_id, test_id=uuid4(), status=SessionStatus.FINISHED)

    async def fake_load_session(rid):
        return session

    _override(app, "student", [], user_id=user_id, is_guest=True)
    monkeypatch.setattr(certificates_router, "_load_session", fake_load_session)

    res = client.get(f"/v1/results/{uuid4()}/certificate")
    assert res.status_code == 403


def test_download_certificate_blocked_if_not_finished(client: TestClient, app: FastAPI, monkeypatch):
    from app.routers import certificates as certificates_router

    user_id = uuid4()
    session = SimpleNamespace(sid=str(uuid4()), user_id=user_id, test_id=uuid4(), status=SessionStatus.ACTIVE)

    async def fake_load_session(rid):
        return session

    async def fake_build_result(s):
        return SimpleNamespace(status="active", id=uuid4(), test_id=s.test_id, user_id=s.user_id, score=None)

    _override(app, "student", [], user_id=user_id)
    monkeypatch.setattr(certificates_router, "_load_session", fake_load_session)
    monkeypatch.setattr(certificates_router, "_build_result", fake_build_result)

    res = client.get(f"/v1/results/{uuid4()}/certificate")
    assert res.status_code == 400


def test_download_certificate_success_for_owner(client: TestClient, app: FastAPI, monkeypatch, tmp_path):
    from app.routers import certificates as certificates_router
    from app.repositories.dao.certificatedao import CertificateTemplateDAO
    from app.repositories.dao.userdao import UserDAO
    from app.models.database import CertificateKind
    from app.services.certificates import storage

    user_id = uuid4()
    test_id = uuid4()
    result_id = uuid4()
    session = SimpleNamespace(
        sid=str(result_id), user_id=user_id, test_id=test_id, status=SessionStatus.FINISHED, score=90.0,
    )

    template_pdf = tmp_path / "bg.pdf"
    template_pdf.write_bytes(_sample_pdf_bytes())

    template = SimpleNamespace(
        id=uuid4(), test_id=test_id, name="T", kind=CertificateKind.BASE, asset_path="bg.pdf",
        fields=[{"key": "full_name_short", "page": 0, "x": 50, "y": 100, "font_size": 20}],
        signature_asset_path=None, signature_position=None,
    )

    async def fake_load_session(rid):
        return session

    async def fake_build_result(s):
        return SimpleNamespace(
            status="completed", id=result_id, test_id=test_id, user_id=user_id, score=90.0,
            duration_seconds=60, time_finish=datetime(2025, 1, 1),
        )

    async def fake_get_for_test(tid):
        return template

    async def fake_get_user_by_id(self, uid):
        return SimpleNamespace(full_name="Ivan Ivanov", school=None)

    async def fake_load_finished(test_id=None):
        return [session]

    _override(app, "student", [], user_id=user_id)
    monkeypatch.setattr(certificates_router, "_load_session", fake_load_session)
    monkeypatch.setattr(certificates_router, "_build_result", fake_build_result)
    monkeypatch.setattr(certificates_router, "_load_finished_sessions", fake_load_finished)
    monkeypatch.setattr(CertificateTemplateDAO, "get_for_test", staticmethod(fake_get_for_test), raising=False)
    monkeypatch.setattr(UserDAO, "get_user_by_id", fake_get_user_by_id, raising=False)
    monkeypatch.setattr(storage, "storage_root", lambda: tmp_path)

    res = client.get(f"/v1/results/{result_id}/certificate")

    assert res.status_code == 200
    assert res.headers["content-type"] == "application/pdf"
    reader = PdfReader(BytesIO(res.content))
    assert "Ivan I." in reader.pages[0].extract_text()
