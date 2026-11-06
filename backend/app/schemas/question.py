"""Question schemas."""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, model_validator


class QuestionType(str, Enum):
    """Question types."""

    SINGLE_CHOICE = "SINGLE_CHOICE"
    MULTIPLE_CHOICE = "MULTIPLE_CHOICE"
    TRUE_FALSE = "TRUE_FALSE"
    SHORT_ANSWER = "SHORT_ANSWER"


class QuestionStatus(str, Enum):
    """Question status."""

    DRAFT = "pending_review"
    PUBLISHED = "published"
    DISABLED = "disabled"


class QuestionSourceType(str, Enum):
    """Question source types."""

    MANUAL = "MANUAL"
    IMPORT = "IMPORT"
    AI = "AI"


class OptionCreate(BaseModel):
    """Schema for creating a question option."""

    option_key: str = Field(
        ..., min_length=1, max_length=10, description="选项标识: A/B/C/D"
    )
    option_content: str = Field(
        ..., min_length=1, description="选项内容文本（不含 A./B. 等选项前缀标签）"
    )
    is_correct: int = Field(
        default=0, ge=0, le=1, description="是否正确: 1=正确, 0=错误"
    )
    sort_order: int = Field(default=0, ge=0, description="展示排序，从 0 开始，越小越靠前")


class OptionResponse(BaseModel):
    """Question option response schema."""

    id: int = Field(description="选项ID")
    question_id: int = Field(description="题目ID")
    option_key: str = Field(description="选项标识")
    option_content: str = Field(description="选项内容")
    is_correct: int = Field(description="是否正确")
    sort_order: int = Field(description="排序")
    created_at: datetime = Field(description="创建时间")

    class Config:
        from_attributes = True


class QuestionCreate(BaseModel):
    """Schema for creating a question."""

    question_bank_id: Optional[int] = Field(
        default=None,
        description="所属题库 ID。不传时默认使用未分类题库",
    )
    question_type: str = Field(
        ..., description="题型: SINGLE_CHOICE/MULTIPLE_CHOICE/TRUE_FALSE/SHORT_ANSWER"
    )
    content: str = Field(..., min_length=1, description="题干内容文本，必填，创建后可编辑（有答题记录后受保护）")
    answer: str = Field(..., min_length=1, description="标准答案：选择题为选项键（如 \"A\" 或 \"A,B\"），判断题为 TRUE/FALSE，简答题为文本")
    analysis: Optional[str] = Field(default=None, description="题目解析文本，可选；手动填写的解析讲解来源为 manual")
    difficulty: int = Field(
        default=1, ge=1, le=3, description="难度: 1=简单, 2=中等, 3=困难"
    )
    status: str = Field(
        default="pending_review", description="状态: pending_review/published/rejected/disabled"
    )
    source_type: str = Field(
        default="MANUAL", description="来源: MANUAL/IMPORT/AI"
    )
    quality_score: Optional[float] = Field(
        default=None, ge=0, le=100, description="质量评分：0-100 数值，可选，供人工标注题目质量"
    )
    options: Optional[List[OptionCreate]] = Field(
        default=None, description="选项列表；单选/多选必填（至少2个），判断/简答必须为空"
    )
    knowledge_ids: Optional[List[int]] = Field(
        default=None, description="关联知识点ID列表，必须是已存在的知识点，可选"
    )

    @model_validator(mode="after")
    def validate_question_type_and_options(self) -> "QuestionCreate":
        """Validate question type matches options."""
        qtype = self.question_type
        options = self.options or []

        if qtype == "SINGLE_CHOICE":
            if len(options) < 2:
                raise ValueError("单选题至少需要2个选项")
            correct_count = sum(1 for o in options if o.is_correct == 1)
            if correct_count != 1:
                raise ValueError("单选题必须有且仅有1个正确答案")

        elif qtype == "MULTIPLE_CHOICE":
            if len(options) < 2:
                raise ValueError("多选题至少需要2个选项")
            correct_count = sum(1 for o in options if o.is_correct == 1)
            if correct_count < 1:
                raise ValueError("多选题至少需要1个正确答案")

        elif qtype == "TRUE_FALSE":
            if options:
                raise ValueError("判断题不应有选项")
            if self.answer not in ("TRUE", "FALSE"):
                raise ValueError('判断题答案必须是 "TRUE" 或 "FALSE"')

        elif qtype == "SHORT_ANSWER":
            if options:
                raise ValueError("简答题不应有选项")

        return self


