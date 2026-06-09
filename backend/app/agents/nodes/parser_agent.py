"""Parser Agent 节点 - 从 raw_text 提取结构化信息。"""
from __future__ import annotations

from app.core.logging import get_logger

logger = get_logger("agent.parser")


def run(raw_text: str) -> dict:
    """占位解析器。返回基本字段。"""
    logger.info("parser agent (stub) running", text_len=len(raw_text))
    return {
        "parsed_resume": {
            "name": None,
            "email": None,
            "skills": [],
            "work_history": [],
        },
        "parse_confidence": 0.0,
    }
