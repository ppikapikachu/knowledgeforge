"""Question API router."""

from typing import Optional

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_admin, get_current_principal
from app.models.admin import AdminUser
from app.schemas.common import ApiResponse, ApiErrorResponse, PaginatedData
from app.schemas.question import (
    OptionResponse,
    QuestionCreate,
    QuestionListItem,
    QuestionResponse,
    QuestionStatisticsResponse,
    QuestionUpdate,
)
from app.services.question_service import QuestionService
from app.utils.response import paginated_response, success_response

router = APIRouter(prefix="/questions", tags=["题目管理"])


# 错误响应文档（统一响应信封 {code, message, data}；业务异常经全局异常处理以 HTTP 400 + 业务码 返回）
ERROR_RESPONSES = {
    400: {
        "model": ApiErrorResponse,
        "description": "业务错误（HTTP 400，envelope code 区分）：40101 未认证（访问令牌无效/过期/用户不存在/已禁用）",
    },
    403: {
        "model": ApiErrorResponse,
        "description": "未提供或非法 Authorization 请求头（HTTP 403）",
    },
    422: {
        "model": ApiErrorResponse,
        "description": "请求参数格式校验失败（HTTP 422，code 42201）",
    },
    500: {
        "model": ApiErrorResponse,
        "description": "系统内部错误（HTTP 500，code 50000），data 恒为 null",
    },
}


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
    response_model=ApiResponse[PaginatedData[QuestionListItem]],
    responses=ERROR_RESPONSES,
    summary="获取题目列表",
    description=(
        "用途：分页查询题目，供管理端题目列表页使用。\n"
        "调用时机：进入题目管理页或切换筛选条件时调用。\n"
        "返回 data 结构（分页信封 {items, page, page_size, total}）：\n"
        "- items: 题目数组，每项含 id 题目ID / question_type 题型(SINGLE_CHOICE|MULTIPLE_CHOICE|TRUE_FALSE|SHORT_ANSWER) / "
        "content 题干 / answer 标准答案 / analysis 解析 / difficulty 难度(1-3) / status 状态(pending_review|published|rejected|disabled) / "
        "source_type 来源(MANUAL|AI) / quality_score 质量分 / question_bank_id 所属题库ID / options 选项数组 / knowledge_ids 关联知识点ID数组 / "
        "created_at 创建时间 / updated_at 更新时间\n"
        "- page: 当前页码\n- page_size: 每页数量\n- total: 符合条件的总条数\n"
        "权限：仅管理员（JWT）。\n"
        "幂等性：只读查询，可安全重复调用。\n"
        "写库：否。"
    ),
)
def get_question_list(
    page: int = Query(default=1, ge=1, description="页码参数，从 1 开始递增，默认第 1 页"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页条数，取值范围 1-100，默认 20"),
    question_type: Optional[str] = Query(
        default=None,
        description="题型筛选，可选 SINGLE_CHOICE 单选 | MULTIPLE_CHOICE 多选 | TRUE_FALSE 判断 | SHORT_ANSWER 简答；不传为全部",
    ),
    difficulty: Optional[int] = Query(
        default=None, ge=1, le=3,
        description="难度筛选，1 简单 | 2 中等 | 3 困难；不传为全部",
    ),
    status: Optional[str] = Query(
        default=None,
        description="状态筛选，可选 pending_review 待审核 | published 已发布 | rejected 已驳回 | disabled 已下架；不传为全部",
    ),
    knowledge_id: Optional[int] = Query(
        default=None, description="按关联知识点ID筛选，只返回关联了该知识点的题目；不传为全部",
    ),
    question_bank_id: Optional[int] = Query(
        default=None, description="按题库ID筛选，只返回该题库下的题目；不传为全部",
    ),
    source_type: Optional[str] = Query(
        default=None,
        description="来源筛选，MANUAL 人工创建 | AI 系统生成；不传为全部",
    ),
    keyword: Optional[str] = Query(
        default=None, description="题干关键词模糊匹配（LIKE 检索题干文本），不传则不按关键词过滤",
    ),
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
    description=(
        "用途：查看单题完整信息（含选项、关联知识点、去重复核与 AI 审核状态），供题目详情/编辑页使用。\n"
        "调用时机：进入题目详情页时调用。\n"
        "返回 data 结构：\n"
        "- id: 题目ID\n- question_type: 题型(SINGLE_CHOICE|MULTIPLE_CHOICE|TRUE_FALSE|SHORT_ANSWER)\n"
        "- content: 题干\n- answer: 标准答案（选择题为选项键，判断为 TRUE/FALSE，简答为文本）\n"
        "- analysis: 解析\n- difficulty: 难度(1-3)\n- status: 状态(pending_review|published|rejected|disabled)\n"
        "- source_type: 来源(MANUAL|AI)\n- quality_score: 质量分\n- question_bank_id: 所属题库ID\n"
        "- used_count: 使用次数\n- correct_count: 正确次数\n"
        "- options: 选项数组（含 option_key/option_content/is_correct/sort_order）\n"
        "- knowledge_ids: 关联知识点ID数组\n"
        "- dedup_review_status: 去重复核状态(none|distinct|duplicate|uncertain，仅本题作为候选被裁定时非 none)\n"
        "- dedup_manual_resolution: 去重人工裁定结论(duplicate|distinct|null)\n"
        "- dedup_effective_decision: 去重最终结论(人工裁定优先于自动判定)\n"
        "- dedup_role: 本题在去重记录中的方向(candidate 候选侧|historical 被撞历史题|null 无记录)\n"
        "- dedup_blocked_candidate_count: 撞上本题后被拦的重复候选数\n"
        "- ai_review_decision: AI 质量审核结论(auto_approve|auto_reject|manual_review|null)\n"
        "- ai_review_risk_level: AI 审核风险等级(low|medium|high|unknown|null)\n"
        "- ai_review_reason: AI 审核理由\n- ai_review_issue_types: AI 审核问题类型数组\n"
        "- ai_reviewed_at: AI 审核时间\n- ai_review_record_id: 审核记录ID\n"
        "- created_at / updated_at: 创建/更新时间\n"
        "权限：仅管理员（JWT）。\n"
        "幂等性：只读查询，可安全重复调用。\n"
        "写库：否。"
    ),
)
def get_question(
    question_id: int = Path(..., description="题目ID，必须为已存在的题目主键，不存在时返回业务错误 40401"),
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
) -> ApiResponse:
    """Get question by ID."""
    service = QuestionService(db)
    question = service.get_question(question_id)
    data = _build_question_response(question)

    # 去重复核状态（uncertain 可追踪，§6）：按记录方向区分——
    # 本题作为新题侧（new_content_hash == 本题指纹）的裁定才是本题自己的结论；
    # 仅匹配侧（matched_question_id == 本题）的记录说明"别的候选撞上本题被拦"，
    # 本题是胜出方，不得据此标注 duplicate。
    from app.models.question_dedup_record import QuestionDedupRecord as QDR
    q_hash = question.content_hash or ""
    linked_rows = (
        db.query(QDR)
        .filter(
            (QDR.matched_question_id == question.id)
            | (QDR.new_content_hash == q_hash)
        )
        .order_by(QDR.id.desc())
        .all()
    ) if q_hash else (
        db.query(QDR)
        .filter(QDR.matched_question_id == question.id)
        .order_by(QDR.id.desc())
        .all()
    )
    own_record = next(
        (
            r for r in linked_rows
            if r.new_content_hash == q_hash
            and r.matched_question_id != question.id
            and not (r.decision == "duplicate" and r.matched_question_id is None)
        ),
        None,
    )
    blocked_candidate_count = sum(
        1 for r in linked_rows
        if (r.matched_question_id == question.id
            or (r.matched_question_id is None and r.new_content_hash == q_hash))
        and (r.manual_resolution or r.decision) == "duplicate"
    )
    if own_record is not None:
        data["dedup_review_status"] = (
            "uncertain" if own_record.decision == "uncertain"
            else "duplicate" if own_record.decision == "duplicate"
            else "distinct"
        )
        # 人工复核结论（不覆盖自动判定；uncertain 不被映射成 duplicate，
        # 人工结论以独立字段 + effective_decision 提供，§2.5/§3.3）
        data["dedup_manual_resolution"] = own_record.manual_resolution
        data["dedup_effective_decision"] = own_record.manual_resolution or own_record.decision
        data["dedup_role"] = "candidate"
    elif linked_rows:
        data["dedup_review_status"] = "distinct"
        data["dedup_manual_resolution"] = None
        data["dedup_effective_decision"] = "distinct"
        data["dedup_role"] = "historical"
    else:
        data["dedup_review_status"] = "none"
        data["dedup_manual_resolution"] = None
        data["dedup_effective_decision"] = "none"
        data["dedup_role"] = None
    data["dedup_blocked_candidate_count"] = blocked_candidate_count

    # AI 质量审核结果（最新一轮，无记录为 null，§7.2）
    from app.models.question_review_record import QuestionReviewRecord as QRR
    review_record = (
        db.query(QRR)
        .filter(QRR.question_id == question.id)
        .order_by(QRR.review_round.desc(), QRR.id.desc())
        .first()
    )
    if review_record is not None:
        data["ai_review_decision"] = review_record.decision
        data["ai_review_risk_level"] = review_record.risk_level
        data["ai_review_reason"] = review_record.reason
        data["ai_review_issue_types"] = review_record.issue_types or []
        data["ai_reviewed_at"] = (
            review_record.updated_at.isoformat() if review_record.updated_at else None
        )
        data["ai_review_record_id"] = review_record.id
    else:
        data["ai_review_decision"] = None
        data["ai_review_risk_level"] = None
        data["ai_review_reason"] = None
        data["ai_review_issue_types"] = None
        data["ai_reviewed_at"] = None
        data["ai_review_record_id"] = None
    return ApiResponse(data=data)


@router.post(
    "",
    response_model=ApiResponse[QuestionResponse],
    summary="创建题目",
    description=(
        "用途：手工创建一道题目，可同时写入选项与知识点关联。\n"
        "调用时机：管理端题目管理页点击\"新建题目\"提交时调用。\n"
        "请求体（QuestionCreate）：question_type 题型必填 / content 题干必填 / answer 标准答案必填 / "
        "analysis 解析可选 / difficulty 难度 1-3 / status 初始状态(默认 pending_review) / source_type 来源 / "
        "quality_score 质量分 / question_bank_id 题库ID(缺省落入 uncategorized 题库) / options 选项数组 / knowledge_ids 知识点ID数组。\n"
        "返回 data 结构：同\"获取题目详情\"的基础字段（创建后的完整题目对象）；其中 dedup_*/ai_review_* 去重与审核状态字段为默认值（null/0），真实状态仅 GET /questions/{id} 详情接口填充。\n"
        "权限：仅管理员（JWT）。\n"
        "幂等性：非幂等，每次调用生成新题目；重复调用会产生多条记录。\n"
        "写库：是（题目+选项+知识点关联同一事务，失败整体回滚）。"
    ),
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
    description=(
        "用途：编辑题目信息（可含选项与知识点关联替换）。\n"
        "调用时机：题目编辑页保存时调用。\n"
        "请求体（QuestionUpdate，均为可选字段，只传需修改的）：question_type/content/answer/analysis/difficulty/"
        "status/source_type/quality_score/options/knowledge_ids。\n"
        "业务约束：题目已有答题记录时，核心字段 content/answer/options/question_type 不允许修改（返回 40001），"
        "此时只能改解析等非核心字段；手动修改 analysis/explanation 会把讲解来源标记为 manual。\n"
        "返回 data 结构：同\"获取题目详情\"的基础字段（更新后的完整题目对象）；其中 dedup_*/ai_review_* 去重与审核状态字段为默认值（null/0），真实状态仅 GET /questions/{id} 详情接口填充。\n"
        "权限：仅管理员（JWT）。\n"
        "幂等性：条件幂等——相同请求重复提交结果一致（最后一次覆盖）。\n"
        "写库：是（题目/选项/知识点关联同一事务）。"
    ),
)
def update_question(
    request: QuestionUpdate,
    question_id: int = Path(..., description="题目ID，必须为已存在的题目主键，不存在时返回业务错误 40401"),
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
    description=(
        "用途：下架/删除题目（软删除，status 置为 disabled，数据保留）。\n"
        "调用时机：题目列表点击\"下架/删除\"时调用；重复调用无副作用。\n"
        "路径参数：question_id 题目ID。\n"
        "返回 data 结构：同\"获取题目详情\"的基础字段（状态变为 disabled 的题目对象）；其中 dedup_*/ai_review_* 去重与审核状态字段为默认值（null/0），真实状态仅 GET /questions/{id} 详情接口填充。\n"
        "权限：仅管理员（JWT）。\n"
        "幂等性：幂等，重复调用结果一致（不物理删除）。\n"
        "写库：是（仅更新 status，不删任何行）。"
    ),
)
def delete_question(
    question_id: int = Path(..., description="题目ID，必须为已存在的题目主键，不存在时返回业务错误 40401"),
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
) -> ApiResponse:
    """Disable a question (soft delete)."""
    service = QuestionService(db)
    question = service.delete_question(question_id)
    # 软删除数据保留、关联关系仍在，返回真实完整题目（含 knowledge_ids），与 GET/POST/PUT 一致。
    return ApiResponse(data=_build_question_response(question))


@router.get(
    "/{question_id}/statistics",
    response_model=ApiResponse[QuestionStatisticsResponse],
    responses=ERROR_RESPONSES,
    summary="题目答题统计",
    description=(
        "用途：查看单题的答题聚合统计（正确率/首次作答正确率/独立作答人数等），不暴露任何用户信息。\n"
        "调用时机：题目详情页或运营看板查看题目数据时调用；管理员与普通用户均可查看。\n"
        "路径参数：question_id 题目ID。\n"
        "返回 data 结构：\n"
        "- question_id: 题目ID\n- graded_submission_count: 已判分（graded）提交次数\n"
        "- total_submission_count: 全部提交次数\n- correct_submission_count: 判分正确次数\n"
        "- accuracy: 全部提交正确率（0-1，样本不足为 null）\n- first_attempt_accuracy: 首次作答正确率（每用户每题首次，样本不足为 null）\n"
        "- first_attempt_total: 首次作答样本总数\n- first_attempt_correct: 首次作答正确数\n"
        "- unique_user_count: 独立作答人数\n"
        "- display_status: available 正常 | insufficient_samples 样本不足（阈值 QUESTION_STATISTICS_MIN_SAMPLES）\n"
        "- sample_threshold: 样本量阈值\n"
        "口径：只统计 app_user_id 非空且 graded 的记录；简答 ungraded 不进分母。\n"
        "权限：管理员或普通用户（JWT）。\n"
        "幂等性：只读查询，可安全重复调用。\n"
        "写库：否。"
    ),
)
def get_question_statistics(
    question_id: int = Path(..., description="题目ID；题目不存在时返回结构一致的空统计结果（全零/null，不报 40401）"),
    db: Session = Depends(get_db),
    principal=Depends(get_current_principal),
):
    """Question answer statistics（统一口径，样本阈值配置化）。"""
    from app.services.statistics_service import StatisticsService

    return success_response(StatisticsService(db).question_statistics(question_id))
