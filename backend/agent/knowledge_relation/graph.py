"""KnowledgeRelationAgent 的 LangGraph 工作流定义。

工作流：
    START → prepare_candidates → llm_judge → validate_results → finalize → END

本 Agent 只输出关系建议，不写入 knowledge_relation 表。
"""

import logging
from typing import Any, Dict, List, Optional, TypedDict

from langgraph.graph import END, START, StateGraph

from agent.knowledge_relation.nodes import (
    finalize_node,
    llm_judge_node,
    prepare_candidates_node,
    validate_results_node,
)
from agent.knowledge_relation.schemas import (
    KnowledgeRelationJudgement,
    RelationKnowledgeInput,
)

logger = logging.getLogger(__name__)


class RelationState(TypedDict):
    """KnowledgeRelationAgent 工作流状态。"""
    source: RelationKnowledgeInput
    provided_candidates: Optional[List[RelationKnowledgeInput]]
    candidate_knowledge_ids: Optional[List[int]]
    resolved_candidates: Optional[List[RelationKnowledgeInput]]
    top_k: int
    candidates: List[RelationKnowledgeInput]
    retrieval_mode: str
    retrieval_error: Optional[str]
    judgements: List[KnowledgeRelationJudgement]
    llm_call_count: int
    llm_error: Optional[str]
    validated_judgements: List[KnowledgeRelationJudgement]
    validation_errors: List[str]
    final_result: Optional[Dict[str, Any]]


def build_relation_graph() -> StateGraph:
    """构建关系判断工作流图。"""
    graph = StateGraph(RelationState)

    graph.add_node("prepare_candidates", prepare_candidates_node)
    graph.add_node("llm_judge", llm_judge_node)
    graph.add_node("validate_results", validate_results_node)
    graph.add_node("finalize", finalize_node)

    graph.add_edge(START, "prepare_candidates")
    graph.add_edge("prepare_candidates", "llm_judge")
    graph.add_edge("llm_judge", "validate_results")
    graph.add_edge("validate_results", "finalize")
    graph.add_edge("finalize", END)

    return graph


# 编译后的图实例缓存
_relation_app = None


def get_relation_graph_app():
    """获取编译后的工作流应用实例。"""
    global _relation_app
    if _relation_app is None:
        graph = build_relation_graph()
        _relation_app = graph.compile()
    return _relation_app


def run_relation_test(
    source: RelationKnowledgeInput,
    provided_candidates: Optional[List[RelationKnowledgeInput]] = None,
    candidate_knowledge_ids: Optional[List[int]] = None,
    resolved_candidates: Optional[List[RelationKnowledgeInput]] = None,
    top_k: int = 10,
) -> Dict[str, Any]:
    """执行关系判断测试。

    Args:
        source: 锚点知识点
        provided_candidates: 人工提供的候选列表
        candidate_knowledge_ids: 候选 ID 列表
        resolved_candidates: 已解析的候选列表（从数据库读取）
        top_k: 自动检索数量

    Returns:
        判断结果 dict
    """
    import time

    app = get_relation_graph_app()
    start_time = time.time()

    initial_state: RelationState = {
        "source": source,
        "provided_candidates": provided_candidates,
        "candidate_knowledge_ids": candidate_knowledge_ids,
        "resolved_candidates": resolved_candidates,
        "top_k": top_k,
        "candidates": [],
        "retrieval_mode": "unknown",
        "retrieval_error": None,
        "judgements": [],
        "llm_call_count": 0,
        "llm_error": None,
        "validated_judgements": [],
        "validation_errors": [],
        "final_result": None,
    }

    try:
        final_state = app.invoke(initial_state)
    except Exception as e:
        elapsed = int((time.time() - start_time) * 1000)
        logger.error(f"关系判断工作流失败: {e}")
        return {
            "source_knowledge_id": source.id,
            "retrieval_mode": "unknown",
            "candidate_count": 0,
            "relation_count": 0,
            "no_relation_count": 0,
            "llm_call_count": 0,
            "elapsed_ms": elapsed,
            "saved": False,
            "evaluations": [],
            "errors": [f"工作流执行失败: {str(e)}"],
        }

    elapsed = int((time.time() - start_time) * 1000)
    result = final_state.get("final_result", {})

    return {
        "source_knowledge_id": source.id,
        "retrieval_mode": result.get("retrieval_mode", "unknown"),
        "candidate_count": result.get("candidate_count", 0),
        "relation_count": result.get("relation_count", 0),
        "no_relation_count": result.get("no_relation_count", 0),
        "llm_call_count": result.get("llm_call_count", 0),
        "elapsed_ms": elapsed,
        "saved": False,
        "evaluations": [
            e.model_dump() for e in result.get("evaluations", [])
        ],
        "errors": result.get("errors", []),
    }
