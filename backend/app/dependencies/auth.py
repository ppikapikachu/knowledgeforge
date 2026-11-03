"""Authentication dependencies."""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import AuthenticationException
from app.core.security import decode_access_token
from app.models.admin import AdminUser
from app.models.app_user import AppUser
from app.repositories.admin_repository import AdminRepository

security_scheme = HTTPBearer()


def _decode_and_check(token: str, allowed_types: tuple) -> dict:
    """Decode JWT and enforce token_type（两类主体 ID 空间重叠，不能只靠 sub）。"""
    payload = decode_access_token(token)
    if payload is None:
        raise AuthenticationException("无效的访问令牌")
    token_type = payload.get("token_type")
    # 旧 token 无 token_type 字段：历史签发的管理端 token 按 admin_access 处理
    if token_type is None:
        token_type = "admin_access"
    if token_type not in allowed_types:
        raise AuthenticationException("无效的访问令牌")
    if payload.get("sub") is None:
        raise AuthenticationException("无效的访问令牌")
    return payload


def get_current_admin(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
    db: Session = Depends(get_db),
) -> AdminUser:
    """Dependency to get current authenticated admin from JWT token."""
    token = credentials.credentials
    payload = _decode_and_check(token, ("admin_access",))

    admin_id = payload.get("sub")

    try:
        admin_id = int(admin_id)
    except (ValueError, TypeError):
        raise AuthenticationException("无效的访问令牌")

    admin_repo = AdminRepository(db)
    admin = admin_repo.get_by_id(admin_id)

    if admin is None:
        raise AuthenticationException("管理员不存在")

    if admin.status == 0:
        raise AuthenticationException("账号已被禁用")

    return admin


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
    db: Session = Depends(get_db),
) -> AppUser:
    """Dependency to get current authenticated app user from JWT token.

    只接受 user_access token；客户端不得自行传 app_user_id。
    """
    token = credentials.credentials
    payload = _decode_and_check(token, ("user_access",))

    try:
        user_id = int(payload.get("sub"))
    except (ValueError, TypeError):
        raise AuthenticationException("无效的访问令牌")

    user = db.query(AppUser).filter(AppUser.id == user_id).first()
    if user is None:
        raise AuthenticationException("用户不存在")
    if user.status == "disabled":
        raise AuthenticationException("账号已被禁用")
    if user.status == "deleted":
        raise AuthenticationException("用户不存在")

    return user


def get_current_principal(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
    db: Session = Depends(get_db),
):
    """接受管理员或普通用户任一 token，返回 (kind, principal)。

    kind ∈ {"admin", "user"}；用于两类主体都可访问的只读聚合接口
    （如题目统计）。历史 token 无 token_type 按 admin_access 处理。
    """
    token = credentials.credentials
    payload = _decode_and_check(token, ("admin_access", "user_access"))
    try:
        subject_id = int(payload.get("sub"))
    except (ValueError, TypeError):
        raise AuthenticationException("无效的访问令牌")

    token_type = payload.get("token_type") or "admin_access"
    if token_type == "admin_access":
        admin = AdminRepository(db).get_by_id(subject_id)
        if admin is None:
            raise AuthenticationException("管理员不存在")
        if admin.status == 0:
            raise AuthenticationException("账号已被禁用")
        return ("admin", admin)

    user = db.query(AppUser).filter(AppUser.id == subject_id).first()
    if user is None:
        raise AuthenticationException("用户不存在")
    if user.status == "disabled":
        raise AuthenticationException("账号已被禁用")
    if user.status == "deleted":
        raise AuthenticationException("用户不存在")
    return ("user", user)
