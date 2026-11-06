"""题目评论相关响应 Schema。"""

from typing import Optional

from pydantic import BaseModel, Field


# ==================== 响应模型 ====================


class CommentResponse(BaseModel):
    """data 载荷：单条评论（创建评论返回的评论对象）。"""

    id: int = Field(description="评论 ID")
    question_id: int = Field(description="题目 ID")
    nickname: Optional[str] = Field(default=None, description="评论者昵称（可空；匿名展示为「匿名用户」）")
    content: str = Field(description="评论内容")
    created_at: Optional[str] = Field(default=None, description="评论时间（ISO 8601 字符串，可空）")


class CommentItem(CommentResponse):
    """items 数组元素：评论条目（字段同 CommentResponse）。"""


class CommentDeleteResponse(BaseModel):
    """data 载荷：删除评论结果（DELETE /comments/{comment_id}）。"""

    comment_id: int = Field(description="被删除的评论 ID")
    status: str = Field(description="删除结果状态，固定 deleted")


class CommentModerateResponse(BaseModel):
    """data 载荷：审核评论结果（POST /comments/{comment_id}/moderate）。"""

    comment_id: int = Field(description="被审核的评论 ID")
    status: str = Field(description="审核后的评论状态（visible=可见 / hidden=隐藏）")
