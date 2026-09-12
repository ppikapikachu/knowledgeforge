"""Dashboard API router."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_admin
from app.models.admin import AdminUser
from app.schemas.common import ApiResponse
from app.schemas.dashboard import DashboardOverview
from app.services.dashboard_service import DashboardService

router = APIRouter(prefix="/dashboard", tags=["仪表盘"])


@router.get(
    "/overview",
    response_model=ApiResponse[DashboardOverview],
    summary="获取仪表盘概览",
    description="获取系统统计数据，包括知识点、题目、导入任务等数量。",
)
def get_dashboard_overview(
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
) -> ApiResponse:
    """Get dashboard overview statistics."""
    service = DashboardService(db)
    data = service.get_overview()
    return ApiResponse(data=data)
