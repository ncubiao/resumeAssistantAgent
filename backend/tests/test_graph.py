"""LangGraph 全图编排测试。

强制关闭 LLM 走 heuristic 路径，让测试离线、确定性。
"""
from __future__ import annotations

import pytest

from app.agents import graph as graph_mod


@pytest.fixture(autouse=True)
def _disable_llm(monkeypatch):
    """关闭 LLM，所有节点走 fallback 路径。"""
    from app.utils.llm_client import llm_client

    monkeypatch.setattr(llm_client, "_unavailable", True)
    yield


def _resume_text() -> str:
    return "张三，本科，3年经验。技能：Python FastAPI Docker。"


def test_graph_runs_all_nodes_in_both_mode():
    state = graph_mod.run_analysis(_resume_text(), jd="招聘 Python 后端", mode="both", thread_id="g-both")
    nodes = [t["node"] for t in state["trace"]]
    assert nodes == ["parser", "analyzer", "matcher", "optimizer"]
    # 每个节点都应有 duration_ms 字段（>=0）和无 error
    for entry in state["trace"]:
        assert entry["duration_ms"] >= 0
        assert entry["error"] is None


def test_graph_match_only_skips_optimizer():
    state = graph_mod.run_analysis(_resume_text(), jd="JD 文本", mode="match", thread_id="g-match")
    nodes = [t["node"] for t in state["trace"]]
    assert nodes == ["parser", "analyzer", "matcher"]
    assert "optimizer" not in nodes


def test_graph_optimize_only_skips_matcher():
    state = graph_mod.run_analysis(_resume_text(), mode="optimize", thread_id="g-opt")
    nodes = [t["node"] for t in state["trace"]]
    assert nodes == ["parser", "analyzer", "optimizer"]


def test_graph_auto_mode_with_jd_routes_to_match():
    state = graph_mod.run_analysis(_resume_text(), jd="some jd", thread_id="g-auto-jd")
    nodes = [t["node"] for t in state["trace"]]
    assert "matcher" in nodes
    assert "optimizer" not in nodes
    assert state["mode"] == "match"


def test_graph_auto_mode_without_jd_routes_to_optimize():
    state = graph_mod.run_analysis(_resume_text(), thread_id="g-auto-nojd")
    nodes = [t["node"] for t in state["trace"]]
    assert "optimizer" in nodes
    assert "matcher" not in nodes
    assert state["mode"] == "optimize"


def test_graph_returns_thread_id():
    state = graph_mod.run_analysis(_resume_text(), thread_id="custom-thread")
    assert state["thread_id"] == "custom-thread"
    state2 = graph_mod.run_analysis(_resume_text())
    assert state2["thread_id"]  # 自动生成


def test_graph_state_contains_analysis_fields():
    state = graph_mod.run_analysis(_resume_text(), thread_id="g-fields")
    # parser
    assert state["parsed_resume"] is not None
    # analyzer
    assert "education_score" in state and "experience_score" in state
    assert isinstance(state["weaknesses"], list)
