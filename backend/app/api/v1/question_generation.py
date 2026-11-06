"""题目生成任务 API 路由。

支持管理员创建生成任务、查看任务列表和详情、审核题目。
任务在后台线程执行，API 立即返回。
"""

import logging
from datetime import datetime

from fastapi import APIRouter, Body, Depends, Path, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_admin
from app.models.admin import AdminUser
from app.models.question import Question
from app.models.question_generation_task import QuestionGenerationTask
from app.models.question_knowledge import QuestionKnowledge
from app.models.question_option import QuestionOption
from app.schemas.common import ApiErrorResponse, ApiResponse, PaginatedData
from app.schemas.question import (
    GenerationTaskDetailResponse,
    GenerationTaskListItem,
    QuestionManualReviewResponse,
)
from app.schemas.question_demand import TaskCreateResponse
from app.utils.response import paginated_response

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/question-generation", tags=["题目生成"])

# 错误响应文档（OpenAPI responses；仅文档用途，不改变运行时 HTTP 状态码）。
# 运行时业务异常（40000/40001/40101/40301/40401/40901 等）统一经全局异常处理器以
# HTTP 400 信封返回；请求体校验失败为 HTTP 422（业务码 42201）；系统内部错误为
# HTTP 500（业务码 50000）。
ERROR_RESPONSES = {
    400: {
        "model": ApiErrorResponse,
        "description": "业务错误（HTTP 400，envelope code 区分）：40001 参数校验（question_bank_id 必填/count 范围 1~500/题型或难度非法/manual 模式缺 knowledge_id/去重服务未就绪/AI 审核未启用/无候选知识点/分配不足/出题策略未启用）/ 40401 不存在（题库/知识点不存在）/ 40101 未认证（管理员令牌无效/过期/管理员不存在/已禁用）",
    },
    403: {"model": ApiErrorResponse, "description": "未提供或非法 Authorization 请求头（HTTP 403）"},
    422: {"model": ApiErrorResponse, "description": "请求参数格式校验失败（HTTP 422，code 42201）"},
    500: {"model": ApiErrorResponse, "description": "系统内部错误（HTTP 500，code 50000）"},
}


