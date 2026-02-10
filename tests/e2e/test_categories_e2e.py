from uuid import uuid4

import httpx
import pytest

from tests.e2e.helpers import assert_status, create_category


@pytest.mark.e2e
def test_category_crud(http_client: httpx.Client):
    category = create_category(http_client, f"e2e-category-{uuid4()}")

    get_resp = http_client.get(f"/v1/categories/{category['id']}")
    assert_status(get_resp, 200)
    assert get_resp.json()["id"] == category["id"]

    update_resp = http_client.patch(
        f"/v1/categories/{category['id']}",
        json={"name": f"e2e-category-updated-{uuid4()}"},
    )
    assert_status(update_resp, 200)

    list_resp = http_client.get("/v1/categories")
    assert_status(list_resp, 200)
    ids = {item["id"] for item in list_resp.json()}
    assert category["id"] in ids

    delete_resp = http_client.delete(f"/v1/categories/{category['id']}")
    assert_status(delete_resp, 200)
