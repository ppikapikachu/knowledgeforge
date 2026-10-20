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
        "支持 manual（指定知识点）和 auto（智能分配）两种模式。"
        "立即返回任务 ID，通过任务详情查询进度。"
    ),
)
async def create_generation_task(
    request: dict,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
) -> ApiResponse:
    """创建题目生成任务。"""
    from app.core.exceptions import ValidationException, ResourceNotFoundException
    from app.models.question_bank import QuestionBank
    from app.models.knowledge import Knowledge

    allocation_mode = request.get("allocation_mode")
    knowledge_id = request.get("knowledge_id")
    question_bank_id = request.get("question_bank_id")
    question_type = request.get("question_type", "SINGLE_CHOICE")
    difficulty = request.get("difficulty", 2)
    count = request.get("count", 5)
    allow_partial = request.get("allow_partial", False)

    # 兼容旧请求：未传 allocation_mode 但传了 knowledge_id → manual
    if not allocation_mode:
        allocation_mode = "manual" if knowledge_id else "auto"

    # 基本校验
    if not question_bank_id:
        raise ValidationException("question_bank_id 必填")
    if count < 1 or count > 500:
        raise ValidationException("count 范围 1~500")
    if question_type not in ("SINGLE_CHOICE", "MULTIPLE_CHOICE", "TRUE_FALSE", "SHORT_ANSWER"):
        raise ValidationException("无效的题型")
    if difficulty not in (1, 2, 3):
        raise ValidationException("难度必须是 1/2/3")

    bank = db.query(QuestionBank).filter(QuestionBank.id == question_bank_id).first()
    if not bank:
        raise ResourceNotFoundException(f"题库 {question_bank_id} 不存在")

    if allocation_mode == "manual":
        if not knowledge_id:
            raise ValidationException("manual 模式必须提供 knowledge_id")
        knowledge = db.query(Knowledge).filter(Knowledge.id == knowledge_id).first()
        if not knowledge:
            raise ResourceNotFoundException(f"知识点 {knowledge_id} 不存在")

        # 创建任务
        task = QuestionGenerationTask(
            created_by=current_admin.id,
            request_config=request,
            status="pending",
            total_count=count,
            allocation_mode="manual",
            allocation_plan={
                "allocation_mode": "manual",
                "requested_count": count,
                "allocated_count": count,
                "unallocated_count": 0,
                "policy_version": None,
                "items": [{
                    "knowledge_id": knowledge.id,
                    "knowledge_name": knowledge.name,
                    "knowledge_base_id": knowledge.knowledge_base_id,
                    "knowledge_base_name": "",
                    "importance_level": knowledge.importance_level,
                    "importance_label": "",
                    "planned_count": count,
                }],
            },
            requested_count=count,
            allocated_count=count,
            unallocated_count=0,
        )
        db.add(task)
        db.commit()
        db.refresh(task)

        from app.services.background_runner import run_generation_in_background
        run_generation_in_background(task.id, request)

        return ApiResponse(data={
            "task_id": task.id,
            "status": task.status,
            "allocation_mode": "manual",
            "requested_count": count,
            "allocated_count": count,
            "unallocated_count": 0,
            "message": "任务已创建，后台执行中",
        })

    else:  # auto
        from app.services.policy_service import PolicyService
        from app.services.knowledge_demand_service import KnowledgePointDemandService

        policy_svc = PolicyService(db)
        effective = policy_svc.get_effective_policy(question_bank_id)
        policy = effective["policy"]

        if not policy.get("is_enabled", True):
            raise ValidationException("QUESTION_DEMAND_POLICY_DISABLED: 出题策略未启用，无法使用智能分配")

        demand_svc = KnowledgePointDemandService(db)
        evaluations = demand_svc.evaluate(question_bank_id, question_type, difficulty, policy)
        allocations, allocatable, unallocated, warnings = demand_svc.allocate(evaluations, count, policy)

        if allocatable == 0:
            raise ValidationException("NO_ELIGIBLE_KNOWLEDGE_POINTS: 无候选知识点")

        if allocatable < count and not allow_partial:
            raise ValidationException(
                f"ALLOCATION_INSUFFICIENT: 最多可分配 {allocatable} 道，少于目标 {count} 道。"
                f"请确认后以 allow_partial=true 重新提交。"
            )

        # 构建分配计划
        kb_names = demand_svc._get_knowledge_base_names(
            list(set(a["knowledge_base_id"] for a in allocations))
        )
        plan_items = []
        for a in allocations:
            plan_items.append({
                "knowledge_id": a["knowledge_id"],
                "knowledge_name": a["knowledge_name"],
                "knowledge_base_id": a["knowledge_base_id"],
                "knowledge_base_name": kb_names.get(a["knowledge_base_id"], ""),
                "importance_level": a["importance_level"],
                "importance_label": a["importance_label"],
                "planned_count": a["allocated_count"],
            })

        allocated_total = sum(a["allocated_count"] for a in allocations)
        allocation_plan = {
            "allocation_mode": "auto",
            "requested_count": count,
            "allocated_count": allocated_total,
            "unallocated_count": count - allocated_total,
            "policy_version": policy.get("version"),
            "items": plan_items,
        }

        task = QuestionGenerationTask(
            created_by=current_admin.id,
            request_config=request,
            status="pending",
            total_count=allocated_total,
            allocation_mode="auto",
            allocation_plan=allocation_plan,
            policy_snapshot=policy,
            requested_count=count,
            allocated_count=allocated_total,
            unallocated_count=count - allocated_total,
        )
        db.add(task)
        db.commit()
        db.refresh(task)

        # 构建后台执行配置（auto 模式按分配计划逐知识点生成）
        bg_config = {
            "allocation_mode": "auto",
            "allocation_plan": allocation_plan,
            "question_bank_id": question_bank_id,
            "question_type": question_type,
            "difficulty": difficulty,
            "count": allocated_total,
        }
        from app.services.background_runner import run_generation_in_background
        run_generation_in_background(task.id, bg_config)

        return ApiResponse(data={
            "task_id": task.id,
            "status": task.status,
            "allocation_mode": "auto",
            "requested_count": count,
            "allocated_count": allocated_total,
            "unallocated_count": count - allocated_total,
            "message": f"任务已创建，已按智能分配方案创建 {allocated_total} 道题目生成计划",
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
            "allocation_mode": t.allocation_mode,
            "requested_count": t.requested_count,
            "allocated_count": t.allocated_count,
            "unallocated_count": t.unallocated_count,
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
        "allocation_mode": task.allocation_mode,
        "allocation_plan": task.allocation_plan,
        "requested_count": task.requested_count,
        "allocated_count": task.allocated_count,
        "unallocated_count": task.unallocated_count,
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
