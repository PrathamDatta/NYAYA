from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from .ml.registry import ModelUnavailableError

log = logging.getLogger("nyaya.api")


def err(status: int, code: str, message: str, **extra) -> JSONResponse:
    return JSONResponse({"error": {"code": code, "message": message, **extra}}, status_code=status)


def install(app: FastAPI) -> None:
    @app.exception_handler(StarletteHTTPException)
    async def http_exc(_: Request, e: StarletteHTTPException):  # noqa: ANN202
        return err(e.status_code, {401: "unauthorized", 403: "forbidden", 404: "not_found", 429: "rate_limited"}.get(e.status_code, "error"), str(e.detail))

    @app.exception_handler(RequestValidationError)
    async def val_exc(_: Request, e: RequestValidationError):  # noqa: ANN202
        fields = [{"field": ".".join(str(x) for x in er["loc"][1:]), "message": er["msg"]} for er in e.errors()]
        return err(422, "validation_error", "Some fields are invalid.", fields=fields)

    @app.exception_handler(ModelUnavailableError)
    async def model_exc(_: Request, e: ModelUnavailableError):  # noqa: ANN202
        return err(503, "model_unavailable", str(e), model=e.key)

    @app.exception_handler(Exception)
    async def any_exc(request: Request, e: Exception):  # noqa: ANN202
        log.exception("unhandled error on %s %s", request.method, request.url.path)  # no request bodies are logged
        return err(500, "internal_error", "Something went wrong on our side. Please try again.")
