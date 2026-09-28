from typing import Literal


ErrorCode = Literal["PRODUCT_NOT_FOUND", "INVALID_INPUT"]


class HairlyError(Exception):
    def __init__(self, code: ErrorCode, message: str, status_code: int) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
