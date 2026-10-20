"""Test configuration and fixtures."""

import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Override settings before importing app
os.environ["MYSQL_DATABASE"] = "interview_agent_test"
os.environ["DEBUG"] = "false"

# Use temp directory for uploads to avoid sandbox permission issues
import tempfile
_upload_tmp = os.path.join(tempfile.gettempdir(), "test_uploads")
os.makedirs(_upload_tmp, exist_ok=True)
os.environ["UPLOAD_DIR"] = _upload_tmp

from app.core.config import settings
from app.core.database import get_db
from app.core.security import hash_password
from app.main import app
from app.models import Base
from app.repositories.admin_repository import AdminRepository

# Test database engine
TEST_DATABASE_URL = (
    f"mysql+pymysql://{settings.MYSQL_USERNAME}:{settings.MYSQL_PASSWORD}"
    f"@{settings.MYSQL_HOST}:{settings.MYSQL_PORT}/interview_agent_test"
    f"?charset=utf8mb4"
)

engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
TestingSessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


@pytest.fixture(scope="session", autouse=True)
def setup_database():
    """Create all tables before tests and drop after."""
    Base.metadata.create_all(bind=engine)
    yield
    # 收尾前等待后台生成/导入线程结束：后台线程的数据库事务
    # 会与 drop_all 的元数据锁互相等待（REPEATABLE READ + MDL）
    try:
        from app.services.background_runner import join_background_tasks
        join_background_tasks(timeout=30.0)
    except Exception:  # noqa: BLE001
        pass
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(autouse=True)
def clean_tables():
    """Clean all tables before each test, then recreate initial knowledge_base data."""
    with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())

    # 重新创建初始知识库数据（因为 clean_tables 清空了所有表）
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT IGNORE INTO knowledge_base (code, name, description, status)
            VALUES
                ('android', 'Android', 'Android 开发相关知识', 1),
                ('java', 'Java', 'Java 语言和生态相关知识', 1),
                ('distributed_systems', '分布式系统', '分布式架构相关知识', 1),
                ('c_language', 'C 语言', 'C 语言编程相关知识', 1),
                ('uncategorized', '未分类', '尚未归类的知识点', 1)
        """))
        conn.execute(text("""
            INSERT IGNORE INTO question_bank (code, name, description, status)
            VALUES
                ('uncategorized', '未分类题库', '未分类题目兜底', 1)
        """))
    yield


@pytest.fixture
def db():
    """Get a test database session."""
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db):
    """Get a test client with overridden database dependency."""
    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def admin_user(db):
    """Create a test admin user."""
    repo = AdminRepository(db)
    admin = repo.create(
        username="testadmin",
        password_hash=hash_password("testpass123"),
        nickname="测试管理员",
    )
    db.commit()
    return admin


@pytest.fixture
def auth_headers(client, admin_user):
    """Get authentication headers with valid JWT token."""
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "testadmin", "password": "testpass123"},
    )
    token = response.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def sample_knowledge(client, auth_headers):
    """Create a sample knowledge point."""
    response = client.post(
        "/api/v1/knowledge",
        headers=auth_headers,
        json={
            "name": "Python装饰器",
            "summary": "装饰器是闭包的应用",
            "content": "装饰器详细内容...",
            "difficulty": 2,
            "status": 1,
            "source_type": "MANUAL",
            "keywords": ["装饰器", "闭包"],
        },
    )
    return response.json()["data"]


@pytest.fixture
def sample_knowledge2(client, auth_headers):
    """Create a second sample knowledge point."""
    response = client.post(
        "/api/v1/knowledge",
        headers=auth_headers,
        json={
            "name": "Python闭包",
            "summary": "闭包是函数式编程基础",
            "difficulty": 2,
        },
    )
    return response.json()["data"]
