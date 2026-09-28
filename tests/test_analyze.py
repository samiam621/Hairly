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


def post(barcode: str, concern: str = "dye allergy") -> httpx.Response:
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
        ("1234567890128", "dye allergy", 404, "PRODUCT_NOT_FOUND"),  # OBF 404
        ("3178041367042", "dye allergy", 404, "PRODUCT_NOT_FOUND"),  # no ingredient list
        ("12ab", "dye allergy", 400, "INVALID_INPUT"),
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


@pytest.mark.parametrize("payload", [{"barcode": "0309978695325"}, {"barcode": "", "concern": "dye allergy"}, None])
def test_bad_request_body_is_invalid_input(payload) -> None:
    response = client.post("/api/analyze/barcode", json=payload)

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_INPUT"


def test_unrecognized_ingredients_are_recorded_for_hair_products_only(obf, unrecognized: list) -> None:
    obf(serve_fixtures)
    body = post("6111056012986").json()  # Arabic label, hair product
    assert unrecognized == [body["unrecognized_ingredients"]] and body["unrecognized_ingredients"]

    product = {"ingredients_text": "Talc, Mystery Pigment", "categories_tags": ["en:make-up"]}
    obf(lambda req: httpx.Response(200, json={"status": 1, "product": product}))
    post("3600523614424")
    assert len(unrecognized) == 1  # the makeup product added nothing