class QuestionUpdate(BaseModel):
    """Schema for updating a question."""

    question_bank_id: Optional[int] = Field(
        default=None, description="所属题库 ID，只传需修改时才生效，必须是已存在的题库"
    )
    question_type: Optional[str] = Field(
        default=None, description="题型：SINGLE_CHOICE 单选 | MULTIPLE_CHOICE 多选 | TRUE_FALSE 判断 | SHORT_ANSWER 简答；有答题记录时不可改"
    )
    content: Optional[str] = Field(
        default=None, min_length=1, description="题干内容文本（整体替换）；有答题记录时不可改"
    )
    answer: Optional[str] = Field(
        default=None, min_length=1, description="标准答案文本（选择题为选项键、判断为 TRUE/FALSE、简答为文本）；有答题记录时不可改"
    )
    analysis: Optional[str] = Field(default=None, description="题目解析文本（手动修改后讲解来源标记为 manual）")
    difficulty: Optional[int] = Field(default=None, ge=1, le=3, description="难度：1 简单 | 2 中等 | 3 困难")
    status: Optional[str] = Field(
        default=None, description="状态：pending_review 待审核 | published 已发布 | rejected 已驳回 | disabled 已下架"
    )
    source_type: Optional[str] = Field(default=None, description="来源：MANUAL 人工 | IMPORT 导入 | AI 生成")
    quality_score: Optional[float] = Field(
        default=None, ge=0, le=100, description="质量评分：0-100 数值，仅传入时更新"
    )
    options: Optional[List[OptionCreate]] = Field(
        default=None, description="选项列表（整体替换全部选项）；有答题记录时不可改"
    )
    knowledge_ids: Optional[List[int]] = Field(
        default=None, description="关联知识点ID列表（整体替换全部关联）：必须是已存在的知识点ID，传空数组清空关联"
    )


class QuestionResponse(BaseModel):
    """Question response schema."""

    id: int = Field(description="题目ID")
    question_bank_id: int = Field(description="所属题库 ID")
    question_type: str = Field(description="题型")
    content: str = Field(description="题目内容")
    answer: str = Field(description="标准答案")
    analysis: Optional[str] = Field(description="解析")
    difficulty: int = Field(description="难度")
    status: str = Field(description="状态")
    source_type: str = Field(description="来源")
    quality_score: Optional[Decimal] = Field(description="质量评分")
    used_count: int = Field(description="使用次数")
    correct_count: int = Field(description="正确次数")
    options: List[OptionResponse] = Field(
        default_factory=list, description="选项列表"
    )
    knowledge_ids: List[int] = Field(
        default_factory=list, description="关联知识点ID"
    )
    dedup_review_status: Optional[str] = Field(
        default=None,
        description="去重复核状态（uncertain/duplicate/distinct/none，详情接口返回）",
    )
    dedup_manual_resolution: Optional[str] = Field(
        default=None,
        description="人工复核结论（duplicate/distinct，未处理为 null；不覆盖自动判定）",
    )
    dedup_effective_decision: Optional[str] = Field(
        default=None,
        description="最终结论：有人工结论时优先人工结论，否则为原始自动结论",
    )
    dedup_role: Optional[str] = Field(
        default=None,
        description=(
            "本题在去重审计记录中的方向角色：candidate=新题侧（有以本题指纹为新题的记录）；"
            "historical=仅匹配侧（本题只作为历史胜出方被其他候选撞上，未被判重）；无记录为 null"
        ),
    )
    dedup_blocked_candidate_count: int = Field(
        default=0,
        description="撞上本题后被判重复而被拦截的候选题目数量（historical 角色的参考信息）",
    )
    ai_review_decision: Optional[str] = Field(
        default=None,
        description="AI 质量审核决策（auto_approve/auto_reject/manual_review，无记录为 null）",
    )
    ai_review_risk_level: Optional[str] = Field(
        default=None,
        description="AI 审核风险级别（low/medium/high/unknown）",
    )
    ai_review_reason: Optional[str] = Field(
        default=None, description="AI 审核理由"
    )
    ai_review_issue_types: Optional[List[str]] = Field(
        default=None, description="AI 审核问题类型列表"
    )
    ai_reviewed_at: Optional[str] = Field(
        default=None, description="AI 审核完成时间"
    )
    ai_review_record_id: Optional[int] = Field(
        default=None, description="AI 审核记录 ID（最新一轮）"
    )
    created_at: datetime = Field(description="创建时间")
    updated_at: datetime = Field(description="更新时间")

    class Config:
        from_attributes = True


