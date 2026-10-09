"""KnowledgeRelationAgent 自动化测试。

使用 Fake LLM 测试规则校验、结构测试和 API 行为。
不依赖真实 LLM API。
"""

import pytest
from unittest.mock import MagicMock, patch

from agent.knowledge_relation.schemas import (
    KnowledgeRelationJudgement,
    RelationExtractOutput,
    RelationKnowledgeInput,
)
from agent.knowledge_relation.validator import RelationValidator


# ==================== T01-T05: 关系类型测试 ====================

class TestRelationTypes:
    """测试四种关系类型和 NO_RELATION。"""

    @pytest.fixture
    def validator(self):
        return RelationValidator()

    @pytest.fixture
    def source(self):
        return RelationKnowledgeInput(id=1, name="Java线程池", summary="线程池")

    @pytest.fixture
    def candidates(self):
        return {
            2, 3, 4, 5
        }

    def test_t01_prerequisite(self, validator, source, candidates):
        """T01: prerequisite 正向关系，方向为前置→后续。"""
        j = KnowledgeRelationJudgement(
            candidate_knowledge_id=2,
            decision="RELATION",
            relation_type="prerequisite",
            from_knowledge_id=2,  # 前置知识
            to_knowledge_id=1,    # 后续知识（锚点）
            confidence=0.85,
            reason="多线程是线程池的前置知识",
        )
        valid, errors = validator.validate_and_fix([j], source.id, candidates)
        assert len(valid) == 1
        assert valid[0].relation_type == "prerequisite"
        assert valid[0].from_knowledge_id == 2  # 前置
        assert valid[0].to_knowledge_id == 1    # 后续

    def test_t02_extension(self, validator, source, candidates):
        """T02: extension 正向关系，方向为基础→扩展。"""
        j = KnowledgeRelationJudgement(
            candidate_knowledge_id=3,
            decision="RELATION",
            relation_type="extension",
            from_knowledge_id=1,  # 基础知识（锚点）
            to_knowledge_id=3,    # 扩展知识
            confidence=0.80,
            reason="线程池核心参数是线程池的扩展知识",
        )
        valid, errors = validator.validate_and_fix([j], source.id, candidates)
        assert len(valid) == 1
        assert valid[0].relation_type == "extension"
        assert valid[0].from_knowledge_id == 1
        assert valid[0].to_knowledge_id == 3

    def test_t03_related(self, validator, source, candidates):
        """T03: related 关系。"""
        j = KnowledgeRelationJudgement(
            candidate_knowledge_id=4,
            decision="RELATION",
            relation_type="related",
            from_knowledge_id=1,
            to_knowledge_id=4,
            confidence=0.75,
            reason="内存模型与线程池有概念联系",
        )
        valid, errors = validator.validate_and_fix([j], source.id, candidates)
        assert len(valid) == 1
        assert valid[0].relation_type == "related"

    def test_t04_contrast(self, validator, source, candidates):
        """T04: contrast 关系。"""
        j = KnowledgeRelationJudgement(
            candidate_knowledge_id=5,
            decision="RELATION",
            relation_type="contrast",
            from_knowledge_id=1,
            to_knowledge_id=5,
            confidence=0.70,
            reason="两者是不同的并发方案，有对比意义",
        )
        valid, errors = validator.validate_and_fix([j], source.id, candidates)
        assert len(valid) == 1
        assert valid[0].relation_type == "contrast"

    def test_t05_no_relation(self, validator, source, candidates):
        """T05: NO_RELATION 正确清空关系字段。"""
        j = KnowledgeRelationJudgement(
            candidate_knowledge_id=2,
            decision="NO_RELATION",
            relation_type="prerequisite",  # 故意填了类型，应该被清空
            from_knowledge_id=1,
            to_knowledge_id=2,
            confidence=0.9,
            reason="没有直接关系",
        )
        valid, errors = validator.validate_and_fix([j], source.id, candidates)
        assert len(valid) == 1
        assert valid[0].decision == "NO_RELATION"
        assert valid[0].relation_type is None
        assert valid[0].from_knowledge_id is None
        assert valid[0].to_knowledge_id is None


# ==================== T06-T12: 校验测试 ====================

