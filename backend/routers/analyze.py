from typing import Annotated

from fastapi import APIRouter, File, Form, UploadFile

from backend.core.errors import HairlyError
from backend.schemas.api import AnalyzeResponse, BarcodeAnalyzeRequest
from backend.services.gemini import MAX_IMAGE_BYTES, MAX_PHOTOS, read_label
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
def analyze_label(
    # alias: the form field stays `image`, sent once per photo (one or several angles of the label)
    images: Annotated[list[UploadFile], File(alias="image")], concern: Annotated[str, Form(min_length=1)]
) -> AnalyzeResponse:
    validate_concern(concern)  # before spending a Gemini call on it
    # Read one photo past the cap and one byte past the size limit: enough to reject without reading everything.
    photos, budget = [], MAX_IMAGE_BYTES + 1
    for image in images[: MAX_PHOTOS + 1]:
        photos.append(image.file.read(budget))
        budget -= len(photos[-1])
    result = evaluate(normalize(read_label(photos)), concern)
    record_unrecognized(result.unrecognized_ingredients)
    return result
