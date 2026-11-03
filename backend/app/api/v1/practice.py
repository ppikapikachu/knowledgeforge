"""练习 API：组卷快照 / 练习会话 / 草稿标记 / 提交判分。

所有接口均以普通用户（AppUser）身份访问，owner 校验在服务层完成。
组卷与判分不调用 LLM/Agent；快照接口不返回未提交题目的正确答案与解析。
"""

from fastapi import APIRouter, Depends, Header, Query

from app.core.database import get_db
from app.core.exceptions import ResourceNotFoundException, ValidationException
from app.dependencies.auth import get_current_user
from app.models.app_user import AppUser
from app.models.question_bank import QuestionBank
from app.schemas.practice import (
    AssemblePaperRequest,
    DraftSaveRequest,
    MarkRequest,
    ProgressRequest,
    SubmitAnswerRequest,
)
from app.services.practice_service import PracticeService
from app.services.question_bank_stats import bank_knowledge_points, bank_question_stats
from app.utils.response import paginated_response, success_response

router = APIRouter(prefix="/practice", tags=["练习"])


def _svc(db=Depends(get_db)) -> PracticeService:
    return PracticeService(db)


@router.post("/papers/assemble")
def assemble_paper(
    request: AssemblePaperRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    current_user: AppUser = Depends(get_current_user),
    db=Depends(get_db),
):
    """组卷：只查询 published + 开放题库题目生成不可变快照。"""
    service = PracticeService(db)
    result = service.assemble_paper(
        user_id=current_user.id,
        question_bank_id=request.question_bank_id,
        title=request.title,
        question_type_counts=request.question_type_counts,
        difficulty_distribution=request.difficulty_distribution.model_dump(),
        total_count=request.total_count,
        knowledge_ids=request.knowledge_ids,
        allow_partial=request.allow_partial,
        idempotency_key=idempotency_key,
    )
    if result.get("error") == "insufficient_stock":
        raise ValidationException(
            f"题库库存不足：请求 {result['requested_count']} 题，"
            f"可用 {result['available_count']} 题，缺少 {result['missing_count']} 题；"
            f"可减少题目数量或调整题型/难度分布后重试",
            data=result,
        )
    return success_response(result)


@router.get("/papers")
def list_papers(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: AppUser = Depends(get_current_user),
    db=Depends(get_db),
):
    items, total = PracticeService(db).list_papers(current_user.id, page, page_size)
    return paginated_response(items, total, page, page_size)


@router.get("/papers/{paper_id}")
def get_paper(
    paper_id: int,
    current_user: AppUser = Depends(get_current_user),
    db=Depends(get_db),
):
    """试卷详情（含题目面，不含未提交题目的正确答案/解析）。"""
    return success_response(PracticeService(db).get_paper(current_user.id, paper_id))


@router.post("/papers/{paper_id}/sessions")
def create_session(
    paper_id: int,
    current_user: AppUser = Depends(get_current_user),
    db=Depends(get_db),
):
    """对已有试卷发起新的练习会话（再练）。"""
    return success_response(PracticeService(db).create_session(current_user.id, paper_id))


@router.patch("/papers/{paper_id}/archive")
def archive_paper(
    paper_id: int,
    current_user: AppUser = Depends(get_current_user),
    db=Depends(get_db),
):
    return success_response(PracticeService(db).archive_paper(current_user.id, paper_id))


