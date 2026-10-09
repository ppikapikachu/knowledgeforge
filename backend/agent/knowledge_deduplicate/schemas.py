"""KnowledgeDeduplicateAgent 的 Pydantic 数据模型定义。

本模块定义了去重流程中所有环节的数据结构：
    1. ExistingKnowledge —— 已有知识点（从数据库或测试输入获取）
    2. NormalizedKnowledge —— 标准化后的知识点
    3. DeduplicateDecision —— 去重决策结果（NEW/DUPLICATE/MERGE）
    4. MergedKnowledge —— 合并后的知识点（仅 MERGE 时有值）
"""

from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class ExistingKnowledge(BaseModel):
    """已有知识点（来自数据库或测试输入）。

    用于与候选知识点进行相似度比较。
    similarity 字段由向量检索填充。
    """

    id: int = Field(description="已有知识点的数据库 ID")
    name: str = Field(description="知识点名称")
    summary: str = Field(description="知识点概述")
    content: str = Field(description="知识点完整内容")
    difficulty: int = Field(description="难度: 1/2/3")
    keywords: List[str] = Field(default_factory=list, description="关键词列表")
    similarity: float = Field(
        default=0.0,
        description="与候选知识点的相似度分数（0~1）"
    )


class MergedKnowledge(BaseModel):
    """合并后的知识点（仅 decision=MERGE 时有值）。

    由 LLM Agent 生成，包含已有知识点和候选知识点的合并内容。
    要求：
        - 不能凭空增加知识
        - 不能丢失重要信息
        - 不能改变原知识语义
    """

    name: str = Field(description="合并后的知识点名称")
    summary: str = Field(description="合并后的概述")
    content: str = Field(description="合并后的完整内容")
    difficulty: int = Field(description="合并后的难度")
    keywords: List[str] = Field(description="合并后的关键词列表")


class DeduplicateDecision(BaseModel):
    """去重决策结果。

    这是 DeduplicatePipeline 的最终输出，包含：
        - decision: NEW / DUPLICATE / MERGE
        - target_knowledge_id: 目标知识点 ID（DUPLICATE/MERGE 时有值）
        - confidence: 决策置信度（0~1）
        - reason: 决策理由
        - merged_knowledge: 合并后的知识点（仅 MERGE 时有值）
    """

    decision: Literal["NEW", "DUPLICATE", "MERGE"] = Field(
        description="去重决策: NEW=新增, DUPLICATE=重复, MERGE=合并"
    )
    target_knowledge_id: Optional[int] = Field(
        default=None,
        description="目标知识点 ID。NEW 时为 None，DUPLICATE/MERGE 时为已有知识点 ID"
    )
    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="决策置信度（0~1）"
    )
    reason: str = Field(
        default="",
        description="决策理由"
    )
    merged_knowledge: Optional[MergedKnowledge] = Field(
        default=None,
        description="合并后的知识点。仅 decision=MERGE 时有值"
    )


class DeduplicateResult(BaseModel):
    """单个候选知识点的去重结果。

    包含候选知识点信息和去重决策。
    """

    candidate_name: str = Field(description="候选知识点名称")
    decision: DeduplicateDecision = Field(description="去重决策")
    exact_match: bool = Field(
        default=False,
        description="是否精确匹配（名称完全相同）"
    )
    top_similarity: float = Field(
        default=0.0,
        description="最高相似度分数"
    )
    method: str = Field(
        default="unknown",
        description="判定方法: exact_match / rule / llm"
    )


class DeduplicatePipelineResult(BaseModel):
    """整个去重 Pipeline 的最终结果。

    汇总所有候选知识点的去重结果和统计信息。
    """

    total_candidates: int = Field(description="候选知识点总数")
    new_count: int = Field(description="新增知识点数")
    duplicate_count: int = Field(description="重复知识点数")
    merge_count: int = Field(description="合并知识点数")
    llm_call_count: int = Field(description="LLM 调用次数")
    embedding_count: int = Field(description="Embedding 调用次数")
    results: List[DeduplicateResult] = Field(
        default_factory=list,
        description="每个候选知识点的去重结果"
    )
    errors: List[str] = Field(
        default_factory=list,
        description="处理过程中的错误"
    )
