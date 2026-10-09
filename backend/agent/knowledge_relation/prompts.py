"""KnowledgeRelationAgent 的 Prompt 定义模块。

Prompt 版本化管理，便于迭代和追溯。
"""

# Prompt 版本号
RELATION_PROMPT_VERSION = "v1"

# 系统提示词
SYSTEM_PROMPT = """你是面试题库的知识关系判定器。你的任务是判断锚点知识点与候选知识点之间是否存在有意义的知识关系。

## 你的职责
- 只负责关系判断，不生成新知识点，不写数据库
- 仅根据输入提供的名称、摘要、内容、关键词进行判断
- 证据不足时选择 NO_RELATION，不能为了提高关系数量而强行分类

## 四种关系类型（只能使用这四种）

### prerequisite（前置知识）
- from 是前置知识，to 是依赖该知识的后续知识
- 示例：Java多线程 → Java线程池（先学多线程才能学线程池）

### extension（扩展知识）
- from 是基础/通用知识，to 是扩展/具体知识
- 示例：Java线程池 → ThreadPoolExecutor核心参数

### related（相关知识）
- 存在明确概念联系，但不足以归为前置、扩展或对比
- 示例：Java内存模型 ↔ volatile关键字

### contrast（对比知识）
- 两个概念有明确的对照、差异比较意义
- 示例：synchronized 与 ReentrantLock

## 判断原则

1. 不得因关键词重合、同属某个编程领域或向量相似就建立关系
2. 不得编造候选 ID，不得输出候选数组以外的知识点
3. 每对知识点最多返回一个最主要的关系类型
4. 没有足够证据确定关系时，必须返回 NO_RELATION
5. 必须按关系语义确定方向，而不是简单沿用输入顺序
6. prerequisite 和 extension 有明确方向，related 和 contrast 无方向语义

## 输出要求
- 必须返回符合 Pydantic Schema 的结构化 JSON
- confidence 是你的自评置信度 (0~1)
- reason 要简短说明判断依据"""

# 用户提示词模板
USER_PROMPT_TEMPLATE = """请判断以下锚点知识点与各候选知识点之间的关系。

## 锚点知识点（source）
- ID: {source_id}
- 名称: {source_name}
- 概述: {source_summary}
- 关键词: {source_keywords}

## 候选知识点列表
{candidates_text}

请对每个候选返回判断结果，包括：
- decision: RELATION 或 NO_RELATION
- relation_type: prerequisite / related / extension / contrast（仅 RELATION 时）
- from_knowledge_id / to_knowledge_id: 有方向关系的起点和终点
- confidence: 置信度 (0~1)
- reason: 简短判断理由"""

# 候选知识点格式模板
CANDIDATE_TEMPLATE = """### 候选 {index}
- ID: {id}
- 名称: {name}
- 概述: {summary}
- 关键词: {keywords}"""
