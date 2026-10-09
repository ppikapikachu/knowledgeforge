"""LangGraph 工作流节点定义模块。

本模块定义了 KnowledgeDeduplicatePipeline 工作流中的所有节点函数。

节点列表：
    1. normalize_node —— 标准化候选知识点
    2. exact_match_node —— 精确匹配检查
    3. embedding_node —— 向量嵌入
    4. vector_search_node —— 向量检索
    5. rule_decision_node —— 规则判定（不使用 LLM）
    6. llm_decision_node —— LLM 判定（仅 AMBIGUOUS 时调用）
    7. finalize_node —— 整理最终结果

判定流程：
    标准化 → 精确匹配 → 向量嵌入 → 向量检索 → 规则判定
    → NEW/DUPLICATE（直接返回）
    → AMBIGUOUS → LLM 判定 → NEW/DUPLICATE/MERGE
"""

import logging
import time
from typing import Any, Dict, List

from agent.common.config import agent_settings
from agent.knowledge_deduplicate.normalizer import KnowledgeNormalizer
from agent.knowledge_deduplicate.schemas import (
    DeduplicateDecision,
    ExistingKnowledge,
    MergedKnowledge,
)

logger = logging.getLogger(__name__)


def normalize_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """节点：标准化候选知识点。

    对候选知识点的名称、概述、关键词进行标准化处理，
    减少无意义的文本差异（如空格、大小写、标点）。

    输入 state:
        candidate: KnowledgeCandidate

    输出 state 更新:
        normalized_name: 标准化后的名称
        normalized_summary: 标准化后的概述
        normalized_keywords: 标准化后的关键词列表
        embedding_text: 用于 Embedding 的拼接文本
    """
    candidate = state["candidate"]
    normalizer = KnowledgeNormalizer()

    normalized_name = normalizer.normalize_name(candidate.name)
    normalized_summary = normalizer.normalize_summary(candidate.summary)
    normalized_keywords = normalizer.normalize_keywords(candidate.keywords)
    embedding_text = normalizer.build_embedding_text(
        candidate.name, candidate.summary, candidate.keywords
    )

    logger.info(f"标准化完成: '{candidate.name}' → '{normalized_name}'")

    return {
        "normalized_name": normalized_name,
        "normalized_summary": normalized_summary,
        "normalized_keywords": normalized_keywords,
        "embedding_text": embedding_text,
    }


def exact_match_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """节点：精确匹配检查。

    检查标准化后的名称是否与已有知识点完全相同。
    如果完全相同，直接判定为 DUPLICATE，无需后续步骤。

    输入 state:
        normalized_name: 标准化后的候选名称
        existing_knowledge_list: 已有知识点列表

    输出 state 更新:
        exact_match_id: 精确匹配的知识点 ID（无匹配时为 None）
        exact_match_result: 精确匹配结果（None / DeduplicateDecision）
    """
    normalized_name = state["normalized_name"]
    existing_list = state.get("existing_knowledge_list", [])

    normalizer = KnowledgeNormalizer()

    for existing in existing_list:
        existing_normalized = normalizer.normalize_name(existing.name)
        if normalized_name == existing_normalized:
            logger.info(f"精确匹配成功: '{normalized_name}' → ID={existing.id}")
            return {
                "exact_match_id": existing.id,
                "exact_match_result": DeduplicateDecision(
                    decision="DUPLICATE",
                    target_knowledge_id=existing.id,
                    confidence=1.0,
                    reason=f"名称精确匹配: '{state['candidate'].name}' 与已有知识点 '{existing.name}' 完全相同",
                ),
            }

    logger.info(f"精确匹配失败: '{normalized_name}'，继续向量检索")
    return {"exact_match_id": None, "exact_match_result": None}


def embedding_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """节点：将候选知识点文本转换为向量。

    使用 EmbeddingService 将候选知识点的 name+summary+keywords
    转换为向量表示，供后续向量检索使用。

    输入 state:
        embedding_text: 用于 Embedding 的拼接文本

    输出 state 更新:
        candidate_vector: 候选知识点的向量
        embedding_time: Embedding 耗时
    """
    from agent.common.embedding import get_embedding_service

    embedding_text = state["embedding_text"]

    start_time = time.time()
    service = get_embedding_service()
    vector = service.embed_text(embedding_text)
    duration = time.time() - start_time

    logger.info(f"Embedding 完成: {len(vector)} 维, 耗时 {duration:.2f}s")

    return {
        "candidate_vector": vector,
        "embedding_time": duration,
    }


