"""FastAPI application entry point."""

import logging
import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_v1_router
from app.core.config import settings
from app.middleware.exception_handler import register_exception_handlers
from app.middleware.request_id import RequestIdMiddleware

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
    force=True,
)

# Suppress noisy loggers
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
logging.getLogger("uvicorn.access").setLevel(logging.INFO)

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="AI面试题库管理系统",
        description="AI驱动的面试题库和知识库管理系统 API V1.0",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Request ID middleware
    app.add_middleware(RequestIdMiddleware)

    # Exception handlers
    register_exception_handlers(app)

    # Include API routers
    app.include_router(api_v1_router)

    @app.get("/", tags=["健康检查"])
    def root():
        """Health check endpoint."""
        return {"status": "ok", "app": settings.APP_NAME, "version": "1.0.0"}

    @app.get("/health", tags=["健康检查"])
    def health():
        """Health check endpoint."""
        return {"status": "healthy"}

    return app


app = create_app()
