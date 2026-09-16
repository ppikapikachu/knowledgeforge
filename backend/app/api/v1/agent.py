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

from fastapi import APIRouter, Depends, UploadFile, File
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_admin
from app.models.admin import AdminUser
from app.schemas.common import ApiResponse
from app.utils.file import is_allowed_file

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agent", tags=["Agent 测试"])


@router.post(
    "/knowledge-extract/test",
    summary="测试知识点提取 Agent",
    description=(
        "上传文档文件（pdf/docx/txt/md），运行 KnowledgeExtractAgent 提取知识点。"
        "注意：此接口不会写入正式 knowledge 表，仅返回结构化测试结果。"
    ),
)
async def test_knowledge_extract(
    file: UploadFile = File(..., description="上传文件"),
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
