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
from app.schemas.common import ApiResponse
from app.schemas.user import (
    UserLoginRequest,
    UserLogoutRequest,
    UserRefreshRequest,
    UserRegisterRequest,
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
                "注册成功直接返回登录令牌（自动登录）。",
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
    description="账号密码登录。失败消息统一为「账号或密码错误」，不暴露账号是否存在。",
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
                "重复使用同一 Refresh Token 视为已失效。",
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
    description="只撤销当前 Refresh Token 对应的会话，不影响其他设备登录。",
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
    description="基于 Bearer Token（user_access）获取资料，不接受客户端传 app_user_id。",
)
def get_me(
    current_user: AppUser = Depends(get_current_user),
) -> ApiResponse:
    return ApiResponse(data=_user_dict(current_user))


@router.patch(
    "/me",
    summary="修改当前用户资料",
    description="只允许修改昵称和头像，不支持通过资料接口换账号/密码/改状态。",
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
    description="返回当前用户的答题汇总与练习汇总（统一统计口径，样本不足时 accuracy 为 null）。",
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
