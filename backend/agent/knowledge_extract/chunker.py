"""文本分块器模块。

本模块负责将 StructuredDocument 切分为可处理的 DocumentChunk 列表。
分块是 Agent 工作流的关键步骤，直接影响 LLM 的理解质量和 Token 成本。

分块策略优先级：
    1. 标题边界 —— 优先按文档标题/章节切分
    2. 段落边界 —— 其次按段落（双换行符）切分
    3. 句子边界 —— 再次按句子切分（兜底策略）
    4. 字符长度 —— 最后按 chunk_size 强制切分

为什么不能简单按字符长度切分：
    - 会切断句子中间，破坏语义完整性
    - 会切断知识点的上下文，导致 LLM 理解困难
    - 标题信息丢失，LLM 无法判断知识层级

重叠（Overlap）的作用：
    - 相邻 Chunk 之间有 overlap 字符的重叠
    - 保证知识点在 Chunk 边界处不会被截断
    - LLM 能从重叠部分获取上下文信息

配置说明：
    - chunk_size: 每个 Chunk 的目标字符数，建议 5000~8000
    - chunk_overlap: 重叠字符数，建议为 chunk_size 的 5%~15%
    - 通过 .env 文件配置，不硬编码在代码中
"""

import logging
import re
import uuid
from typing import List

from agent.common.config import agent_settings
from agent.knowledge_extract.schemas import DocumentChunk, StructuredDocument

logger = logging.getLogger(__name__)


