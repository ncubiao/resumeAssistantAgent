"""Analyzer 节点（启发式）单元测试。"""
from __future__ import annotations

from app.agents.nodes import analyzer_agent


def test_analyzer_with_full_resume():
    parsed = {
        "name": "张三",
        "email": "z@x.com",
        "phone": "1380000",
        "education_level": "硕士",
        "years_of_experience": 5,
        "skills": ["python", "fastapi", "docker"],
        "work_history": [
            {"company": "A", "role": "工程师", "highlights": ["主导支付重构", "上线 K8s 集群"]}
        ],
        "projects": [{"name": "P", "description": "高并发订单系统"}],
    }
    out = analyzer_agent.run(parsed)
    assert out["education_score"] == 75  # 硕士
    assert out["experience_score"] == 60  # 5 * 12
    assert out["skills"] == ["python", "fastapi", "docker"]
    assert "主导支付重构" in out["highlights"]
    assert "高并发订单系统" in out["highlights"]
    # 完整简历 -> weaknesses 应为空或很少
    assert out["weaknesses"] == []


def test_analyzer_with_empty_resume():
    out = analyzer_agent.run({})
    assert out["education_score"] == 30  # 默认
    assert out["experience_score"] == 0
    assert out["skills"] == []
    assert out["highlights"] == []
    # 空简历应触发多条 weakness
    assert len(out["weaknesses"]) >= 3


def test_analyzer_with_none():
    out = analyzer_agent.run(None)
    assert isinstance(out, dict)
    assert out["education_score"] == 30
    assert out["experience_score"] == 0


def test_analyzer_education_mapping():
    for level, expected in [("博士", 90), ("Master of Science", 75), ("本科", 60), ("大专", 40)]:
        out = analyzer_agent.run({"education_level": level})
        assert out["education_score"] == expected, level


def test_analyzer_experience_capped():
    out = analyzer_agent.run({"years_of_experience": 100})
    assert out["experience_score"] == 100  # 封顶
