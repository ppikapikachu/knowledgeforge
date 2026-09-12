"""API router aggregation."""

from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.dashboard import router as dashboard_router
from app.api.v1.import_task import router as import_task_router
from app.api.v1.knowledge import router as knowledge_router
from app.api.v1.question import router as question_router

api_v1_router = APIRouter(prefix="/api/v1")

api_v1_router.include_router(auth_router)
api_v1_router.include_router(knowledge_router)
api_v1_router.include_router(question_router)
api_v1_router.include_router(import_task_router)
api_v1_router.include_router(dashboard_router)
