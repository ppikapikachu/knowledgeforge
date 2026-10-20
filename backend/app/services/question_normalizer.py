"""题目标准化与指纹（content_hash）模块（hash_version 2）。

v2 相对 v1 的变化（专项加固执行文档 §4，核心目标：避免误杀真正不同的题目）：

- 不再无差别删除全部空白：普通文本折叠连续空白为单空格，只删除紧邻中日韩
  文字的空格（保留英文词边界）；"JDK 8" 与 "JDK8" 不再强行同指纹；
- 字符串字面量与行内代码完全保真（"..."、'...'、"..."、'...'、`...`）：
  "a b" 与 "ab" 不再产生相同指纹（v1 的误判风险，§4.1 实例）；
- Markdown 代码围栏 ``` ``` 的围栏标记与语言标注剥离，围栏内按代码空白规则
  （行首缩进删除、行内连续空白折叠）处理；围栏内字符串字面量仍保真；
- 大小写敏感技术标识（HashMap/hashmap）、运算符（==/===）、C/C++、JDK 8 vs
  JDK 18 等差异继续保留，不做小写化、不做全局去标点；
- 选择题选项顺序无关签名（(归一化选项内容, 是否正确) 排序拼接），正确答案映射
  由 is_correct 位承载，剥离 A./B) 展示标签不影响指纹。

指纹版本（hash_version）：
- "0" = 历史 content-only 指纹（已废弃）；
- "1" = v1（去全部空白，存在代码语义误判风险）；
- "2" = 本模块当前指纹。不同版本的指纹不得相互比较（精确层按 hash_version 过滤）。

指纹 = sha256(signature)[:32]，signature =
    f"{question_type}|{norm(content)}|{option_sig}|{answer_part}"
其中 answer_part 仅对 TRUE_FALSE / SHORT_ANSWER 参与（选择题的答案已包含在
option_sig 的 is_correct 位中）。
"""

import hashlib
import re
import unicodedata
from collections import Counter
from typing import List, Optional, Sequence, Tuple

# 当前指纹算法版本
HASH_VERSION = "2"

# 全角/中文标点 → 半角（NFKC 不处理中文句读符号，此处显式映射）
_PUNCT_MAP = {
    "，": ",", "。": ".", "！": "!", "？": "?", "；": ";", "：": ":",
    "（": "(", "）": ")", "【": "[", "】": "]", "、": ",", "＂": '"',
    "～": "~", "％": "%",
    "＜": "<", "＞": ">", "＝": "=", "＋": "+", "－": "-", "／": "/",
    "｜": "|", "＊": "*", "＃": "#", "＠": "@", "＆": "&", "＾": "^",
    "｛": "{", "｝": "}", "＿": "_", "•": "·",
}

# 句末标点（归一化后删除，避免"数据结构。" vs "数据结构" 判不同）
_TRAILING_PUNCT_RE = re.compile(r"[\s。.!?？;；,，:：]+$")
# 选项前缀标签：A. B、 C) D： 等
_OPTION_LABEL_RE = re.compile(r"^\s*[A-Fa-f][.、．:：)）]\s*")
# 空白折叠
_WS_RE = re.compile(r"\s+")
# 中日韩文字（含扩展A/兼容区）：其紧邻空格视为无意义，删除
_CJK_CLASS = "\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff"
_CJK_SPACE_RE = re.compile(rf"(?<=[{_CJK_CLASS}]) | (?=[{_CJK_CLASS}])")

# Markdown 代码围栏：```[语言标注] ... ```（标记与语言标注剥离，内容保留）
_FENCE_RE = re.compile(r"```[^\n]*\n?(.*?)```", re.DOTALL)
# 保真段：字符串字面量（支持 \ 转义）与行内代码；内容完全不动
_LITERAL_RE = re.compile(
    r'"(?:[^"\\]|\\.)*"'
    r"|'(?:[^'\\]|\\.)*'"
    r"|“[^”]*”"
    r"|‘[^’]*’"
    r"|`[^`\n]*`"
)
# 关键词抽取：ASCII 单词（含 C++/== 这类符号词）或中文连续段
_KEYWORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9_+#.=]{1,}|[\u4e00-\u9fff]{2,}")

