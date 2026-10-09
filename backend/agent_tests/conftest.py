"""agent_tests 的测试配置，复用 tests/conftest.py 的 fixtures。"""

import os
import sys

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 复用 tests/conftest.py 的 fixtures
from tests.conftest import (  # noqa: F401
    admin_user,
    auth_headers,
    clean_tables,
    client,
    db,
    sample_knowledge,
    sample_knowledge2,
    setup_database,
)
