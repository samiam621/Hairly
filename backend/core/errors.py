from typing import Literal

from pydantic import BaseModel


ErrorCode = Literal[
    "PRODUCT_NOT_FOUND",
    "LABEL_UNREADABLE",
    "INVALID_INPUT",
    "AI_UNAVAILABLE",
    "RATE_LIMITED",
]


class ErrorBody(BaseModel):
    code: ErrorCode
    message: str


class ErrorResponse(BaseModel):
    error: ErrorBody


class HairlyError(Exception):
    def __init__(self, code: ErrorCode, message: str, status_code: int) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
