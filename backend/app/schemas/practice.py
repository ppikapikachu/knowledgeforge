"""练习相关请求/响应 Schema（DTO 白名单投影，禁止 ORM 直接序列化）。"""

from decimal import Decimal
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.common import ApiResponse


class DifficultyDistribution(BaseModel):
    easy: int = Field(default=0, ge=0, le=200, description="简单题数量（difficulty=1），默认 0")
    normal: int = Field(default=0, ge=0, le=200, description="中等题数量（difficulty=2），默认 0")
    hard: int = Field(default=0, ge=0, le=200, description="困难题数量（difficulty=3），默认 0")


class AssemblePaperRequest(BaseModel):
    question_bank_id: int = Field(
        ..., ge=1,
        description="题库 ID（必填）；必须为已开放练习（is_available_for_practice=true）的题库",
    )
    title: Optional[str] = Field(
        default=None, max_length=128,
        description="试卷标题（可选；未传时按项目约定生成默认标题）",
    )
    knowledge_ids: Optional[List[int]] = Field(
        default=None,
        description="可选：限定知识点；每个 ID 必须与指定题库存在真实关联，无效 ID 直接参数错误",
    )
    question_type_counts: Dict[str, int] = Field(
        default_factory=dict,
        description="题型数量分布，键限 SINGLE_CHOICE/MULTIPLE_CHOICE/TRUE_FALSE/SHORT_ANSWER，如 {\"SINGLE_CHOICE\": 3, \"TRUE_FALSE\": 2}；与 difficulty_distribution 各项之和须等于 total_count",
    )
    difficulty_distribution: DifficultyDistribution = Field(
        default_factory=DifficultyDistribution,
        description="难度分布 {easy: 2, normal: 2, hard: 1}",
    )
    total_count: int = Field(..., ge=1, le=200, description="题目数量，必须与两个分布之和一致")
    allow_partial: bool = Field(
        default=False, description="库存不足时是否允许按可用量出卷（默认不允许，不静默少题）"
    )
    selection_strategy: str = Field(default="random", description="目前仅支持 random")

    @field_validator("question_type_counts")
    @classmethod
    def _check_type_counts(cls, v: Dict[str, int]) -> Dict[str, int]:
        allowed = {"SINGLE_CHOICE", "MULTIPLE_CHOICE", "TRUE_FALSE", "SHORT_ANSWER"}
        for k, n in (v or {}).items():
            if k not in allowed:
                raise ValueError(f"不支持的题型: {k}")
            if not isinstance(n, int) or n < 0:
                raise ValueError(f"题型数量必须为非负整数: {k}")
        return v

    @field_validator("selection_strategy")
    @classmethod
    def _check_strategy(cls, v: str) -> str:
        if v != "random":
            raise ValueError("selection_strategy 目前仅支持 random")
        return v


class DraftSaveRequest(BaseModel):
    answer: Any = Field(        default=None,
        description="草稿答案（按题型 JSON 值：单选/简答=字符串，多选=字符串数组，判断=布尔；仅写草稿不判分）",
    )


class MarkRequest(BaseModel):
    is_marked: bool = Field(..., description="标记状态（true=标记该题为疑难题，false=取消标记；与作答状态相互独立）")


class ProgressRequest(BaseModel):
    current_item_order: int = Field(..., ge=1, le=200, description="当前题序（1~试卷题量 total_count，用于恢复练习位置，不改变答题状态与统计）")


