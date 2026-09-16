"""应用全局配置管理模块。

本模块负责从 .env 文件和环境变量加载所有应用级配置。
配置通过 Pydantic Settings 自动读取，支持类型校验和默认值。

配置分类：
    - 应用配置：名称、环境、调试模式
    - MySQL 配置：主机、端口、数据库、用户名、密码
    - JWT 配置：密钥、算法、有效期
    - 文件上传配置：目录、大小限制
    - CORS 配置：允许的来源域名

使用方式：
    from app.core.config import settings
    db_url = settings.database_url
    jwt_key = settings.JWT_SECRET_KEY
"""

import json
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用全局配置类。

    通过 pydantic-settings 自动从 .env 文件读取配置。
    环境变量优先级高于 .env 文件。
    """

    model_config = SettingsConfigDict(
        env_file=".env",           # 配置文件路径
        env_file_encoding="utf-8", # 文件编码
        case_sensitive=False,      # 环境变量名不区分大小写
        extra="ignore",            # 忽略 .env 中与本类无关的变量（如 LLM 配置）
    )

    # ==================== 应用配置 ====================
    APP_NAME: str = "interview_agent"   # 应用名称
    APP_ENV: str = "development"        # 运行环境：development / production
    DEBUG: bool = True                  # 是否开启调试模式（生产环境应设为 False）

    # ==================== MySQL 数据库配置 ====================
    MYSQL_HOST: str = "127.0.0.1"       # 数据库主机地址
    MYSQL_PORT: int = 3306              # 数据库端口
    MYSQL_DATABASE: str = "interview_agent"  # 数据库名称
    MYSQL_USERNAME: str = "root"        # 数据库用户名
    MYSQL_PASSWORD: str = ""            # 数据库密码（禁止硬编码，从 .env 读取）

    # ==================== JWT 认证配置 ====================
    JWT_SECRET_KEY: str = "change-me-to-a-random-secret-key"
    # JWT 签名密钥，生产环境必须修改为随机字符串
    JWT_ALGORITHM: str = "HS256"        # JWT 签名算法
    JWT_EXPIRE_MINUTES: int = 120       # Token 有效期（分钟）

    # ==================== 文件上传配置 ====================
    UPLOAD_DIR: str = "./uploads"       # 上传文件保存目录
    MAX_UPLOAD_SIZE: int = 10 * 1024 * 1024  # 最大上传大小：10MB

    # ==================== CORS 跨域配置 ====================
    CORS_ORIGINS: str = '["http://localhost:3000","http://localhost:5173"]'
    # 允许的前端来源域名（JSON 数组格式）

    @property
    def database_url(self) -> str:
        """构建 MySQL 连接 URL，供 SQLAlchemy 使用。

        返回格式：mysql+pymysql://user:pass@host:port/db?charset=utf8mb4
        """
        return (
            f"mysql+pymysql://{self.MYSQL_USERNAME}:{self.MYSQL_PASSWORD}"
            f"@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DATABASE}"
            f"?charset=utf8mb4"
        )

    @property
    def async_database_url(self) -> str:
        """构建异步 MySQL 连接 URL（预留，当前未使用）。"""
        return (
            f"mysql+aiomysql://{self.MYSQL_USERNAME}:{self.MYSQL_PASSWORD}"
            f"@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DATABASE}"
            f"?charset=utf8mb4"
        )

    @property
    def cors_origins_list(self) -> List[str]:
        """解析 CORS 来源列表。

        将 JSON 格式的字符串转换为 Python 列表。
        解析失败时返回默认值。
        """
        try:
            return json.loads(self.CORS_ORIGINS)
        except (json.JSONDecodeError, TypeError):
            return ["http://localhost:3000", "http://localhost:5173"]


# 全局配置单例
# 在模块加载时自动读取 .env 文件，后续通过 settings 直接访问
settings = Settings()
