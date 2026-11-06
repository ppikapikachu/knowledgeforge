"""Agent 测试 API 路由模块。

本模块提供 KnowledgeExtractAgent 的测试接口。

重要约束：
    - 此接口不会写入正式 knowledge 表
    - 此接口不会接入正式 ImportTask
    - 仅用于验证 Agent 提取效果

使用方法：
    1. 通过 Swagger 或 curl 上传文件
    2. Agent 解析文件 → 分块 → LLM 提取 → 返回结构化结果
    3. 检查返回的 knowledge_points 是否合理

接口地址：
    POST /api/v1/agent/knowledge-extract/test
"""

import logging
import os
import tempfile
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, UploadFile, File
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_admin
from app.models.admin import AdminUser
from app.schemas.common import ApiErrorResponse, ApiResponse
from app.utils.file import is_allowed_file

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


class KnowledgeExtractPointItem(BaseModel):
    """知识点抽取候选（knowledge_points 数组元素）。

    注：此处为接口响应投影，不含内部候选的 importance_level 字段。
    """

    name: str = Field(description="中文：知识点名称")
    summary: str = Field(description="中文：知识点摘要")
    content: str = Field(description="中文：知识点内容")
    difficulty: int = Field(description="中文：难度（1=简单/2=中等/3=困难）")
    keywords: List[str] = Field(
        default_factory=list, description="中文：关键词列表"
    )
    source_chunk_id: str = Field(description="中文：来源文档分块 ID")
    source_title: Optional[str] = Field(
        default=None, description="中文：来源标题（可空）"
    )
    source_page_start: Optional[int] = Field(
        default=None, description="中文：来源起始页码（可空）"
    )
    source_page_end: Optional[int] = Field(
        default=None, description="中文：来源结束页码（可空）"
    )


class KnowledgeExtractTestResponse(BaseModel):
    """知识点提取测试响应（POST /agent/knowledge-extract/test 的 data）。"""

    run_id: str = Field(description="中文：本次提取运行 ID")
    file_name: str = Field(description="中文：上传文件名")
    chunk_count: int = Field(description="中文：文档分块数")
    knowledge_count: int = Field(description="中文：抽取到的知识点数量")
    knowledge_points: List[KnowledgeExtractPointItem] = Field(
        default_factory=list, description="中文：抽取的知识点列表"
    )
    errors: List[str] = Field(
        default_factory=list, description="中文：运行过程错误列表（正常时为空）"
    )


