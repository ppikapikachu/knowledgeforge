"""生成任务接入去重的集成测试（执行文档 §7.2/§7.3/§12.2-10）。

验证 background_runner.execute_generation_task 的：
- 批次内去重统计（generated/exact/semantic/uncertain/unfulfilled 口径）；
- 重试上限与生成上限（不无限生成）；
- uncertain 保留入库并计数；
- 手动/自动分配目标都走同一去重链路；
- 不同内容正常入库（不回归旧出题链路）。
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from agent.question_generate.schemas import GeneratedOption, GeneratedQuestion
from app.models import Question, QuestionGenerationTask, QuestionKnowledge
from app.services.background_runner import execute_generation_task
from app.services.question_dedup_service import QuestionDeduplicationService
from app.services.question_normalizer import HASH_VERSION

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from test_question_dedup import (  # noqa: E402 —— 复用测试替身与工具
    FakeEmbedding,
    FakeVectorStore,
    StubLLMReviewer,
    ensure_knowledge,
    get_bank_id,
    make_question,
    make_snap,
)


def make_task(db, *, total_count=2, allocation_mode="manual", allocation_plan=None):
    from app.models import AdminUser

    admin = db.query(AdminUser).order_by(AdminUser.id).first()
    if admin is None:
        admin = AdminUser(username="testadmin", password_hash="x", nickname="测试管理员", status=1)
        db.add(admin)
        db.flush()
    task = QuestionGenerationTask(
        total_count=total_count, success_count=0, duplicate_count=0, failed_count=0,
        status="pending", allocation_mode=allocation_mode,
        allocation_plan=allocation_plan, requested_count=total_count,
        created_by=admin.id,
    )
    db.add(task)
    db.flush()
    db.commit()
    return task


def gen_question(content, *, knowledge_id=1, question_type="SINGLE_CHOICE", answer="A"):
    return GeneratedQuestion(
        question_type=question_type, content=content, answer=answer, analysis="解析",
        difficulty=2,
        options=[GeneratedOption(option_key="A", option_content="选项一", is_correct=True),
                 GeneratedOption(option_key="B", option_content="选项二", is_correct=False)],
        knowledge_id=knowledge_id,
    )


class ScriptedAgent:
    """按轮次返回脚本化生成结果的假 Agent。"""

    def __init__(self, batches):
        self.batches = list(batches)
        self.calls = 0

    def generate_for_plan_item(self, knowledge_id=None, question_bank_id=None,
                               question_type=None, difficulty=None, count=1, **kwargs):
        self.calls += 1
        batch = self.batches.pop(0) if self.batches else []
        questions = batch[:count]
        return {
            "questions": questions,
            "success_count": len(questions),
            "failed_count": max(0, count - len(questions)),
            "errors": [],
            "duration": 0.01,
        }


@pytest.fixture
def runner_env(db, monkeypatch):
    """把生成任务链路的外部依赖换成测试替身。"""
    ensure_knowledge(db, [1, 2, 3])
    embed, store, reviewer = FakeEmbedding(), FakeVectorStore(), StubLLMReviewer()
    agent_holder = {}

    def install_agent(agent):
        agent_holder["agent"] = agent

    monkeypatch.setattr(
        "agent.question_generate.agent.QuestionGenerateAgent.generate_for_plan_item",
        lambda self, **kwargs: agent_holder["agent"].generate_for_plan_item(**kwargs),
    )
    monkeypatch.setattr(
        "app.services.question_dedup_service.get_embedding_service", lambda: embed)
    monkeypatch.setattr(
        "app.services.question_dedup_service.get_question_vector_store", lambda: store)
    monkeypatch.setattr(
        "app.services.question_dedup_service.LLMQuestionReviewer", lambda *a, **k: reviewer)

    env = {
        "embed": embed, "store": store, "reviewer": reviewer,
        "install_agent": install_agent,
        "session_factory": sessionmaker(bind=db.get_bind()),
    }
    return env


def run_task(task, request_config, runner_env):
    execute_generation_task(task.id, request_config,
                            session_factory=runner_env["session_factory"])


def refresh(db):
    """测试会话读取后台线程的提交前，必须结束旧快照事务。

    MySQL REPEATABLE READ 下，测试会话在后台任务提交前开启的事务会一直持有旧快照，
    expire_all() 只过期对象、不换快照；rollback() 结束事务后的新查询才能看到新提交。
    """
    db.rollback()
    db.expire_all()


class TestRunnerDedupIntegration:
    def test_batch_and_db_dedup_statistics(self, db, runner_env):
        """同批两道完全相同 → 批次内去重 1；补生成仍是同题 → 精确去重 1。"""
        runner_env["install_agent"](ScriptedAgent([
            [gen_question("固定生成的题目内容A"), gen_question("固定生成的题目内容A")],
            [gen_question("固定生成的题目内容A")],
        ]))
        task = make_task(db, total_count=2)
        run_task(task, {
            "question_bank_id": get_bank_id(db), "question_type": "SINGLE_CHOICE",
            "difficulty": 2, "allocation_mode": "manual", "knowledge_id": 1, "count": 2,
        }, runner_env)

        refresh(db)
        task = db.query(QuestionGenerationTask).get(task.id)
        assert task.generated_count == 3
        assert task.semantic_duplicate_count == 1   # 批次内重复
        assert task.exact_duplicate_count == 1      # 库内精确指纹重复
        assert task.duplicate_count == 2
        assert task.success_count == 1
        assert task.unfulfilled_count == 1
        assert task.status == "partial_success"

        rows = db.query(Question).filter(Question.content == "固定生成的题目内容A").all()
        assert len(rows) == 1
        assert rows[0].hash_version == HASH_VERSION and rows[0].dedup_key == rows[0].content_hash

    def test_regeneration_caps_no_infinite_loop(self, db, runner_env):
        """全部候选都是重复题 → 受重试上限/生成上限约束，不无限生成。"""
        make_question(db, "库里已存在的题目内容")
        runner_env["install_agent"](ScriptedAgent([
            [gen_question("库里已存在的题目内容"), gen_question("库里已存在的题目内容")],
            [gen_question("库里已存在的题目内容")],
        ]))
        task = make_task(db, total_count=2)
        run_task(task, {
            "question_bank_id": get_bank_id(db), "question_type": "SINGLE_CHOICE",
            "difficulty": 2, "allocation_mode": "manual", "knowledge_id": 1, "count": 2,
        }, runner_env)

        refresh(db)
        task = db.query(QuestionGenerationTask).get(task.id)
        assert task.success_count == 0
        assert task.exact_duplicate_count == 3
        assert task.unfulfilled_count == 2
        assert task.status == "failed"
        # 生成上限 = 2*1.5=3 → 第一轮 2 道 + 第二轮 1 道，最多 2 次调用，绝不无限循环
        assert db.query(Question).filter(Question.content == "库里已存在的题目内容").count() == 1

    def test_uncertain_kept_and_counted(self, db, runner_env, monkeypatch):
        """LLM 复核 uncertain → 保留入库 + 计数 + 人工复核标记。"""
        from agent.common.config import agent_settings

        monkeypatch.setattr(agent_settings, "QUESTION_DEDUP_SAME_SCOPE_CANDIDATE_THRESHOLD", 0.15)
        runner_env["reviewer"].verdict_fn = lambda p: "uncertain"
        make_question(db, "JDK 8 中 HashMap 的底层采用什么数据结构实现？", knowledge_ids=(1, 2))
        runner_env["install_agent"](ScriptedAgent([
            [gen_question("Java 中 HashMap 底层是什么结构？")],
        ]))
        task = make_task(db, total_count=1)
        run_task(task, {
            "question_bank_id": get_bank_id(db), "question_type": "SINGLE_CHOICE",
            "difficulty": 2, "allocation_mode": "manual", "knowledge_id": 2, "count": 1,
        }, runner_env)

        refresh(db)
        task = db.query(QuestionGenerationTask).get(task.id)
        assert task.success_count == 1
        assert task.uncertain_count == 1
        assert task.status == "success"
        assert runner_env["reviewer"].calls >= 1

    def test_normal_questions_not_regressed(self, db, runner_env):
        """互不相同的正常题目全部入库（旧出题链路不回归）。"""
        runner_env["install_agent"](ScriptedAgent([
            [gen_question("互不相同的题目内容甲"), gen_question("互不相同的题目内容乙")],
        ]))
        task = make_task(db, total_count=2)
        run_task(task, {
            "question_bank_id": get_bank_id(db), "question_type": "SINGLE_CHOICE",
            "difficulty": 2, "allocation_mode": "manual", "knowledge_id": 1, "count": 2,
        }, runner_env)

        refresh(db)
        task = db.query(QuestionGenerationTask).get(task.id)
        assert task.status == "success"
        assert task.success_count == 2
        assert task.duplicate_count == 0
        assert task.unfulfilled_count == 0
        # 每道题都关联了知识点并登记了指纹
        rows = db.query(Question).filter(Question.generation_task_id == task.id).all()
        assert len(rows) == 2
        for row in rows:
            assert row.content_hash and row.hash_version == HASH_VERSION
            assert db.query(QuestionKnowledge).filter(
                QuestionKnowledge.question_id == row.id).count() == 1
        # 向量索引已写入（MySQL 先、向量后）
        assert runner_env["store"].count() == 2

    def test_auto_allocation_targets_each_get_dedup(self, db, runner_env):
        """自动分配（allocation_plan）多知识点目标走同一去重链路。"""
        runner_env["install_agent"](ScriptedAgent([
            [gen_question("知识点一的题目内容")],
            [gen_question("知识点二的题目内容")],
        ]))
        task = make_task(
            db, total_count=2, allocation_mode="auto",
            allocation_plan={"items": [
                {"knowledge_id": 1, "planned_count": 1},
                {"knowledge_id": 2, "planned_count": 1},
            ]},
        )
        run_task(task, {
            "question_bank_id": get_bank_id(db), "question_type": "SINGLE_CHOICE",
            "difficulty": 2, "allocation_mode": "auto",
        }, runner_env)

        refresh(db)
        task = db.query(QuestionGenerationTask).get(task.id)
        assert task.status == "success"
        assert task.success_count == 2
        kids = {
            ka.knowledge_id
            for ka in db.query(QuestionKnowledge).filter(
                QuestionKnowledge.question_id.in_(
                    [q.id for q in db.query(Question).filter(
                        Question.generation_task_id == task.id).all()])).all()
        }
        assert kids == {1, 2}
