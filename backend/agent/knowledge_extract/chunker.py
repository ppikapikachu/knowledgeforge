"""自适应文本分块器。

将文档单元聚合为目标大小的 Chunk。
支持多种文档格式，不依赖单一的 Q&A 模式。

分块策略：
    1. 使用 BoundaryDetector 识别文档单元
    2. 过滤噪声（版权声明、URL 等）
    3. 将多个单元聚合到 chunk_size 目标
    4. 短块合并 + 最小长度保护
    5. 保留单元来源映射
"""

import logging
import uuid
from typing import List

from agent.common.config import agent_settings
from agent.knowledge_extract.boundary import BoundaryDetector
from agent.knowledge_extract.schemas import DocumentChunk, StructuredDocument
from agent.knowledge_extract.units import DocumentUnit

logger = logging.getLogger(__name__)

# 最小 Chunk 长度
MIN_CHUNK_LENGTH = 100


class TextChunker:
    """自适应文本分块器。"""

    def __init__(self, chunk_size: int = None, chunk_overlap: int = None):
        self.chunk_size = chunk_size or agent_settings.CHUNK_SIZE
        self.chunk_overlap = chunk_overlap or agent_settings.CHUNK_OVERLAP
        self.detector = BoundaryDetector()

    def chunk(self, document: StructuredDocument) -> List[DocumentChunk]:
        """将文档切分为 Chunk 列表。"""
        text = document.full_text

        # 1. 识别文档单元
        units = self.detector.detect_units(text)
        logger.info(f"识别到 {len(units)} 个文档单元")

        # 2. 过滤噪声
        units = self.detector.filter_noise(units)
        logger.info(f"过滤噪声后: {len(units)} 个单元")

        # 3. 聚合为 Chunk
        chunks = self._aggregate_units_to_chunks(units)
        logger.info(f"聚合为 {len(chunks)} 个 Chunk")

        # 4. 最终保护：合并极短 Chunk
        chunks = self._merge_tiny_chunks(chunks)

        logger.info(f"分块完成: {len(chunks)} 个 Chunk")
        return chunks

    def _aggregate_units_to_chunks(self, units: List[DocumentUnit]) -> List[DocumentChunk]:
        """将文档单元聚合为目标大小的 Chunk。"""
        if not units:
            return []

        chunks = []
        current_text = ""
        current_start = 0
        current_end = 0
        current_title = None
        current_section = None
        current_unit_ids = []

        for unit in units:
            unit_len = len(unit.text)

            # 当前 Chunk + 新单元超过 chunk_size → 保存当前 Chunk
            if current_text and len(current_text) + unit_len + 2 > self.chunk_size:
                chunks.append(self._make_chunk(
                    current_text, current_title, current_section,
                    current_start, current_end, current_unit_ids,
                ))
                current_text = ""
                current_title = None
                current_unit_ids = []

            # 开始新 Chunk 或追加
            if not current_text:
                current_text = unit.text
                current_start = unit.source_start
                current_title = unit.section_context
                current_section = unit.section_context
            else:
                current_text += "\n\n" + unit.text

            current_end = unit.source_end
            current_unit_ids.append(unit.unit_id)

        # 保存最后一个 Chunk
        if current_text:
            chunks.append(self._make_chunk(
                current_text, current_title, current_section,
                current_start, current_end, current_unit_ids,
            ))

        return chunks

    def _merge_tiny_chunks(self, chunks: List[DocumentChunk]) -> List[DocumentChunk]:
        """合并极短的 Chunk。"""
        if not chunks:
            return []

        result = []
        for chunk in chunks:
            if result and len(chunk.text) < MIN_CHUNK_LENGTH:
                prev = result[-1]
                combined = prev.text + "\n\n" + chunk.text
                result[-1] = DocumentChunk(
                    chunk_id=prev.chunk_id,
                    text=combined,
                    title=prev.title or chunk.title,
                    page_start=prev.page_start,
                    page_end=chunk.page_end,
                    char_start=prev.char_start,
                    char_end=chunk.char_end,
                )
            else:
                result.append(chunk)

        return result

    def _make_chunk(
        self,
        text: str,
        title: str,
        section: str,
        char_start: int,
        char_end: int,
        unit_ids: List[str],
    ) -> DocumentChunk:
        """创建 DocumentChunk 实例。"""
        display_title = section or title

        return DocumentChunk(
            chunk_id=f"chunk_{uuid.uuid4().hex[:8]}",
            text=text,
            title=display_title,
            page_start=None,
            page_end=None,
            char_start=char_start,
            char_end=char_end,
        )
