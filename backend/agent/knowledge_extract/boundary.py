"""通用文档边界识别器。

从原始文本中识别逻辑单元边界，支持多种格式：
    1. 编号问答（1、2. 等）
    2. 符号列表（*、-、□、• 等）
    3. Markdown 标题（#、## 等）
    4. 空行分段
    5. 单换行文本
    6. 无标记连续文本
    7. 混合格式

设计原则：
    - 高置信度边界优先使用确定性规则
    - 低置信度时不强行判定，保留为较大单元
    - 不因格式标记误切（如正文中的 * 号）
    - 标题作为上下文，不单独成单元
"""

import re
import uuid
from typing import List, Optional, Tuple

from agent.knowledge_extract.units import DocumentUnit

# 顶层题目编号：1、2、3. 等（行首）
TOP_QUESTION_PATTERN = re.compile(r"^\s*(\d+)\s*[、.]\s*\S", re.MULTILINE)

# 答案内子项：1）2）3）等
SUB_ITEM_PATTERN = re.compile(r"^\s*\d+\s*[）)]\s*", re.MULTILINE)

# Markdown 标题
MD_HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)

# 列表标记：*、-、□、•、· 等（行首）
LIST_ITEM_PATTERN = re.compile(r"^\s*[*\-□•·+]\s+\S", re.MULTILINE)

# 章节标题（常见面试题章节）
SECTION_TITLE_PATTERN = re.compile(
    r"^[A-Za-z\u4e00-\u9fff]{2,20}面试题\s*$"
    r"|^Activity$|^Fragment面试题$|^Service面试题$"
    r"|^IPC面试题$|^view面试题$",
    re.MULTILINE,
)

# 空行
BLANK_LINE_PATTERN = re.compile(r"\n\s*\n")

# 版权声明/页眉页脚（高置信度过滤）
NOISE_PATTERNS = [
    re.compile(r"^版权声明[:：].*$", re.MULTILINE),
    re.compile(r"^原文链接[:：].*$", re.MULTILINE),
    re.compile(r"^https?://\S+$", re.MULTILINE),
    re.compile(r"^—+\s*$", re.MULTILINE),
]


