"""知识导入编排服务模块。

本模块是正式导入流程的核心编排层，负责协调：
    DocumentParser → TextChunker → KnowledgeExtractAgent
    → Batch 去重 → 数据库去重 → NEW/DUPLICATE/MERGE 落库
    → Embedding 同步 → KnowledgeRelationAgent 关系生成

职责边界：
    - KnowledgeImportService = 流程编排（本模块）
    - KnowledgeExtractAgent = LLM 提取候选知识
    - KnowledgeDeduplicatePipeline = 去重判断
    - KnowledgeService = 真正保存 Knowledge
    - KnowledgeRelationAgent = 关系判断
    - EmbeddingSyncService = 向量同步

数据所有权：
    MySQL = Source of Truth
    Vector DB = Search Index

关键原则：
    1. 先提交 MySQL，再同步 Vector DB
    2. 单个 Candidate 失败不影响其他 Candidate
    3. 关系失败不回滚已保存的 Knowledge
    4. 重复导入必须幂等（去重 + 唯一约束）
    5. 关系检索限定同一知识库
"""

import logging
import os
import time
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple

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
from app.models.knowledge_relation import KnowledgeRelation
from app.repositories.import_task_repository import ImportTaskRepository
from app.repositories.knowledge_relation_repository import KnowledgeRelationRepository
from app.repositories.knowledge_repository import KnowledgeRepository
from app.services.embedding_sync_service import EmbeddingSyncService

logger = logging.getLogger(__name__)

# 导入任务的处理阶段和进度映射
STAGE_PARSING = "PARSING"
STAGE_EXTRACTING = "EXTRACTING_KNOWLEDGE"
STAGE_DEDUPLICATING = "DEDUPLICATING_KNOWLEDGE"
STAGE_SAVING = "SAVING_KNOWLEDGE"
STAGE_SYNCING = "SYNCING_EMBEDDINGS"
STAGE_RELATIONS = "BUILDING_RELATIONS"

# 置信度阈值（集中配置）
RELATION_MIN_CONFIDENCE = 0.5


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
        self.decision = decision
        self.target_knowledge_id = target_knowledge_id
        self.knowledge_id = knowledge_id
        self.status = status
        self.error = error
        self.method = method