class TextChunker:
    """文本分块器，将 StructuredDocument 切分为 DocumentChunk 列表。

    使用方法：
        chunker = TextChunker(chunk_size=6000, chunk_overlap=500)
        chunks = chunker.chunk(document)
        for chunk in chunks:
            print(chunk.chunk_id, len(chunk.text))
    """

    def __init__(
        self,
        chunk_size: int = None,
        chunk_overlap: int = None,
    ):
        """初始化分块器。

        Args:
            chunk_size: Chunk 目标大小（字符数），默认从配置读取
            chunk_overlap: 相邻 Chunk 重叠大小（字符数），默认从配置读取
        """
        self.chunk_size = chunk_size or agent_settings.CHUNK_SIZE
        self.chunk_overlap = chunk_overlap or agent_settings.CHUNK_OVERLAP

    def chunk(self, document: StructuredDocument) -> List[DocumentChunk]:
        """将文档切分为 Chunk 列表。

        处理流程：
            1. 遍历文档的每个页面/章节
            2. 如果页面内容 <= chunk_size，直接作为一个 Chunk
            3. 如果页面内容 > chunk_size，调用 _split_long_text 进一步拆分
            4. 如果没有任何 Chunk（如空文档），用全文创建一个

        Args:
            document: 解析后的结构化文档

        Returns:
            DocumentChunk 列表
        """
        all_chunks = []
        current_pos = 0  # 当前在 full_text 中的扫描位置

        for page in document.pages:
            page_text = page.text.strip()
            if not page_text:
                continue

            # 定位当前页面在 full_text 中的起始位置
            # 使用前 100 个字符作为锚点搜索
            page_start_in_doc = document.full_text.find(page_text[:100], current_pos)
            if page_start_in_doc == -1:
                page_start_in_doc = current_pos

            if len(page_text) <= self.chunk_size:
                # 页面内容未超过 chunk_size，作为一个完整 Chunk
                chunk = DocumentChunk(
                    chunk_id=f"chunk_{uuid.uuid4().hex[:8]}",
                    text=page_text,
                    title=page.title,
                    page_start=page.page_number,
                    page_end=page.page_number,
                    char_start=page_start_in_doc,
                    char_end=page_start_in_doc + len(page_text),
                )
                all_chunks.append(chunk)
            else:
                # 页面内容过长，需要进一步拆分
                sub_chunks = self._split_long_text(
                    text=page_text,
                    title=page.title,
                    page_number=page.page_number,
                    base_offset=page_start_in_doc,
                )
                all_chunks.extend(sub_chunks)

            current_pos = page_start_in_doc + len(page_text)

        # 兜底：如果没有任何 Chunk，用全文创建一个
        if not all_chunks and document.full_text.strip():
            all_chunks.append(DocumentChunk(
                chunk_id=f"chunk_{uuid.uuid4().hex[:8]}",
                text=document.full_text[:self.chunk_size],
                title=None,
                page_start=None,
                page_end=None,
                char_start=0,
                char_end=min(len(document.full_text), self.chunk_size),
            ))

        logger.info(f"文档分块完成，共 {len(all_chunks)} 个 Chunk")
        return all_chunks

    def _split_long_text(
        self,
        text: str,
        title: str,
        page_number: int,
        base_offset: int,
    ) -> List[DocumentChunk]:
        """拆分过长文本，优先按段落边界拆分。

        处理流程：
            1. 按双换行符（\\n\\n）分割为段落
            2. 逐段落累加到当前 Chunk
            3. 如果累加后超过 chunk_size，保存当前 Chunk 并开始新 Chunk
            4. 如果单个段落就超过 chunk_size，调用 _split_by_sentences 按句子拆分
            5. 新 Chunk 带上 overlap 以保持上下文连续性
        """
        chunks = []

        # 按双换行符分割为段落
        paragraphs = re.split(r"\n\s*\n", text)

        current_chunk_text = ""  # 当前正在积累的 Chunk 文本
        current_offset = 0       # 当前段落在原文中的偏移量

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            # 单个段落超过 chunk_size，需要按句子拆分
            if len(para) > self.chunk_size:
                # 先保存已积累的文本
                if current_chunk_text:
                    chunks.append(self._make_chunk(
                        current_chunk_text, title, page_number,
                        base_offset + current_offset,
                    ))
                    current_offset += len(current_chunk_text) + 2  # +2 为 \n\n
                    current_chunk_text = ""

                # 按句子拆分这个长段落
                sentence_chunks = self._split_by_sentences(
                    para, title, page_number,
                    base_offset + current_offset,
                )
                chunks.extend(sentence_chunks)
                current_offset += len(para) + 2
                continue

            # 尝试将当前段落加入 Chunk
            if current_chunk_text and len(current_chunk_text) + len(para) + 2 > self.chunk_size:
                # 加入后会超过 chunk_size，保存当前 Chunk
                chunks.append(self._make_chunk(
                    current_chunk_text, title, page_number,
                    base_offset + current_offset,
                ))
                # 新 Chunk 带上 overlap 部分以保持上下文
                if len(current_chunk_text) > self.chunk_overlap:
                    overlap_text = current_chunk_text[-self.chunk_overlap:]
                else:
                    overlap_text = ""
                current_offset += len(current_chunk_text) + 2
                current_chunk_text = overlap_text + "\n\n" + para if overlap_text else para
            else:
                # 加入后未超过 chunk_size，继续累加
                if current_chunk_text:
                    current_chunk_text += "\n\n" + para
                else:
                    current_chunk_text = para

        # 保存最后一个 Chunk
        if current_chunk_text:
            chunks.append(self._make_chunk(
                current_chunk_text, title, page_number,
                base_offset + current_offset,
            ))

        return chunks

    def _split_by_sentences(
        self,
        text: str,
        title: str,
        page_number: int,
        base_offset: int,
    ) -> List[DocumentChunk]:
        """按句子拆分文本（段落拆分仍不够时的兜底策略）。

        按中英文句号、感叹号、问号分割句子。
        同样支持 overlap 以保持上下文连续性。
        """
        chunks = []
        # 按中英文句子结束符分割
        sentences = re.split(r"(?<=[。！？.!?])\s*", text)

        current_text = ""
        current_offset = 0

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue

            if current_text and len(current_text) + len(sentence) + 1 > self.chunk_size:
                # 保存当前 Chunk
                chunks.append(self._make_chunk(
                    current_text, title, page_number,
                    base_offset + current_offset,
                ))
                # 带 overlap 开始新 Chunk
                if len(current_text) > self.chunk_overlap:
                    overlap = current_text[-self.chunk_overlap:]
                else:
                    overlap = ""
                current_offset += len(current_text) + 1
                current_text = overlap + " " + sentence if overlap else sentence
            else:
                current_text = (current_text + " " + sentence).strip() if current_text else sentence

        # 保存最后一个 Chunk
        if current_text:
            chunks.append(self._make_chunk(
                current_text, title, page_number,
                base_offset + current_offset,
            ))

        return chunks

    def _make_chunk(
        self,
        text: str,
        title: str,
        page_number: int,
        offset: int,
    ) -> DocumentChunk:
        """创建一个 DocumentChunk 实例。

        为每个 Chunk 生成唯一的 chunk_id（UUID 前 8 位）。
        """
        return DocumentChunk(
            chunk_id=f"chunk_{uuid.uuid4().hex[:8]}",
            text=text,
            title=title,
            page_start=page_number,
            page_end=page_number,
            char_start=offset,
            char_end=offset + len(text),
        )
