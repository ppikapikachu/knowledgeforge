"""题库 Repository。"""

from typing import List, Optional, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.question import Question
from app.models.question_bank import QuestionBank


class QuestionBankRepository:
    """题库数据访问层。"""

    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, qb_id: int) -> Optional[QuestionBank]:
        """根据 ID 获取题库。"""
        return self.db.query(QuestionBank).filter(
            QuestionBank.id == qb_id
        ).first()

    def get_by_code(self, code: str) -> Optional[QuestionBank]:
        """根据 code 获取题库。"""
        return self.db.query(QuestionBank).filter(
            QuestionBank.code == code
        ).first()

    def get_list(
        self,
        page: int = 1,
        page_size: int = 20,
        keyword: Optional[str] = None,
        status: Optional[int] = None,
    ) -> Tuple[List[QuestionBank], int]:
        """获取题库列表。"""
        query = self.db.query(QuestionBank)
        if keyword:
            query = query.filter(QuestionBank.name.contains(keyword))
        if status is not None:
            query = query.filter(QuestionBank.status == status)

        total = query.count()
        items = (
            query.order_by(QuestionBank.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return items, total

    def create(self, **kwargs) -> QuestionBank:
        """创建题库。"""
        qb = QuestionBank(**kwargs)
        self.db.add(qb)
        self.db.flush()
        return qb

    def update(self, qb: QuestionBank, **kwargs) -> QuestionBank:
        """更新题库。"""
        for key, value in kwargs.items():
            if value is not None and hasattr(qb, key):
                setattr(qb, key, value)
        self.db.flush()
        return qb

    def get_question_count(self, qb_id: int) -> int:
        """获取题库下题目数量。"""
        return self.db.query(func.count(Question.id)).filter(
            Question.question_bank_id == qb_id
        ).scalar() or 0

    def get_question_counts(self, qb_ids: List[int]) -> dict:
        """批量获取题库下题目数量。"""
        if not qb_ids:
            return {}
        rows = (
            self.db.query(
                Question.question_bank_id,
                func.count(Question.id),
            )
            .filter(Question.question_bank_id.in_(qb_ids))
            .group_by(Question.question_bank_id)
            .all()
        )
        return {row[0]: row[1] for row in rows}
