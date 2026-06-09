"""FastAPI 应用入口 - resumeAssistantAgent 后端。"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import resume, match, optimize
from app.core.config import settings
from app.core.logging import setup_logging

# 初始化日志
setup_logging(settings.log_level)

app = FastAPI(
    title=settings.app_name,
    description="简历分析 AI Agent 后端 API",
    version="0.1.0",
    debug=settings.debug,
)

# CORS 配置（开发期全放开，生产期收窄）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 路由注册
app.include_router(resume.router, prefix="/api/v1/resumes", tags=["resumes"])
app.include_router(match.router, prefix="/api/v1/matches", tags=["matches"])
app.include_router(optimize.router, prefix="/api/v1/optimize", tags=["optimize"])


@app.get("/health", tags=["health"])
async def health_check() -> dict[str, str]:
    """服务健康检查。"""
    return {"status": "ok", "service": settings.app_name, "env": settings.app_env}


@app.get("/", tags=["root"])
async def root() -> dict[str, str]:
    return {
        "message": "resumeAssistantAgent API",
        "docs": "/docs",
        "health": "/health",
    }