def vector_search_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """节点：向量检索相似知识点。

    使用 VectorRepository 检索与候选知识点最相似的 Top K 已有知识点。

    输入 state:
        candidate_vector: 候选知识点的向量

    输出 state 更新:
        similar_knowledge: 相似知识点列表（含相似度分数）
        search_time: 检索耗时
    """
    from agent.common.vector_store import get_vector_store

    candidate_vector = state["candidate_vector"]
    existing_list = state.get("existing_knowledge_list", [])
    top_k = agent_settings.DEDUP_TOP_K

    start_time = time.time()
    store = get_vector_store()
    search_results = store.search(candidate_vector, top_k=top_k)
    duration = time.time() - start_time

    # 将检索结果转换为 ExistingKnowledge 列表
    similar_knowledge = []
    for result in search_results:
        # 从已有知识点列表中找到对应的知识点
        existing = None
        for ex in existing_list:
            if str(ex.id) == result.id:
                existing = ex
                break

        if existing:
            similar_knowledge.append(ExistingKnowledge(
                id=existing.id,
                name=existing.name,
                summary=existing.summary,
                content=existing.content,
                difficulty=existing.difficulty,
                keywords=existing.keywords,
                similarity=result.score,
            ))
        else:
            # 向量存储中有元数据时直接使用
            similar_knowledge.append(ExistingKnowledge(
                id=int(result.id) if result.id.isdigit() else 0,
                name=result.metadata.get("name", ""),
                summary=result.metadata.get("summary", ""),
                content=result.metadata.get("content", ""),
                difficulty=result.metadata.get("difficulty", 2),
                keywords=result.metadata.get("keywords", []),
                similarity=result.score,
            ))

    logger.info(
        f"向量检索完成: 返回 {len(similar_knowledge)} 个相似知识点, "
        f"耗时 {duration:.2f}s"
    )

    return {
        "similar_knowledge": similar_knowledge,
        "search_time": duration,
    }


def rule_decision_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """节点：规则判定（不使用 LLM）。

    根据精确匹配结果和相似度分数，使用规则判定：
        - 精确匹配 → DUPLICATE
        - 相似度 < LOW_THRESHOLD → NEW
        - 相似度 >= HIGH_THRESHOLD → DUPLICATE
        - 中间区域 → AMBIGUOUS（需要 LLM 判断）

    输入 state:
        exact_match_result: 精确匹配结果
        similar_knowledge: 相似知识点列表

    输出 state 更新:
        rule_decision: 规则判定结果（NEW/DUPLICATE/AMBIGUOUS）
        rule_decision_result: DeduplicateDecision（仅 NEW/DUPLICATE 时有值）
    """
    exact_match_result = state.get("exact_match_result")
    similar_knowledge = state.get("similar_knowledge", [])

    low_threshold = agent_settings.DEDUP_LOW_THRESHOLD
    high_threshold = agent_settings.DEDUP_HIGH_THRESHOLD

    # 如果精确匹配成功，直接返回 DUPLICATE
    if exact_match_result:
        return {
            "rule_decision": "DUPLICATE",
            "rule_decision_result": exact_match_result,
        }

    # 没有相似知识点，判定为 NEW
    if not similar_knowledge:
        logger.info("规则判定: 无相似知识点 → NEW")
        return {
            "rule_decision": "NEW",
            "rule_decision_result": DeduplicateDecision(
                decision="NEW",
                target_knowledge_id=None,
                confidence=0.9,
                reason="向量检索未找到相似知识点",
            ),
        }

    # 取最高相似度
    top_similarity = similar_knowledge[0].similarity
    top_existing = similar_knowledge[0]

    if top_similarity < low_threshold:
        # 低相似度 → NEW
        logger.info(f"规则判定: 相似度 {top_similarity:.2f} < {low_threshold} → NEW")
        return {
            "rule_decision": "NEW",
            "rule_decision_result": DeduplicateDecision(
                decision="NEW",
                target_knowledge_id=None,
                confidence=0.8,
                reason=f"最高相似度 {top_similarity:.2f} 低于阈值 {low_threshold}",
            ),
        }

    if top_similarity >= high_threshold:
        # 高相似度 → DUPLICATE
        logger.info(f"规则判定: 相似度 {top_similarity:.2f} >= {high_threshold} → DUPLICATE")
        return {
            "rule_decision": "DUPLICATE",
            "rule_decision_result": DeduplicateDecision(
                decision="DUPLICATE",
                target_knowledge_id=top_existing.id,
                confidence=0.85,
                reason=f"最高相似度 {top_similarity:.2f} >= 阈值 {high_threshold}，与 '{top_existing.name}' 高度相似",
            ),
        }

    # 中间区域 → AMBIGUOUS（需要 LLM 判断）
    logger.info(
        f"规则判定: 相似度 {top_similarity:.2f} 在 [{low_threshold}, {high_threshold}) "
        f"之间 → AMBIGUOUS，需要 LLM 判断"
    )
    return {
        "rule_decision": "AMBIGUOUS",
        "rule_decision_result": None,
    }


