import json
from pathlib import Path

import httpx
import pytest

from backend.core.errors import HairlyError
from backend.services.product_lookup import fetch_product, lookup_product


FIXTURES = Path(__file__).parent / "fixtures" / "obf"
MISSES = {"3178041367042", "1234567890128", "0000000000017"}  # empty ingredients, wrong product type (404), invalid code
HTTP_404 = {"1234567890128"}


@pytest.mark.parametrize("path", sorted(FIXTURES.glob("*.json")), ids=lambda p: p.stem)
def test_fixture(obf, path: Path) -> None:
    barcode = path.stem
    body = json.loads(path.read_text())
    obf(lambda req: httpx.Response(404 if barcode in HTTP_404 else 200, json=body))

    product = fetch_product(barcode)

    if barcode in MISSES:
        assert product is None
    else:
        assert product is not None
        assert product.barcode == barcode
        assert product.ingredients_raw == body["product"]["ingredients_text"].strip()


@pytest.mark.parametrize("barcode", ["", "abc", "12345", "123456789012345", "12345678901a3", "１２３４５６７８"])
def test_invalid_barcode(barcode: str) -> None:
    with pytest.raises(HairlyError) as exc:
        fetch_product(barcode)
    assert (exc.value.code, exc.value.status_code) == ("INVALID_INPUT", 400)


def raise_timeout(req):
    raise httpx.ReadTimeout("timeout", request=req)


@pytest.mark.parametrize(
    "handler",
    [raise_timeout, lambda req: httpx.Response(500), lambda req: httpx.Response(200, text="<html>")],
    ids=["timeout", "server_error", "bad_json"],
)
def test_upstream_failure_is_not_a_miss(obf, handler) -> None:
    obf(handler)
    with pytest.raises(HairlyError) as exc:
        fetch_product("3178040643802")
    assert (exc.value.code, exc.value.status_code) == ("PRODUCT_NOT_FOUND", 503)


@pytest.mark.parametrize(
    ("categories", "is_hair"),
    [(["en:hair", "en:shampoos"], True), (["nl:Foundation", "nl:Make-up"], False), (None, True)],
)
def test_is_hair(obf, categories, is_hair: bool) -> None:
    body = {"status": 1, "product": {"ingredients_text": "Aqua", "categories_tags": categories}}
    obf(lambda req: httpx.Response(200, json=body))
    assert fetch_product("3600523614424").is_hair is is_hair


def test_cache(obf, cache: dict) -> None:
    calls = []

    def count(status: int, body: dict | None = None):
        def handler(req):
            calls.append(req.url.path)
            return httpx.Response(status, json=body or {})
        return handler

    obf(count(200, {"status": 1, "product": {"product_name": "Dye", "ingredients_text": "Aqua"}}))
    assert lookup_product("0309978695325").name == "Dye"
    assert lookup_product("0309978695325").name == "Dye"  # second scan served from cache
    assert len(calls) == 1

    obf(count(404))
    assert lookup_product("1234567890128") is None
    assert lookup_product("1234567890128") is None  # known miss cached too
    assert len(calls) == 2

    obf(count(502))
    with pytest.raises(HairlyError):
        lookup_product("3178040643802")
    assert "3178040643802" not in cache  # outage is not a miss


def test_expired_entry(obf, cache: dict) -> None:
    cache["0309978695325"] = (False, "found", "Old name", "Aqua", True)  # expired

    obf(lambda req: httpx.Response(502))
    assert lookup_product("0309978695325").name == "Old name"  # OBF down: serve stale

    obf(lambda req: httpx.Response(200, json={"status": 1, "product": {"product_name": "New name", "ingredients_text": "Aqua"}}))
    assert lookup_product("0309978695325").name == "New name"  # OBF up: refresh
    assert cache["0309978695325"][:3] == (True, "found", "New name")