class QuestionListItem(QuestionResponse):
    """题目列表条目（GET /questions 的 data.items 元素）。

    字段与 QuestionResponse 完全一致。
    """

    pass


class QuestionStatisticsResponse(BaseModel):
    """题目答题统计响应（GET /questions/{question_id}/statistics 的 data）。

    口径：仅统计 app_user_id 非空的答题记录；accuracy 分母仅含已判分（graded）提交；
    first_attempt 按 (created_at, id) 取每用户对该题的首条已判分提交。
    display_status=insufficient_samples 表示样本量不足（已判分提交数 < sample_threshold），
    此时比率仅供参考；accuracy/first_attempt_accuracy 为 null 仅当无有效样本（或题目不存在）。
    """

    question_id: int = Field(description="题目ID")
    accuracy: Optional[float] = Field(
        default=None,
        description="全部提交正确率（0-1，保留4位小数）。无已判分提交或题目不存在时为 null；"
        "样本不足时数值仍返回但仅供参考，见 display_status",
    )
    first_attempt_accuracy: Optional[float] = Field(
        default=None,
        description="首次作答正确率（每用户每题首条已判分提交的正确率，0-1，保留4位小数）。"
        "无首次作答样本或题目不存在时为 null",
    )
    first_attempt_total: Optional[int] = Field(
        default=None,
        description="首次作答样本总数（参与统计的用户数）。题目不存在时不返回该字段",
    )
    first_attempt_correct: Optional[int] = Field(
        default=None,
        description="首次作答正确数。题目不存在时不返回该字段",
    )
    unique_user_count: int = Field(
        default=0, description="作答独立用户数（app_user_id 去重）"
    )
    graded_submission_count: int = Field(
        default=0, description="已判分提交数（accuracy 的样本量）"
    )
    total_submission_count: Optional[int] = Field(
        default=None,
        description="提交总数（含未判分）。题目不存在时不返回该字段",
    )
    correct_submission_count: Optional[int] = Field(
        default=None,
        description="正确提交数（已判分中正确的数量）。题目不存在时不返回该字段",
    )
    display_status: str = Field(
        description="统计展示状态：available=样本充足（已判分提交数 ≥ sample_threshold）；"
        "insufficient_samples=样本不足或题目不存在，accuracy 等比率仅供参考或为 null"
    )
    sample_threshold: int = Field(
        default=20,
        description="样本充足阈值（QUESTION_STATISTICS_MIN_SAMPLES，默认 20）",
    )


# =====================================================================
# 出题任务响应模型（question_generation 路由使用）
# =====================================================================


class GenerationTaskQuestionItem(BaseModel):
    """生成任务详情内嵌题目摘要项（GET /question-generation/tasks/{task_id} 的 data.questions 元素）。"""

    id: int = Field(description="中文：题目 ID")
    question_type: str = Field(
        description="中文：题型（single_choice/multiple_choice/true_false/short_answer）"
    )
    content: str = Field(
        description="中文：题干摘要（超过 100 字符截断并追加 ...）"
    )
    difficulty: int = Field(description="中文：难度（整数）")
    status: str = Field(
        description="中文：题目状态（pending_review/published/disabled 等）"
    )
    knowledge_ids: List[int] = Field(
        default_factory=list, description="中文：关联知识点 ID 列表"
    )
    option_count: int = Field(
        default=0, description="中文：选项数量（选择题为选项个数，其他题型为 0）"
    )


