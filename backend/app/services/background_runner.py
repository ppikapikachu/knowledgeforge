"""后台任务执行器。

将耗时的导入任务从 API 请求路径中分离，避免阻塞事件循环。
使用 threading 实现，不引入 Redis/Celery/RabbitMQ。

工作方式：
    API 验证并创建任务 → 启动后台线程 → 立即返回 task_id
    后台线程独立执行导入流程 → 更新任务状态
"""

import logging
import threading
from typing import Optional

logger = logging.getLogger(__name__)

# 控制并发：初期限制为 1
_import_semaphore = threading.Semaphore(1)

# 后台线程注册表：测试/进程收尾时可等待后台任务结束（防止
# 后台生成线程的数据库事务与 teardown 的 DDL 互相等待）
_background_threads_lock = threading.Lock()
_background_threads: list = []


def _spawn(name: str, target, args=()) -> threading.Thread:
    thread = threading.Thread(target=target, args=args, name=name, daemon=True)
    thread.start()
    with _background_threads_lock:
        _background_threads[:] = [t for t in _background_threads if t.is_alive()]
        _background_threads.append(thread)
    return thread


def join_background_tasks(timeout: float = 30.0) -> bool:
    """等待所有后台线程结束（最多 timeout 秒）。全部结束返回 True。"""
    with _background_threads_lock:
        threads = [t for t in _background_threads if t.is_alive()]
    for thread in threads:
        thread.join(timeout=max(0.0, timeout / max(1, len(threads))))
    return not any(t.is_alive() for t in threads)


def run_generation_in_background(task_id: int, request_config: dict) -> None:
    """在后台线程中执行题目生成任务。"""
    _spawn(f"gen-task-{task_id}", execute_generation_task, (task_id, request_config))


