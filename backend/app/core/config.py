"""Pydantic Settings 配置管理。

从 .env 文件或环境变量读取配置。支持以下路径（按优先级，后读到的覆盖前面：
1. 项目根目录（backend/ 的上级目录，与 .env.example 同级）
2. backend/ 目录
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# 项目根目录：backend/app/core/config.py 的上三层（与 .env.example 同级）
REPO_ROOT = Path(__file__).resolve().parents[3]
# backend/ 目录
BACKEND_ROOT = Path(__file__).resolve().parents[2]


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

    # Embedding（向量化）—— 与 LLM 解耦，可独立切换 provider/model。
    # 留空的项会按以下规则回退，老 .env 无需改动即可运行：
    #   embedding_provider 空 -> 跟随 llm_provider
    #   embedding_model    空 -> 按 provider 推断（见 services/embedding.py）
    #   embedding_base_url 空 -> 跟随该 provider 的默认 /v1 地址
    #   embedding_api_key  空 -> 复用 llm_api_key
    # 注意：DeepSeek 无 embedding 端点，会自动降级为关键词检索。
    embedding_provider: str = ""
    embedding_model: str = ""
    embedding_dim: int = 1024
    embedding_base_url: str = ""
    embedding_api_key: str = ""

    # 向量检索
    vector_index_path: str = str(BACKEND_ROOT / "data" / "vector_index" / "faiss_index.bin")
    # deprecated：维度的单一事实来源已改为 embedding_dim，此项仅为向后兼容保留。
    vector_dim: int = 1536

    # 文件上传
    upload_dir: str = str(BACKEND_ROOT / "data" / "uploads")
    max_file_size_mb: int = 20

    # 日志
    log_level: str = "INFO"
    log_format: str = "json"

    model_config = SettingsConfigDict(
        env_file=[str(REPO_ROOT / ".env"), str(BACKEND_ROOT / ".env")],
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )


@lru_cache
def get_settings() -> Settings:
    """单例配置。"""
    return Settings()


settings = get_settings()
