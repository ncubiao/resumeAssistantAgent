"""LangGraph StateGraph 定义。

阶段 1：定义状态模型与图的骨架结构，后续阶段填充节点逻辑。
"""
from __future__ import annotations

from typing import TypedDict

from app.core.logging import get_logger

logger = get_logger("agent.graph")


class ResumeAnalysisState(TypedDict, total=False):
    """Agent 工作流状态。

    整个流程：raw_text -> parser -> analyzer -> (matcher | optimizer) -> END
    """

    # 输入
    raw_text: str
    jd: str | None

    # 解析
    parsed_resume: dict | None
    parse_confidence: float

    # 分析
    skills: list[str]
    highlights: list[str]
    weaknesses: list[str]
    education_score: int
    experience_score: int

    # 匹配
    match_score: float | None
    match_breakdown: dict | None
    match_reasons: list[str]

    # 优化
    optimize_suggestions: list[dict]

    # 元信息
    current_node: str
    trace: list[dict]
    error: str | None


def build_default_state(raw_text: str, jd: str | None = None) -> ResumeAnalysisState:
    """创建一个初始状态字典。"""
    return {
        "raw_text": raw_text,
        "jd": jd,
        "parsed_resume": None,
        "parse_confidence": 0.0,
        "skills": [],
        "highlights": [],
        "weaknesses": [],
        "education_score": 0,
        "experience_score": 0,
        "match_score": None,
        "match_breakdown": None,
        "match_reasons": [],
        "optimize_suggestions": [],
        "current_node": "start",
        "trace": [],
        "error": None,
    }


def build_graph():
    """构建 LangGraph 工作流图（骨架版）。

    阶段 4 会填充节点真实逻辑。此处仅确保结构可导入、可实例化。
    """
    try:
        from langgraph.graph import END, StateGraph  # type: ignore

        graph = StateGraph(ResumeAnalysisState)

        # 节点占位
        graph.add_node("parser", _parser_node_stub)
        graph.add_node("analyzer", _analyzer_node_stub)
        graph.add_node("matcher", _matcher_node_stub)
        graph.add_node("optimizer", _optimizer_node_stub)

        graph.set_entry_point("parser")
        graph.add_edge("parser", "analyzer")
        graph.add_conditional_edges(
            "analyzer",
            _route_after_analyzer,
            {"matcher": "matcher", "optimizer": "optimizer"},
        )
        graph.add_edge("matcher", END)
        graph.add_edge("optimizer", END)

        logger.info("agent graph built (skeleton)")
        return graph.compile()
    except Exception as exc:  # noqa: BLE001
        logger.warning("langgraph not available, return stub", error=str(exc))
        return None


# ---------- 占位节点 ----------

def _parser_node_stub(state: dict) -> dict:
    return {"current_node": "parser", "trace": [{"node": "parser"}]}


def _analyzer_node_stub(state: dict) -> dict:
    return {"current_node": "analyzer", "trace": [{"node": "analyzer"}]}


def _matcher_node_stub(state: dict) -> dict:
    return {"current_node": "matcher", "trace": [{"node": "matcher"}]}


def _optimizer_node_stub(state: dict) -> dict:
    return {"current_node": "optimizer", "trace": [{"node": "optimizer"}]}


def _route_after_analyzer(state: dict) -> str:
    return "matcher" if state.get("jd") else "optimizer"
