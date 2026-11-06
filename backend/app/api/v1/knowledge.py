"""Knowledge API router."""

from typing import List, Optional

from fastapi import APIRouter, Body, Depends, Path, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import ResourceNotFoundException, ValidationException
from app.dependencies.auth import get_current_admin
from app.models.admin import AdminUser
from app.repositories.knowledge_repository import KnowledgeRepository
from app.schemas.common import ApiResponse, ApiErrorResponse, DataNull, PaginatedData
from app.schemas.knowledge import (
    KnowledgeCreate,
    KnowledgeListItem,
    KnowledgeRelationCreate,
    KnowledgeRelationItem,
    KnowledgeRelationResponse,
    KnowledgeResponse,
    KnowledgeUpdate,
)
from app.schemas.question_demand import ImportanceResponse, ImportanceUpdate
from app.services.knowledge_service import KnowledgeService
from app.utils.response import paginated_response, success_response

router = APIRouter(prefix="/knowledge", tags=["知识点管理"])


# 错误响应文档（统一响应信封 {code, message, data}；业务异常经全局异常处理以 HTTP 400 + 业务码 返回）
ERROR_RESPONSES = {
    400: {
        "model": ApiErrorResponse,
        "description": "业务错误（HTTP 400，envelope code 区分）：40001 参数校验（关系不属于该知识点）/ "
        "40401 不存在（知识点/关系不存在）/ 40101 未认证（管理员令牌无效/过期/管理员不存在/已禁用）",
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
    "",
    response_model=ApiResponse[PaginatedData[KnowledgeListItem]],
    responses=ERROR_RESPONSES,
    summary="获取知识点列表",
    description=(
        "用途：分页查询知识点列表，支持关键词、难度、状态、知识库筛选。\n"
        "调用时机：管理后台知识点列表页加载、切换筛选条件或翻页时调用。\n"
        "返回 data 结构（分页信封）：\n"
        "  items: 知识点数组，元素字段：\n"
        "  id: 知识点ID\n"
        "  knowledge_base_id: 所属知识库ID\n"
        "  name: 知识点名称\n"
        "  summary: 简要说明\n"
        "  content: 完整知识内容\n"
        "  difficulty: 难度（1=简单，2=中等，3=困难）\n"
        "  status: 状态（1=正常，0=禁用）\n"
        "  source_type: 来源类型（MANUAL=人工，IMPORT=导入，AI=AI生成）\n"
        "  source_document: 来源文档名\n"
        "  keywords: 关键词列表\n"
        "  importance_level: 重要程度（core=核心，important=重要，normal=一般，supplementary=补充）\n"
        "  importance_source: 重要程度来源（default=默认，agent=AI判定，manual=人工）\n"
        "  question_count: 关联题目数量\n"
        "  created_at: 创建时间\n"
        "  updated_at: 更新时间\n"
        "  total: 满足条件的总条数\n"
        "  page: 当前页码\n"
        "  page_size: 每页数量\n"
        "权限：需要管理员登录（Authorization: Bearer 管理员 access token）。\n"
        "幂等性：只读查询，天然幂等；不写数据库。"
    ),
)
def get_knowledge_list(
    page: int = Query(default=1, ge=1, description="页码，从 1 开始递增，默认第 1 页，取值小于 1 时按参数校验错误返回"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页条数，默认 20，取值范围 1~100，超出范围按参数校验错误返回"),
    keyword: Optional[str] = Query(default=None, description="关键词，对知识点名称等内容模糊搜索，不传则不按关键词过滤"),
    difficulty: Optional[int] = Query(default=None, ge=1, le=3, description="难度筛选：1=简单，2=中等，3=困难，不传则返回全部难度"),
    status: Optional[int] = Query(default=None, ge=0, le=1, description="状态筛选：1=正常，0=禁用，不传则返回全部状态"),
    knowledge_base_id: Optional[int] = Query(default=None, description="所属知识库ID，只返回该知识库下的知识点，不传则不限知识库"),
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
    description=(
        "用途：按 ID 查询单个知识点的完整详情。\n"
        "调用时机：管理后台知识点详情页打开、编辑前回显数据时调用。\n"
        "返回 data 结构：\n"
        "  id: 知识点ID\n"
        "  knowledge_base_id: 所属知识库ID\n"
        "  name: 知识点名称\n"
        "  summary: 简要说明\n"
        "  content: 完整知识内容\n"
        "  difficulty: 难度（1=简单，2=中等，3=困难）\n"
        "  status: 状态（1=正常，0=禁用）\n"
        "  source_type: 来源类型（MANUAL=人工，IMPORT=导入，AI=AI生成）\n"
        "  source_document: 来源文档名\n"
        "  keywords: 关键词列表\n"
        "  importance_level: 重要程度（core=核心，important=重要，normal=一般，supplementary=补充）\n"
        "  importance_source: 重要程度来源（default=默认，agent=AI判定，manual=人工）\n"
        "  question_count: 关联题目数量\n"
        "  created_at: 创建时间\n"
        "  updated_at: 更新时间\n"
        "权限：需要管理员登录。\n"
        "幂等性：只读查询，天然幂等；不写数据库。"
    ),
)
def get_knowledge(
    knowledge_id: int = Path(..., description="知识点ID，必须为已存在的知识点主键，不存在时返回业务错误 40401"),
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
    description=(
        "用途：手工创建一个新的知识点记录。\n"
        "调用时机：管理后台知识点列表点击“新建”提交表单时调用。\n"
        "请求体（KnowledgeCreate）：\n"
        "  knowledge_base_id: 所属知识库ID，不传时默认归入未分类(uncategorized)知识库\n"
        "  name: 知识点名称，必填\n"
        "  summary: 简要说明\n"
        "  content: 完整知识内容\n"
        "  difficulty: 难度（1=简单，2=中等，3=困难）\n"
        "  status: 状态（1=正常，0=禁用）\n"
        "  source_type: 来源（MANUAL/IMPORT/AI）\n"
        "  source_document: 来源文档名\n"
        "  keywords: 关键词列表\n"
        "  importance_level: 重要程度（core/important/normal/supplementary）\n"
        "返回 data 结构：\n"
        "  id: 新知识点ID\n"
        "  knowledge_base_id: 所属知识库ID\n"
        "  name: 知识点名称\n"
        "  summary: 简要说明\n"
        "  content: 完整知识内容\n"
        "  difficulty: 难度\n"
        "  status: 状态\n"
        "  source_type: 来源类型\n"
        "  source_document: 来源文档名\n"
        "  keywords: 关键词列表\n"
        "  importance_level: 重要程度\n"
        "  importance_source: 重要程度来源\n"
        "  question_count: 关联题目数量（新建时为 0）\n"
        "  created_at: 创建时间\n"
        "  updated_at: 更新时间\n"
        "权限：需要管理员登录。\n"
        "幂等性：非幂等，重复调用会创建多条知识点；写数据库。"
    ),
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
    description=(
        "用途：更新指定知识点的字段（仅提交的字段会被修改）。\n"
        "调用时机：管理后台知识点编辑表单保存时调用。\n"
        "请求体（KnowledgeUpdate）：所有字段可选，仅传入的字段被更新；字段含义同创建接口。\n"
        "返回 data 结构：更新后的知识点完整对象，字段含义同“获取知识点详情”。\n"
        "权限：需要管理员登录。\n"
        "幂等性：同一请求体重复提交结果一致（幂等覆盖式更新）；写数据库。\n"
        "注意：更新题目关联知识点后，题目侧的缓存/指纹不受影响，本接口不触发出题或审核流程。"
    ),
)
def update_knowledge(
    knowledge_id: int = Path(..., description="知识点ID，必须为已存在的知识点主键，不存在时返回业务错误 40401"),
    request: KnowledgeUpdate = Body(..., description="知识点更新字段（仅传入的字段被更新，含义同创建接口）"),
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
) -> ApiResponse:
    """Update a knowledge point."""
    service = KnowledgeService(db)
    update_data = request.model_dump(exclude_unset=True)
    knowledge = service.update_knowledge(knowledge_id, **update_data)
    data = KnowledgeResponse.model_validate(knowledge).model_dump(mode="json")
    data["question_count"] = KnowledgeRepository(db).get_question_counts([knowledge.id]).get(knowledge.id, 0)
    return ApiResponse(data=data)


@router.delete(
    "/{knowledge_id}",
    response_model=ApiResponse[KnowledgeResponse],
    summary="删除知识点",
    description=(
        "用途：禁用（软删除）指定知识点，将状态置为 0，不物理删除数据。\n"
        "调用时机：管理后台知识点列表点击删除并确认时调用。\n"
        "请求体：无。\n"
        "返回 data 结构：更新后的知识点对象（status=0），字段含义同“获取知识点详情”。\n"
        "权限：需要管理员登录。\n"
        "幂等性：重复禁用同一知识点结果一致（幂等）；写数据库（仅改状态，保留历史数据与题目关联）。\n"
        "注意：软删除不会删除题目、答题记录、去重/审核记录等历史数据。"
    ),
)
def delete_knowledge(
    knowledge_id: int = Path(..., description="知识点ID，必须为已存在的知识点主键，不存在时返回业务错误 40401"),
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
) -> ApiResponse:
    """Disable a knowledge point (soft delete)."""
    service = KnowledgeService(db)
    knowledge = service.delete_knowledge(knowledge_id)
    data = KnowledgeResponse.model_validate(knowledge).model_dump(mode="json")
    data["question_count"] = KnowledgeRepository(db).get_question_counts([knowledge.id]).get(knowledge.id, 0)
    return ApiResponse(data=data)


@router.patch(
    "/{knowledge_id}/importance",
    response_model=ApiResponse[ImportanceResponse],
    summary="修改知识点重要程度",
    description=(
        "用途：手动修改知识点重要程度，设置后来源标记为 manual，不会被后续导入覆盖。\n"
        "调用时机：管理后台知识点列表/详情调整重要程度时调用。\n"
        "请求体（ImportanceUpdate）：importance_level 取 core/important/normal/supplementary 之一。\n"
        "返回 data 结构：\n"
        "  id: 知识点ID\n"
        "  importance_level: 重要程度（core=核心，important=重要，normal=一般，supplementary=补充）\n"
        "  importance_source: 重要程度来源，手动设置后为 manual\n"
        "  updated_at: 更新时间\n"
        "权限：需要管理员登录。\n"
        "幂等性：同一 importance_level 重复提交结果一致（幂等）；写数据库。\n"
        "注意：importance_level 不在允许取值内时返回业务错误 40001；该值参与智能出题分配权重。"
    ),
)
def update_knowledge_importance(
    knowledge_id: int = Path(..., description="知识点ID，必须为已存在的知识点主键，不存在时返回业务错误 40401"),
    request: ImportanceUpdate = Body(..., description="重要度设置：importance_level 取 core/important/normal/supplementary 之一"),
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
    response_model=ApiResponse[List[KnowledgeRelationItem]],
    responses=ERROR_RESPONSES,
    summary="获取知识点关系列表",
    description=(
        "用途：获取指定知识点关联的全部知识关系（含出边与入边）。\n"
        "调用时机：管理后台知识点详情的关系标签页加载时调用。\n"
        "返回 data 结构（关系对象数组）：\n"
        "  id: 关系ID\n"
        "  source_knowledge_id: 源知识点ID\n"
        "  target_knowledge_id: 目标知识点ID\n"
        "  relation_type: 关系类型（prerequisite=前置，related=相关，extension=扩展，contrast=对比）\n"
        "  target_knowledge_name: 目标知识点名称\n"
        "  created_at: 创建时间\n"
        "权限：需要管理员登录。\n"
        "幂等性：只读查询，天然幂等；不写数据库。"
    ),
)
def get_knowledge_relations(
    knowledge_id: int = Path(..., description="知识点ID，必须为已存在的知识点主键，不存在时返回业务错误 40401"),
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
    description=(
        "用途：为指定知识点创建一条指向目标知识点的关系（源知识点为路径中的 knowledge_id）。\n"
        "调用时机：管理后台知识点详情关系页点击“添加关系”时调用。\n"
        "请求体（KnowledgeRelationCreate）：\n"
        "  target_knowledge_id: 目标知识点ID，必填，必须已存在且不等于源知识点ID\n"
        "  relation_type: 关系类型，取 prerequisite（前置）/related（相关）/extension（扩展）/contrast（对比）之一\n"
        "返回 data 结构：\n"
        "  id: 关系ID\n"
        "  source_knowledge_id: 源知识点ID\n"
        "  target_knowledge_id: 目标知识点ID\n"
        "  relation_type: 关系类型\n"
        "  target_knowledge_name: 目标知识点名称\n"
        "  created_at: 创建时间\n"
        "权限：需要管理员登录。\n"
        "幂等性：非幂等，重复创建相同关系会被唯一约束拒绝（业务错误 40901）；写数据库。\n"
        "校验：目标知识点不存在、源目标相同（自关联）均返回业务错误 40001。"
    ),
)
def create_knowledge_relation(
    knowledge_id: int = Path(..., description="源知识点ID，必须为已存在的知识点主键，不存在时返回业务错误 40401"),
    request: KnowledgeRelationCreate = Body(..., description="关系参数：target_knowledge_id 目标知识点ID、relation_type 关系类型（prerequisite|related|extension|contrast）"),
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
    response_model=ApiResponse[DataNull],
    responses=ERROR_RESPONSES,
    summary="删除知识点关系",
    description=(
        "用途：删除指定知识点名下的一条关系记录。\n"
        "调用时机：管理后台知识点详情关系列表点击删除时调用。\n"
        "请求体：无。\n"
        "返回 data 结构：data 为 null，message 返回“删除成功”。\n"
        "权限：需要管理员登录。\n"
        "幂等性：重复删除同一关系会因记录不存在返回业务错误 40401（非幂等）；写数据库（物理删除关系记录）。\n"
        "校验：关系不属于路径中的知识点时返回业务错误 40001。"
    ),
)
def delete_knowledge_relation(
    knowledge_id: int = Path(..., description="源知识点ID，必须为已存在的知识点主键，用于校验关系归属"),
    relation_id: int = Path(..., description="关系ID，必须为已存在的关系主键，不存在时返回业务错误 40401"),
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
) -> ApiResponse:
    """Delete a knowledge relation."""
    service = KnowledgeService(db)
    service.delete_knowledge_relation(knowledge_id, relation_id)
    return ApiResponse(message="删除成功")
