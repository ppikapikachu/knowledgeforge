"""普通用户认证与资料 API。

    POST   /api/v1/users/register   注册
    POST   /api/v1/users/login      登录
    POST   /api/v1/users/refresh    刷新令牌（轮换）
    POST   /api/v1/users/logout     退出登录（只撤销当前会话）
    GET    /api/v1/users/me         获取资料
    PATCH  /api/v1/users/me         修改资料（昵称/头像）
"""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.app_user import AppUser
from app.schemas.common import ApiErrorResponse, ApiResponse, DataNull
from app.schemas.user import (
    UserLoginRequest,
    UserLogoutRequest,
    UserRefreshRequest,
    UserRegisterRequest,
    UserProfileResponse,
    UserStatisticsResponse,
    UserTokenResponse,
    UserUpdateRequest,
)
from app.services.user_service import UserService

router = APIRouter(prefix="/users", tags=["普通用户"])


def _user_dict(user: AppUser) -> dict:
    return {
        "id": user.id,
        "account": user.account,
        "nickname": user.nickname,
        "avatar": user.avatar,
    }


@router.post(
    "/register",
    summary="普通用户注册",
    description="注册普通用户账号。账号服务端规范化（去空格+小写），重复注册返回冲突。"
                "注册成功直接返回登录令牌（自动登录）。\n\n"
                "调用时机：App/H5 注册页提交表单。\n\n"
                "返回 data：access_token: 访问令牌（user_access，有效期 USER_ACCESS_TOKEN_EXPIRE_MINUTES 分钟，默认 30）；"
                "refresh_token: 刷新令牌（长期凭证，仅存哈希，用于 /users/refresh）；token_type: 固定 `Bearer`；"
                "expires_in: access_token 有效期秒数；user: {id: 用户 ID, account: 登录账号, nickname: 昵称, avatar: 头像 URL}。\n\n"
                "权限：公开接口。\n\n"
                "幂等性：非幂等（每次调用创建新账号）；同账号重复注册返回 40901。\n\n"
                "写库：是（新增 app_user 行与首个 user_auth_session）。",
    response_model=ApiResponse[UserTokenResponse],
    responses={
        400: {"model": ApiErrorResponse, "description": "业务错误（HTTP 400，envelope code 区分）：40001 参数校验（账号格式非法/密码长度须在 6-64 之间）/ 40901 冲突（账号已存在）"},
        422: {"model": ApiErrorResponse, "description": "请求参数格式校验失败（HTTP 422，code 42201）"},
        500: {"model": ApiErrorResponse, "description": "系统内部错误（HTTP 500，code 50000）"},
    },
)
def register(
    request: UserRegisterRequest,
    db: Session = Depends(get_db),
) -> ApiResponse:
    user = UserService(db).register(
        account=request.account,
        password=request.password,
        nickname=request.nickname,
        avatar=request.avatar,
    )
    tokens = UserService(db)._token_payload(user, _issue_refresh(db, user))
    return ApiResponse(message="注册成功", data=tokens)


@router.post(
    "/login",
    summary="普通用户登录",
    description="账号密码登录。失败消息统一为「账号或密码错误」，不暴露账号是否存在。\n\n"
                "调用时机：App/H5 登录页提交表单。\n\n"
                "返回 data：access_token: 访问令牌（user_access）；refresh_token: 刷新令牌（同设备重复登录生成新会话）；"
                "token_type: 固定 `Bearer`；expires_in: access_token 有效期秒数；"
                "user: {id: 用户 ID, account: 登录账号, nickname: 昵称, avatar: 头像 URL}。\n\n"
                "权限：公开接口。\n\n"
                "幂等性：非幂等（每次登录创建新会话；并发频繁登录会触发限频保护 40001）。\n\n"
                "写库：是（新增 user_auth_session、更新 last_login_at）。",
    response_model=ApiResponse[UserTokenResponse],
    responses={
        400: {"model": ApiErrorResponse, "description": "业务错误（HTTP 400，envelope code 区分）：40001 参数校验（登录尝试过于频繁）/ 40101 未认证（账号或密码错误）"},
        422: {"model": ApiErrorResponse, "description": "请求参数格式校验失败（HTTP 422，code 42201）"},
        500: {"model": ApiErrorResponse, "description": "系统内部错误（HTTP 500，code 50000）"},
    },
)
def login(
    request: UserLoginRequest,
    db: Session = Depends(get_db),
) -> ApiResponse:
    payload = UserService(db).login(
        account=request.account,
        password=request.password,
        device_id=request.device_id,
        device_name=request.device_name,
    )
    return ApiResponse(message="登录成功", data=payload)


