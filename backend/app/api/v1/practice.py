"""练习 API：组卷快照 / 练习会话 / 草稿标记 / 提交判分。

所有接口均以普通用户（AppUser）身份访问，owner 校验在服务层完成。
组卷与判分不调用 LLM/Agent；快照接口不返回未提交题目的正确答案与解析。
"""

from fastapi import APIRouter, Body, Depends, Header, Path, Query

from app.core.database import get_db
from app.core.exceptions import ResourceNotFoundException, ValidationException
from app.dependencies.auth import get_current_user
from app.models.app_user import AppUser
from app.models.question_bank import QuestionBank
from app.schemas.common import ApiErrorResponse, ApiResponse, PaginatedData
from app.schemas.practice import (
    AssemblePaperRequest,
    AssemblePaperResponse,
    BankKnowledgePointsResponse,
    DraftSaveRequest,
    DraftSaveResponse,
    InsufficientStockErrorData,
    InsufficientStockErrorResponse,
    MarkItemResponse,
    MarkRequest,
    OpenQuestionBankItem,
    OpenQuestionBankResponse,
    PaperDetailResponse,
    PaperListItem,
    PaperResponse,
    ProgressRequest,
    ProgressUpdateResponse,
    SessionAnswersResponse,
    SessionDetailResponse,
    SessionListItem,
    SessionResponse,
    SessionResultResponse,
    SubmitAnswerRequest,
    SubmitAnswerResponse,
)
from app.services.practice_service import PracticeService
from app.services.question_bank_stats import bank_knowledge_points, bank_question_stats
from app.utils.response import paginated_response, success_response

router = APIRouter(prefix="/practice", tags=["练习"])


def _svc(db=Depends(get_db)) -> PracticeService:
    return PracticeService(db)


def _error_responses(not_found: str = "目标资源不存在或不属于当前用户") -> dict:
    """统一错误响应文档（ApiErrorResponse 信封）。

    业务错误实际以 HTTP 400 信封返回（envelope code 区分语义）；此处仅文档化，
    不改变任何实际 HTTP 状态码。
    """
    return {
        400: {
            "model": ApiErrorResponse,
            "description": (
                "业务错误（HTTP 400，envelope code 区分）：40001 参数校验（幂等冲突、进度越界、状态不允许修改、"
                f"题型/难度无题可抽等）/ 40401 不存在（{not_found}，与越权同码防枚举）/ "
                "40101 未认证（访问令牌无效/过期/用户不存在/已禁用）；data 多为 null"
            ),
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
            "description": "系统内部错误（HTTP 500，code 50000）",
        },
    }


def _assemble_error_responses() -> dict:
    """组卷接口错误文档：400 额外给出库存不足时的 data 结构示例（InsufficientStockErrorData）。"""
    responses = _error_responses(not_found="题库不存在或未开放练习")
    responses[400] = {
        "model": InsufficientStockErrorResponse,
        "description": (
            "业务错误（HTTP 400，envelope code 区分）：40001 参数校验失败、幂等冲突（同 Idempotency-Key 不同参数）、"
            "题型/难度无题可抽等；40401 不存在（题库不存在或未开放练习，与越权同码防枚举）；"
            "40101 未认证（访问令牌无效/过期/用户不存在/已禁用）。allow_partial=false 且库存不足时 "
            "data=InsufficientStockErrorData（error/requested_count/available_count/missing_count，"
            "见下方 data 结构）；其余错误 data 多为 null"
        ),
        "content": {
            "application/json": {
                "schema": {"$ref": "#/components/schemas/InsufficientStockErrorResponse"},
                "example": InsufficientStockErrorResponse(
                    code=40001,
                    message=(
                        "题库库存不足：请求 30 题，可用 12 题，缺少 18 题；"
                        "可减少题目数量或调整题型/难度分布后重试"
                    ),
                    data=InsufficientStockErrorData(
                        requested_count=30, available_count=12, missing_count=18
                    ),
                ).model_dump(),
            }
        },
    }
    return responses


