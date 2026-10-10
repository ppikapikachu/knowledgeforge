# DSH 后端任务：MiMo-V2.6-Pro 思考模式缓存与并发隔离优化

> 执行对象：DeepSeek Harness（DSH）  
> 修改范围：仅 `backend/` 目录  
> 当前模型：`mimo-v2.6-pro`  
> 目标：支持不同 Agent 按任务选择是否开启思考模式，同时避免重复创建 LLM 客户端、共享实例配置串扰和并发任务模式混乱。

---

## 1. 背景与现状

当前后端通过 `agent/common/llm.py` 中的 `get_llm()` 获取缓存的 `ChatOpenAI` 实例。原实现使用模块级单例 `_llm_instance`，所有调用共用同一个实例。

项目现在需要按 Agent 的任务类型选择 MiMo 的思考模式：

- 知识点提取：关闭思考，优先关注原文忠实度、结构化输出和响应效率。
- 复杂语义去重、内容冲突判断：仅在规则和向量检索无法明确判断时调用模型，并开启思考。
- 知识关系判断：思考模式单独配置，初期不要硬编码绑定到提取 Agent 的模式；通过测试决定默认值。

MiMo 的思考开关通过 OpenAI 兼容 API 的 `extra_body` 传递。关闭思考的核心配置为：

```python
ChatOpenAI(
    # 保留当前项目已有的 model、api_key、base_url 等参数
    extra_body={
        "thinking": {"type": "disabled"}
    },
)
```

开启思考时对应使用：

```python
extra_body={
    "thinking": {"type": "enabled"}
}
```

注意：`thinking` 是 MiMo 服务商扩展参数，不是通用 OpenAI 标准参数。必须使用项目当前的 Xiaomi MiMo API 地址与实际 LangChain 版本验证请求体是否按预期发送。

## 2. 核心实现原则

### 2.1 不要在每次调用时创建新的 LLM 客户端

不要在每个 Chunk、每个知识点或每次 `invoke()` 时临时构造 `ChatOpenAI`。

应当在每个后端进程内缓存不同思考模式的客户端：

- `disabled`：一个缓存实例。
- `enabled`：一个缓存实例。

因此，在模型参数配置不发生热更新的前提下，每个进程最多需要两个 `ChatOpenAI` 包装实例，不会因为 100 个 Chunk 或多个并发任务而创建 100 个实例。这些实例调用的是同一个远端 `mimo-v2.6-pro` 模型服务，不代表启动了两份远端模型。

### 2.2 禁止修改共享实例的思考参数

禁止以下做法：

- 在任务开始时修改共享 `llm` 的 `model_kwargs` / `extra_body`，任务结束再改回去。
- 使用全局变量保存“当前思考模式”，然后让所有任务读取这个可变值。
- 为了切换模式调用 `reset_llm()` 并重新创建单例。
- 运行时修改 `.env` 或 `agent_settings` 中的公共思考开关来临时切换任务。

原因：多个任务可能同时执行。一个任务将共享对象改为 `disabled`，另一个任务改为 `enabled` 时，会有模式串扰风险。

应通过“按模式取缓存实例”的方式隔离配置；创建完成后不再修改该实例的思考参数。

### 2.3 所有生产调用方应明确声明模式

建议将接口调整为显式参数，例如：

```python
llm = get_llm(thinking="disabled")
```

或：

```python
llm = get_llm(thinking="enabled")
```

推荐使用 `Literal["enabled", "disabled"]` 或等效类型限制，非法值应尽早报错。请先搜索并更新 `backend/` 内所有 `get_llm()` 调用点，避免旧调用遗漏后无意使用默认模式。

## 3. 推荐实现结构

以下为实现参考，DSH 必须结合当前代码与依赖版本进行整合，不要机械覆盖现有配置。

