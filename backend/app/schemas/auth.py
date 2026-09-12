"""Authentication schemas."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    """Login request schema."""

    username: str = Field(
        ..., min_length=1, max_length=50, description="登录账号"
    )
    password: str = Field(
        ..., min_length=1, max_length=128, description="密码"
    )


class TokenResponse(BaseModel):
    """JWT token response schema."""

    access_token: str = Field(description="访问令牌")
    token_type: str = Field(default="bearer", description="令牌类型")


class AdminInfo(BaseModel):
    """Admin user info response schema."""

    id: int = Field(description="管理员ID")
    username: str = Field(description="登录账号")
    nickname: str = Field(description="显示昵称")
    avatar: Optional[str] = Field(default=None, description="头像URL")
    status: int = Field(description="状态")
    last_login_at: Optional[datetime] = Field(
        default=None, description="最后登录时间"
    )
    created_at: datetime = Field(description="创建时间")

    class Config:
        from_attributes = True