@router.get("/sessions")
def list_sessions(
    status: str | None = Query(default=None, description="in_progress/completed/abandoned"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: AppUser = Depends(get_current_user),
    db=Depends(get_db),
):
    if status is not None and status not in ("in_progress", "completed", "abandoned"):
        raise ValidationException("status 仅支持 in_progress/completed/abandoned")
    items, total = PracticeService(db).list_sessions(current_user.id, status, page, page_size)
    return paginated_response(items, total, page, page_size)


@router.get("/sessions/{session_id}")
def get_session(
    session_id: int,
    current_user: AppUser = Depends(get_current_user),
    db=Depends(get_db),
):
    """会话详情：快照题目 + 草稿 + 进度；已提交题目附判分结果。"""
    return success_response(PracticeService(db).get_session_detail(current_user.id, session_id))


@router.post("/sessions/{session_id}/resume")
def resume_session(
    session_id: int,
    current_user: AppUser = Depends(get_current_user),
    db=Depends(get_db),
):
    return success_response(PracticeService(db).resume_session(current_user.id, session_id))


@router.post("/sessions/{session_id}/complete")
def complete_session(
    session_id: int,
    current_user: AppUser = Depends(get_current_user),
    db=Depends(get_db),
):
    """完成会话（幂等）；未答题保留 unanswered，不伪造。"""
    return success_response(PracticeService(db).complete_session(current_user.id, session_id))


@router.post("/sessions/{session_id}/abandon")
def abandon_session(
    session_id: int,
    current_user: AppUser = Depends(get_current_user),
    db=Depends(get_db),
):
    return success_response(PracticeService(db).abandon_session(current_user.id, session_id))


@router.get("/sessions/{session_id}/result")
def session_result(
    session_id: int,
    current_user: AppUser = Depends(get_current_user),
    db=Depends(get_db),
):
    """整卷答案与解析（owner 专属）。"""
    return success_response(PracticeService(db).session_result(current_user.id, session_id))


@router.get("/sessions/{session_id}/answers")
def session_answers(
    session_id: int,
    current_user: AppUser = Depends(get_current_user),
    db=Depends(get_db),
):
    return success_response(PracticeService(db).session_answers(current_user.id, session_id))


@router.put("/sessions/{session_id}/items/{paper_item_id}/draft")
def save_draft(
    session_id: int,
    paper_item_id: int,
    request: DraftSaveRequest,
    current_user: AppUser = Depends(get_current_user),
    db=Depends(get_db),
):
    return success_response(
        PracticeService(db).save_draft(
            current_user.id, session_id, paper_item_id, request.answer
        )
    )


@router.patch("/sessions/{session_id}/items/{paper_item_id}/mark")
def mark_item(
    session_id: int,
    paper_item_id: int,
    request: MarkRequest,
    current_user: AppUser = Depends(get_current_user),
    db=Depends(get_db),
):
    return success_response(
        PracticeService(db).mark_item(
            current_user.id, session_id, paper_item_id, request.is_marked
        )
    )


@router.patch("/sessions/{session_id}/progress")
def update_progress(
    session_id: int,
    request: ProgressRequest,
    current_user: AppUser = Depends(get_current_user),
    db=Depends(get_db),
):
    return success_response(
        PracticeService(db).update_progress(
            current_user.id, session_id, request.current_item_order
        )
    )


@router.post("/sessions/{session_id}/items/{paper_item_id}/submit")
def submit_answer(
    session_id: int,
    paper_item_id: int,
    request: SubmitAnswerRequest,
    current_user: AppUser = Depends(get_current_user),
    db=Depends(get_db),
):
    """提交答案并判分（以快照标准答案为准；响应含正确答案与解析）。"""
    return success_response(
        PracticeService(db).submit_answer(
            current_user.id,
            session_id,
            paper_item_id,
            request.answer,
            request.idempotency_key,
            request.time_spent_ms,
        )
    )


# ==================== 开放练习题库（用户端浏览） ====================


def _open_bank_payload(qb, stats_entry: dict) -> dict:
    """开放题库对外负载（§4.1）：库存统计 + 是否可组卷 + 不可组卷原因。"""
    published = (stats_entry or {}).get("available_question_count", 0)
    return {
        "id": qb.id,
        "code": qb.code,
        "name": qb.name,
        "description": qb.description or "",
        "available_question_count": published,
        "question_type_counts": (stats_entry or {}).get("question_type_counts", {}),
        "difficulty_counts": (stats_entry or {}).get("difficulty_counts", {}),
        "can_assemble": published > 0,
        "unavailable_reason": None if published > 0 else "暂无可练习题目",
    }


@router.get(
    "/question-banks",
    summary="开放练习题库列表",
    description=(
        "普通用户可见的练习题库列表（仅 is_available_for_practice=true）。"
        "空库存题库也返回但 can_assemble=false 并给出原因；库存统计一次聚合，无 N+1。"
    ),
)
def list_open_question_banks(
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页数量"),
    keyword: str = Query(default="", description="按名称模糊搜索"),
    current_user: AppUser = Depends(get_current_user),
    db=Depends(get_db),
):
    query = db.query(QuestionBank).filter(QuestionBank.is_available_for_practice.is_(True))
    if keyword.strip():
        query = query.filter(QuestionBank.name.like(f"%{keyword.strip()}%"))
    total = query.count()
    rows = query.order_by(QuestionBank.id.asc()).offset((page - 1) * page_size).limit(page_size).all()
    stats_map = bank_question_stats(db, [qb.id for qb in rows])
    items = [_open_bank_payload(qb, stats_map.get(qb.id)) for qb in rows]
    return paginated_response(items=items, total=total, page=page, page_size=page_size)


@router.get(
    "/question-banks/{qb_id}",
    summary="开放练习题库详情",
    description="题库详情；未开放与不存在返回同一资源错误，不泄露私有题库存在性。",
)
def get_open_question_bank(
    qb_id: int,
    current_user: AppUser = Depends(get_current_user),
    db=Depends(get_db),
):
    qb = (
        db.query(QuestionBank)
        .filter(QuestionBank.id == qb_id, QuestionBank.is_available_for_practice.is_(True))
        .first()
    )
    if not qb:
        raise ResourceNotFoundException("题库", qb_id)
    return success_response(_open_bank_payload(qb, bank_question_stats(db, [qb_id]).get(qb_id)))


@router.get(
    "/question-banks/{qb_id}/knowledge-points",
    summary="题库可练习知识点",
    description=(
        "仅返回该题库内存在已发布题目的知识点（真实 QuestionKnowledge 关联，禁止名称匹配），"
        "按可用题量倒序；用于组卷前筛选 knowledge_ids。"
    ),
)
def get_open_question_bank_knowledge_points(
    qb_id: int,
    current_user: AppUser = Depends(get_current_user),
    db=Depends(get_db),
):
    qb = (
        db.query(QuestionBank)
        .filter(QuestionBank.id == qb_id, QuestionBank.is_available_for_practice.is_(True))
        .first()
    )
    if not qb:
        raise ResourceNotFoundException("题库", qb_id)
    return success_response({
        "question_bank_id": qb_id,
        "knowledge_points": bank_knowledge_points(db, qb_id),
    })
