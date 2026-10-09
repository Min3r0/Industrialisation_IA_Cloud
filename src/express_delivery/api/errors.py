"""Toutes les erreurs HTTP sortent au format `Error` du contrat OpenAPI."""
from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from express_delivery.api.schemas import Error

logger = logging.getLogger(__name__)


class ApiError(Exception):
    def __init__(self, status_code: int, error: str, message: str,
                 headers: dict[str, str] | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.error = error
        self.message = message
        self.headers = headers


def _respond(status_code: int, body: Error, headers: dict[str, str] | None = None) -> JSONResponse:
    return JSONResponse(status_code=status_code, content=body.model_dump(exclude_none=True),
                        headers=headers)


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def handle_api_error(_: Request, exc: ApiError) -> JSONResponse:
        return _respond(exc.status_code, Error(error=exc.error, message=exc.message), exc.headers)

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        details = [
            f"{'.'.join(str(part) for part in err['loc'] if part != 'body')} : {err['msg']}"
            for err in exc.errors()
        ]
        return _respond(422, Error(error="validation_error", message="Commande invalide", details=details))

    @app.exception_handler(Exception)
    async def handle_unexpected_error(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("Erreur interne non gérée", exc_info=exc)
        return _respond(500, Error(error="internal_error", message="Erreur interne"))
