"""题目评论 API 路由。

身份迁移说明（docs/14 补充 §12）：
    - 评论读写接口面向**普通用户**（AppUser，token 中的 app_user_id），
      不再使用 admin_user.id 塞进普通用户身份；
    - 历史数据 question_comment.app_user_id=NULL（旧管理员时代记录）保留不删，
      展示为"匿名用户"，绝不冒充具体普通用户；
    - 历史列 question_comment.user_id 仅为兼容保留，新评论写 0，
      任何展示都不返回该字段；
    - 管理审核接口（moderate）保留管理员身份（隐藏/恢复记录 moderated_by）。
"""

import logging
from collections import defaultdict, deque
from datetime import datetime
from threading import Lock
from typing import Deque, Dict

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import ValidationException
from app.dependencies.auth import get_current_admin, get_current_user
from app.models.admin import AdminUser
from app.models.app_user import AppUser
from app.models.question_comment import QuestionComment
from app.schemas.comment import (
    CommentDeleteResponse,
    CommentItem,
    CommentModerateResponse,
    CommentResponse,
)
from app.schemas.common import ApiErrorResponse, ApiResponse, PaginatedData
from app.utils.response import paginated_response

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/comments", tags=["题目评论"])

# 限频：进程内滑动窗口（单进程保护；无 Redis，不声称集群全局限频）
_COMMENT_RATE_WINDOW_SECONDS = 60
_COMMENT_RATE_MAX_COUNT = 5
_comment_rate_lock = Lock()
_comment_rate_buckets: Dict[int, Deque[datetime]] = defaultdict(deque)


def _check_comment_rate(user_id: int) -> None:
    """发帖限频（进程内）：60 秒内最多 5 条，超出报 40001。"""
    now = datetime.utcnow()
    with _comment_rate_lock:
        bucket = _comment_rate_buckets[user_id]
        while bucket and (now - bucket[0]).total_seconds() > _COMMENT_RATE_WINDOW_SECONDS:
            bucket.popleft()
        if len(bucket) >= _COMMENT_RATE_MAX_COUNT:
            raise ValidationException("评论过于频繁，请稍后再试")
        bucket.append(now)


def _display_name(comment: QuestionComment) -> str:
    """历史 NULL 评论安全显示为匿名，不冒充具体普通用户。"""
    return "匿名用户"


