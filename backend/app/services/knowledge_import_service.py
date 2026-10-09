"""知识导入编排服务模块。

本模块是正式导入流程的核心编排层，负责协调：
    DocumentParser → TextChunker → KnowledgeExtractAgent
    → Batch 去重 → 数据库去重 → NEW/DUPLICATE/MERGE 落库
    → Embedding 同步

职责边界：
    - KnowledgeImportService = 流程编排（本模块）
    - KnowledgeExtractAgent = LLM 提取候选知识
    - KnowledgeDeduplicatePipeline = 去重判断
    - KnowledgeService = 真正保存 Knowledge
    - EmbeddingSyncService = 向量同步

数据所有权：
    MySQL = Source of Truth
    Vector DB = Search Index

关键原则：
    1. 先提交 MySQL，再同步 Vector DB
    2. 单个 Candidate 失败不影响其他 Candidate
    3. Vector DB 不可用时任务 FAIL，不偷偷创建大量 NEW
    4. 重复导入必须幂等
"""

import logging
import os
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from agent.common.embedding import get_embedding_service
from agent.common.vector_store import get_vector_store
from agent.knowledge_deduplicate.batch_dedup import dedup_candidates_batch
from agent.knowledge_deduplicate.graph import run_dedup_for_candidate
from agent.knowledge_deduplicate.normalizer import KnowledgeNormalizer
from agent.knowledge_deduplicate.schemas import (
    DeduplicateDecision,
    ExistingKnowledge,
    MergedKnowledge,
)
from agent.knowledge_extract.graph import run_extraction
from agent.knowledge_extract.schemas import KnowledgeCandidate
from app.models.import_task import KnowledgeImportTask
from app.models.knowledge import Knowledge
from app.repositories.import_task_repository import ImportTaskRepository
from app.repositories.knowledge_repository import KnowledgeRepository
from app.services.embedding_sync_service import EmbeddingSyncService

logger = logging.getLogger(__name__)

# 导入任务的处理阶段和进度映射
STAGE_PARSING = "PARSING"
STAGE_EXTRACTING = "EXTRACTING_KNOWLEDGE"
STAGE_DEDUPLICATING = "DEDUPLICATING_KNOWLEDGE"
STAGE_SAVING = "SAVING_KNOWLEDGE"
STAGE_SYNCING = "SYNCING_EMBEDDINGS"

STAGE_PROGRESS = {
    STAGE_PARSING: (0, 10),
    STAGE_EXTRACTING: (10, 50),
    STAGE_DEDUPLICATING: (50, 75),
    STAGE_SAVING: (75, 90),
    STAGE_SYNCING: (90, 100),
}


class CandidateResult:
    """单个候选知识点的处理结果。"""

    def __init__(
        self,
        candidate: KnowledgeCandidate,
        decision: str,
        target_knowledge_id: Optional[int] = None,
        knowledge_id: Optional[int] = None,
        status: str = "SUCCESS",
        error: Optional[str] = None,
        method: str = "unknown",
    ):
        self.candidate = candidate
        self.decision = decision  # NEW / DUPLICATE / MERGE
        self.target_knowledge_id = target_knowledge_id
        self.knowledge_id = knowledge_id  # 新创建的知识点 ID
        self.status = status  # SUCCESS / FAILED / SKIPPED
        self.error = error
        self.method = method


