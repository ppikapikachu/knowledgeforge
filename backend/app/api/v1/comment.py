"""题目评论 API 路由。"""

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_admin
from app.models.admin import AdminUser
from app.models.question_comment import QuestionComment
from app.schemas.common import ApiResponse
from app.utils.response import paginated_response

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/comments", tags=["题目评论"])


@router.get(
    "/question/{question_id}",
    summary="获取题目评论",
    description="分页获取指定题目的可见评论。",
)
def get_comments(
    question_id: int,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
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
        item_data.append({
            "id": c.id,
            "question_id": c.question_id,
            "user_id": c.user_id,
            "content": c.content,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        })

    return paginated_response(items=item_data, total=total, page=page, page_size=page_size)


@router.post(
    "/question/{question_id}",
    summary="发表评论",
    description="登录用户发表评论。评论为纯文本，长度限制 2000 字符。",
)
async def create_comment(
    question_id: int,
    request: dict,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
) -> ApiResponse:
    """发表评论。"""
    content = request.get("content", "").strip()

    if not content:
        return ApiResponse(code=40001, message="评论内容不能为空", data=None)
    if len(content) > 2000:
        return ApiResponse(code=40001, message="评论内容过长，最大2000字符", data=None)

    comment = QuestionComment(
        question_id=question_id,
        user_id=current_admin.id,
        content=content,
        status="visible",
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)

    return ApiResponse(data={
        "id": comment.id,
        "question_id": comment.question_id,
        "content": comment.content,
        "created_at": comment.created_at.isoformat() if comment.created_at else None,
    })


@router.delete(
    "/{comment_id}",
    summary="删除评论",
    description="用户删除自己的评论（软删除）。",
)
async def delete_comment(
    comment_id: int,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
) -> ApiResponse:
    """删除自己的评论。"""
    comment = db.query(QuestionComment).filter(
        QuestionComment.id == comment_id
    ).first()

    if not comment:
        return ApiResponse(code=40401, message="评论不存在", data=None)

    if comment.user_id != current_admin.id:
        return ApiResponse(code=40301, message="只能删除自己的评论", data=None)

    comment.status = "deleted"
    comment.deleted_at = datetime.utcnow()
    db.commit()

    return ApiResponse(data={"comment_id": comment_id, "status": "deleted"})


@router.post(
    "/{comment_id}/moderate",
    summary="管理评论（管理员）",
    description="管理员隐藏/恢复评论。",
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
