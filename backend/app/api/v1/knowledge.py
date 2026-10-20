"""Knowledge API router."""

from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import ResourceNotFoundException, ValidationException
from app.dependencies.auth import get_current_admin
from app.models.admin import AdminUser
from app.repositories.knowledge_repository import KnowledgeRepository
from app.schemas.common import ApiResponse, PaginatedData
from app.schemas.knowledge import (
    KnowledgeCreate,
    KnowledgeRelationCreate,
    KnowledgeRelationResponse,
    KnowledgeResponse,
    KnowledgeUpdate,
)
from app.schemas.question_demand import ImportanceResponse, ImportanceUpdate
from app.services.knowledge_service import KnowledgeService
from app.utils.response import paginated_response, success_response

router = APIRouter(prefix="/knowledge", tags=["知识点管理"])


@router.get(
    "",
    summary="获取知识点列表",
    description="分页获取知识点列表，支持按关键词、难度、状态筛选。",
)
def get_knowledge_list(
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页数量"),
    keyword: Optional[str] = Query(default=None, description="关键词搜索"),
    difficulty: Optional[int] = Query(default=None, ge=1, le=3, description="难度"),
    status: Optional[int] = Query(default=None, ge=0, le=1, description="状态"),
    knowledge_base_id: Optional[int] = Query(default=None, description="按知识库筛选"),
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    """Get knowledge list with pagination and filters."""
    service = KnowledgeService(db)
    items, total = service.get_knowledge_list(
        page=page,
        page_size=page_size,
        keyword=keyword,
        difficulty=difficulty,
        status=status,
        knowledge_base_id=knowledge_base_id,
    )

    # Get question counts for all knowledge items
    knowledge_ids = [k.id for k in items]
    repo = KnowledgeRepository(db)
    q_counts = repo.get_question_counts(knowledge_ids)

    item_data = []
    for k in items:
        data = KnowledgeResponse.model_validate(k).model_dump(mode="json")
        data["question_count"] = q_counts.get(k.id, 0)
        item_data.append(data)
    return paginated_response(
        items=item_data,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{knowledge_id}",
    response_model=ApiResponse[KnowledgeResponse],
    summary="获取知识点详情",
    description="根据ID获取知识点详细信息。",
)
def get_knowledge(
    knowledge_id: int,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
) -> ApiResponse:
    """Get knowledge by ID."""
    service = KnowledgeService(db)
    knowledge = service.get_knowledge(knowledge_id)

    repo = KnowledgeRepository(db)
    q_counts = repo.get_question_counts([knowledge.id])

    data = KnowledgeResponse.model_validate(knowledge).model_dump(mode="json")
    data["question_count"] = q_counts.get(knowledge.id, 0)
    return ApiResponse(data=data)


@router.post(
    "",
    response_model=ApiResponse[KnowledgeResponse],
    summary="创建知识点",
    description="创建一个新的知识点。",
)
def create_knowledge(
    request: KnowledgeCreate,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
) -> ApiResponse:
    """Create a new knowledge point."""
    service = KnowledgeService(db)

    data = request.model_dump()

    # 处理默认知识库
    if not data.get("knowledge_base_id"):
        from app.repositories.knowledge_base_repository import KnowledgeBaseRepository
        kb_repo = KnowledgeBaseRepository(db)
        uncategorized = kb_repo.get_by_code("uncategorized")
        data["knowledge_base_id"] = uncategorized.id if uncategorized else 1

    knowledge = service.create_knowledge(**data)
    return ApiResponse(data=KnowledgeResponse.model_validate(knowledge))


@router.put(
    "/{knowledge_id}",
    response_model=ApiResponse[KnowledgeResponse],
    summary="更新知识点",
    description="更新指定知识点的信息。",
)
def update_knowledge(
    knowledge_id: int,
    request: KnowledgeUpdate,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
) -> ApiResponse:
    """Update a knowledge point."""
    service = KnowledgeService(db)
    update_data = request.model_dump(exclude_unset=True)
    knowledge = service.update_knowledge(knowledge_id, **update_data)
    return ApiResponse(data=KnowledgeResponse.model_validate(knowledge))


@router.delete(
    "/{knowledge_id}",
    response_model=ApiResponse[KnowledgeResponse],
    summary="删除知识点",
    description="禁用指定知识点（软删除）。",
)
def delete_knowledge(
    knowledge_id: int,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
) -> ApiResponse:
    """Disable a knowledge point (soft delete)."""
    service = KnowledgeService(db)
    knowledge = service.delete_knowledge(knowledge_id)
    return ApiResponse(data=KnowledgeResponse.model_validate(knowledge))


@router.patch(
    "/{knowledge_id}/importance",
    response_model=ApiResponse[ImportanceResponse],
    summary="修改知识点重要程度",
    description="手动修改知识点重要程度，设置后来源标记为 manual，不会被后续导入覆盖。",
)
def update_knowledge_importance(
    knowledge_id: int,
    request: ImportanceUpdate,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
) -> ApiResponse:
    valid_levels = {"core", "important", "normal", "supplementary"}
    if request.importance_level not in valid_levels:
        raise ValidationException(f"非法重要程度: {request.importance_level}，允许值: {valid_levels}")

    from app.models.knowledge import Knowledge
    from app.core.exceptions import ResourceNotFoundException
    knowledge = db.query(Knowledge).filter(Knowledge.id == knowledge_id).first()
    if not knowledge:
        raise ResourceNotFoundException("知识点不存在")

    knowledge.importance_level = request.importance_level
    knowledge.importance_source = "manual"
    db.commit()
    db.refresh(knowledge)

    return ApiResponse(data=ImportanceResponse(
        id=knowledge.id,
        importance_level=knowledge.importance_level,
        importance_source=knowledge.importance_source,
        updated_at=knowledge.updated_at,
    ))


# Knowledge Relations
@router.get(
    "/{knowledge_id}/relations",
    summary="获取知识点关系列表",
    description="获取指定知识点的所有关系。",
)
def get_knowledge_relations(
    knowledge_id: int,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
) -> ApiResponse:
    """Get relations for a knowledge point."""
    service = KnowledgeService(db)
    relations = service.get_knowledge_relations(knowledge_id)
    data = [
        KnowledgeRelationResponse.model_validate(r).model_dump(mode="json")
        for r in relations
    ]
    return ApiResponse(data=data)


@router.post(
    "/{knowledge_id}/relations",
    response_model=ApiResponse[KnowledgeRelationResponse],
    summary="创建知识点关系",
    description="为指定知识点创建一条关系。",
)
def create_knowledge_relation(
    knowledge_id: int,
    request: KnowledgeRelationCreate,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
) -> ApiResponse:
    """Create a knowledge relation."""
    service = KnowledgeService(db)
    relation = service.create_knowledge_relation(
        source_id=knowledge_id,
        target_id=request.target_knowledge_id,
        relation_type=request.relation_type,
    )
    return ApiResponse(data=KnowledgeRelationResponse.model_validate(relation))


@router.delete(
    "/{knowledge_id}/relations/{relation_id}",
    summary="删除知识点关系",
    description="删除指定知识点的指定关系。",
)
def delete_knowledge_relation(
    knowledge_id: int,
    relation_id: int,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
) -> ApiResponse:
    """Delete a knowledge relation."""
    service = KnowledgeService(db)
    service.delete_knowledge_relation(knowledge_id, relation_id)
    return ApiResponse(message="删除成功")
