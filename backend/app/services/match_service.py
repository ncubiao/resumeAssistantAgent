"""匹配服务 - 基于 JD 计算简历匹配度。

阶段 1 骨架：定义接口。
阶段 4 接入 Matcher Agent。
"""
from __future__ import annotations

from app.core.logging import get_logger
from app.models.schemas import MatchResultOut

logger = get_logger("match_service")


def compute_match(resume_id: str, jd: str, resume_text: str) -> MatchResultOut:
    """占位：计算简历与 JD 的匹配度。"""
    logger.info("match requested", resume_id=resume_id, jd_len=len(jd))
    return MatchResultOut(
        resume_id=resume_id,
        overall_score=0.0,
        strengths=[],
        gaps=[],
    )