class SubmitAnswerRequest(BaseModel):
    """提交答案请求：answer 按题型为不同 JSON 值（单选=字符串、多选=字符串数组、判断=布尔、简答=字符串）。

    只接受 answer/idempotency_key/time_spent_ms 三个字段，
    不接受 app_user_id/question_id/correct_answer/is_correct/score（由服务端判定或派生）。
    """
    # 严格模式：多余字段（含伪造 is_correct/score/app_user_id）一律拒绝（docs/14 补充 §9.2）
    model_config = ConfigDict(extra="forbid")

    answer: Any = Field(        ..., description="答案（按题型 JSON 值：单选=选项键字符串、多选=选项键数组、判断=布尔、简答=文本）"
    )
    idempotency_key: str = Field(..., min_length=8, max_length=64, description="幂等键（8~64 位）：同 key 同内容重复提交返回原答题记录（idempotent=true），同 key 不同内容报 40001 幂等冲突")
    time_spent_ms: Optional[int] = Field(default=None, ge=0, le=86400000, description="本题作答耗时（毫秒，非负，上限 24 小时；可选，仅作统计参考）")

    @field_validator("idempotency_key")
    @classmethod
    def _check_key(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("idempotency_key 不能为空")
        return v


# ==================== 响应模型（OpenAPI 文档用） ====================
# practice 路由 handler 直接返回 JSONResponse（success_response/paginated_response），
# FastAPI 不会用 response_model 过滤响应体，以下模型仅用于 /docs 响应结构文档，无运行时影响。
# 答案安全：correct_answer/explanation/is_correct 仅在题目已提交或会话 completed 时返回，
# in_progress/abandoned 会话的未提交题只有题目面字段，相关字段一律 Optional 并注明条件。


# 按题型的作答值：单选/简答=字符串、多选=字符串数组、判断=布尔或字符串
AnswerValue = Union[str, bool, List[str]]


class AssemblyConfigInfo(BaseModel):
    """组卷参数快照（practice_paper.assembly_config）。

    来自组卷签名；历史行可能缺键，故字段均可缺省。
    """

    question_bank_id: Optional[int] = Field(default=None, description="组卷来源题库 ID")
    knowledge_ids: List[int] = Field(
        default_factory=list,
        description="组卷限定的知识点 ID 列表（升序去重；未限定知识点为空列表）",
    )
    question_type_counts: Dict[str, int] = Field(
        default_factory=dict,
        description="题型数量分布：键=题型（SINGLE_CHOICE/MULTIPLE_CHOICE/TRUE_FALSE/SHORT_ANSWER），值=题量",
    )
    difficulty_distribution: DifficultyDistribution = Field(
        default_factory=DifficultyDistribution,
        description="难度分布（easy/normal/hard 各难度题量）",
    )
    total_count: Optional[int] = Field(default=None, description="组卷题目总数")
    selection_strategy: Optional[str] = Field(default=None, description="抽题策略（当前固定 random）")


class PaperResponse(BaseModel):
    """试卷快照头（practice_paper 不可变快照）。

    作为归档接口的 data 载荷，也用于组卷/详情等响应的 paper 字段。
    """

    paper_id: int = Field(description="试卷 ID")
    title: str = Field(description="试卷标题")
    question_count: int = Field(description="试卷题量")
    total_score: float = Field(description="试卷总分")
    status: str = Field(description="试卷状态：ready=可练习，archived=已归档（不可再发起新会话）")
    source_question_bank_id: Optional[int] = Field(default=None, description="来源题库 ID")
    assembly_config: Optional[AssemblyConfigInfo] = Field(
        default=None, description="组卷参数快照（题型/难度分布等）；历史/异常数据可能为 null"
    )
    snapshot_version: int = Field(description="快照版本（当前固定 1）")
    snapshot_hash: str = Field(description="快照内容哈希（SHA-256）")
    created_at: Optional[str] = Field(default=None, description="组卷时间（ISO 8601 字符串）")
    archived_at: Optional[str] = Field(default=None, description="归档时间（ISO 8601；未归档为 null）")


class SessionResponse(BaseModel):
    """练习会话（practice_session）。

    作为创建/恢复/完成/放弃会话接口的 data 载荷，也用于组卷/详情等响应的 session 字段。
    """

    session_id: int = Field(description="练习会话 ID")
    paper_id: int = Field(description="所属试卷 ID")
    mode: str = Field(description="练习模式（固定 practice）")
    status: str = Field(description="会话状态：in_progress=进行中，completed=已完成，abandoned=已放弃")
    current_item_order: int = Field(description="当前题序（从 1 开始）")
    total_count: int = Field(description="题目总数")
    answered_count: int = Field(description="已作答题数")
    correct_count: int = Field(description="判分正确题数")
    incorrect_count: int = Field(description="判分错误题数")
    ungraded_count: int = Field(description="未判分题数（如简答题）")
    started_at: Optional[str] = Field(default=None, description="开始时间（ISO 8601）")
    last_active_at: Optional[str] = Field(default=None, description="最后活跃时间（ISO 8601）")
    completed_at: Optional[str] = Field(default=None, description="完成时间（ISO 8601；未完成为 null）")
    abandoned_at: Optional[str] = Field(default=None, description="放弃时间（ISO 8601；未放弃为 null）")
    duration_ms: Optional[int] = Field(default=None, description="作答耗时（毫秒，完成时计算）")


class SessionProgressInfo(BaseModel):
    """会话进度（进度接口与提交接口返回的统计摘要）。"""

    session_id: int = Field(description="练习会话 ID")
    status: str = Field(description="会话状态：in_progress|completed|abandoned")
    total_count: int = Field(description="题目总数")
    answered_count: int = Field(description="已作答题数")
    correct_count: int = Field(description="判分正确题数")
    incorrect_count: int = Field(description="判分错误题数")
    ungraded_count: int = Field(description="未判分题数")
    current_item_order: int = Field(description="当前题序（从 1 开始）")


class RecentSessionInfo(BaseModel):
    """最近一次练习会话摘要（试卷列表 recent_session 字段）。"""

    session_id: int = Field(description="练习会话 ID")
    status: str = Field(description="会话状态：in_progress|completed|abandoned")
    answered_count: int = Field(description="已作答题数")
    total_count: int = Field(description="题目总数")
    last_active_at: Optional[str] = Field(default=None, description="最后活跃时间（ISO 8601）")


class QuestionOptionInfo(BaseModel):
    """题目选项（白名单投影，不含 is_correct）。"""

    option_key: Optional[str] = Field(default=None, description="选项键（如 A/B/C/D）")
    content: Optional[str] = Field(default=None, description="选项文本")


class QuestionKnowledgePointInfo(BaseModel):
    """题目关联知识点（快照投影）。"""

    knowledge_id: int = Field(description="知识点 ID")
    name: str = Field(description="知识点名称")
    difficulty: int = Field(description="知识点难度码（1=easy，2=normal，3=hard）")
    importance_level: str = Field(description="知识点重要度（字符串取值）")


class QuestionSnapshotItem(BaseModel):
    """题目面白名单投影（item_public_projection）。

    绝不含 correct_answer/explanation/is_correct（答案安全）。
    """

    paper_item_id: int = Field(description="题目项 ID（practice_paper_item 主键）")
    sort_order: int = Field(description="题目序号（从 1 开始）")
    question_type: str = Field(
        description="题型：SINGLE_CHOICE=单选，MULTIPLE_CHOICE=多选，TRUE_FALSE=判断，SHORT_ANSWER=简答"
    )
    difficulty: int = Field(description="难度码：1=easy，2=normal，3=hard")
    difficulty_name: str = Field(description="难度名：easy|normal|hard")
    score: float = Field(description="本题分值")
    content: str = Field(description="题干内容")
    options: List[QuestionOptionInfo] = Field(default_factory=list, description="选项列表（判断/简答可能为空）")
    knowledge_points: List[QuestionKnowledgePointInfo] = Field(
        default_factory=list, description="关联知识点列表"
    )


class QuestionResultItem(QuestionSnapshotItem):
    """题目结果投影（item_result_projection）：题目面 + 判分结果。

    答案安全：correct_answer/explanation/is_correct 仅在本题已提交或会话 completed 时返回；
    in_progress/abandoned 会话的未提交题只有题目面字段（下列判分字段缺省）。
    """

    correct_answer: Optional[str] = Field(
        default=None, description="正确答案文本（答案安全：仅已提交或 completed 会话返回）"
    )
    explanation: Optional[str] = Field(
        default=None, description="答案解析（答案安全：仅已提交或 completed 会话返回）"
    )
    your_answer: Optional[AnswerValue] = Field(
        default=None,
        description="我的作答（单选/简答=字符串、多选=字符串数组、判断=布尔或字符串；未作答为 null）",
    )
    is_correct: Optional[bool] = Field(
        default=None, description="是否判分正确（未提交题不返回；简答未评分为 null）"
    )
    grading_status: Optional[str] = Field(
        default=None, description="判分状态：graded=已判分，ungraded=未判分（简答）"
    )
    first_submitted_at: Optional[str] = Field(default=None, description="首次提交时间（ISO 8601）")
    last_submitted_at: Optional[str] = Field(default=None, description="最近提交时间（ISO 8601）")


class SessionResultItem(QuestionResultItem):
    """整卷结果 items[] 元素：题目结果投影 + 题目项状态。"""

    status: str = Field(description="题目项状态：unanswered=未作答，draft_saved=有草稿，answered=已提交")


class SessionDetailItem(QuestionResultItem):
    """会话详情 items[] 元素：状态化投影。

    已提交题含判分结果（正确答案/解析等）；未提交题含 draft_answer 草稿（不含正确答案/解析/is_correct）。
    """

    status: str = Field(description="题目项状态：unanswered=未作答，draft_saved=有草稿，answered=已提交")
    is_marked: bool = Field(description="是否标记为疑难题（与作答状态独立）")
    draft_answer: Optional[AnswerValue] = Field(
        default=None,
        description="草稿作答（仅未提交题返回；单选/简答=字符串、多选=字符串数组、判断=布尔或字符串）",
    )


class AssemblePaperResponse(BaseModel):
    """组卷生成练习卷接口的 data 载荷。"""

    paper: PaperResponse = Field(description="试卷快照头（不可变快照）")
    session: Optional[SessionResponse] = Field(
        default=None, description="自动创建的首个练习会话（幂等命中且原请求无会话时为 null）"
    )
    idempotent: bool = Field(
        description="是否幂等命中返回的原卷（true=同 Idempotency-Key 重复请求返回原卷，false=本次新生成）"
    )


class PaperListItem(PaperResponse):
    """试卷列表 items[] 元素：试卷快照头 + 最近会话摘要。"""

    recent_session: Optional[RecentSessionInfo] = Field(
        default=None, description="最近一次练习会话摘要（从未练习为 null）"
    )


class PaperDetailResponse(PaperResponse):
    """试卷详情 data 载荷：试卷快照头字段平铺 + 题目面投影列表（无嵌套 paper 键）。"""

    items: List[QuestionSnapshotItem] = Field(
        default_factory=list, description="题目面投影列表（白名单投影，不含正确答案/解析）"
    )


class SessionListItem(SessionResponse):
    """练习会话列表 items[] 元素（字段同练习会话）。"""


class SessionDetailResponse(BaseModel):
    """练习会话详情接口的 data 载荷。"""

    session: SessionResponse = Field(description="会话信息")
    paper: PaperResponse = Field(description="试卷快照头")
    items: List[SessionDetailItem] = Field(
        default_factory=list,
        description="题目状态化投影列表（答案安全：未提交题不含正确答案/解析/is_correct）",
    )
    progress: SessionProgressInfo = Field(description="会话进度")


class SessionResultSummaryInfo(BaseModel):
    """整卷结果汇总（result 接口 summary 字段）。"""

    total_count: int = Field(description="题目总数")
    answered_count: int = Field(description="已作答题数")
    correct_count: int = Field(description="判分正确题数")
    incorrect_count: int = Field(description="判分错误题数")
    ungraded_count: int = Field(description="未判分题数")
    total_score: float = Field(description="试卷总分")
    earned_score: float = Field(description="累计得分")


class SessionResultResponse(BaseModel):
    """整卷结果与解析接口的 data 载荷。"""

    session: SessionResponse = Field(description="会话信息")
    items: List[SessionResultItem] = Field(
        default_factory=list,
        description="题目结果投影列表（答案安全：in_progress/abandoned 会话未提交题不含正确答案/解析）",
    )
    summary: SessionResultSummaryInfo = Field(description="结果汇总")


class AnswerRecordItem(BaseModel):
    """答题记录 answers[] 元素（question_answer_record）。"""

    id: int = Field(description="答题记录 ID")
    question_id: Optional[int] = Field(default=None, description="源题目 ID（快照无源题时可能为 null）")
    practice_paper_item_id: int = Field(description="题目项 ID（practice_paper_item 主键）")
    user_answer: Optional[str] = Field(default=None, description="用户作答文本（规范化后的文本表示）")
    is_correct: Optional[bool] = Field(default=None, description="是否判分正确（null=未评分简答题）")
    grading_status: str = Field(description="判分状态：graded|ungraded")
    score: Optional[float] = Field(default=None, description="本题得分（未评分为 null）")
    time_spent_ms: Optional[int] = Field(default=None, description="作答耗时（毫秒）")
    idempotency_key: Optional[str] = Field(default=None, description="提交幂等键（8~64 位；历史/兼容记录可能为 null）")
    created_at: Optional[str] = Field(default=None, description="提交时间（ISO 8601）")


class SessionAnswersResponse(BaseModel):
    """会话答题记录列表接口的 data 载荷。"""

    session_id: int = Field(description="练习会话 ID")
    answers: List[AnswerRecordItem] = Field(default_factory=list, description="答题记录列表（每次提交一条）")


class DraftAnswerInfo(BaseModel):
    """草稿内容（draft_answer 字段的 {answer: ...} 结构）。"""

    answer: Optional[AnswerValue] = Field(
        default=None,
        description="草稿作答值（单选/简答=字符串、多选=字符串数组、判断=布尔或字符串）",
    )


class DraftSaveResponse(BaseModel):
    """保存题目草稿接口的 data 载荷。"""

    session_id: int = Field(description="练习会话 ID")
    paper_item_id: int = Field(description="题目项 ID")
    status: str = Field(
        description="题目项保存后状态：draft_saved=有草稿；已提交题目保持 answered"
    )
    draft_answer: DraftAnswerInfo = Field(description="最新草稿内容（{answer: 作答值}）")


class MarkItemResponse(BaseModel):
    """标记/取消标记题目接口的 data 载荷。"""

    paper_item_id: int = Field(description="题目项 ID")
    is_marked: bool = Field(description="当前标记状态（true=已标记，false=已取消）")


class ProgressUpdateResponse(BaseModel):
    """更新练习进度接口的 data 载荷。"""

    session_id: int = Field(description="练习会话 ID")
    current_item_order: int = Field(description="当前题序（1..total_count，越界报 40001）")


class SubmitAnswerResponse(BaseModel):
    """提交答题并判分接口的 data 载荷。"""

    answer_record_id: int = Field(description="答题记录 ID")
    idempotent: bool = Field(
        description="是否幂等命中（true=同 idempotency_key 重复提交返回原记录）"
    )
    paper_item_id: int = Field(description="题目项 ID")
    question_id: Optional[int] = Field(default=None, description="源题目 ID（快照无源题时可能为 null）")
    is_correct: Optional[bool] = Field(default=None, description="是否判分正确（null=未评分简答题）")
    grading_status: str = Field(description="判分状态：graded=已判分，ungraded=未判分")
    score: Optional[float] = Field(default=None, description="本题得分（未评分为 null）")
    correct_answer: Optional[str] = Field(default=None, description="正确答案（仅提交后返回）")
    explanation: Optional[str] = Field(default=None, description="答案解析（仅提交后返回）")
    session_progress: SessionProgressInfo = Field(description="会话最新进度")


class OpenQuestionBankResponse(BaseModel):
    """开放练习题库对外负载（question_bank 库存统计 + 可组卷状态）。"""

    id: int = Field(description="题库 ID")
    code: str = Field(description="题库编码")
    name: str = Field(description="题库名称")
    description: str = Field(description="题库描述（无描述为空串）")
    available_question_count: int = Field(description="可练习题量（published 题数）")
    question_type_counts: Dict[str, int] = Field(
        default_factory=dict,
        description="各题型可练习题量：键=题型（SINGLE_CHOICE/MULTIPLE_CHOICE/TRUE_FALSE/SHORT_ANSWER），值=题量",
    )
    difficulty_counts: Dict[str, int] = Field(
        default_factory=dict,
        description="各难度可练习题量：键=难度（easy/normal/hard），值=题量",
    )
    can_assemble: bool = Field(description="是否可组卷（有可练习题时 true）")
    unavailable_reason: Optional[str] = Field(
        default=None, description="不可组卷原因（可组卷为 null；空库存为“暂无可练习题目”）"
    )


class OpenQuestionBankItem(OpenQuestionBankResponse):
    """开放练习题库列表 items[] 元素（字段同题库详情）。"""


class BankKnowledgePointItem(BaseModel):
    """题库可练习知识点 knowledge_points[] 元素。"""

    knowledge_id: int = Field(description="知识点 ID")
    name: str = Field(description="知识点名称")
    available_question_count: int = Field(description="该知识点下可练习题量")


class BankKnowledgePointsResponse(BaseModel):
    """题库可练习知识点接口的 data 载荷。"""

    question_bank_id: int = Field(description="题库 ID")
    knowledge_points: List[BankKnowledgePointItem] = Field(
        default_factory=list, description="可练习知识点列表（按可用题量倒序）"
    )


class InsufficientStockErrorData(BaseModel):
    """组卷库存不足错误的 data（allow_partial=false 且库存不足时返回，零落库）。"""

    error: str = Field(default="insufficient_stock", description="错误类型标识（固定 insufficient_stock）")
    requested_count: int = Field(description="请求题目数量（total_count）")
    available_count: int = Field(description="题库实际可用题目数量")
    missing_count: int = Field(description="缺少题目数量")


class InsufficientStockErrorResponse(ApiResponse[InsufficientStockErrorData]):
    """库存不足错误信封示例（code=40001，data=InsufficientStockErrorData）。"""
