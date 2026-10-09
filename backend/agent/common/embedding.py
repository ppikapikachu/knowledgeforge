"""Embedding 服务模块。

本模块提供统一的文本向量嵌入接口，使用本地部署的 FlagModel 模型。
用于将知识点文本转换为向量，供后续向量检索和相似度计算使用。

当前使用的模型：BAAI/bge-small-zh-v1.5（中文小模型，512维）
    - 本地加载，无需网络请求
    - 支持批量 Embedding
    - 使用 FP16 半精度加速

使用方式：
    from agent.common.embedding import get_embedding_service
    service = get_embedding_service()
    vectors = service.embed_texts(["Java线程池", "Activity生命周期"])
"""

import logging
import os
from typing import List, Optional

from agent.common.config import agent_settings

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Embedding 服务，封装本地 FlagModel 模型。

    使用方式：
        service = EmbeddingService()
        vector = service.embed_text("Java线程池")
        vectors = service.embed_texts(["Java线程池", "Activity生命周期"])
    """

    def __init__(self):
        """初始化 Embedding 服务。

        从 agent_settings 读取模型路径，本地加载 FlagModel。
        """
        from FlagEmbedding import FlagModel

        self.model_path = agent_settings.EMBEDDING_MODEL
        self.use_fp16 = agent_settings.EMBEDDING_USE_FP16

        logger.info(f"正在加载 Embedding 模型: {self.model_path} (fp16={self.use_fp16})")

        # 本地加载模型
        self.model = FlagModel(
            self.model_path,
            use_fp16=self.use_fp16,
        )

        # 获取向量维度（通过编码一条测试文本）
        test_vec = self.model.encode(["test"])
        self.dimension = len(test_vec[0])

        logger.info(f"Embedding 模型加载完成: dimension={self.dimension}")

    def embed_text(self, text: str) -> List[float]:
        """将单条文本转换为向量。

        Args:
            text: 待嵌入的文本

        Returns:
            浮点数列表，表示文本的向量
        """
        embeddings = self.model.encode([text])
        return embeddings[0].tolist()

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """批量将多条文本转换为向量。

        一次调用处理多条文本，比逐条调用更高效。

        Args:
            texts: 待嵌入的文本列表

        Returns:
            向量列表，与输入文本一一对应
        """
        if not texts:
            return []

        embeddings = self.model.encode(texts)
        return [vec.tolist() for vec in embeddings]


# 全局单例
_embedding_service: Optional[EmbeddingService] = None


def get_embedding_service() -> EmbeddingService:
    """获取 Embedding 服务单例。"""
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service


def reset_embedding_service() -> None:
    """重置 Embedding 服务单例（用于测试）。"""
    global _embedding_service
    _embedding_service = None
