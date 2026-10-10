# 知识导入通用化与提取质量优化 交付报告

## 一、根因与修改总结

### 根因

| 问题 | 根因 |
|------|------|
| 仅支持 Q&A 格式 | `_detect_qa_blocks` 是唯一分块策略，非 Q&A 文档回退到段落切分 |
| 无通用单元抽象 | 缺少 Document Unit 中间层，无法统一处理多格式 |
| 短块合并不足 | 虽有合并逻辑，但未覆盖所有场景 |
| 同名冲突处理简单 | 仅按长度差异判断，无互补/冲突区分 |

### 修改文件

| 文件 | 修改内容 |
|------|----------|
| `agent/knowledge_extract/units.py` | **新增** DocumentUnit 中间表示（unit_id/text/source_offset/unit_kind） |
| `agent/knowledge_extract/boundary.py` | **新增** 通用边界识别器（Q&A/Markdown/列表/段落/混合） |
| `agent/knowledge_extract/chunker.py` | **重写** 基于 DocumentUnit 的自适应分块 |
| `agent/knowledge_extract/prompts.py` | **升级 v3** 内容完整性 + 无答案跳过 |
| `agent/knowledge_deduplicate/batch_dedup.py` | **重写** 互补合并 + 冲突检测 |

## 二、通用边界识别策略

```
优先级从高到低：
1. 编号问答（1、2. 等）→ unit_kind="qa", confidence=0.9
2. Markdown 标题（# ## 等）→ unit_kind="heading", confidence=0.85
3. 列表标记（*、-、□ 等）→ unit_kind="list_item", confidence=0.6
4. 空行分段 → unit_kind="paragraph", confidence=0.5
5. 兜底 → unit_kind="unknown"
```

- 不因单一格式写死逻辑
- 低置信度不强行判定，保留为较大单元
- 标题作为上下文，不单独成单元

## 三、分块效果（导入测试.txt）

| 指标 | 修复前 | 当前 |
|------|--------|------|
| Chunk 数 | 86 | **2** |
| 最小 Chunk | 4 字符 | 4,964 字符 |
| 最大 Chunk | 587 字符 | 5,958 字符 |

## 四、批次去重改进

| 场景 | 处理 |
|------|------|
| 同名同内容 | 保留更完整版本 |
| 同名互补内容 | **合并**（保留更长 content + 合并 keywords） |
| 同名冲突内容 | 标记冲突，保留先出现版本，记录可审计信息 |

## 五、测试结果

```
95 passed, 0 failed
```

## 六、已知限制

1. 无标记连续文本的边界识别置信度低，可能产生较大 Chunk
2. 章节标题与首个问题在同一文本块时，section_context 可能未正确传递
3. 真实 LLM 提取质量需实测验证
4. 性能数据需真实环境测试