def should_use_llm(state: Dict[str, Any]) -> str:
    """条件边：判断是否需要调用 LLM。

    如果规则层已经判定为 NEW 或 DUPLICATE，直接进入 finalize。
    如果判定为 AMBIGUOUS，进入 LLM 判断。
    """
    rule_decision = state.get("rule_decision", "AMBIGUOUS")

    if rule_decision in ("NEW", "DUPLICATE"):
        return "finalize"
    else:
        return "llm_decision"


def llm_decision_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """节点：调用 LLM 判断去重决策（仅 AMBIGUOUS 时调用）。

    将候选知识点和相似知识点列表发送给 LLM，
    由 LLM 判断属于 NEW、DUPLICATE 还是 MERGE。

    输入 state:
        candidate: 候选知识点
        similar_knowledge: 相似知识点列表

    输出 state 更新:
        llm_decision: LLM 判定结果（DeduplicateDecision）
        llm_time: LLM 调用耗时
    """
    from langchain_core.messages import HumanMessage, SystemMessage
    from agent.common.llm import get_llm
    from agent.knowledge_deduplicate.prompts import (
        DEDUP_SYSTEM_PROMPT,
        DEDUP_USER_PROMPT_TEMPLATE,
        EXISTING_KNOWLEDGE_TEMPLATE,
    )

    candidate = state["candidate"]
    similar_knowledge = state.get("similar_knowledge", [])

    # 构造已有知识点文本
    existing_text_parts = []
    for i, ex in enumerate(similar_knowledge, 1):
        existing_text_parts.append(EXISTING_KNOWLEDGE_TEMPLATE.format(
            index=i,
            similarity=ex.similarity,
            id=ex.id,
            name=ex.name,
            summary=ex.summary,
            content=ex.content[:500] + "..." if len(ex.content) > 500 else ex.content,
            difficulty=ex.difficulty,
            keywords=", ".join(ex.keywords),
        ))
    existing_text = "\n\n".join(existing_text_parts)

    # 构造用户提示词
    user_prompt = DEDUP_USER_PROMPT_TEMPLATE.format(
        candidate_name=candidate.name,
        candidate_summary=candidate.summary,
        candidate_content=candidate.content[:500] + "..." if len(candidate.content) > 500 else candidate.content,
        candidate_difficulty=candidate.difficulty,
        candidate_keywords=", ".join(candidate.keywords),
        existing_knowledge_text=existing_text,
    )

    # 调用 LLM
    llm = get_llm()
    structured_llm = llm.with_structured_output(DeduplicateDecision)

    start_time = time.time()
    try:
        messages = [
            SystemMessage(content=DEDUP_SYSTEM_PROMPT),
            HumanMessage(content=user_prompt),
        ]
        result = structured_llm.invoke(messages)
        duration = time.time() - start_time

        logger.info(
            f"LLM 去重判定完成: decision={result.decision}, "
            f"target={result.target_knowledge_id}, "
            f"耗时 {duration:.2f}s"
        )

        return {
            "llm_decision": result,
            "llm_time": duration,
        }

    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"LLM 去重判定失败: {e}，耗时 {duration:.2f}s")

        # 失败时默认为 NEW（保守策略）
        return {
            "llm_decision": DeduplicateDecision(
                decision="NEW",
                target_knowledge_id=None,
                confidence=0.3,
                reason=f"LLM 判定失败，默认 NEW: {str(e)}",
            ),
            "llm_time": duration,
        }


def finalize_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """节点：整理最终结果。

    汇总所有判定结果，生成最终的 DeduplicateDecision。

    输入 state:
        rule_decision: 规则判定结果
        rule_decision_result: 规则层的 DeduplicateDecision
        llm_decision: LLM 判定结果（可能为 None）
        exact_match: 是否精确匹配
        similar_knowledge: 相似知识点列表

    输出 state 更新:
        final_decision: 最终去重决策
        decision_method: 判定方法（exact_match/rule/llm）
    """
    rule_decision = state.get("rule_decision", "AMBIGUOUS")
    rule_decision_result = state.get("rule_decision_result")
    llm_decision = state.get("llm_decision")
    exact_match_result = state.get("exact_match_result")
    similar_knowledge = state.get("similar_knowledge", [])

    # 精确匹配
    if exact_match_result:
        return {
            "final_decision": exact_match_result,
            "decision_method": "exact_match",
        }

    # LLM 判定（AMBIGUOUS 时）
    if rule_decision == "AMBIGUOUS" and llm_decision:
        return {
            "final_decision": llm_decision,
            "decision_method": "llm",
        }

    # 规则判定（NEW/DUPLICATE）
    if rule_decision_result:
        return {
            "final_decision": rule_decision_result,
            "decision_method": "rule",
        }

    # 兜底：默认 NEW
    return {
        "final_decision": DeduplicateDecision(
            decision="NEW",
            target_knowledge_id=None,
            confidence=0.3,
            reason="无法确定，默认 NEW",
        ),
        "decision_method": "fallback",
    }
