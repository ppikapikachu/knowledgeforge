"""向量存储与检索模块。

本模块提供 VectorRepository 抽象接口和基于 FAISS 的内存实现。
用于存储知识点的向量表示，并支持相似度检索。

架构：
    DeduplicateService
        ↓
    VectorRepository（抽象接口）
        ↓
    FaissVectorStore（FAISS 内存实现）

为什么需要抽象接口：
    未来可能从 FAISS 切换到 pgvector、Qdrant 等，
    只需新增实现类，不需要修改 Agent 代码。

使用方式：
    store = FaissVectorStore(dimension=512)
    store.upsert("k_1001", vector, {"name": "Java线程池"})
    results = store.search(query_vector, top_k=3)
"""

import logging
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class VectorSearchResult:
    """向量检索结果。"""

    id: str                          # 向量记录 ID（通常对应 knowledge_id）
    score: float                     # 相似度分数（0~1，越大越相似）
    metadata: Dict[str, Any] = field(default_factory=dict)  # 附加元数据


class VectorRepository(Protocol):
    """向量存储抽象接口。

    所有向量存储实现都应遵守此接口。
    Agent 代码只依赖此接口，不直接使用具体实现。
    """

    def upsert(self, id: str, vector: List[float], metadata: Dict[str, Any] = None) -> None:
        """插入或更新一条向量记录。"""
        ...

    def search(self, query_vector: List[float], top_k: int = 3) -> List[VectorSearchResult]:
        """检索最相似的 top_k 条记录。"""
        ...

    def delete(self, id: str) -> None:
        """删除一条向量记录。"""
        ...

    def count(self) -> int:
        """返回当前存储的向量总数。"""
        ...


