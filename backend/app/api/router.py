"""API 路由聚合模块。

本模块将所有 v1 版本的路由注册到统一的路由器中。
新增业务模块时，只需在此处添加 include_router 即可。

路由分组：
    - /api/v1/auth —— 认证管理（登录、获取管理员信息）
    - /api/v1/knowledge —— 知识点管理（CRUD + 关系）
    - /api/v1/questions —— 题目管理（CRUD + 选项 + 知识点关联）
    - /api/v1/import-tasks —— 导入任务（文件上传 + 任务管理）
    - /api/v1/dashboard —— 仪表盘（统计数据）
    - /api/v1/agent —— Agent 测试（知识点提取测试接口）
"""

from fastapi import APIRouter

from app.api.v1.agent import router as agent_router
from app.api.v1.agent_dedup import router as agent_dedup_router
from app.api.v1.agent_relation import router as agent_relation_router
from app.api.v1.auth import router as auth_router
from app.api.v1.dashboard import router as dashboard_router
from app.api.v1.import_task import router as import_task_router
from app.api.v1.knowledge import router as knowledge_router
from app.api.v1.knowledge_base import router as knowledge_base_router
from app.api.v1.question import router as question_router
from app.api.v1.question_bank import router as question_bank_router
from app.api.v1.question_plan import router as question_plan_router
from app.api.v1.question_generation import router as question_generation_router
from app.api.v1.answer import router as answer_router
from app.api.v1.comment import router as comment_router

# v1 版本的总路由器，所有 v1 接口都挂在此路由器下
api_v1_router = APIRouter(prefix="/api/v1")

# 注册各业务模块路由
api_v1_router.include_router(auth_router)         # 认证管理：登录、获取管理员信息
api_v1_router.include_router(knowledge_router)    # 知识点管理：CRUD、关系管理
api_v1_router.include_router(knowledge_base_router)  # 知识库管理
api_v1_router.include_router(question_router)     # 题目管理：CRUD、选项、知识点关联
api_v1_router.include_router(question_bank_router)  # 题库管理
api_v1_router.include_router(question_plan_router)  # 出题计划
api_v1_router.include_router(question_generation_router)  # 题目生成
api_v1_router.include_router(answer_router)        # 答题记录
api_v1_router.include_router(comment_router)       # 题目评论
api_v1_router.include_router(import_task_router)  # 导入任务：文件上传、任务查询
api_v1_router.include_router(dashboard_router)    # 仪表盘：系统统计数据
api_v1_router.include_router(agent_router)        # Agent 测试：知识点提取测试接口
api_v1_router.include_router(agent_dedup_router)  # Agent 测试：知识点去重测试接口
api_v1_router.include_router(agent_relation_router)  # Agent 测试：知识点关系判断测试接口
