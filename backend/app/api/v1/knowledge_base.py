"""知识库 API 路由。"""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import ResourceNotFoundException, ValidationException
from app.dependencies.auth import get_current_admin
from app.models.admin import AdminUser
from app.repositories.knowledge_base_repository import KnowledgeBaseRepository
from app.schemas.common import ApiResponse
from app.schemas.knowledge_base import (
    KnowledgeBaseCreate,
    KnowledgeBaseResponse,
    KnowledgeBaseStatusUpdate,
    KnowledgeBaseUpdate,
)
from app.utils.response import paginated_response

router = APIRouter(prefix="/knowledge-bases", tags=["知识库管理"])


@router.get(
    "",
    summary="获取知识库列表",
    description="分页获取知识库列表，附带每个知识库的知识点数量。",
)
def get_knowledge_base_list(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status: Optional[int] = Query(default=None, ge=0, le=1),
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    """获取知识库列表。"""
    repo = KnowledgeBaseRepository(db)
    items, total = repo.get_list(page=page, page_size=page_size, status=status)

    kb_ids = [kb.id for kb in items]
    counts = repo.get_knowledge_counts(kb_ids)

    item_data = []
    for kb in items:
        data = KnowledgeBaseResponse.model_validate(kb).model_dump(mode="json")
        data["knowledge_count"] = counts.get(kb.id, 0)
        item_data.append(data)

    return paginated_response(items=item_data, total=total, page=page, page_size=page_size)


@router.get(
    "/{kb_id}",
    response_model=ApiResponse[KnowledgeBaseResponse],
    summary="获取知识库详情",
)
def get_knowledge_base(
    kb_id: int,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
) -> ApiResponse:
    """获取知识库详情。"""
    repo = KnowledgeBaseRepository(db)
    kb = repo.get_by_id(kb_id)
    if not kb:
        raise ResourceNotFoundException("知识库", kb_id)

    data = KnowledgeBaseResponse.model_validate(kb).model_dump(mode="json")
    data["knowledge_count"] = repo.get_knowledge_count(kb_id)
    return ApiResponse(data=data)


@router.post(
    "",
    response_model=ApiResponse[KnowledgeBaseResponse],
    summary="创建知识库",
)
def create_knowledge_base(
    request: KnowledgeBaseCreate,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
) -> ApiResponse:
    """创建知识库。code 创建后不可修改。"""
    repo = KnowledgeBaseRepository(db)

    # 检查 code 唯一
    if repo.get_by_code(request.code):
        raise ValidationException(f"编码 '{request.code}' 已存在")

    kb = repo.create(**request.model_dump())
    db.commit()
    db.refresh(kb)

    data = KnowledgeBaseResponse.model_validate(kb).model_dump(mode="json")
    data["knowledge_count"] = 0
    return ApiResponse(data=data)


@router.put(
    "/{kb_id}",
    response_model=ApiResponse[KnowledgeBaseResponse],
    summary="更新知识库",
    description="修改名称、描述。code 不可修改。",
)
def update_knowledge_base(
    kb_id: int,
    request: KnowledgeBaseUpdate,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
) -> ApiResponse:
    """更新知识库。"""
    repo = KnowledgeBaseRepository(db)
    kb = repo.get_by_id(kb_id)
    if not kb:
        raise ResourceNotFoundException("知识库", kb_id)

    kb = repo.update(kb, **request.model_dump(exclude_unset=True))
    db.commit()
    db.refresh(kb)

    data = KnowledgeBaseResponse.model_validate(kb).model_dump(mode="json")
    data["knowledge_count"] = repo.get_knowledge_count(kb_id)
    return ApiResponse(data=data)


@router.patch(
    "/{kb_id}/status",
    response_model=ApiResponse[KnowledgeBaseResponse],
    summary="停用/启用知识库",
    description="停用后不能作为新导入目标，但旧知识仍可查看。",
)
def update_knowledge_base_status(
    kb_id: int,
    request: KnowledgeBaseStatusUpdate,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
) -> ApiResponse:
    """停用/启用知识库。"""
    repo = KnowledgeBaseRepository(db)
    kb = repo.get_by_id(kb_id)
    if not kb:
        raise ResourceNotFoundException("知识库", kb_id)

    kb = repo.update(kb, status=request.status)
    db.commit()
    db.refresh(kb)

    data = KnowledgeBaseResponse.model_validate(kb).model_dump(mode="json")
    data["knowledge_count"] = repo.get_knowledge_count(kb_id)
    return ApiResponse(data=data)
