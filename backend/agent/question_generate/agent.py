"""QuestionGenerateAgent：根据知识点生成面试题。

职责：
    - 根据计划项生成题目
    - 校验题目格式和规则
    - 生成内容指纹用于去重
    - 保存为 pending_review 状态

不负责：
    - 决定生成什么题（由 QuestionDecisionAgent 决定）
    - 自动发布题目（需管理员审核）
"""

import hashlib  # noqa: F401 —— 兼容旧引用（指纹统一走 question_normalizer）
import logging
import time
from typing import Dict, List, Optional

from agent.question_generate.prompts import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE
from agent.question_generate.schemas import (
    GeneratedQuestion,
    QuestionGenerateOutput,
)

logger = logging.getLogger(__name__)


class QuestionGenerateAgent:
    """题目生成 Agent。"""

    def __init__(self, db):
        self.db = db

    def generate_for_plan_item(
        self,
        knowledge_id: int,
        question_bank_id: int,
        question_type: str,
        difficulty: int,
        count: int,
    ) -> Dict:
        """为一个计划项生成题目。

        Returns:
            {"questions": [...], "success_count": N, "failed_count": N, "errors": [...]}
        """
        from app.models.knowledge import Knowledge

        start_time = time.time()
        errors = []
        generated = []

        # 获取知识点上下文
        knowledge = self.db.query(Knowledge).filter(
            Knowledge.id == knowledge_id
        ).first()
        if not knowledge:
            return {
                "questions": [],
                "success_count": 0,
                "failed_count": count,
                "errors": [f"知识点 {knowledge_id} 不存在"],
            }

        try:
            # 调用 LLM 生成题目
            questions = self._call_llm_generate(
                knowledge, question_bank_id, question_type, difficulty, count
            )

            # 校验每道题
            for q in questions:
                try:
                    self._validate_question(q, question_type)
                    generated.append(q)
                except ValueError as e:
                    errors.append(f"校验失败: {e}")

        except Exception as e:
            errors.append(f"LLM 生成失败: {e}")

        duration = time.time() - start_time

        return {
            "questions": generated,
            "success_count": len(generated),
            "failed_count": count - len(generated),
            "errors": errors,
            "duration": round(duration, 2),
        }

    def _call_llm_generate(
        self,
        knowledge,
        question_bank_id: int,
        question_type: str,
        difficulty: int,
        count: int,
    ) -> List[GeneratedQuestion]:
        """调用 LLM 生成题目。"""
        from langchain_core.messages import HumanMessage, SystemMessage
        from agent.common.llm import get_llm

        llm = get_llm(thinking="disabled")
        structured_llm = llm.with_structured_output(QuestionGenerateOutput)

        user_prompt = USER_PROMPT_TEMPLATE.format(
            count=count,
            question_type=question_type,
            difficulty=difficulty,
            knowledge_name=knowledge.name,
            knowledge_content=(knowledge.content or "")[:2000],
            knowledge_keywords=", ".join(knowledge.keywords or []),
        )

        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=user_prompt),
        ]

        result = structured_llm.invoke(messages)
        return result.questions

    def _validate_question(self, q: GeneratedQuestion, expected_type: str) -> None:
        """校验生成的题目。"""
        if not q.content or len(q.content.strip()) < 5:
            raise ValueError("题干过短或为空")

        if q.question_type != expected_type:
            raise ValueError(f"题型不匹配: {q.question_type} != {expected_type}")

        if q.question_type == "SINGLE_CHOICE":
            if len(q.options) < 2:
                raise ValueError("单选题至少需要2个选项")
            correct = sum(1 for o in q.options if o.is_correct == 1)
            if correct != 1:
                raise ValueError("单选题必须恰好1个正确答案")

        elif q.question_type == "MULTIPLE_CHOICE":
            if len(q.options) < 2:
                raise ValueError("多选题至少需要2个选项")
            correct = sum(1 for o in q.options if o.is_correct == 1)
            if correct < 1:
                raise ValueError("多选题至少1个正确答案")

        elif q.question_type == "TRUE_FALSE":
            if q.answer not in ("TRUE", "FALSE"):
                raise ValueError("判断题答案必须是 TRUE 或 FALSE")
            if q.options:
                raise ValueError("判断题不应有选项")

        elif q.question_type == "SHORT_ANSWER":
            if q.options:
                raise ValueError("简答题不应有选项")

    def generate_content_hash(self, q: GeneratedQuestion) -> str:
        """生成内容指纹用于去重（v1：题型 + 规范化题干 + 选项签名 + 答案，执行文档 §3）。

        兼容保留本方法；实现统一走 app.services.question_normalizer，保证
        生成侧与去重侧的指纹算法完全一致。
        """
        from app.services.question_normalizer import question_normalizer

        options = [(opt.option_content, 1 if opt.is_correct else 0) for opt in q.options]
        return question_normalizer.compute_content_hash(
            q.question_type, q.content, q.answer or "", options
        )
