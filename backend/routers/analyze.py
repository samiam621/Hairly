from fastapi import APIRouter

from backend.core.errors import HairlyError
from backend.schemas.api import AnalyzeResponse, BarcodeAnalyzeRequest
from backend.services.normalize import normalize
from backend.services.product_lookup import lookup_product
from backend.services.rules_engine import evaluate, record_unrecognized


router = APIRouter(prefix="/api/analyze")


@router.post("/barcode", response_model=AnalyzeResponse)
def analyze_barcode(request: BarcodeAnalyzeRequest) -> AnalyzeResponse:
    product = lookup_product(request.barcode)
    if product is None:
        raise HairlyError("PRODUCT_NOT_FOUND", "We don't have ingredients for this product. Try a photo of the label.", 404)
    result = evaluate(normalize(product.ingredients_raw), request.concern, product.name, product.is_hair)
    if product.is_hair:  # a non-hair product would fill the backlog with makeup ingredients
        record_unrecognized(result.unrecognized_ingredients)
    return result
