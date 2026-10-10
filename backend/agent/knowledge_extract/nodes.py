"""LangGraph 工作流节点定义模块。

本模块定义了 KnowledgeExtractAgent 工作流中的所有节点函数。
每个节点接收 state 字典作为输入，返回需要更新的 state 字段。

节点列表：
    1. parse_document_node —— 解析文档文件为 StructuredDocument
    2. chunk_document_node —— 将文档切分为 Chunk 列表
    3. extract_current_chunk_node —— 调用 LLM 提取当前 Chunk 的知识点
    4. should_continue_node —— 条件判断，是否有更多 Chunk 需要处理
    5. merge_results_node —— 合并所有 Chunk 的提取结果

节点执行流程：
    parse_document → chunk_document → extract_current_chunk
    → should_continue?
        → YES: extract_current_chunk（循环处理下一个 Chunk）
        → NO: merge_results

关键设计：
    - extract_current_chunk 是唯一调用 LLM 的节点
    - 单个 Chunk 失败不影响其他 Chunk（错误记录到 errors 列表）
    - LLM 返回非法结构时支持重试（最多 AGENT_MAX_RETRIES 次）
"""

import logging
import time
from typing import Any, Dict

from langchain_core.messages import HumanMessage, SystemMessage

from agent.common.config import agent_settings
from agent.common.llm import get_llm
from agent.knowledge_extract.prompts import (
    KNOWLEDGE_EXTRACT_PROMPT_VERSION,
    RETRY_PROMPT_TEMPLATE,
    SYSTEM_PROMPT,
    USER_PROMPT_TEMPLATE,
)
from agent.knowledge_extract.schemas import (
    DocumentChunk,
    KnowledgeExtractResult,
)
from agent.knowledge_extract.validator import KnowledgeValidator

logger = logging.getLogger(__name__)


def parse_document_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """节点：解析文档文件为 StructuredDocument。

    输入 state:
        file_path: 待解析文件的路径

    输出 state 更新:
        document: 解析后的 StructuredDocument

    说明：
        这是一个普通 Tool 节点，不涉及 LLM 调用。
        解析过程是确定性的，相同输入总是产生相同输出。
    """
    from agent.knowledge_extract.parser import DocumentParser

    file_path = state["file_path"]
    logger.info(f"开始解析文档: {file_path}")

    parser = DocumentParser()
    document = parser.parse(file_path)

    logger.info(
        f"文档解析完成: {document.file_name}, "
        f"类型={document.file_type}, "
        f"页面数={len(document.pages)}, "
        f"文本长度={len(document.full_text)}"
    )

    return {"document": document}


def chunk_document_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """节点：将文档切分为 Chunk 列表。

    输入 state:
        document: StructuredDocument

    输出 state 更新:
        chunks: DocumentChunk 列表
        current_chunk_index: 初始化为 0（从第一个 Chunk 开始处理）

    说明：
        这是一个普通 Tool 节点，不涉及 LLM 调用。
        分块策略由 TextChunker 决定，优先按标题/段落边界切分。
    """
    from agent.knowledge_extract.chunker import TextChunker

    document = state["document"]
    logger.info(f"开始分块文档: {document.file_name}")

    chunker = TextChunker()
    chunks = chunker.chunk(document)

    logger.info(f"文档分块完成，共 {len(chunks)} 个 Chunk")

    return {"chunks": chunks, "current_chunk_index": 0}


