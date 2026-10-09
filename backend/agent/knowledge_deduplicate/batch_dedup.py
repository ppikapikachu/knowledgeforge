"""候选知识点批次内部去重模块。

在正式落库之前，先对本次导入产生的候选知识点进行内部去重。
避免同一个批次内产生重复知识点。

流程：
    Candidates → 标准化 → 精确去重 → 向量相似去重 → Unique Candidates

原则：
    - 全程内存操作，不写 MySQL
    - 保留 canonical candidate（第一个合理候选）
    - 其余标记为重复，指向 canonical
"""

import logging
from typing import Dict, List, Optional, Tuple

from agent.common.embedding import get_embedding_service
from agent.common.vector_store import get_vector_store
from agent.knowledge_deduplicate.normalizer import KnowledgeNormalizer
from agent.knowledge_extract.schemas import KnowledgeCandidate

logger = logging.getLogger(__name__)


class CandidateDedupResult:
    """批次内部去重结果。"""

    def __init__(
        self,
        unique_candidates: List[KnowledgeCandidate],
        duplicates: List[Tuple[KnowledgeCandidate, int]],
    ):
        """
        Args:
            unique_candidates: 去重后的唯一候选列表
            duplicates: 重复候选列表，每个元素是 (候选, 指向的 unique_index)
        """
        self.unique_candidates = unique_candidates
        self.duplicates = duplicates


def dedup_candidates_batch(
    candidates: List[KnowledgeCandidate],
    similarity_threshold: float = 0.90,
) -> CandidateDedupResult:
    """对候选知识点列表进行批次内部去重。

    流程：
        1. 标准化名称
        2. 精确匹配去重（标准化名称相同）
        3. 向量相似度去重（相似度 >= 阈值）

    Args:
        candidates: 候选知识点列表
        similarity_threshold: 向量相似度阈值，高于此值判定为重复

    Returns:
        CandidateDedupResult（唯一候选列表 + 重复列表）
    """
    normalizer = KnowledgeNormalizer()

    if not candidates:
        return CandidateDedupResult([], [])

    # 第一步：标准化名称
    normalized_names = [
        normalizer.normalize_name(c.name) for c in candidates
    ]

    # 第二步：精确匹配去重
    unique_indices = []  # 唯一候选的索引
    duplicates = []  # (候选, 指向的 unique_index)
    seen_names = {}  # 标准化名称 → unique_index

    for i, (candidate, norm_name) in enumerate(zip(candidates, normalized_names)):
        if norm_name in seen_names:
            # 标准化名称重复
            duplicates.append((candidate, seen_names[norm_name]))
            logger.info(f"批次去重(精确): '{candidate.name}' 与候选 {seen_names[norm_name]} 重复")
        else:
            seen_names[norm_name] = len(unique_indices)
            unique_indices.append(i)

    unique_candidates = [candidates[i] for i in unique_indices]

    # 第三步：向量相似度去重
    if len(unique_candidates) > 1:
        try:
            service = get_embedding_service()
            normalizer2 = KnowledgeNormalizer()
            texts = [
                normalizer2.build_embedding_text(c.name, c.summary, c.keywords)
                for c in unique_candidates
            ]
            vectors = service.embed_texts(texts)

            # 用临时向量库做内部检索
            store = get_vector_store()
            final_unique = []
            final_duplicates = []
            vector_ids = {}  # unique_index → vector_id

            for i, (candidate, vec) in enumerate(zip(unique_candidates, vectors)):
                # 检查与已有 unique 候选的相似度
                is_dup = False
                for j, prev_candidate in enumerate(final_unique):
                    vid = f"internal_{j}"
                    if vid in vector_ids:
                        results = store.search(vec, top_k=1)
                        if results and results[0].score >= similarity_threshold:
                            final_duplicates.append((candidate, j))
                            is_dup = True
                            logger.info(
                                f"批次去重(向量): '{candidate.name}' 与 '{prev_candidate.name}' "
                                f"相似度 {results[0].score:.4f}"
                            )
                            break

                if not is_dup:
                    vid = f"internal_{len(final_unique)}"
                    store.upsert(vid, vec, {"name": candidate.name})
                    vector_ids[vid] = True
                    final_unique.append(candidate)

            # 清理临时向量
            for vid in vector_ids:
                store.delete(vid)

            return CandidateDedupResult(final_unique, final_duplicates)

        except Exception as e:
            logger.warning(f"向量去重失败，跳过: {e}")

    return CandidateDedupResult(unique_candidates, duplicates)
