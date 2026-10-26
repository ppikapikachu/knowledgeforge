"""LLM Provider 抽象模块。

按思考模式缓存 ChatOpenAI 实例，避免并发任务模式串扰。
支持 MiMo 的 thinking 扩展参数（extra_body）。

使用方式：
    llm = get_llm(thinking="disabled")   # 知识提取
    llm = get_llm(thinking="enabled")    # 语义去重/冲突判断

设计原则：
    1. 每种模式一个缓存实例，不为每个 Chunk 创建新实例
    2. 创建后不修改实例参数（线程安全）
    3. 所有调用方必须显式声明 thinking 模式
"""

import logging
import threading
from typing import Literal, Optional

from langchain_openai import ChatOpenAI

from agent.common.config import agent_settings

logger = logging.getLogger(__name__)

# 思考模式类型
ThinkingMode = Literal["enabled", "disabled"]

# 按（模式, 模型）缓存的 LLM 实例
_llm_instances: dict[str, ChatOpenAI] = {}
_llm_lock = threading.Lock()


def get_llm(*, thinking: ThinkingMode, model: Optional[str] = None) -> ChatOpenAI:
    """按固定思考模式获取进程内缓存的 LLM 客户端。

    Args:
        thinking: 思考模式
            - "disabled": 知识提取等不需要深度推理的任务
            - "enabled": 语义去重、冲突判断等需要推理的任务
        model: 可选的模型覆盖（如独立审核模型 QUESTION_AI_REVIEW_MODEL）；
            为空时使用 agent_settings.LLM_MODEL

    Returns:
        缓存的 ChatOpenAI 实例（同模式+模型返回同一对象）

    Raises:
        ValueError: 非法的 thinking 值
    """
    if thinking not in ("enabled", "disabled"):
        raise ValueError(f"不支持的思考模式: {thinking}，必须是 'enabled' 或 'disabled'")

    cache_key = f"{thinking}:{model or ''}"

    # 快速路径：已缓存
    cached = _llm_instances.get(cache_key)
    if cached is not None:
        return cached

    # 慢路径：双重检查加锁创建
    with _llm_lock:
        cached = _llm_instances.get(cache_key)
        if cached is not None:
            return cached

        config = agent_settings
        kwargs = {
            "model": model or config.LLM_MODEL,
            "api_key": config.LLM_API_KEY,
            "base_url": config.LLM_BASE_URL,
            "max_tokens": config.LLM_MAX_TOKENS,
            # MiMo thinking 扩展参数
            "extra_body": {"thinking": {"type": thinking}},
        }

        # MiMo 开启思考时不支持自定义 temperature/top_p
        if thinking == "disabled":
            kwargs["temperature"] = config.LLM_TEMPERATURE

        cached = ChatOpenAI(**kwargs)
        _llm_instances[cache_key] = cached

        logger.info(
            f"LLM 实例创建: thinking={thinking}, "
            f"model={model or config.LLM_MODEL}"
        )
        return cached


def reset_llm() -> None:
    """重置所有 LLM 实例缓存（仅用于测试）。

    用同一把锁保护，不用于运行时切换思考模式。
    """
    global _llm_instances
    with _llm_lock:
        _llm_instances.clear()
        logger.info("LLM 实例缓存已重置")