def extract_current_chunk_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """节点：调用 LLM 从当前 Chunk 提取知识点（核心节点）。

    这是整个工作流中唯一调用 LLM 的节点。

    处理流程：
        1. 获取当前 Chunk（根据 current_chunk_index）
        2. 构造 System Prompt + User Prompt
        3. 使用 with_structured_output 绑定 Pydantic Schema
        4. 调用 LLM 获取结构化输出
        5. 校验提取结果（KnowledgeValidator）
        6. 如果失败，重试最多 AGENT_MAX_RETRIES 次
        7. 将结果追加到 results 列表

    错误处理：
        - 单个 Chunk 的 LLM 调用失败不会导致整个任务崩溃
        - 失败的 Chunk 会被记录到 errors 列表
        - 其他 Chunk 继续正常处理

    输入 state:
        chunks: Chunk 列表
        current_chunk_index: 当前处理的 Chunk 索引
        results: 已有的提取结果列表
        errors: 已有的错误列表
        file_name: 文件名

    输出 state 更新:
        results: 追加当前 Chunk 的提取结果
        errors: 可能追加新的错误信息
        current_chunk_index: +1（指向下一个 Chunk）
    """
    chunks = state["chunks"]
    current_index = state["current_chunk_index"]
    results = state.get("results", [])
    errors = state.get("errors", [])
    file_name = state.get("file_name", "unknown")

    # 索引越界检查
    if current_index >= len(chunks):
        return {"results": results, "errors": errors}

    chunk = chunks[current_index]
    logger.info(
        f"开始提取 Chunk {current_index + 1}/{len(chunks)}: "
        f"{chunk.chunk_id} ({len(chunk.text)} 字符)"
    )

    # 获取 LLM 实例（知识提取：关闭思考模式）
    llm = get_llm(thinking="disabled")
    validator = KnowledgeValidator()

    # 构造用户提示词，填充文档信息和 Chunk 文本
    page_range = _format_page_range(chunk.page_start, chunk.page_end)
    user_prompt = USER_PROMPT_TEMPLATE.format(
        file_name=file_name,
        chunk_title=chunk.title or "无标题",
        chunk_id=chunk.chunk_id,
        page_range=page_range,
        text=chunk.text,
    )

    # 使用 LangChain 的结构化输出功能
    # LLM 会被要求严格按照 KnowledgeExtractResult 的 Schema 返回 JSON
    structured_llm = llm.with_structured_output(KnowledgeExtractResult)

    start_time = time.time()
    result = None
    last_error = None

    # 带重试的 LLM 调用
    max_retries = agent_settings.AGENT_MAX_RETRIES
    for attempt in range(max_retries + 1):
        try:
            if attempt == 0:
                # ---- 首次调用 ----
                messages = [
                    SystemMessage(content=SYSTEM_PROMPT),
                    HumanMessage(content=user_prompt),
                ]
            else:
                # ---- 重试调用：附带错误信息引导 LLM 修正 ----
                retry_prompt = RETRY_PROMPT_TEMPLATE.format(
                    error_message=str(last_error),
                    file_name=file_name,
                    chunk_title=chunk.title or "无标题",
                    chunk_id=chunk.chunk_id,
                    text=chunk.text,
                )
                messages = [
                    SystemMessage(content=SYSTEM_PROMPT),
                    HumanMessage(content=retry_prompt),
                ]

            # 调用 LLM
            result = structured_llm.invoke(messages)
            duration = time.time() - start_time

            # 校验提取结果
            valid_candidates, validation_errors = validator.validate_candidates(
                result.knowledge_points, chunk.chunk_id
            )

            # 记录校验错误（不阻断流程）
            if validation_errors:
                errors.extend(validation_errors)

            # 只保留通过校验的候选
            result.knowledge_points = valid_candidates

            logger.info(
                f"Chunk {chunk.chunk_id}: 提取了 {len(valid_candidates)} 个知识点，"
                f"耗时 {duration:.1f}s（第 {attempt + 1} 次尝试）"
            )

            results.append(result)
            break  # 成功，跳出重试循环

        except Exception as e:
            last_error = e
            duration = time.time() - start_time
            logger.warning(
                f"Chunk {chunk.chunk_id} 提取失败"
                f"（第 {attempt + 1} 次尝试）: {e}"
            )

            # 重试耗尽，记录错误并继续下一个 Chunk
            if attempt == max_retries:
                error_msg = (
                    f"Chunk {chunk.chunk_id} 提取失败"
                    f"（重试 {max_retries} 次）: {str(e)}"
                )
                errors.append(error_msg)
                logger.error(error_msg)

    return {
        "results": results,
        "errors": errors,
        "current_chunk_index": current_index + 1,
    }


def should_continue_node(state: Dict[str, Any]) -> str:
    """条件边：判断是否还有更多 Chunk 需要处理。

    这是一个条件节点，根据 current_chunk_index 和 chunks 长度
    决定下一步走向：
        - 还有 Chunk → 返回 "extract_current_chunk"（继续处理）
        - 全部处理完 → 返回 "merge_results"（合并结果）
    """
    chunks = state["chunks"]
    current_index = state["current_chunk_index"]

    if current_index < len(chunks):
        return "extract_current_chunk"
    else:
        return "merge_results"


def merge_results_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """节点：合并所有 Chunk 的提取结果为最终列表。

    遍历所有 Chunk 的提取结果，将知识点汇总到一个列表中。
    这个列表就是最终返回给用户的 knowledge_points。

    输入 state:
        results: 各 Chunk 的 KnowledgeExtractResult 列表
        errors: 错误信息列表

    输出 state 更新:
        merged_knowledge: 合并后的所有 KnowledgeCandidate 列表
    """
    results = state.get("results", [])
    errors = state.get("errors", [])

    # 遍历所有 Chunk 结果，提取知识点
    all_knowledge = []
    for result in results:
        if result and result.knowledge_points:
            all_knowledge.extend(result.knowledge_points)

    logger.info(
        f"结果合并完成: 共 {len(all_knowledge)} 个知识点, "
        f"{len(errors)} 个错误"
    )

    return {"merged_knowledge": all_knowledge}


def _format_page_range(start: int, end: int) -> str:
    """格式化页码范围为可读字符串。

    示例：
        _format_page_range(1, 1) → "第1页"
        _format_page_range(1, 5) → "第1-5页"
        _format_page_range(None, None) → "未知"
    """
    if start is None and end is None:
        return "未知"
    if start == end or end is None:
        return f"第{start}页" if start else "未知"
    return f"第{start}-{end}页"
