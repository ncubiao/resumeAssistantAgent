"""FastAPI 应用入口 - resumeAssistantAgent 后端。"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import agent, chat, match, optimize, resume
from app.core.config import settings
from app.core.database import init_db
from app.core.logging import get_logger, setup_logging
from app.utils.llm_client import llm_client

# 初始化日志
setup_logging(settings.log_level)
logger = get_logger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时建表（create_all 幂等，已存在则跳过）。

    阶段 2 起数据库正式启用。生产化时建议切换为 Alembic 迁移管理。
    """
    init_db()
    logger.info("application startup complete", env=settings.app_env)
    yield


app = FastAPI(
    title=settings.app_name,
    description="简历分析 AI Agent 后端 API（支持 DashScope / OpenAI 兼容模式）",
    version="0.2.0",
    debug=settings.debug,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(resume.router, prefix="/api/v1/resumes", tags=["resumes"])
app.include_router(match.router, prefix="/api/v1/matches", tags=["matches"])
app.include_router(optimize.router, prefix="/api/v1/optimize", tags=["optimize"])
app.include_router(chat.router, prefix="/api/v1/chat", tags=["chat"])
app.include_router(agent.router, prefix="/api/v1/agent", tags=["agent"])


@app.get("/health", tags=["health"])
async def health_check() -> dict:
    """服务健康检查。"""
    return {
        "status": "ok",
        "service": settings.app_name,
        "env": settings.app_env,
    }


@app.get("/api/v1/llm/health", tags=["llm"])
async def llm_health_check() -> dict:
    """LLM 连通性检查。

    该接口不真正调用模型，只报告：
    - 当前配置的 provider / model / base_url
    - api_key 是否已配置（不回传 key 本身）
    - 依赖是否可导入
    """
    key = settings.llm_api_key or ""
    key_masked = key[:8] + "***" if len(key) > 8 else "(empty)"
    return {
        "provider": llm_client.provider,
        "model": llm_client.model,
        "base_url": llm_client.base_url,
        "api_key_configured": bool(key),
        "api_key_preview": key_masked,
        "api_key_passes_check": (
            bool(key)
            and "你的" not in key
            and "your" not in key.lower()
            and key.strip() not in {"sk-", "sk-proj-", "sk-proj-你的xxx"}
            and len(key.strip()) >= 8
        ),
        "client_available": llm_client.available,
        "note": (
            "如果 api_key_passes_check=false，请检查 .env 文件中 LLM_API_KEY。"
            " 如果 client_available=false，说明 key 被判定为占位符或未配置，模型会走 fallback。"
        ),
    }


@app.post("/api/v1/llm/test", tags=["llm"])
async def llm_test(payload: dict | None = None) -> dict:
    """真正发起一次 LLM 调用，用于验证配置。

    可通过 JSON body 传入自定义 prompt：
        {"prompt": "请用一句话介绍你自己"}
    """
    prompt = (payload or {}).get("prompt") or "你好，请用一句话介绍你自己。"
    reply = llm_client.invoke(prompt)
    return {
        "provider": llm_client.provider,
        "model": llm_client.model,
        "prompt": prompt,
        "reply": reply or "(empty - LLM 未配置 / 调用失败)",
        "ok": bool(reply),
    }


@app.get("/", tags=["root"])
async def root() -> dict:
    return {
        "message": "resumeAssistantAgent API",
        "docs": "/docs",
        "health": "/health",
        "llm_health": "/api/v1/llm/health",
        "supported_providers": ["dashscope", "openai", "deepseek"],
    }
