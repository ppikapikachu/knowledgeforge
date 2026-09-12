"""Script to create an admin user."""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.repositories.admin_repository import AdminRepository


def create_admin(username: str, password: str, nickname: str = "管理员") -> None:
    """Create a new admin user."""
    db = SessionLocal()
    try:
        repo = AdminRepository(db)

        # Check if admin already exists
        existing = repo.get_by_username(username)
        if existing:
            print(f"错误: 用户名 '{username}' 已存在")
            return

        password_hash = hash_password(password)
        admin = repo.create(
            username=username,
            password_hash=password_hash,
            nickname=nickname,
        )
        db.commit()
        print(f"成功创建管理员: id={admin.id}, username={admin.username}")
    except Exception as e:
        db.rollback()
        print(f"创建管理员失败: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="创建管理员账号")
    parser.add_argument("--username", default="admin", help="用户名 (默认: admin)")
    parser.add_argument("--password", default="admin123", help="密码 (默认: admin123)")
    parser.add_argument("--nickname", default="管理员", help="昵称 (默认: 管理员)")

    args = parser.parse_args()

    create_admin(
        username=args.username,
        password=args.password,
        nickname=args.nickname,
    )
