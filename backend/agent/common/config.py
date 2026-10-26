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

    # ==================== 题目去重配置 ====================
    # 多层去重（精确指纹 / 关键词+向量召回 / 范围阈值 / LLM 复核）
    # 初始值为建议默认值，需用 scripts/calibrate_question_dedup_thresholds.py 标定后调整

    QUESTION_DEDUP_ENABLED: bool = True
    # 总开关；关闭后退回"仅生成不去重"旧行为

    QUESTION_DEDUP_SAME_SCOPE_CANDIDATE_THRESHOLD: float = 0.65
    # 同范围（同题库且知识点相交）候选进入 LLM 复核的算法分数下限（宽召回）
    # 2026-10-20 真实 Embedding 标定（scripts/calibrate_question_dedup_thresholds.py）：0.65 处漏判 0、误判最少

    QUESTION_DEDUP_CROSS_SCOPE_HIGH_THRESHOLD: float = 0.75
    # 跨范围候选进入 LLM 复核的高阈值；必须严于同范围阈值（跨库只在极高相似才复核）
    # 2026-10-20 真实 Embedding 标定：0.75 起误判 0、漏判 0（跨库完全相同题干 fused=1.000）

    QUESTION_DEDUP_FINAL_BLOCK_THRESHOLD: float = 0.85
    # 入库前二次校验（并发竞争兜底）直接拦截的严格语义阈值（不走 LLM，防误杀取严格值）

    QUESTION_DEDUP_VECTOR_TOP_K: int = 15
    # 向量通道召回候选数（建议 10~20）

    QUESTION_DEDUP_KEYWORD_TOP_K: int = 15
    # 关键词通道召回候选数

    QUESTION_DEDUP_LLM_MAX_CANDIDATES: int = 5
    # 每道新题最多送入 LLM 复核的候选对数

    QUESTION_DEDUP_LLM_BATCH_SIZE: int = 5
    # 每次 LLM 调用批量判定的配对数

    QUESTION_DEDUP_MAX_REGENERATION_ATTEMPTS: int = 2
    # 单知识点因去重/生成失败补题的最大轮次

    QUESTION_DEDUP_MAX_GENERATION_MULTIPLIER: float = 1.5
    # 单知识点实际生成候选量相对计划量的放大倍数上限（防无限生成）

    QUESTION_DEDUP_LLM_TIMEOUT_SECONDS: int = 60
    # 单次 LLM 复核调用超时（秒）；超时按 uncertain 处理，保留新题并标记人工复核

    EMBEDDING_VERSION: str = "bge-small-zh-v1.5"
    # Embedding 版本标签，写入向量索引 metadata，用于一致性检查/重算

    # ==================== AI 质量审核配置（QuestionReviewAgent） ====================
    QUESTION_AI_REVIEW_ENABLED: bool = False
    # 后端功能总开关（默认关闭）。任务级 enable_ai_review=true 须同时满足本开关开启

    QUESTION_AI_REVIEW_MODEL: str = ""
    # 独立审核模型（可选）；为空时复用 LLM_MODEL（独立调用与独立 Prompt 不变）

    QUESTION_AI_REVIEW_TIMEOUT_SECONDS: int = 60
    # 单题审核单次模型调用超时（秒）；超时 fail-safe 转人工，不自动通过/驳回

    QUESTION_AI_REVIEW_MAX_RETRIES: int = 1
    # 单题审核模型调用重试上限（结构化输出失败时）

    QUESTION_AI_REVIEW_MAX_PER_TASK: int = 200
    # 每任务最大审核题目数（成本保护）；超出部分计入 skipped（budget_exceeded）

    QUESTION_AI_REVIEW_MAX_CONCURRENCY: int = 1
    # 每任务审核并发上限（第一版串行执行，复用生成后台线程，不新开每题线程）

    QUESTION_AI_REVIEW_BATCH_MAX_ITEMS: int = 100
    # 手动批量 AI 审核单批题目数上限（硬上限 200，防无界 LLM 调用）


# 全局配置单例
# 在模块加载时自动读取 .env 文件，后续通过 agent_settings 直接访问
agent_settings = AgentSettings()
