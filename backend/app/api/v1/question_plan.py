"""QuestionDecisionAgent API 路由。"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_admin
from app.models.admin import AdminUser
from app.schemas.common import ApiResponse
from agent.question_decision.schemas import (
    DifficultyDistribution,
    QuestionDecisionRequest,
    QuestionDecisionResponse,
)

router = APIRouter(prefix="/question-plans", tags=["出题计划"])


@router.post(
    "/decision",
    response_model=ApiResponse[QuestionDecisionResponse],
    summary="生成出题计划",
    description=(
        "用途：根据题库与出题要求生成结构化的出题计划（QuestionDecisionAgent 决策），供后续创建生成任务使用。\n"
        "调用时机：出题配置页点击\"生成出题计划\"预览计划时调用。\n"
        "请求体（QuestionDecisionRequest）：question_bank_ids 题库ID列表（至少1个，必须存在且启用）/"
        "total_question_count 计划总题量/question_types 允许题型列表（可选）/"
        "difficulty_distribution 难度分配百分比（可选，easy+normal+hard 合计 100）。\n"
        "业务行为：只做决策规划——**不生成题目内容、不调用题目生成 LLM、不写入数据库**；决策失败返回 code=50000。\n"
        "返回 data 结构：QuestionDecisionResponse 决策计划（题库分配、题型与难度分布建议）。\n"
        "权限：仅管理员（JWT）。\n"
        "幂等性：只读计算，可安全重复调用。\n"
        "写库：否。"
    ),
)
async def make_question_decision(
    request: QuestionDecisionRequest,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
) -> ApiResponse[QuestionDecisionResponse]:
    """生成出题计划。

    - **question_bank_ids**: 题库 ID 列表（至少 1 个，必须存在且启用）
    - **total_question_count**: 计划总题量
    - **question_types**: 允许题型（可选）
    - **difficulty_distribution**: 难度分配百分比（可选）
    """
    from agent.question_decision.agent import QuestionDecisionAgent

    try:
        agent = QuestionDecisionAgent(db)
        result = agent.make_decision(request)
        return ApiResponse[QuestionDecisionResponse](data=result)

    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"出题决策失败: {e}", exc_info=True)
        return ApiResponse[QuestionDecisionResponse](
            code=50000,
            message=f"出题决策失败: {str(e)}",
            data=None,
        )
