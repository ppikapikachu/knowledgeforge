"""Authentication service."""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.core.exceptions import AuthenticationException, ResourceNotFoundException
from app.core.security import (
    create_access_token,
    hash_password,
    verify_password,
)
from app.models.admin import AdminUser
from app.repositories.admin_repository import AdminRepository


class AuthService:
    """Service for authentication business logic."""

    def __init__(self, db: Session):
        self.db = db
        self.admin_repo = AdminRepository(db)

    def login(self, username: str, password: str) -> dict:
        """Authenticate admin and return JWT token."""
        admin = self.admin_repo.get_by_username(username)
        if not admin:
            raise AuthenticationException("用户名或密码错误")

        if admin.status == 0:
            raise AuthenticationException("账号已被禁用")

        if not verify_password(password, admin.password_hash):
            raise AuthenticationException("用户名或密码错误")

        # Update last login time
        self.admin_repo.update_last_login(admin.id)
        self.db.commit()

        # Create token
        access_token = create_access_token(subject=admin.id)

        return {
            "access_token": access_token,
            "token_type": "bearer",
        }

    def get_admin_info(self, admin_id: int) -> AdminUser:
        """Get admin user information."""
        admin = self.admin_repo.get_by_id(admin_id)
        if not admin:
            raise ResourceNotFoundException("管理员")
        return admin

    def create_admin(
        self,
        username: str,
        password: str,
        nickname: str = "管理员",
    ) -> AdminUser:
        """Create a new admin user."""
        # Check if username already exists
        existing = self.admin_repo.get_by_username(username)
        if existing:
            raise AuthenticationException("用户名已存在")

        password_hash = hash_password(password)
        return self.admin_repo.create(
            username=username,
            password_hash=password_hash,
            nickname=nickname,
        )
