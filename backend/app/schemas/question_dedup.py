"""题目去重人工复核 Schema（API 修复与人工复核接口开发执行文档 §3）。"""

from typing import Literal, Optional

from pydantic import BaseModel, Field


class QuestionDedupResolveRequest(BaseModel):
    """人工复核结论请求。

    - conclusion 只接受 duplicate / distinct：uncertain 是自动判断尚不能确定的
      状态，人工复核必须给出确定结论（§3.2）；
    - reason 去除首尾空白后必须非空，长度 1-1000（§3.2）。
    """

    conclusion: Literal["duplicate", "distinct"] = Field(
        description="人工最终结论：duplicate（确认重复）或 distinct（确认不重复）"
    )
    reason: str = Field(
        min_length=1,
        max_length=1000,
        description="人工判断依据（去除首尾空白后非空，1-1000 字符）",
    )


class QuestionDedupResolutionResponse(BaseModel):
    """人工复核结果（原始自动判定证据保留不变，§3.3）。"""

    id: int
    decision: str = Field(description="原始自动判定结论（duplicate/distinct/uncertain），不被人工结论覆盖")
    manual_resolution: str = Field(description="人工最终结论（duplicate/distinct）")
    effective_decision: str = Field(
        description="最终结论：有人工结论时优先人工结论，否则为原始自动结论"
    )
    needs_manual_review: bool = Field(description="处理完成后为 false（曾经需要复核的事实由 resolved_by/resolved_at 追溯）")
    resolution_reason: Optional[str] = None
    resolved_by: Optional[int] = Field(default=None, description="处理人（管理员 ID，取自认证上下文）")
    resolved_at: Optional[str] = None
