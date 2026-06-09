"""FastAPI 应用入口 - resumeAssistantAgent 后端。"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import match, optimize, resume
from app.core.config import settings
from app.core.logging import setup_logging
from app.utils.llm_client import llm_client

# 初始化日志
setup_logging(settings.log_level)

app = FastAPI(
    title=settings.app_name,
    description="简历分析 AI Agent 后端 API（支持 DashScope / OpenAI 兼容模式）",
    version="0.2.0",
    debug=settings.debug,
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
    return {
        "provider": llm_client.provider,
        "model": llm_client.model,
        "base_url": llm_client.base_url,
        "api_key_configured": bool(llm_client.api_key) and "你的" not in (llm_client.api_key or ""),
        "client_available": llm_client.available,
        "note": (
            "未配置 key 或依赖缺失时，API 会走启发式 fallback 而不是报错。"
            " 若要真正测试模型响应，请使用 POST /api/v1/llm/test。"
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
