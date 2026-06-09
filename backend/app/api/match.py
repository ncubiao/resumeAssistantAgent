"""岗位匹配相关 API 路由。"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.core.logging import get_logger
from app.models.schemas import MatchRequest, MatchResultOut, BatchMatchRequest, BatchMatchResultOut

logger = get_logger("api.match")
router = APIRouter()


@router.post("/single", response_model=MatchResultOut, summary="单份简历 vs JD 匹配")
async def match_single(payload: MatchRequest) -> MatchResultOut:
    """根据简历 ID 和 JD 文本，计算匹配度。"""
    logger.info("single match requested", resume_id=payload.resume_id)
    raise HTTPException(status_code=501, detail="Matcher Agent 在阶段 4 实现")


@router.post("/batch", response_model=BatchMatchResultOut, summary="多份简历批量匹配 & 排序")
async def match_batch(payload: BatchMatchRequest) -> BatchMatchResultOut:
    """同一 JD 下对多份简历批量匹配并排序。"""
    logger.info("batch match requested", count=len(payload.resume_ids))
    raise HTTPException(status_code=501, detail="Matcher Agent 在阶段 4 实现")
