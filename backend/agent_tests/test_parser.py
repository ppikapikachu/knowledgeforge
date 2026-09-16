"""DocumentParser 测试模块。

测试内容：
    1. TXT 文件解析（段落分割、编码处理）
    2. MD 文件解析（标题层级保留）
    3. 异常处理（不存在的文件、不支持的类型）
    4. 真实测试数据（android_sample.txt）
"""

import os
import tempfile

import pytest

from agent.knowledge_extract.parser import DocumentParser
from agent.knowledge_extract.schemas import StructuredDocument


@pytest.fixture
def parser():
    """创建解析器实例。"""
    return DocumentParser()


@pytest.fixture
def sample_txt_file():
    """创建临时 TXT 测试文件。

    内容包含两个章节（双换行符分隔），
    用于验证解析器的段落分割能力。
    """
    content = """# Android面试

## Activity生命周期

Activity是Android四大组件之一。

## Handler机制

Handler是线程间通信的核心。"""
    path = tempfile.mktemp(suffix=".txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    yield path
    os.unlink(path)  # 测试结束后清理临时文件


@pytest.fixture
def sample_md_file():
    """创建临时 MD 测试文件。

    内容包含多级标题（# ## ###），
    用于验证解析器的标题层级保留能力。
    """
    content = """# Android面试题

## Activity生命周期

Activity具有完整生命周期。

### onCreate

Activity创建时调用。

## Handler消息机制

Handler用于线程间通信。"""
    path = tempfile.mktemp(suffix=".md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    yield path
    os.unlink(path)


class TestDocumentParser:
    """文档解析器测试类。"""

    def test_parse_txt(self, parser, sample_txt_file):
        """测试解析 TXT 文件。

        验证点：
            - 返回类型为 StructuredDocument
            - 文件类型为 "txt"
            - 至少产生 1 个页面
            - 完整文本非空
            - 文本中包含预期关键词
        """
        doc = parser.parse(sample_txt_file)
        assert isinstance(doc, StructuredDocument)
        assert doc.file_type == "txt"
        assert len(doc.pages) > 0
        assert len(doc.full_text) > 0
        assert "Activity" in doc.full_text

    def test_parse_markdown(self, parser, sample_md_file):
        """测试解析 MD 文件，验证标题被保留。

        验证点：
            - 返回类型为 StructuredDocument
            - 文件类型为 "md"
            - 至少产生 1 个页面
            - 页面标题列表非空（MD 标题被保留）
        """
        doc = parser.parse(sample_md_file)
        assert isinstance(doc, StructuredDocument)
        assert doc.file_type == "md"
        assert len(doc.pages) > 0
        # 验证标题被保留
        titles = [p.title for p in doc.pages if p.title]
        assert len(titles) > 0

    def test_parse_nonexistent_file(self, parser):
        """测试解析不存在的文件，应抛出 FileNotFoundError。"""
        with pytest.raises(FileNotFoundError):
            parser.parse("/nonexistent/file.txt")

    def test_parse_unsupported_type(self, parser):
        """测试解析不支持的文件类型（.xyz），应抛出 ValueError。"""
        with tempfile.NamedTemporaryFile(suffix=".xyz", delete=False) as f:
            f.write(b"test")
            f.name
        try:
            with pytest.raises(ValueError, match="不支持的文件类型"):
                parser.parse(f.name)
        finally:
            os.unlink(f.name)

    def test_parse_real_fixture(self, parser):
        """测试解析真实的 android_sample.txt 测试数据。

        验证点：
            - 文件存在时能正常解析
            - 文本长度 > 100 字符
            - 包含 "Activity" 关键词
        """
        fixture_path = os.path.join(
            os.path.dirname(__file__),
            "fixtures",
            "android_sample.txt",
        )
        if os.path.exists(fixture_path):
            doc = parser.parse(fixture_path)
            assert isinstance(doc, StructuredDocument)
            assert doc.file_type == "txt"
            assert len(doc.full_text) > 100
            assert "Activity" in doc.full_text
