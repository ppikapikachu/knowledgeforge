"""通用文档单元（Document Unit）定义。

文档单元是解析和分块之间的内部中间表示，用于：
    1. 通用边界识别（不依赖单一格式）
    2. 来源追踪（unit_id + 原文偏移）
    3. 提取时的单元隔离（防止跨单元污染）

不是正式知识库表，不入库。
"""

from typing import List, Optional

from pydantic import BaseModel, Field


class DocumentUnit(BaseModel):
    """通用文档单元。"""

    unit_id: str = Field(description="单元唯一 ID，如 unit_001")
    text: str = Field(description="单元的原文文本")
    source_start: int = Field(description="在原文中的起始字符位置")
    source_end: int = Field(description="在原文中的结束字符位置")
    unit_kind: str = Field(
        default="unknown",
        description=(
            "单元类型: paragraph/qa/list_item/heading/sentence/unknown。"
            "是识别结果提示，不是硬性前提"
        ),
    )
    section_context: Optional[str] = Field(
        default=None,
        description="所属章节标题（上下文元数据，不作为知识点内容）",
    )
    marker: Optional[str] = Field(
        default=None,
        description="识别到的标记（如 '1、'、'*'、'##'），无标记时为 None",
    )
    boundary_confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="边界识别置信度 (0~1)。低置信度时不强行判定为独立知识点",
    )


class DocumentUnitGroup(BaseModel):
    """一组相关单元（如一道题+答案、一个章节）。"""

    group_id: str = Field(description="组 ID")
    units: List[DocumentUnit] = Field(default_factory=list, description="组内单元列表")
    section_context: Optional[str] = Field(default=None, description="章节上下文")
    total_length: int = Field(default=0, description="组内总文本长度")
