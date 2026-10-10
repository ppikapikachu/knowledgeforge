"""临时脚本：输出完整分块结果"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.knowledge_extract.parser import DocumentParser
from agent.knowledge_extract.chunker import TextChunker
from agent.knowledge_extract.boundary import BoundaryDetector

parser = DocumentParser()
doc = parser.parse(r"D:\pythonproject\knowledgeforge\docs\导入测试.txt")

detector = BoundaryDetector()
units = detector.detect_units(doc.full_text)
units = detector.filter_noise(units)

chunker = TextChunker()
chunks = chunker.chunk(doc)

out = []
out.append("=" * 70)
out.append("  导入测试.txt 分块结果")
out.append("=" * 70)
out.append(f"  文件总长: {len(doc.full_text)} 字符")
out.append(f"  chunk_size: {chunker.chunk_size}")
out.append(f"  chunk_overlap: {chunker.chunk_overlap}")
out.append(f"  识别单元数: {len(units)}")
out.append(f"  分块数: {len(chunks)}")
out.append("")
out.append("  单元列表:")
for u in units:
    out.append(f"    [{u.unit_id}] {u.unit_kind} (conf={u.boundary_confidence}) "
               f"[{u.source_start}-{u.source_end}] {len(u.text)}字符 "
               f"title={u.section_context or 'None'} marker={u.marker or 'None'}")
out.append("=" * 70)

for i, chunk in enumerate(chunks):
    out.append("")
    out.append("=" * 70)
    out.append(f"  Chunk {i+1}/{len(chunks)}")
    out.append(f"  chunk_id: {chunk.chunk_id}")
    out.append(f"  title: {chunk.title}")
    out.append(f"  char_start: {chunk.char_start}, char_end: {chunk.char_end}")
    out.append(f"  text_length: {len(chunk.text)} 字符")
    out.append("=" * 70)
    out.append("")
    out.append(chunk.text)
    out.append("")

with open(r"D:\pythonproject\knowledgeforge\backend\chunk_result.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(out))

print(f"单元数: {len(units)}, 分块数: {len(chunks)}")
for i, c in enumerate(chunks):
    print(f"  Chunk {i+1}: {len(c.text)} 字符")
