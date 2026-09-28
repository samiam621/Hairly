import json
from pathlib import Path

import httpx
import pytest

from backend.routers import analyze
from backend.services import normalize, product_lookup, rules_engine


DB = Path(__file__).parents[1] / "backend" / "db"


@pytest.fixture(autouse=True, scope="session")
def rules() -> None:
    """Load the seed JSON straight into memory, in place of rules_engine.load_rules() reading the tables."""
    seed = json.loads((DB / "rules.json").read_text())
    rules_engine.RULES.update(seed["concerns"])
    rules_engine.KNOWN.update(seed["known_ingredients"], *seed["concerns"].values())
    normalize.ALIASES.update(json.loads((DB / "aliases.json").read_text()))


@pytest.fixture(autouse=True)
def unrecognized(monkeypatch) -> list[list[str]]:
    """Capture record_unrecognized() calls instead of writing to the database."""
    calls = []
    monkeypatch.setattr(analyze, "record_unrecognized", calls.append)
    return calls


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
            (True, "found", product.name, product.ingredients_raw, product.is_hair)
            if product else (True, "not_found", None, None, None)
        )

    monkeypatch.setattr(product_lookup, "_read_cache", rows.get)
    monkeypatch.setattr(product_lookup, "_save", save)
    return rows