@router.post(
    "/refresh",
    summary="刷新令牌",
    description="用 Refresh Token 换取新令牌对。旧 Refresh Token 用后即撤销（轮换），"
                "重复使用同一 Refresh Token 视为已失效。\n\n"
                "调用时机：access_token 过期前或请求因未认证失败（envelope code 40101）时静默刷新。\n\n"
                "返回 data：access_token: 新访问令牌；refresh_token: 新刷新令牌（旧票立即作废）；"
                "token_type: 固定 `Bearer`；expires_in: access_token 有效期秒数；user: {id, account, nickname, avatar}。\n\n"
                "权限：公开接口（凭 refresh_token 本体鉴权）。\n\n"
                "幂等性：非幂等（每次调用轮换令牌）；旧 refresh_token 重放返回 40101。\n\n"
                "写库：是（旧会话 revoked_at 置撤销、新增新会话）。",
    response_model=ApiResponse[UserTokenResponse],
    responses={
        400: {"model": ApiErrorResponse, "description": "业务错误（HTTP 400，envelope code 区分）：40101 未认证（刷新令牌无效/已失效/已过期/账号已被禁用）"},
        422: {"model": ApiErrorResponse, "description": "请求参数格式校验失败（HTTP 422，code 42201）"},
        500: {"model": ApiErrorResponse, "description": "系统内部错误（HTTP 500，code 50000）"},
    },
)
def refresh(
    request: UserRefreshRequest,
    db: Session = Depends(get_db),
) -> ApiResponse:
    payload = UserService(db).refresh(request.refresh_token)
    return ApiResponse(message="刷新成功", data=payload)


@router.post(
    "/logout",
    summary="退出登录",
    description="只撤销当前 Refresh Token 对应的会话，不影响其他设备登录。\n\n"
                "调用时机：用户主动退出登录。\n\n"
                "返回 data：null（message=已退出登录）。\n\n"
                "权限：公开接口（凭 refresh_token 本体鉴权）。\n\n"
                "幂等性：天然幂等（会话已撤销时结果一致）。\n\n"
                "写库：是（该会话 revoked_at 置撤销）。注意：access_token 为无状态 JWT，"
                "已签发的访问令牌在 exp 前仍有效（不引 Redis 黑名单），风险窗口由短 TTL 控制。",
    response_model=ApiResponse[DataNull],
    responses={
        422: {"model": ApiErrorResponse, "description": "请求参数格式校验失败（HTTP 422，code 42201）"},
        500: {"model": ApiErrorResponse, "description": "系统内部错误（HTTP 500，code 50000）"},
    },
)
def logout(
    request: UserLogoutRequest,
    db: Session = Depends(get_db),
) -> ApiResponse:
    UserService(db).logout(request.refresh_token)
    return ApiResponse(message="已退出登录", data=None)


@router.get(
    "/me",
    summary="获取当前用户资料",
    description="基于 Bearer Token（user_access）获取资料，不接受客户端传 app_user_id。\n\n"
                "调用时机：登录后加载个人信息页。\n\n"
                "返回 data：id: 用户 ID；account: 登录账号；nickname: 昵称；avatar: 头像 URL（可空）。\n\n"
                "权限：普通用户令牌（user_access）。\n\n"
                "幂等性：只读接口，无副作用。\n\n"
                "写库：否。",
    response_model=ApiResponse[UserProfileResponse],
    responses={
        400: {"model": ApiErrorResponse, "description": "业务错误（HTTP 400，envelope code 区分）：40101 未认证（访问令牌无效/过期/用户不存在/已禁用）"},
        403: {"model": ApiErrorResponse, "description": "未提供或非法 Authorization 请求头（HTTP 403）"},
        500: {"model": ApiErrorResponse, "description": "系统内部错误（HTTP 500，code 50000）"},
    },
)
def get_me(
    current_user: AppUser = Depends(get_current_user),
) -> ApiResponse:
    return ApiResponse(data=_user_dict(current_user))


