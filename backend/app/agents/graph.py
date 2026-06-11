"""LangGraph StateGraph：简历分析多 Agent 工作流。

阶段 3 真实实现：
  parser -> analyzer -> [match | optimize | both] -> END

设计要点：
- ``trace`` 字段用 ``Annotated[list, add]`` 作为 reducer，节点返回 ``{"trace": [新条目]}``
  即可累加；其他字段沿用默认 "覆盖" 语义。
- 节点函数用 ``_traced(name, fn)`` 包裹，自动记录 started_at / duration_ms /
  output_keys / error，写入 trace。
- Checkpointer 用 MemorySaver（单进程作品集场景足够）。多实例切 SqliteSaver/
  PostgresSaver 即可。
- 路由由 ``state["mode"]`` 决定（match / optimize / both），mode 留空则按 jd 是否存在自动推断。
"""
from __future__ import annotations

import operator
import time
import traceback
from datetime import datetime, timezone
from typing import Annotated, Any, Callable, TypedDict
from uuid import uuid4

from app.agents.nodes import analyzer_agent, matcher_agent, optimizer_agent, parser_agent
from app.core.logging import get_logger

logger = get_logger("agent.graph")


class ResumeAnalysisState(TypedDict, total=False):
    """Agent 工作流状态。"""

    # 输入
    raw_text: str
    jd: str | None
    mode: str | None  # "match" | "optimize" | "both"

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
    match_strengths: list[str]
    match_gaps: list[str]
    match_reasoning: str

    # 优化
    optimize_suggestions: list[dict]

    # 元信息：trace 用 add 作为 reducer，节点返回 [一条新记录] 会被累加
    current_node: str
    trace: Annotated[list[dict], operator.add]
    error: str | None


def build_default_state(
    raw_text: str, jd: str | None = None, mode: str | None = None
) -> ResumeAnalysisState:
    return {
        "raw_text": raw_text,
        "jd": jd,
        "mode": mode,
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
        "match_strengths": [],
        "match_gaps": [],
        "match_reasoning": "",
        "optimize_suggestions": [],
        "current_node": "start",
        "trace": [],
        "error": None,
    }


# ---------------- trace 装饰器 ----------------

def _traced(name: str, fn: Callable[[ResumeAnalysisState], dict]):
    """包裹节点函数，自动记录 trace 条目。"""

    def wrapper(state: ResumeAnalysisState) -> dict:
        started_at = datetime.now(timezone.utc).isoformat()
        t0 = time.perf_counter()
        entry: dict[str, Any] = {"node": name, "started_at": started_at, "error": None}
        try:
            result = fn(state) or {}
        except Exception as exc:  # noqa: BLE001
            duration = int((time.perf_counter() - t0) * 1000)
            logger.error("node failed", node=name, error=str(exc), tb=traceback.format_exc())
            entry.update({
                "duration_ms": duration,
                "output_keys": [],
                "error": str(exc),
            })
            return {"current_node": name, "trace": [entry], "error": str(exc)}

        duration = int((time.perf_counter() - t0) * 1000)
        entry.update({
            "duration_ms": duration,
            "output_keys": sorted(list(result.keys())),
            "error": None,
        })
        # 节点 result 里若已带 trace，会被 reducer 自动累加；这里再 append 我们的条目
        return {**result, "current_node": name, "trace": [entry]}

    return wrapper


# ---------------- 节点 ----------------

def _parser_node(state: ResumeAnalysisState) -> dict:
    out = parser_agent.run(state.get("raw_text") or "")
    return {
        "parsed_resume": out.get("parsed_resume"),
        "parse_confidence": float(out.get("parse_confidence") or 0.0),
    }


def _analyzer_node(state: ResumeAnalysisState) -> dict:
    return analyzer_agent.run(state.get("parsed_resume"))


def _matcher_node(state: ResumeAnalysisState) -> dict:
    raw = state.get("raw_text") or ""
    jd = state.get("jd") or ""
    if not jd:
        return {}
    return matcher_agent.run(raw, jd)


def _optimizer_node(state: ResumeAnalysisState) -> dict:
    raw = state.get("raw_text") or ""
    jd = state.get("jd")
    return optimizer_agent.run(raw, jd)


# ---------------- 路由 ----------------

def _resolve_mode(state: ResumeAnalysisState) -> str:
    """空 mode -> 按 jd 是否存在自动推断。"""
    mode = (state.get("mode") or "").strip().lower()
    if mode in {"match", "optimize", "both"}:
        return mode
    return "match" if state.get("jd") else "optimize"


def _route_after_analyzer(state: ResumeAnalysisState) -> str:
    """analyzer 结束后第一站。"""
    mode = _resolve_mode(state)
    if mode == "optimize":
        return "optimizer"
    # match 或 both 都先走 matcher
    return "matcher"


def _route_after_matcher(state: ResumeAnalysisState) -> str:
    """matcher 结束后：both 模式继续 optimizer，否则结束。"""
    return "optimizer" if _resolve_mode(state) == "both" else "__end__"


# ---------------- 构图 ----------------

_compiled_graph: Any = None


def build_graph():
    """构建并编译 LangGraph 图（带 MemorySaver checkpointer）。"""
    global _compiled_graph
    if _compiled_graph is not None:
        return _compiled_graph
    try:
        from langgraph.checkpoint.memory import MemorySaver  # type: ignore
        from langgraph.graph import END, StateGraph  # type: ignore

        graph = StateGraph(ResumeAnalysisState)
        graph.add_node("parser", _traced("parser", _parser_node))
        graph.add_node("analyzer", _traced("analyzer", _analyzer_node))
        graph.add_node("matcher", _traced("matcher", _matcher_node))
        graph.add_node("optimizer", _traced("optimizer", _optimizer_node))

        graph.set_entry_point("parser")
        graph.add_edge("parser", "analyzer")
        graph.add_conditional_edges(
            "analyzer",
            _route_after_analyzer,
            {"matcher": "matcher", "optimizer": "optimizer"},
        )
        graph.add_conditional_edges(
            "matcher",
            _route_after_matcher,
            {"optimizer": "optimizer", "__end__": END},
        )
        graph.add_edge("optimizer", END)

        # 单进程作品集场景：MemorySaver 够用。
        # TODO 多实例 / 持久化场景：换 SqliteSaver 或 PostgresSaver。
        _compiled_graph = graph.compile(checkpointer=MemorySaver())
        logger.info("agent graph compiled")
        return _compiled_graph
    except Exception as exc:  # noqa: BLE001
        logger.error("langgraph build failed", error=str(exc))
        return None


def run_analysis(
    raw_text: str,
    jd: str | None = None,
    mode: str | None = None,
    thread_id: str | None = None,
) -> dict:
    """对外的便捷入口：执行整张图，返回最终 state（含 trace）+ thread_id。"""
    state = build_default_state(raw_text, jd=jd, mode=mode)
    state["mode"] = _resolve_mode(state)

    compiled = build_graph()
    if compiled is None:
        # 兜底：不依赖 langgraph 也能给出结果
        out = _parser_node(state)
        state.update(out)
        analyzer_out = _analyzer_node(state)
        state.update(analyzer_out)
        if state["mode"] in {"match", "both"} and state.get("jd"):
            state.update(_matcher_node(state))
        if state["mode"] in {"optimize", "both"}:
            state.update(_optimizer_node(state))
        state["thread_id"] = thread_id or str(uuid4())
        return state

    tid = thread_id or str(uuid4())
    config = {"configurable": {"thread_id": tid}}
    final_state = compiled.invoke(state, config=config)
    final_state["thread_id"] = tid
    return final_state
