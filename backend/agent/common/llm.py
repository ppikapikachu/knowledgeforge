"""LLM Provider 抽象模块。

本模块提供统一的 LLM 实例获取接口，支持 OpenAI、DeepSeek 及其他兼容
OpenAI API 的模型服务商。

设计目的：
    1. 统一管理 LLM 实例的创建和缓存
    2. 切换模型时只需修改 .env 配置，无需改动 Agent 核心代码
    3. 未来扩展多 Provider 时，只需修改本模块

使用方式：
    from agent.common.llm import get_llm
    llm = get_llm()
    result = llm.invoke("你好")

支持的服务商（通过 LLM_BASE_URL 切换）：
    - OpenAI:  https://api.openai.com/v1
    - DeepSeek: https://api.deepseek.com/v1
    - 智谱:    https://open.bigmodel.cn/api/paas/v4
    - 其他兼容 OpenAI Chat API 的服务商
"""

import logging
from typing import Optional

from langchain_openai import ChatOpenAI

from agent.common.config import agent_settings

logger = logging.getLogger(__name__)

# 模块级缓存，避免每次调用都创建新的 LLM 实例
# 使用 None 表示尚未初始化
_llm_instance: Optional[ChatOpenAI] = None


def get_llm() -> ChatOpenAI:
    """获取或创建 LLM 实例（单例模式）。

    首次调用时根据 .env 配置创建 ChatOpenAI 实例并缓存，
    后续调用直接返回缓存的实例。

    Returns:
        ChatOpenAI: 兼容 LangChain 接口的 LLM 实例

    注意：
        - ChatOpenAI 同时支持 OpenAI 和其他兼容 API
        - 通过 base_url 参数切换不同的服务商
        - temperature 设为低值以保证提取结果的稳定性
    """
    global _llm_instance

    # 如果已有缓存实例，直接返回
    if _llm_instance is not None:
        return _llm_instance

    config = agent_settings

    logger.info(
        f"初始化 LLM 实例: "
        f"provider={config.LLM_PROVIDER}, "
        f"model={config.LLM_MODEL}, "
        f"base_url={config.LLM_BASE_URL}"
    )

    # 创建 ChatOpenAI 实例
    # LangChain 的 ChatOpenAI 类兼容所有 OpenAI 兼容 API
    _llm_instance = ChatOpenAI(
        model=config.LLM_MODEL,          # 模型名称
        api_key=config.LLM_API_KEY,      # API 密钥
        base_url=config.LLM_BASE_URL,    # API 基础地址
        temperature=config.LLM_TEMPERATURE,  # 温度参数
        max_tokens=config.LLM_MAX_TOKENS,    # 最大输出 Token
        # 关闭思考的核心配置
        extra_body={
            "thinking": {"type": "disabled"}
        }
    )

    return _llm_instance


def reset_llm() -> None:
    """重置 LLM 实例缓存。

    主要用于以下场景：
        - 单元测试中需要重新初始化 LLM
        - 运行时动态切换模型配置
    """
    global _llm_instance
    _llm_instance = None
