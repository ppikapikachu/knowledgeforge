"""普通用户服务：注册/登录/刷新/退出/资料维护。

设计要点：
    - 账号服务端规范化（去首尾空格 + 小写），唯一性基于规范化结果
    - 密码哈希复用 app.core.security（bcrypt），禁止明文
    - Refresh Token 轮换：每次刷新旧会话立即撤销，DB 只存 SHA-256 哈希
    - 登录失败消息统一，不暴露账号是否存在
    - 登录频率保护：进程内滑动窗口（不引入 Redis）
"""

import threading
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import Optional, Tuple

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import (
    AuthenticationException,
    DuplicateException,
    ValidationException,
)
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_access_token,
    hash_password,
    hash_token,
    verify_password,
)
from app.models.app_user import AppUser
from app.models.user_auth_session import UserAuthSession

LOGIN_FAIL_MESSAGE = "账号或密码错误"
_ACCOUNT_RULE_MSG = "账号仅允许字母、数字、_.-@，长度 4-64"
_DUMMY_HASH = hash_password("dummy-password-for-timing-equalization")

# 登录频率保护（进程内，滑动窗口）
_LOGIN_WINDOW_SECONDS = 60
_LOGIN_MAX_ATTEMPTS = 10
_login_attempts: dict = defaultdict(deque)
_login_lock = threading.Lock()


def normalize_account(account: str) -> str:
    """账号规范化：去首尾空格 + 小写。"""
    return (account or "").strip().lower()


def _validate_account_format(account: str) -> None:
    if not (4 <= len(account) <= 64):
        raise ValidationException(_ACCOUNT_RULE_MSG)
    allowed = set("abcdefghijklmnopqrstuvwxyz0123456789_.-@")
    if not set(account) <= allowed:
        raise ValidationException(_ACCOUNT_RULE_MSG)


def _throttle_login(account: str) -> None:
    now = time.monotonic()
    with _login_lock:
        q = _login_attempts[account]
        while q and now - q[0] > _LOGIN_WINDOW_SECONDS:
            q.popleft()
        if len(q) >= _LOGIN_MAX_ATTEMPTS:
            raise ValidationException("登录尝试过于频繁，请稍后再试")
        q.append(now)


class UserService:
    """普通用户账号服务。"""

    def __init__(self, db: Session):
        self.db = db

    # ---------- 注册 / 登录 ----------

    def register(
        self,
        account: str,
        password: str,
        nickname: Optional[str] = None,
        avatar: Optional[str] = None,
    ) -> AppUser:
        acc = normalize_account(account)
        _validate_account_format(acc)
        if not (6 <= len(password or "") <= 64):
            raise ValidationException("密码长度须在 6-64 之间")

        exists = self.db.query(AppUser).filter(AppUser.account == acc).first()
        if exists:
            raise DuplicateException("账号已存在")

        user = AppUser(
            account=acc,
            password_hash=hash_password(password),
            nickname=(nickname or acc).strip()[:64],
            avatar=(avatar.strip() if avatar else None),
            status="active",
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def login(
        self,
        account: str,
        password: str,
        device_id: Optional[str] = None,
        device_name: Optional[str] = None,
    ) -> dict:
        acc = normalize_account(account)
        _throttle_login(acc)

        user = self.db.query(AppUser).filter(AppUser.account == acc).first()
        if user is None:
            # 时间侧信道均衡：用户不存在也执行一次哈希校验
            verify_password(password or "", _DUMMY_HASH)
            raise AuthenticationException(LOGIN_FAIL_MESSAGE)

        if user.status != "active" or not verify_password(password or "", user.password_hash):
            # 统一错误消息：禁用/删除/密码错误一律不暴露账号存在性
            raise AuthenticationException(LOGIN_FAIL_MESSAGE)

        session, refresh_token = self._create_session(user, device_id, device_name)
        user.last_login_at = datetime.utcnow()
        self.db.commit()
        return self._token_payload(user, refresh_token)

    # ---------- 刷新 / 退出 ----------

    def refresh(self, refresh_token: str) -> dict:
        payload = decode_access_token(refresh_token or "")
        if payload is None or payload.get("token_type") != "user_refresh":
            raise AuthenticationException("无效的刷新令牌")

        token_hash = hash_token(refresh_token)
        session = (
            self.db.query(UserAuthSession)
            .filter(UserAuthSession.refresh_token_hash == token_hash)
            .first()
        )
        if session is None or session.revoked_at is not None:
            raise AuthenticationException("刷新令牌已失效，请重新登录")
        if session.expires_at < datetime.utcnow():
            raise AuthenticationException("刷新令牌已过期，请重新登录")

        user = self.db.query(AppUser).filter(AppUser.id == session.app_user_id).first()
        if user is None or user.status != "active":
            raise AuthenticationException("账号已被禁用")

        # 轮换：旧会话立即撤销，签发新会话
        session.revoked_at = datetime.utcnow()
        new_session, new_refresh = self._create_session(
            user, session.device_id, session.device_name
        )
        self.db.commit()
        return self._token_payload(user, new_refresh)

    def logout(self, refresh_token: str) -> None:
        """退出登录：只撤销当前会话，不影响其他设备。"""
        token_hash = hash_token(refresh_token or "")
        session = (
            self.db.query(UserAuthSession)
            .filter(UserAuthSession.refresh_token_hash == token_hash)
            .first()
        )
        if session is not None and session.revoked_at is None:
            session.revoked_at = datetime.utcnow()
            self.db.commit()

    # ---------- 资料 ----------

    def update_profile(
        self,
        user: AppUser,
        nickname: Optional[str] = None,
        avatar: Optional[str] = None,
    ) -> AppUser:
        changed = False
        if nickname is not None:
            user.nickname = nickname.strip()[:64]
            changed = True
        if avatar is not None:
            user.avatar = (avatar.strip() or None)
            changed = True
        if changed:
            self.db.commit()
            self.db.refresh(user)
        return user

    # ---------- 内部 ----------

    def _create_session(
        self,
        user: AppUser,
        device_id: Optional[str],
        device_name: Optional[str],
    ) -> Tuple[UserAuthSession, str]:
        placeholder = UserAuthSession(
            app_user_id=user.id,
            refresh_token_hash="pending",
            device_id=(device_id or None),
            device_name=(device_name or None),
            expires_at=datetime.utcnow() + timedelta(days=settings.JWT_REFRESH_EXPIRE_DAYS),
        )
        self.db.add(placeholder)
        self.db.flush()  # 取得 session.id 后才能把 sid 签进 token

        refresh_token = create_refresh_token(user.id, placeholder.id)
        placeholder.refresh_token_hash = hash_token(refresh_token)
        placeholder.last_used_at = datetime.utcnow()
        self.db.flush()
        return placeholder, refresh_token

    @staticmethod
    def _token_payload(user: AppUser, refresh_token: str) -> dict:
        access_token = create_access_token(
            user.id,
            expires_delta=timedelta(minutes=settings.USER_ACCESS_TOKEN_EXPIRE_MINUTES),
            token_type="user_access",
        )
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "Bearer",
            "expires_in": settings.USER_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            "user": {
                "id": user.id,
                "account": user.account,
                "nickname": user.nickname,
                "avatar": user.avatar,
            },
        }
