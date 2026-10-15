"""题目生成任务 API 路由。

支持管理员创建生成任务、查看任务列表和详情、审核题目。
任务在后台线程执行，API 立即返回。
"""

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_admin
from app.models.admin import AdminUser
from app.models.question import Question
from app.models.question_generation_task import QuestionGenerationTask
from app.models.question_knowledge import QuestionKnowledge
from app.models.question_option import QuestionOption
from app.schemas.common import ApiResponse
from app.utils.response import paginated_response

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/question-generation", tags=["题目生成"])


@router.post(
    "/tasks",
    summary="创建题目生成任务",
    description=(
        "创建 AI 题目生成任务，后台异步执行。"
        "立即返回任务 ID，通过任务详情查询进度。"
        "生成的题目状态为 pending_review，需管理员审核后才能使用。"
    ),
)
async def create_generation_task(
    request: dict,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
) -> ApiResponse:
    """创建题目生成任务。"""
    knowledge_id = request.get("knowledge_id")
    question_bank_id = request.get("question_bank_id")
    question_type = request.get("question_type", "SINGLE_CHOICE")
    difficulty = request.get("difficulty", 2)
    count = request.get("count", 5)

    # 参数校验
    if not knowledge_id or not question_bank_id:
        return ApiResponse(code=40001, message="knowledge_id 和 question_bank_id 必填", data=None)
    if count < 1 or count > 50:
        return ApiResponse(code=40001, message="count 范围 1~50", data=None)
    if question_type not in ("SINGLE_CHOICE", "MULTIPLE_CHOICE", "TRUE_FALSE", "SHORT_ANSWER"):
        return ApiResponse(code=40001, message="无效的题型", data=None)
    if difficulty not in (1, 2, 3):
        return ApiResponse(code=40001, message="难度必须是 1/2/3", data=None)

    # 校验题库和知识点存在
    from app.models.question_bank import QuestionBank
    from app.models.knowledge import Knowledge

    bank = db.query(QuestionBank).filter(QuestionBank.id == question_bank_id).first()
    if not bank:
        return ApiResponse(code=40401, message=f"题库 {question_bank_id} 不存在", data=None)

    knowledge = db.query(Knowledge).filter(Knowledge.id == knowledge_id).first()
    if not knowledge:
        return ApiResponse(code=40401, message=f"知识点 {knowledge_id} 不存在", data=None)

    # 创建任务记录
    task = QuestionGenerationTask(
        created_by=current_admin.id,
        request_config=request,
        status="pending",
        total_count=count,
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    # 后台执行
    from app.services.background_runner import run_generation_in_background
    run_generation_in_background(task.id, request)

    return ApiResponse(data={
        "task_id": task.id,
        "status": task.status,
        "message": "任务已创建，后台执行中",
    })


@router.get(
    "/tasks",
    summary="获取生成任务列表",
    description="分页获取生成任务列表，支持状态筛选。",
)
def get_generation_tasks(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status: str = Query(default=None),
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    """获取生成任务列表。"""
    query = db.query(QuestionGenerationTask)
    if status:
        query = query.filter(QuestionGenerationTask.status == status)

    total = query.count()
    items = query.order_by(QuestionGenerationTask.id.desc()).offset(
        (page - 1) * page_size
    ).limit(page_size).all()

    item_data = []
    for t in items:
        item_data.append({
            "id": t.id,
            "status": t.status,
            "total_count": t.total_count,
            "success_count": t.success_count,
            "duplicate_count": t.duplicate_count,
            "failed_count": t.failed_count,
            "request_config": t.request_config,
            "error_summary": t.error_summary,
            "started_at": t.started_at.isoformat() if t.started_at else None,
            "completed_at": t.completed_at.isoformat() if t.completed_at else None,
            "created_at": t.created_at.isoformat() if t.created_at else None,
        })

    return paginated_response(items=item_data, total=total, page=page, page_size=page_size)


@router.get(
    "/tasks/{task_id}",
    summary="获取生成任务详情",
    description="查看任务参数、进度、结果和失败原因。",
)
def get_generation_task_detail(
    task_id: int,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
) -> ApiResponse:
    """获取生成任务详情。"""
    task = db.query(QuestionGenerationTask).filter(
        QuestionGenerationTask.id == task_id
    ).first()
    if not task:
        return ApiResponse(code=40401, message="任务不存在", data=None)

    # 获取关联题目
    questions = db.query(Question).filter(
        Question.generation_task_id == task_id
    ).all()

    question_list = []
    for q in questions:
        options = db.query(QuestionOption).filter(
            QuestionOption.question_id == q.id
        ).all()
        knowledge_ids = [
            qk.knowledge_id
            for qk in db.query(QuestionKnowledge).filter(
                QuestionKnowledge.question_id == q.id
            ).all()
        ]
        question_list.append({
            "id": q.id,
            "question_type": q.question_type,
            "content": q.content[:100] + "..." if len(q.content) > 100 else q.content,
            "difficulty": q.difficulty,
            "status": q.status,
            "knowledge_ids": knowledge_ids,
            "option_count": len(options),
        })

    # 进度
    processed = task.success_count + task.failed_count + task.duplicate_count
    progress = int(processed / task.total_count * 100) if task.total_count > 0 else 0

    return ApiResponse(data={
        "task_id": task.id,
        "created_by": task.created_by,
        "status": task.status,
        "request_config": task.request_config,
        "total_count": task.total_count,
        "success_count": task.success_count,
        "duplicate_count": task.duplicate_count,
        "failed_count": task.failed_count,
        "progress": progress,
        "error_summary": task.error_summary,
        "started_at": task.started_at.isoformat() if task.started_at else None,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "questions": question_list,
    })


@router.post(
    "/questions/{question_id}/review",
    summary="审核题目",
    description="发布或驳回待审核题目。驳回时建议记录原因。",
)
async def review_question(
    question_id: int,
    request: dict,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
) -> ApiResponse:
    """审核题目（发布/驳回）。"""
    question = db.query(Question).filter(Question.id == question_id).first()
    if not question:
        return ApiResponse(code=40401, message="题目不存在", data=None)

    action = request.get("action")  # publish / reject
    reason = request.get("reason", "")

    if action == "publish":
        if question.status == "published":
            return ApiResponse(code=40001, message="题目已是发布状态", data=None)
        question.status = "published"
    elif action == "reject":
        if question.status == "published":
            return ApiResponse(code=40001, message="已发布题目不能驳回，请使用下架", data=None)
        question.status = "rejected"
        question.analysis = reason or question.analysis
    else:
        return ApiResponse(code=40001, message="action 必须是 publish 或 reject", data=None)

    db.commit()

    return ApiResponse(data={
        "question_id": question.id,
        "status": question.status,
        "reviewed_by": current_admin.id,
        "reviewed_at": datetime.utcnow().isoformat(),
    })