@router.post(
    "/knowledge-extract/test",
    response_model=ApiResponse[KnowledgeExtractTestResponse],
    responses={
        **ERROR_RESPONSES,
        200: {
            "description": "成功（code=0）。业务错误时 HTTP 仍为 200，用 envelope code（如 40001/50000）标识，前端须检查 code。",
        },
    },
    summary="测试知识点提取 Agent",
    description=(
        "用途：上传文档文件（pdf/docx/txt/md），运行 KnowledgeExtractAgent（解析→分块→LLM 抽取→合并）提取知识点，返回结构化测试结果。\n"
        "调用时机：管理后台 Agent 调试页验证抽取效果时调用；正式导入请走导入任务接口。\n"
        "请求体（multipart/form-data）：\n"
        "  file: 上传文件，仅支持 pdf/docx/txt/md，大小上限 50MB，类型或大小不符返回业务错误 40001\n"
        "返回 data 结构：\n"
        "  run_id: 本次提取运行 ID\n"
        "  file_name: 上传文件名\n"
        "  chunk_count: 文档分块数量\n"
        "  knowledge_count: 抽取的知识点数量\n"
        "  knowledge_points: 抽取的知识点数组（name/summary/content/difficulty/keywords/source_chunk_id/source_title/source_page_start/source_page_end）\n"
        "  errors: 运行过程错误列表（正常时为空）\n"
        "权限：需要管理员登录。\n"
        "幂等性：只读测试接口，不写数据库（不会写入正式 knowledge 表），可重复调用；\n"
        "注意：LLM 抽取较耗时；业务错误（如文件名为空/类型不符/超过 50MB，code 40001）与超时或模型异常（code 50000）时 HTTP 仍为 200，用 envelope code 标识，前端须检查 code。"
    ),
)
async def test_knowledge_extract(
    file: UploadFile = File(..., description="上传文件：仅 pdf/docx/txt/md 四种类型，文件名不能为空，大小不超过 50MB"),
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
) -> ApiResponse:
    """测试 KnowledgeExtractAgent：上传文件 → 提取知识点 → 返回结果。

    处理流程：
        1. 校验文件名和文件类型
        2. 读取文件内容，检查大小限制（50MB）
        3. 保存到临时文件（Agent 需要文件路径来解析）
        4. 调用 run_extraction 执行 Agent 工作流
        5. 将结果转换为 JSON 响应
        6. 清理临时文件

    请求方式：
        POST /api/v1/agent/knowledge-extract/test
        Content-Type: multipart/form-data
        Body: file=<文件>

    响应示例：
        {
            "code": 0,
            "message": "success",
            "data": {
                "run_id": "run_a1b2c3d4e5f6",
                "file_name": "android-interview.txt",
                "chunk_count": 5,
                "knowledge_count": 12,
                "knowledge_points": [...],
                "errors": []
            }
        }


    """
    from agent.knowledge_extract.graph import run_extraction

    # ---- 1. 校验文件名 ----
    if not file.filename:
        return ApiResponse(code=40001, message="文件名不能为空", data=None)

    # ---- 2. 校验文件类型 ----
    if not is_allowed_file(file.filename):
        return ApiResponse(
            code=40001,
            message="不支持的文件类型，允许: pdf, docx, txt, md",
            data=None,
        )

    # ---- 3. 读取文件内容并检查大小 ----
    content = await file.read()
    if len(content) > 50 * 1024 * 1024:  # 50MB 限制
        return ApiResponse(code=40001, message="文件过大，最大 50MB", data=None)

    # ---- 4. 保存到临时文件 ----
    # Agent 的 DocumentParser 需要文件路径来解析
    # 使用 tempfile 创建临时目录，任务完成后清理
    ext = os.path.splitext(file.filename)[1]
    temp_dir = tempfile.mkdtemp(prefix="agent_test_")
    temp_path = os.path.join(temp_dir, f"{uuid.uuid4().hex}{ext}")

    try:
        with open(temp_path, "wb") as f:
            f.write(content)

        # ---- 5. 执行 Agent 提取 ----
        logger.info(f"开始 Agent 测试，文件: {file.filename}")
        result = run_extraction(file_path=temp_path, file_name=file.filename)

        # ---- 6. 构造响应数据 ----
        response_data = {
            "run_id": result.run_id,
            "file_name": result.file_name,
            "chunk_count": result.chunk_count,
            "knowledge_count": result.knowledge_count,
            "knowledge_points": [
                {
                    "name": kp.name,
                    "summary": kp.summary,
                    "content": kp.content,
                    "difficulty": kp.difficulty,
                    "keywords": kp.keywords,
                    "source_chunk_id": kp.source_chunk_id,
                    "source_title": kp.source_title,
                    "source_page_start": kp.source_page_start,
                    "source_page_end": kp.source_page_end,
                }
                for kp in result.knowledge_points
            ],
            "errors": result.errors,
        }

        return ApiResponse(data=response_data)

    except Exception as e:
        logger.error(f"Agent 测试失败: {e}", exc_info=True)
        return ApiResponse(
            code=50000,
            message=f"Agent 执行失败: {str(e)}",
            data=None,
        )
    finally:
        # ---- 7. 清理临时文件 ----
        try:
            os.remove(temp_path)
            os.rmdir(temp_dir)
        except OSError:
            pass  # 清理失败不影响响应
