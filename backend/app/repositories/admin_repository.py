"""Admin user repository."""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.models.admin import AdminUser


class AdminRepository:
    """Repository for admin user database operations."""

    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, admin_id: int) -> Optional[AdminUser]:
        """Get admin by ID."""
        return self.db.query(AdminUser).filter(AdminUser.id == admin_id).first()

    def get_by_username(self, username: str) -> Optional[AdminUser]:
        """Get admin by username."""
        return (
            self.db.query(AdminUser)
            .filter(AdminUser.username == username)
            .first()
        )

    def update_last_login(self, admin_id: int) -> None:
        """Update last login time."""
        admin = self.get_by_id(admin_id)
        if admin:
            admin.last_login_at = datetime.now(timezone.utc)
            self.db.flush()

    def create(
        self,
        username: str,
        password_hash: str,
        nickname: str = "管理员",
    ) -> AdminUser:
        """Create a new admin user."""
        admin = AdminUser(
            username=username,
            password_hash=password_hash,
            nickname=nickname,
        )
        self.db.add(admin)
        self.db.flush()
        return admin
