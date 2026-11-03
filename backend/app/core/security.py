"""Security utilities: password hashing and JWT tokens."""

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import bcrypt
import jwt

from app.core.config import settings


def hash_password(password: str) -> str:
    """Hash a plain text password using bcrypt."""
    password_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain text password against its hash."""
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8"),
        )
    except Exception:
        return False


def create_access_token(
    subject: Any,
    expires_delta: Optional[timedelta] = None,
    token_type: str = "admin_access",
) -> str:
    """Create a JWT access token.

    token_type 区分签发对象（admin_access/user_access/user_refresh），
    不能只靠 sub 猜身份：两类主体 ID 空间重叠。
    """
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.JWT_EXPIRE_MINUTES
        )

    to_encode = {
        "sub": str(subject),
        "token_type": token_type,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }

    encoded_jwt = jwt.encode(
        to_encode,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    return encoded_jwt


def create_refresh_token(subject: Any, session_id: int) -> str:
    """Create a long-lived refresh token bound to an auth session row.

    payload 携带 sid（会话行 ID），轮换/撤销在 user_auth_session 落库，
    DB 只保存 token 的 SHA-256 哈希。
    """
    expire = datetime.now(timezone.utc) + timedelta(
        days=settings.JWT_REFRESH_EXPIRE_DAYS
    )
    to_encode = {
        "sub": str(subject),
        "sid": session_id,
        "token_type": "user_refresh",
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(
        to_encode,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


def hash_token(token: str) -> str:
    """SHA-256 hex of a token string (refresh token storage form)."""
    import hashlib

    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def decode_access_token(token: str) -> Optional[dict]:
    """Decode and validate a JWT access token."""
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None
