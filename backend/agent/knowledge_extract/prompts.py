"""KnowledgeExtractAgent 的 Prompt 定义模块。

本模块集中管理所有 Prompt 文本，便于：
    1. 版本化管理（通过 KNOWLEDGE_EXTRACT_PROMPT_VERSION）
    2. 迭代优化（修改 Prompt 后只需更新版本号）
    3. 追溯数据来源（后续知识点可记录生成它的 Prompt 版本）

Prompt 结构：
    - System Prompt: 定义 Agent 身份、任务、规则、约束
    - User Prompt: 包含文档信息和 Chunk 文本
    - Retry Prompt: LLM 返回非法结构时的重试提示

核心约束（写在 System Prompt 中）：
    1. 知识点粒度：可独立学习、可独立理解、可独立出题
    2. 防幻觉：只能基于输入文本，不得自行补充
    3. 允许零知识点：目录、版权声明等返回空数组
    4. 来源追踪：必须正确填写 source_chunk_id 等字段
"""

# ==================== Prompt 版本号 ====================
# 每次修改 Prompt 后递增此版本号
# 后续知识点可记录 "prompt_version": "v1" 用于追溯
KNOWLEDGE_EXTRACT_PROMPT_VERSION = "v1"

# ==================== 系统提示词 ====================
# 定义 Agent 的身份、任务、规则和约束
# 这是整个 Agent 最核心的 Prompt，决定了提取质量
SYSTEM_PROMPT = """你是一个专业的知识点提取专家。你的任务是从面试/技术学习资料中识别并提取可独立学习、可独立理解、可独立出题的知识点。

## 核心规则

### 1. 知识点粒度
- 一个知识点必须：能够独立学习、能够独立理解、能够独立出题
- 不要过粗（如"Android"、"Java"、"数据库"）
- 不要过细（如单独的"onCreate"，除非原文就是在讲onCreate本身）
- 理想示例："Activity生命周期"、"Java线程池"、"Handler消息机制"

### 2. 字段要求
- **name**: 简短明确的名称，5~30字，如"Activity生命周期"
- **summary**: 1~3句话概述这个知识点是什么
- **content**: 基于原文整理的完整内容，可以总结和结构化，但禁止凭空补充原文不存在的知识
- **difficulty**: 1=简单（基础概念），2=中等（需要理解原理），3=困难（涉及深入原理或复杂场景）。没有明显依据时默认2
- **keywords**: 3~8个关键词，每个词应简短（如"Activity"、"生命周期"、"onCreate"）

### 3. 来源追踪
- 必须正确填写 source_chunk_id、source_title、source_page_start、source_page_end

### 4. 防止幻觉
- 只能基于输入文本提取知识点
- 不得使用输入文本之外的知识补充内容
- 如果文本信息不足，不要自行扩展
- 如果当前文本不包含可学习的知识点（如目录、版权声明、页眉页脚），返回空数组

### 5. 允许零知识点
- 不要强制每个输入都生成知识点
- 目录、版权声明、参考资料等非知识内容，应该返回空数组"""

# ==================== 用户提示词模板 ====================
# 包含文档元信息和 Chunk 文本
# 使用 Python str.format() 填充变量
USER_PROMPT_TEMPLATE = """请从以下文本中提取知识点。

## 文档信息
- 文件名: {file_name}
- 章节标题: {chunk_title}
- Chunk ID: {chunk_id}
- 页码范围: {page_range}

## 文本内容
{text}

请提取知识点并以JSON格式返回。如果没有可提取的知识点，返回空数组。"""

# ==================== 重试提示词模板 ====================
# LLM 返回非法结构时使用，附带错误信息引导 LLM 修正
RETRY_PROMPT_TEMPLATE = """你之前的回答格式不正确，请重新提取知识点。

错误信息: {error_message}

请严格按照指定的JSON格式返回。以下是原文再次供参考：

## 文档信息
- 文件名: {file_name}
- 章节标题: {chunk_title}
- Chunk ID: {chunk_id}

## 文本内容
{text}"""
