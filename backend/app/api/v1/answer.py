"""答题记录 API 路由（兼容层）。

docs/14 §5.8 兼容约定：
    - 旧 POST /answers/submit 保留：身份必须是真实普通用户（AppUser），
      app_user_id 如实写入；practice_paper_id / practice_paper_item_id /
      practice_session_id 可为 NULL（该接口不参与练习会话）
    - 旧 GET /answers/statistics/{question_id} 保留，统计改由
      StatisticsService 统一口径（样本阈值配置化）
    - 新增 GET /answers/history、GET /answers/{id}（按 app_user_id 过滤）

练习会话内的提交请走 POST /practice/sessions/{sid}/items/{pid}/submit
（以快照标准答案判分）。
"""

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.exceptions import ResourceNotFoundException, ValidationException
from app.dependencies.auth import get_current_admin, get_current_principal, get_current_user
from app.models.admin import AdminUser
from app.models.app_user import AppUser
from app.models.question import Question
from app.models.question_answer_record import QuestionAnswerRecord
from app.schemas.answer import (
    AnswerRecordItem,
    AnswerRecordResponse,
    AnswerStatisticsResponse,
    AnswerSubmitResponse,
)
from app.schemas.common import ApiErrorResponse, ApiResponse, PaginatedData
from app.services.statistics_service import StatisticsService
from app.utils.response import paginated_response, success_response

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/answers", tags=["答题记录"])