@router.get(
    "/question/{question_id}",
    summary="获取题目评论",
    description=(
        "分页获取指定题目的可见评论（普通用户可读；只返回 visible，隐藏/删除的不展示）。\n\n"
        "调用时机：题目详情页评论区加载。\n\n"
        "返回 data（分页信封）：items: 评论数组，每项 {id: 评论 ID, question_id: 题目 ID, "
        "nickname: 显示昵称（历史无归属评论显示「匿名用户」，不冒充普通用户）, content: 评论文本, "
        "created_at: 发表时间}；page/page_size/total: 分页信息。\n\n"
        "权限：普通用户令牌（user_access，可读）。\n\n"
        "幂等性：只读接口，无副作用。\n\n"
        "写库：否。"
    ),
    response_model=ApiResponse[PaginatedData[CommentItem]],
    responses={
        400: {"model": ApiErrorResponse, "description": "业务错误（HTTP 400，envelope code 区分）：40101 未认证（访问令牌无效/过期/用户不存在/已禁用）"},
        403: {"model": ApiErrorResponse, "description": "未提供或非法 Authorization 请求头（HTTP 403）"},
        422: {"model": ApiErrorResponse, "description": "请求参数格式校验失败（HTTP 422，code 42201）"},
        500: {"model": ApiErrorResponse, "description": "系统内部错误（HTTP 500，code 50000）"},
    },
)
def get_comments(
    question_id: int = Path(description="题目 ID，对应 question 表主键；只返回该题下状态为 visible 的评论"),
    page: int = Query(default=1, ge=1, description="页码，从 1 开始；不传=默认第 1 页"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页返回条数；不传=默认 20，取值 1~100"),
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    """获取题目评论（只返回 visible）。"""
    query = db.query(QuestionComment).filter(
        QuestionComment.question_id == question_id,
        QuestionComment.status == "visible",
    )

    total = query.count()
    items = query.order_by(
        QuestionComment.created_at.desc(),
        QuestionComment.id.desc(),
    ).offset((page - 1) * page_size).limit(page_size).all()

    item_data = []
    for c in items:
        owner = (
            db.query(AppUser).filter(AppUser.id == c.app_user_id).first()
            if c.app_user_id else None
        )
        item_data.append({
            "id": c.id,
            "question_id": c.question_id,
            "nickname": owner.nickname if owner else _display_name(c),
            "content": c.content,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        })

    return paginated_response(items=item_data, total=total, page=page, page_size=page_size)


@router.post(
    "/question/{question_id}",
    summary="发表评论",
    description=(
        "普通用户发表评论（身份来自 token）。纯文本，长度限制 2000 字符；"
        "进程内限频：60 秒最多 5 条（不称集群全局限频）。\n\n"
        "调用时机：题目详情页评论区提交。\n\n"
        "请求体：content: 评论文本（必填，非空，≤2000 字符）。\n\n"
        "返回 data：id: 评论 ID；question_id: 题目 ID；nickname: 发表者昵称；content: 评论文本；created_at: 发表时间。\n\n"
        "权限：普通用户令牌（user_access，身份取自令牌）。\n\n"
        "幂等性：非幂等（每次调用新增一条评论）；过于频繁返回 40001。\n\n"
        "写库：是（新增 question_comment，app_user_id 记录真实用户）。"
    ),
    response_model=ApiResponse[CommentResponse],
    responses={
        200: {"description": "成功（code=0）。业务错误时 HTTP 仍为 200，用 envelope code（如 40001 内容为空或超长）标识，前端须检查 code。"},
        400: {"model": ApiErrorResponse, "description": "业务错误（HTTP 400，envelope code 区分）：40001 参数校验（评论过于频繁）/ 40101 未认证（访问令牌无效/过期/用户不存在/已禁用）"},
        403: {"model": ApiErrorResponse, "description": "未提供或非法 Authorization 请求头（HTTP 403）"},
        422: {"model": ApiErrorResponse, "description": "请求参数格式校验失败（HTTP 422，code 42201）"},
        500: {"model": ApiErrorResponse, "description": "系统内部错误（HTTP 500，code 50000）"},
    },
)
async def create_comment(
    request: dict,
    question_id: int = Path(description="题目 ID，对应 question 表主键；只返回该题下状态为 visible 的评论"),
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
) -> ApiResponse:
    """发表评论。"""
    content = request.get("content", "").strip()

    if not content:
        return ApiResponse(code=40001, message="评论内容不能为空", data=None)
    if len(content) > 2000:
        return ApiResponse(code=40001, message="评论内容过长，最大2000字符", data=None)
    _check_comment_rate(current_user.id)

    comment = QuestionComment(
        question_id=question_id,
        user_id=0,  # 历史兼容列，不再承载身份（身份在 app_user_id）
        app_user_id=current_user.id,
        content=content,
        status="visible",
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)

    return ApiResponse(data={
        "id": comment.id,
        "question_id": comment.question_id,
        "nickname": current_user.nickname,
        "content": comment.content,
        "created_at": comment.created_at.isoformat() if comment.created_at else None,
    })


@router.delete(
    "/{comment_id}",
    summary="删除评论",
    description=(
        "普通用户删除自己的评论（软删除；只能删除本人评论，他人评论返回 40301）。\n\n"
        "调用时机：题目详情页评论区删除操作。\n\n"
        "返回 data：comment_id: 被删除评论 ID；status: 固定 `deleted`（软删除，内容保留不再展示）。\n\n"
        "权限：普通用户令牌（user_access，仅本人）。\n\n"
        "幂等性：非幂等（重复删除同一条评论会因状态校验报错）。\n\n"
        "写库：是（question_comment.status 置 deleted，不物理删除）。"
    ),
    response_model=ApiResponse[CommentDeleteResponse],
    responses={
        200: {"description": "成功（code=0）。业务错误时 HTTP 仍为 200，用 envelope code（如 40401 评论不存在/40301 只能删除自己的评论）标识，前端须检查 code。"},
        400: {"model": ApiErrorResponse, "description": "业务错误（HTTP 400，envelope code 区分）：40101 未认证（访问令牌无效/过期/用户不存在/已禁用）"},
        403: {"model": ApiErrorResponse, "description": "未提供或非法 Authorization 请求头（HTTP 403）"},
        500: {"model": ApiErrorResponse, "description": "系统内部错误（HTTP 500，code 50000）"},
    },
)
async def delete_comment(
    comment_id: int = Path(description="评论 ID，对应 question_comment 表主键"),
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
) -> ApiResponse:
    """删除自己的评论。"""
    comment = db.query(QuestionComment).filter(
        QuestionComment.id == comment_id
    ).first()

    if not comment:
        return ApiResponse(code=40401, message="评论不存在", data=None)

    if comment.app_user_id != current_user.id:
        return ApiResponse(code=40301, message="只能删除自己的评论", data=None)

    comment.status = "deleted"
    comment.deleted_at = datetime.utcnow()
    db.commit()

    return ApiResponse(data={"comment_id": comment_id, "status": "deleted"})


@router.post(
    "/{comment_id}/moderate",
    summary="管理评论（管理员）",
    description=(
        "管理员隐藏/恢复评论（保留操作人与原因，不删除内容）。\n\n"
        "调用时机：管理端评论审核操作。\n\n"
        "请求体：action: 操作类型，hide=隐藏（不再展示给普通用户）/restore=恢复展示；reason: 处理原因（可空，用于审计）。\n\n"
        "返回 data：comment_id: 评论 ID；status: 处理后状态（visible|hidden）。\n\n"
        "权限：管理员令牌。\n\n"
        "幂等性：幂等（同 action 重复执行结果一致）。\n\n"
        "写库：是（更新 question_comment.status/moderated_by/moderation_reason）。"
    ),
    response_model=ApiResponse[CommentModerateResponse],
    responses={
        200: {"description": "成功（code=0）。业务错误时 HTTP 仍为 200，用 envelope code（如 40401 评论不存在/40001 action 非法）标识，前端须检查 code。"},
        400: {"model": ApiErrorResponse, "description": "业务错误（HTTP 400，envelope code 区分）：40101 未认证（管理员令牌无效/过期/管理员不存在/已禁用）"},
        403: {"model": ApiErrorResponse, "description": "未提供或非法 Authorization 请求头（HTTP 403）"},
        500: {"model": ApiErrorResponse, "description": "系统内部错误（HTTP 500，code 50000）"},
    },
)
async def moderate_comment(
    request: dict,
    comment_id: int = Path(description="评论 ID，对应 question_comment 表主键"),
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
) -> ApiResponse:
    """管理员隐藏/恢复评论。"""
    comment = db.query(QuestionComment).filter(
        QuestionComment.id == comment_id
    ).first()

    if not comment:
        return ApiResponse(code=40401, message="评论不存在", data=None)

    action = request.get("action")  # hide / restore
    reason = request.get("reason", "")

    if action == "hide":
        comment.status = "hidden"
    elif action == "restore":
        comment.status = "visible"
    else:
        return ApiResponse(code=40001, message="action 必须是 hide 或 restore", data=None)

    comment.moderated_by = current_admin.id
    comment.moderation_reason = reason
    db.commit()

    return ApiResponse(data={
        "comment_id": comment_id,
        "status": comment.status,
    })
