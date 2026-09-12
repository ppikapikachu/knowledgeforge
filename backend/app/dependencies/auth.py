"""Authentication dependencies."""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import AuthenticationException
from app.core.security import decode_access_token
from app.models.admin import AdminUser
from app.repositories.admin_repository import AdminRepository

security_scheme = HTTPBearer()


def get_current_admin(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
    db: Session = Depends(get_db),
) -> AdminUser:
    """Dependency to get current authenticated admin from JWT token."""
    token = credentials.credentials
    payload = decode_access_token(token)

    if payload is None:
        raise AuthenticationException("无效的访问令牌")

    admin_id = payload.get("sub")
    if admin_id is None:
        raise AuthenticationException("无效的访问令牌")

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
