"""Authentication API router."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_admin
from app.models.admin import AdminUser
from app.schemas.auth import AdminInfo, LoginRequest, TokenResponse
from app.schemas.common import ApiResponse
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["认证管理"])


@router.post(
    "/login",
    response_model=ApiResponse[TokenResponse],
    summary="管理员登录",
    description="使用用户名和密码登录，返回JWT访问令牌。",
)
def login(
    request: LoginRequest,
    db: Session = Depends(get_db),
) -> ApiResponse:
    """Admin login endpoint."""
    service = AuthService(db)
    result = service.login(request.username, request.password)
    return ApiResponse(data=result)


@router.get(
    "/me",
    response_model=ApiResponse[AdminInfo],
    summary="获取当前管理员信息",
    description="获取当前已登录管理员的详细信息。",
)
def get_me(
    current_admin: AdminUser = Depends(get_current_admin),
) -> ApiResponse:
    """Get current admin info endpoint."""
    return ApiResponse(data=AdminInfo.model_validate(current_admin))
