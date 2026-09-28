from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from backend.core.errors import ErrorBody, ErrorResponse, HairlyError
from backend.db.database import pool
from backend.routers import analyze


@asynccontextmanager
async def lifespan(app: FastAPI):
    pool.open()
    yield
    pool.close()


app = FastAPI(title="Hairly API", lifespan=lifespan)
app.include_router(analyze.router)


@app.exception_handler(HairlyError)
async def hairly_error(request: Request, exc: HairlyError) -> JSONResponse:
    body = ErrorResponse(error=ErrorBody(code=exc.code, message=exc.message))
    return JSONResponse(body.model_dump(), status_code=exc.status_code)


@app.exception_handler(RequestValidationError)
async def invalid_request(request: Request, exc: RequestValidationError) -> JSONResponse:
    error = exc.errors()[0]
    return await hairly_error(request, HairlyError("INVALID_INPUT", f"{error['loc'][-1]}: {error['msg']}", 400))


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
