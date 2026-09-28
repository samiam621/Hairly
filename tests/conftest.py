import httpx
import pytest

from backend.services import product_lookup


@pytest.fixture
def obf(monkeypatch):
    """Replace Open Beauty Facts with a handler: request in, httpx.Response out."""
    def use(handler) -> None:
        monkeypatch.setattr(product_lookup, "_client", httpx.Client(transport=httpx.MockTransport(handler)))
    return use


@pytest.fixture(autouse=True)
def cache(monkeypatch) -> dict:
    """Swap the products table for a dict so tests never touch Supabase."""
    rows = {}

    def save(barcode, product):
        rows[barcode] = (
            (True, "found", product.name, product.brand, product.ingredients_raw, product.is_hair)
            if product else (True, "not_found", None, None, None, None)
        )

    monkeypatch.setattr(product_lookup, "_read_cache", rows.get)
    monkeypatch.setattr(product_lookup, "_save", save)
    return rows
