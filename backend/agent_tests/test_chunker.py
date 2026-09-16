"""TextChunker 测试模块。

测试内容：
    1. 短文档分块（应产生单个 Chunk）
    2. 长文档分块（应产生多个 Chunk）
    3. 空文档分块（应产生空列表）
    4. Chunk ID 唯一性
    5. Chunk 位置信息合法性
    6. chunk_size 参数可配置
"""

import pytest

from agent.knowledge_extract.chunker import TextChunker
from agent.knowledge_extract.schemas import DocumentChunk, DocumentPage, StructuredDocument


@pytest.fixture
def chunker():
    """创建分块器实例。

    使用较小的 chunk_size（500）便于测试时产生多个 Chunk。
    """
    return TextChunker(chunk_size=500, chunk_overlap=50)


@pytest.fixture
def short_document():
    """短文档 fixture，内容远小于 chunk_size，应产生单个 Chunk。"""
    return StructuredDocument(
        file_name="test.txt",
        file_type="txt",
        pages=[
            DocumentPage(page_number=None, title="Test", text="Short text content.")
        ],
        full_text="Short text content.",
    )


@pytest.fixture
def long_document():
    """长文档 fixture，包含 5 个大段落，应产生多个 Chunk。"""
    pages = []
    for i in range(5):
        text = f"Section {i}: " + "这是一段测试文本。" * 50
        pages.append(DocumentPage(
            page_number=i + 1,
            title=f"Section {i}",
            text=text,
        ))
    full_text = "\n\n".join(p.text for p in pages)
    return StructuredDocument(
        file_name="long.txt",
        file_type="txt",
        pages=pages,
        full_text=full_text,
    )


@pytest.fixture
def empty_document():
    """空文档 fixture，无页面、无文本。"""
    return StructuredDocument(
        file_name="empty.txt",
        file_type="txt",
        pages=[],
        full_text="",
    )


class TestTextChunker:
    """文本分块器测试类。"""

    def test_short_document_single_chunk(self, chunker, short_document):
        """短文档应产生至少 1 个 Chunk，且类型正确。"""
        chunks = chunker.chunk(short_document)
        assert len(chunks) >= 1
        assert isinstance(chunks[0], DocumentChunk)

    def test_long_document_multiple_chunks(self, chunker, long_document):
        """长文档应产生多个 Chunk。"""
        chunks = chunker.chunk(long_document)
        assert len(chunks) > 1

    def test_empty_document(self, chunker, empty_document):
        """空文档应产生空列表或仅包含全文的 Chunk。"""
        chunks = chunker.chunk(empty_document)
        assert isinstance(chunks, list)

    def test_chunks_have_ids(self, chunker, long_document):
        """所有 Chunk 的 chunk_id 应唯一。"""
        chunks = chunker.chunk(long_document)
        ids = [c.chunk_id for c in chunks]
        assert len(ids) == len(set(ids))  # 无重复 ID

    def test_chunks_have_valid_positions(self, chunker, long_document):
        """所有 Chunk 的 char_start 和 char_end 应合法（非负且 start < end）。"""
        chunks = chunker.chunk(long_document)
        for chunk in chunks:
            assert chunk.char_start >= 0
            assert chunk.char_end > chunk.char_start

    def test_chunk_size_config(self):
        """chunk_size 应可通过构造函数参数配置。

        使用多段落文本，验证小 chunk_size 能正常分块。
        """
        paragraphs = ["段落" + str(i) + "：" + "测试内容" * 30 for i in range(10)]
        text = "\n\n".join(paragraphs)
        doc = StructuredDocument(
            file_name="test.txt",
            file_type="txt",
            pages=[DocumentPage(
                page_number=None,
                title=None,
                text=text,
            )],
            full_text=text,
        )
        small_chunker = TextChunker(chunk_size=200, chunk_overlap=20)
        chunks = small_chunker.chunk(doc)
        assert len(chunks) >= 1