class GenerationTaskListItem(BaseModel):
    """生成任务列表条目（GET /question-generation/tasks 的 data.items 元素）。"""

    id: int = Field(description="中文：生成任务 ID")
    status: str = Field(
        description="中文：任务状态（pending=待执行|running=执行中|success=成功|partial_success=部分成功|failed=失败）"
    )
    allocation_mode: str = Field(
        description="中文：出题分配方式（manual=手动指定知识点与数量；auto=按需求策略自动分配）"
    )
    requested_count: int = Field(description="中文：请求出题总数")
    allocated_count: int = Field(description="中文：已分配到知识点的题目数")
    unallocated_count: int = Field(description="中文：未分配（缺知识点需求）的题目数")
    total_count: int = Field(description="中文：计划生成题目总数")
    success_count: int = Field(description="中文：生成成功的题目数")
    duplicate_count: int = Field(description="中文：重复命中数（历史口径）")
    generated_count: int = Field(description="中文：生成的候选题目数（去重前口径；实际入库数见 success_count）")
    exact_duplicate_count: int = Field(description="中文：精确重复（内容哈希命中）题目数")
    semantic_duplicate_count: int = Field(description="中文：语义重复（向量/LLM 判定）题目数")
    uncertain_count: int = Field(description="中文：去重结论不确定（uncertain）的题目数")
    unfulfilled_count: int = Field(description="中文：因需求不足未生成的题目数")
    failed_count: int = Field(description="中文：生成失败的题目数")
    enable_ai_review: bool = Field(
        description="中文：是否开启 AI 审核（任务创建时的开关）"
    )
    ai_review_status: str = Field(
        description="中文：AI 审核状态（not_requested|queued|running|completed|partial|failed）"
    )
    ai_review_total_count: int = Field(description="中文：进入 AI 审核的题目总数")
    ai_review_processed_count: int = Field(description="中文：AI 审核已处理题目数")
    ai_auto_approved_count: int = Field(description="中文：AI 自动通过题目数")
    ai_auto_rejected_count: int = Field(description="中文：AI 自动驳回题目数")
    ai_manual_review_count: int = Field(description="中文：AI 转人工复核题目数")
    ai_review_failed_count: int = Field(description="中文：AI 审核执行失败题目数")
    ai_review_skipped_count: int = Field(description="中文：AI 审核准入跳过题目数")
    ai_review_pending_count: int = Field(description="中文：AI 审核未处理题目数")
    request_config: Optional[Dict[str, Any]] = Field(
        default=None,
        description="中文：出题请求配置快照（动态字典，含题型/难度/知识点等请求参数；可空）",
    )
    error_summary: Optional[str] = Field(
        default=None, description="中文：错误摘要（无错误时为 null）"
    )
    started_at: Optional[str] = Field(
        default=None, description="中文：开始执行时间（ISO8601 字符串，可空）"
    )
    completed_at: Optional[str] = Field(
        default=None, description="中文：完成时间（ISO8601 字符串，可空）"
    )
    created_at: Optional[str] = Field(
        default=None, description="中文：创建时间（ISO8601 字符串，可空）"
    )


