"""LangGraph 工作流定义模块。

本模块使用 LangGraph 编排 KnowledgeExtractAgent 的完整执行流程。
工作流由多个节点组成，通过边和条件边连接。

工作流结构：
    START
      ↓
    parse_document（解析文档文件）
      ↓
    chunk_document（文本分块）
      ↓
    extract_current_chunk（调用 LLM 提取知识点）
      ↓
    should_continue?（是否还有更多 Chunk？）
      ├── YES → extract_current_chunk（循环）
      └── NO  → merge_results（合并结果）
                  ↓
                END

为什么使用 LangGraph：
    1. 后续会扩展更多 Agent（去重、关系、题目生成等）
    2. LangGraph 天然支持多节点编排和条件分支
    3. 方便后续加入并行处理、人工审核等节点
    4. 状态管理清晰，每个节点的输入输出都有明确类型

当前阶段保持简单：
    - 串行处理 Chunk（不并行）
    - 不接入数据库
    - 不接入正式 ImportTask
"""

import logging
import uuid
from typing import Any, Dict, List, TypedDict

from langgraph.graph import END, START, StateGraph

from agent.knowledge_extract.nodes import (
    chunk_document_node,
    extract_current_chunk_node,
    merge_results_node,
    parse_document_node,
    should_continue_node,
)
from agent.knowledge_extract.schemas import (
    DocumentChunk,
    ExtractRunResult,
    KnowledgeCandidate,
    KnowledgeExtractResult,
    StructuredDocument,
)

logger = logging.getLogger(__name__)


class KnowledgeExtractState(TypedDict):
    """LangGraph 工作流状态定义。

    所有节点共享此状态字典，通过键名读写数据。
    LangGraph 会自动管理状态的传递和更新。

    字段说明：
        file_path: 输入文件的路径
        file_name: 原始文件名（用于日志和结果返回）
        document: DocumentParser 解析后的结构化文档
        chunks: TextChunker 切分后的 Chunk 列表
        current_chunk_index: 当前正在处理的 Chunk 索引
        results: 各 Chunk 的 LLM 提取结果列表
        errors: 处理过程中的错误信息列表
        merged_knowledge: 最终合并的知识点列表
    """
    file_path: str
    file_name: str
    document: StructuredDocument | None
    chunks: List[DocumentChunk]
    current_chunk_index: int
    results: List[KnowledgeExtractResult]
    errors: List[str]
    merged_knowledge: List[KnowledgeCandidate]


def build_graph() -> StateGraph:
    """构建 LangGraph 工作流图。

    注册所有节点和边，定义执行流程。
    编译后的图可以反复调用，每次传入不同的初始状态。

    Returns:
        StateGraph: 未编译的工作流图
    """
    graph = StateGraph(KnowledgeExtractState)

    # ---- 注册节点 ----
    graph.add_node("parse_document", parse_document_node)       # 解析文档
    graph.add_node("chunk_document", chunk_document_node)       # 文本分块
    graph.add_node("extract_current_chunk", extract_current_chunk_node)  # LLM 提取
    graph.add_node("merge_results", merge_results_node)         # 合并结果

    # ---- 注册边（无条件跳转） ----
    graph.add_edge(START, "parse_document")           # 入口 → 解析文档
    graph.add_edge("parse_document", "chunk_document")  # 解析 → 分块
    graph.add_edge("chunk_document", "extract_current_chunk")  # 分块 → 提取

    # ---- 注册条件边（根据状态决定走向） ----
    graph.add_conditional_edges(
        "extract_current_chunk",    # 源节点
        should_continue_node,       # 条件判断函数
        {
            "extract_current_chunk": "extract_current_chunk",  # 还有 Chunk → 继续提取
            "merge_results": "merge_results",                  # 全部完成 → 合并结果
        },
    )

    graph.add_edge("merge_results", END)  # 合并 → 结束

    return graph


# 编译后的图实例缓存（单例）
# 避免每次调用都重新编译图
_app = None


def get_graph_app():
    """获取编译后的 LangGraph 应用实例。

    首次调用时编译图并缓存，后续直接返回缓存的实例。
    """
    global _app
    if _app is None:
        graph = build_graph()
        _app = graph.compile()
    return _app


def run_extraction(file_path: str, file_name: str) -> ExtractRunResult:
    """执行完整的知识点提取流程。

    这是 Agent 的主入口函数，接收文件路径，返回提取结果。

    Args:
        file_path: 待处理文件的路径
        file_name: 原始文件名（用于日志和结果返回）

    Returns:
        ExtractRunResult: 包含所有提取的知识点和错误信息

    处理流程：
        1. 生成唯一的 run_id
        2. 初始化工作流状态
        3. 调用 LangGraph 工作流
        4. 从最终状态中提取结果
        5. 返回 ExtractRunResult

    错误处理：
        - 如果整个工作流执行失败（如文件解析错误），返回包含错误信息的结果
        - 单个 Chunk 的失败由 nodes.py 内部处理，不会导致整个任务失败
    """
    run_id = f"run_{uuid.uuid4().hex[:12]}"
    logger.info(f"开始提取任务 {run_id}，文件: {file_name}")

    app = get_graph_app()

    # 初始化工作流状态
    # 状态是工作流的核心，用于存储和传递信息。
    initial_state: KnowledgeExtractState = {
        "file_path": file_path,
        "file_name": file_name,
        "document": None,
        "chunks": [],
        "current_chunk_index": 0,
        "results": [],
        "errors": [],
        "merged_knowledge": [],
    }

    try:
        # 执行工作流
        final_state = app.invoke(initial_state)
    except Exception as e:
        logger.error(f"提取任务 {run_id} 执行失败: {e}")
        return ExtractRunResult(
            run_id=run_id,
            file_name=file_name,
            chunk_count=0,
            knowledge_count=0,
            knowledge_points=[],
            errors=[f"Workflow 执行失败: {str(e)}"],
        )

    # 从最终状态中提取结果
    all_knowledge = final_state.get("merged_knowledge", [])
    errors = final_state.get("errors", [])
    chunks = final_state.get("chunks", [])

    result = ExtractRunResult(
        run_id=run_id,
        file_name=file_name,
        chunk_count=len(chunks),
        knowledge_count=len(all_knowledge),
        knowledge_points=all_knowledge,
        errors=errors,
    )

    logger.info(
        f"提取任务 {run_id} 完成: "
        f"chunks={result.chunk_count}, "
        f"知识点={result.knowledge_count}, "
        f"错误={len(result.errors)}"
    )

    return result
