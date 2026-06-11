"""
app/core/exceptions.py
Global exception handlers registered on the FastAPI app in main.py.
"""
import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

logger = logging.getLogger(__name__)


def register_exception_handlers(app: FastAPI) -> None:

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """Pydantic validation failures — 422 with field-level error detail."""
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "detail": "Validation error",
                "errors": [
                    {
                        "field": " → ".join(str(loc) for loc in e["loc"]),
                        "message": e["msg"],
                    }
                    for e in exc.errors()
                ],
            },
        )

    @app.exception_handler(IntegrityError)
    async def integrity_error_handler(
        request: Request, exc: IntegrityError
    ) -> JSONResponse:
        """
        DB constraint violations — duplicate email, broken FK, etc.
        Log the detail for debugging but never expose raw DB errors to clients.
        """
        logger.warning("IntegrityError on %s: %s", request.url, exc.orig)
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"detail": "A record with this data already exists"},
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        """
        Catch-all for anything not handled above.
        Always log the full traceback, never expose internals to the client.
        """
        logger.exception("Unhandled error on %s: %s", request.url, exc)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "An unexpected error occurred"},
        )