class GenerationTaskDetailResponse(BaseModel):
    """生成任务详情响应（GET /question-generation/tasks/{task_id} 的 data）。

    任务不存在时 data 为 null（业务码 40401）。
    """

    task_id: int = Field(description="中文：生成任务 ID")
    created_by: int = Field(description="中文：创建者（管理员） ID")
    status: str = Field(
        description="中文：任务状态（pending=待执行|running=执行中|success=成功|partial_success=部分成功|failed=失败）"
    )
    allocation_mode: str = Field(
        description="中文：出题分配方式（manual=手动指定知识点与数量；auto=按需求策略自动分配）"
    )
    allocation_plan: Optional[Dict[str, Any]] = Field(
        default=None,
        description="中文：知识点分配方案（动态字典，含 allocation_mode/requested_count/"
        "allocated_count/unallocated_count/policy_version/items 等；可空）",
    )
    requested_count: int = Field(description="中文：请求出题总数")
    allocated_count: int = Field(description="中文：已分配到知识点的题目数")
    unallocated_count: int = Field(description="中文：未分配（缺知识点需求）的题目数")
    request_config: Optional[Dict[str, Any]] = Field(
        default=None,
        description="中文：出题请求配置快照（动态字典，含题型/难度/知识点等请求参数；可空）",
    )
    total_count: int = Field(description="中文：计划生成题目总数")
    success_count: int = Field(description="中文：生成成功的题目数")
    duplicate_count: int = Field(description="中文：重复命中数（历史口径）")
    generated_count: int = Field(description="中文：生成的候选题目数（去重前口径；实际入库数见 success_count）")
    exact_duplicate_count: int = Field(description="中文：精确重复（内容哈希命中）题目数")
    semantic_duplicate_count: int = Field(description="中文：语义重复（向量/LLM 判定）题目数")
    uncertain_count: int = Field(description="中文：去重结论不确定（uncertain）的题目数")
    unfulfilled_count: int = Field(description="中文：因需求不足未生成的题目数")
    failed_count: int = Field(description="中文：生成失败的题目数")
    dedup_review_status: str = Field(
        description="中文：去重人工复核状态（manual_review_required=待人工复核；"
        "deduplicated=已去重；clean=无重复）"
    )
    dedup_manual_review_count: int = Field(
        description="中文：去重待人工复核记录数"
    )
    enable_ai_review: bool = Field(
        description="中文：是否开启 AI 审核（任务创建时的开关）"
    )
    ai_review_status: str = Field(
        description="中文：AI 审核状态（not_requested|queued|running|completed|partial|failed）"
    )
    ai_review_total_count: int = Field(description="中文：进入 AI 审核的题目总数")
    ai_review_processed_count: int = Field(description="中文：AI 审核已处理题目数")
    ai_auto_approved_count: int = Field(description="中文：AI 自动通过题目数")
    ai_auto_rejected_count: int = Field(description="中文：AI 自动驳回题目数")
    ai_manual_review_count: int = Field(description="中文：AI 转人工复核题目数")
    ai_review_failed_count: int = Field(description="中文：AI 审核执行失败题目数")
    ai_review_skipped_count: int = Field(description="中文：AI 审核准入跳过题目数")
    ai_review_pending_count: int = Field(description="中文：AI 审核未处理题目数")
    progress: int = Field(description="中文：任务进度百分比（0-100）")
    error_summary: Optional[str] = Field(
        default=None, description="中文：错误摘要（无错误时为 null）"
    )
    started_at: Optional[str] = Field(
        default=None, description="中文：开始执行时间（ISO8601 字符串，可空）"
    )
    completed_at: Optional[str] = Field(
        default=None, description="中文：完成时间（ISO8601 字符串，可空）"
    )
    created_at: Optional[str] = Field(
        default=None, description="中文：创建时间（ISO8601 字符串，可空）"
    )
    questions: List[GenerationTaskQuestionItem] = Field(
        default_factory=list,
        description="中文：任务生成的题目摘要列表（仅含轻量字段，不含答案与选项）",
    )


class QuestionManualReviewResponse(BaseModel):
    """题目人工审核结果响应（POST /question-generation/questions/{question_id}/review 的 data）。

    题目不存在或状态不允许时 data 为 null（业务码 40401/40001）。
    """

    question_id: int = Field(description="中文：题目 ID")
    status: str = Field(description="中文：审核后的题目状态（published=通过上架；rejected=驳回，软驳回不删数据）")
    reviewed_by: int = Field(description="中文：审核人（管理员） ID")
    reviewed_at: str = Field(
        description="中文：审核时间（ISO8601 字符串）"
    )