class FaissVectorStore:
    """基于 FAISS 的内存向量存储实现。

    特点：
        - 使用 FAISS 进行高效的向量相似度检索
        - 纯内存存储，重启后数据丢失（适合测试和开发）
        - 线程安全（使用锁保护共享状态）
        - 支持 cosine 相似度

    注意：
        - 这是开发/测试用的实现，生产环境应使用持久化存储
        - 向量维度在创建时确定，后续不可更改
    """

    def __init__(self, dimension: int = 512):
        # FAISS 是 Meta 开源的向量检索库，专门用来做高效相似度搜索，支持十亿级向量。
        """初始化 FAISS 向量存储。

        Args:
            dimension: 向量维度，必须与 Embedding 模型输出维度一致
        """
        self.dimension = dimension
        self._lock = threading.Lock()

        # FAISS 索引：使用 InnerProduct（余弦相似度需要先归一化）
        try:
            import faiss
            self._index = faiss.IndexFlatIP(dimension)
            self._use_faiss = True
            logger.info(f"FAISS 向量存储初始化: dimension={dimension}")
        except ImportError:
            # FAISS 不可用时使用 numpy 实现
            self._vectors: List[np.ndarray] = []
            self._use_faiss = False
            logger.info(f"NumPy 向量存储初始化（FAISS 不可用）: dimension={dimension}")

        # 元数据存储：id → (index, metadata)
        self._id_to_index: Dict[str, int] = {}
        self._index_to_id: Dict[int, str] = {}
        self._metadata: Dict[str, Dict[str, Any]] = {}
        self._next_index = 0

    def upsert(self, id: str, vector: List[float], metadata: Dict[str, Any] = None) -> None:
        """插入或更新一条向量记录。

        如果 ID 已存在，更新其向量和元数据。
        向量会自动归一化以支持 cosine 相似度计算。

        Args:
            id: 记录 ID（如 "k_1001"）
            vector: 向量（浮点数列表）
            metadata: 附加元数据（如 {"name": "Java线程池"}）
        """
        with self._lock:
            # 归一化向量（cosine 相似度需要）
            vec = np.array(vector, dtype=np.float32)
            norm = np.linalg.norm(vec)
            if norm > 0:
                vec = vec / norm

            if id in self._id_to_index:
                # 更新已有记录
                idx = self._id_to_index[id]
                if self._use_faiss:
                    # FAISS 不支持原地更新，需要重建
                    # 简单方案：标记旧记录，追加新记录
                    self._index.add(vec.reshape(1, -1))
                    self._id_to_index[id] = self._next_index
                    self._index_to_id[self._next_index] = id
                    self._next_index += 1
                else:
                    self._vectors[idx] = vec
            else:
                # 新增记录
                if self._use_faiss:
                    self._index.add(vec.reshape(1, -1))
                else:
                    self._vectors.append(vec)

                self._id_to_index[id] = self._next_index
                self._index_to_id[self._next_index] = id
                self._next_index += 1

            self._metadata[id] = metadata or {}

    def search(self, query_vector: List[float], top_k: int = 3) -> List[VectorSearchResult]:
        """检索最相似的 top_k 条记录。

        使用 cosine 相似度进行检索。

        Args:
            query_vector: 查询向量
            top_k: 返回的最大结果数

        Returns:
            按相似度降序排列的检索结果列表
        """
        with self._lock:
            total = len(self._id_to_index)
            if total == 0:
                return []

            # 归一化查询向量
            vec = np.array(query_vector, dtype=np.float32)
            norm = np.linalg.norm(vec)
            if norm > 0:
                vec = vec / norm

            # 实际返回数量不超过已有记录数
            k = min(top_k, total)

            if self._use_faiss:
                scores, indices = self._index.search(vec.reshape(1, -1), k)
                results = []
                for score, idx in zip(scores[0], indices[0]):
                    if idx < 0 or idx not in self._index_to_id:
                        continue
                    rid = self._index_to_id[idx]
                    results.append(VectorSearchResult(
                        id=rid,
                        score=float(score),
                        metadata=self._metadata.get(rid, {}),
                    ))
                return results
            else:
                # NumPy 实现
                all_vecs = np.stack(self._vectors)
                scores = all_vecs @ vec
                top_indices = np.argsort(scores)[::-1][:k]

                results = []
                for idx in top_indices:
                    rid = self._index_to_id.get(int(idx))
                    if rid:
                        results.append(VectorSearchResult(
                            id=rid,
                            score=float(scores[idx]),
                            metadata=self._metadata.get(rid, {}),
                        ))
                return results

    def delete(self, id: str) -> None:
        """删除一条向量记录。

        注意：FAISS 不支持真正的删除，这里只清除元数据映射。
        搜索时会跳过已删除的记录。
        """
        with self._lock:
            if id in self._id_to_index:
                idx = self._id_to_index.pop(id)
                self._index_to_id.pop(idx, None)
                self._metadata.pop(id, None)

    def count(self) -> int:
        """返回当前存储的向量总数。"""
        return len(self._id_to_index)

    def list_ids(self) -> List[str]:
        """返回当前存储的全部向量 ID（用于增量重建/一致性检查）。"""
        with self._lock:
            return list(self._id_to_index.keys())

    def get_metadata(self, id: str) -> Dict[str, Any]:
        """返回指定 ID 的元数据；不存在返回空 dict。"""
        with self._lock:
            return dict(self._metadata.get(id, {}))


# 全局单例
_vector_store: Optional[FaissVectorStore] = None


def get_vector_store(dimension: int = 512) -> FaissVectorStore:
    """获取向量存储单例。"""
    global _vector_store
    if _vector_store is None:
        _vector_store = FaissVectorStore(dimension=dimension)
    return _vector_store


def reset_vector_store() -> None:
    """重置向量存储单例（用于测试）。"""
    global _vector_store
    _vector_store = None


# 题目向量库单例（与知识点向量库隔离，独立 collection/命名空间）
_question_vector_store: Optional[FaissVectorStore] = None


def get_question_vector_store(dimension: int = 512) -> FaissVectorStore:
    """获取题目向量存储单例（独立于知识点向量库）。"""
    global _question_vector_store
    if _question_vector_store is None:
        _question_vector_store = FaissVectorStore(dimension=dimension)
    return _question_vector_store


def reset_question_vector_store() -> None:
    """重置题目向量存储单例（用于测试）。"""
    global _question_vector_store
    _question_vector_store = None
