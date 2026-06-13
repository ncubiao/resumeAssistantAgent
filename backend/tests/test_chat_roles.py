"""双角色（招聘方 / 求职者）的 chat agent 单测。

聚焦行为差异（system prompt 视角 + 工具白名单），不依赖真实 LLM。
"""
from __future__ import annotations

import pytest

from app.agents import chat_agent
from app.agents.chat_agent import (
    ROLE_CANDIDATE,
    ROLE_RECRUITER,
    AgentResponse,
    _filter_tools_for,
    _resolve_role,
    _system_prompt_for,
)
from app.agents.tools import get_all_tools

# ---------------- 角色解析 ----------------

def test_resolve_role_known():
    assert _resolve_role("recruiter") == ROLE_RECRUITER
    assert _resolve_role("candidate") == ROLE_CANDIDATE


def test_resolve_role_normalizes_case_and_whitespace():
    assert _resolve_role("  Candidate  ") == ROLE_CANDIDATE
    assert _resolve_role("RECRUITER") == ROLE_RECRUITER


def test_resolve_role_unknown_defaults_recruiter():
    assert _resolve_role("admin") == ROLE_RECRUITER
    assert _resolve_role(None) == ROLE_RECRUITER
    assert _resolve_role("") == ROLE_RECRUITER


# ---------------- System Prompt 切换 ----------------

def test_system_prompt_recruiter_perspective():
    prompt = _system_prompt_for(ROLE_RECRUITER)
    assert "招聘" in prompt
    assert "招聘方视角" in prompt


def test_system_prompt_candidate_perspective():
    prompt = _system_prompt_for(ROLE_CANDIDATE)
    assert "求职" in prompt
    assert "求职者视角" in prompt


def test_system_prompts_are_distinct():
    assert _system_prompt_for(ROLE_RECRUITER) != _system_prompt_for(ROLE_CANDIDATE)


# ---------------- 工具白名单 ----------------

def test_filter_tools_recruiter_has_all_current_tools():
    tools = _filter_tools_for(ROLE_RECRUITER, get_all_tools())
    names = {t.name for t in tools}
    assert "match_resume_to_jd" in names
    assert "parse_resume_text" in names
    assert "generate_optimize_suggestions" in names


def test_filter_tools_candidate_has_self_serve_tools():
    """求职者至少能用：解析自己简历、看匹配度、得优化建议。"""
    tools = _filter_tools_for(ROLE_CANDIDATE, get_all_tools())
    names = {t.name for t in tools}
    assert "parse_resume_text" in names
    assert "match_resume_to_jd" in names
    assert "generate_optimize_suggestions" in names


def test_filter_tools_excludes_unknown():
    """白名单外的工具会被剔除。"""

    class FakeTool:
        name = "search_resumes"  # 不在任何白名单内

    fakes = list(get_all_tools()) + [FakeTool()]
    rec_names = {t.name for t in _filter_tools_for(ROLE_RECRUITER, fakes)}
    cand_names = {t.name for t in _filter_tools_for(ROLE_CANDIDATE, fakes)}
    assert "search_resumes" not in rec_names
    assert "search_resumes" not in cand_names


# ---------------- run_agent 集成（mock LLM 路径） ----------------

@pytest.fixture
def force_fallback(monkeypatch):
    """让 LLM 不可用，走 prompt-based fallback；让我们能直接观察 system_prompt 选择行为。"""
    from app.utils.llm_client import llm_client

    monkeypatch.setattr(llm_client, "_unavailable", True)
    yield


def test_run_agent_returns_user_role_in_response(force_fallback):
    resp = chat_agent.run_agent("你好", user_role="candidate")
    assert isinstance(resp, AgentResponse)
    assert resp.user_role == ROLE_CANDIDATE


def test_run_agent_default_role_is_recruiter(force_fallback):
    resp = chat_agent.run_agent("你好")
    assert resp.user_role == ROLE_RECRUITER


def test_run_agent_unknown_role_falls_back_to_recruiter(force_fallback):
    resp = chat_agent.run_agent("你好", user_role="hacker")
    assert resp.user_role == ROLE_RECRUITER


def test_run_agent_passes_correct_system_prompt(force_fallback, monkeypatch):
    """验证不同角色调用 LLM 时使用了正确的 system prompt（即使 LLM 不可用，
    我们打开 LLM 走真实 invoke 路径并捕获 system 参数）。"""
    captured = {}

    def fake_invoke(prompt, system=None, **kwargs):
        captured["system"] = system
        return "我已了解，请问还有什么需要帮助的吗？"

    from app.utils.llm_client import llm_client

    monkeypatch.setattr(llm_client, "_unavailable", False)
    monkeypatch.setattr(llm_client, "_client", object())  # 装作可用
    monkeypatch.setattr(llm_client, "invoke", fake_invoke)
    # 关掉原生 tool_calls 路径，强制走 prompt-based
    monkeypatch.setattr(chat_agent, "_try_native_tool_calls", lambda *a, **k: None)

    chat_agent.run_agent("你好", user_role="candidate")
    assert "求职" in captured["system"]
    assert "招聘方视角" not in captured["system"]

    captured.clear()
    chat_agent.run_agent("你好", user_role="recruiter")
    assert "招聘" in captured["system"]
    assert "求职者视角" not in captured["system"]