@router.post(
    "/tasks",
    response_model=ApiResponse[TaskCreateResponse],
    responses=ERROR_RESPONSES,
    summary="创建题目生成任务",
    description=(
        "用途：创建 AI 题目生成任务，后台线程异步执行（立即返回任务，不阻塞请求）。\n"
        "调用时机：管理端\"智能出题\"页提交生成任务时调用。\n"
        "请求体（JSON 对象）：\n"
        "- question_bank_id: 目标题库ID，必填且题库须存在\n"
        "- question_type: 题型(SINGLE_CHOICE|MULTIPLE_CHOICE|TRUE_FALSE|SHORT_ANSWER)\n"
        "- difficulty: 难度(1-3)\n"
        "- count: 生成数量，必填为正整数\n"
        "- mode: manual 指定知识点 | auto 智能分配（默认 manual）\n"
        "- knowledge_id: manual 模式必填，知识点ID\n"
        "- enable_ai_review: 是否启用任务级 AI 质量审核（默认 false；总开关 QUESTION_AI_REVIEW_ENABLED=false 时传 true 会报 40001）\n"
        "业务约束：题目去重服务未就绪（initializing/degraded）时安全失败明确报错；生成过程带去重（重复候选不入库）与有限补生成。\n"
        "返回 data 结构：task_id 任务ID / status 任务状态（创建时为 pending，后台执行中依次变为 running→success|partial_success|failed）/"
        "allocation_mode 分配方式(manual|auto) / requested_count 请求生成数 / allocated_count 已分配生成数 / "
        "unallocated_count 未分配数 / message 提示。\n"
        "权限：仅管理员（JWT）。\n"
        "幂等性：非幂等，每次调用创建新任务。\n"
        "写库：是（任务记录；题目由后台线程分批写入）。"
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

    # §2.4：题目去重服务未就绪时新任务不得进入正式生成流程（安全失败，明确报错）
    from app.core.config import settings as app_settings
    from agent.common.config import agent_settings
    from app.services.question_dedup_service import get_dedup_readiness
    if agent_settings.QUESTION_DEDUP_ENABLED:
        readiness = get_dedup_readiness()
        if readiness.get("status") in ("initializing", "degraded"):
            raise ValidationException(
                f"题目去重服务未就绪（status={readiness.get('status')}），"
                f"当前不允许创建生成任务；请等待索引恢复后重试"
            )

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

    # ---- AI 质量审核开关（§2.2）：默认 false；请求 true 但总开关关 → 明确业务错误，不静默降级 ----
    enable_ai_review = bool(request.get("enable_ai_review", False))
    if enable_ai_review and not agent_settings.QUESTION_AI_REVIEW_ENABLED:
        raise ValidationException(
            "AI 质量审核功能当前未启用（QUESTION_AI_REVIEW_ENABLED=false），"
            "本次任务无法开启 AI 审核；请启用服务端总开关后重新发起任务"
        )

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
            enable_ai_review=enable_ai_review,
            ai_review_status="queued" if enable_ai_review else "not_requested",
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
            enable_ai_review=enable_ai_review,
            ai_review_status="queued" if enable_ai_review else "not_requested",
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
    response_model=ApiResponse[PaginatedData[GenerationTaskListItem]],
    responses=ERROR_RESPONSES,
    summary="获取生成任务列表",
    description=(
        "用途：分页查询题目生成任务，供任务列表页使用。\n"
        "调用时机：进入生成任务列表页或筛选状态时调用。\n"
        "返回 data 结构（分页信封 {items, page, page_size, total}）：items 每项含 "
        "id 任务ID / status 状态(pending|running|success|partial_success|failed) / "
        "allocation_mode 分配方式(manual|auto) / requested_count 请求生成数 / allocated_count 已分配数 / unallocated_count 未分配数 / "
        "total_count 计划数 / success_count 成功数 / "
        "duplicate_count 去重跳过数 / failed_count 失败数 / generated_count 生成候选数 / "
        "exact_duplicate_count 精确重复数 / semantic_duplicate_count 语义重复数 / uncertain_count 待人工复核数 / "
        "unfulfilled_count 未补足数 / enable_ai_review 是否启用AI审核 / ai_review_status AI审核状态 / "
        "8 项 AI 审核计数（ai_review_total_count/ai_review_processed_count/ai_auto_approved_count/ai_auto_rejected_count/"
        "ai_manual_review_count/ai_review_failed_count/ai_review_skipped_count/ai_review_pending_count）/ "
        "request_config 请求配置快照 / error_summary 错误摘要 / started_at/completed_at/created_at。\n"
        "权限：仅管理员（JWT）。\n"
        "幂等性：只读查询，可安全重复调用。\n"
        "写库：否。"
    ),
)
def get_generation_tasks(
    page: int = Query(default=1, ge=1, description="页码参数，从 1 开始递增，默认第 1 页"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页条数，取值范围 1-100，默认 20"),
    status: str = Query(
        default=None,
        description="任务状态筛选：pending 待执行 | running 执行中 | success 成功 | partial_success 部分成功 | failed 失败；不传为全部",
    ),
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
            "generated_count": t.generated_count,
            "exact_duplicate_count": t.exact_duplicate_count,
            "semantic_duplicate_count": t.semantic_duplicate_count,
            "uncertain_count": t.uncertain_count,
            "unfulfilled_count": t.unfulfilled_count,
            "failed_count": t.failed_count,
            "enable_ai_review": bool(t.enable_ai_review),
            "ai_review_status": t.ai_review_status,
            "ai_review_total_count": t.ai_review_total_count,
            "ai_review_processed_count": t.ai_review_processed_count,
            "ai_auto_approved_count": t.ai_auto_approved_count,
            "ai_auto_rejected_count": t.ai_auto_rejected_count,
            "ai_manual_review_count": t.ai_manual_review_count,
            "ai_review_failed_count": t.ai_review_failed_count,
            "ai_review_skipped_count": t.ai_review_skipped_count,
            "ai_review_pending_count": t.ai_review_pending_count,
            "request_config": t.request_config,
            "error_summary": t.error_summary,
            "started_at": t.started_at.isoformat() if t.started_at else None,
            "completed_at": t.completed_at.isoformat() if t.completed_at else None,
            "created_at": t.created_at.isoformat() if t.created_at else None,
        })

    return paginated_response(items=item_data, total=total, page=page, page_size=page_size)


@router.get(
    "/tasks/{task_id}",
    response_model=ApiResponse[GenerationTaskDetailResponse],
    responses={**ERROR_RESPONSES, 200: {"description": "成功（code=0）。任务不存在时 HTTP 仍为 200，用 envelope code（40401 任务不存在）标识，前端须检查 code。"}},
    summary="获取生成任务详情",
    description=(
        "用途：查看单个生成任务的参数、实时进度、去重/审核统计与失败原因。\n"
        "调用时机：任务列表点进详情页、或轮询任务进度时调用。\n"
        "路径参数：task_id 任务ID。\n"
        "返回 data 结构：task_id/created_by 创建管理员ID/allocation_mode 分配方式/status/"
        "requested_count/allocated_count/unallocated_count/request_config 请求配置快照/"
        "total_count 计划数/success_count 已入库数/duplicate_count 去重跳过数（=exact+semantic）/failed_count 失败数/"
        "generated_count 生成候选数/exact_duplicate_count 精确重复数/semantic_duplicate_count 语义重复数/"
        "uncertain_count 待人工复核数/unfulfilled_count 未补足数/error_summary 错误摘要/progress 进度百分比(0-100)/"
        "allocation_plan 分配计划快照/enable_ai_review 是否启用AI审核/"
        "ai_review_status AI审核状态(not_requested|queued|running|completed|partial|failed)+8 项审核计数/"
        "dedup_review_status 本任务去重复核状态(manual_review_required|deduplicated|clean)/dedup_manual_review_count 待人工复核记录数/"
        "questions 生成题目摘要列表（id/question_type/content 截断100字/difficulty/status/knowledge_ids/option_count）/"
        "started_at/completed_at/created_at。\n"
        "权限：仅管理员（JWT）。\n"
        "幂等性：只读查询，可安全重复调用。\n"
        "写库：否。"
    ),
)
def get_generation_task_detail(
    task_id: int = Path(..., description="生成任务ID，必须为已存在的任务主键，不存在时返回业务错误 40401"),
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

    # 进度（去重/重试会产生额外处理量，进度封顶 100）
    processed = task.success_count + task.failed_count + task.duplicate_count
    progress = int(processed / task.total_count * 100) if task.total_count > 0 else 0
    progress = min(100, progress)

    # 去重复核状态（uncertain 可追踪，§6）：需要人工裁决的记录数
    from app.models.question_dedup_record import QuestionDedupRecord as QDR
    manual_review_rows = (
        db.query(QDR.id)
        .filter(QDR.task_id == task.id, QDR.needs_manual_review == 1)
        .count()
    )
    dedup_review_status = (
        "manual_review_required" if manual_review_rows > 0
        else "deduplicated" if task.duplicate_count > 0
        else "clean"
    )

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
        "generated_count": task.generated_count,
        "exact_duplicate_count": task.exact_duplicate_count,
        "semantic_duplicate_count": task.semantic_duplicate_count,
        "uncertain_count": task.uncertain_count,
        "unfulfilled_count": task.unfulfilled_count,
        "failed_count": task.failed_count,
        "dedup_review_status": dedup_review_status,
        "dedup_manual_review_count": manual_review_rows,
        "enable_ai_review": bool(task.enable_ai_review),
        "ai_review_status": task.ai_review_status,
        "ai_review_total_count": task.ai_review_total_count,
        "ai_review_processed_count": task.ai_review_processed_count,
        "ai_auto_approved_count": task.ai_auto_approved_count,
        "ai_auto_rejected_count": task.ai_auto_rejected_count,
        "ai_manual_review_count": task.ai_manual_review_count,
        "ai_review_failed_count": task.ai_review_failed_count,
        "ai_review_skipped_count": task.ai_review_skipped_count,
        "ai_review_pending_count": task.ai_review_pending_count,
        "progress": progress,
        "error_summary": task.error_summary,
        "started_at": task.started_at.isoformat() if task.started_at else None,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "questions": question_list,
    })


