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

    thread = threading.Thread(
        target=_worker,
        name=f"import-task-{task_id}",
        daemon=True,
    )
    thread.start()
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

    thread = threading.Thread(
        target=_worker,
        name=f"relation-retry-{task_id}",
        daemon=True,
    )
    thread.start()
    logger.info(f"关系重试任务 {task_id} 已提交后台执行")
