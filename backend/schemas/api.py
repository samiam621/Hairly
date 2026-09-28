from typing import Literal

from pydantic import BaseModel, Field


Verdict = Literal["safe", "caution", "avoid", "unknown"]
Severity = Literal["low", "medium", "high"]


class BarcodeAnalyzeRequest(BaseModel):
    barcode: str = Field(min_length=1)
    concern: str = Field(min_length=1)


class FlaggedIngredient(BaseModel):
    name: str
    reason: str
    severity: Severity


class AnalyzeResponse(BaseModel):
    product_name: str | None
    verdict: Verdict
    summary: str
    flagged_ingredients: list[FlaggedIngredient]
    all_ingredients: list[str]
    unrecognized_ingredients: list[str]
    disclaimer: str


