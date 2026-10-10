"""Agent 配置模块。

本模块负责从 .env 文件中加载所有与 Agent 相关的配置项。
配置分为三大类：
    1. LLM 配置：模型提供商、API密钥、模型名称、温度参数等
    2. 分块配置：每个 Chunk 的目标大小和相邻 Chunk 的重叠字符数
    3. Agent 配置：LLM 返回非法结果时的最大重试次数

使用方式：
    from agent.common.config import agent_settings
    model = agent_settings.LLM_MODEL
    chunk_size = agent_settings.CHUNK_SIZE

注意：
    - 所有敏感信息（如 API Key）必须通过 .env 文件配置，禁止硬编码
    - extra="ignore" 允许 .env 中包含本类未定义的变量（如 MySQL 配置）
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class AgentSettings(BaseSettings):
    """Agent 专用配置类。

    通过 pydantic-settings 自动从 .env 文件和环境变量读取配置。
    与 app/core/config.py 的 Settings 类独立，各自管理不同领域的配置。
    """

    model_config = SettingsConfigDict(
        env_file=".env",           # 配置文件路径
        env_file_encoding="utf-8", # 文件编码
        case_sensitive=False,      # 环境变量名不区分大小写
        extra="ignore",            # 忽略 .env 中与本类无关的变量
    )

    # ==================== LLM 配置 ====================
    # 这些配置决定了 Agent 调用哪个大语言模型

    LLM_PROVIDER: str = "openai"
    # LLM 提供商标识，如 "openai"、"deepseek"、"zhipu" 等
    # 当前仅用于日志记录，实际调用通过 LLM_BASE_URL 决定

    LLM_MODEL: str = "gpt-4o-mini"
    # 模型名称，会传递给 OpenAI 兼容 API 的 model 参数
    # 示例：gpt-4o-mini、deepseek-chat、glm-4-flash 等

    LLM_API_KEY: str = ""
    # API 密钥，必须从 .env 读取
    # 禁止在代码中硬编码任何 API Key

    LLM_BASE_URL: str = "https://api.openai.com/v1"
    # API 基础地址
    # OpenAI: https://api.openai.com/v1
    # DeepSeek: https://api.deepseek.com/v1
    # 其他兼容 OpenAI API 的服务商地址

    LLM_TEMPERATURE: float = 0.1
    # 温度参数，控制输出的随机性
    # 0.0 = 完全确定性，适合结构化提取任务
    # 1.0 = 高随机性，适合创意生成
    # 知识点提取建议 0.0~0.2

    LLM_MAX_TOKENS: int = 16384
    # 单次 LLM 调用的最大输出 Token 数
    # 设置过大会增加成本，设置过小可能截断输出

    # ==================== 分块配置 ====================
    # 这些配置决定了文档如何被切分为 Chunk

    CHUNK_SIZE: int = 6000
    # 每个 Chunk 的目标字符数（中文字符）
    # 建议范围：5000~8000
    # 太小：Chunk 太多，LLM 调用次数多，成本高
    # 太大：单个 Chunk 超出 LLM 上下文窗口，理解质量下降

    CHUNK_OVERLAP: int = 500
    # 相邻 Chunk 之间的重叠字符数
    # 作用：保持上下文连续性，避免知识点在 Chunk 边界处被截断
    # 建议为 CHUNK_SIZE 的 5%~15%

    # ==================== Agent 配置 ====================

    AGENT_MAX_RETRIES: int = 2
    # LLM 返回非法结构时的最大重试次数
    # 重试时会附带错误信息，引导 LLM 修正输出格式
    # 设置为 0 表示不重试，设置过大可能浪费 Token

    # ==================== Embedding 配置 ====================
    # 用于将知识点文本转换为向量，支持向量检索和相似度计算

    EMBEDDING_MODEL: str = "D:/python/ai_model/models--BAAI--bge-small-zh-v1.5/snapshots/7999e1d3359715c523056ef9478215996d62a620"
    # Embedding 模型本地路径
    # 当前使用: BAAI/bge-small-zh-v1.5（中文小模型，512维）

    EMBEDDING_USE_FP16: bool = True
    # 是否使用 FP16 半精度推理
    # 开启可减少显存占用、加快推理速度

    # ==================== 去重配置 ====================
    # 控制去重 Pipeline 的判定阈值

    DEDUP_LOW_THRESHOLD: float = 0.60
    # 低于此阈值判定为 NEW（新知识点）
    # 建议范围：0.50~0.70

    DEDUP_HIGH_THRESHOLD: float = 0.88
    # 高于此阈值判定为 DUPLICATE（重复）
    # 建议范围：0.85~0.95

    DEDUP_TOP_K: int = 3
    # 向量检索返回的最大相似知识点数量


# 全局配置单例
# 在模块加载时自动读取 .env 文件，后续通过 agent_settings 直接访问
agent_settings = AgentSettings()
