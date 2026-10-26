"""QuestionReviewAgent：题目质量 AI 审核 Agent。

职责边界（执行文档 §4.1/§4.6）：
- 只检查题目质量，返回严格结构化审核建议和证据；
- 不直接读写数据库、不发布/驳回题目（状态流转统一经 QuestionReviewService）；
- 独立 Prompt、独立结构化输出 Schema、独立审核配置；
- 生成 Agent 的自评内容不作为审核证据（调用方不得把生成自评放进上下文）。

失败安全（§4.3）：字段不合法、缺项、无法解析或超时，一律抛
QuestionReviewAgentError 由服务层按 manual_review/failed 处理，
绝不能当成 auto_approve 或 auto_reject。
"""

import logging
import threading
from typing import Any, Dict, List, Optional

from agent.common.config import agent_settings
from agent.common.llm import get_llm
from agent.question_review.prompts import (
    KNOWLEDGE_ITEM_TEMPLATE,
    OPTION_LINE_TEMPLATE,
    REVIEW_PROMPT_VERSION,
    SYSTEM_PROMPT,
    USER_PROMPT_TEMPLATE,
    VERSION_ENV_UNKNOWN,
)
from agent.question_review.schemas import QuestionReviewOutput

logger = logging.getLogger(__name__)


class QuestionReviewAgentError(Exception):
    """审核执行失败（超时/模型异常/结构化输出不可解析）。"""


class QuestionReviewAgent:
    """题目质量审核 Agent。

    输入为构建好的审核上下文 dict（Service 负责从 DB 组装）：
    {
        "question_id": int,
        "question_type": str,
        "difficulty": int,
        "content": str,
        "answer": str,
        "analysis": str | None,
        "options": [{"option_key", "option_content", "is_correct"}],
        "knowledge_points": [{"knowledge_id", "name", "content", "importance_level"}],
        "version_environment": str | None,
        "dedup_status": str,
        "dedup_unresolved": bool,
    }
    """

    prompt_version = REVIEW_PROMPT_VERSION

    def __init__(
        self,
        *,
        llm=None,
        model: Optional[str] = None,
        timeout: Optional[int] = None,
        max_retries: Optional[int] = None,
    ) -> None:
        self._llm = llm
        self._model = model or (agent_settings.QUESTION_AI_REVIEW_MODEL or None)
        self.timeout = int(
            timeout if timeout is not None
            else agent_settings.QUESTION_AI_REVIEW_TIMEOUT_SECONDS
        )
        self.max_retries = int(
            max_retries if max_retries is not None
            else agent_settings.QUESTION_AI_REVIEW_MAX_RETRIES
        )

    # ------------------------------------------------------------------
    # 公共入口
    # ------------------------------------------------------------------
    def review(self, context: Dict[str, Any]) -> QuestionReviewOutput:
        """执行一次质量审核。失败抛 QuestionReviewAgentError。"""
        user_prompt = self.build_user_prompt(context)
        last_error: Optional[Exception] = None

        attempts = max(1, self.max_retries + 1)
        for attempt in range(attempts):
            try:
                llm = self._get_llm()
                structured = llm.with_structured_output(QuestionReviewOutput)
                raw = self._invoke_with_timeout(structured, user_prompt)
                output = self._validate_output(raw)
                return output
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                logger.warning(
                    f"QuestionReviewAgent 第 {attempt + 1}/{attempts} 次调用失败: {exc}"
                )

        raise QuestionReviewAgentError(
            f"质量审核执行失败（安全降级，不作自动判定）: {last_error}"
        )

    # ------------------------------------------------------------------
    # Prompt 构建
    # ------------------------------------------------------------------
    @staticmethod
    def build_user_prompt(context: Dict[str, Any]) -> str:
        options: List[Dict[str, Any]] = list(context.get("options") or [])
        if options:
            options_block = "\n".join(
                OPTION_LINE_TEMPLATE.format(
                    key=opt.get("option_key", "?"),
                    content=opt.get("option_content", ""),
                    correct="是" if opt.get("is_correct") else "否",
                )
                for opt in options
            )
        else:
            options_block = "（本题无选项）"

        knowledge_points = list(context.get("knowledge_points") or [])
        if knowledge_points:
            knowledge_block = "\n".join(
                KNOWLEDGE_ITEM_TEMPLATE.format(
                    knowledge_id=kp.get("knowledge_id", "?"),
                    importance=kp.get("importance_level", "normal"),
                    name=kp.get("name", ""),
                    content=(kp.get("content") or "")[:3000],
                )
                for kp in knowledge_points
            )
        else:
            knowledge_block = "（无关联知识点资料）"

        return USER_PROMPT_TEMPLATE.format(
            question_id=context.get("question_id", "?"),
            question_type=context.get("question_type", "?"),
            difficulty=context.get("difficulty", "?"),
            content=context.get("content", ""),
            options_block=options_block,
            answer=context.get("answer", ""),
            analysis=context.get("analysis") or "（未提供解析）",
            knowledge_block=knowledge_block,
            version_environment=context.get("version_environment") or VERSION_ENV_UNKNOWN,
            dedup_status=context.get("dedup_status", "clean"),
            dedup_unresolved="是" if context.get("dedup_unresolved") else "否",
        )

    # ------------------------------------------------------------------
    # 模型调用与校验
    # ------------------------------------------------------------------
    def _get_llm(self):
        if self._llm is not None:
            return self._llm
        # 独立调用：审核任务不需要深度思考链，thinking="disabled"
        return get_llm(thinking="disabled", model=self._model)

    def _invoke_with_timeout(self, structured, user_prompt: str):
        """带超时的模型调用；超时抛 QuestionReviewAgentError（fail-safe）。"""
        result: Dict[str, Any] = {}

        def _call():
            try:
                result["value"] = structured.invoke(
                    [("system", SYSTEM_PROMPT), ("user", user_prompt)]
                )
            except Exception as exc:  # noqa: BLE001
                result["error"] = exc

        thread = threading.Thread(target=_call, name="question-review-llm", daemon=True)
        thread.start()
        thread.join(timeout=self.timeout)
        if thread.is_alive():
            raise QuestionReviewAgentError(
                f"质量审核模型调用超时（>{self.timeout}s）"
            )
        if "error" in result:
            raise result["error"]
        return result.get("value")

    def _validate_output(self, raw: Any) -> QuestionReviewOutput:
        if raw is None:
            raise QuestionReviewAgentError("模型返回为空")
        if isinstance(raw, QuestionReviewOutput):
            return raw
        if isinstance(raw, dict):
            return QuestionReviewOutput.model_validate(raw)
        raise QuestionReviewAgentError(f"模型返回类型不受支持: {type(raw)}")
