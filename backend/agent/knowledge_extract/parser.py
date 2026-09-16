"""文档解析器模块。

本模块负责将各种格式的文件解析为统一的 StructuredDocument 结构。
支持的文件格式：PDF、DOCX、TXT、MD

设计原则：
    1. DocumentParser 是普通 Service/Tool，不是 LLM Agent
    2. 它只负责"文件 → 结构化文本"，不参与语义理解
    3. 扫描型 PDF 当前明确返回错误，不偷偷进行 OCR

解析流程：
    文件路径 → 根据扩展名分发 → 对应格式解析 → StructuredDocument

各格式解析策略：
    - TXT: 按双换行符分割为段落，尝试多种编码
    - MD: 保留标题层级结构（# ## ###），按标题分割章节
    - DOCX: 提取段落和标题样式，同时提取表格内容
    - PDF: 逐页提取文本，检测扫描型 PDF 并报错
"""

import logging
import os
import re
from pathlib import Path

from agent.knowledge_extract.schemas import DocumentPage, StructuredDocument

logger = logging.getLogger(__name__)


class DocumentParser:
    """文档解析器，将文件解析为统一的 StructuredDocument 结构。

    使用方法：
        parser = DocumentParser()
        doc = parser.parse("/path/to/file.pdf")
        print(doc.file_name, doc.full_text)
    """

    def parse(self, file_path: str) -> StructuredDocument:
        """解析文件为 StructuredDocument。

        根据文件扩展名自动选择对应的解析方法。

        Args:
            file_path: 待解析文件的绝对或相对路径

        Returns:
            StructuredDocument: 解析后的结构化文档

        Raises:
            FileNotFoundError: 文件不存在
            ValueError: 不支持的文件类型或解析失败
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"文件不存在: {file_path}")

        ext = Path(file_path).suffix.lower()  # 获取小写扩展名
        file_name = Path(file_path).name       # 获取文件名

        # 根据扩展名分发到对应的解析方法
        if ext == ".txt":
            return self._parse_txt(file_path, file_name)
        elif ext == ".md":
            return self._parse_markdown(file_path, file_name)
        elif ext == ".docx":
            return self._parse_docx(file_path, file_name)
        elif ext == ".pdf":
            return self._parse_pdf(file_path, file_name)
        else:
            raise ValueError(f"不支持的文件类型: {ext}")

    def _read_text_file(self, file_path: str) -> str:
        """读取文本文件，自动检测编码。

        依次尝试以下编码：
            1. UTF-8（最常见）
            2. UTF-8 with BOM（Windows 记事本保存的文件）
            3. GBK（中文 Windows 常见）
            4. GB2312（GBK 的子集）
            5. Latin-1（兜底，几乎不会失败）

        Returns:
            文件的文本内容

        Raises:
            ValueError: 所有编码都失败
        """
        encodings = ["utf-8", "utf-8-sig", "gbk", "gb2312", "latin-1"]
        for encoding in encodings:
            try:
                with open(file_path, "r", encoding=encoding) as f:
                    return f.read()
            except (UnicodeDecodeError, UnicodeError):
                continue
        raise ValueError(f"无法识别文件编码: {file_path}")

    def _parse_txt(self, file_path: str, file_name: str) -> StructuredDocument:
        """解析纯文本文件。

        解析策略：
            - 按双换行符（\\n\\n）分割为逻辑段落
            - 每个非空段落作为一个 DocumentPage
            - TXT 文件没有真实页码，page_number 为 None

        Args:
            file_path: 文件路径
            file_name: 文件名
        """
        text = self._read_text_file(file_path)

        # 按双换行符分割为段落
        sections = re.split(r"\n\s*\n", text.strip())
        pages = []
        for i, section in enumerate(sections):
            section = section.strip()
            if section:
                pages.append(DocumentPage(
                    page_number=None,  # TXT 无真实页码
                    title=None,        # TXT 无标题结构
                    text=section,
                ))

        # 如果没有有效段落（如文件只有一个段落），将整个文本作为一个页面
        if not pages:
            pages = [DocumentPage(page_number=None, title=None, text=text)]

        return StructuredDocument(
            file_name=file_name,
            file_type="txt",
            pages=pages,
            full_text=text,
        )

    def _parse_markdown(self, file_path: str, file_name: str) -> StructuredDocument:
        """解析 Markdown 文件，保留标题层级结构。

        解析策略：
            - 使用正则识别 Markdown 标题（# ## ### #### 等）
            - 按标题分割文档为章节
            - 每个章节的 title 保留原始标题文本
            - 同级或更高级标题作为章节分界线

        为什么保留标题结构：
            Markdown 标题对知识点提取非常重要。
            例如 "# Activity" 和 "## Activity生命周期" 明确了知识层级。

        Args:
            file_path: 文件路径
            file_name: 文件名
        """
        text = self._read_text_file(file_path)

        # 正则匹配 Markdown 标题：行首的 # 号 + 空格 + 标题文本
        heading_pattern = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
        sections = []  # (标题, 内容) 元组列表
        last_end = 0

        for match in heading_pattern.finditer(text):
            # 标题之前如果有内容（如前言），单独作为一个 section
            if match.start() > last_end:
                pre_content = text[last_end:match.start()].strip()
                if pre_content and not sections:
                    sections.append((None, pre_content))

            level = len(match.group(1))  # 标题层级：1~6
            title = match.group(2).strip()

            # 添加当前标题的 section（内容稍后填充）
            sections.append((title, ""))

            # 查找下一个同级或更高级标题的位置
            # 例如 level=2 时，匹配 # 或 ## 开头的下一行
            remaining = text[match.end():]
            next_heading = re.search(
                rf"^#{{1,{level}}}\s+", remaining, re.MULTILINE
            )
            if next_heading:
                content = remaining[:next_heading.start()].strip()
            else:
                content = remaining.strip()

            # 更新当前 section 的内容
            if sections:
                sections[-1] = (title, content)

            last_end = match.end()

        # 处理最后一个标题之后的剩余内容
        if last_end < len(text):
            remaining = text[last_end:].strip()
            if remaining and sections:
                old_title, old_content = sections[-1]
                sections[-1] = (old_title, old_content + "\n\n" + remaining)

        # 如果没有找到任何标题，将整个文本作为一个页面
        if not sections:
            sections = [(None, text)]

        # 转换为 DocumentPage 列表
        pages = []
        for title, content in sections:
            if content.strip():
                pages.append(DocumentPage(
                    page_number=None,  # MD 无真实页码
                    title=title,       # 保留 Markdown 标题
                    text=content,
                ))

        return StructuredDocument(
            file_name=file_name,
            file_type="md",
            pages=pages,
            full_text=text,
        )

    def _parse_docx(self, file_path: str, file_name: str) -> StructuredDocument:
        """解析 DOCX 文件，提取段落、标题和表格。

        解析策略：
            - 遍历所有段落，根据样式判断是否为标题
            - Heading 样式的段落作为新章节的标题
            - 普通段落作为章节内容
            - 表格内容也会被提取（以 | 分隔列）

        Args:
            file_path: 文件路径
            file_name: 文件名

        Raises:
            ValueError: 未安装 python-docx 库
        """
        try:
            from docx import Document as DocxDocument
        except ImportError:
            raise ValueError(
                "解析 DOCX 需要安装 python-docx: pip install python-docx"
            )

        doc = DocxDocument(file_path)
        pages = []
        current_text = []    # 当前章节的文本行
        current_title = None  # 当前章节标题

        for para in doc.paragraphs:
            text = para.text.strip()
            if not text:
                continue

            # 检测标题样式（Heading 1, Heading 2, 等）
            if para.style.name.startswith("Heading"):
                # 保存上一个章节
                if current_text:
                    pages.append(DocumentPage(
                        page_number=None,
                        title=current_title,
                        text="\n".join(current_text),
                    ))
                    current_text = []
                current_title = text
            else:
                current_text.append(text)

        # 保存最后一个章节
        if current_text:
            pages.append(DocumentPage(
                page_number=None,
                title=current_title,
                text="\n".join(current_text),
            ))

        # 提取表格内容（如果文档中有表格）
        for table in doc.tables:
            table_text = []
            for row in table.rows:
                # 每行的单元格用 " | " 连接
                row_text = [cell.text.strip() for cell in row.cells]
                table_text.append(" | ".join(row_text))
            if table_text:
                pages.append(DocumentPage(
                    page_number=None,
                    title=current_title,  # 表格归属当前章节
                    text="\n".join(table_text),
                ))

        # 拼接所有页面的文本作为完整文本
        full_text = "\n\n".join(p.text for p in pages)

        return StructuredDocument(
            file_name=file_name,
            file_type="docx",
            pages=pages,
            full_text=full_text,
        )

    def _parse_pdf(self, file_path: str, file_name: str) -> StructuredDocument:
        """解析 PDF 文件，逐页提取文本。

        解析策略：
            - 使用 pdfplumber 库逐页提取文本
            - 每页作为一个 DocumentPage，保留真实页码
            - 检测扫描型 PDF（提取文本极少）并报错

        扫描型 PDF 检测逻辑：
            如果提取的总文本少于 50 字但有页面，
            说明 PDF 是扫描图片而非文字型，当前版本不支持 OCR。

        Args:
            file_path: 文件路径
            file_name: 文件名

        Raises:
            ValueError: 未安装 pdfplumber、扫描型 PDF、无文本内容
        """
        try:
            import pdfplumber
        except ImportError:
            raise ValueError(
                "解析 PDF 需要安装 pdfplumber: pip install pdfplumber"
            )

        pages = []
        full_text_parts = []

        with pdfplumber.open(file_path) as pdf:
            for i, page in enumerate(pdf.pages, 1):
                text = page.extract_text()
                if text:
                    text = text.strip()
                    pages.append(DocumentPage(
                        page_number=i,  # PDF 有真实页码
                        title=None,     # PDF 标题需要额外解析，暂不支持
                        text=text,
                    ))
                    full_text_parts.append(text)

        # 检测扫描型 PDF
        total_text = "\n\n".join(full_text_parts)
        if len(total_text.strip()) < 50 and len(pages) > 0:
            raise ValueError(
                "UNSUPPORTED_SCANNED_PDF: "
                "该 PDF 似乎是扫描型 PDF，当前版本不支持 OCR 解析。"
            )

        if not pages:
            raise ValueError("PDF 文件无法提取任何文本内容")

        return StructuredDocument(
            file_name=file_name,
            file_type="pdf",
            pages=pages,
            full_text=total_text,
        )
