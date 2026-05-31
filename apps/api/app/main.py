from __future__ import annotations

from typing import Dict

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.v1.routes.evals import router as evals_router
from app.api.v1.routes.external_endpoints import router as external_endpoints_router
from app.api.v1.routes.playground import router as playground_router
from app.api.v1.routes.traces import router as traces_router
from app.services.errors import ServiceError


def create_app() -> FastAPI:
    app = FastAPI(
        title="ContextTrace API",
        version="0.1.0",
        description="RAG reliability tracing and citation support verification API.",
    )

    @app.get("/healthz", tags=["health"])
    def healthz() -> Dict[str, str]:
        return {"status": "ok"}

    @app.exception_handler(ServiceError)
    async def service_error_handler(
        request: Request,
        exc: ServiceError,
    ) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})

    app.include_router(traces_router, prefix="/v1")
    app.include_router(evals_router, prefix="/v1")
    app.include_router(external_endpoints_router, prefix="/v1")
    app.include_router(playground_router, prefix="/v1")
    return app


app = create_app()
