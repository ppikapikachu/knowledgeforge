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
        "根据用户选择的题库和出题要求，生成结构化的出题计划。"
        "不生成题目内容，不写入数据库。"
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