@router.post(
    "/submit",
    summary="提交答题（兼容旧接口）",
    description="普通用户提交答题，自动判分（无快照，按当前题目判分）。"
                "支持幂等（相同 idempotency_key 不重复入账）。"
                "练习会话请使用 /practice/sessions/{sid}/items/{pid}/submit。\n\n"
                "调用时机：题库练习/自由刷题页提交答案（不带练习会话的旧路径）。\n\n"
                "请求体：question_id: 题目 ID（必填，须为 published 状态）；user_answer: 用户答案"
                "（选择题为选项键数组或键串，判断题为布尔/TRUE/FALSE，简答为文本）；"
                "idempotency_key: 幂等键（可空，同用户+题目+同键重复提交返回原记录）；time_spent_ms: 作答耗时毫秒（可空，非负）。\n\n"
                "返回 data：record_id: 答题记录 ID；is_correct: 判分结果（1=正确 0=错误 null=未判分，简答题为 null）；"
                "grading_status: 判分状态（graded|ungraded）；idempotent: 幂等命中（同键重复提交）时为 true，新提交不返回该字段。\n\n"
                "权限：普通用户令牌（user_access，身份取自令牌，不接受传 app_user_id）。\n\n"
                "幂等性：同 idempotency_key 重复提交返回首条记录（idempotent=true），不同 key 记为新尝试。\n\n"
                "写库：是（新增 question_answer_record；与练习会话无关时 practice_paper_id/practice_session_id 为空）。",
    response_model=ApiResponse[AnswerSubmitResponse],
    responses={
        400: {"model": ApiErrorResponse, "description": "业务错误（HTTP 400，envelope code 区分）：40001 参数校验（question_id 必填/题目未发布）/ 40401 不存在（题目不存在）/ 40101 未认证（访问令牌无效/过期/用户不存在/已禁用）"},
        403: {"model": ApiErrorResponse, "description": "未提供或非法 Authorization 请求头（HTTP 403）"},
        500: {"model": ApiErrorResponse, "description": "系统内部错误（HTTP 500，code 50000）"},
    },
)
async def submit_answer(
    request: dict,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
) -> ApiResponse:
    """提交答题并判分（兼容旧接口，身份为真实普通用户）。"""
    question_id = request.get("question_id")
    user_answer = request.get("user_answer", "")
    idempotency_key = request.get("idempotency_key")
    time_spent_ms = request.get("time_spent_ms")

    if not question_id:
        raise ValidationException("question_id 必填")

    # 检查幂等（同一用户 + 题目 + 幂等键）
    if idempotency_key:
        existing = db.query(QuestionAnswerRecord).filter(
            QuestionAnswerRecord.app_user_id == current_user.id,
            QuestionAnswerRecord.question_id == question_id,
            QuestionAnswerRecord.idempotency_key == idempotency_key,
        ).first()
        if existing:
            return ApiResponse(data={
                "record_id": existing.id,
                "is_correct": existing.is_correct,
                "grading_status": existing.grading_status,
                "idempotent": True,
            })

    # 获取题目
    question = db.query(Question).filter(Question.id == question_id).first()
    if not question:
        raise ResourceNotFoundException("题目不存在")
    if question.status != "published":
        raise ValidationException("题目未发布，不能作答")

    # 判分（兼容旧接口无快照，按当前题目判定；**统一复用 judge() 判分服务，无分叉**）
    # docs/14 §9.7：新旧接口共用同一判分 Service，避免规则漂移。
    from app.services.grading_service import judge as judge_answer

    if question.question_type in ("SINGLE_CHOICE", "MULTIPLE_CHOICE"):
        from app.models.question_option import QuestionOption
        options = db.query(QuestionOption).filter(
            QuestionOption.question_id == question_id,
        ).all()
        correct_keys = {o.option_key for o in options if o.is_correct}
        snapshot = {
            "question_type": question.question_type,
            "correct_answer": ",".join(sorted(correct_keys)),
            "options": [
                {
                    "option_key": o.option_key,
                    "option_content": o.option_content,
                    "is_correct": bool(o.is_correct),
                }
                for o in options
            ],
        }
    else:
        snapshot = {
            "question_type": question.question_type,
            "correct_answer": (question.answer or "").strip(),
            "options": [],
        }

    verdict = judge_answer(snapshot, user_answer)
    is_correct = (
        1 if verdict["is_correct"] is True
        else (0 if verdict["is_correct"] is False else None)
    )
    grading_status = verdict["grading_status"]
    user_answer = verdict["user_answer_text"] or user_answer

    # 保存答题记录（app_user_id 如实写入；不参与练习会话，paper/item/session 为空）
    record = QuestionAnswerRecord(
        question_id=question_id,
        user_id=current_user.id,
        app_user_id=current_user.id,
        user_answer=user_answer,
        is_correct=is_correct,
        grading_status=grading_status,
        time_spent_ms=time_spent_ms,
        idempotency_key=idempotency_key,
        created_at=datetime.utcnow(),
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    return ApiResponse(data={
        "record_id": record.id,
        "is_correct": record.is_correct,
        "grading_status": record.grading_status,
    })


@router.get(
    "/history",
    summary="我的答题历史",
    description="按当前普通用户分页查询答题记录，可按题目/练习会话过滤。仅返回本人记录。\n\n"
                "调用时机：个人中心「我的答题」列表页。\n\n"
                "返回 data（分页信封）：items: 答题记录数组，每项 {id: 记录 ID, question_id: 题目 ID, "
                "user_answer: 作答内容, is_correct: 是否正确（1/0/null）, grading_status: graded|ungraded, "
                "score: 得分（可空）, time_spent_ms: 作答耗时毫秒, practice_paper_id/practice_paper_item_id/practice_session_id: "
                "所属练习卷/卷题/会话（自由刷题为空）, idempotency_key: 幂等键, created_at: 提交时间}；"
                "page/page_size/total: 分页信息。\n\n"
                "权限：普通用户令牌（user_access，仅本人）。\n\n"
                "幂等性：只读接口，无副作用。\n\n"
                "写库：否。",
    response_model=ApiResponse[PaginatedData[AnswerRecordItem]],
    responses={
        400: {"model": ApiErrorResponse, "description": "业务错误（HTTP 400，envelope code 区分）：40101 未认证（访问令牌无效/过期/用户不存在/已禁用）"},
        403: {"model": ApiErrorResponse, "description": "未提供或非法 Authorization 请求头（HTTP 403）"},
        422: {"model": ApiErrorResponse, "description": "请求参数格式校验失败（HTTP 422，code 42201）"},
        500: {"model": ApiErrorResponse, "description": "系统内部错误（HTTP 500，code 50000）"},
    },
)
def get_answer_history(
    question_id: int | None = Query(default=None, description="按题目 ID 过滤，只看该题的作答记录；不传=返回全部题目的作答"),
    practice_session_id: int | None = Query(default=None, description="按练习会话 ID 过滤，只看某次练习会话内的作答；不传=不限会话"),
    page: int = Query(default=1, ge=1, description="页码，从 1 开始；不传=默认第 1 页"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页返回条数；不传=默认 20，取值 1~100"),
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    query = db.query(QuestionAnswerRecord).filter(
        QuestionAnswerRecord.app_user_id == current_user.id
    )
    if question_id is not None:
        query = query.filter(QuestionAnswerRecord.question_id == question_id)
    if practice_session_id is not None:
        query = query.filter(
            QuestionAnswerRecord.practice_session_id == practice_session_id
        )
    query = query.order_by(QuestionAnswerRecord.id.desc())
    total = query.count()
    rows = query.offset((page - 1) * page_size).limit(page_size).all()
    return paginated_response(
        [_answer_dict(r) for r in rows], total, page, page_size
    )


@router.get(
    "/{record_id}",
    summary="查看单条答题记录",
    description=(
        "查看本人的单条答题记录详情。他人记录按不存在处理（40401），防止 ID 枚举。\n\n"
        "调用时机：答题记录详情页。\n\n"
        "返回 data：id: 记录 ID；question_id: 题目 ID；user_answer: 作答内容；is_correct: 是否正确（1/0/null）；"
        "grading_status: graded|ungraded；score: 得分（可空）；time_spent_ms: 作答耗时毫秒；"
        "practice_paper_id/practice_paper_item_id/practice_session_id: 所属练习卷/卷题/会话（自由刷题为空）；"
        "idempotency_key: 幂等键；created_at: 提交时间。\n\n"
        "权限：普通用户令牌（user_access，仅本人）。\n\n"
        "幂等性：只读接口，无副作用。\n\n"
        "写库：否。"
    ),
    response_model=ApiResponse[AnswerRecordResponse],
    responses={
        400: {"model": ApiErrorResponse, "description": "业务错误（HTTP 400，envelope code 区分）：40401 不存在（答题记录不存在或非本人）/ 40101 未认证（访问令牌无效/过期/用户不存在/已禁用）"},
        403: {"model": ApiErrorResponse, "description": "未提供或非法 Authorization 请求头（HTTP 403）"},
        500: {"model": ApiErrorResponse, "description": "系统内部错误（HTTP 500，code 50000）"},
    },
)
def get_answer_record(
    record_id: int = Path(description="答题记录 ID，对应 question_answer_record 表主键；他人记录按不存在处理"),
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
) -> ApiResponse:
    record = db.query(QuestionAnswerRecord).filter(
        QuestionAnswerRecord.id == record_id,
        QuestionAnswerRecord.app_user_id == current_user.id,
    ).first()
    if record is None:
        raise ResourceNotFoundException("答题记录不存在")
    return ApiResponse(data=_answer_dict(record))


@router.get(
    "/statistics/{question_id}",
    summary="获取题目答题统计（兼容旧接口）",
    description=(
        "获取题目的正确率、首次作答正确率等统计数据（统一口径，样本阈值配置化）。"
        "只聚合统计，不暴露任何用户信息。\n\n"
        "调用时机：题目统计卡片/管理端题目分析。\n\n"
        "返回 data：graded_attempt_count: 已判分提交次数；correct_attempt_count: 判分正确次数；"
        "attempt_accuracy: 全部提交正确率（可空，样本不足为 null）；first_attempt_user_count: 首次作答统计的用户数（分母）；"
        "first_attempt_correct_count: 首次作答正确数；first_attempt_accuracy: 首次作答正确率（可空）；"
        "unique_user_count: 独立作答用户数；is_sample_sufficient: 样本是否充足（true/false）；"
        "accuracy: 同 attempt_accuracy（统一口径字段）；display_status: 统计状态（available|insufficient_samples）；"
        "sample_threshold: 样本量阈值（QUESTION_STATISTICS_MIN_SAMPLES，默认 20）。\n\n"
        "权限：管理员令牌。\n\n"
        "幂等性：只读接口，无副作用。\n\n"
        "写库：否。"
    ),
    response_model=ApiResponse[AnswerStatisticsResponse],
    responses={
        400: {"model": ApiErrorResponse, "description": "业务错误（HTTP 400，envelope code 区分）：40101 未认证（管理员令牌无效/过期/管理员不存在/已禁用）"},
        403: {"model": ApiErrorResponse, "description": "未提供或非法 Authorization 请求头（HTTP 403）"},
        500: {"model": ApiErrorResponse, "description": "系统内部错误（HTTP 500，code 50000）"},
    },
)
def get_answer_statistics(
    question_id: int = Path(description="题目 ID，统计该题在全部用户作答下的正确率与样本口径"),
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
) -> ApiResponse:
    """获取题目答题统计（兼容旧字段名 + 统一口径新字段）。"""
    stats = StatisticsService(db).question_statistics(question_id)
    # 兼容旧响应字段名
    return ApiResponse(data={
        "graded_attempt_count": stats["graded_submission_count"],
        "correct_attempt_count": stats["correct_submission_count"],
        "attempt_accuracy": stats["accuracy"],
        "first_attempt_user_count": stats["first_attempt_total"],
        "first_attempt_correct_count": stats["first_attempt_correct"],
        "first_attempt_accuracy": stats["first_attempt_accuracy"],
        "unique_user_count": stats["unique_user_count"],
        "is_sample_sufficient": stats["display_status"] == "available",
        # 新增统一口径字段
        "accuracy": stats["accuracy"],
        "display_status": stats["display_status"],
        "sample_threshold": stats["sample_threshold"],
    })


def _answer_dict(record: QuestionAnswerRecord) -> dict:
    return {
        "id": record.id,
        "question_id": record.question_id,
        "user_answer": record.user_answer,
        "is_correct": record.is_correct,
        "grading_status": record.grading_status,
        "score": float(record.score) if record.score is not None else None,
        "time_spent_ms": record.time_spent_ms,
        "practice_paper_id": record.practice_paper_id,
        "practice_paper_item_id": record.practice_paper_item_id,
        "practice_session_id": record.practice_session_id,
        "idempotency_key": record.idempotency_key,
        "created_at": record.created_at.isoformat() if record.created_at else None,
    }
