"""题目去重性能测量（一次性探针，非交付脚本）。"""
import ctypes
import ctypes.wintypes
import json
import logging
import os
import sys
import time

sys.path.insert(0, r"D:\pythonproject\knowledgeforge\backend")
os.chdir(r"D:\pythonproject\knowledgeforge\backend")
logging.disable(logging.INFO)


class PMC(ctypes.Structure):
    _fields_ = [
        ("cb", ctypes.wintypes.DWORD), ("PageFaultCount", ctypes.wintypes.DWORD),
        ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
        ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t),
    ]


def rss_mb() -> float:
    pmc = PMC()
    pmc.cb = ctypes.sizeof(PMC)
    ctypes.windll.psapi.GetProcessMemoryInfo(
        ctypes.windll.kernel32.GetCurrentProcess(), ctypes.byref(pmc), pmc.cb)
    return round(pmc.WorkingSetSize / 1048576.0, 1)


out = {}
t_load = time.time()
from agent.common.embedding import get_embedding_service  # noqa: E402

get_embedding_service()
out["model_load_s"] = round(time.time() - t_load, 2)
out["rss_after_model_mb"] = rss_mb()

from app.core.database import SessionLocal  # noqa: E402
from app.models import Question  # noqa: E402
from app.models.question_knowledge import QuestionKnowledge  # noqa: E402
from app.services.question_dedup_service import (  # noqa: E402
    QuestionDeduplicationService, QuestionSnapshot, initialize_question_index,
)

db = SessionLocal()
out["history_blocking_total"] = (
    db.query(Question).filter(Question.status.in_(("pending_review", "published"))).count()
)

t = time.time()
out["index_stats"] = initialize_question_index(db, only_missing=False)
out["startup_index_total_s"] = round(time.time() - t, 2)
out["rss_after_index_mb"] = rss_mb()

svc = QuestionDeduplicationService(db)
q = db.query(Question).filter(Question.status == "published").first()
kids = [r.knowledge_id for r in db.query(QuestionKnowledge)
        .filter(QuestionKnowledge.question_id == q.id).all()]
snap = QuestionSnapshot(
    question_type=q.question_type, content=q.content, answer=q.answer or "",
    options=[], question_bank_id=q.question_bank_id, knowledge_ids=kids,
)

durs = []
for _ in range(10):
    t = time.time()
    svc.check_one(snap)
    durs.append(round(time.time() - t, 3))
out["check_one_10_runs_s"] = durs
out["check_one_avg_s"] = round(sum(durs) / len(durs), 3)

snaps = [
    QuestionSnapshot(
        question_type=q.question_type, content=f"{q.content}（批量{i}）",
        answer=q.answer or "", options=[], question_bank_id=q.question_bank_id,
        knowledge_ids=kids)
    for i in range(20)
]
reviewer = svc._get_llm_reviewer()
calls_before = reviewer.call_count
t = time.time()
results = svc.check_batch(snaps)
out["check_batch_20_total_s"] = round(time.time() - t, 2)
out["check_batch_20_llm_calls"] = reviewer.call_count - calls_before
out["check_batch_20_decisions"] = [r.decision for r in results]
out["check_batch_20_llm_avg_pair_latency_s"] = reviewer.avg_latency if hasattr(reviewer, "avg_latency") else None

from agent.common.vector_store import get_question_vector_store  # noqa: E402

out["faiss_vectors"] = get_question_vector_store().count()
out["rss_final_mb"] = rss_mb()
db.close()
print("PERF_RESULT_JSON_BEGIN")
print(json.dumps(out, ensure_ascii=False, indent=2))
print("PERF_RESULT_JSON_END")