@router.post(
    "/papers/assemble",
    summary="组卷生成练习卷（快照）",
    response_model=ApiResponse[AssemblePaperResponse],
    responses=_assemble_error_responses(),
    description=(
        "用途：按题型/难度分布从开放练习题库抽取已发布题目，生成不可变快照试卷并自动创建首个练习会话。\n"
        "调用时机：用户开始一轮练习前；组卷只读题库，不调用 LLM/Agent、不生成补录题目。\n"
        "权限：普通用户 access token。\n"
        "幂等性：支持请求头 Idempotency-Key（首字符字母数字，1~128 位，允许 [A-Za-z0-9._:~-]）；"
        "同 key 同参返回原卷（data.idempotent=true 不再抽题），同 key 异参返回 40001 幂等冲突，不同用户同 key 互不影响。\n"
        "写库：是（paper/paper_item/session/session_item 一次事务原子写入；校验失败或 allow_partial=false 库存不足时零落库）。\n"
        "返回 data：\n"
        "paper: 试卷快照头（paper_id 试卷 ID/title 标题/question_count 题量/total_score 总分/status 状态 ready|archived/"
        "source_question_bank_id 来源题库/assembly_config 组卷参数/snapshot_version 快照版本/snapshot_hash 快照哈希/created_at/archived_at）\n"
        "session: 首个练习会话（见会话字段说明）\n"
        "idempotent: 是否幂等命中返回的原卷（false=本次新生成）"
    ),
)
def assemble_paper(
    request: AssemblePaperRequest,
    idempotency_key: str | None = Header(
        default=None,
        alias="Idempotency-Key",
        description="幂等键（可选）：同 key 同参返回原卷、同 key 异参报 40001 冲突；格式为首字符字母数字的 1~128 位 [A-Za-z0-9._:~-] 串",
    ),
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


@router.get(
    "/papers",
    summary="我的试卷列表",
    response_model=ApiResponse[PaginatedData[PaperListItem]],
    responses=_error_responses(),
    description=(
        "用途：分页查看当前用户拥有的试卷快照（含最近一次练习会话摘要）。\n"
        "调用时机：练习首页/历史试卷列表；不触发组卷。\n"
        "权限：普通用户 access token，仅返回本人数据。\n"
        "幂等性：只读幂等。\n"
        "写库：否（仅查询）。\n"
        "返回 data：\n"
        "items[].paper_id: 试卷 ID\n"
        "items[].title: 试卷标题\n"
        "items[].question_count: 题量\n"
        "items[].total_score: 总分\n"
        "items[].status: 试卷状态 ready|archived\n"
        "items[].source_question_bank_id: 来源题库 ID\n"
        "items[].assembly_config: 组卷参数（题型/难度分布等）\n"
        "items[].snapshot_version: 快照版本（固定 1）\n"
        "items[].snapshot_hash: 快照内容哈希（SHA-256）\n"
        "items[].created_at: 组卷时间\n"
        "items[].archived_at: 归档时间（未归档为 null）\n"
        "items[].recent_session: 最近会话摘要（session_id/status/answered_count/total_count/last_active_at，无会话为 null）\n"
        "page/page_size/total: 分页信封字段"
    ),
)
def list_papers(
    page: int = Query(default=1, ge=1, description="页码（可选参数，从 1 开始计数，缺省默认第 1 页）"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页条数（可选参数，默认 20 条，取值范围 1~100）"),
    current_user: AppUser = Depends(get_current_user),
    db=Depends(get_db),
):
    items, total = PracticeService(db).list_papers(current_user.id, page, page_size)
    return paginated_response(items, total, page, page_size)


@router.get(
    "/papers/{paper_id}",
    summary="试卷详情（题目面）",
    response_model=ApiResponse[PaperDetailResponse],
    responses=_error_responses(not_found="试卷不存在或不属于当前用户"),
    description=(
        "用途：查看单份试卷快照的完整题目面（题干/选项/知识点/分值）。\n"
        "调用时机：用户查看试卷或回顾题目；不含未提交题的正确答案与解析（白名单投影，安全字段一律不返回）。\n"
        "权限：普通用户 access token，仅本人试卷可见（他人 40401 防枚举）。\n"
        "幂等性：只读幂等。\n"
        "写库：否（仅查询）。\n"
        "返回 data：\n"
        "paper_id/title/question_count/total_score/status/source_question_bank_id/assembly_config/snapshot_version/snapshot_hash/created_at/archived_at: 同试卷字段说明\n"
        "items[]: 题目面投影（paper_item_id 题目项 ID/sort_order 序号/question_type 题型/difficulty 难度码/difficulty_name 难度名/"
        "score 分值/content 题干/options 选项(option_key 键,content 文本)/knowledge_points 知识点列表）"
    ),
)
def get_paper(
    paper_id: int = Path(default=..., ge=1, description="试卷 ID（practice_paper 主键正整数；非本人试卷统一返回 40401，不泄露存在性）"),
    current_user: AppUser = Depends(get_current_user),
    db=Depends(get_db),
):
    """试卷详情（含题目面，不含未提交题目的正确答案/解析）。"""
    return success_response(PracticeService(db).get_paper(current_user.id, paper_id))


@router.post(
    "/papers/{paper_id}/sessions",
    summary="对试卷发起新练习会话（再练）",
    response_model=ApiResponse[SessionResponse],
    responses=_error_responses(not_found="试卷不存在或不属于当前用户"),
    description=(
        "用途：对已有试卷重新练习，创建全新会话（复用同一份不可变快照，不重新组卷）。\n"
        "调用时机：用户点击\"再练一次\"；已归档试卷拒绝（40001），历史会话不受影响。\n"
        "权限：普通用户 access token，仅本人试卷。\n"
        "幂等性：非幂等（每次调用新建一个会话）。\n"
        "写库：是（practice_session + practice_session_item 批量插入，一次事务）。\n"
        "返回 data（会话）：\n"
        "session_id: 会话 ID\n"
        "paper_id: 所属试卷 ID\n"
        "mode: 练习模式（固定 practice）\n"
        "status: 会话状态 in_progress|completed|abandoned\n"
        "current_item_order: 当前题序（从 1 开始）\n"
        "total_count/answered_count/correct_count/incorrect_count/ungraded_count: 题量/已答/正确/错误/未评分计数\n"
        "started_at/last_active_at/completed_at/abandoned_at/duration_ms: 时间与耗时字段"
    ),
)
def create_session(
    paper_id: int = Path(default=..., ge=1, description="试卷 ID（practice_paper 主键正整数；非本人试卷统一返回 40401，不泄露存在性）"),
    current_user: AppUser = Depends(get_current_user),
    db=Depends(get_db),
):
    """对已有试卷发起新的练习会话（再练）。"""
    return success_response(PracticeService(db).create_session(current_user.id, paper_id))


@router.patch(
    "/papers/{paper_id}/archive",
    summary="归档试卷",
    response_model=ApiResponse[PaperResponse],
    responses=_error_responses(not_found="试卷不存在或不属于当前用户"),
    description=(
        "用途：将试卷标记为 archived（软归档，不物理删除，不删除历史练习数据）。\n"
        "调用时机：用户不再需要该试卷；归档后不可再发起新会话，历史会话仍可查看。\n"
        "权限：普通用户 access token，仅本人试卷。\n"
        "幂等性：幂等（已归档重复调用直接返回当前状态）。\n"
        "写库：是（status→archived + archived_at）。\n"
        "返回 data（试卷）：paper_id/title/question_count/total_score/status/source_question_bank_id/"
        "assembly_config/snapshot_version/snapshot_hash/created_at/archived_at"
    ),
)
def archive_paper(
    paper_id: int = Path(default=..., ge=1, description="试卷 ID（practice_paper 主键正整数；非本人试卷统一返回 40401，不泄露存在性）"),
    current_user: AppUser = Depends(get_current_user),
    db=Depends(get_db),
):
    return success_response(PracticeService(db).archive_paper(current_user.id, paper_id))


@router.get(
    "/sessions",
    summary="我的练习会话列表",
    response_model=ApiResponse[PaginatedData[SessionListItem]],
    responses=_error_responses(),
    description=(
        "用途：分页查看当前用户的练习会话，可按状态筛选。\n"
        "调用时机：练习记录/继续练习入口。\n"
        "权限：普通用户 access token，仅本人数据。\n"
        "幂等性：只读幂等。\n"
        "写库：否（仅查询）。\n"
        "返回 data：\n"
        "items[].session_id: 会话 ID\n"
        "items[].paper_id: 所属试卷 ID\n"
        "items[].mode: 练习模式（practice）\n"
        "items[].status: in_progress|completed|abandoned\n"
        "items[].current_item_order: 当前题序\n"
        "items[].total_count/answered_count/correct_count/incorrect_count/ungraded_count: 题量与判分计数\n"
        "items[].started_at/last_active_at/completed_at/abandoned_at/duration_ms: 时间与耗时\n"
        "page/page_size/total: 分页信封字段"
    ),
)
def list_sessions(
    status: str | None = Query(
        default=None,
        description="会话状态筛选，取值 in_progress/completed/abandoned；不传=全部。其他取值返回 40001",
    ),
    page: int = Query(default=1, ge=1, description="页码（可选参数，从 1 开始计数，缺省默认第 1 页）"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页条数（可选参数，默认 20 条，取值范围 1~100）"),
    current_user: AppUser = Depends(get_current_user),
    db=Depends(get_db),
):
    if status is not None and status not in ("in_progress", "completed", "abandoned"):
        raise ValidationException("status 仅支持 in_progress/completed/abandoned")
    items, total = PracticeService(db).list_sessions(current_user.id, status, page, page_size)
    return paginated_response(items, total, page, page_size)


@router.get(
    "/sessions/{session_id}",
    summary="练习会话详情（状态化投影）",
    response_model=ApiResponse[SessionDetailResponse],
    responses=_error_responses(not_found="练习会话不存在或不属于当前用户"),
    description=(
        "用途：查看会话整体信息 + 快照题目 + 草稿 + 进度；已提交题目附判分结果。\n"
        "调用时机：进入练习页面或继续答题；安全投影：in_progress/abandoned 会话中未提交题目不返回 "
        "correct_answer/explanation/is_correct，仅已提交题目返回自身判分结果（completed 会话全量回顾）。\n"
        "权限：普通用户 access token，仅本人会话。\n"
        "幂等性：只读幂等（会顺带刷新 last_active_at）。\n"
        "写库：是（仅 last_active_at 时间戳）。\n"
        "返回 data：\n"
        "session: 会话信息（字段同会话字段说明）\n"
        "paper: 试卷快照头\n"
        "items[]: 题目投影（paper_item_id/sort_order/question_type/difficulty/difficulty_name/score/content/options/"
        "knowledge_points + 未提交题含 draft_answer 草稿、status unanswered|draft_saved|answered、is_marked 标记；"
        "已提交题含 correct_answer/explanation/is_correct/grading_status/score 判分结果）\n"
        "progress: 进度（session_id/status/total_count/answered_count/correct_count/incorrect_count/ungraded_count/current_item_order）"
    ),
)
def get_session(
    session_id: int = Path(default=..., ge=1, description="练习会话 ID（正整数），仅本人会话可访问"),
    current_user: AppUser = Depends(get_current_user),
    db=Depends(get_db),
):
    """会话详情：快照题目 + 草稿 + 进度；已提交题目附判分结果。"""
    return success_response(PracticeService(db).get_session_detail(current_user.id, session_id))


@router.post(
    "/sessions/{session_id}/resume",
    summary="恢复练习会话",
    response_model=ApiResponse[SessionResponse],
    responses=_error_responses(not_found="练习会话不存在或不属于当前用户"),
    description=(
        "用途：恢复一个 in_progress 会话继续答题（刷新活跃时间）。\n"
        "调用时机：用户回到未完成的练习；completed/abandoned 会话拒绝恢复（40001）。\n"
        "权限：普通用户 access token，仅本人会话。\n"
        "幂等性：幂等（重复调用不改变状态）。\n"
        "写库：是（last_active_at）。\n"
        "返回 data（会话）：session_id/paper_id/mode/status/current_item_order/total_count/answered_count/"
        "correct_count/incorrect_count/ungraded_count/started_at/last_active_at/completed_at/abandoned_at/duration_ms"
    ),
)
def resume_session(
    session_id: int = Path(default=..., ge=1, description="练习会话 ID（正整数），仅本人会话可访问"),
    current_user: AppUser = Depends(get_current_user),
    db=Depends(get_db),
):
    return success_response(PracticeService(db).resume_session(current_user.id, session_id))


@router.post(
    "/sessions/{session_id}/complete",
    summary="完成练习会话",
    response_model=ApiResponse[SessionResponse],
    responses=_error_responses(not_found="练习会话不存在或不属于当前用户"),
    description=(
        "用途：将会话标记为 completed，进入只读回顾；未答题目保留 unanswered，不伪造作答。\n"
        "调用时机：用户交卷/结束练习；completed_at 只在首次完成时设置。\n"
        "权限：普通用户 access token，仅本人会话。\n"
        "幂等性：幂等（已完成重复调用直接返回，不重复写完成时间）。\n"
        "写库：是（status→completed + completed_at + 统计重算）。\n"
        "返回 data（会话）：session_id/paper_id/mode/status/current_item_order/total_count/answered_count/"
        "correct_count/incorrect_count/ungraded_count/started_at/last_active_at/completed_at/abandoned_at/duration_ms"
    ),
)
def complete_session(
    session_id: int = Path(default=..., ge=1, description="练习会话 ID（正整数），仅本人会话可访问"),
    current_user: AppUser = Depends(get_current_user),
    db=Depends(get_db),
):
    """完成会话（幂等）；未答题保留 unanswered，不伪造。"""
    return success_response(PracticeService(db).complete_session(current_user.id, session_id))


@router.post(
    "/sessions/{session_id}/abandon",
    summary="放弃练习会话",
    response_model=ApiResponse[SessionResponse],
    responses=_error_responses(not_found="练习会话不存在或不属于当前用户"),
    description=(
        "用途：将会话标记为 abandoned（软结束，不删除任何答题/草稿数据）。\n"
        "调用时机：用户主动放弃本次练习；abandoned 后不可 resume/提交，结果查看仍按状态化投影隐藏未提交题答案。\n"
        "权限：普通用户 access token，仅本人会话。\n"
        "幂等性：幂等（已放弃重复调用直接返回）。\n"
        "写库：是（status→abandoned + abandoned_at）。\n"
        "返回 data（会话）：session_id/paper_id/mode/status/current_item_order/total_count/answered_count/"
        "correct_count/incorrect_count/ungraded_count/started_at/last_active_at/completed_at/abandoned_at/duration_ms"
    ),
)
def abandon_session(
    session_id: int = Path(default=..., ge=1, description="练习会话 ID（正整数），仅本人会话可访问"),
    current_user: AppUser = Depends(get_current_user),
    db=Depends(get_db),
):
    return success_response(PracticeService(db).abandon_session(current_user.id, session_id))


@router.get(
    "/sessions/{session_id}/result",
    summary="整卷结果与解析",
    response_model=ApiResponse[SessionResultResponse],
    responses=_error_responses(not_found="练习会话不存在或不属于当前用户"),
    description=(
        "用途：查看会话的整卷作答与解析。\n"
        "调用时机：练习结束或回顾；安全投影：in_progress/abandoned 会话未提交题目不返回 "
        "correct_answer/explanation/is_correct（仅已提交题返回自身结果），completed 会话全量返回正确答案与解析。\n"
        "权限：普通用户 access token，仅本人会话。\n"
        "幂等性：只读幂等。\n"
        "写库：否（仅查询）。\n"
        "返回 data：\n"
        "session: 会话信息（字段同会话字段说明）\n"
        "items[]: 题目结果投影（paper_item_id/sort_order 题序/question_type/difficulty/difficulty_name/score 分值/"
        "content 题干/options 选项/knowledge_points 知识点 + status（unanswered|draft_saved|answered）/"
        "your_answer 用户作答 + 已提交题（completed 会话全量）的 correct_answer/explanation/is_correct/"
        "grading_status/first_submitted_at/last_submitted_at）\n"
        "summary: 结果汇总（total_count 题目总数/answered_count 已作答/correct_count 正确/incorrect_count 错误/"
        "ungraded_count 未判分/total_score 试卷总分/earned_score 累计得分）"
    ),
)
def session_result(
    session_id: int = Path(default=..., ge=1, description="练习会话 ID（正整数），仅本人会话可访问"),
    current_user: AppUser = Depends(get_current_user),
    db=Depends(get_db),
):
    """整卷答案与解析（owner 专属）。"""
    return success_response(PracticeService(db).session_result(current_user.id, session_id))


@router.get(
    "/sessions/{session_id}/answers",
    summary="会话答题记录列表",
    response_model=ApiResponse[SessionAnswersResponse],
    responses=_error_responses(not_found="练习会话不存在或不属于当前用户"),
    description=(
        "用途：查看当前用户在某会话下的全部答题记录（每次提交一条，按提交时间正序 created_at、id 升序）。\n"
        "调用时机：练习记录明细/错题回顾；只返回本人记录，不含他人数据。\n"
        "权限：普通用户 access token，仅本人会话。\n"
        "幂等性：只读幂等。\n"
        "写库：否（仅查询）。\n"
        "返回 data：\n"
        "session_id: 会话 ID\n"
        "answers[]: 答题记录（id 记录 ID/question_id 源题目 ID/practice_paper_item_id 题目项 ID/user_answer 用户作答文本/"
        "is_correct 是否正确|null=未评分/grading_status graded|ungraded/score 得分/time_spent_ms 作答耗时/"
        "idempotency_key 提交幂等键（历史/兼容记录可空）/created_at 提交时间）"
    ),
)
def session_answers(
    session_id: int = Path(default=..., ge=1, description="练习会话 ID（正整数），仅本人会话可访问"),
    current_user: AppUser = Depends(get_current_user),
    db=Depends(get_db),
):
    return success_response(PracticeService(db).session_answers(current_user.id, session_id))


@router.put(
    "/sessions/{session_id}/items/{paper_item_id}/draft",
    summary="保存题目草稿",
    response_model=ApiResponse[DraftSaveResponse],
    responses=_error_responses(not_found="练习会话/题目项不存在或不属于当前用户"),
    description=(
        "用途：保存某道题的作答草稿（随时暂存，不判分、不进入统计）。\n"
        "调用时机：练习中用户暂存答案；completed/abandoned 会话拒绝修改（40001）。\n"
        "权限：普通用户 access token，仅本人会话。\n"
        "幂等性：幂等覆盖（同一题目项反复保存仅保留最新草稿）。\n"
        "写库：是（practice_session_item.draft_answer + status→draft_saved）。\n"
        "返回 data：\n"
        "session_id: 会话 ID\n"
        "paper_item_id: 题目项 ID\n"
        "status: 题目项状态（draft_saved）\n"
        "draft_answer: 最新草稿内容"
    ),
)
def save_draft(
    session_id: int = Path(default=..., ge=1, description="练习会话 ID（正整数），仅本人会话可访问"),
    paper_item_id: int = Path(default=..., ge=1, description="题目项 ID（practice_paper_item 主键，须属于该会话的试卷）"),
    request: DraftSaveRequest = Body(
        default=...,
        description="草稿内容（answer 为按题型的 JSON 值：单选/简答=字符串、多选=字符串数组、判断=布尔或字符串；仅写草稿不判分）",
    ),
    current_user: AppUser = Depends(get_current_user),
    db=Depends(get_db),
):
    return success_response(
        PracticeService(db).save_draft(
            current_user.id, session_id, paper_item_id, request.answer
        )
    )


@router.patch(
    "/sessions/{session_id}/items/{paper_item_id}/mark",
    summary="标记/取消标记题目",
    response_model=ApiResponse[MarkItemResponse],
    responses=_error_responses(not_found="练习会话/题目项不存在或不属于当前用户"),
    description=(
        "用途：对某道题做标记（如疑难题），标记与草稿/作答状态相互独立。\n"
        "调用时机：练习中标记回头检查；completed/abandoned 会话拒绝修改（40001）。\n"
        "权限：普通用户 access token，仅本人会话。\n"
        "幂等性：幂等（重复置同一标记值不报错）。\n"
        "写库：是（practice_session_item.is_marked）。\n"
        "返回 data：\n"
        "paper_item_id: 题目项 ID\n"
        "is_marked: 当前标记状态（true=已标记，false=已取消）"
    ),
)
def mark_item(
    session_id: int = Path(default=..., ge=1, description="练习会话 ID（正整数），仅本人会话可访问"),
    paper_item_id: int = Path(default=..., ge=1, description="题目项 ID（practice_paper_item 主键，须属于该会话的试卷）"),
    request: MarkRequest = Body(default=..., description="标记状态（is_marked：true=标记该题为疑难题，false=取消标记）"),
    current_user: AppUser = Depends(get_current_user),
    db=Depends(get_db),
):
    return success_response(
        PracticeService(db).mark_item(
            current_user.id, session_id, paper_item_id, request.is_marked
        )
    )


@router.patch(
    "/sessions/{session_id}/progress",
    summary="更新练习进度（当前题序）",
    response_model=ApiResponse[ProgressUpdateResponse],
    responses=_error_responses(not_found="练习会话不存在或不属于当前用户"),
    description=(
        "用途：记录用户当前做到第几题（便于恢复练习位置），不改变答题状态与统计。\n"
        "调用时机：用户翻题时上报；completed/abandoned 会话拒绝修改（40001）。\n"
        "权限：普通用户 access token，仅本人会话。\n"
        "幂等性：幂等覆盖（同一 current_item_order 重复提交无副作用）。\n"
        "写库：是（practice_session.current_item_order + last_active_at）。\n"
        "返回 data：\n"
        "session_id: 会话 ID\n"
        "current_item_order: 当前题序（1..total_count，越界报 40001）"
    ),
)
def update_progress(
    session_id: int = Path(default=..., ge=1, description="练习会话 ID（正整数），仅本人会话可访问"),
    request: ProgressRequest = Body(default=..., description="进度内容（current_item_order：当前题序，取值 1~total_count）"),
    current_user: AppUser = Depends(get_current_user),
    db=Depends(get_db),
):
    return success_response(
        PracticeService(db).update_progress(
            current_user.id, session_id, request.current_item_order
        )
    )


@router.post(
    "/sessions/{session_id}/items/{paper_item_id}/submit",
    summary="提交答题并判分",
    response_model=ApiResponse[SubmitAnswerResponse],
    responses=_error_responses(not_found="练习会话/题目项不存在或不属于当前用户"),
    description=(
        "用途：提交某道题的作答，按试卷快照内标准答案判分（源题后续变化不影响结果），追加答题记录并更新会话统计。\n"
        "调用时机：用户答完一道题点击提交；completed/abandoned 会话拒绝提交（40001）。\n"
        "权限：普通用户 access token，仅本人会话。\n"
        "幂等性：以 request.idempotency_key 为准（8~64 位）——同 key 同内容重复提交返回原记录（data.idempotent=true），"
        "同 key 不同内容报 40001 幂等冲突，新 key 视为新一次尝试追加记录。\n"
        "写库：是（question_answer_record 追加 + practice_session_item 状态/判分 + practice_session 计数，单事务）。\n"
        "返回 data：\n"
        "answer_record_id: 答题记录 ID\n"
        "idempotent: 是否幂等命中（true=返回此前提交的原记录）\n"
        "paper_item_id: 题目项 ID\n"
        "question_id: 源题目 ID\n"
        "is_correct: 是否正确（null=未评分简答题）\n"
        "grading_status: 判分状态 graded|ungraded\n"
        "score: 本题得分（未评分为 null）\n"
        "correct_answer: 正确答案（仅提交后返回）\n"
        "explanation: 答案解析（仅提交后返回）\n"
        "session_progress: 会话进度（session_id/status/total_count/answered_count/correct_count/incorrect_count/ungraded_count/current_item_order）"
    ),
)
def submit_answer(
    session_id: int = Path(default=..., ge=1, description="练习会话 ID（正整数），仅本人会话可访问"),
    paper_item_id: int = Path(default=..., ge=1, description="题目项 ID（practice_paper_item 主键，须属于该会话的试卷）"),
    request: SubmitAnswerRequest = Body(
        default=...,
        description=(
            "提交内容（仅接受 answer/idempotency_key/time_spent_ms，多余字段一律 422 拒绝）："
            "answer 按题型取 JSON 值——单选=选项键字符串（如 'A'）、多选=选项键字符串数组（如 ['A','C']，集合完全匹配才算对）、"
            "判断=布尔或 'true'/'false' 字符串、简答=文本（ungraded 不判分）；"
            "idempotency_key=8~64 位幂等键（同 key 同内容返回原记录）；time_spent_ms=作答耗时毫秒（非负）"
        ),
    ),
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
    response_model=ApiResponse[PaginatedData[OpenQuestionBankItem]],
    responses=_error_responses(),
    description=(
        "用途：分页列出普通用户可见的练习题库（仅 is_available_for_practice=true 的题库）。\n"
        "调用时机：练习入口选题库/组卷前浏览；空库存题库也返回（can_assemble=false 并给出 unavailable_reason），库存统计一次聚合无 N+1。\n"
        "权限：普通用户 access token。\n"
        "幂等性：只读幂等。\n"
        "写库：否（仅查询）。\n"
        "返回 data：\n"
        "items[].id: 题库 ID\n"
        "items[].name: 题库名称\n"
        "items[].description: 题库描述\n"
        "items[].is_available_for_practice: 是否开放练习（此处恒 true）\n"
        "items[].available_question_count: 可练习题量（published 题数）\n"
        "items[].question_type_counts: 各题型可练习题量（SINGLE_CHOICE/MULTIPLE_CHOICE/TRUE_FALSE/SHORT_ANSWER）\n"
        "items[].difficulty_counts: 各难度可练习题量（easy/normal/hard）\n"
        "items[].can_assemble: 是否可组卷（有可练习题时 true）\n"
        "items[].unavailable_reason: 不可组卷原因（可组卷时为 null；空库存为'暂无可练习题目'）\n"
        "page/page_size/total: 分页信封字段"
    ),
)
def list_open_question_banks(
    page: int = Query(default=1, ge=1, description="页码（可选参数，从 1 开始计数，缺省默认第 1 页）"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页条数（可选参数，默认 20 条，取值范围 1~100）"),
    keyword: str = Query(default="", description="按题库名称模糊搜索（去空格后非空才生效；空串=不筛选）"),
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
    response_model=ApiResponse[OpenQuestionBankResponse],
    responses=_error_responses(not_found="题库不存在或未开放练习"),
    description=(
        "用途：查看单个开放练习题库的详情与可练习题量统计。\n"
        "调用时机：用户进入题库前查看；未开放与不存在返回同一 40401 资源错误，不泄露私有题库存在性。\n"
        "权限：普通用户 access token。\n"
        "幂等性：只读幂等。\n"
        "写库：否（仅查询）。\n"
        "返回 data：\n"
        "id: 题库 ID\n"
        "name: 题库名称\n"
        "description: 题库描述\n"
        "is_available_for_practice: 是否开放练习（此处恒 true）\n"
        "available_question_count: 可练习题量（published 题数）\n"
        "question_type_counts: 各题型可练习题量\n"
        "difficulty_counts: 各难度可练习题量（easy/normal/hard）\n"
        "can_assemble: 是否可组卷\n"
        "unavailable_reason: 不可组卷原因（可组卷为 null）"
    ),
)
def get_open_question_bank(
    qb_id: int = Path(default=..., ge=1, description="题库 ID（question_bank 主键正整数；未开放或不存在统一返回 40401，不泄露存在性）"),
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
    response_model=ApiResponse[BankKnowledgePointsResponse],
    responses=_error_responses(not_found="题库不存在或未开放练习"),
    description=(
        "用途：列出题库内可练习的知识点，供组卷前筛选 knowledge_ids。\n"
        "调用时机：组卷页选择知识点范围；仅返回存在 published 题的知识点（真实 QuestionKnowledge 关联，禁止名称匹配），按可用题量倒序。\n"
        "权限：普通用户 access token；题库未开放/不存在返回 40401。\n"
        "幂等性：只读幂等。\n"
        "写库：否（仅查询）。\n"
        "返回 data：\n"
        "knowledge_points[].knowledge_id: 知识点 ID\n"
        "knowledge_points[].name: 知识点名称\n"
        "knowledge_points[].available_question_count: 该知识点下可练习题量"
    ),
)
def get_open_question_bank_knowledge_points(
    qb_id: int = Path(default=..., ge=1, description="题库 ID（question_bank 主键正整数；未开放或不存在统一返回 40401，不泄露存在性）"),
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
