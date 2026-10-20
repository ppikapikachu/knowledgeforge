"""知识库列表 + 题库-知识库映射 API。"""

from typing import List, Optional

from fastapi import APIRouter, Depends, Query
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
from app.schemas.common import ApiResponse, PaginatedData
from app.schemas.question_demand import (
    KnowledgeBaseMappingResponse,
    KnowledgeBaseMappingUpdate,
)
from app.utils.response import paginated_response

router = APIRouter(tags=["知识库与题库映射"])


@router.get(
    "/knowledge-bases",
    summary="获取知识库列表",
    description="分页返回知识库列表，含知识点数量。",
)
def get_knowledge_bases(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=500),
    keyword: Optional[str] = Query(default=None),
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
    summary="获取题库关联的知识库",
)
def get_question_bank_knowledge_bases(
    question_bank_id: int,
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
    summary="设置题库关联的知识库（全量替换）",
)
def set_question_bank_knowledge_bases(
    question_bank_id: int,
    request: KnowledgeBaseMappingUpdate,
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
