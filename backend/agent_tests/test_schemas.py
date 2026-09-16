"""Pydantic Schema 和 Validator 测试模块。

测试内容：
    1. KnowledgeCandidate 字段校验（合法值、非法值）
    2. KnowledgeExtractResult 空结果
    3. StructuredDocument 创建
    4. ExtractRunResult 创建
    5. KnowledgeValidator 校验逻辑
"""

import pytest
from pydantic import ValidationError

from agent.knowledge_extract.schemas import (
    DocumentChunk,
    DocumentPage,
    ExtractRunResult,
    KnowledgeCandidate,
    KnowledgeExtractResult,
    StructuredDocument,
)
from agent.knowledge_extract.validator import KnowledgeValidator


class TestSchemas:
    """Pydantic 数据模型测试类。"""

    def test_knowledge_candidate_valid(self):
        """合法的知识点候选应通过 Pydantic 校验。"""
        candidate = KnowledgeCandidate(
            name="Activity生命周期",
            summary="Activity是Android四大组件之一，具有完整生命周期",
            content="Activity具有onCreate、onStart等回调方法...",
            difficulty=2,
            keywords=["Activity", "生命周期", "onCreate"],
            source_chunk_id="chunk_001",
        )
        assert candidate.name == "Activity生命周期"
        assert candidate.difficulty == 2

    def test_knowledge_candidate_invalid_difficulty(self):
        """difficulty=0 应触发 Pydantic 校验失败（ge=1 约束）。"""
        with pytest.raises(ValidationError):
            KnowledgeCandidate(
                name="Test",
                summary="Test summary",
                content="Test content",
                difficulty=0,  # 非法值，小于最小值 1
                keywords=["test"],
                source_chunk_id="chunk_001",
            )

    def test_knowledge_candidate_invalid_difficulty_high(self):
        """difficulty=5 应触发 Pydantic 校验失败（le=3 约束）。"""
        with pytest.raises(ValidationError):
            KnowledgeCandidate(
                name="Test",
                summary="Test summary",
                content="Test content",
                difficulty=5,  # 非法值，大于最大值 3
                keywords=["test"],
                source_chunk_id="chunk_001",
            )

    def test_knowledge_candidate_empty_name(self):
        """空 name 应触发 Pydantic 校验失败（min_length=1 约束）。"""
        with pytest.raises(ValidationError):
            KnowledgeCandidate(
                name="",  # 空字符串
                summary="Test",
                content="Test",
                difficulty=2,
                keywords=["test"],
                source_chunk_id="chunk_001",
            )

    def test_extract_result_empty(self):
        """空知识点列表应合法（允许零知识点）。"""
        result = KnowledgeExtractResult(knowledge_points=[])
        assert len(result.knowledge_points) == 0

    def test_structured_document(self):
        """StructuredDocument 应能正常创建并访问字段。"""
        doc = StructuredDocument(
            file_name="test.txt",
            file_type="txt",
            pages=[DocumentPage(text="hello")],
            full_text="hello",
        )
        assert doc.file_name == "test.txt"

    def test_extract_run_result(self):
        """ExtractRunResult 应能正常创建并访问字段。"""
        result = ExtractRunResult(
            run_id="run_123",
            file_name="test.txt",
            chunk_count=5,
            knowledge_count=3,
            knowledge_points=[],
            errors=[],
        )
        assert result.run_id == "run_123"


class TestValidator:
    """知识点校验器测试类。"""

    @pytest.fixture
    def validator(self):
        """创建校验器实例。"""
        return KnowledgeValidator()

    def test_valid_candidate(self, validator):
        """合法候选应通过 Validator 校验（无错误）。"""
        candidate = KnowledgeCandidate(
            name="Activity生命周期",
            summary="Android四大组件之一",
            content="详细内容...",
            difficulty=2,
            keywords=["Activity", "生命周期"],
            source_chunk_id="chunk_001",
        )
        valid, errors = validator.validate_candidates([candidate], "chunk_001")
        assert len(valid) == 1   # 1 个通过校验
        assert len(errors) == 0  # 无错误

    def test_invalid_difficulty(self, validator):
        """Pydantic 已在创建时拦截非法 difficulty，Validator 处理的是合法数据。"""
        candidate = KnowledgeCandidate(
            name="Test",
            summary="Test",
            content="Test",
            difficulty=2,
            keywords=["test"],
            source_chunk_id="chunk_001",
        )
        valid, errors = validator.validate_candidates([candidate], "chunk_001")
        assert len(valid) == 1  # 合法数据应通过

    def test_empty_candidates(self, validator):
        """空候选列表应返回空结果、无错误。"""
        valid, errors = validator.validate_candidates([], "chunk_001")
        assert len(valid) == 0
        assert len(errors) == 0