# 真假题答案归一
_TRUE_TOKENS = {"TRUE", "T", "对", "正确", "是", "YES"}
_FALSE_TOKENS = {"FALSE", "F", "错", "错误", "否", "NO"}

# 中文引号 → 半角（仅用于保真段的引号形式归一，段内容不动）
_QUOTE_MAP = {"“": '"', "”": '"', "‘": "'", "’": "'"}


def _translate_punct(text: str) -> str:
    return "".join(_PUNCT_MAP.get(ch, ch) for ch in text)


class QuestionNormalizer:
    """题目标准化、指纹、文本相似度与向量文本构建。"""

    # ---------- 标准化 ----------

    def normalize_text(self, text: str) -> str:
        """题干/答案归一（v2）。

        流程：换行归一 → 剥代码围栏标记 → 分段（保真段/普通段）→ 各段归一
        → 去首尾与句末标点。保留大小写。
        """
        if not text:
            return ""
        t = text.replace("\r\n", "\n").replace("\r", "\n")
        t = self._expand_fences(t)
        parts: List[str] = []
        for kind, seg in self._split_segments(t):
            if kind == "literal":
                parts.append(self._normalize_literal(seg))
            else:
                parts.append(self._normalize_plain(seg))
        t = "".join(parts)
        t = _TRAILING_PUNCT_RE.sub("", t.strip())
        return t.strip()

    def normalize_option_content(self, text: str) -> str:
        """选项内容归一：先剥离 A./B) 等标签前缀，再按 normalize_text 归一。"""
        if not text:
            return ""
        t = _OPTION_LABEL_RE.sub("", text)
        return self.normalize_text(t)

    def normalize_answer(self, question_type: str, answer: str) -> str:
        """答案归一：TRUE_FALSE 统一为 TRUE/FALSE，其余按 normalize_text。"""
        if question_type == "TRUE_FALSE":
            a = (answer or "").strip().upper()
            if a in _TRUE_TOKENS or (answer or "").strip() in _TRUE_TOKENS:
                return "TRUE"
            if a in _FALSE_TOKENS or (answer or "").strip() in _FALSE_TOKENS:
                return "FALSE"
            return a
        return self.normalize_text(answer)

    # ---------- v2 分段与段内归一 ----------

    @staticmethod
    def _expand_fences(text: str) -> str:
        """剥离 Markdown 代码围栏标记与语言标注，保留围栏内容。"""
        return _FENCE_RE.sub(lambda m: "\n" + m.group(1) + "\n", text)

    @staticmethod
    def _split_segments(text: str) -> List[Tuple[str, str]]:
        """把文本切成 (kind, segment) 序列；kind ∈ literal / plain。"""
        out: List[Tuple[str, str]] = []
        pos = 0
        for m in _LITERAL_RE.finditer(text):
            if m.start() > pos:
                out.append(("plain", text[pos:m.start()]))
            out.append(("literal", m.group(0)))
            pos = m.end()
        if pos < len(text):
            out.append(("plain", text[pos:]))
        return out

    @staticmethod
    def _normalize_plain(seg: str) -> str:
        """普通文本/代码非字面量部分：NFKC + 标点统一 + 空白折叠 + 中文边界空格删除。"""
        t = unicodedata.normalize("NFKC", seg)
        t = _translate_punct(t)
        t = _WS_RE.sub(" ", t)          # 连续空白（含换行/制表）→ 单空格（行首缩进由此消除）
        t = _CJK_SPACE_RE.sub("", t)    # 删除紧邻中文的空格（无意义分隔），保留英文词边界
        return t

    @staticmethod
    def _normalize_literal(seg: str) -> str:
        """字符串字面量/行内代码：内容完全保真，仅把中文引号形式归一为半角。"""
        return "".join(_QUOTE_MAP.get(ch, ch) for ch in seg)

    # ---------- 指纹 ----------

    def option_signature(self, options: Optional[Sequence[Tuple[str, int]]]) -> str:
        """选择题选项的顺序无关签名。

        options: [(option_content, is_correct)]；is_correct 1/0。
        签名 = 排序后的 (归一化内容::是否正确) 拼接，因此选项换序不改变指纹，
        而"选项内容相同但正确项不同"会改变指纹。
        """
        if not options:
            return ""
        pairs = []
        for content, is_correct in options:
            pairs.append(f"{self.normalize_option_content(content)}::{1 if is_correct else 0}")
        return ";".join(sorted(pairs))

    def build_signature(self, question_type: str, content: str, answer: str = "",
                        options: Optional[Sequence[Tuple[str, int]]] = None) -> str:
        opt_sig = self.option_signature(options) if question_type in ("SINGLE_CHOICE", "MULTIPLE_CHOICE") else ""
        # 选择题答案已由选项正确位覆盖；真假/简答题答案参与指纹
        answer_part = ""
        if question_type == "TRUE_FALSE":
            answer_part = self.normalize_answer(question_type, answer)
        elif question_type == "SHORT_ANSWER":
            answer_part = self.normalize_answer(question_type, answer)
        return f"{question_type}|{self.normalize_text(content)}|{opt_sig}|{answer_part}"

    def compute_content_hash(self, question_type: str, content: str, answer: str = "",
                             options: Optional[Sequence[Tuple[str, int]]] = None) -> str:
        signature = self.build_signature(question_type, content, answer, options)
        return hashlib.sha256(signature.encode("utf-8")).hexdigest()[:32]

    # ---------- 相似度 ----------

    def similarity_text(self, text: str) -> str:
        """模糊匹配用文本：归一化 + casefold（只用于召回打分，不进指纹）。"""
        return self.normalize_text(text).casefold()

    def text_similarity(self, a: str, b: str) -> float:
        """字符 bigram 余弦相似度（0~1）。短文本退化为 unigram。"""
        ta = self.similarity_text(a)
        tb = self.similarity_text(b)
        if not ta or not tb:
            return 0.0
        if ta == tb:
            return 1.0
        return self._cosine(self._ngrams(ta), self._ngrams(tb))

    @staticmethod
    def _ngrams(text: str) -> Counter:
        if len(text) < 2:
            return Counter([text])
        return Counter([text[i:i + 2] for i in range(len(text) - 1)])

    @staticmethod
    def _cosine(ca: Counter, cb: Counter) -> float:
        common = set(ca) & set(cb)
        if not common:
            return 0.0
        num = sum(ca[k] * cb[k] for k in common)
        da = sum(v * v for v in ca.values()) ** 0.5
        db = sum(v * v for v in cb.values()) ** 0.5
        if da == 0 or db == 0:
            return 0.0
        return num / (da * db)

    # ---------- 关键词 ----------

    def extract_keywords(self, text: str, limit: int = 5) -> List[str]:
        """抽取检索关键词（长词优先、去重），用于关键词通道召回。"""
        if not text:
            return []
        seen = set()
        tokens = []
        for tok in _KEYWORD_RE.findall(text):
            key = tok.casefold()
            if key in seen:
                continue
            seen.add(key)
            tokens.append(tok)
        tokens.sort(key=lambda t: -len(t))
        return tokens[:limit]

    # ---------- 向量文本 ----------

    def build_vector_text(self, question_type: str, content: str,
                          options: Optional[Sequence[Tuple[str, str]]] = None) -> str:
        """向量化文本 = 题型 + 题干 + 选项内容（不含知识点名称、解析）。

        options: [(option_key, option_content)]，按 option_key 原序。
        """
        parts = [question_type, (content or "").strip()]
        if options:
            opts = " ".join(f"{key}.{str(val).strip()}" for key, val in options)
            parts.append(opts)
        return " | ".join(p for p in parts if p)


question_normalizer = QuestionNormalizer()