def execute_generation_task(task_id: int, request_config: dict, session_factory=None) -> None:
    """题目生成任务主流程（同步可测；run_generation_in_background 包一层线程）。

    集成题目多层去重（执行文档《DSH_题目多层去重服务开发与接入执行文档》§7）：
    - 每个知识点按"重试轮次"生成：本轮被去重跳过 / 生成失败的缺口在上限内重试
      （QUESTION_DEDUP_MAX_REGENERATION_ATTEMPTS、QUESTION_DEDUP_MAX_GENERATION_MULTIPLIER）；
    - 同一任务共享 batch_context（任务内新题相互去重）与 TaskContext（审计）；
    - 精确重复 = exact_duplicate_count；算法/语义重复（含批次内）= semantic_duplicate_count；
      LLM 不确定但保留 = uncertain_count（保持 pending_review，本就需人工审核）；
      duplicate_count = exact + semantic（兼容旧字段）；success_count = 最终入库数；
      failed_count = 普通生成/校验失败数；unfulfilled_count = 重试用尽仍未补足数。
    """
    from datetime import datetime

    from agent.common.config import agent_settings

    if session_factory is None:
        from app.core.database import SessionLocal as session_factory  # noqa: N813

    from agent.question_generate.agent import QuestionGenerateAgent
    from app.models.question import Question
    from app.models.question_generation_task import QuestionGenerationTask
    from app.models.question_knowledge import QuestionKnowledge
    from app.models.question_option import QuestionOption
    from app.services.question_dedup_service import (
        QuestionDeduplicationService,
        TaskContext,
        get_dedup_readiness_status,
        snapshot_from_generated,
    )
    from app.services.question_normalizer import HASH_VERSION

    db = session_factory()
    try:
        task = db.query(QuestionGenerationTask).filter(
            QuestionGenerationTask.id == task_id
        ).first()
        if not task:
            logger.error(f"生成任务 {task_id} 不存在")
            return

        # §2.4 索引不可用时新任务不得进入正式生成流程：安全失败 + 明确报错
        readiness_status = get_dedup_readiness_status()
        if agent_settings.QUESTION_DEDUP_ENABLED and readiness_status in ("initializing", "degraded"):
            task.status = "failed"
            task.error_summary = (
                f"题目去重服务未就绪（status={readiness_status}），"
                f"为避免无提示跳过语义去重，任务安全失败；请恢复索引后重新发起生成"
            )
            task.completed_at = datetime.utcnow()
            db.commit()
            return

        task.status = "running"
        task.started_at = datetime.utcnow()
        db.commit()

        question_bank_id = request_config.get("question_bank_id")
        question_type = request_config.get("question_type", "SINGLE_CHOICE")
        difficulty = request_config.get("difficulty", 2)
        allocation_mode = request_config.get("allocation_mode", "manual")

        agent = QuestionGenerateAgent(db)

        # Determine generation targets: manual (single knowledge_id) or auto (allocation_plan)
        if allocation_mode == "auto" and task.allocation_plan:
            plan_items = task.allocation_plan.get("items", [])
            targets = [
                {"knowledge_id": item["knowledge_id"], "count": item.get("planned_count", 1)}
                for item in plan_items
            ]
        else:
            knowledge_id = request_config.get("knowledge_id")
            count = request_config.get("count", 5)
            targets = [{"knowledge_id": knowledge_id, "count": count}]

        dedup = QuestionDeduplicationService(db)
        task_context = TaskContext(
            task_id=task_id, question_bank_id=question_bank_id,
            question_type=question_type, difficulty=difficulty,
        )
        batch_context: dict = {"accepted": [], "hashes": set()}

        stats = {
            "saved": 0,
            "generated": 0,
            "exact_duplicate": 0,
            "semantic_duplicate": 0,
            "uncertain": 0,
            "failed": 0,
        }
        all_errors: list = []

        for target in targets:
            kid = target["knowledge_id"]
            want = target["count"]
            got = 0
            attempts = 0
            produced = 0
            max_total = max(want, int(want * float(
                getattr(agent_settings, "QUESTION_DEDUP_MAX_GENERATION_MULTIPLIER", 1.5))))
            max_attempts = int(getattr(agent_settings, "QUESTION_DEDUP_MAX_REGENERATION_ATTEMPTS", 2))

            while (got < want and attempts <= max_attempts and produced < max_total):
                # §2.4 执行中索引失效 → 安全失败/暂停，不得静默只跑 Hash 继续出题
                if agent_settings.QUESTION_DEDUP_ENABLED and get_dedup_readiness_status() == "degraded":
                    all_errors.append(
                        f"知识点 {kid}: 执行中向量索引失效（degraded），"
                        f"安全中止该知识点剩余生成")
                    break
                attempts += 1
                to_generate = min(want - got, max_total - produced)
                try:
                    result = agent.generate_for_plan_item(
                        knowledge_id=kid,
                        question_bank_id=question_bank_id,
                        question_type=question_type,
                        difficulty=difficulty,
                        count=to_generate,
                    )
                except Exception as item_err:  # noqa: BLE001
                    all_errors.append(f"知识点 {kid}: {item_err}")
                    logger.error(f"生成任务 {task_id} 知识点 {kid} 生成失败: {item_err}")
                    continue

                if result["errors"]:
                    all_errors.extend(result["errors"])
                stats["failed"] += int(result.get("failed_count") or 0)

                candidates = list(result["questions"])
                produced += len(candidates)
                stats["generated"] += len(candidates)

                snapshots = [
                    snapshot_from_generated(q, question_bank_id, [kid]) for q in candidates
                ]
                dedup_results = dedup.check_batch(snapshots, task_context, batch_context)

                for q, snap, dr in zip(candidates, snapshots, dedup_results):
                    if dr.decision == "duplicate":
                        if dr.decision_method == "exact_hash" or dr.scope_mode == "global_exact":
                            stats["exact_duplicate"] += 1
                        else:
                            stats["semantic_duplicate"] += 1
                        db.commit()  # 持久化审计记录
                        continue

                    def _save(q=q, snap=snap, kid=kid):
                        question = Question(
                            question_type=q.question_type,
                            content=q.content,
                            answer=q.answer,
                            analysis=q.analysis,
                            difficulty=q.difficulty,
                            status="pending_review",
                            source_type="AI",
                            question_bank_id=question_bank_id,
                            generation_task_id=task_id,
                            content_hash=snap.content_hash,
                            hash_version=HASH_VERSION,
                            dedup_key=snap.content_hash,
                        )
                        db.add(question)
                        db.flush()
                        for opt in q.options:
                            db.add(QuestionOption(
                                question_id=question.id,
                                option_key=opt.option_key,
                                option_content=opt.option_content,
                                is_correct=opt.is_correct,
                                sort_order=ord(opt.option_key) - ord("A"),
                            ))
                        db.add(QuestionKnowledge(
                            question_id=question.id,
                            knowledge_id=kid,
                        ))
                        return question

                    question, verdict = dedup.guarded_save(
                        snap, _save,
                        reviewed_question_ids=dr.reviewed_question_ids,
                        task_context=task_context,
                        reviewed_content_hashes=dr.reviewed_content_hashes,
                    )
                    if question is None:
                        # 入库前二次校验拦截（并发竞争/唯一键冲突/语义不可用）→ 计数
                        reason = verdict.get("reason")
                        if reason == "exact_hash":
                            stats["exact_duplicate"] += 1
                        elif reason == "semantic_unavailable":
                            # 语义层不可用的安全失败：不是重复题，不入库也不冒充成功
                            stats["failed"] += 1
                            all_errors.append(f"知识点 {kid}: 语义去重不可用，候选题安全失败（不入库）")
                        elif reason == "semantic_concurrent_uncertain":
                            # LLM 对并发新竞争候选判不确定：不入库，进入补生成轮次
                            all_errors.append(
                                f"知识点 {kid}: 并发竞争候选复核不确定，不入库转补生成")
                        else:
                            stats["semantic_duplicate"] += 1
                        # 该候选不是有效保留题，不能成为后续新题的批次内对照
                        batch_context["accepted"] = [
                            s for s in batch_context["accepted"] if s is not snap
                        ]
                        db.commit()
                        continue

                    got += 1
                    stats["saved"] += 1
                    if dr.decision == "uncertain" or dr.needs_manual_review:
                        stats["uncertain"] += 1
                    if not verdict.get("indexed", True):
                        # §2.5 向量写失败：MySQL 已落库（事实源），索引 degraded 待修复
                        all_errors.append(f"知识点 {kid}: 题目已入库但向量索引写入失败，待修复")
                    db.commit()

            unfulfilled = max(0, want - got)
            if unfulfilled:
                all_errors.append(
                    f"知识点 {kid} 未补足 {unfulfilled} 题（已重试 {attempts} 轮，"
                    f"生成候选 {produced} 道，受重试上限约束）"
                )

        total_requested = sum(t["count"] for t in targets)
        exact_dup = stats["exact_duplicate"]
        semantic_dup = stats["semantic_duplicate"]
        saved_count = stats["saved"]
        task.generated_count = stats["generated"]
        task.exact_duplicate_count = exact_dup
        task.semantic_duplicate_count = semantic_dup
        task.uncertain_count = stats["uncertain"]
        task.duplicate_count = exact_dup + semantic_dup
        task.success_count = saved_count
        # 未补足数按计划口径统计（重试用尽仍缺的名额）
        task.unfulfilled_count = max(0, total_requested - saved_count)
        task.failed_count = stats["failed"]
        task.status = "success" if saved_count == total_requested else (
            "partial_success" if saved_count > 0 else "failed")
        task.completed_at = datetime.utcnow()
        if all_errors:
            task.error_summary = "; ".join(str(e) for e in all_errors[:5])
        db.commit()

    except Exception as e:
        logger.error(f"生成任务 {task_id} 失败: {e}", exc_info=True)
        try:
            task.status = "failed"
            task.error_summary = str(e)[:500]
            task.completed_at = datetime.utcnow()
            db.commit()
        except Exception:  # noqa: BLE001
            db.rollback()
    finally:
        db.close()


