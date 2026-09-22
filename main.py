from __future__ import annotations

import logging
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import tenants, views


def _gcp_severity(
    _logger: object, method_name: str, event_dict: dict
) -> dict:
    """Cloud Logging usa `severity` en lugar de `level`."""
    event_dict["severity"] = event_dict.pop("level", method_name).upper()
    return event_dict


def configure_logging() -> None:
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            _gcp_severity,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )


configure_logging()
log = structlog.get_logger("portal-ai-data-backend")


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    log.info("startup", service="portal-ai-data-backend")
    yield
    log.info("shutdown", service="portal-ai-data-backend")


app = FastAPI(
    title="portal-ai-data-backend",
    version="0.1.0",
    lifespan=lifespan,
)

# Desarrollo: CORS permisivo. En producción restringir a orígenes concretos.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(tenants.router, prefix="/api/v1")
app.include_router(views.router, prefix="/api/v1")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
