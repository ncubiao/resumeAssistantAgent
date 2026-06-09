"""Analyzer Agent 节点 - 对结构化简历进行打分分析。"""
from __future__ import annotations

from app.core.logging import get_logger

logger = get_logger("agent.analyzer")


def run(parsed_resume: dict | None) -> dict:
    """占位分析器。"""
    logger.info("analyzer agent (stub) running")
    return {
        "highlights": [],
        "weaknesses": [],
        "education_score": 0,
        "experience_score": 0,
        "skills": [],
    }
