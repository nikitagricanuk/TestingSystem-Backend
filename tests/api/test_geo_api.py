from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.repositories.dao.geodao import RegionDAO, SettlementDAO, SchoolDAO


@pytest.fixture()
def app():
    app = FastAPI()
    from app.routers import geo as geo_router

    app.include_router(geo_router.router, prefix="/v1")
    return app


@pytest.fixture()
def client(app: FastAPI):
    return TestClient(app)


def test_list_regions_returns_filtered_rows(client, monkeypatch):
    region = SimpleNamespace(id=uuid4(), region="Иркутская область")
    captured = {}

    async def fake_list(q=None, offset=0, limit=100, session=None):
        captured["q"] = q
        return [region]

    monkeypatch.setattr(RegionDAO, "list", fake_list)

    response = client.get("/v1/regions", params={"q": "Иркут"})

    assert response.status_code == 200
    assert response.json() == [{"id": str(region.id), "region": region.region}]
    assert captured["q"] == "Иркут"


def test_list_settlements_filters_by_region(client, monkeypatch):
    region_id = uuid4()
    settlement = SimpleNamespace(id=uuid4(), name="Иркутск", type="city", region_id=region_id)
    captured = {}

    async def fake_list(region_id=None, q=None, offset=0, limit=100, session=None):
        captured["region_id"] = region_id
        return [settlement]

    monkeypatch.setattr(SettlementDAO, "list", fake_list)

    response = client.get("/v1/settlements", params={"region_id": str(region_id)})

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": str(settlement.id),
            "name": settlement.name,
            "type": settlement.type,
            "region_id": str(region_id),
        }
    ]
    assert captured["region_id"] == region_id


def test_list_schools_filters_by_settlement(client, monkeypatch):
    settlement_id = uuid4()
    school = SimpleNamespace(
        id=uuid4(), full_name="МАОУ Школа №4", short_name="Школа №4", city_id=settlement_id
    )
    captured = {}

    async def fake_list(settlement_id=None, q=None, offset=0, limit=100, session=None):
        captured["settlement_id"] = settlement_id
        return [school]

    monkeypatch.setattr(SchoolDAO, "list", fake_list)

    response = client.get("/v1/schools", params={"settlement_id": str(settlement_id)})

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": str(school.id),
            "full_name": school.full_name,
            "short_name": school.short_name,
            "city_id": str(settlement_id),
        }
    ]
    assert captured["settlement_id"] == settlement_id
