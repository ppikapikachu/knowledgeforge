"""KnowledgeExtractAgent 的 Pydantic 数据模型定义。

本模块定义了 Agent 工作流中所有环节的数据结构：
    1. DocumentPage / StructuredDocument —— 文档解析后的结构化表示
    2. DocumentChunk —— 文本分块后的单个块
    3. KnowledgeCandidate —— LLM 提取的单个知识点候选
    4. KnowledgeExtractResult —— LLM 对单个 Chunk 的结构化输出
    5. ExtractRunResult —— 整个提取任务的最终结果

所有模型使用 Pydantic v2 定义，支持：
    - 自动字段校验（类型、范围、长度）
    - JSON 序列化/反序列化
    - LangChain 结构化输出（with_structured_output）
"""

from typing import List, Optional

from pydantic import BaseModel, Field


class DocumentPage(BaseModel):
    """文档中的一个页面或章节。

    由 DocumentParser 解析生成，代表文档的逻辑分段。
    不同文件类型的 page_number 含义不同：
        - PDF: 真实页码（从 1 开始）
        - DOCX: None（无真实页码概念）
        - TXT: None
        - MD: None（但 title 会保留 Markdown 标题）
    """

    page_number: Optional[int] = Field(
        default=None,
        description="页码。PDF 文件为真实页码，TXT/MD/DOCX 为 None"
    )
    title: Optional[str] = Field(
        default=None,
        description="页面或章节标题。MD 文件会保留 # ## ### 等标题"
    )
    text: str = Field(
        description="该页面/章节的文本内容"
    )


class StructuredDocument(BaseModel):
    """解析后的结构化文档。

    DocumentParser 的输出，包含文档的完整信息：
        - 元信息：文件名、文件类型
        - 内容：按页面/章节组织的文本列表 + 完整文本
    """

    file_name: str = Field(
        description="原始文件名，如 'android-interview.pdf'"
    )
    file_type: str = Field(
        description="文件类型: pdf / docx / txt / md"
    )
    pages: List[DocumentPage] = Field(
        default_factory=list,
        description="按页面/章节组织的文本列表"
    )
    full_text: str = Field(
        description="文档的完整文本内容（所有页面拼接）"
    )


class DocumentChunk(BaseModel):
    """文档分块后的单个 Chunk。

    TextChunker 的输出，每个 Chunk 包含：
        - 文本内容
        - 来源位置信息（用于追溯知识点来源）
        - 唯一标识（用于关联知识点与 Chunk）

    位置信息说明：
        - page_start/page_end: 在原始文档中的页码范围
        - char_start/char_end: 在 full_text 中的字符位置范围
    """

    chunk_id: str = Field(
        description="Chunk 唯一标识，格式如 'chunk_a1b2c3d4'，由 UUID 生成"
    )
    text: str = Field(
        description="该 Chunk 的文本内容"
    )
    title: Optional[str] = Field(
        default=None,
        description="所属章节标题（从 DocumentPage 继承）"
    )
    page_start: Optional[int] = Field(
        default=None,
        description="起始页码"
    )
    page_end: Optional[int] = Field(
        default=None,
        description="结束页码"
    )
    char_start: int = Field(
        description="在 full_text 中的起始字符位置（含）"
    )
    char_end: int = Field(
        description="在 full_text 中的结束字符位置（不含）"
    )


class KnowledgeCandidate(BaseModel):
    """从 Chunk 中提取的单个知识点候选。

    这是 LLM 结构化输出的核心对象，每个字段都有严格的校验规则：
        - name: 5~200 字，简短明确，如"Activity生命周期"
        - summary: 1~1000 字，概述这个知识点是什么
        - content: 非空，基于原文整理的完整内容
        - difficulty: 1/2/3，无依据时默认 2
        - keywords: 1~15 个，每个词简短
        - source_*: 来源追溯信息，必须正确填写

    注意：
        - 禁止凭空补充原文不存在的知识（防幻觉）
        - 允许返回空列表（当 Chunk 不含可学习内容时）
    """

    name: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="知识点名称，简短明确，如'Activity生命周期'、'Java线程池'"
    )
    summary: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="1~3 句话概述这个知识点是什么"
    )
    content: str = Field(
        ...,
        min_length=1,
        description="基于原文整理的完整知识点内容。可以总结和结构化，但禁止虚构"
    )
    difficulty: int = Field(
        ...,
        ge=1,
        le=3,
        description="难度: 1=简单（基础概念）, 2=中等（需理解原理）, 3=困难（深入原理或复杂场景）"
    )
    keywords: List[str] = Field(
        ...,
        min_length=1,
        max_length=15,
        description="3~8 个关键词，每个词简短，如['Activity','生命周期','onCreate']"
    )
    source_chunk_id: str = Field(
        description="来源 Chunk 的 ID，用于追溯知识点来自哪个 Chunk"
    )
    source_title: Optional[str] = Field(
        default=None,
        description="来源章节标题"
    )
    source_page_start: Optional[int] = Field(
        default=None,
        description="来源起始页码"
    )
    source_page_end: Optional[int] = Field(
        default=None,
        description="来源结束页码"
    )


class KnowledgeExtractResult(BaseModel):
    """LLM 对单个 Chunk 的结构化输出。

    作为 LangChain with_structured_output 的目标 Schema，
    LLM 会被要求严格按照此格式返回 JSON。

    knowledge_points 允许为空数组，表示当前 Chunk 不含可提取的知识点。
    """

    knowledge_points: List[KnowledgeCandidate] = Field(
        default_factory=list,
        description="从当前 Chunk 提取的知识点列表。无可提取内容时返回空数组"
    )


class ExtractRunResult(BaseModel):
    """整个提取任务的最终结果。

    由 LangGraph 工作流的 merge_results 节点生成，
    汇总了所有 Chunk 的提取结果和处理过程中的错误。

    字段说明：
        - run_id: 本次运行的唯一标识，格式如 'run_a1b2c3d4e5f6'
        - chunk_count: 文档被切分的 Chunk 总数
        - knowledge_count: 最终提取的知识点总数
        - errors: 处理过程中的错误列表（如某个 Chunk 的 LLM 调用失败）
    """

    run_id: str = Field(
        description="本次运行的唯一标识"
    )
    file_name: str = Field(
        description="原始文件名"
    )
    chunk_count: int = Field(
        description="文档被切分的 Chunk 总数"
    )
    knowledge_count: int = Field(
        description="最终提取的知识点总数"
    )
    knowledge_points: List[KnowledgeCandidate] = Field(
        default_factory=list,
        description="所有 Chunk 提取的知识点合并列表"
    )
    errors: List[str] = Field(
        default_factory=list,
        description="处理过程中的错误信息列表"
    )
