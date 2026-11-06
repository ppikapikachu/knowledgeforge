"""题目去重人工复核 Schema（API 修复与人工复核接口开发执行文档 §3）。"""

from typing import Any, Dict, List, Literal, Optional

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


# =====================================================================
# 去重索引状态 / 记录 / 统计 / 重建响应模型（question_dedup 路由使用）
# =====================================================================


class QuestionDedupFailureItem(BaseModel):
    """索引构建失败明细项（status.failures 与 rebuild.recent_failures 的元素）。"""

    question_id: Optional[int] = Field(
        default=None, description="中文：失败题目 ID（失败发生在题目定位前时为 null）"
    )
    error: Optional[str] = Field(
        default=None, description="中文：失败原因（错误信息，超长截断至 500 字符）"
    )


class QuestionDedupThresholdsResponse(BaseModel):
    """去重阈值配置（GET /question-dedup/status 的 data.thresholds）。"""

    same_scope_candidate_threshold: float = Field(
        description="中文：同范围候选阈值（相似度达到该值才进入候选，默认 0.65）"
    )
    cross_scope_high_threshold: float = Field(
        description="中文：跨范围高相似阈值（默认 0.75）"
    )
    final_block_threshold: float = Field(
        description="中文：最终拦截阈值（相似度达到该值直接判 duplicate，默认 0.85）"
    )
    vector_top_k: int = Field(description="中文：向量召回候选条数（默认 15）")
    keyword_top_k: int = Field(description="中文：关键词召回候选条数（默认 15）")
    llm_max_candidates_per_question: int = Field(
        description="中文：每题送入 LLM 判定的最大候选数（默认 5）"
    )
    llm_batch_size: int = Field(description="中文：LLM 判定批量大小（默认 5）")


class QuestionDedupStatusResponse(BaseModel):
    """去重索引状态响应（GET /question-dedup/status 的 data）。"""

    enabled: bool = Field(description="中文：去重功能总开关（QUESTION_DEDUP_ENABLED）")
    status: Optional[str] = Field(
        default=None,
        description="中文：索引状态（ready=就绪；initializing=构建中；degraded=降级；disabled=已关闭）",
    )
    reason: Optional[str] = Field(
        default=None, description="中文：状态原因说明（正常时为 null）"
    )
    stats: Dict[str, Any] = Field(
        default_factory=dict,
        description="中文：索引构建统计（动态字典，常见键 total/success/failed/skipped/"
        "duration_seconds/embedding_model/embedding_version）",
    )
    failures: List[QuestionDedupFailureItem] = Field(
        default_factory=list,
        description="中文：索引构建失败明细（当前实现恒为空数组，失败记录见 stats）",
    )
    blocking_question_count: int = Field(
        description="中文：处于待审核/已发布状态、会拦截出题的题目数"
    )
    thresholds: QuestionDedupThresholdsResponse = Field(
        description="中文：去重阈值配置快照"
    )
    hash_version: str = Field(
        description="中文：内容哈希算法版本（当前为 \"2\"）"
    )