```python
import threading
from typing import Literal

from langchain_openai import ChatOpenAI

from agent.common.config import agent_settings

ThinkingMode = Literal["enabled", "disabled"]

_llm_instances: dict[str, ChatOpenAI] = {}
_llm_lock = threading.Lock()


def get_llm(*, thinking: ThinkingMode) -> ChatOpenAI:
    """按固定思考模式获取进程内缓存的 LLM 客户端。"""
    if thinking not in ("enabled", "disabled"):
        raise ValueError(f"Unsupported thinking mode: {thinking}")

    cached = _llm_instances.get(thinking)
    if cached is not None:
        return cached

    with _llm_lock:
        # 双重检查，避免多个线程首次并发调用时重复创建同一模式的实例。
        cached = _llm_instances.get(thinking)
        if cached is not None:
            return cached

        config = agent_settings
        kwargs = {
            "model": config.LLM_MODEL,
            "api_key": config.LLM_API_KEY,
            "base_url": config.LLM_BASE_URL,
            "max_tokens": config.LLM_MAX_TOKENS,
            "extra_body": {"thinking": {"type": thinking}},
        }

        # MiMo 在开启思考时不支持自定义 temperature/top_p。
        # 所以 thinking=enabled 时不要传入项目现有的自定义 temperature，
        # thinking=disabled 时再按当前项目配置传入 temperature。
        if thinking == "disabled":
            kwargs["temperature"] = config.LLM_TEMPERATURE

        cached = ChatOpenAI(**kwargs)
        _llm_instances[thinking] = cached
        return cached
```

### 实现注意事项

1. 当前项目可能使用的 `ChatOpenAI`、LangChain、Pydantic 类型和 `max_tokens` 参数版本需要先检查，不要假设示例代码可以直接复制运行。
2. MiMo 官方 OpenAI 兼容 API 示例使用 `max_completion_tokens`。请确认当前 `langchain_openai.ChatOpenAI` 版本将 `max_tokens` 映射为何种请求字段，以及 MiMo 端是否接受；不能未经验证就更改现有 Token 参数。
3. MiMo 官方说明：开启思考时，`mimo-v2.6-pro` 不支持自定义 `temperature` 和 `top_p`，实际会使用模型推荐默认值。因此思考开启实例应避免显式传递自定义 `temperature`/`top_p`。关闭思考时可以继续使用现有温度配置。
4. 缓存只针对本进程。若项目使用多个 Uvicorn Worker 或独立任务 Worker，每个进程有自己的最多两个客户端缓存，这是预期行为，不是跨进程共享单例。
5. 如果项目确实支持运行时变更模型、URL 或凭据，需要把有效配置加入缓存键或明确要求配置变更后重启进程。不要记录 API Key，也不要把密钥输出到日志。
6. `reset_llm()` 若保留，应仅用于测试或明确的客户端重建流程，并用同一把锁保护缓存清理；不要用它实现思考模式切换。

## 4. Agent 调用点的模式分配

先全局搜索 `get_llm()`、`with_structured_output()`、`ChatOpenAI(` 和当前 LLM 工厂的所有使用位置，以实际代码为准。建议初始映射如下：

| 调用位置 | 初始思考模式 | 说明 |
|---|---|---|
| `KnowledgeExtractAgent` / `extract_current_chunk_node` | `disabled` | 主要任务是根据来源文本提取并完整保留内容，不需要每个 Chunk 都进行深度推理。 |
| 批次内部精确去重、名称规范化、空值和字段校验 | 不调用 LLM | 通过普通 Python 规则完成。 |
| `KnowledgeDeduplicatePipeline` 的歧义候选裁决 | `enabled` | 仅在规则与向量相似度不能明确判断时调用；不要让每条候选都无条件进入深度思考。 |
| 同名但内容冲突、需要判断是否合并 | `enabled` | 必须保留来源和冲突信息，禁止无依据地将内容合并。 |
| `KnowledgeRelationAgent` | 单独配置，初期可 `disabled` 并通过测试评估 | 不要和知识提取强制共用同一个模式；根据关系判断质量、延迟和成本决定是否开启。 |
| 其他 Agent 或新功能 | 必须显式声明 | 禁止依赖全局“当前思考模式”。 |

如果现有去重 Agent 或关系 Agent 无法稳定按业务分支选择模式，先把模式配置放在各 Agent 的调用入口，而不是把思考选择逻辑散落在通用工具层。

## 5. 配置与日志要求

如项目配置风格适合，可增加独立配置项，例如：

```env
AGENT_KNOWLEDGE_EXTRACT_THINKING=disabled
AGENT_KNOWLEDGE_DEDUP_THINKING=enabled
AGENT_KNOWLEDGE_RELATION_THINKING=disabled
```

