from typing import Annotated

from fastapi import APIRouter, File, Form, UploadFile

from backend.core.errors import HairlyError
from backend.schemas.api import AnalyzeResponse, BarcodeAnalyzeRequest
from backend.services.gemini import MAX_IMAGE_BYTES, read_label
from backend.services.normalize import normalize
from backend.services.product_lookup import lookup_product
from backend.services.rules_engine import evaluate, record_unrecognized, validate_concern


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


# Not cached: a label photo has no reliable barcode to key it on.
@router.post("/label", response_model=AnalyzeResponse)
def analyze_label(image: Annotated[UploadFile, File()], concern: Annotated[str, Form(min_length=1)]) -> AnalyzeResponse:
    validate_concern(concern)  # before spending a Gemini call on it
    # One byte over the limit is enough to spot an oversized photo without reading all of it.
    result = evaluate(normalize(read_label(image.file.read(MAX_IMAGE_BYTES + 1))), concern)
    record_unrecognized(result.unrecognized_ingredients)
    return result
