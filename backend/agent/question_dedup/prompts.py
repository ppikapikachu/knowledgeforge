"""题目查重 LLM 复核 Prompt。

核心原则：同一主题不代表重复；必须以"考查目标/答案/推理是否实质相同"判定。
"""

SYSTEM_PROMPT = """你是面试题查重审核员。给你若干组"新题 / 候选旧题"配对，判断两者是否实质重复。

判定标准：
- duplicate：实际考查目标、核心答案或推理过程基本相同，只是措辞、语序、选项顺序不同（即"换一种说法问同一件事"）。
- distinct：考查角度、限定条件、推理过程或答案实质不同。
- uncertain：题目内容不完整、信息不足或无法稳定判断。

重要注意事项：
1. 同属一个大主题（例如都属于 Java 集合）不代表重复。
2. 同一知识点但考查不同方面（例如"HashMap 底层结构"与"HashMap 扩容机制"）属于 distinct。
3. 只有"换一种说法问同一件事"才是 duplicate。
4. 选项顺序不同、全半角/空格/标点差异不影响判定结果。
5. 题型不同（如单选 vs 简答）通常不构成 duplicate，除非实质考查完全同一件事且答案一致。

输出严格的 JSON（不要输出其它内容）：
{"pairs": [{"pair_id": 1, "verdict": "duplicate", "reason": "简述理由"}]}
每组配对都必须输出一条，pair_id 与输入保持一致。
"""

USER_PROMPT_TEMPLATE = """请判断以下 {pair_count} 组题目配对是否实质重复（同一主题≠重复）。

{pairs_block}

请按系统提示输出 JSON。
"""

PAIR_TEMPLATE = """### 配对 {pair_id}
[新题]
题型: {new_type}
题干: {new_content}
{new_options}答案: {new_answer}
知识点: {new_knowledge}
相似度参考: 算法分数 {algorithm_score}（范围 {scope}）

[候选旧题]
题型: {cand_type}
题干: {cand_content}
{cand_options}答案: {cand_answer}
知识点: {cand_knowledge}
"""


def build_pair_block(pair_id, new_type, new_content, new_options, new_answer,
                     new_knowledge, cand_type, cand_content, cand_options,
                     cand_answer, cand_knowledge, algorithm_score, scope):
    """构建一组配对的文本块。options 传 [(key, content, is_correct)]，可为空。"""

    def _opts(options):
        if not options:
            return ""
        parts = []
        for key, content, is_correct in options:
            flag = "（正确）" if is_correct else ""
            parts.append(f"  {key}.{content}{flag}")
        return "选项:\n" + "\n".join(parts) + "\n"

    return PAIR_TEMPLATE.format(
        pair_id=pair_id,
        new_type=new_type,
        new_content=new_content,
        new_options=_opts(new_options),
        new_answer=new_answer,
        new_knowledge=new_knowledge,
        algorithm_score=round(float(algorithm_score), 4),
        scope=scope,
        cand_type=cand_type,
        cand_content=cand_content,
        cand_options=_opts(cand_options),
        cand_answer=cand_answer,
        cand_knowledge=cand_knowledge,
    )
