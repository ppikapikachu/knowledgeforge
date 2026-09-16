"""知识点提取 Agent 耗时测试。

测试文件：tests/test_知识点.txt
记录各节点耗时，找出性能瓶颈。
"""

import os
import sys
import time
import io

# 设置标准输出编码为 UTF-8（解决 Windows GBK 编码问题）
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.knowledge_extract.parser import DocumentParser
from agent.knowledge_extract.chunker import TextChunker
from agent.knowledge_extract.schemas import KnowledgeExtractResult
from agent.common.config import agent_settings


def run_timing_test():
    """运行耗时测试，记录各节点的执行时间。"""

    test_file = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "tests", "test_知识点.txt"
    )

    print("=" * 70)
    print("  KnowledgeExtractAgent 耗时测试")
    print("=" * 70)
    print(f"  测试文件: {test_file}")
    print(f"  文件大小: {os.path.getsize(test_file)} 字节")
    print(f"  LLM 模型: {agent_settings.LLM_MODEL}")
    print(f"  LLM 地址: {agent_settings.LLM_BASE_URL}")
    print(f"  Chunk 大小: {agent_settings.CHUNK_SIZE}")
    print(f"  Chunk 重叠: {agent_settings.CHUNK_OVERLAP}")
    print("=" * 70)

    # ==================== 节点 1：解析文档 ====================
    print("\n[节点 1] parse_document —— 解析文档")
    t1_start = time.time()

    parser = DocumentParser()
    document = parser.parse(test_file)

    t1_end = time.time()
    t1_duration = t1_end - t1_start

    print(f"  文件类型: {document.file_type}")
    print(f"  页面数: {len(document.pages)}")
    print(f"  全文长度: {len(document.full_text)} 字符")
    print(f"  耗时: {t1_duration:.4f} 秒")

    # 打印各页面信息
    for i, page in enumerate(document.pages):
        print(f"  页面 {i+1}: title={page.title}, text_len={len(page.text)}")

    # ==================== 节点 2：文本分块 ====================
    print(f"\n[节点 2] chunk_document —— 文本分块")
    t2_start = time.time()

    chunker = TextChunker()
    chunks = chunker.chunk(document)

    t2_end = time.time()
    t2_duration = t2_end - t2_start

    print(f"  Chunk 数量: {len(chunks)}")
    print(f"  耗时: {t2_duration:.4f} 秒")

    for i, chunk in enumerate(chunks):
        print(f"  Chunk {i+1}: id={chunk.chunk_id}, "
              f"text_len={len(chunk.text)}, "
              f"title={chunk.title}, "
              f"pages={chunk.page_start}-{chunk.page_end}")

    # ==================== 节点 3：LLM 提取 ====================
    print(f"\n[节点 3] extract_current_chunk —— LLM 提取知识点")

    if not agent_settings.LLM_API_KEY:
        print("  [跳过] 未配置 LLM_API_KEY，无法调用 LLM")
        print("  如需测试 LLM 耗时，请在 .env 中配置 LLM_API_KEY")
        t3_duration = 0
        all_results = []
        errors = ["LLM_API_KEY 未配置"]
    else:
        from langchain_core.messages import HumanMessage, SystemMessage
        from agent.knowledge_extract.prompts import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE
        from agent.common.llm import get_llm
        from agent.knowledge_extract.validator import KnowledgeValidator

        llm = get_llm()
        structured_llm = llm.with_structured_output(KnowledgeExtractResult)
        validator = KnowledgeValidator()

        all_results = []
        errors = []
        t3_total_start = time.time()

        for i, chunk in enumerate(chunks):
            print(f"\n  --- Chunk {i+1}/{len(chunks)}: {chunk.chunk_id} ({len(chunk.text)} 字符) ---")

            page_range = f"第{chunk.page_start}页" if chunk.page_start else "未知"
            user_prompt = USER_PROMPT_TEMPLATE.format(
                file_name="test_知识点.txt",
                chunk_title=chunk.title or "无标题",
                chunk_id=chunk.chunk_id,
                page_range=page_range,
                text=chunk.text,
            )

            messages = [
                SystemMessage(content=SYSTEM_PROMPT),
                HumanMessage(content=user_prompt),
            ]

            chunk_start = time.time()
            try:
                result = structured_llm.invoke(messages)
                chunk_end = time.time()
                chunk_duration = chunk_end - chunk_start

                # 校验
                valid, validation_errors = validator.validate_candidates(
                    result.knowledge_points, chunk.chunk_id
                )
                result.knowledge_points = valid

                all_results.append(result)

                print(f"    提取知识点数: {len(valid)}")
                print(f"    校验错误数: {len(validation_errors)}")
                print(f"    耗时: {chunk_duration:.2f} 秒")

                for j, kp in enumerate(valid):
                    print(f"    知识点 {j+1}: {kp.name} | 难度={kp.difficulty} | 关键词={kp.keywords}")

            except Exception as e:
                chunk_end = time.time()
                chunk_duration = chunk_end - chunk_start
                error_msg = f"Chunk {chunk.chunk_id} 失败: {str(e)}"
                errors.append(error_msg)
                print(f"    [错误] {error_msg}")
                print(f"    耗时: {chunk_duration:.2f} 秒")

        t3_total_end = time.time()
        t3_duration = t3_total_end - t3_total_start

    # ==================== 节点 4：合并结果 ====================
    print(f"\n[节点 4] merge_results —— 合并结果")
    t4_start = time.time()

    all_knowledge = []
    for result in all_results:
        if result and result.knowledge_points:
            all_knowledge.extend(result.knowledge_points)

    t4_end = time.time()
    t4_duration = t4_end - t4_start

    print(f"  合并知识点总数: {len(all_knowledge)}")
    print(f"  耗时: {t4_duration:.6f} 秒")

    # ==================== 汇总 ====================
    total_duration = t1_duration + t2_duration + t3_duration + t4_duration

    print("\n" + "=" * 70)
    print("  耗时统计汇总")
    print("=" * 70)

    timings = [
        ("parse_document（解析文档）", t1_duration),
        ("chunk_document（文本分块）", t2_duration),
        ("extract_chunks（LLM 提取）", t3_duration),
        ("merge_results（合并结果）", t4_duration),
    ]

    for name, duration in timings:
        pct = (duration / total_duration * 100) if total_duration > 0 else 0
        bar = "█" * int(pct / 2)
        print(f"  {name:<30} {duration:>8.4f}s  {pct:>5.1f}%  {bar}")

    print(f"  {'-' * 58}")
    print(f"  {'总计':<30} {total_duration:>8.4f}s  100.0%")

    # 找出耗时最长的节点
    max_node = max(timings, key=lambda x: x[1])
    print(f"\n  >> 耗时最长: {max_node[0]} ({max_node[1]:.4f}s)")

    # 输出最终结果
    print("\n" + "=" * 70)
    print("  最终提取结果")
    print("=" * 70)
    print(f"  知识点总数: {len(all_knowledge)}")
    print(f"  错误数: {len(errors)}")

    if all_knowledge:
        print("\n  知识点列表:")
        for i, kp in enumerate(all_knowledge):
            print(f"    {i+1}. {kp.name}")
            print(f"       概述: {kp.summary}")
            print(f"       难度: {kp.difficulty} | 关键词: {kp.keywords}")
            print(f"       来源: {kp.source_chunk_id}")

    if errors:
        print("\n  错误列表:")
        for err in errors:
            print(f"    - {err}")

    print("\n" + "=" * 70)


if __name__ == "__main__":
    run_timing_test()
