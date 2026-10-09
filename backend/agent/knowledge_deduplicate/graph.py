"""LangGraph 工作流定义模块。

本模块使用 LangGraph 编排 KnowledgeDeduplicatePipeline 的完整执行流程。

工作流结构：
    START
      ↓
    normalize（标准化候选知识点）
      ↓
    exact_match（精确匹配检查）
      ↓
    embedding（向量嵌入）
      ↓
    vector_search（向量检索相似知识点）
      ↓
    rule_decision（规则判定 NEW/DUPLICATE/AMBIGUOUS）
      ↓
    should_use_llm?（条件边）
      ├── NEW/DUPLICATE → finalize
      └── AMBIGUOUS → llm_decision → finalize
                                ↓
                              END

设计原则：
    - 能用规则判定的不用 LLM（降低 Token 消耗）
    - 只有"不确定"的候选才进入 LLM
    - 单个候选失败不影响其他候选
"""

import logging
from typing import Any, Dict, List, TypedDict

from langgraph.graph import END, START, StateGraph

from agent.knowledge_deduplicate.nodes import (
    embedding_node,
    exact_match_node,
    finalize_node,
    llm_decision_node,
    normalize_node,
    rule_decision_node,
    should_use_llm,
    vector_search_node,
)
from agent.knowledge_deduplicate.schemas import (
    DeduplicateDecision,
    DeduplicatePipelineResult,
    DeduplicateResult,
    ExistingKnowledge,
)
from agent.knowledge_extract.schemas import KnowledgeCandidate

logger = logging.getLogger(__name__)


class DeduplicateState(TypedDict):
    """LangGraph 去重工作流状态定义。

    处理单个候选知识点的状态。
    """
    # 输入
    candidate: KnowledgeCandidate                # 候选知识点
    existing_knowledge_list: List[ExistingKnowledge]  # 已有知识点列表

    # 标准化结果
    normalized_name: str                          # 标准化后的名称
    normalized_summary: str                       # 标准化后的概述
    normalized_keywords: List[str]                # 标准化后的关键词
    embedding_text: str                           # 用于 Embedding 的文本

    # 精确匹配结果
    exact_match_id: int | None                    # 精确匹配的知识点 ID
    exact_match_result: DeduplicateDecision | None  # 精确匹配结果

    # 向量相关
    candidate_vector: List[float] | None          # 候选知识点的向量
    similar_knowledge: List[ExistingKnowledge]    # 相似知识点列表

    # 规则判定结果
    rule_decision: str                            # NEW / DUPLICATE / AMBIGUOUS
    rule_decision_result: DeduplicateDecision | None  # 规则层判定结果

    # LLM 判定结果
    llm_decision: DeduplicateDecision | None      # LLM 判定结果

    # 最终结果
    final_decision: DeduplicateDecision | None    # 最终去重决策
    decision_method: str                          # 判定方法

    # 性能统计
    embedding_time: float                         # Embedding 耗时
    search_time: float                            # 向量检索耗时
    llm_time: float                               # LLM 调用耗时


def build_dedup_graph() -> StateGraph:
    """构建去重工作流图。

    注册所有节点和边，定义执行流程。

    Returns:
        StateGraph: 未编译的工作流图
    """
    graph = StateGraph(DeduplicateState)

    # 注册节点
    graph.add_node("normalize", normalize_node)
    graph.add_node("exact_match", exact_match_node)
    graph.add_node("embedding", embedding_node)
    graph.add_node("vector_search", vector_search_node)
    graph.add_node("rule_decision", rule_decision_node)
    graph.add_node("llm_decision", llm_decision_node)
    graph.add_node("finalize", finalize_node)

    # 注册边（顺序执行）
    graph.add_edge(START, "normalize")
    graph.add_edge("normalize", "exact_match")
    graph.add_edge("exact_match", "embedding")
    graph.add_edge("embedding", "vector_search")
    graph.add_edge("vector_search", "rule_decision")

    # 条件边：规则层判定后决定是否调用 LLM
    graph.add_conditional_edges(
        "rule_decision",
        should_use_llm,
        {
            "finalize": "finalize",     # NEW/DUPLICATE 直接完成
            "llm_decision": "llm_decision",  # AMBIGUOUS 进入 LLM
        },
    )

    graph.add_edge("llm_decision", "finalize")
    graph.add_edge("finalize", END)

    return graph


# 编译后的图实例缓存
_dedup_app = None


def get_dedup_graph_app():
    """获取编译后的去重工作流应用实例。"""
    global _dedup_app
    if _dedup_app is None:
        graph = build_dedup_graph()
        _dedup_app = graph.compile()
    return _dedup_app