class QuestionDedupRecordItem(BaseModel):
    """去重记录列表条目（GET /question-dedup/records 的 data.items 元素）。"""

    id: int = Field(description="中文：去重记录 ID")
    task_id: Optional[int] = Field(
        default=None, description="中文：关联出题任务 ID（非出题触发时为 null）"
    )
    new_content_hash: str = Field(description="中文：新题目内容哈希（sha256 hex）")
    new_hash_version: str = Field(
        description="中文：新题目哈希算法版本（当前为 \"2\"）"
    )
    new_question_type: str = Field(description="中文：新题目题型")
    new_question_bank_id: Optional[int] = Field(
        default=None, description="中文：新题目所属题库 ID（可空）"
    )
    new_knowledge_ids: Optional[List[int]] = Field(
        default=None, description="中文：新题目关联知识点 ID 列表（可空）"
    )
    new_content_snapshot: str = Field(
        description="中文：新题目内容快照（用于人工复核比对）"
    )
    matched_question_id: Optional[int] = Field(
        default=None, description="中文：命中（疑似重复）的既有题目 ID（未命中为 null）"
    )
    matched_question_bank_id: Optional[int] = Field(
        default=None, description="中文：命中题目所属题库 ID（可空）"
    )
    matched_knowledge_ids: Optional[List[int]] = Field(
        default=None, description="中文：命中题目关联知识点 ID 列表（可空）"
    )
    matched_source: Optional[str] = Field(
        default=None, description="中文：命中来源说明（可空）"
    )
    scope_mode: Optional[str] = Field(
        default=None,
        description="中文：比对范围模式（global_exact/batch_internal/same_scope/cross_scope）",
    )
    keyword_score: float = Field(description="中文：关键词相似度得分（0-1）")
    vector_score: float = Field(description="中文：向量相似度得分（0-1）")
    algorithm_score: float = Field(description="中文：算法综合得分（0-1）")
    llm_called: bool = Field(description="中文：是否调用了 LLM 判定")
    llm_decision: Optional[str] = Field(
        default=None, description="中文：LLM 判定结论（duplicate/distinct/uncertain，未调用为 null）"
    )
    llm_reason: Optional[str] = Field(
        default=None, description="中文：LLM 判定理由（可空）"
    )
    decision: str = Field(
        description="中文：自动判定结论（duplicate/distinct/uncertain）"
    )
    decision_method: str = Field(
        description="中文：判定方式（exact_hash/algorithm_only/vector_and_llm/batch_internal）"
    )
    needs_manual_review: bool = Field(description="中文：是否需要人工复核")
    manual_resolution: Optional[str] = Field(
        default=None, description="中文：人工复核结论（duplicate/distinct，未处理为 null）"
    )
    effective_decision: str = Field(
        description="中文：最终生效结论（有人工结论时优先人工结论，否则为自动结论）"
    )
    resolution_reason: Optional[str] = Field(
        default=None, description="中文：人工复核理由（可空）"
    )
    resolved_by: Optional[int] = Field(
        default=None, description="中文：人工复核处理人（管理员 ID，未处理为 null）"
    )
    resolved_at: Optional[str] = Field(
        default=None, description="中文：人工复核处理时间（ISO8601 字符串，可空）"
    )
    created_at: Optional[str] = Field(
        default=None, description="中文：记录创建时间（ISO8601 字符串，可空）"
    )


class QuestionDedupStatsResponse(BaseModel):
    """任务去重统计响应（GET /question-dedup/stats/{task_id} 的 data）。"""

    task_id: Optional[int] = Field(
        default=None, description="中文：生成任务 ID"
    )
    records: int = Field(description="中文：去重记录总数")
    by_decision: Dict[str, int] = Field(
        default_factory=dict,
        description="中文：按自动判定结论分组的记录数（键=结论分类 duplicate/distinct/uncertain，值=计数）",
    )
    by_method: Dict[str, int] = Field(
        default_factory=dict,
        description="中文：按判定方式分组的记录数（键=\"结论:判定方式\"，如 uncertain:algorithm_only，值=计数）",
    )
    llm_called: int = Field(description="中文：调用 LLM 判定的记录数")


class QuestionDedupIndexRebuildResponse(BaseModel):
    """索引重建响应（POST /question-dedup/index/rebuild 的 data）。

    取值为重建过程的状态快照；stats 为重建统计动态字典（常见键 total/success/failed/skipped，
    还可能含 duration_seconds/embedding_model/embedding_version）。
    """

    status: str = Field(
        default="",
        description="中文：重建后索引状态（ready/initializing/degraded/disabled）",
    )
    reason: Optional[str] = Field(
        default=None, description="中文：状态原因说明（正常时为 null）"
    )
    stats: Dict[str, Any] = Field(
        default_factory=dict,
        description="中文：重建统计（动态字典：total/success/failed/skipped 等）",
    )
    failure_count: int = Field(
        default=0, description="中文：重建失败条目数"
    )
    recent_failures: List[QuestionDedupFailureItem] = Field(
        default_factory=list,
        description="中文：最近的重建失败明细（最多保留 5 条）",
    )
