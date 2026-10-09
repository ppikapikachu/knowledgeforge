"""KnowledgeRelationAgent 测试 API 路由。

提供只读的关系判断测试接口，不写入 knowledge_relation 表。
"""

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_admin
from app.models.admin import AdminUser
from app.models.knowledge import Knowledge
from app.schemas.common import ApiResponse
from agent.knowledge_relation.schemas import (
    RelationKnowledgeInput,
    RelationTestRequest,
    RelationTestResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agent", tags=["Agent 测试"])


@router.post(
    "/knowledge-relation/test",
    summary="测试知识点关系判断 Agent",
    description=(
        "判断锚点知识点与候选知识点之间的关系（prerequisite/related/extension/contrast）。"
        "支持三种模式：\n\n"
        "1. **人工候选模式**：传 `source_knowledge` + `candidates`，跳过向量检索\n"
        "2. **指定ID模式**：传 `source_knowledge_id` + `candidate_knowledge_ids`，从数据库读取\n"
        "3. **自动检索模式**：传 `source_knowledge_id`，自动向量检索候选\n\n"
        "注意：此接口**不会写入 knowledge_relation 表**，仅返回判断结果。"
    ),
    response_model=ApiResponse[RelationTestResponse],
)
async def test_knowledge_relation(
    request: RelationTestRequest,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
) -> ApiResponse[RelationTestResponse]:
    """测试 KnowledgeRelationAgent，返回关系判断结果。"""
    from agent.knowledge_relation.graph import run_relation_test

    try:
        # ---- 解析锚点 ----
        if request.source_knowledge:
            source = RelationKnowledgeInput(
                id=request.source_knowledge.id,
                name=request.source_knowledge.name,
                summary=request.source_knowledge.summary or "",
                content=(request.source_knowledge.content or "")[:500],
                keywords=request.source_knowledge.keywords or [],
            )
        elif request.source_knowledge_id:
            knowledge = db.query(Knowledge).filter(
                Knowledge.id == request.source_knowledge_id
            ).first()
            if not knowledge:
                return ApiResponse[RelationTestResponse](
                    code=40401,
                    message=f"知识点 {request.source_knowledge_id} 不存在",
                    data=None,
                )
            source = RelationKnowledgeInput(
                id=knowledge.id,
                name=knowledge.name,
                summary=knowledge.summary or "",
                content=(knowledge.content or "")[:500],
                keywords=knowledge.keywords or [],
            )
        else:
            return ApiResponse[RelationTestResponse](
                code=40001,
                message="必须提供 source_knowledge_id 或 source_knowledge",
                data=None,
            )

        # ---- 解析候选 ----
        provided_candidates = None
        if request.candidates is not None:
            provided_candidates = [
                RelationKnowledgeInput(
                    id=c.id, name=c.name,
                    summary=c.summary or "",
                    content=(c.content or "")[:500],
                    keywords=c.keywords or [],
                )
                for c in request.candidates
            ]

        resolved_candidates = None
        if request.candidate_knowledge_ids and not provided_candidates:
            resolved_candidates = []
            for kid in request.candidate_knowledge_ids:
                k = db.query(Knowledge).filter(Knowledge.id == kid).first()
                if k:
                    resolved_candidates.append(RelationKnowledgeInput(
                        id=k.id, name=k.name,
                        summary=k.summary or "",
                        content=(k.content or "")[:500],
                        keywords=k.keywords or [],
                    ))

        # ---- 执行判断 ----
        result = run_relation_test(
            source=source,
            provided_candidates=provided_candidates,
            candidate_knowledge_ids=request.candidate_knowledge_ids,
            resolved_candidates=resolved_candidates,
            top_k=request.top_k,
        )

        # 按 min_confidence 过滤
        if request.min_confidence > 0:
            result["evaluations"] = [
                e for e in result["evaluations"]
                if e.get("confidence", 0) >= request.min_confidence
            ]

        result["min_confidence"] = request.min_confidence

        return ApiResponse[RelationTestResponse](data=result)

    except Exception as e:
        logger.error(f"关系判断测试失败: {e}", exc_info=True)
        return ApiResponse[RelationTestResponse](
            code=50000,
            message=f"关系判断测试失败: {str(e)}",
            data=None,
        )
