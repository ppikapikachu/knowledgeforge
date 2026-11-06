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
    description=(
        "使用用户名和密码登录管理端，签发 JWT 访问令牌。\n\n"
        "调用时机：管理后台登录页提交表单时调用；后续所有管理端接口在请求头携带 "
        "`Authorization: Bearer <access_token>`。\n\n"
        "请求体：username: 登录账号（1-50 字符）；password: 密码（1-128 字符）。\n\n"
        "返回 data：access_token: JWT 访问令牌（有效期见 JWT_EXPIRE_MINUTES 配置，默认 120 分钟）；"
        "token_type: 令牌类型，固定 `bearer`。\n\n"
        "权限：公开接口（无需令牌）。\n\n"
        "幂等性：无副作用（仅签发令牌并更新最后登录时间），可重复调用。\n\n"
        "写库：是（更新 admin_user.last_login_at）。"
    ),
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
    description=(
        "获取当前登录管理员的账号信息，用于前端初始化登录态与展示当前用户。\n\n"
        "调用时机：登录后加载管理端用户信息、校验令牌有效性。\n\n"
        "返回 data：id: 管理员 ID；username: 登录账号；nickname: 显示昵称；avatar: 头像 URL（可空）；"
        "status: 账号状态（1=启用）；last_login_at: 最后登录时间（可空）；created_at: 创建时间。\n\n"
        "权限：管理员令牌（Authorization: Bearer <admin_access_token>）。\n\n"
        "幂等性：只读接口，无副作用。\n\n"
        "写库：否。"
    ),
)
def get_me(
    current_admin: AdminUser = Depends(get_current_admin),
) -> ApiResponse:
    """Get current admin info endpoint."""
    return ApiResponse(data=AdminInfo.model_validate(current_admin))