@router.patch(
    "/me",
    summary="修改当前用户资料",
    description="只允许修改昵称和头像，不支持通过资料接口换账号/密码/改状态。\n\n"
                "调用时机：个人信息页编辑保存。\n\n"
                "返回 data：id: 用户 ID；account: 登录账号；nickname: 昵称（更新后）；avatar: 头像 URL（更新后）。\n\n"
                "权限：普通用户令牌（user_access，仅本人）。\n\n"
                "幂等性：幂等（相同内容重复提交结果一致）。\n\n"
                "写库：是（更新 app_user 昵称/头像）。",
    response_model=ApiResponse[UserProfileResponse],
    responses={
        400: {"model": ApiErrorResponse, "description": "业务错误（HTTP 400，envelope code 区分）：40101 未认证（访问令牌无效/过期/用户不存在/已禁用）"},
        403: {"model": ApiErrorResponse, "description": "未提供或非法 Authorization 请求头（HTTP 403）"},
        422: {"model": ApiErrorResponse, "description": "请求参数格式校验失败（HTTP 422，code 42201）"},
        500: {"model": ApiErrorResponse, "description": "系统内部错误（HTTP 500，code 50000）"},
    },
)
def update_me(
    request: UserUpdateRequest,
    current_user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse:
    user = UserService(db).update_profile(
        current_user, nickname=request.nickname, avatar=request.avatar
    )
    return ApiResponse(message="修改成功", data=_user_dict(user))


@router.get(
    "/me/statistics",
    summary="我的练习/答题统计",
    description="返回当前用户的答题汇总与练习汇总（统一统计口径，样本不足时 accuracy 为 null）。\n\n"
                "调用时机：个人中心/学习报告页。\n\n"
                "返回 data：answer_summary: {graded_submission_count: 已判分提交次数（仅计入 app_user 绑定且已判分的有效记录）, "
                "correct_submission_count: 判分正确次数, accuracy: 整体正确率（无 graded 样本为 null）, "
                "first_attempt_accuracy: 首次作答正确率（每题只取首次 graded 提交，无样本为 null）, "
                "answered_question_count: 独立作答题目数, display_status: 统计口径状态（available/insufficient_samples）, "
                "sample_threshold: 样本充足阈值}; "
                "practice_summary: {session_total: 累计练习会话数, session_completed: 已完成会话数, "
                "session_in_progress: 进行中会话数, session_abandoned: 已放弃会话数, total_duration_ms: 累计作答时长(毫秒)}。\n\n"
                "权限：普通用户令牌（user_access，仅本人）。\n\n"
                "幂等性：只读接口，无副作用。\n\n"
                "写库：否。",
    response_model=ApiResponse[UserStatisticsResponse],
    responses={
        400: {"model": ApiErrorResponse, "description": "业务错误（HTTP 400，envelope code 区分）：40101 未认证（访问令牌无效/过期/用户不存在/已禁用）"},
        403: {"model": ApiErrorResponse, "description": "未提供或非法 Authorization 请求头（HTTP 403）"},
        500: {"model": ApiErrorResponse, "description": "系统内部错误（HTTP 500，code 50000）"},
    },
)
def get_my_statistics(
    current_user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse:
    from app.services.statistics_service import StatisticsService

    return ApiResponse(data=StatisticsService(db).user_statistics(current_user.id))


def _issue_refresh(db: Session, user: AppUser) -> str:
    """注册后直接签发首对令牌（内部复用会话创建）。"""
    _session, refresh_token = UserService(db)._create_session(user, None, None)
    db.commit()
    return refresh_token
