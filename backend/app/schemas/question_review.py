"""AI 质量审核相关 Schema。"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


class QuestionReviewReopenRequest(BaseModel):
    """重新开启人工复核请求（§7.3）。"""

    reason: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="重新开启原因（必填，去除首尾空白后 1~1000 字符，用于审计追溯）",
    )


class QuestionReviewBatchRequest(BaseModel):
    """批量 AI 审核请求（§6.1/§6.2，preview 与 create 共用）。"""

    question_ids: list[int] = Field(
        ...,
        min_length=1,
        max_length=200,
        description="待审核题目 ID 列表（非空、去重保序；硬上限 200，实际以配置 QUESTION_AI_REVIEW_BATCH_MAX_ITEMS 为准）",
    )

    @field_validator("question_ids")
    @classmethod
    def _dedupe_preserve_order(cls, v: list[int]) -> list[int]:
        """按文档 §6.1：前端提交先去重（保持顺序）。"""
        if any(qid <= 0 for qid in v):
            raise ValueError("question_ids 必须为正整数")
        return list(dict.fromkeys(v))


class QuestionReviewRecordOut(BaseModel):
    """AI 审核记录（响应结构参考用，实际以 dict 序列化）。"""

    id: int = Field(description="审核记录 ID")
    question_id: int = Field(description="被审核题目 ID")
    generation_task_id: Optional[int] = Field(default=None, description="触发审核的生成任务 ID（手动批量审核时为空）")
    review_round: int = Field(default=1, description="审核轮次（同题同轮唯一；重复审核递增轮次）")
    trigger_source: str = Field(default="generation_task", description="触发来源：generation_task=生成任务自动审核，manual_batch=人工批量审核")
    execution_status: str = Field(default="success", description="执行状态：success=审核成功，failed=执行失败，skipped=准入跳过")
    decision: Optional[str] = Field(default=None, description="审核决策：auto_approve=自动通过，auto_reject=自动驳回，manual_review=转人工（skipped 时为空）")
    risk_level: Optional[str] = Field(default=None, description="风险等级：low|medium|high|unknown")
    issue_types: Optional[list] = Field(default=None, description="问题类型列表（incorrect_answer 等 13 枚举，宽松入库可追溯）")
    checks: Optional[dict] = Field(default=None, description="八维检查结果（answer_correctness 等，每项 pass|fail|uncertain|not_applicable）")
    reason: Optional[str] = Field(default=None, description="审核理由（LLM 给出的判定依据）")
    evidence: Optional[list] = Field(default=None, description="证据列表（知识点摘录与说明）")
    model_name: Optional[str] = Field(default=None, description="执行审核的模型名称")
    prompt_version: Optional[str] = Field(default=None, description="审核提示词版本（review-v1/review-v2）")
    reviewed_content_hash: Optional[str] = Field(default=None, description="审核时题目内容指纹（人工改题后旧审核不覆盖新内容的依据）")
    duration_ms: Optional[int] = Field(default=None, description="审核耗时（毫秒）")
    error_code: Optional[str] = Field(default=None, description="失败/跳过原因码（如 execution_failed、question_not_pending）")
    error_message: Optional[str] = Field(default=None, description="失败/跳过详细信息")
    reopened_by: Optional[int] = Field(default=None, description="执行 reopen 的管理员 ID（未重开为空）")
    reopened_at: Optional[str] = Field(default=None, description="reopen 操作时间（ISO 格式）")
    reopen_reason: Optional[str] = Field(default=None, description="reopen 操作理由")

    model_config = {"from_attributes": True}


# =====================================================================
# 审核记录 / 统计 / 批次响应模型（question_review 路由使用）
# =====================================================================


class EvidenceItem(BaseModel):
    """审核证据条目（审核记录 evidence 数组元素：知识点摘录与说明）。"""

    knowledge_id: Optional[int] = Field(
        default=None, description="中文：证据关联的知识点 ID（可空）"
    )
    source_excerpt: str = Field(
        default="", description="中文：题目原文摘录片段"
    )
    explanation: str = Field(
        default="", description="中文：该证据的说明（LLM 给出的判定依据）"
    )


class QuestionReviewRecordItem(BaseModel):
    """AI 审核记录列表条目（GET /question-reviews/records 的 data.items 元素）。"""

    id: int = Field(description="中文：审核记录 ID")
    question_id: int = Field(description="中文：被审核题目 ID")
    generation_task_id: Optional[int] = Field(
        default=None,
        description="中文：触发审核的生成任务 ID（手动批量审核时为 null）",
    )
    batch_id: Optional[int] = Field(
        default=None, description="中文：所属审核批次 ID（手动批量审核时存在，否则为 null）"
    )
    review_round: int = Field(description="中文：审核轮次（同题重复审核递增）")
    trigger_source: str = Field(
        description="中文：触发来源（generation_task=生成任务自动审核；manual_batch=人工批量审核）"
    )
    execution_status: str = Field(
        description="中文：执行状态（success=审核成功；failed=执行失败；skipped=准入跳过）"
    )
    decision: Optional[str] = Field(
        default=None,
        description="中文：审核决策（auto_approve=自动通过；auto_reject=自动驳回；manual_review=转人工；skipped 时为 null）",
    )
    risk_level: Optional[str] = Field(
        default=None, description="中文：风险等级（low|medium|high|unknown）"
    )
    issue_types: List[str] = Field(
        default_factory=list,
        description="中文：问题类型列表（incorrect_answer 等枚举，宽松入库可追溯）",
    )
    checks: Dict[str, str] = Field(
        default_factory=dict,
        description="中文：八维检查结果（键为 factual_correctness/answer_correctness/"
        "question_clarity/option_quality/knowledge_alignment/difficulty_alignment/"
        "explanation_consistency/version_environment，值为 pass|fail|uncertain|not_applicable；无数据时为空字典）",
    )
    reason: Optional[str] = Field(
        default=None, description="中文：审核理由（LLM 给出的判定依据）"
    )
    evidence: List[EvidenceItem] = Field(
        default_factory=list,
        description="中文：证据列表（知识点摘录与说明）",
    )
    model_name: Optional[str] = Field(
        default=None, description="中文：执行审核的模型名称"
    )
    prompt_version: Optional[str] = Field(
        default=None, description="中文：审核提示词版本（review-v1/review-v2）"
    )
    reviewed_content_hash: Optional[str] = Field(
        default=None,
        description="中文：审核时题目内容指纹（人工改题后旧审核不覆盖新内容的依据）",
    )
    duration_ms: Optional[int] = Field(
        default=None, description="中文：审核耗时（毫秒）"
    )
    error_code: Optional[str] = Field(
        default=None, description="中文：失败/跳过原因码（如 execution_failed、question_not_pending）"
    )
    error_message: Optional[str] = Field(
        default=None, description="中文：失败/跳过详细信息"
    )
    reopened_by: Optional[int] = Field(
        default=None, description="中文：执行 reopen 的管理员 ID（未重开为 null）"
    )
    reopened_at: Optional[str] = Field(
        default=None, description="中文：reopen 操作时间（ISO8601 字符串，可空）"
    )
    reopen_reason: Optional[str] = Field(
        default=None, description="中文：reopen 操作理由"
    )
    question_status: Optional[str] = Field(
        default=None, description="中文：题目当前状态（题目不存在时为 null）"
    )
    question_type: Optional[str] = Field(
        default=None, description="中文：题型（题目不存在时为 null）"
    )
    question_bank_name: Optional[str] = Field(
        default=None, description="中文：题目所属题库名称（无题库或题目不存在时为 null）"
    )
    created_at: Optional[str] = Field(
        default=None, description="中文：记录创建时间（ISO8601 字符串，可空）"
    )


class QuestionReviewStatsResponse(BaseModel):
    """任务级 AI 审核统计响应（GET /question-reviews/stats/{task_id} 的 data）。

    无审核数据时全部计数为 0、状态为 not_requested。
    """

    task_id: int = Field(description="中文：生成任务 ID")
    enable_ai_review: bool = Field(description="中文：任务是否开启 AI 审核")
    ai_review_status: str = Field(
        description="中文：审核状态（not_requested|queued|running|completed|partial|failed）"
    )
    ai_review_total_count: int = Field(description="中文：进入审核的题目总数")
    ai_review_processed_count: int = Field(description="中文：已处理题目数")
    ai_auto_approved_count: int = Field(description="中文：自动通过题目数")
    ai_auto_rejected_count: int = Field(description="中文：自动驳回题目数")
    ai_manual_review_count: int = Field(description="中文：转人工复核题目数")
    ai_review_failed_count: int = Field(description="中文：执行失败题目数")
    ai_review_skipped_count: int = Field(
        description="中文：准入跳过题目数（含去重疑点与不支持题型）"
    )
    ai_review_pending_count: int = Field(description="中文：未处理题目数")


class QuestionReviewReopenResponse(BaseModel):
    """重新开启人工复核响应（POST /question-reviews/questions/{question_id}/reopen 的 data）。"""

    question_id: int = Field(description="中文：题目 ID")
    status: str = Field(
        description="中文：重开后的题目状态（pending_review=待审核）"
    )
    reopened_by: int = Field(description="中文：执行重开的管理员 ID")
    reopen_reason: str = Field(description="中文：重开原因")
    record_id: int = Field(description="中文：关联的审核记录 ID（= 既有最新 auto_reject 审核记录 id；重开不新建审核记录，仅回填该记录的 reopened_by/reopened_at/reopen_reason）")


class ReviewBatchPreviewItem(BaseModel):
    """批量审核预检明细项（POST /question-reviews/batches/preview 的 data.items 元素）。"""

    question_id: int = Field(description="中文：题目 ID")
    eligible: bool = Field(description="中文：是否可进入批量审核")
    reason_code: str = Field(
        description="中文：不可进入原因码（question_not_found/question_not_pending/"
        "unsupported_question_type/dedup_unresolved/dedup_duplicate/"
        "concurrent_review_in_progress；可进入时为空字符串）",
    )
    reason: str = Field(
        description="中文：不可进入原因文案（可进入时为空字符串）"
    )


class QuestionReviewBatchPreviewResponse(BaseModel):
    """批量审核预检响应（POST /question-reviews/batches/preview 的 data）。"""

    requested: int = Field(description="中文：请求题目数（去重后）")
    eligible: int = Field(description="中文：可进入审核的题目数")
    ineligible: int = Field(description="中文：不可进入审核的题目数")
    eligible_question_ids: List[int] = Field(
        default_factory=list, description="中文：可进入审核的题目 ID 列表"
    )
    items: List[ReviewBatchPreviewItem] = Field(
        default_factory=list, description="中文：逐题预检明细"
    )


class QuestionReviewBatchCreateResponse(BaseModel):
    """创建审核批次响应（POST /question-reviews/batches 的 data）。"""

    batch_id: int = Field(description="中文：审核批次 ID")
    status: str = Field(description="中文：批次初始状态（queued=已排队）")
    requested: int = Field(description="中文：请求题目数（去重后）")
    accepted: int = Field(description="中文：实际纳入批次的题目数")
    skipped: int = Field(description="中文：因准入规则跳过的题目数")


class QuestionReviewBatchListItem(BaseModel):
    """审核批次列表条目（GET /question-reviews/batches 的 data.items 元素）。"""

    id: int = Field(description="中文：审核批次 ID")
    created_by: int = Field(description="中文：创建批次的管理员 ID")
    status: str = Field(
        description="中文：批次状态（queued=排队中|running=执行中|completed=全部完成|partial=部分完成|failed=失败；cancelled=预留枚举，当前不产生）"
    )
    total_count: int = Field(description="中文：批次内题目总数")
    accepted_count: int = Field(description="中文：认领/受理并进入执行的题目数（非审核通过数；通过数见 auto_approved_count）")
    processed_count: int = Field(description="中文：已处理题目数")
    auto_approved_count: int = Field(description="中文：自动通过题目数")
    auto_rejected_count: int = Field(description="中文：自动驳回题目数")
    manual_review_count: int = Field(description="中文：转人工复核题目数")
    failed_count: int = Field(description="中文：执行失败题目数")
    skipped_count: int = Field(description="中文：准入跳过题目数")
    pending_count: int = Field(description="中文：未处理题目数")
    started_at: Optional[str] = Field(
        default=None, description="中文：开始执行时间（ISO8601 字符串，可空）"
    )
    finished_at: Optional[str] = Field(
        default=None, description="中文：结束时间（ISO8601 字符串，可空）"
    )
    error_message: Optional[str] = Field(
        default=None, description="中文：批次级错误信息（可空）"
    )
    created_at: Optional[str] = Field(
        default=None, description="中文：创建时间（ISO8601 字符串，可空）"
    )
    updated_at: Optional[str] = Field(
        default=None, description="中文：更新时间（ISO8601 字符串，可空）"
    )


class ReviewBatchProgress(BaseModel):
    """审核批次执行进度（GET /question-reviews/batches/{batch_id} 的 data.progress）。"""

    processed: int = Field(description="中文：已处理题目数")
    accepted: int = Field(description="中文：认领/受理进入执行的题目数")
    pending: int = Field(description="中文：未处理题目数")


class ReviewEvidenceSummaryItem(BaseModel):
    """批次明细内审核证据摘要项（items 元素的 review_evidence_summary 数组元素）。"""

    knowledge_id: Optional[int] = Field(
        default=None, description="中文：证据关联的知识点 ID（可空）"
    )
    explanation: str = Field(
        default="", description="中文：证据说明摘要（超过 120 字符截断）"
    )


class ReviewBatchItemDetail(BaseModel):
    """审核批次明细项（GET /question-reviews/batches/{batch_id} 的 data.items 元素）。"""

    id: int = Field(description="中文：批次条目 ID")
    question_id: int = Field(description="中文：题目 ID")
    question_content: Optional[str] = Field(
        default=None, description="中文：题干摘要（超过 120 字符截断）"
    )
    question_type: Optional[str] = Field(
        default=None, description="中文：题型（可空）"
    )
    question_status: Optional[str] = Field(
        default=None, description="中文：题目当前状态（可空）"
    )
    status: str = Field(
        description="中文：条目状态（queued|running|completed|failed|skipped）"
    )
    skip_reason: Optional[str] = Field(
        default=None, description="中文：跳过原因码（未跳过为 null）"
    )
    skip_reason_text: Optional[str] = Field(
        default=None, description="中文：跳过原因文案（未跳过为 null）"
    )
    error_code: Optional[str] = Field(
        default=None, description="中文：失败原因码（可空）"
    )
    error_message: Optional[str] = Field(
        default=None, description="中文：失败详细信息（可空）"
    )
    review_record_id: Optional[int] = Field(
        default=None, description="中文：生成的审核记录 ID（未生成为 null）"
    )
    review_decision: Optional[str] = Field(
        default=None,
        description="中文：审核决策（auto_approve|auto_reject|manual_review，未审核为 null）",
    )
    review_risk_level: Optional[str] = Field(
        default=None, description="中文：风险等级（low|medium|high|unknown，可空）"
    )
    review_reason: Optional[str] = Field(
        default=None, description="中文：审核理由（可空）"
    )
    review_issue_types: List[str] = Field(
        default_factory=list, description="中文：审核问题类型列表（无记录时为空列表）"
    )
    review_evidence_summary: List[ReviewEvidenceSummaryItem] = Field(
        default_factory=list,
        description="中文：审核证据摘要列表（无记录时为空列表）",
    )
    started_at: Optional[str] = Field(
        default=None, description="中文：条目开始执行时间（ISO8601 字符串，可空）"
    )
    finished_at: Optional[str] = Field(
        default=None, description="中文：条目结束时间（ISO8601 字符串，可空）"
    )


class QuestionReviewBatchDetailResponse(QuestionReviewBatchListItem):
    """审核批次详情响应（GET /question-reviews/batches/{batch_id} 的 data）。

    结构为批次字段（与列表条目一致）+ progress 进度 + items 逐题明细。
    """

    progress: ReviewBatchProgress = Field(description="中文：批次执行进度")
    items: List[ReviewBatchItemDetail] = Field(
        default_factory=list, description="中文：逐题审核明细列表"
    )