这些配置是可选设计；若当前项目规模较小，也可先在各调用点显式传入固定模式。不要为了这项功能引入 Redis、Celery、RabbitMQ 等基础设施。

日志至少记录：

- Agent 名称；
- 思考模式（enabled/disabled）；
- 模型名称；
- 请求耗时；
- 是否重试及重试次数；
- 结构化输出解析是否成功。

日志不得记录 API Key 或其他敏感凭据。不要默认打印完整思考内容。

## 6. 必须增加的测试

### 6.1 缓存测试

- 连续调用 `get_llm(thinking="disabled")`，应返回同一个对象。
- 连续调用 `get_llm(thinking="enabled")`，应返回同一个对象。
- enabled 与 disabled 应得到两个不同对象。
- 并发首次请求同一模式时，只应初始化一个对应缓存实例。
- 正常处理每个 Chunk 不得重新构造客户端。

### 6.2 请求参数隔离测试

通过 mock HTTP transport 或测试服务器捕获真正发出的请求体：

- disabled 请求携带 `thinking.type=disabled`；
- enabled 请求携带 `thinking.type=enabled`；
- 并发执行 enabled 和 disabled 请求，多次交错执行后仍各自携带正确参数；
- 确认切换调用顺序不会改变已经缓存实例的模式；
- 不得只测试 Python 对象里的 `extra_body`，必须验证实际请求体或等价的 HTTP 层行为。

### 6.3 Agent 调用测试

- 知识提取使用 disabled 实例；
- 疑难语义去重 / 冲突合并使用 enabled 实例；
- 精确去重不产生额外 LLM 调用；
- 结构化输出 `with_structured_output()` 在两种模式下均可正常运行；
- 模型报错或输出无法解析时，现有重试和错误处理仍然有效。

### 6.4 参数兼容性测试

- 验证 MiMo API 接收到的模型名为 `mimo-v2.6-pro`；
- 验证 `thinking` 扩展字段在请求体中的实际位置和取值正确；
- enabled 请求不发送自定义 `temperature`/`top_p`；
- disabled 请求的温度与当前项目配置一致；
- 验证 Token 限制参数与当前 `ChatOpenAI` 版本以及 MiMo API 兼容，防止请求失败或输出被意外截断。

## 7. 执行限制

- 只允许修改 `backend/`。
- 不修改 `admin-web/`。
- 不改动当前业务数据模型，除非发现实现该能力必不可少且说明原因。
- 不更换模型，继续使用 `mimo-v2.6-pro`。
- 不把思考模式切换实现成任务运行时对共享对象的修改。
- 不因启用两种模式而在每次请求中创建新的 `ChatOpenAI` 客户端。
- 不要仅凭单元测试通过就宣称并发安全；必须覆盖 HTTP 请求体参数隔离。

## 8. 验收标准

以下全部满足才算完成：

- [ ] 每个 Agent 的思考模式可显式配置或显式声明。
- [ ] enabled 和 disabled 分别使用进程内缓存实例。
- [ ] 同一模式重复调用返回同一实例，不会为每个 Chunk 创建实例。
- [ ] 并发任务同时运行时，每个请求都使用调用方指定的思考模式。
- [ ] 任何生产调用都不通过修改共享实例参数来切换模式。
- [ ] 现有知识提取、去重、关系处理流程及结构化输出没有被破坏。
- [ ] 思考开启时不发送 MiMo 不支持的自定义 temperature/top_p。
- [ ] 缓存初始化、并发参数隔离、结构化输出和错误处理测试通过。
- [ ] 现有后端回归测试通过。
- [ ] 提交最终报告：修改文件清单、模式映射、测试命令及结果、并发请求体验证结果、已知限制。

## 9. 官方参数参考

以小米 MiMo 官方文档为参数依据：

- OpenAI 兼容 Chat API：https://mimo.mi.com/docs/zh-CN/api/chat/openai-api
- 深度思考说明：https://mimo.mi.com/docs/zh-CN/quick-start/usage-guide/text-generation/deep-thinking

官方文档说明：通过 `extra_body={"thinking": {"type": "enabled"}}` 或 `disabled` 控制思考模式；在思考模式下，MiMo-V2.6-Pro 不支持自定义 `temperature` 和 `top_p`。
