from dataclasses import dataclass

import httpx

from backend.core.errors import HairlyError
from backend.db.database import pool


FOUND_TTL = "30 days"
MISS_TTL = "3 days"  # short, so a product added to OBF later gets picked up

OBF_URL = "https://world.openbeautyfacts.org/api/v2/product/{barcode}.json"
OBF_FIELDS = "product_name,categories_tags,ingredients_text,ingredients_text_en"
BARCODE_LENGTHS = {8, 12, 13, 14}  # EAN-8, UPC-A, EAN-13, GTIN-14

_client = httpx.Client(
    timeout=5.0,
    headers={"User-Agent": "Hairly/0.1"},
)


@dataclass
class Product:
    barcode: str
    name: str | None
    ingredients_raw: str
    is_hair: bool


def validate_barcode(barcode: str) -> str:
    barcode = barcode.strip()
    if not (barcode.isdigit() and barcode.isascii() and len(barcode) in BARCODE_LENGTHS):
        raise HairlyError("INVALID_INPUT", "That barcode doesn't look valid. Try scanning again.", 400)
    return barcode


def fetch_product(barcode: str) -> Product | None:
    """Look up a barcode on Open Beauty Facts.

    Returns None for a known miss (not found, or no ingredient list), which is safe to cache.
    Raises HairlyError(PRODUCT_NOT_FOUND, 503) when OBF is unreachable, which must not be cached.
    """
    barcode = validate_barcode(barcode)
    try:
        response = _client.get(OBF_URL.format(barcode=barcode), params={"fields": OBF_FIELDS})
        if response.status_code == 404:
            return None
        response.raise_for_status()
        data = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise HairlyError(
            "PRODUCT_NOT_FOUND",
            "We couldn't look up this product right now. Try a photo of the ingredient label.",
            503,
        ) from exc

    product = data.get("product") if isinstance(data, dict) else None
    if not isinstance(product, dict) or data.get("status") != 1:
        return None

    ingredients = (product.get("ingredients_text") or product.get("ingredients_text_en") or "").strip()
    if not ingredients:
        return None

    # ponytail: untagged products are assumed hair; OBF categories are often missing.
    categories = product.get("categories_tags") or []
    return Product(
        barcode=barcode,
        name=(product.get("product_name") or "").strip() or None,
        ingredients_raw=ingredients,
        is_hair=not categories or "en:hair" in categories,
    )


def lookup_product(barcode: str) -> Product | None:
    """Cache-first lookup: our products table, then Open Beauty Facts, then save what OBF said.

    An expired row is refreshed from OBF; if OBF is down, the expired row is served instead.
    """
    barcode = validate_barcode(barcode)
    row = _read_cache(barcode)
    if row is not None and row[0]:  # fresh
        return _from_row(barcode, row)

    try:
        product = fetch_product(barcode)  # an OBF outage raises here, so it never reaches the cache
    except HairlyError:
        if row is not None:
            return _from_row(barcode, row)  # stale beats nothing
        raise
    _save(barcode, product)
    return product


def _from_row(barcode: str, row: tuple) -> Product | None:
    _fresh, status, name, ingredients_raw, is_hair = row
    return Product(barcode, name, ingredients_raw, is_hair) if status == "found" else None


def _read_cache(barcode: str) -> tuple | None:
    """Return (fresh, lookup_status, name, ingredients_raw, is_hair), expired rows included."""
    with pool.connection() as conn:
        return conn.execute(
            "select expires_at > now(), lookup_status, name, ingredients_raw, is_hair from products"
            " where barcode = %s",
            (barcode,),
        ).fetchone()


def _save(barcode: str, product: Product | None) -> None:
    if product:
        values = (barcode, product.name, product.ingredients_raw, product.is_hair, "found", FOUND_TTL)
    else:
        values = (barcode, None, None, None, "not_found", MISS_TTL)
    # Upsert: two simultaneous scans of one barcode both write; the second overwrites instead of erroring.
    with pool.connection() as conn:
        conn.execute(
            """
            insert into products (barcode, name, ingredients_raw, is_hair, lookup_status, fetched_at, expires_at)
            values (%s, %s, %s, %s, %s, now(), now() + %s::interval)
            on conflict (barcode) do update set
                name = excluded.name,
                ingredients_raw = excluded.ingredients_raw,
                is_hair = excluded.is_hair,
                lookup_status = excluded.lookup_status,
                fetched_at = excluded.fetched_at,
                expires_at = excluded.expires_at,
                updated_at = now()
            """,
            values,
        )
