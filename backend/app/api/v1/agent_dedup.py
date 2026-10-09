"""知识点去重 Agent 测试 API 路由模块。

本模块提供 KnowledgeDeduplicateAgent 的测试接口。

重要约束：
    - 此接口不会写入正式 knowledge 表
    - 不会接入正式 ImportTask
    - 仅用于验证去重 Pipeline 的判定效果

使用方法：
    1. 通过 Swagger 或 curl 发送候选知识点 + 已有知识点列表
    2. Pipeline 执行：标准化 → 精确匹配 → 向量检索 → 规则判定 → LLM 判定
    3. 返回去重决策结果（NEW/DUPLICATE/MERGE）
"""

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_admin
from app.models.admin import AdminUser
from app.schemas.common import ApiResponse
from agent.knowledge_deduplicate.schemas import ExistingKnowledge
from agent.knowledge_deduplicate.graph import run_dedup_pipeline
from agent.knowledge_extract.schemas import KnowledgeCandidate

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agent", tags=["Agent 测试"])


@router.post(
    "/knowledge-deduplicate/test",
    summary="测试知识点去重 Agent",
    description=(
        "输入候选知识点和已有知识点列表，运行去重 Pipeline 判断 NEW/DUPLICATE/MERGE。"
        "注意：此接口不会写入正式 knowledge 表，仅返回判定结果。"
    ),
)
async def test_knowledge_deduplicate(
    request: dict,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
) -> ApiResponse:
    """测试 KnowledgeDeduplicateAgent。

    请求格式：
        {
            "candidates": [
                {
                    "name": "Java线程池",
                    "summary": "线程池用于复用线程",
                    "content": "...",
                    "difficulty": 2,
                    "keywords": ["Java", "线程池"],
                    "source_chunk_id": "chunk_001"
                }
            ],
            "existing_knowledge": [
                {
                    "id": 1001,
                    "name": "Java线程池",
                    "summary": "Java线程池的概念和使用",
                    "content": "...",
                    "difficulty": 2,
                    "keywords": ["Java", "线程池"],
                    "similarity": 0.96
                }
            ]
        }

    响应格式：
        {
            "code": 0,
            "message": "success",
            "data": {
                "total_candidates": 1,
                "new_count": 0,
                "duplicate_count": 1,
                "merge_count": 0,
                "llm_call_count": 0,
                "embedding_count": 0,
                "results": [...]
            }
        }
    """
    try:
        # 解析请求数据
        candidates_data = request.get("candidates", [])
        existing_data = request.get("existing_knowledge", [])

        if not candidates_data:
            return ApiResponse(code=40001, message="候选知识点列表不能为空", data=None)

        # 转换为 Pydantic 模型
        candidates = []
        for c in candidates_data:
            candidates.append(KnowledgeCandidate(
                name=c.get("name", ""),
                summary=c.get("summary", ""),
                content=c.get("content", ""),
                difficulty=c.get("difficulty", 2),
                keywords=c.get("keywords", []),
                source_chunk_id=c.get("source_chunk_id", "test"),
            ))

        existing_list = []
        for e in existing_data:
            existing_list.append(ExistingKnowledge(
                id=e.get("id", 0),
                name=e.get("name", ""),
                summary=e.get("summary", ""),
                content=e.get("content", ""),
                difficulty=e.get("difficulty", 2),
                keywords=e.get("keywords", []),
                similarity=e.get("similarity", 0.0),
            ))

        # 执行去重 Pipeline
        logger.info(
            f"开始去重测试: {len(candidates)} 个候选, "
            f"{len(existing_list)} 个已有知识点"
        )

        result = run_dedup_pipeline(
            candidates=candidates,
            existing_knowledge_list=existing_list,
            sync_existing_to_vector=True,
        )

        # 构造响应
        response_data = {
            "total_candidates": result.total_candidates,
            "new_count": result.new_count,
            "duplicate_count": result.duplicate_count,
            "merge_count": result.merge_count,
            "llm_call_count": result.llm_call_count,
            "embedding_count": result.embedding_count,
            "results": [
                {
                    "candidate_name": r.candidate_name,
                    "decision": r.decision.decision,
                    "target_knowledge_id": r.decision.target_knowledge_id,
                    "confidence": r.decision.confidence,
                    "reason": r.decision.reason,
                    "exact_match": r.exact_match,
                    "top_similarity": round(r.top_similarity, 4),
                    "method": r.method,
                    "merged_knowledge": {
                        "name": r.decision.merged_knowledge.name,
                        "summary": r.decision.merged_knowledge.summary,
                        "content": r.decision.merged_knowledge.content,
                        "difficulty": r.decision.merged_knowledge.difficulty,
                        "keywords": r.decision.merged_knowledge.keywords,
                    } if r.decision.merged_knowledge else None,
                }
                for r in result.results
            ],
            "errors": result.errors,
        }

        return ApiResponse(data=response_data)

    except Exception as e:
        logger.error(f"去重测试失败: {e}", exc_info=True)
        return ApiResponse(
            code=50000,
            message=f"去重测试失败: {str(e)}",
            data=None,
        )
