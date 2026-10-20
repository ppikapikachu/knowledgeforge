"""标准化/指纹 v2 专项测试（加固执行文档 §4.5 的 12 项必测）。

核心原则（§4.2）：优先避免误杀——宁可让近似文本进入关键词/向量层，
也不允许为了提高 Hash 命中率而破坏代码、字符串、技术标识符语义。
"""

import pytest

from app.services.question_normalizer import HASH_VERSION, question_normalizer


def h(question_type="SHORT_ANSWER", content="", answer="", options=()):
    return question_normalizer.compute_content_hash(
        question_type, content, answer, list(options)
    )


class TestNormalizerV2:
    def test_hash_version_is_v2(self):
        assert HASH_VERSION == "2"

    # 1. 普通中文题目：仅空格/换行不同 → 同指纹
    def test_plain_chinese_whitespace_only(self):
        a = h(content="什么是\n  面向对象  编程？")
        b = h(content="什么是面向对象编程？")
        assert a == b

    # 2. 代码块缩进不同 → 行为相同（行首缩进折叠）
    def test_code_block_indent_equivalent(self):
        a = h(content="```python\nif x:\n    return 1\n```")
        b = h(content="```python\nif x:\n        return 1\n```")
        assert a == b

    # 3. 引号/字符串字面量中的空白必须保留："a b" ≠ "ab"
    def test_string_literal_whitespace_preserved(self):
        a = h(content='System.out.println("a b");')
        b = h(content='System.out.println("ab");')
        assert a != b

    # 4. 技术标识符大小写敏感：HashMap ≠ hashmap
    def test_case_sensitive_identifier(self):
        a = h(content="HashMap 的底层结构是什么？")
        b = h(content="hashmap 的底层结构是什么？")
        assert a != b

    # 5. C 与 C++ 是不同技术：不得归一为相同
    def test_c_vs_cpp_distinct(self):
        a = h(content="C 语言中的指针是什么？")
        b = h(content="C++ 语言中的指针是什么？")
        assert a != b

    # 6. 运算符 == 与 === 语义不同
    def test_operators_distinct(self):
        a = h(content="解释 Java == 的含义")
        b = h(content="解释 Java === 的含义")
        assert a != b

    # 7. JDK 8 与 JDK 18 是不同版本（英文词边界保留，不得删除空格）
    def test_jdk8_vs_jdk18_distinct(self):
        a = h(content="JDK 8 中的 Lambda 表达式怎么用？")
        b = h(content="JDK 18 中的 Lambda 表达式怎么用？")
        assert a != b
        # "JDK 8" 与 "JDK8" 属于英文词边界差异：保留词边界（与字符串
        # 保真同源），指纹不同，由关键词/向量层复核（§4.2 宁可进向量层）
        c = h(content="JDK 8 中的 Lambda 表达式怎么用？")
        d = h(content="JDK8 中的 Lambda 表达式怎么用？")
        assert c != d

    # 8. 选项标签变化（A./无标签）不影响指纹
    def test_option_label_stripped(self):
        a = h("SINGLE_CHOICE", "题干内容", "A", [("A. 数组", 1), ("B. 链表", 0)])
        b = h("SINGLE_CHOICE", "题干内容", "A", [("数组", 1), ("链表", 0)])
        assert a == b

    # 9. 选项顺序变化但答案映射不变 → 同指纹
    def test_option_reorder_same_answer_mapping(self):
        a = h("SINGLE_CHOICE", "题干内容", "A",
              [("数组", 1), ("链表", 0), ("栈", 0)])
        b = h("SINGLE_CHOICE", "题干内容", "B",
              [("链表", 0), ("栈", 0), ("数组", 1)])
        assert a == b

    # 10. 选项顺序变化且答案映射变化 → 不同指纹
    def test_option_reorder_answer_mapping_changed(self):
        a = h("SINGLE_CHOICE", "题干内容", "A",
              [("数组", 1), ("链表", 0)])
        b = h("SINGLE_CHOICE", "题干内容", "A",
              [("数组", 0), ("链表", 1)])
        assert a != b

    # 11. 单选与简答是不同题型：同题干不同指纹
    def test_question_type_participates(self):
        a = h("SINGLE_CHOICE", "题干内容", "A", [("数组", 1)])
        b = h("SHORT_ANSWER", "题干内容", "数组")
        assert a != b

    # 12. 代码块围栏 vs 普通文本相似代码：围栏剥除后按同一规则归一；
    #     但字符串/行内代码中的空白差异仍然保留（不得抹除）
    def test_fence_vs_plain_code(self):
        fenced = h(content="```java\nint a = 1;\n```")
        plain = h(content="int a = 1;")
        assert fenced == plain
        fenced_str = h(content='```java\nString s = "a b";\n```')
        plain_str = h(content='String s = "ab";')
        assert fenced_str != plain_str

    # 补充：行内代码字面量同样保真
    def test_inline_code_literal_preserved(self):
        a = h(content="请解释 `==` 与 `===` 的区别")
        b = h(content="请解释 == 与 === 的区别")
        # 行内反引号内容作为 literal 保真 → 与无反引号版本不同指纹
        # （宁可进向量层复核，也不冒误杀风险）
        assert a != b

    # 补充：中文标点全半角等价
    def test_fullwidth_punctuation_equivalent(self):
        a = h(content="什么是多态？")
        b = h(content="什么是多态?")
        assert a == b


class TestSignatureRobustness:
    def test_options_required_for_choice_signature(self):
        """选择题无选项时仍可计算（防御），但与有选项的题不同指纹。"""
        a = h("SINGLE_CHOICE", "题干内容", "A", [])
        b = h("SINGLE_CHOICE", "题干内容", "A", [("数组", 1)])
        assert a != b

    def test_true_false_answer_normalized(self):
        a = h("TRUE_FALSE", "Java 是静态类型语言", "TRUE")
        b = h("TRUE_FALSE", "Java 是静态类型语言", "true")
        assert a == b

    def test_similarity_not_hash_identity(self):
        """近似文本不应同指纹，但相似度应显著高于无关文本（进向量层）。"""
        s1 = question_normalizer.text_similarity(
            "HashMap 底层数据结构是什么", "HashMap 的底层是什么数据结构")
        s2 = question_normalizer.text_similarity(
            "HashMap 底层数据结构是什么", "线程池的核心参数有哪些")
        assert s1 > s2
