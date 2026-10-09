"""知识点标准化模块。

本模块负责对知识点文本进行标准化处理，减少无意义的文本差异，
提高精确匹配和文本相似度计算的准确性。

标准化规则：
    1. 去除多余空格（连续空格合并为一个）
    2. 统一中英文标点（全角→半角）
    3. 统一大小写（英文转小写）
    4. 去掉首尾空白字符
    5. 清理重复关键词

注意：
    - 标准化的目的是减少无意义差异，不是改变语义
    - 不要把 "Java线程池" 改成 "线程池"
    - 不要删除具有语义意义的信息

使用方式：
    normalizer = KnowledgeNormalizer()
    normalized = normalizer.normalize(candidate)
    print(normalized.name)  # 标准化后的名称
"""

import logging
import re
from typing import List

logger = logging.getLogger(__name__)


class KnowledgeNormalizer:
    """知识点标准化器。

    使用方法：
        normalizer = KnowledgeNormalizer()
        name = normalizer.normalize_name("Java  线程池")  # "java线程池"
        keywords = normalizer.normalize_keywords(["Java", "java", "线程池", "线程池"])
        # ["java", "线程池"]
    """

    # 全角→半角标点映射字典
    PUNCTUATION_MAP = {
        "，": ",",
        "。": ".",
        "！": "!",
        "？": "?",
        "；": ";",
        "：": ":",
        "（": "(",
        "）": ")",
        "【": "[",
        "】": "]",
        "、": ",",
    }

    def normalize_name(self, name: str) -> str:
        """标准化知识点名称。

        处理步骤：
            1. 去除首尾空白
            2. 合并连续空格为一个
            3. 统一中英文标点
            4. 英文转小写

        Args:
            name: 原始知识点名称

        Returns:
            标准化后的名称
        """
        if not name:
            return ""

        # 去除首尾空白
        result = name.strip()

        # 合并连续空格为一个
        result = re.sub(r"\s+", " ", result)

        # 统一标点（全角→半角）
        for zh, en in self.PUNCTUATION_MAP.items():
            result = result.replace(zh, en)

        # 英文转小写
        result = result.lower()

        return result

    def normalize_summary(self, summary: str) -> str:
        """标准化知识点概述。

        Args:
            summary: 原始概述

        Returns:
            标准化后的概述
        """
        if not summary:
            return ""

        result = summary.strip()
        result = re.sub(r"\s+", " ", result)
        for zh, en in self.PUNCTUATION_MAP.items():
            result = result.replace(zh, en)
        result = result.lower()

        return result

    def normalize_keywords(self, keywords: List[str]) -> List[str]:
        """标准化关键词列表。

        处理步骤：
            1. 每个关键词标准化（去空格、转小写）
            2. 去除空字符串
            3. 去除重复项（保持顺序）

        Args:
            keywords: 原始关键词列表

        Returns:
            去重、标准化后的关键词列表
        """
        if not keywords:
            return []

        seen = set()
        result = []

        for kw in keywords:
            # 标准化单个关键词
            normalized = kw.strip().lower()
            normalized = re.sub(r"\s+", "", normalized)  # 关键词内去除所有空格

            if normalized and normalized not in seen:
                seen.add(normalized)
                result.append(normalized)

        return result

    def build_embedding_text(
        self,
        name: str,
        summary: str,
        keywords: List[str],
    ) -> str:
        """构建用于 Embedding 的文本。

        推荐组合：name + summary + keywords
        比单独使用 content 更稳定、更省计算。

        Args:
            name: 知识点名称
            summary: 知识点概述
            keywords: 关键词列表

        Returns:
            拼接后的文本，用于传给 Embedding 模型
        """
        parts = []

        if name:
            parts.append(name.strip())
        if summary:
            parts.append(summary.strip())
        if keywords:
            parts.append(", ".join(k.strip() for k in keywords if k.strip()))

        return " | ".join(parts)
