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
from typing import List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_admin
from app.models.admin import AdminUser
from app.schemas.common import ApiErrorResponse, ApiResponse
from agent.knowledge_deduplicate.schemas import ExistingKnowledge
from agent.knowledge_deduplicate.graph import run_dedup_pipeline
from agent.knowledge_extract.schemas import KnowledgeCandidate

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agent", tags=["Agent 测试"])

# 错误响应文档（OpenAPI responses；仅文档用途，不改变运行时 HTTP 状态码）。
# 运行时业务异常（40000/40001/40101/40301/40401/40901 等）统一经全局异常处理器以
# HTTP 400 信封返回；请求体校验失败为 HTTP 422（业务码 42201）；系统内部错误为
# HTTP 500（业务码 50000）。
ERROR_RESPONSES = {
    400: {
        "model": ApiErrorResponse,
        "description": "业务错误（HTTP 400，envelope code 区分）：40101 未认证（访问令牌无效/过期/管理员不存在/已禁用）",
    },
    403: {"model": ApiErrorResponse, "description": "未提供或非法 Authorization 请求头（HTTP 403）"},
    422: {"model": ApiErrorResponse, "description": "请求参数格式校验失败（HTTP 422，code 42201）"},
    500: {"model": ApiErrorResponse, "description": "系统内部错误（HTTP 500，code 50000）"},
}


class KnowledgeDedupMergedItem(BaseModel):
    """去重合并产物（MERGE 判定命中时的合并后知识点，merged_knowledge）。"""

    name: str = Field(description="中文：合并后知识点名称")
    summary: str = Field(description="中文：合并后知识点摘要")
    content: str = Field(description="中文：合并后知识点内容")
    difficulty: int = Field(description="中文：难度（1=简单/2=中等/3=困难）")
    keywords: List[str] = Field(
        default_factory=list, description="中文：合并后关键词列表"
    )


class KnowledgeDedupResultItem(BaseModel):
    """去重判定结果（results 数组元素）。"""

    candidate_name: str = Field(description="中文：候选知识点名称")
    decision: str = Field(
        description="中文：判定结果，NEW=新增 / DUPLICATE=重复丢弃 / MERGE=合并进已有知识点"
    )
    target_knowledge_id: Optional[int] = Field(
        default=None, description="中文：命中/合并目标知识点 ID（NEW 时为空）"
    )
    confidence: float = Field(
        default=0.0, description="中文：判定置信度（0-1）"
    )
    reason: str = Field(default="", description="中文：判定理由说明")
    exact_match: bool = Field(
        default=False, description="中文：是否精确指纹命中（归一化 hash 完全一致）"
    )
    top_similarity: float = Field(
        default=0.0, description="中文：最高相似度得分（保留 4 位小数）"
    )
    method: str = Field(
        default="", description="中文：判定方式（exact_hash/algorithm/llm 等）"
    )
    merged_knowledge: Optional[KnowledgeDedupMergedItem] = Field(
        default=None, description="中文：MERGE 判定时的合并后知识点（其余判定为空）"
    )


class KnowledgeDedupTestResponse(BaseModel):
    """知识点去重测试响应（POST /agent/knowledge-deduplicate/test 的 data）。"""

    total_candidates: int = Field(description="中文：候选知识点总数")
    new_count: int = Field(description="中文：判定为新增（NEW）的数量")
    duplicate_count: int = Field(description="中文：判定为重复（DUPLICATE）的数量")
    merge_count: int = Field(description="中文：判定为合并（MERGE）的数量")
    llm_call_count: int = Field(description="中文：LLM 调用次数")
    embedding_count: int = Field(description="中文：向量计算次数")
    results: List[KnowledgeDedupResultItem] = Field(
        default_factory=list, description="中文：逐候选判定结果列表"
    )
    errors: List[str] = Field(
        default_factory=list, description="中文：运行过程错误列表（正常时为空）"
    )


@router.post(
    "/knowledge-deduplicate/test",
    response_model=ApiResponse[KnowledgeDedupTestResponse],
    responses={
        **ERROR_RESPONSES,
        200: {
            "description": "成功（code=0）。业务错误时 HTTP 仍为 200，用 envelope code（如 40001/50000）标识，前端须检查 code。",
        },
    },
    summary="测试知识点去重 Agent",
    description=(
        "用途：输入候选知识点和已有知识点列表，运行去重 Pipeline（归一化→精确指纹→向量检索→规则判定→LLM 复核）判断 NEW/DUPLICATE/MERGE。\n"
        "调用时机：管理后台 Agent 调试页验证去重效果时调用。\n"
        "请求体（JSON）：\n"
        "  candidates: 候选知识点数组（必填，为空返回业务错误 40001），元素含 name/summary/content/difficulty/keywords/source_chunk_id\n"
        "  existing_knowledge: 已有知识点数组（可选），元素含 id/name/summary/content/difficulty/keywords/similarity\n"
        "三种 decision 语义：\n"
        "- `NEW`：建议新增（target_knowledge_id 为空）\n"
        "- `DUPLICATE`：重复丢弃（target_knowledge_id 指向命中的已有知识点 ID）\n"
        "- `MERGE`：合并进已有知识点（target_knowledge_id 为合并目标 ID，merged_knowledge 为合并后知识点）\n\n"
        "返回 data 结构：\n"
        "  total_candidates: 候选总数\n"
        "  new_count: 判定为新增（NEW）的数量\n"
        "  duplicate_count: 判定为重复（DUPLICATE）的数量\n"
        "  merge_count: 判定为合并（MERGE）的数量\n"
        "  llm_call_count: LLM 调用次数\n"
        "  embedding_count: 向量编码次数\n"
        "  results: 逐条判定结果数组（candidate_name/decision/target_knowledge_id/confidence/reason/exact_match/top_similarity/method/merged_knowledge）\n"
        "  errors: 运行过程错误列表（正常时为空）\n"
        "权限：需要管理员登录。\n"
        "幂等性：只读测试接口，不写数据库（不会写入正式 knowledge 表），可重复调用；\n"
        "注意：LLM 复核较耗时；业务错误（如候选列表为空 code 40001）与超时或模型异常（code 50000）时 HTTP 仍为 200，用 envelope code 标识，前端须检查 code。"
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