def run_dedup_for_candidate(
    candidate: KnowledgeCandidate,
    existing_knowledge_list: List[ExistingKnowledge],
) -> DeduplicateResult:
    """对单个候选知识点执行去重判断。

    Args:
        candidate: 待判断的候选知识点
        existing_knowledge_list: 已有知识点列表

    Returns:
        DeduplicateResult: 去重结果
    """
    app = get_dedup_graph_app()

    initial_state: DeduplicateState = {
        "candidate": candidate,
        "existing_knowledge_list": existing_knowledge_list,
        "normalized_name": "",
        "normalized_summary": "",
        "normalized_keywords": [],
        "embedding_text": "",
        "exact_match_id": None,
        "exact_match_result": None,
        "candidate_vector": None,
        "similar_knowledge": [],
        "rule_decision": "AMBIGUOUS",
        "rule_decision_result": None,
        "llm_decision": None,
        "final_decision": None,
        "decision_method": "unknown",
        "embedding_time": 0.0,
        "search_time": 0.0,
        "llm_time": 0.0,
    }

    try:
        final_state = app.invoke(initial_state)
    except Exception as e:
        logger.error(f"去重判断失败: {candidate.name}: {e}")
        return DeduplicateResult(
            candidate_name=candidate.name,
            decision=DeduplicateDecision(
                decision="NEW",
                target_knowledge_id=None,
                confidence=0.0,
                reason=f"去重流程异常: {str(e)}",
            ),
            exact_match=False,
            top_similarity=0.0,
            method="error",
        )

    final_decision = final_state.get("final_decision")
    if not final_decision:
        final_decision = DeduplicateDecision(
            decision="NEW",
            target_knowledge_id=None,
            confidence=0.0,
            reason="未产生判定结果",
        )

    # 获取最高相似度
    similar = final_state.get("similar_knowledge", [])
    top_similarity = similar[0].similarity if similar else 0.0

    return DeduplicateResult(
        candidate_name=candidate.name,
        decision=final_decision,
        exact_match=final_state.get("exact_match_result") is not None,
        top_similarity=top_similarity,
        method=final_state.get("decision_method", "unknown"),
    )


def run_dedup_pipeline(
    candidates: List[KnowledgeCandidate],
    existing_knowledge_list: List[ExistingKnowledge],
    sync_existing_to_vector: bool = True,
) -> DeduplicatePipelineResult:
    """执行完整的去重 Pipeline。

    处理流程：
        1. 将已有知识点同步到向量存储（如果需要）
        2. 逐个候选知识点执行去重判断
        3. 汇总结果和统计信息

    Args:
        candidates: 候选知识点列表
        existing_knowledge_list: 已有知识点列表
        sync_existing_to_vector: 是否将已有知识点同步到向量存储

    Returns:
        DeduplicatePipelineResult: 完整的去重结果
    """
    from agent.common.embedding import get_embedding_service
    from agent.common.vector_store import get_vector_store

    total_start = time.time()
    results = []
    errors = []
    llm_call_count = 0
    embedding_count = 0

    # 将已有知识点同步到向量存储
    if sync_existing_to_vector and existing_knowledge_list:
        logger.info(f"同步 {len(existing_knowledge_list)} 个已有知识点到向量存储")
        service = get_embedding_service()
        store = get_vector_store()

        from agent.knowledge_deduplicate.normalizer import KnowledgeNormalizer
        normalizer = KnowledgeNormalizer()

        # 批量 Embedding
        texts = [
            normalizer.build_embedding_text(ex.name, ex.summary, ex.keywords)
            for ex in existing_knowledge_list
        ]
        vectors = service.embed_texts(texts)
        embedding_count += len(texts)

        # 批量写入向量存储
        for existing, vector in zip(existing_knowledge_list, vectors):
            store.upsert(
                id=str(existing.id),
                vector=vector,
                metadata={
                    "name": existing.name,
                    "summary": existing.summary,
                    "content": existing.content,
                    "difficulty": existing.difficulty,
                    "keywords": existing.keywords,
                },
            )

    # 逐个候选知识点执行去重判断
    for i, candidate in enumerate(candidates):
        logger.info(f"处理候选 {i+1}/{len(candidates)}: {candidate.name}")
        try:
            result = run_dedup_for_candidate(candidate, existing_knowledge_list)
            results.append(result)

            if result.method == "llm":
                llm_call_count += 1

        except Exception as e:
            error_msg = f"候选 '{candidate.name}' 处理失败: {str(e)}"
            errors.append(error_msg)
            logger.error(error_msg)

    total_duration = time.time() - total_start

    # 统计各决策数量
    new_count = sum(1 for r in results if r.decision.decision == "NEW")
    duplicate_count = sum(1 for r in results if r.decision.decision == "DUPLICATE")
    merge_count = sum(1 for r in results if r.decision.decision == "MERGE")

    logger.info(
        f"去重 Pipeline 完成: 总计 {len(candidates)} 个候选, "
        f"新增 {new_count}, 重复 {duplicate_count}, 合并 {merge_count}, "
        f"LLM 调用 {llm_call_count} 次, "
        f"耗时 {total_duration:.2f}s"
    )

    return DeduplicatePipelineResult(
        total_candidates=len(candidates),
        new_count=new_count,
        duplicate_count=duplicate_count,
        merge_count=merge_count,
        llm_call_count=llm_call_count,
        embedding_count=embedding_count,
        results=results,
        errors=errors,
    )


import time  # 放在文件顶部会导致循环导入问题
