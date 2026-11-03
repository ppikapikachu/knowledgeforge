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

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import ValidationException
from app.dependencies.auth import get_current_admin, get_current_user
from app.models.admin import AdminUser
from app.models.app_user import AppUser
from app.models.question_comment import QuestionComment
from app.schemas.common import ApiResponse
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
    description="分页获取指定题目的可见评论（普通用户可读；只返回 visible）。",
)
def get_comments(
    question_id: int,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
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
        "进程内限频：60 秒最多 5 条（不称集群全局限频）。"
    ),
)
async def create_comment(
    question_id: int,
    request: dict,
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
    description="普通用户删除自己的评论（软删除；只能删除本人评论）。",
)
async def delete_comment(
    comment_id: int,
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
    description="管理员隐藏/恢复评论（保留操作人与原因，不删除内容）。",
)
async def moderate_comment(
    comment_id: int,
    request: dict,
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
