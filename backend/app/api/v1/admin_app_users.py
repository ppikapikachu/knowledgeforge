"""普通用户管理 API（管理员，docs/14 补充 §13，P2）。

仅三个只读/状态接口：
    - GET  /admin/app-users        列表（keyword/status 筛选、分页）
    - GET  /admin/app-users/{id}   详情（含活跃会话数，不含令牌/密码）
    - PATCH /admin/app-users/{id}/status  启用/禁用（仅 active↔disabled）
        禁用立即撤销该用户全部 refresh 会话（revoked_at 置位），
        后续登录/刷新一律拒绝；不删除任何历史数据（答题/评论/试卷保留）。

安全：响应一律不含 password_hash / refresh_token_hash。
"""

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import ResourceNotFoundException, ValidationException
from app.dependencies.auth import get_current_admin
from app.models.admin import AdminUser
from app.models.app_user import AppUser
from app.models.user_auth_session import UserAuthSession
from app.schemas.common import ApiErrorResponse, ApiResponse, PaginatedData
from app.schemas.user import AdminAppUserItem, AdminAppUserResponse, AppUserStatusResponse
from app.utils.response import paginated_response

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/app-users", tags=["用户管理"])


def _user_payload(db: Session, user: AppUser) -> dict:
    """安全序列化：不含 password_hash / refresh_token_hash。"""
    active_sessions = (
        db.query(UserAuthSession)
        .filter(
            UserAuthSession.app_user_id == user.id,
            UserAuthSession.revoked_at.is_(None),
        )
        .count()
    )
    return {
        "id": user.id,
        "account": user.account,
        "nickname": user.nickname,
        "avatar": user.avatar,
        "status": user.status,
        "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
        "deleted_at": user.deleted_at.isoformat() if user.deleted_at else None,
        "active_session_count": active_sessions,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


@router.get(
    "",
    summary="普通用户列表（管理员）",
    description=(
        "按关键字/状态筛选普通用户，分页返回。序列化为安全白名单，绝不含 password_hash/refresh_token_hash。\n\n"
        "调用时机：管理端后台「用户管理」列表页。\n\n"
        "返回 data（分页信封）：items: 用户数组，每项 {id: 用户 ID, account: 登录账号, nickname: 昵称, avatar: 头像 URL, "
        "status: 账号状态（active|disabled|deleted）, last_login_at: 最后登录时间, deleted_at: 注销时间（可空）, "
        "active_session_count: 未撤销的 refresh 会话数, created_at: 注册时间}；page: 当前页；page_size: 每页条数；total: 总条数。\n\n"
        "权限：管理员令牌。\n\n"
        "幂等性：只读接口，无副作用。\n\n"
        "写库：否。"
    ),
    response_model=ApiResponse[PaginatedData[AdminAppUserItem]],
    responses={
        400: {"model": ApiErrorResponse, "description": "业务错误（HTTP 400，envelope code 区分）：40001 参数校验（status 取值非法）/ 40101 未认证（管理员令牌无效/过期/管理员不存在/已禁用）"},
        403: {"model": ApiErrorResponse, "description": "未提供或非法 Authorization 请求头（HTTP 403）"},
        422: {"model": ApiErrorResponse, "description": "请求参数格式校验失败（HTTP 422，code 42201）"},
        500: {"model": ApiErrorResponse, "description": "系统内部错误（HTTP 500，code 50000）"},
    },
)
def list_app_users(
    keyword: str = Query(default=None, description="关键字，对账号/昵称做模糊匹配；不传=不过滤"),
    status: str = Query(default=None, description="账号状态筛选，取值 active/disabled/deleted；不传=全部"),
    page: int = Query(default=1, ge=1, description="页码，从 1 开始；不传=默认第 1 页"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页返回条数；不传=默认 20，取值 1~100"),
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    """普通用户列表。"""
    query = db.query(AppUser)
    if keyword:
        like = f"%{keyword.strip()}%"
        query = query.filter(
            (AppUser.account.like(like)) | (AppUser.nickname.like(like))
        )
    if status:
        if status not in ("active", "disabled", "deleted"):
            raise ValidationException("status 必须是 active/disabled/deleted")
        query = query.filter(AppUser.status == status)

    total = query.count()
    items = (
        query.order_by(AppUser.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return paginated_response(
        items=[_user_payload(db, u) for u in items],
        total=total, page=page, page_size=page_size,
    )


@router.get(
    "/{user_id}",
    summary="普通用户详情（管理员）",
    description=(
        "查看单个普通用户的账号信息。\n\n"
        "调用时机：管理端用户详情抽屉/页面。\n\n"
        "返回 data：id: 用户 ID；account: 登录账号；nickname: 昵称；avatar: 头像 URL；status: 账号状态（active|disabled|deleted）；"
        "last_login_at: 最后登录时间（可空）；deleted_at: 注销时间（可空）；active_session_count: 未撤销的 refresh 会话数；"
        "created_at: 注册时间。\n\n"
        "权限：管理员令牌。\n\n"
        "幂等性：只读接口，无副作用。不存在返回业务码 40401。\n\n"
        "写库：否。"
    ),
    response_model=ApiResponse[AdminAppUserResponse],
    responses={
        400: {"model": ApiErrorResponse, "description": "业务错误（HTTP 400，envelope code 区分）：40401 不存在（普通用户不存在）/ 40101 未认证（管理员令牌无效/过期/管理员不存在/已禁用）"},
        403: {"model": ApiErrorResponse, "description": "未提供或非法 Authorization 请求头（HTTP 403）"},
        500: {"model": ApiErrorResponse, "description": "系统内部错误（HTTP 500，code 50000）"},
    },
)
def get_app_user(
    user_id: int = Path(description="普通用户 ID，对应 app_user 表主键；不存在返回业务错误 40401"),
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
) -> ApiResponse:
    """普通用户详情。"""
    user = db.query(AppUser).filter(AppUser.id == user_id).first()
    if not user:
        raise ResourceNotFoundException("普通用户不存在", user_id)
    return ApiResponse(data=_user_payload(db, user))


@router.patch(
    "/{user_id}/status",
    summary="启用/禁用普通用户（管理员）",
    description=(
        "启用/禁用普通用户账号。仅允许 active↔disabled（deleted 不可恢复）。"
        "禁用立即撤销该用户全部 refresh 会话并拒绝后续登录/刷新；不删除任何历史数据。\n\n"
        "调用时机：管理端用户列表/详情的启用、禁用操作。\n\n"
        "请求体：status: 目标状态，仅 active|disabled（其他值业务码 40001）；reason: 操作原因（可空，用于审计记录）。\n\n"
        "返回 data：id: 用户ID、status: 变更后状态（active|disabled）、revoked_sessions: 本次操作撤销的 refresh 会话数（禁用时为撤销数，启用时为 0）。\n\n"
        "权限：管理员令牌。\n\n"
        "幂等性：非幂等——状态未变化时返回业务码 40001（状态未变化），重复禁用不会重复撤销已撤销会话。\n\n"
        "写库：是（更新 app_user.status；禁用时批量撤销 user_auth_session）。"
    ),
    response_model=ApiResponse[AppUserStatusResponse],
    responses={
        400: {"model": ApiErrorResponse, "description": "业务错误（HTTP 400，envelope code 区分）：40001 参数校验（status 非法/已注销不可改/状态未变化）/ 40401 不存在（普通用户不存在）/ 40101 未认证（管理员令牌无效/过期/管理员不存在/已禁用）"},
        403: {"model": ApiErrorResponse, "description": "未提供或非法 Authorization 请求头（HTTP 403）"},
        422: {"model": ApiErrorResponse, "description": "请求参数格式校验失败（HTTP 422，code 42201）"},
        500: {"model": ApiErrorResponse, "description": "系统内部错误（HTTP 500，code 50000）"},
    },
)
def update_app_user_status(
    request: dict,
    user_id: int = Path(description="普通用户 ID，对应 app_user 表主键；不存在返回业务错误 40401"),
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
) -> ApiResponse:
    """启用/禁用普通用户。"""
    user = db.query(AppUser).filter(AppUser.id == user_id).first()
    if not user:
        raise ResourceNotFoundException("普通用户不存在", user_id)

    new_status = request.get("status")
    reason = (request.get("reason") or "").strip()
    if new_status not in ("active", "disabled"):
        raise ValidationException("status 只允许 active 或 disabled")
    if user.status == "deleted":
        raise ValidationException("已注销账号不可修改状态")
    if user.status == new_status:
        raise ValidationException("状态未变化")

    revoked = 0
    if new_status == "disabled":
        # 禁用：立即撤销全部 refresh 会话；历史数据不删除
        sessions = db.query(UserAuthSession).filter(
            UserAuthSession.app_user_id == user.id,
            UserAuthSession.revoked_at.is_(None),
        ).all()
        for s in sessions:
            s.revoked_at = datetime.utcnow()
            revoked += 1

    user.status = new_status
    db.commit()
    db.refresh(user)

    logger.info(
        "管理员 %s 将普通用户 %s 状态改为 %s（撤销会话 %d，原因：%s）",
        current_admin.id, user.id, new_status, revoked, reason or "-",
    )
    return ApiResponse(data={
        "id": user.id,
        "status": user.status,
        "revoked_sessions": revoked,
    })
