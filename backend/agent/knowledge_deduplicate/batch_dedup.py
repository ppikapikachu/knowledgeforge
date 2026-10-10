"""候选知识点批次内部去重模块。

在正式落库之前，先对本次导入产生的候选知识点进行内部去重。

去重策略：
    1. 标准化名称精确匹配 → 必定重复，保留内容更完整的
    2. 同名不同内容 → 检测冲突，保留先出现的版本并记录冲突
    3. 内容互补 → 合并（保留所有有来源支持的细节）

原则：
    - 全程内存操作，不写 MySQL
    - 不静默丢弃有效内容
    - 冲突产生可审计的记录
"""

import logging
from typing import List, Optional, Tuple

from agent.knowledge_deduplicate.normalizer import KnowledgeNormalizer
from agent.knowledge_extract.schemas import KnowledgeCandidate

logger = logging.getLogger(__name__)


class CandidateDedupResult:
    """批次内部去重结果。"""

    def __init__(
        self,
        unique_candidates: List[KnowledgeCandidate],
        duplicates: List[Tuple[KnowledgeCandidate, int]],
        conflicts: Optional[List[dict]] = None,
    ):
        self.unique_candidates = unique_candidates
        self.duplicates = duplicates
        self.conflicts = conflicts or []


def dedup_candidates_batch(
    candidates: List[KnowledgeCandidate],
) -> CandidateDedupResult:
    """对候选知识点列表进行批次内部去重。

    流程：
        1. 标准化名称（大小写、空格、标点统一）
        2. 精确匹配去重（标准化名称相同 → 保留内容更完整的）
        3. 同名冲突检测（名称相同但内容差异大 → 标记冲突）

    Args:
        candidates: 候选知识点列表

    Returns:
        CandidateDedupResult
    """
    normalizer = KnowledgeNormalizer()

    if not candidates:
        return CandidateDedupResult([], [])

    # 标准化名称
    normalized_names = [
        normalizer.normalize_name(c.name) for c in candidates
    ]

    unique_indices = []
    duplicates = []
    conflicts = []
    seen_names = {}  # 标准化名称 → (unique_index, candidate)

    for i, (candidate, norm_name) in enumerate(zip(candidates, normalized_names)):
        if norm_name in seen_names:
            prev_idx, prev_candidate = seen_names[norm_name]

            # 内容比较
            content_relation = _compare_content(candidate, prev_candidate)

            if content_relation == "same":
                # 内容基本相同 → 重复，保留更完整的
                duplicates.append((candidate, prev_idx))
                if _content_length(candidate) > _content_length(prev_candidate):
                    unique_indices[prev_idx] = i
                    seen_names[norm_name] = (prev_idx, candidate)
                logger.info(f"批次去重(重复): '{candidate.name}' 保留更完整版本")

            elif content_relation == "complementary":
                # 内容互补 → 合并
                merged = _merge_candidates(prev_candidate, candidate)
                unique_indices[prev_idx] = i
                seen_names[norm_name] = (prev_idx, merged)
                duplicates.append((candidate, prev_idx))
                logger.info(f"批次去重(合并): '{candidate.name}' 内容互补已合并")

            else:
                # 内容冲突 → 标记冲突，保留先出现的
                conflicts.append({
                    "name": candidate.name,
                    "kept_index": prev_idx,
                    "dropped_index": i,
                    "reason": "同名但内容冲突",
                })
                duplicates.append((candidate, prev_idx))
                logger.warning(f"批次去重(冲突): '{candidate.name}' 同名但内容冲突")

        else:
            seen_names[norm_name] = (len(unique_indices), candidate)
            unique_indices.append(i)

    unique_candidates = [candidates[i] for i in unique_indices]

    logger.info(
        f"批次去重完成: 输入 {len(candidates)}, "
        f"去重后 {len(unique_candidates)}, "
        f"重复 {len(duplicates)}, 冲突 {len(conflicts)}"
    )

    return CandidateDedupResult(unique_candidates, duplicates, conflicts)


def _compare_content(a: KnowledgeCandidate, b: KnowledgeCandidate) -> str:
    """比较两个同名候选的内容关系。

    Returns:
        "same" - 内容基本相同
        "complementary" - 内容互补（可合并）
        "conflict" - 内容冲突
    """
    content_a = (a.content or "").strip()
    content_b = (b.content or "").strip()

    if not content_a or not content_b:
        return "same"  # 一方无内容，视为重复

    len_a, len_b = len(content_a), len(content_b)
    max_len = max(len_a, len_b)
    if max_len == 0:
        return "same"

    # 长度差异
    diff_ratio = abs(len_a - len_b) / max_len

    if diff_ratio < 0.2:
        # 长度接近 → 内容基本相同
        return "same"
    elif diff_ratio < 0.6:
        # 长度差异中等 → 可能互补
        return "complementary"
    else:
        # 长度差异很大 → 冲突
        return "conflict"


def _content_length(candidate: KnowledgeCandidate) -> int:
    """获取候选内容长度。"""
    return len((candidate.content or "").strip())


def _merge_candidates(
    a: KnowledgeCandidate, b: KnowledgeCandidate
) -> KnowledgeCandidate:
    """合并两个内容互补的候选。

    保留更长的 content，合并 keywords。
    """
    # 保留更长的 content
    if _content_length(b) > _content_length(a):
        main, extra = b, a
    else:
        main, extra = a, b

    # 合并关键词（去重）
    merged_keywords = list(dict.fromkeys(
        (main.keywords or []) + (extra.keywords or [])
    ))

    return KnowledgeCandidate(
        name=main.name,
        summary=main.summary,
        content=main.content,
        difficulty=main.difficulty,
        keywords=merged_keywords[:15],  # 限制数量
        source_chunk_id=main.source_chunk_id,
        source_title=main.source_title,
        source_page_start=main.source_page_start,
        source_page_end=main.source_page_end,
    )
