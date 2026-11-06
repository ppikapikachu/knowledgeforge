"""知识库列表 + 题库-知识库映射 API。"""

from typing import List, Optional

from fastapi import APIRouter, Body, Depends, Path, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import ResourceNotFoundException, ValidationException
from app.dependencies.auth import get_current_admin
from app.models.admin import AdminUser
from app.models.knowledge import Knowledge
from app.models.knowledge_base import KnowledgeBase
from app.models.question_bank import QuestionBank
from app.models.question_bank_knowledge_base import QuestionBankKnowledgeBase
from app.schemas.common import ApiResponse, ApiErrorResponse, PaginatedData
from app.schemas.knowledge_base import (
    KnowledgeBaseMappingDetailResponse,
    KnowledgeBaseMappingSaveResponse,
    KnowledgeBaseMappingSelectItem,
)
from app.schemas.question_demand import (
    KnowledgeBaseMappingResponse,
    KnowledgeBaseMappingUpdate,
)
from app.utils.response import paginated_response

router = APIRouter(tags=["知识库与题库映射"])


# 错误响应文档（统一响应信封 {code, message, data}；业务异常经全局异常处理以 HTTP 400 + 业务码 返回）
ERROR_RESPONSES = {
    400: {
        "model": ApiErrorResponse,
        "description": "业务错误（HTTP 400，envelope code 区分）：40001 参数校验（如知识库不存在）/ "
        "40401 不存在（如题库不存在）/ 40101 未认证（管理员令牌无效/过期/管理员不存在/已禁用）",
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
        "description": "系统内部错误（HTTP 500，code 50000），data 恒为 null",
    },
}


