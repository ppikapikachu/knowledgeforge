"""Question API router."""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_admin
from app.models.admin import AdminUser
from app.schemas.common import ApiResponse
from app.schemas.question import (
    OptionResponse,
    QuestionCreate,
    QuestionResponse,
    QuestionUpdate,
)
from app.services.question_service import QuestionService
from app.utils.response import paginated_response, success_response

router = APIRouter(prefix="/questions", tags=["题目管理"])


def _build_question_response(question) -> dict:
    """Build question response with options and knowledge IDs."""
    options = [
        OptionResponse.model_validate(opt).model_dump(mode="json")
        for opt in (question.options or [])
    ]
    knowledge_ids = [
        qk.knowledge_id for qk in (question.knowledge_associations or [])
    ]

    resp = QuestionResponse.model_validate(question)
    resp_dict = resp.model_dump(mode="json")
    resp_dict["options"] = options
    resp_dict["knowledge_ids"] = knowledge_ids
    return resp_dict


@router.get(
    "",
    summary="获取题目列表",
    description="分页获取题目列表，支持多种筛选条件。",
)
def get_question_list(
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页数量"),
    question_type: Optional[str] = Query(default=None, description="题型"),
    difficulty: Optional[int] = Query(default=None, ge=1, le=3, description="难度"),
    status: Optional[str] = Query(default=None, description="状态"),
    knowledge_id: Optional[int] = Query(default=None, description="知识点ID"),
    question_bank_id: Optional[int] = Query(default=None, description="按题库筛选"),
    source_type: Optional[str] = Query(default=None, description="来源"),
    keyword: Optional[str] = Query(default=None, description="关键词"),
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    """Get question list with pagination and filters."""
    service = QuestionService(db)
    items, total = service.get_question_list(
        page=page,
        page_size=page_size,
        question_type=question_type,
        difficulty=difficulty,
        status=status,
        knowledge_id=knowledge_id,
        question_bank_id=question_bank_id,
        source_type=source_type,
        keyword=keyword,
    )
    item_data = [_build_question_response(q) for q in items]
    return paginated_response(
        items=item_data,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{question_id}",
    response_model=ApiResponse[QuestionResponse],
    summary="获取题目详情",
    description="根据ID获取题目详细信息，包含选项和关联知识点。",
)
def get_question(
    question_id: int,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
) -> ApiResponse:
    """Get question by ID."""
    service = QuestionService(db)
    question = service.get_question(question_id)
    data = _build_question_response(question)

    # 去重复核状态（uncertain 可追踪，§6）：查最近一条去重判定审计记录
    from app.models.question_dedup_record import QuestionDedupRecord as QDR
    record = (
        db.query(QDR)
        .filter(
            (QDR.matched_question_id == question.id)
            | (QDR.new_content_hash == (question.content_hash or ""))
        )
        .order_by(QDR.id.desc())
        .first()
    )
    if record is not None:
        data["dedup_review_status"] = (
            "uncertain" if record.decision == "uncertain"
            else "duplicate" if record.decision == "duplicate"
            else "distinct"
        )
        # 人工复核结论（不覆盖自动判定；uncertain 不被映射成 duplicate，
        # 人工结论以独立字段 + effective_decision 提供，§2.5/§3.3）
        data["dedup_manual_resolution"] = record.manual_resolution
        data["dedup_effective_decision"] = record.manual_resolution or record.decision
    else:
        data["dedup_review_status"] = "none"
        data["dedup_manual_resolution"] = None
        data["dedup_effective_decision"] = "none"
    return ApiResponse(data=data)


@router.post(
    "",
    response_model=ApiResponse[QuestionResponse],
    summary="创建题目",
    description="创建一道新题目，支持选项和知识点关联。操作在事务中执行。",
)
def create_question(
    request: QuestionCreate,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
) -> ApiResponse:
    """Create a new question with options and knowledge associations."""
    service = QuestionService(db)

    # 处理默认题库
    question_bank_id = request.question_bank_id
    if not question_bank_id:
        from app.repositories.question_bank_repository import QuestionBankRepository
        qb_repo = QuestionBankRepository(db)
        uncategorized = qb_repo.get_by_code("uncategorized")
        question_bank_id = uncategorized.id if uncategorized else 1

    # Convert options to dicts
    options_data = None
    if request.options:
        options_data = [opt.model_dump() for opt in request.options]

    question = service.create_question(
        question_type=request.question_type,
        content=request.content,
        answer=request.answer,
        analysis=request.analysis,
        difficulty=request.difficulty,
        status=request.status,
        source_type=request.source_type,
        quality_score=request.quality_score,
        question_bank_id=question_bank_id,
        options=options_data,
        knowledge_ids=request.knowledge_ids,
    )
    return ApiResponse(data=_build_question_response(question))


@router.put(
    "/{question_id}",
    response_model=ApiResponse[QuestionResponse],
    summary="更新题目",
    description="更新题目信息，包括选项和知识点关联。操作在事务中执行。",
)
def update_question(
    question_id: int,
    request: QuestionUpdate,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
) -> ApiResponse:
    """Update a question. Core content is protected when answer records exist."""
    service = QuestionService(db)

    update_data = request.model_dump(exclude_unset=True)

    # 历史答题保护：已有答题记录的题目不能修改核心内容
    from app.models.question_answer_record import QuestionAnswerRecord
    answer_count = db.query(QuestionAnswerRecord).filter(
        QuestionAnswerRecord.question_id == question_id
    ).count()

    if answer_count > 0:
        # 有答题记录，只允许修改解析等非核心字段
        core_fields = {"content", "answer", "options", "question_type"}
        modified_core = core_fields & set(update_data.keys())
        if modified_core:
            from app.core.exceptions import ValidationException
            raise ValidationException(
                f"题目已有 {answer_count} 条答题记录，"
                f"不能修改核心内容: {', '.join(modified_core)}。"
                f"如需修改核心内容，请下架旧题并创建新题。"
            )

    # 手动编辑解析时标记来源
    if "analysis" in update_data or "explanation" in update_data:
        update_data["explanation_source"] = "manual"

    # Convert options to dicts if provided
    if "options" in update_data and update_data["options"]:
        update_data["options"] = [
            opt if isinstance(opt, dict) else opt.model_dump()
            for opt in update_data["options"]
        ]

    question = service.update_question(question_id, **update_data)
    return ApiResponse(data=_build_question_response(question))


@router.delete(
    "/{question_id}",
    response_model=ApiResponse[QuestionResponse],
    summary="删除题目",
    description="禁用指定题目（软删除）。",
)
def delete_question(
    question_id: int,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
) -> ApiResponse:
    """Disable a question (soft delete)."""
    service = QuestionService(db)
    question = service.delete_question(question_id)
    return ApiResponse(data=QuestionResponse.model_validate(question))