def run_import_in_background(task_id: int) -> None:
    """在后台线程中执行导入任务。

    使用独立的数据库 Session，不影响 API 请求的 Session。
    """
    def _worker():
        # 获取并发锁（初期限制并发为 1）
        if not _import_semaphore.acquire(blocking=False):
            logger.warning(f"已有导入任务在执行，任务 {task_id} 等待中")
            _import_semaphore.acquire()  # 阻塞等待

        try:
            # 创建独立的数据库 Session
            from app.core.database import SessionLocal
            from app.services.knowledge_import_service import KnowledgeImportService

            db = SessionLocal()
            try:
                logger.info(f"后台导入任务 {task_id} 开始执行")
                service = KnowledgeImportService(db)
                result = service.execute_import(task_id)
                logger.info(f"后台导入任务 {task_id} 完成: {result.get('status')}")
            except Exception as e:
                logger.error(f"后台导入任务 {task_id} 失败: {e}")
            finally:
                db.close()
        finally:
            _import_semaphore.release()

    _spawn(f"import-task-{task_id}", _worker)
    logger.info(f"导入任务 {task_id} 已提交后台执行")


def run_relations_retry_in_background(task_id: int) -> None:
    """在后台线程中执行关系重试任务。"""
    def _worker():
        try:
            from app.core.database import SessionLocal
            from app.services.knowledge_import_service import KnowledgeImportService

            db = SessionLocal()
            try:
                logger.info(f"后台关系重试任务 {task_id} 开始执行")
                service = KnowledgeImportService(db)
                result = service.retry_relations(task_id)
                logger.info(f"后台关系重试任务 {task_id} 完成: {result.get('status')}")
            except Exception as e:
                logger.error(f"后台关系重试任务 {task_id} 失败: {e}")
            finally:
                db.close()
        except Exception as e:
            logger.error(f"后台关系重试任务 {task_id} 启动失败: {e}")

    _spawn(f"relation-retry-{task_id}", _worker)
    logger.info(f"关系重试任务 {task_id} 已提交后台执行")
