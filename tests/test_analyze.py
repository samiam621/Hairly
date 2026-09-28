from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from backend.main import app


FIXTURES = Path(__file__).parent / "fixtures" / "obf"
client = TestClient(app)


def serve_fixtures(request: httpx.Request) -> httpx.Response:
    path = FIXTURES / Path(request.url.path).name
    if not path.exists() or path.stem == "1234567890128":
        return httpx.Response(404, json={"status": 0})
    return httpx.Response(200, content=path.read_bytes())


def post(barcode: str, concern: str = "dye safety") -> httpx.Response:
    return client.post("/api/analyze/barcode", json={"barcode": barcode, "concern": concern})


def test_found_product_returns_verdict(obf) -> None:
    obf(serve_fixtures)
    response = post("0309978695325")

    assert response.status_code == 200
    body = response.json()
    assert body["verdict"] == "avoid"
    assert body["flagged_ingredients"][0]["name"] == "p-phenylenediamine"
    assert body["flagged_ingredients"][0]["severity"] == "high"
    assert body["product_name"] and body["disclaimer"]
    assert "p-phenylenediamine" in body["all_ingredients"]


@pytest.mark.parametrize(
    ("barcode", "concern", "status", "code"),
    [
        ("1234567890128", "dye safety", 404, "PRODUCT_NOT_FOUND"),  # OBF 404
        ("3178041367042", "dye safety", 404, "PRODUCT_NOT_FOUND"),  # no ingredient list
        ("12ab", "dye safety", 400, "INVALID_INPUT"),
        ("0309978695325", "vegan", 400, "INVALID_INPUT"),
    ],
)
def test_errors_use_error_shape(obf, barcode: str, concern: str, status: int, code: str) -> None:
    obf(serve_fixtures)
    response = post(barcode, concern)

    assert response.status_code == status
    assert response.json()["error"]["code"] == code
    assert response.json()["error"]["message"]


def test_obf_down_is_503(obf) -> None:
    obf(lambda request: httpx.Response(502))
    response = post("0309978695325")

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "PRODUCT_NOT_FOUND"


@pytest.mark.parametrize("payload", [{"barcode": "0309978695325"}, {"barcode": "", "concern": "dye safety"}, None])
def test_bad_request_body_is_invalid_input(payload) -> None:
    response = client.post("/api/analyze/barcode", json=payload)

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_INPUT"
