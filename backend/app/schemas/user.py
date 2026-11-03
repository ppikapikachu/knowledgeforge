"""普通用户相关请求/响应 Schema。"""

from typing import Optional

from pydantic import BaseModel, Field


class UserRegisterRequest(BaseModel):
    """注册请求。"""

    account: str = Field(..., min_length=4, max_length=64, description="登录账号")
    password: str = Field(..., min_length=6, max_length=64, description="密码")
    nickname: Optional[str] = Field(default=None, max_length=64, description="昵称")
    avatar: Optional[str] = Field(default=None, max_length=512, description="头像 URL")


class UserLoginRequest(BaseModel):
    """登录请求。"""

    account: str = Field(..., min_length=1, max_length=64, description="登录账号")
    password: str = Field(..., min_length=1, max_length=64, description="密码")
    device_id: Optional[str] = Field(default=None, max_length=128, description="设备标识")
    device_name: Optional[str] = Field(default=None, max_length=128, description="设备名称")


class UserRefreshRequest(BaseModel):
    """刷新令牌请求。"""

    refresh_token: str = Field(..., min_length=1, description="Refresh Token")


class UserLogoutRequest(BaseModel):
    """退出登录请求。"""

    refresh_token: str = Field(..., min_length=1, description="Refresh Token")


class UserUpdateRequest(BaseModel):
    """资料修改请求（只允许昵称/头像）。"""

    nickname: Optional[str] = Field(default=None, max_length=64, description="昵称")
    avatar: Optional[str] = Field(default=None, max_length=512, description="头像 URL")
