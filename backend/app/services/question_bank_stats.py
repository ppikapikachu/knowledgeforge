"""题库开放练习的统计聚合（一次聚合查询，禁 N+1）。

供两处共用：
    - 管理端题库列表/详情（published_question_count / pending_review_count / can_assemble）
    - 用户端开放题库浏览（available_question_count / question_type_counts / difficulty_counts）

can_assemble：存在至少 1 道 published 题即可出卷（题型/难度分布不足在组卷时按 §6 明确报缺）。
"""

from typing import Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.knowledge import Knowledge
from app.models.question import Question
from app.models.question_knowledge import QuestionKnowledge

# 练习开放题库可抽取的题状态（组卷同口径：只 published）
ASSEMBLABLE_STATUS = "published"


def bank_question_stats(db: Session, bank_ids: Optional[List[int]] = None) -> Dict[int, dict]:
    """按题库一次聚合：published/pending_review 数量、题型分布、难度分布。

    返回 {bank_id: {published_question_count, pending_review_count,
                   question_type_counts, difficulty_counts, available_question_count}}。
    """
    query = db.query(
        Question.question_bank_id,
        Question.status,
        Question.question_type,
        Question.difficulty,
        func.count(Question.id).label("cnt"),
    )
    if bank_ids is not None:
        query = query.filter(Question.question_bank_id.in_(bank_ids))
    rows = query.group_by(
        Question.question_bank_id, Question.status, Question.question_type, Question.difficulty
    ).all()

    stats: Dict[int, dict] = {}
    for bank_id, status, q_type, difficulty, cnt in rows:
        entry = stats.setdefault(
            bank_id,
            {
                "published_question_count": 0,
                "pending_review_count": 0,
                "question_type_counts": {},
                "difficulty_counts": {},
                "available_question_count": 0,
            },
        )
        if status == ASSEMBLABLE_STATUS:
            entry["published_question_count"] += int(cnt)
            entry["available_question_count"] += int(cnt)
            entry["question_type_counts"][q_type] = entry["question_type_counts"].get(q_type, 0) + int(cnt)
            name = {1: "easy", 2: "normal", 3: "hard"}.get(difficulty, "normal")
            entry["difficulty_counts"][name] = entry["difficulty_counts"].get(name, 0) + int(cnt)
        elif status == "pending_review":
            entry["pending_review_count"] += int(cnt)
    return stats


def bank_knowledge_points(db: Session, bank_id: int) -> List[dict]:
    """题库内有 published 题的知识点（真实 QuestionKnowledge 关联，禁止名称匹配）。

    返回 [{knowledge_id, name, available_question_count}]，按可用题量倒序、id 升序。
    """
    rows = (
        db.query(
            Knowledge.id,
            Knowledge.name,
            func.count(func.distinct(Question.id)).label("cnt"),
        )
        .join(QuestionKnowledge, QuestionKnowledge.knowledge_id == Knowledge.id)
        .join(Question, Question.id == QuestionKnowledge.question_id)
        .filter(
            Question.question_bank_id == bank_id,
            Question.status == ASSEMBLABLE_STATUS,
        )
        .group_by(Knowledge.id, Knowledge.name)
        .order_by(func.count(func.distinct(Question.id)).desc(), Knowledge.id.asc())
        .all()
    )
    return [
        {"knowledge_id": kid, "name": name, "available_question_count": int(cnt)}
        for kid, name, cnt in rows
    ]
