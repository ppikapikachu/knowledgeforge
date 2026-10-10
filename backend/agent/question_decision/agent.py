"""QuestionDecisionAgent：根据题库范围生成出题计划。

职责边界：
    - 把用户练题要求转化为可验证的出题计划
    - 不生成题目内容，不写数据库
    - 知识点必须来自候选集，不能编造
"""

import logging
from typing import Dict, List, Optional

from agent.question_decision.schemas import (
    KnowledgePlanItem,
    QuestionBankPlan,
    QuestionDecisionRequest,
    QuestionDecisionResponse,
)

logger = logging.getLogger(__name__)


class QuestionDecisionAgent:
    """出题决策 Agent。

    使用方式：
        agent = QuestionDecisionAgent(db)
        result = agent.make_decision(request)
    """

    def __init__(self, db):
        self.db = db

    def make_decision(self, request: QuestionDecisionRequest) -> QuestionDecisionResponse:
        """生成出题计划。

        流程：
            1. 校验题库存在且启用
            2. 为每个题库检索候选知识点
            3. 调用 LLM 生成分配计划
            4. 校验计划（题量汇总、知识点有效性）
        """
        from app.repositories.question_bank_repository import QuestionBankRepository
        from app.repositories.knowledge_repository import KnowledgeRepository

        qb_repo = QuestionBankRepository(db=self.db)
        kb_repo = KnowledgeRepository(db=self.db)

        warnings = []

        # 1. 校验题库
        banks = []
        for qb_id in request.question_bank_ids:
            bank = qb_repo.get_by_id(qb_id)
            if not bank:
                return QuestionDecisionResponse(
                    total_question_count=request.total_question_count,
                    planned_question_count=0,
                    question_banks=[],
                    warnings=[f"题库 {qb_id} 不存在"],
                )
            if bank.status == 0:
                return QuestionDecisionResponse(
                    total_question_count=request.total_question_count,
                    planned_question_count=0,
                    question_banks=[],
                    warnings=[f"题库 '{bank.name}' 已停用"],
                )
            banks.append(bank)

        # 2. 为每个题库检索候选知识点
        bank_candidates = {}
        for bank in banks:
            candidates = self._get_candidates_for_bank(bank, kb_repo)
            bank_candidates[bank.id] = candidates
            if not candidates:
                warnings.append(f"题库 '{bank.name}' 没有可用的候选知识点")

        # 3. 调用 LLM 生成计划
        plan = self._generate_plan(request, banks, bank_candidates, warnings)

        return plan

    def _get_candidates_for_bank(self, bank, kb_repo) -> List[Dict]:
        """为题库检索候选知识点。

        MVP 策略：从知识点表中检索正常状态的知识点，
        通过关键词匹配题库描述来筛选。
        """
        from app.models.knowledge import Knowledge

        # 获取正常状态的知识点
        knowledge_list = self.db.query(Knowledge).filter(
            Knowledge.status == 1
        ).limit(50).all()

        # 简单的关键词匹配筛选
        bank_keywords = self._extract_bank_keywords(bank)
        candidates = []

        for k in knowledge_list:
            # 如果题库没有特定关键词，接受所有候选
            if not bank_keywords:
                candidates.append({
                    "id": k.id,
                    "name": k.name,
                    "summary": k.summary or "",
                    "keywords": k.keywords or [],
                })
                continue

            # 检查知识点是否与题库关键词匹配
            k_text = f"{k.name} {k.summary or ''} {' '.join(k.keywords or [])}".lower()
            if any(kw.lower() in k_text for kw in bank_keywords):
                candidates.append({
                    "id": k.id,
                    "name": k.name,
                    "summary": k.summary or "",
                    "keywords": k.keywords or [],
                })

        return candidates[:30]  # 限制候选数量

    def _extract_bank_keywords(self, bank) -> List[str]:
        """从题库名称和描述中提取关键词。"""
        keywords = []
        name = bank.name.lower()

        # 根据题库名称提取主题关键词
        keyword_map = {
            "java基础": ["java", "语法", "面向对象", "异常", "基础"],
            "java集合": ["java", "集合", "list", "set", "map", "collection"],
            "java并发": ["java", "并发", "线程", "锁", "线程池", "jmm"],
            "jvm": ["jvm", "类加载", "垃圾回收", "gc", "运行时", "字节码"],
            "android": ["android", "activity", "fragment", "service", "handler", "生命周期"],
            "数据库": ["数据库", "sql", "索引", "事务", "mysql"],
            "分布式": ["分布式", "一致性", "服务治理", "缓存", "消息"],
        }

        for key, kws in keyword_map.items():
            if key in name:
                keywords.extend(kws)
                break

        return keywords

    def _generate_plan(
        self,
        request: QuestionDecisionRequest,
        banks: list,
        bank_candidates: dict,
        warnings: list,
    ) -> QuestionDecisionResponse:
        """生成出题计划（确定性逻辑，不调用 LLM）。

        MVP 实现：基于候选数量按比例分配题量。
        """
        total = request.total_question_count
        bank_plans = []

        # 计算每个题库的候选数量
        total_candidates = sum(len(v) for v in bank_candidates.values())
        if total_candidates == 0:
            return QuestionDecisionResponse(
                total_question_count=total,
                planned_question_count=0,
                question_banks=[],
                warnings=warnings + ["所有题库都没有可用候选知识点"],
            )

        remaining = total
        for i, bank in enumerate(banks):
            candidates = bank_candidates.get(bank.id, [])
            if not candidates:
                continue

            # 按候选数量比例分配
            if i == len(banks) - 1:
                bank_count = remaining  # 最后一个题库拿剩余
            else:
                ratio = len(candidates) / total_candidates
                bank_count = max(1, int(total * ratio))
                bank_count = min(bank_count, remaining)

            remaining -= bank_count

            # 分配到知识点
            knowledge_plans = self._allocate_to_knowledge(
                candidates, bank_count, request
            )

            bank_plans.append(QuestionBankPlan(
                question_bank_id=bank.id,
                question_bank_name=bank.name,
                planned_count=bank_count,
                knowledge_points=knowledge_plans,
            ))

        planned_total = sum(bp.planned_count for bp in bank_plans)

        if planned_total < total:
            warnings.append(f"候选知识点不足，实际计划 {planned_total} 题，少于要求的 {total} 题")

        return QuestionDecisionResponse(
            total_question_count=total,
            planned_question_count=planned_total,
            question_banks=bank_plans,
            warnings=warnings,
        )

    def _allocate_to_knowledge(
        self,
        candidates: List[Dict],
        count: int,
        request: QuestionDecisionRequest,
    ) -> List[KnowledgePlanItem]:
        """将题量分配到知识点。"""
        if not candidates or count <= 0:
            return []

        # 每个知识点至少 1 题，剩余按顺序分配
        per_knowledge = max(1, count // len(candidates))
        remaining = count

        items = []
        for i, cand in enumerate(candidates):
            if remaining <= 0:
                break

            if i == len(candidates) - 1:
                alloc = remaining
            else:
                alloc = min(per_knowledge, remaining)

            remaining -= alloc

            # 分配难度
            diff_counts = self._allocate_difficulty(alloc, request.difficulty_distribution)

            items.append(KnowledgePlanItem(
                knowledge_id=cand["id"],
                knowledge_name=cand["name"],
                planned_count=alloc,
                question_types=request.question_types or ["SINGLE_CHOICE"],
                difficulty_counts=diff_counts,
            ))

        return items

    def _allocate_difficulty(self, count: int, dist) -> Dict[str, int]:
        """按难度分配题量。"""
        if not dist:
            # 默认均分
            easy = count // 3
            medium = count // 3
            hard = count - easy - medium
            return {"easy": easy, "medium": medium, "hard": hard}

        # 按百分比分配
        total_pct = dist.easy + dist.medium + dist.hard
        if total_pct == 0:
            return {"easy": count, "medium": 0, "hard": 0}

        easy = round(count * dist.easy / total_pct)
        medium = round(count * dist.medium / total_pct)
        hard = count - easy - medium

        return {"easy": easy, "medium": medium, "hard": hard}