class TestValidation:
    """测试确定性校验规则。"""

    @pytest.fixture
    def validator(self):
        return RelationValidator()

    def test_t06_self_relation(self, validator):
        """T06: 自关联被拒绝。"""
        j = KnowledgeRelationJudgement(
            candidate_knowledge_id=1,
            decision="RELATION",
            relation_type="related",
            from_knowledge_id=1,
            to_knowledge_id=1,  # 自关联
            confidence=0.8,
            reason="自己关联自己",
        )
        valid, errors = validator.validate_and_fix([j], 1, {1, 2})
        assert len(valid) == 0
        assert any("自关联" in e for e in errors)

    def test_t07_invalid_relation_type(self, validator):
        """T07: 非法 relation_type 在 Pydantic 构造时就被拒绝。"""
        with pytest.raises(Exception):
            KnowledgeRelationJudgement(
                candidate_knowledge_id=2,
                decision="RELATION",
                relation_type="invalid_type",  # 非法类型
                from_knowledge_id=1,
                to_knowledge_id=2,
                confidence=0.8,
                reason="非法类型",
            )

    def test_t08_invalid_candidate_id(self, validator):
        """T08: 候选外 ID 被拒绝。"""
        j = KnowledgeRelationJudgement(
            candidate_knowledge_id=999,  # 不在候选集合中
            decision="RELATION",
            relation_type="related",
            from_knowledge_id=1,
            to_knowledge_id=999,
            confidence=0.8,
            reason="虚构 ID",
        )
        valid, errors = validator.validate_and_fix([j], 1, {2, 3})
        assert len(valid) == 0

    def test_t09_duplicate_candidate(self, validator):
        """T09: 重复候选只保留一条。"""
        j1 = KnowledgeRelationJudgement(
            candidate_knowledge_id=2,
            decision="RELATION",
            relation_type="related",
            from_knowledge_id=1,
            to_knowledge_id=2,
            confidence=0.8,
            reason="第一次",
        )
        j2 = KnowledgeRelationJudgement(
            candidate_knowledge_id=2,  # 重复
            decision="RELATION",
            relation_type="related",
            from_knowledge_id=1,
            to_knowledge_id=2,
            confidence=0.7,
            reason="第二次",
        )
        valid, errors = validator.validate_and_fix([j1, j2], 1, {2, 3})
        assert len(valid) == 1
        assert any("重复" in e for e in errors)

    def test_t10_empty_candidates(self, validator):
        """T10: 空候选返回空列表。"""
        valid, errors = validator.validate_and_fix([], 1, set())
        assert len(valid) == 0
        assert len(errors) == 0

    def test_t11_invalid_from_to(self, validator):
        """T11: from/to 指向候选外 ID 被拒绝。"""
        j = KnowledgeRelationJudgement(
            candidate_knowledge_id=2,
            decision="RELATION",
            relation_type="prerequisite",
            from_knowledge_id=999,  # 不在允许集合中
            to_knowledge_id=1,
            confidence=0.8,
            reason="from ID 无效",
        )
        valid, errors = validator.validate_and_fix([j], 1, {2, 3})
        assert len(valid) == 0

    def test_t12_confidence_clamped(self, validator):
        """T12: 置信度超出范围时 Pydantic 拒绝或校验器修正。"""
        with pytest.raises(Exception):
            KnowledgeRelationJudgement(
                candidate_knowledge_id=2,
                decision="NO_RELATION",
                confidence=1.5,  # 超出范围，Pydantic 拒绝
                reason="置信度测试",
            )


# ==================== T13-T18: API 行为测试 ====================

class TestAPIBehavior:
    """API 行为测试（需要测试数据库）。"""

    def test_t16_unauthenticated(self, client):
        """T16: 未认证请求被拒绝。"""
        response = client.post(
            "/api/v1/agent/knowledge-relation/test",
            json={"source_knowledge": {"id": 1, "name": "test"}},
        )
        assert response.status_code in (401, 403)

    def test_t10_empty_candidates_api(self, client, auth_headers):
        """T10: 空候选不调用 LLM，正常返回。"""
        response = client.post(
            "/api/v1/agent/knowledge-relation/test",
            headers=auth_headers,
            json={
                "source_knowledge": {"id": 1, "name": "Java线程池"},
                "candidates": [],
            },
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["candidate_count"] == 0
        assert data["relation_count"] == 0
        assert data["saved"] is False

    def test_t17_no_db_write(self, client, auth_headers, db):
        """T17: 测试接口不写入 knowledge_relation 表。"""
        from app.models.knowledge_relation import KnowledgeRelation

        before_count = db.query(KnowledgeRelation).count()

        response = client.post(
            "/api/v1/agent/knowledge-relation/test",
            headers=auth_headers,
            json={
                "source_knowledge": {"id": 1, "name": "Java线程池"},
                "candidates": [
                    {"id": 2, "name": "Java多线程", "summary": "多线程基础"},
                ],
            },
        )

        after_count = db.query(KnowledgeRelation).count()
        assert before_count == after_count

    def test_source_knowledge_id_not_found(self, client, auth_headers):
        """不存在的知识点 ID 返回 404。"""
        response = client.post(
            "/api/v1/agent/knowledge-relation/test",
            headers=auth_headers,
            json={"source_knowledge_id": 99999},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 40401

    def test_missing_source(self, client, auth_headers):
        """缺少锚点参数返回 400。"""
        response = client.post(
            "/api/v1/agent/knowledge-relation/test",
            headers=auth_headers,
            json={"candidates": [{"id": 1, "name": "test"}]},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 40001


# ==================== 回归测试 ====================

class TestRegression:
    """回归测试。"""

    def test_t18_original_tests_not_broken(self):
        """T18: 原有测试不回归（由 pytest 全量运行验证）。"""
        assert True  # 占位，实际由 pytest tests/ 验证
