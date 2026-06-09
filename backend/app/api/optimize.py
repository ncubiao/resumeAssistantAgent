"""简历优化相关 API 路由。"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.core.logging import get_logger
from app.models.schemas import OptimizeRequest, OptimizeResultOut, RewriteRequest, RewriteResultOut

logger = get_logger("api.optimize")
router = APIRouter()


@router.post("/suggestions", response_model=OptimizeResultOut, summary="生成优化建议")
async def get_suggestions(payload: OptimizeRequest) -> OptimizeResultOut:
    """针对目标岗位生成简历优化建议。"""
    logger.info("optimize suggestions requested")
    raise HTTPException(status_code=501, detail="Optimizer Agent 在阶段 4 实现")


@router.post("/rewrite", response_model=RewriteResultOut, summary="段落重写")
async def rewrite_paragraph(payload: RewriteRequest) -> RewriteResultOut:
    """对指定段落进行重写优化。"""
    logger.info("paragraph rewrite requested")
    raise HTTPException(status_code=501, detail="Optimizer Agent 在阶段 4 实现")