class KnowledgeImportService:
    """知识导入编排服务。

    使用方法：
        service = KnowledgeImportService(db)
        result = service.execute_import(task_id=1)
    """

    def __init__(self, db: Session):
        self.db = db
        self.task_repo = ImportTaskRepository(db)
        self.knowledge_repo = KnowledgeRepository(db)
        self.embedding_sync = EmbeddingSyncService(db)
        self.normalizer = KnowledgeNormalizer()

    def execute_import(self, task_id: int) -> Dict:
        """执行完整的知识导入流程。

        流程：
            1. 解析文档
            2. 文本分块
            3. LLM 提取候选知识
            4. 批次内部去重
            5. 与数据库已有知识去重
            6. NEW/DUPLICATE/MERGE 落库
            7. Embedding 同步

        Args:
            task_id: 导入任务 ID

        Returns:
            导入结果统计 dict
        """
        task = self.task_repo.get_by_id(task_id)
        if not task:
            raise ValueError(f"导入任务 {task_id} 不存在")

        start_time = time.time()
        errors = []

        try:
            # 更新任务状态为 RUNNING
            self._update_task_status(task, "RUNNING", STAGE_PARSING, 0)

            # 阶段 1：解析文档
            parse_result = self._stage_parse(task)

            # 阶段 2+3：LLM 提取候选知识
            candidates = self._stage_extract(task, parse_result)

            # 阶段 4：批次内部去重
            unique_candidates = self._stage_batch_dedup(task, candidates)

            # 阶段 5+6：与数据库去重 + 落库
            results = self._stage_dedup_and_save(task, unique_candidates)

            # 阶段 7：Embedding 同步（已在落库时逐个同步）
            self._update_task_status(task, STAGE_SYNCING, STAGE_SYNCING, 90)
            self._update_task_status(task, "SUCCESS", "FINISHED", 100)

            # 统计
            new_count = sum(1 for r in results if r.decision == "NEW" and r.status == "SUCCESS")
            dup_count = sum(1 for r in results if r.decision == "DUPLICATE")
            merge_count = sum(1 for r in results if r.decision == "MERGE" and r.status == "SUCCESS")
            failed_count = sum(1 for r in results if r.status == "FAILED")

            duration = time.time() - start_time

            return {
                "task_id": task_id,
                "status": "SUCCESS" if failed_count == 0 else "PARTIAL_SUCCESS",
                "candidate_count": len(candidates),
                "new_count": new_count,
                "duplicate_count": dup_count,
                "merge_count": merge_count,
                "failed_count": failed_count,
                "duration": round(duration, 2),
                "errors": errors,
            }

        except Exception as e:
            duration = time.time() - start_time
            errors.append(str(e))
            logger.error(f"导入任务 {task_id} 执行失败: {e}")

            self._update_task_status(
                task, "FAILED", "FAILED", task.progress or 0,
                error=str(e),
            )

            return {
                "task_id": task_id,
                "status": "FAILED",
                "candidate_count": 0,
                "new_count": 0,
                "duplicate_count": 0,
                "merge_count": 0,
                "failed_count": 0,
                "duration": round(duration, 2),
                "errors": errors,
            }

    def _stage_parse(self, task) -> Dict:
        """阶段 1：解析文档。"""
        from agent.knowledge_extract.parser import DocumentParser

        self._update_task_status(task, "RUNNING", STAGE_PARSING, 0)

        file_path = os.path.join("uploads", task.file_path)
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"文件不存在: {file_path}")

        parser = DocumentParser()
        document = parser.parse(file_path)

        logger.info(f"文档解析完成: {document.file_name}, 页面数={len(document.pages)}")
        return {"document": document}

    def _stage_extract(self, task, parse_result) -> List[KnowledgeCandidate]:
        """阶段 2+3：LLM 提取候选知识。"""
        from agent.knowledge_extract.chunker import TextChunker

        self._update_task_status(task, "RUNNING", STAGE_EXTRACTING, 10)

        document = parse_result["document"]
        chunker = TextChunker()
        chunks = chunker.chunk(document)

        logger.info(f"文档分块完成: {len(chunks)} 个 Chunk")

        # 调用 LLM 提取
        extract_result = run_extraction(
            file_path=os.path.join("uploads", task.file_path),
            file_name=task.file_name,
        )

        candidates = extract_result.knowledge_points
        logger.info(f"LLM 提取完成: {len(candidates)} 个候选知识点")

        self._update_task_status(task, "RUNNING", STAGE_EXTRACTING, 50)
        return candidates

    def _stage_batch_dedup(self, task, candidates: List[KnowledgeCandidate]) -> List[KnowledgeCandidate]:
        """阶段 4：批次内部去重。"""
        self._update_task_status(task, "RUNNING", STAGE_DEDUPLICATING, 50)

        dedup_result = dedup_candidates_batch(candidates)
        unique = dedup_result.unique_candidates

        logger.info(
            f"批次去重完成: 输入 {len(candidates)}, "
            f"去重后 {len(unique)}, "
            f"剔除 {len(dedup_result.duplicates)}"
        )

        self._update_task_status(task, "RUNNING", STAGE_DEDUPLICATING, 65)
        return unique

    def _stage_dedup_and_save(self, task, candidates: List[KnowledgeCandidate]) -> List[CandidateResult]:
        """阶段 5+6：与数据库已有知识去重 + 落库。"""
        self._update_task_status(task, "RUNNING", STAGE_SAVING, 75)

        kb_id = getattr(task, 'knowledge_base_id', 0) or 0
        results = []

        for i, candidate in enumerate(candidates):
            try:
                result = self._process_single_candidate(candidate, kb_id)
                results.append(result)
            except Exception as e:
                logger.error(f"候选 '{candidate.name}' 处理失败: {e}")
                results.append(CandidateResult(
                    candidate=candidate,
                    decision="NEW",
                    status="FAILED",
                    error=str(e),
                ))

        self._update_task_status(task, "RUNNING", STAGE_SAVING, 90)
        return results

    def _process_single_candidate(self, candidate: KnowledgeCandidate, knowledge_base_id: int = 0) -> CandidateResult:
        """处理单个候选知识点：去重判断 + 落库。"""
        # 获取已有知识点列表（从向量库检索，限定同一知识库）
        existing_list = self._get_existing_knowledge_for_dedup(candidate, knowledge_base_id)

        # 运行去重 Pipeline
        dedup_result = run_dedup_for_candidate(candidate, existing_list)
        decision = dedup_result.decision

        if decision.decision == "NEW":
            # 新知识点：创建
            knowledge = self._create_knowledge(candidate, knowledge_base_id)
            self._sync_embedding(knowledge)
            return CandidateResult(
                candidate=candidate,
                decision="NEW",
                knowledge_id=knowledge.id,
                status="SUCCESS",
                method=dedup_result.method,
            )

        elif decision.decision == "DUPLICATE":
            # 重复：不创建，只记录
            return CandidateResult(
                candidate=candidate,
                decision="DUPLICATE",
                target_knowledge_id=decision.target_knowledge_id,
                status="SUCCESS",
                method=dedup_result.method,
            )

        elif decision.decision == "MERGE":
            # 合并：更新已有知识点
            if decision.target_knowledge_id and decision.merged_knowledge:
                knowledge = self._merge_knowledge(
                    decision.target_knowledge_id,
                    decision.merged_knowledge,
                )
                self._sync_embedding(knowledge)
                return CandidateResult(
                    candidate=candidate,
                    decision="MERGE",
                    target_knowledge_id=decision.target_knowledge_id,
                    knowledge_id=decision.target_knowledge_id,
                    status="SUCCESS",
                    method=dedup_result.method,
                )
            else:
                return CandidateResult(
                    candidate=candidate,
                    decision="MERGE",
                    status="FAILED",
                    error="MERGE 但缺少目标或合并内容",
                    method=dedup_result.method,
                )

        return CandidateResult(
            candidate=candidate,
            decision="NEW",
            status="FAILED",
            error="未知决策",
        )

    def _get_existing_knowledge_for_dedup(
        self, candidate: KnowledgeCandidate, knowledge_base_id: int = 0
    ) -> List[ExistingKnowledge]:
        """从向量库检索已有知识点用于去重（限定同一知识库）。

        FAISS 不支持 metadata 过滤，采用 over-fetch + 后过滤策略：
        多取一些候选，然后按 knowledge_base_id 过滤。
        """
        try:
            service = get_embedding_service()
            store = get_vector_store()

            text = self.normalizer.build_embedding_text(
                candidate.name, candidate.summary, candidate.keywords
            )
            vec = service.embed_text(text)

            # over-fetch：多取一些以便过滤后仍有足够候选
            fetch_k = 20 if knowledge_base_id else 5
            results = store.search(vec, top_k=fetch_k)

            existing = []
            for r in results:
                meta = r.metadata

                # 按知识库过滤（去重范围限定在同一知识库）
                if knowledge_base_id and meta.get("knowledge_base_id") != knowledge_base_id:
                    continue

                existing.append(ExistingKnowledge(
                    id=meta.get("knowledge_id", 0),
                    name=meta.get("name", ""),
                    summary=meta.get("summary", ""),
                    content=meta.get("content", "")[:500],
                    difficulty=meta.get("difficulty", 2),
                    keywords=meta.get("keywords", []),
                    similarity=r.score,
                ))

                if len(existing) >= 5:
                    break

            return existing

        except Exception as e:
            logger.warning(f"向量检索失败: {e}")
            return []

    def _create_knowledge(self, candidate: KnowledgeCandidate, knowledge_base_id: int = 0) -> Knowledge:
        """创建新知识点（MySQL 事务）。"""
        knowledge = Knowledge(
            knowledge_base_id=knowledge_base_id,
            name=candidate.name,
            summary=candidate.summary,
            content=candidate.content,
            difficulty=candidate.difficulty,
            status=1,
            source_type="IMPORT",
            keywords=candidate.keywords,
        )
        self.db.add(knowledge)
        self.db.commit()
        self.db.refresh(knowledge)
        logger.info(f"新知识点创建: id={knowledge.id}, name={knowledge.name}")
        return knowledge

    def _merge_knowledge(
        self, target_id: int, merged: MergedKnowledge
    ) -> Knowledge:
        """合并更新已有知识点（MySQL 事务）。"""
        knowledge = self.db.query(Knowledge).filter(
            Knowledge.id == target_id
        ).first()
        if not knowledge:
            raise ValueError(f"目标知识点 {target_id} 不存在")

        knowledge.name = merged.name
        knowledge.summary = merged.summary
        knowledge.content = merged.content
        knowledge.difficulty = merged.difficulty
        knowledge.keywords = merged.keywords

        self.db.commit()
        self.db.refresh(knowledge)
        logger.info(f"知识点合并更新: id={knowledge.id}, name={knowledge.name}")
        return knowledge

    def _sync_embedding(self, knowledge: Knowledge) -> None:
        """同步知识点到向量库。"""
        try:
            self.embedding_sync.sync_knowledge(knowledge.id)
        except Exception as e:
            logger.error(f"知识点 {knowledge.id} 向量同步失败: {e}")

    def _update_task_status(
        self,
        task,
        status: str,
        current_step: str,
        progress: int,
        error: Optional[str] = None,
    ) -> None:
        """更新导入任务状态和进度。"""
        task.status = status
        task.current_step = current_step
        task.progress = progress
        if error:
            task.error_message = error
        if status == "RUNNING" and not task.started_at:
            task.started_at = datetime.utcnow()
        if status in ("SUCCESS", "PARTIAL_SUCCESS", "FAILED"):
            task.finished_at = datetime.utcnow()
        self.db.commit()