class KnowledgeImportService:
    """知识导入编排服务。"""

    def __init__(self, db: Session):
        self.db = db
        self.task_repo = ImportTaskRepository(db)
        self.knowledge_repo = KnowledgeRepository(db)
        self.relation_repo = KnowledgeRelationRepository(db)
        self.embedding_sync = EmbeddingSyncService(db)
        self.normalizer = KnowledgeNormalizer()

    def execute_import(self, task_id: int) -> Dict:
        """执行完整的知识导入流程（含关系生成）。"""
        task = self.task_repo.get_by_id(task_id)
        if not task:
            raise ValueError(f"导入任务 {task_id} 不存在")

        start_time = time.time()
        errors = []

        try:
            self._update_task_status(task, "RUNNING", STAGE_PARSING, 0)

            # 阶段 1~6：解析→提取→去重→落库→Embedding 同步
            parse_result = self._stage_parse(task)
            candidates = self._stage_extract(task, parse_result)
            unique_candidates = self._stage_batch_dedup(task, candidates)
            results, changed_knowledge_ids = self._stage_dedup_and_save(task, unique_candidates)

            # 阶段 7：Embedding 同步
            self._update_task_status(task, "RUNNING", STAGE_SYNCING, 85)

            # 阶段 8：关系生成（只处理本批新增/变更的知识）
            relation_stats = {}
            if changed_knowledge_ids:
                self._update_task_status(task, "RUNNING", STAGE_RELATIONS, 90)
                relation_stats = self.build_relations_for_import(
                    changed_knowledge_ids=list(changed_knowledge_ids),
                    knowledge_base_id=getattr(task, 'knowledge_base_id', 0) or 0,
                    task_id=task_id,
                )

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
                "changed_knowledge_ids": list(changed_knowledge_ids),
                "relation_stats": relation_stats,
                "duration": round(duration, 2),
                "errors": errors,
            }

        except Exception as e:
            duration = time.time() - start_time
            errors.append(str(e))
            logger.error(f"导入任务 {task_id} 执行失败: {e}")
            self._update_task_status(task, "FAILED", "FAILED", task.progress or 0, error=str(e))
            return {
                "task_id": task_id,
                "status": "FAILED",
                "candidate_count": 0, "new_count": 0,
                "duplicate_count": 0, "merge_count": 0,
                "failed_count": 0,
                "changed_knowledge_ids": [],
                "relation_stats": {},
                "duration": round(duration, 2),
                "errors": errors,
            }

    # ========== 知识保存阶段（收集 changed_knowledge_ids） ==========

    def _stage_dedup_and_save(self, task, candidates: List[KnowledgeCandidate]) -> Tuple[List[CandidateResult], Set[int]]:
        """阶段 5+6：去重 + 落库，收集本批新增/变更的 knowledge_id。"""
        self._update_task_status(task, "RUNNING", STAGE_SAVING, 75)

        kb_id = getattr(task, 'knowledge_base_id', 0) or 0
        results = []
        changed_ids: Set[int] = set()

        for candidate in candidates:
            try:
                result = self._process_single_candidate(candidate, kb_id)
                results.append(result)

                # 收集新增或变更的 knowledge_id
                if result.status == "SUCCESS":
                    if result.decision == "NEW" and result.knowledge_id:
                        changed_ids.add(result.knowledge_id)
                    elif result.decision == "MERGE" and result.knowledge_id:
                        changed_ids.add(result.knowledge_id)
                # DUPLICATE 不需要生成关系

            except Exception as e:
                logger.error(f"候选 '{candidate.name}' 处理失败: {e}")
                results.append(CandidateResult(
                    candidate=candidate, decision="NEW",
                    status="FAILED", error=str(e),
                ))

        self._update_task_status(task, "RUNNING", STAGE_SAVING, 85)
        return results, changed_ids

    def _process_single_candidate(self, candidate: KnowledgeCandidate, knowledge_base_id: int = 0) -> CandidateResult:
        """处理单个候选知识点。"""
        existing_list = self._get_existing_knowledge_for_dedup(candidate, knowledge_base_id)
        dedup_result = run_dedup_for_candidate(candidate, existing_list)
        decision = dedup_result.decision

        if decision.decision == "NEW":
            knowledge = self._create_knowledge(candidate, knowledge_base_id)
            self._sync_embedding(knowledge)
            return CandidateResult(
                candidate=candidate, decision="NEW",
                knowledge_id=knowledge.id, status="SUCCESS",
                method=dedup_result.method,
            )
        elif decision.decision == "DUPLICATE":
            return CandidateResult(
                candidate=candidate, decision="DUPLICATE",
                target_knowledge_id=decision.target_knowledge_id,
                status="SUCCESS", method=dedup_result.method,
            )
        elif decision.decision == "MERGE":
            if decision.target_knowledge_id and decision.merged_knowledge:
                knowledge = self._merge_knowledge(decision.target_knowledge_id, decision.merged_knowledge)
                self._sync_embedding(knowledge)
                return CandidateResult(
                    candidate=candidate, decision="MERGE",
                    target_knowledge_id=decision.target_knowledge_id,
                    knowledge_id=decision.target_knowledge_id,
                    status="SUCCESS", method=dedup_result.method,
                )
            else:
                return CandidateResult(
                    candidate=candidate, decision="MERGE",
                    status="FAILED", error="MERGE 但缺少目标或合并内容",
                    method=dedup_result.method,
                )

        return CandidateResult(candidate=candidate, decision="NEW", status="FAILED", error="未知决策")

    # ========== 关系生成阶段 ==========

    def build_relations_for_import(
        self,
        changed_knowledge_ids: List[int],
        knowledge_base_id: int,
        task_id: int,
    ) -> Dict:
        """为本批新增/变更的知识点自动生成关系。

        流程：
            1. 逐个 changed_knowledge 作为锚点
            2. 同库 Vector 检索候选
            3. MySQL 二次校验（同库、可用）
            4. KnowledgeRelationAgent 判断
            5. 确定性校验 + 去重
            6. RelationService 写入

        Args:
            changed_knowledge_ids: 本批新增/变更的知识点 ID 列表
            knowledge_base_id: 目标知识库 ID
            task_id: 导入任务 ID

        Returns:
            关系生成统计 dict
        """
        from agent.knowledge_relation.graph import run_relation_test
        from agent.knowledge_relation.schemas import RelationKnowledgeInput

        start_time = time.time()
        stats = {
            "anchor_count": 0,
            "relation_suggested": 0,
            "relation_written": 0,
            "relation_duplicate": 0,
            "relation_failed": 0,
            "llm_call_count": 0,
        }

        # 去重排序
        unique_ids = sorted(set(changed_knowledge_ids))
        logger.info(f"关系生成开始: {len(unique_ids)} 个锚点, 知识库={knowledge_base_id}")

        for anchor_id in unique_ids:
            try:
                anchor = self.knowledge_repo.get_by_id(anchor_id)
                if not anchor or anchor.status != 1:
                    continue

                # 校验锚点属于目标知识库
                if knowledge_base_id and anchor.knowledge_base_id != knowledge_base_id:
                    logger.warning(f"锚点 {anchor_id} 不属于知识库 {knowledge_base_id}，跳过")
                    continue

                stats["anchor_count"] += 1

                # 构造锚点输入
                source = RelationKnowledgeInput(
                    id=anchor.id, name=anchor.name,
                    summary=anchor.summary or "",
                    content=(anchor.content or "")[:500],
                    keywords=anchor.keywords or [],
                )

                # 同库检索候选
                candidates = self._get_relation_candidates(anchor, knowledge_base_id)

                if not candidates:
                    logger.info(f"锚点 {anchor_id} 无同库候选，跳过")
                    continue

                # 调用 RelationAgent
                result = run_relation_test(
                    source=source,
                    provided_candidates=candidates,
                    top_k=10,
                )
                stats["llm_call_count"] += result.get("llm_call_count", 0)

                # 处理判定结果
                for eval_item in result.get("evaluations", []):
                    if eval_item.get("decision") != "RELATION":
                        continue

                    relation_type = eval_item.get("relation_type")
                    from_id = eval_item.get("from_knowledge_id")
                    to_id = eval_item.get("to_knowledge_id")
                    confidence = eval_item.get("confidence", 0)

                    stats["relation_suggested"] += 1

                    # 置信度过滤
                    if confidence < RELATION_MIN_CONFIDENCE:
                        continue

                    # 确定性校验
                    if not from_id or not to_id or from_id == to_id:
                        continue
                    if relation_type not in {"prerequisite", "related", "extension", "contrast"}:
                        continue

                    # 校验双方都属于同一知识库
                    from_k = self.knowledge_repo.get_by_id(from_id)
                    to_k = self.knowledge_repo.get_by_id(to_id)
                    if not from_k or not to_k:
                        continue
                    if knowledge_base_id and (from_k.knowledge_base_id != knowledge_base_id or to_k.knowledge_base_id != knowledge_base_id):
                        continue

                    # 写入关系（幂等）
                    try:
                        # 检查是否已存在（含反向 related/contrast）
                        if self.relation_repo.check_exists(from_id, to_id, relation_type):
                            stats["relation_duplicate"] += 1
                            continue

                        # related/contrast 对称关系：也检查反向
                        if relation_type in ("related", "contrast"):
                            if self.relation_repo.check_exists(to_id, from_id, relation_type):
                                stats["relation_duplicate"] += 1
                                continue

                        self.relation_repo.create(
                            source_knowledge_id=from_id,
                            target_knowledge_id=to_id,
                            relation_type=relation_type,
                        )
                        stats["relation_written"] += 1

                    except Exception as e:
                        stats["relation_failed"] += 1
                        logger.error(f"关系写入失败: {from_id}->{to_id} {relation_type}: {e}")

                self.db.commit()

            except Exception as e:
                stats["relation_failed"] += 1
                logger.error(f"锚点 {anchor_id} 关系生成失败: {e}")
                self.db.rollback()

        duration = round(time.time() - start_time, 2)
        stats["duration"] = duration

        logger.info(
            f"关系生成完成: 锚点={stats['anchor_count']}, "
            f"建议={stats['relation_suggested']}, "
            f"写入={stats['relation_written']}, "
            f"重复跳过={stats['relation_duplicate']}, "
            f"失败={stats['relation_failed']}, "
            f"LLM调用={stats['llm_call_count']}, "
            f"耗时={duration}s"
        )

        return stats

    def _get_relation_candidates(self, anchor: Knowledge, knowledge_base_id: int) -> List:
        """为锚点获取同库候选知识点（用于关系判断）。"""
        from agent.knowledge_relation.schemas import RelationKnowledgeInput

        try:
            service = get_embedding_service()
            store = get_vector_store()

            text = self.normalizer.build_embedding_text(
                anchor.name, anchor.summary, anchor.keywords or []
            )
            vec = service.embed_text(text)

            # over-fetch + 后过滤
            results = store.search(vec, top_k=20)

            candidates = []
            for r in results:
                meta = r.metadata
                kid = meta.get("knowledge_id", 0)

                # 排除自身
                if kid == anchor.id:
                    continue

                # 限定同库
                if knowledge_base_id and meta.get("knowledge_base_id") != knowledge_base_id:
                    continue

                # MySQL 二次校验
                k = self.knowledge_repo.get_by_id(kid)
                if not k or k.status != 1:
                    continue
                if knowledge_base_id and k.knowledge_base_id != knowledge_base_id:
                    continue

                candidates.append(RelationKnowledgeInput(
                    id=k.id, name=k.name,
                    summary=k.summary or "",
                    content=(k.content or "")[:500],
                    keywords=k.keywords or [],
                ))

                if len(candidates) >= 10:
                    break

            return candidates

        except Exception as e:
            logger.error(f"关系候选检索失败: {e}")
            return []

    # ========== 其余辅助方法（复用原有） ==========

    def _stage_parse(self, task) -> Dict:
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
        from agent.knowledge_extract.chunker import TextChunker
        self._update_task_status(task, "RUNNING", STAGE_EXTRACTING, 10)
        document = parse_result["document"]
        chunker = TextChunker()
        chunks = chunker.chunk(document)
        logger.info(f"文档分块完成: {len(chunks)} 个 Chunk")
        extract_result = run_extraction(
            file_path=os.path.join("uploads", task.file_path),
            file_name=task.file_name,
        )
        candidates = extract_result.knowledge_points
        logger.info(f"LLM 提取完成: {len(candidates)} 个候选知识点")
        self._update_task_status(task, "RUNNING", STAGE_EXTRACTING, 50)
        return candidates

    def _stage_batch_dedup(self, task, candidates: List[KnowledgeCandidate]) -> List[KnowledgeCandidate]:
        self._update_task_status(task, "RUNNING", STAGE_DEDUPLICATING, 50)
        dedup_result = dedup_candidates_batch(candidates)
        unique = dedup_result.unique_candidates
        logger.info(f"批次去重完成: 输入 {len(candidates)}, 去重后 {len(unique)}")
        self._update_task_status(task, "RUNNING", STAGE_DEDUPLICATING, 65)
        return unique

    def _get_existing_knowledge_for_dedup(self, candidate: KnowledgeCandidate, knowledge_base_id: int = 0) -> List[ExistingKnowledge]:
        try:
            service = get_embedding_service()
            store = get_vector_store()
            text = self.normalizer.build_embedding_text(candidate.name, candidate.summary, candidate.keywords)
            vec = service.embed_text(text)
            fetch_k = 20 if knowledge_base_id else 5
            results = store.search(vec, top_k=fetch_k)
            existing = []
            for r in results:
                meta = r.metadata
                if knowledge_base_id and meta.get("knowledge_base_id") != knowledge_base_id:
                    continue
                existing.append(ExistingKnowledge(
                    id=meta.get("knowledge_id", 0), name=meta.get("name", ""),
                    summary=meta.get("summary", ""), content=meta.get("content", "")[:500],
                    difficulty=meta.get("difficulty", 2), keywords=meta.get("keywords", []),
                    similarity=r.score,
                ))
                if len(existing) >= 5:
                    break
            return existing
        except Exception as e:
            logger.warning(f"向量检索失败: {e}")
            return []

    def _create_knowledge(self, candidate: KnowledgeCandidate, knowledge_base_id: int = 0) -> Knowledge:
        knowledge = Knowledge(
            knowledge_base_id=knowledge_base_id, name=candidate.name,
            summary=candidate.summary, content=candidate.content,
            difficulty=candidate.difficulty, status=1,
            source_type="IMPORT", keywords=candidate.keywords,
        )
        self.db.add(knowledge)
        self.db.commit()
        self.db.refresh(knowledge)
        logger.info(f"新知识点创建: id={knowledge.id}, name={knowledge.name}")
        return knowledge

    def _merge_knowledge(self, target_id: int, merged: MergedKnowledge) -> Knowledge:
        knowledge = self.db.query(Knowledge).filter(Knowledge.id == target_id).first()
        if not knowledge:
            raise ValueError(f"目标知识点 {target_id} 不存在")
        knowledge.name = merged.name
        knowledge.summary = merged.summary
        knowledge.content = merged.content
        knowledge.difficulty = merged.difficulty
        knowledge.keywords = merged.keywords
        self.db.commit()
        self.db.refresh(knowledge)
        logger.info(f"知识点合并更新: id={knowledge.id}")
        return knowledge

    def _sync_embedding(self, knowledge: Knowledge) -> None:
        try:
            self.embedding_sync.sync_knowledge(knowledge.id)
        except Exception as e:
            logger.error(f"知识点 {knowledge.id} 向量同步失败: {e}")

    def _update_task_status(self, task, status: str, current_step: str, progress: int, error: Optional[str] = None) -> None:
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

    # ========== 关系阶段重试 ==========

    def retry_relations(self, task_id: int) -> Dict:
        """重试导入任务的关系生成阶段（仅重跑关系，不重复导入知识）。"""
        task = self.task_repo.get_by_id(task_id)
        if not task:
            raise ValueError(f"导入任务 {task_id} 不存在")

        # 找到本任务关联的知识点（通过 source_type=IMPORT 且时间相近）
        kb_id = getattr(task, 'knowledge_base_id', 0) or 0

        # 从任务结果中获取 changed_knowledge_ids（如果有记录）
        # 或者按时间范围查找本次任务创建的知识
        if task.started_at and task.finished_at:
            from sqlalchemy import and_
            changed = self.db.query(Knowledge.id).filter(
                and_(
                    Knowledge.knowledge_base_id == kb_id,
                    Knowledge.source_type == "IMPORT",
                    Knowledge.created_at >= task.started_at,
                    Knowledge.created_at <= task.finished_at,
                )
            ).all()
            changed_ids = [row[0] for row in changed]
        else:
            changed_ids = []

        if not changed_ids:
            return {
                "task_id": task_id,
                "status": "SKIPPED",
                "message": "未找到本任务的知识点，无法重试关系",
                "relation_stats": {},
            }

        self._update_task_status(task, "RUNNING", STAGE_RELATIONS, 90)
        relation_stats = self.build_relations_for_import(
            changed_knowledge_ids=changed_ids,
            knowledge_base_id=kb_id,
            task_id=task_id,
        )

        self._update_task_status(task, "SUCCESS", "FINISHED", 100)

        return {
            "task_id": task_id,
            "status": "SUCCESS",
            "changed_knowledge_ids": changed_ids,
            "relation_stats": relation_stats,
        }
