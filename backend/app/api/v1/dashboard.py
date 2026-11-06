"""Dashboard API router."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_admin
from app.models.admin import AdminUser
from app.schemas.common import ApiErrorResponse, ApiResponse
from app.schemas.dashboard import DashboardOverview
from app.services.dashboard_service import DashboardService

router = APIRouter(prefix="/dashboard", tags=["仪表盘"])

# 错误响应文档（OpenAPI responses；仅文档用途，不改变运行时 HTTP 状态码）。
# 运行时业务异常（40000/40001/40101/40301/40401/40901 等）统一经全局异常处理器以
# HTTP 400 信封返回；请求体校验失败为 HTTP 422（业务码 42201）；系统内部错误为
# HTTP 500（业务码 50000）。
ERROR_RESPONSES = {
    400: {
        "model": ApiErrorResponse,
        "description": "业务错误（HTTP 400，envelope code 区分）：40101 未认证（管理员令牌无效/过期/管理员不存在/已禁用）",
    },
    403: {"model": ApiErrorResponse, "description": "未提供或非法 Authorization 请求头（HTTP 403）"},
    422: {"model": ApiErrorResponse, "description": "请求参数格式校验失败（HTTP 422，code 42201）"},
    500: {"model": ApiErrorResponse, "description": "系统内部错误（HTTP 500，code 50000）"},
}


@router.get(
    "/overview",
    response_model=ApiResponse[DashboardOverview],
    responses=ERROR_RESPONSES,
    summary="获取仪表盘概览",
    description=(
        "用途：获取系统核心统计数据，用于管理后台仪表盘首页展示。\n"
        "调用时机：管理后台仪表盘页加载时调用。\n"
        "请求体：无。\n"
        "返回 data 结构：\n"
        "  knowledge_count: 知识点总数\n"
        "  question_count: 题目总数\n"
        "  single_choice_count: 单选题数量\n"
        "  multiple_choice_count: 多选题数量\n"
        "  true_false_count: 判断题数量\n"
        "  short_answer_count: 简答题数量\n"
        "  import_task_count: 导入任务总数\n"
        "权限：需要管理员登录。\n"
        "幂等性：只读查询，天然幂等；不写数据库。"
    ),
)
def get_dashboard_overview(
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
) -> ApiResponse:
    """Get dashboard overview statistics."""
    service = DashboardService(db)
    data = service.get_overview()
    return ApiResponse(data=data)