@router.post(
    "/questions/{question_id}/review",
    response_model=ApiResponse[QuestionManualReviewResponse],
    responses={**ERROR_RESPONSES, 200: {"description": "成功（code=0）。业务错误时 HTTP 仍为 200，用 envelope code（如 40401 题目不存在/40001 状态不允许或 action 非法）标识，前端须检查 code。"}},
    summary="审核题目",
    description=(
        "用途：人工审核题目——发布（status→published）或驳回（status→rejected，软驳回不删数据）。\n"
        "调用时机：题目审核页点击\"发布/驳回\"时调用。\n"
        "路径参数：question_id 题目ID。\n"
        "请求体（JSON 对象）：action 动作，publish 发布 | reject 驳回；reason 驳回原因（驳回时建议填写）。\n"
        "业务行为：发布/驳回同步去重索引状态（dedup_key 登记/释放）；题目不存在返回 code=40401。\n"
        "返回 data 结构：question_id 题目ID / status 审核后的题目状态(published|rejected) / "
        "reviewed_by 审核管理员ID / reviewed_at 审核时间。\n"
        "权限：仅管理员（JWT）。\n"
        "幂等性：条件幂等——同一动作重复提交结果一致（状态条件更新，已发布/已驳回再操作为最终状态覆盖）。\n"
        "写库：是（题目状态+去重索引状态）。"
    ),
)
async def review_question(
    question_id: int = Path(..., description="题目ID，必须为已存在的题目主键，不存在时返回业务错误 40401"),
    request: dict = Body(..., description="审核动作：action= publish 发布 | reject 驳回；reason 驳回原因（驳回时建议填写）"),
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

    # 状态流转同步去重状态：发布=登记 dedup_key+向量索引；驳回=解除（§3.3/§8）
    from app.services.question_dedup_service import sync_question_dedup_state
    sync_question_dedup_state(db, question)

    db.commit()

    return ApiResponse(data={
        "question_id": question.id,
        "status": question.status,
        "reviewed_by": current_admin.id,
        "reviewed_at": datetime.utcnow().isoformat(),
    })