class BoundaryDetector:
    """通用文档边界识别器。"""

    def detect_units(self, text: str) -> List[DocumentUnit]:
        """从原始文本识别文档单元。

        策略：
            1. 先识别高置信度边界（编号题目、Markdown 标题）
            2. 再按空行/段落切分剩余内容
            3. 合并过短单元
            4. 过滤噪声内容

        Args:
            text: 原始文本

        Returns:
            DocumentUnit 列表（按原文顺序）
        """
        # 尝试多种识别策略，取最优结果
        qa_units = self._detect_qa_units(text)
        md_units = self._detect_markdown_units(text)
        para_units = self._detect_paragraph_units(text)

        # 选择识别效果最好的策略
        # 优先级：Q&A > Markdown > 段落
        if qa_units and len(qa_units) >= 2:
            units = qa_units
        elif md_units and len(md_units) >= 2:
            units = md_units
        else:
            units = para_units

        # 合并过短单元
        units = self._merge_tiny_units(units)

        # 重新分配 unit_id
        for i, unit in enumerate(units):
            unit.unit_id = f"unit_{i+1:04d}"

        return units

    def _detect_qa_units(self, text: str) -> List[DocumentUnit]:
        """识别编号问答格式的单元。"""
        matches = list(TOP_QUESTION_PATTERN.finditer(text))
        if len(matches) < 2:
            return []

        units = []
        section_context = None

        for i, match in enumerate(matches):
            start = match.start()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            block_text = text[start:end].rstrip()
            first_line = block_text.split("\n")[0].strip()

            # 章节标题作为上下文
            if SECTION_TITLE_PATTERN.match(first_line):
                section_context = first_line
                continue

            marker = match.group(0).strip()
            title = re.sub(r"^\s*\d+\s*[、.]\s*", "", first_line).strip()

            units.append(DocumentUnit(
                unit_id=f"unit_{len(units)+1:04d}",
                text=block_text,
                source_start=start,
                source_end=end,
                unit_kind="qa",
                section_context=section_context,
                marker=marker,
                boundary_confidence=0.9,
            ))

        return units

    def _detect_markdown_units(self, text: str) -> List[DocumentUnit]:
        """识别 Markdown 格式的单元。"""
        matches = list(MD_HEADING_PATTERN.finditer(text))
        if len(matches) < 2:
            return []

        units = []
        for i, match in enumerate(matches):
            level = len(match.group(1))
            heading = match.group(2).strip()
            start = match.start()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            block_text = text[start:end].rstrip()

            units.append(DocumentUnit(
                unit_id=f"unit_{len(units)+1:04d}",
                text=block_text,
                source_start=start,
                source_end=end,
                unit_kind="heading",
                section_context=heading,
                marker=match.group(1),
                boundary_confidence=0.85,
            ))

        return units

    def _detect_paragraph_units(self, text: str) -> List[DocumentUnit]:
        """按空行分段识别单元（通用回退）。"""
        units = []
        last_end = 0

        for match in BLANK_LINE_PATTERN.finditer(text):
            para_text = text[last_end:match.start()].strip()
            if para_text:
                start = text.find(para_text[:50], last_end)
                if start == -1:
                    start = last_end
                end = start + len(para_text)

                # 判断单元类型
                kind = "paragraph"
                marker = None
                confidence = 0.5

                first_line = para_text.split("\n")[0].strip()
                if LIST_ITEM_PATTERN.match(first_line):
                    kind = "list_item"
                    marker = first_line[0]
                    confidence = 0.6
                elif SUB_ITEM_PATTERN.match(first_line):
                    kind = "list_item"
                    marker = SUB_ITEM_PATTERN.match(first_line).group(0).strip()
                    confidence = 0.6

                units.append(DocumentUnit(
                    unit_id=f"unit_{len(units)+1:04d}",
                    text=para_text,
                    source_start=start,
                    source_end=end,
                    unit_kind=kind,
                    marker=marker,
                    boundary_confidence=confidence,
                ))

            last_end = match.end()

        # 处理最后一段
        remaining = text[last_end:].strip()
        if remaining:
            start = text.find(remaining[:50], last_end)
            if start == -1:
                start = last_end
            units.append(DocumentUnit(
                unit_id=f"unit_{len(units)+1:04d}",
                text=remaining,
                source_start=start,
                source_end=start + len(remaining),
                unit_kind="paragraph",
                boundary_confidence=0.5,
            ))

        return units

    def _merge_tiny_units(self, units: List[DocumentUnit]) -> List[DocumentUnit]:
        """合并过短的单元。"""
        if not units:
            return []

        MIN_UNIT_LENGTH = 50
        merged = []
        current = units[0]

        for next_unit in units[1:]:
            if len(current.text) < MIN_UNIT_LENGTH:
                # 合并到下一个单元
                combined_text = current.text + "\n\n" + next_unit.text
                current = DocumentUnit(
                    unit_id=current.unit_id,
                    text=combined_text,
                    source_start=current.source_start,
                    source_end=next_unit.source_end,
                    unit_kind=current.unit_kind,
                    section_context=current.section_context or next_unit.section_context,
                    marker=current.marker,
                    boundary_confidence=min(current.boundary_confidence, next_unit.boundary_confidence),
                )
            else:
                merged.append(current)
                current = next_unit

        merged.append(current)
        return merged

    def filter_noise(self, units: List[DocumentUnit]) -> List[DocumentUnit]:
        """过滤噪声单元（版权声明、URL 等）。"""
        result = []
        for unit in units:
            is_noise = False
            for pattern in NOISE_PATTERNS:
                if pattern.match(unit.text.strip()):
                    is_noise = True
                    break

            # 过滤纯空白/极短无意义内容
            if len(unit.text.strip()) < 3:
                is_noise = True

            if not is_noise:
                result.append(unit)

        return result
