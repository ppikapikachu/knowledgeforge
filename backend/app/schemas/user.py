"""普通用户相关请求/响应 Schema。"""

from typing import Optional

from pydantic import BaseModel, Field


class UserRegisterRequest(BaseModel):
    """注册请求。"""

    account: str = Field(..., min_length=4, max_length=64, description="登录账号（4-64 字符，服务端规范化为小写，仅允许字母/数字/._-@）")
    password: str = Field(..., min_length=6, max_length=64, description="登录密码（6-64 字符，服务端仅存 bcrypt 哈希）")
    nickname: Optional[str] = Field(default=None, max_length=64, description="昵称（可空，展示用）")
    avatar: Optional[str] = Field(default=None, max_length=512, description="头像 URL（可空）")


class UserLoginRequest(BaseModel):
    """登录请求。"""

    account: str = Field(..., min_length=1, max_length=64, description="登录账号（大小写不敏感，服务端规范化匹配）")
    password: str = Field(..., min_length=1, max_length=64, description="登录密码")
    device_id: Optional[str] = Field(default=None, max_length=128, description="设备标识（可空，用于多设备会话管理）")
    device_name: Optional[str] = Field(default=None, max_length=128, description="设备名称（可空，仅作会话展示）")


class UserRefreshRequest(BaseModel):
    """刷新令牌请求。"""

    refresh_token: str = Field(..., min_length=1, description="刷新令牌（登录/注册时下发；使用后旧令牌立即作废，不可重放）")


class UserLogoutRequest(BaseModel):
    """退出登录请求。"""

    refresh_token: str = Field(..., min_length=1, description="要撤销的刷新令牌（仅撤销该令牌对应会话，不影响其他设备）")


class UserUpdateRequest(BaseModel):
    """资料修改请求（只允许昵称/头像）。"""

    nickname: Optional[str] = Field(default=None, max_length=64, description="新昵称（可空，不传=不变）")
    avatar: Optional[str] = Field(default=None, max_length=512, description="新头像 URL（可空，不传=不变）")


# ==================== 响应模型 ====================


class UserProfileResponse(BaseModel):
    """data 载荷：普通用户基础资料（同时作为令牌响应内嵌的 user 对象）。"""

    id: int = Field(description="用户 ID（app_user 表主键）")
    account: str = Field(description="登录账号（服务端规范化为小写）")
    nickname: Optional[str] = Field(default=None, description="昵称（可空）")
    avatar: Optional[str] = Field(default=None, description="头像 URL（可空）")


class UserTokenResponse(BaseModel):
    """data 载荷：注册/登录/刷新成功后返回的令牌对与用户信息。"""

    access_token: str = Field(description="访问令牌（user_access，JWT，有效期 USER_ACCESS_TOKEN_EXPIRE_MINUTES 分钟，默认 30）")
    refresh_token: str = Field(description="刷新令牌（长期凭证，仅存哈希，用于 /users/refresh 换取新令牌对；使用后旧令牌立即作废）")
    token_type: str = Field(description="令牌类型，固定 Bearer")
    expires_in: int = Field(description="access_token 有效期秒数（USER_ACCESS_TOKEN_EXPIRE_MINUTES*60，如 1800）")
    user: UserProfileResponse = Field(description="当前登录用户基础资料")


class UserAnswerSummary(BaseModel):
    """我的统计 - 答题汇总（answer_summary）。"""

    graded_submission_count: int = Field(description="已判分提交次数（有效 graded 提交数）")
    correct_submission_count: int = Field(description="判分正确次数")
    accuracy: Optional[float] = Field(default=None, description="整体正确率（正确/已判分，保留 4 位小数；样本不足为 null）")
    first_attempt_accuracy: Optional[float] = Field(default=None, description="首次作答正确率（每题只取首次 graded 提交；样本不足为 null）")
    answered_question_count: int = Field(description="已作答（已判分）的独立题目数")
    display_status: str = Field(description="统计口径状态（available=样本充足 / insufficient_samples=样本不足）")
    sample_threshold: int = Field(description="样本量阈值（QUESTION_STATISTICS_MIN_SAMPLES，默认 20）")


class UserPracticeSummary(BaseModel):
    """我的统计 - 练习汇总（practice_summary）。"""

    session_total: int = Field(description="累计练习会话数")
    session_completed: int = Field(description="已完成会话数（status=completed）")
    session_in_progress: int = Field(description="进行中会话数（status=in_progress）")
    session_abandoned: int = Field(description="已放弃会话数（status=abandoned）")
    total_duration_ms: int = Field(description="已完成会话累计用时（毫秒）")


class UserStatisticsResponse(BaseModel):
    """data 载荷：我的练习/答题统计（/users/me/statistics）。"""

    answer_summary: UserAnswerSummary = Field(description="答题汇总（统一统计口径）")
    practice_summary: UserPracticeSummary = Field(description="练习汇总")


class AdminAppUserResponse(BaseModel):
    """data 载荷：普通用户的管理端安全序列化（绝不含 password_hash/refresh_token_hash）。"""

    id: int = Field(description="用户 ID（app_user 表主键）")
    account: str = Field(description="登录账号")
    nickname: Optional[str] = Field(default=None, description="昵称（可空）")
    avatar: Optional[str] = Field(default=None, description="头像 URL（可空）")
    status: str = Field(description="账号状态（active=正常 / disabled=禁用 / deleted=已注销）")
    last_login_at: Optional[str] = Field(default=None, description="最后登录时间（ISO 8601 字符串，可空）")
    deleted_at: Optional[str] = Field(default=None, description="注销时间（ISO 8601 字符串，可空）")
    active_session_count: int = Field(description="未撤销的 refresh 会话数")
    created_at: Optional[str] = Field(default=None, description="注册时间（ISO 8601 字符串，可空）")


class AdminAppUserItem(AdminAppUserResponse):
    """items 数组元素：普通用户条目（字段同 AdminAppUserResponse）。"""


class AppUserStatusResponse(BaseModel):
    """data 载荷：启用/禁用普通用户结果（PATCH /admin/app-users/{user_id}/status）。"""

    id: int = Field(description="用户 ID")
    status: str = Field(description="变更后的账号状态（active=正常 / disabled=禁用）")
    revoked_sessions: int = Field(description="本次禁用操作撤销的 refresh 会话数（启用时为 0）")
