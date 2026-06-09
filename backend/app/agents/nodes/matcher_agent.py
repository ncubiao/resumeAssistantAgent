"""Matcher Agent 节点 - 基于 JD 计算匹配度。"""
from __future__ import annotations

from app.core.logging import get_logger

logger = get_logger("agent.matcher")


def run(resume: dict, jd: str) -> dict:
    """占位匹配器。"""
    logger.info("matcher agent (stub) running", jd_len=len(jd))
    return {
        "match_score": 0.0,
        "match_breakdown": {"skill_match": 0.0, "experience_match": 0.0, "education_match": 0.0},
        "match_reasons": [],
    }
