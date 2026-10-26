"""AI 质量审核相关 Schema。"""

from typing import Optional

from pydantic import BaseModel, Field


class QuestionReviewReopenRequest(BaseModel):
    """重新开启人工复核请求（§7.3）。"""

    reason: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="重新开启原因，1~1000 字符",
    )


class QuestionReviewRecordOut(BaseModel):
    """AI 审核记录（响应结构参考用，实际以 dict 序列化）。"""

    id: int
    question_id: int
    generation_task_id: Optional[int] = None
    review_round: int = 1
    trigger_source: str = "generation_task"
    execution_status: str = "success"
    decision: Optional[str] = None
    risk_level: Optional[str] = None
    issue_types: Optional[list] = None
    checks: Optional[dict] = None
    reason: Optional[str] = None
    evidence: Optional[list] = None
    model_name: Optional[str] = None
    prompt_version: Optional[str] = None
    reviewed_content_hash: Optional[str] = None
    duration_ms: Optional[int] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    reopened_by: Optional[int] = None
    reopened_at: Optional[str] = None
    reopen_reason: Optional[str] = None

    model_config = {"from_attributes": True}
