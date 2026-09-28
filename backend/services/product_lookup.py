from dataclasses import dataclass

import httpx

from backend.core.errors import HairlyError


OBF_URL = "https://world.openbeautyfacts.org/api/v2/product/{barcode}.json"
OBF_FIELDS = "product_name,brands,categories_tags,ingredients_text,ingredients_text_en"
BARCODE_LENGTHS = {8, 12, 13, 14}  # EAN-8, UPC-A, EAN-13, GTIN-14

_client = httpx.Client(
    timeout=5.0,
    headers={"User-Agent": "Hairly/0.1"},
)


@dataclass
class Product:
    barcode: str
    name: str | None
    brand: str | None
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
        brand=(product.get("brands") or "").strip() or None,
        ingredients_raw=ingredients,
        is_hair=not categories or "en:hair" in categories,
    )