@router.get(
    "/knowledge-base-mapping/select-options",
    response_model=ApiResponse[PaginatedData[KnowledgeBaseMappingSelectItem]],
    responses=ERROR_RESPONSES,
    summary="获取知识库选择列表（映射配置页）",
    description=(
        "用途：分页查询知识库列表（用于题库-知识库映射配置页选择知识库）。"
        "**注意**：本接口与 GET /api/v1/knowledge-bases（知识库 CRUD 管理列表）不同，"
        "这里返回映射配置所需的选择项（status 为 active|disabled 字符串、knowledge_count 有效知识点数、支持 keyword 名称搜索）。"
        "本接口使用独立根路径 /knowledge-base-mapping/*（而非 /knowledge-bases/*），"
        "以避免被 GET /knowledge-bases/{kb_id}（int 路径参数）捕获导致 422，同时消除与知识库 CRUD 列表的同路径遮蔽。\n"
        "调用时机：映射配置页打开、搜索知识库时调用。\n"
        "参数：page 页码（≥1，默认 1）；page_size 每页条数（1-500，默认 100）；keyword 按知识库名称模糊搜索（可选）。\n"
        "返回 data 结构（分页信封）：items 每项 id 知识库ID/name 名称/description 描述/status 状态(active|disabled)/"
        "knowledge_count 有效知识点数量（status=1）；page/page_size/total。\n"
        "权限：仅管理员（JWT）。\n"
        "幂等性：只读查询，可安全重复调用。\n"
        "写库：否。"
    ),
)
def get_knowledge_bases(
    page: int = Query(default=1, ge=1, description="页码，从 1 开始递增，默认第 1 页，取值小于 1 按参数校验错误返回"),
    page_size: int = Query(default=100, ge=1, le=500, description="每页条数，取值范围 1-500，默认 100，超出范围按参数校验错误返回"),
    keyword: Optional[str] = Query(default=None, description="按知识库名称模糊搜索（可选，为空返回全部）"),
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    query = db.query(KnowledgeBase)
    if keyword:
        query = query.filter(KnowledgeBase.name.like(f"%{keyword}%"))
    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()

    kb_ids = [kb.id for kb in items]
    counts = {}
    if kb_ids:
        rows = (
            db.query(Knowledge.knowledge_base_id, func.count(Knowledge.id))
            .filter(Knowledge.knowledge_base_id.in_(kb_ids), Knowledge.status == 1)
            .group_by(Knowledge.knowledge_base_id)
            .all()
        )
        counts = {r[0]: r[1] for r in rows}

    item_data = []
    for kb in items:
        item_data.append({
            "id": kb.id,
            "name": kb.name,
            "description": kb.description,
            "status": "active" if kb.status == 1 else "disabled",
            "knowledge_count": counts.get(kb.id, 0),
        })

    return paginated_response(items=item_data, total=total, page=page, page_size=page_size)


@router.get(
    "/question-banks/{question_bank_id}/knowledge-bases",
    response_model=ApiResponse[KnowledgeBaseMappingDetailResponse],
    responses=ERROR_RESPONSES,
    summary="获取题库关联的知识库",
    description=(
        "用途：查询某题库当前关联的知识库列表（出题范围映射）。\n"
        "调用时机：映射配置页打开时回显当前关联关系。\n"
        "路径参数：question_bank_id 题库ID。\n"
        "返回 data 结构：question_bank_id 题库ID / items 关联知识库数组（id/name/description/knowledge_count 有效知识点数）/"
        "knowledge_base_ids 关联知识库ID数组（与 items 顺序一致，用于前端回显勾选）。\n"
        "错误：题库不存在返回 code=40401。\n"
        "权限：仅管理员（JWT）。\n"
        "幂等性：只读查询，可安全重复调用。\n"
        "写库：否。"
    ),
)
def get_question_bank_knowledge_bases(
    question_bank_id: int = Path(..., description="题库 ID，必须为已存在的题库主键，不存在时返回业务错误 40401"),
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
) -> ApiResponse:
    qb = db.query(QuestionBank).filter(QuestionBank.id == question_bank_id).first()
    if not qb:
        raise ResourceNotFoundException("题库不存在")

    mappings = (
        db.query(QuestionBankKnowledgeBase)
        .filter(QuestionBankKnowledgeBase.question_bank_id == question_bank_id)
        .all()
    )
    kb_ids = [m.knowledge_base_id for m in mappings]

    items = []
    if kb_ids:
        kbs = db.query(KnowledgeBase).filter(KnowledgeBase.id.in_(kb_ids)).all()
        for kb in kbs:
            count = db.query(func.count(Knowledge.id)).filter(
                Knowledge.knowledge_base_id == kb.id, Knowledge.status == 1
            ).scalar()
            items.append({
                "id": kb.id,
                "name": kb.name,
                "description": kb.description,
                "knowledge_count": count,
            })

    return ApiResponse(data={
        "question_bank_id": question_bank_id,
        "items": items,
        "knowledge_base_ids": kb_ids,
    })


@router.put(
    "/question-banks/{question_bank_id}/knowledge-bases",
    response_model=ApiResponse[KnowledgeBaseMappingSaveResponse],
    responses=ERROR_RESPONSES,
    summary="设置题库关联的知识库（全量替换）",
    description=(
        "用途：设置题库的知识库关联（出题范围映射），**全量替换**语义。\n"
        "调用时机：映射配置页点击保存时调用。\n"
        "路径参数：question_bank_id 题库ID。\n"
        "请求体（KnowledgeBaseMappingUpdate）：knowledge_base_ids 知识库ID数组（传空数组=清空关联；"
        "重复ID自动去重保序；任一 ID 不存在返回 40001\"知识库不存在\"）。\n"
        "业务行为：事务化删除旧关联后重建——失败全回滚，不会出现半替换状态。\n"
        "返回 data 结构：question_bank_id 题库ID / knowledge_base_ids 生效的关联知识库ID数组（去重后）。\n"
        "权限：仅管理员（JWT）。\n"
        "幂等性：条件幂等——相同 knowledge_base_ids 重复提交结果一致（覆盖式保存）。\n"
        "写库：是（question_bank_knowledge_base 删除重建）。"
    ),
)
def set_question_bank_knowledge_bases(
    question_bank_id: int = Path(..., description="题库 ID，必须为已存在的题库主键，不存在时返回业务错误 40401"),
    request: KnowledgeBaseMappingUpdate = Body(..., description="知识库ID列表（全量替换语义；空数组=清空关联）"),
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
) -> ApiResponse:
    qb = db.query(QuestionBank).filter(QuestionBank.id == question_bank_id).first()
    if not qb:
        raise ResourceNotFoundException("题库不存在")

    kb_ids = list(dict.fromkeys(request.knowledge_base_ids))  # deduplicate preserving order
    if kb_ids:
        existing = db.query(KnowledgeBase.id).filter(KnowledgeBase.id.in_(kb_ids)).all()
        existing_ids = {r[0] for r in existing}
        missing = set(kb_ids) - existing_ids
        if missing:
            raise ValidationException(f"知识库不存在: {missing}")

    # 事务化替换
    db.query(QuestionBankKnowledgeBase).filter(
        QuestionBankKnowledgeBase.question_bank_id == question_bank_id
    ).delete()

    for kid in kb_ids:
        db.add(QuestionBankKnowledgeBase(
            question_bank_id=question_bank_id,
            knowledge_base_id=kid,
        ))
    db.commit()

    from datetime import datetime
    return ApiResponse(data={
        "question_bank_id": question_bank_id,
        "knowledge_base_ids": kb_ids,
        "updated_at": datetime.utcnow().isoformat(),
    })
