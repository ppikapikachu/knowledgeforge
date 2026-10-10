"""KnowledgeRelationAgent 的 LangGraph 节点定义。

工作流节点：
    1. prepare_candidates —— 准备候选列表（人工/自动检索）
    2. llm_judge —— LLM 批量关系判断
    3. validate_results —— 确定性校验
    4. finalize —— 汇总结果
"""

import logging
import time
from typing import Any, Dict, List, Optional

from agent.knowledge_relation.prompts import (
    CANDIDATE_TEMPLATE,
    SYSTEM_PROMPT,
    USER_PROMPT_TEMPLATE,
)
from agent.knowledge_relation.schemas import (
    KnowledgeRelationJudgement,
    RelationExtractOutput,
    RelationKnowledgeInput,
)
from agent.knowledge_relation.validator import RelationValidator

logger = logging.getLogger(__name__)


def prepare_candidates_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """节点：准备候选知识点列表。

    如果请求提供了人工候选，直接使用。
    否则从向量库自动检索。
    """
    source = state["source"]
    provided_candidates = state.get("provided_candidates")
    candidate_ids = state.get("candidate_knowledge_ids")
    top_k = state.get("top_k", 10)

    # 模式 1：人工提供候选（包括空列表）
    if provided_candidates is not None:
        logger.info(f"使用人工候选: {len(provided_candidates)} 个")
        return {
            "candidates": provided_candidates,
            "retrieval_mode": "provided_candidates",
        }

    # 模式 2：从数据库读取指定 ID 的候选
    if candidate_ids:
        logger.info(f"从数据库读取候选: {len(candidate_ids)} 个")
        # 这里需要在 API 层准备好数据，Agent 不直接访问数据库
        return {
            "candidates": state.get("resolved_candidates", []),
            "retrieval_mode": "provided_ids",
        }

    # 模式 3：向量自动检索
    logger.info(f"向量自动检索: top_k={top_k}")
    try:
        candidates = _auto_search_candidates(source, top_k)
        return {
            "candidates": candidates,
            "retrieval_mode": "auto_search",
        }
    except Exception as e:
        logger.error(f"向量检索失败: {e}")
        return {
            "candidates": [],
            "retrieval_mode": "auto_search",
            "retrieval_error": str(e),
        }


def llm_judge_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """节点：LLM 批量关系判断。

    将锚点和所有候选放入一次 LLM 请求中批量判断。
    """
    from langchain_core.messages import HumanMessage, SystemMessage
    from agent.common.llm import get_llm

    source = state["source"]
    candidates = state.get("candidates", [])

    if not candidates:
        logger.info("无候选，跳过 LLM 判断")
        return {"judgements": [], "llm_call_count": 0}

    # 构造 Prompt
    candidates_text = "\n\n".join([
        CANDIDATE_TEMPLATE.format(
            index=i + 1,
            id=c.id,
            name=c.name,
            summary=c.summary or "无",
            keywords=", ".join(c.keywords) if c.keywords else "无",
        )
        for i, c in enumerate(candidates)
    ])

    user_prompt = USER_PROMPT_TEMPLATE.format(
        source_id=source.id,
        source_name=source.name,
        source_summary=source.summary or "无",
        source_keywords=", ".join(source.keywords) if source.keywords else "无",
        candidates_text=candidates_text,
    )

    # 调用 LLM
    llm = get_llm(thinking="disabled")
    structured_llm = llm.with_structured_output(RelationExtractOutput)

    start_time = time.time()
    try:
        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=user_prompt),
        ]
        result = structured_llm.invoke(messages)
        duration = time.time() - start_time

        logger.info(
            f"LLM 判断完成: {len(result.judgements)} 条结果, "
            f"耗时 {duration:.2f}s"
        )

        return {
            "judgements": result.judgements,
            "llm_call_count": 1,
        }

    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"LLM 判断失败: {e}, 耗时 {duration:.2f}s")
        return {
            "judgements": [],
            "llm_call_count": 1,
            "llm_error": str(e),
        }


def validate_results_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """节点：确定性校验 LLM 输出。"""
    judgements = state.get("judgements", [])
    source = state["source"]
    candidates = state.get("candidates", [])

    valid_candidate_ids = {c.id for c in candidates}
    validator = RelationValidator()

    valid, errors = validator.validate_and_fix(
        judgements, source.id, valid_candidate_ids
    )

    logger.info(
        f"校验完成: 有效 {len(valid)}, "
        f"错误 {len(errors)}"
    )

    return {
        "validated_judgements": valid,
        "validation_errors": errors,
    }


def finalize_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """节点：汇总最终结果。"""
    validated = state.get("validated_judgements", [])
    errors = state.get("validation_errors", [])
    retrieval_mode = state.get("retrieval_mode", "unknown")
    llm_call_count = state.get("llm_call_count", 0)
    candidates = state.get("candidates", [])
    retrieval_error = state.get("retrieval_error")

    relation_count = sum(1 for j in validated if j.decision == "RELATION")
    no_relation_count = sum(1 for j in validated if j.decision == "NO_RELATION")

    return {
        "final_result": {
            "retrieval_mode": retrieval_mode,
            "candidate_count": len(candidates),
            "relation_count": relation_count,
            "no_relation_count": no_relation_count,
            "llm_call_count": llm_call_count,
            "evaluations": validated,
            "errors": errors + ([retrieval_error] if retrieval_error else []),
        }
    }


def _auto_search_candidates(
    source: RelationKnowledgeInput,
    top_k: int,
) -> List[RelationKnowledgeInput]:
    """从向量库自动检索候选知识点。

    复用现有 Embedding + Vector Search。
    """
    from agent.common.embedding import get_embedding_service
    from agent.common.vector_store import get_vector_store
    from agent.knowledge_deduplicate.normalizer import KnowledgeNormalizer

    normalizer = KnowledgeNormalizer()
    text = normalizer.build_embedding_text(
        source.name, source.summary, source.keywords
    )

    service = get_embedding_service()
    vec = service.embed_text(text)

    store = get_vector_store()
    results = store.search(vec, top_k=top_k + 5)  # 多取一些以便排除自身

    candidates = []
    for r in results:
        meta = r.metadata
        kid = meta.get("knowledge_id", 0)

        # 排除自身
        if kid == source.id:
            continue

        candidates.append(RelationKnowledgeInput(
            id=kid,
            name=meta.get("name", ""),
            summary=meta.get("summary", ""),
            content=meta.get("content", "")[:500],
            keywords=meta.get("keywords", []),
        ))

        if len(candidates) >= top_k:
            break

    return candidates
