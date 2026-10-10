"""QuestionDecisionAgent API 路由。"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_admin
from app.models.admin import AdminUser
from app.schemas.common import ApiResponse

router = APIRouter(prefix="/question-plans", tags=["出题计划"])


@router.post(
    "/decision",
    summary="生成出题计划",
    description=(
        "根据用户选择的题库和出题要求，生成结构化的出题计划。"
        "不生成题目内容，不写入数据库。"
    ),
)
async def make_question_decision(
    request: dict,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
) -> ApiResponse:
    """生成出题计划。

    请求格式：
        {
            "question_bank_ids": [1, 4],
            "total_question_count": 20,
            "question_types": ["SINGLE_CHOICE", "SHORT_ANSWER"],
            "difficulty_distribution": {"easy": 40, "medium": 40, "hard": 20}
        }
    """
    from agent.question_decision.agent import QuestionDecisionAgent
    from agent.question_decision.schemas import (
        DifficultyDistribution,
        QuestionDecisionRequest,
    )

    try:
        # 解析请求
        bank_ids = request.get("question_bank_ids", [])
        total_count = request.get("total_question_count", 10)
        question_types = request.get("question_types")
        diff_data = request.get("difficulty_distribution")

        difficulty = None
        if diff_data:
            difficulty = DifficultyDistribution(**diff_data)

        decision_request = QuestionDecisionRequest(
            question_bank_ids=bank_ids,
            total_question_count=total_count,
            question_types=question_types,
            difficulty_distribution=difficulty,
        )

        # 执行决策
        agent = QuestionDecisionAgent(db)
        result = agent.make_decision(decision_request)

        return ApiResponse(data=result.model_dump())

    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"出题决策失败: {e}", exc_info=True)
        return ApiResponse(
            code=50000,
            message=f"出题决策失败: {str(e)}",
            data=None,
        )
