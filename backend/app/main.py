"""FastAPI application entry point."""

import logging
import os
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_v1_router
from app.core.config import settings
from app.middleware.exception_handler import register_exception_handlers
from app.middleware.request_id import RequestIdMiddleware

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
    force=True,
)

# Suppress noisy loggers
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
logging.getLogger("uvicorn.access").setLevel(logging.INFO)

logger = logging.getLogger(__name__)


def _detect_worker_count() -> int:
    """检测部署 worker 数（uvicorn --workers / WEB_CONCURRENCY / UVICORN_WORKERS）。"""
    for source in (os.environ.get("WEB_CONCURRENCY"), os.environ.get("UVICORN_WORKERS")):
        try:
            if source and int(source) > 1:
                return int(source)
        except (TypeError, ValueError):
            pass
    for i, arg in enumerate(sys.argv):
        if arg in ("--workers", "-w") and i + 1 < len(sys.argv):
            try:
                return max(1, int(sys.argv[i + 1]))
            except ValueError:
                pass
        if arg.startswith("--workers="):
            try:
                return max(1, int(arg.split("=", 1)[1]))
            except ValueError:
                pass
    return 1


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """启动/关闭钩子（题目向量索引生命周期，§2.2/§2.6）。

    - 强制单 worker/单进程：题目向量索引为进程内存态且写入锁为进程级，
      多进程部署无法保证语义去重一致性——启动配置阻止多 worker；
    - 启动期同步构建题目向量索引（幂等），就绪状态机记录
      initializing/ready/degraded；构建完成前不对外提供服务；
    - 索引构建失败 → degraded：生成任务会被安全拒绝，绝不静默跳过语义去重。
    """
    worker_count = _detect_worker_count()
    if worker_count > 1:
        raise RuntimeError(
            f"检测到多 worker 配置（workers={worker_count}）：题目去重向量索引为进程内存态，"
            f"多进程无法保证语义去重一致性。请以单 worker/单进程启动（uvicorn --workers 1），"
            f"或引入共享向量存储后另行改造。"
        )

    from app.core.database import SessionLocal
    from app.services.question_dedup_service import initialize_question_index

    db = SessionLocal()
    try:
        readiness = initialize_question_index(db)
        logger.info("题目向量索引初始化完成: %s", readiness)

        # 批量审核批次重启恢复（补充开发文档 §8）：queued/running 批次的
        # 卡死项标记中断失败并释放题目认领，不静默挂起、不无限重试
        from app.services.question_review_batch_service import QuestionReviewBatchService

        recovery = QuestionReviewBatchService(db).recover_incomplete_batches()
        if recovery.get("recovered_batches"):
            logger.warning("批量审核批次重启恢复: %s", recovery)
    finally:
        db.close()

    yield
    # 关闭：向量索引为内存态，无持久化需要清理


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="AI面试题库管理系统",
        description="AI驱动的面试题库和知识库管理系统 API V1.0",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Request ID middleware
    app.add_middleware(RequestIdMiddleware)

    # Exception handlers
    register_exception_handlers(app)

    # Include API routers
    app.include_router(api_v1_router)

    @app.get("/", tags=["健康检查"])
    def root():
        """Health check endpoint."""
        return {"status": "ok", "app": settings.APP_NAME, "version": "1.0.0"}

    @app.get("/health", tags=["健康检查"])
    def health():
        """Health check endpoint."""
        return {"status": "healthy"}

    return app


app = create_app()
