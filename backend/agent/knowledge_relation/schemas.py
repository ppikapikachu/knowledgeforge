"""KnowledgeRelationAgent 的 Pydantic 数据模型定义。

定义关系判断的输入、单条判定结果和总响应结构。
本阶段只生成关系建议，不写入 knowledge_relation 表。
"""

from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class RelationKnowledgeInput(BaseModel):
    """知识点输入对象。"""

    id: int = Field(
        ...,
        description="知识点唯一 ID",
        examples=[1001],
    )
    name: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="知识点名称",
        examples=["Java 线程池"],
    )
    summary: str = Field(
        default="",
        max_length=1000,
        description="知识点概述，1~3 句话",
        examples=["线程池用于复用线程并管理并发任务执行。"],
    )
    content: str = Field(
        default="",
        description="知识点内容（建议截断到 500 字以内）",
        examples=["线程池通过任务队列、线程复用和拒绝策略等机制管理任务。"],
    )
    keywords: List[str] = Field(
        default_factory=list,
        description="关键词列表",
        examples=[["Java", "并发", "线程池"]],
    )


class KnowledgeRelationJudgement(BaseModel):
    """单个候选知识点的关系判定结果。"""

    candidate_knowledge_id: int = Field(
        description="被判断的候选知识 ID",
        examples=[1002],
    )
    decision: Literal["RELATION", "NO_RELATION"] = Field(
        description="RELATION=存在关系，NO_RELATION=无关系",
        examples=["RELATION"],
    )
    relation_type: Optional[
        Literal["prerequisite", "related", "extension", "contrast"]
    ] = Field(
        default=None,
        description=(
            "关系类型。prerequisite=前置知识，related=相关知识，"
            "extension=扩展知识，contrast=对比知识。NO_RELATION 时为 null"
        ),
        examples=["prerequisite"],
    )
    from_knowledge_id: Optional[int] = Field(
        default=None,
        description=(
            "有方向关系的语义起点。prerequisite=前置知识，"
            "extension=基础知识。NO_RELATION 时为 null"
        ),
        examples=[1002],
    )
    to_knowledge_id: Optional[int] = Field(
        default=None,
        description="有方向关系的语义终点。NO_RELATION 时为 null",
        examples=[1001],
    )
    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="置信度 (0~1)，仅辅助评估，非校准概率",
        examples=[0.86],
    )
    reason: str = Field(
        default="",
        description="判断理由，简短说明为什么存在/不存在关系",
        examples=["线程池建立在多线程并发执行机制之上。"],
    )


class RelationExtractOutput(BaseModel):
    """LLM 批量关系判断的结构化输出（内部使用）。"""

    judgements: List[KnowledgeRelationJudgement] = Field(
        default_factory=list,
        description="关系判定结果列表",
    )


class RelationTestRequest(BaseModel):
    """关系测试 API 请求体。"""

    source_knowledge_id: Optional[int] = Field(
        default=None,
        description=(
            "锚点知识点 ID（从数据库读取）。"
            "与 source_knowledge 二选一，必须提供其中一个"
        ),
        examples=[1001],
    )
    source_knowledge: Optional[RelationKnowledgeInput] = Field(
        default=None,
        description=(
            "人工提供的锚点知识点对象（用于独立测试）。"
            "与 source_knowledge_id 二选一"
        ),
    )
    candidates: Optional[List[RelationKnowledgeInput]] = Field(
        default=None,
        description=(
            "人工提供的候选知识点列表。提供后跳过 Vector DB 直接判断。"
            "传空数组表示无候选（不会触发自动检索）"
        ),
    )
    candidate_knowledge_ids: Optional[List[int]] = Field(
        default=None,
        description="候选知识点 ID 列表（从数据库读取详情）。与 candidates 不可同时提供",
        examples=[[1002, 1003, 1004]],
    )
    top_k: int = Field(
        default=10,
        ge=1,
        le=50,
        description="自动检索模式下的候选数量（默认 10）",
        examples=[10],
    )
    min_confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="置信度过滤阈值，低于此值的结果不返回（默认 0 不过滤）",
        examples=[0.5],
    )


class RelationEvaluationItem(BaseModel):
    """响应中的单条评估结果。"""

    candidate_knowledge_id: int = Field(description="候选知识 ID")
    decision: str = Field(description="RELATION 或 NO_RELATION")
    relation_type: Optional[str] = Field(
        description="关系类型（prerequisite/related/extension/contrast），无关系时为 null"
    )
    from_knowledge_id: Optional[int] = Field(
        description="方向起点 ID，无方向或无关系时为 null"
    )
    to_knowledge_id: Optional[int] = Field(
        description="方向终点 ID，无方向或无关系时为 null"
    )
    confidence: float = Field(description="置信度 (0~1)")
    reason: str = Field(description="判断理由")


class RelationTestResponse(BaseModel):
    """关系测试 API 响应体。"""

    source_knowledge_id: Optional[int] = Field(
        description="锚点知识点 ID",
    )
    retrieval_mode: str = Field(
        description="候选来源模式：provided_candidates=人工候选 / auto_search=向量检索 / provided_ids=指定ID",
    )
    candidate_count: int = Field(description="候选总数")
    relation_count: int = Field(description="判定为有关系的数量")
    no_relation_count: int = Field(description="判定为无关系的数量")
    llm_call_count: int = Field(description="LLM 调用次数")
    elapsed_ms: int = Field(description="总耗时（毫秒）")
    saved: bool = Field(
        default=False,
        description="是否已保存到数据库（本阶段固定 false，不会写入 knowledge_relation）",
    )
    evaluations: List[RelationEvaluationItem] = Field(
        default_factory=list,
        description="每个候选的判定结果列表",
    )
    errors: List[str] = Field(
        default_factory=list,
        description="处理过程中的错误信息",
    )
