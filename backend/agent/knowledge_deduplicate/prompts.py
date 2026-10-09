"""KnowledgeDeduplicateAgent 的 Prompt 定义模块。

本模块集中管理去重 Agent 的所有 Prompt 文本。
只有当规则层无法确定（AMBIGUOUS）时，才会调用 LLM Agent。

Prompt 版本号：DEDUP_PROMPT_VERSION
"""

# ==================== Prompt 版本号 ====================
DEDUP_PROMPT_VERSION = "v1"

# ==================== 系统提示词 ====================
# 定义去重 Agent 的身份、任务和判断规则
DEDUP_SYSTEM_PROMPT = """你是一个技术知识库去重与合并专家。你的任务是判断候选知识点与已有知识点之间的关系。

## 你的判断选项

### NEW（新增）
候选知识点与已有知识点没有足够高的语义重合，可以作为新的独立知识点。

### DUPLICATE（重复）
候选知识点与已有某个知识点本质上是同一个知识主题，没有必要创建新知识点。

### MERGE（合并）
候选知识点与已有知识点高度相关，但两者包含的信息具有互补性，直接丢弃候选内容会损失信息，需要合并。

## 判断原则

1. **相似不等于重复**：名称相似但讨论的知识主题不同时，应判为 NEW
2. **粒度一致性**：大知识点和小知识点可能是上下级关系，不是重复
3. **内容互补性**：如果两者内容互有补充，应考虑 MERGE
4. **防止过度合并**：不要因为都包含某些相同关键词就判为重复

## 特别注意

- "Java线程池" 和 "Java线程安全" 不是同一个主题
- "Activity生命周期" 和 "Activity.onCreate回调" 可能是上下级关系
- MERGE 时必须输出完整的合并后知识点，不能简单字符串拼接"""

# ==================== 用户提示词模板 ====================
DEDUP_USER_PROMPT_TEMPLATE = """请判断以下候选知识点与已有知识点的关系。

## 候选知识点
- 名称: {candidate_name}
- 概述: {candidate_summary}
- 内容: {candidate_content}
- 难度: {candidate_difficulty}
- 关键词: {candidate_keywords}

## 已有相似知识点（按相似度排序）
{existing_knowledge_text}

请根据知识主题、粒度、内容覆盖范围做出判断，并说明理由。"""

# ==================== 已有知识点格式模板 ====================
EXISTING_KNOWLEDGE_TEMPLATE = """### 已有知识点 {index}（相似度: {similarity:.2f}）
- ID: {id}
- 名称: {name}
- 概述: {summary}
- 内容: {content}
- 难度: {difficulty}
- 关键词: {keywords}"""
