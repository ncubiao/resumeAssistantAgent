"""Pydantic Settings 配置管理。

从 .env 文件或环境变量读取配置。
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# 项目根目录（backend/ 下的 app/core 往上两层）
PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """全局应用配置。"""

    # 应用
    app_env: str = "dev"
    app_name: str = "resumeAssistantAgent"
    debug: bool = True

    backend_host: str = "0.0.0.0"
    backend_port: int = 8000

    # 数据库
    database_url: str = "sqlite:///./resume_agent.db"

    # LLM
    llm_provider: str = "openai"
    llm_api_key: str = ""
    llm_model: str = "gpt-4o-mini"
    llm_base_url: str = "https://api.openai.com/v1"
    llm_temperature: float = 0.2
    llm_max_tokens: int = 2048

    # 向量检索
    vector_index_path: str = str(PROJECT_ROOT / "data" / "vector_index" / "faiss_index.bin")
    vector_dim: int = 1536

    # 文件上传
    upload_dir: str = str(PROJECT_ROOT / "data" / "uploads")
    max_file_size_mb: int = 20

    # 日志
    log_level: str = "INFO"
    log_format: str = "json"

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )


@lru_cache
def get_settings() -> Settings:
    """单例配置。"""
    return Settings()


settings = get_settings()
