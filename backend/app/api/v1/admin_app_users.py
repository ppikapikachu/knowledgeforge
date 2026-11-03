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

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import ResourceNotFoundException, ValidationException
from app.dependencies.auth import get_current_admin
from app.models.admin import AdminUser
from app.models.app_user import AppUser
from app.models.user_auth_session import UserAuthSession
from app.schemas.common import ApiResponse
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
    description="按关键字/状态筛选普通用户，分页返回（不含令牌与密码）。",
)
def list_app_users(
    keyword: str = Query(default=None, description="账号/昵称模糊匹配"),
    status: str = Query(default=None, description="active/disabled/deleted，不传=全部"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
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
    description="查看单个普通用户；不存在返回 40401。",
)
def get_app_user(
    user_id: int,
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
        "仅允许 active↔disabled（deleted 不可恢复）。禁用立即撤销该用户全部 "
        "refresh 会话并拒绝后续登录/刷新；不删除任何历史数据。"
    ),
)
def update_app_user_status(
    user_id: int,
    request: dict,
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
