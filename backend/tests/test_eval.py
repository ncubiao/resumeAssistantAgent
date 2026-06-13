"""Eval 指标的单元测试 + Eval 集成测试。

指标计算是纯函数，作为普通单测跑（快、确定）。
真正的 Eval（对真实 LLM 跑黄金集）标记 @pytest.mark.eval，需显式启用：
    pytest -m eval -v
默认 pytest 跑不会触发，避免 CI 在无 key 环境失败。
"""
from __future__ import annotations

import pytest

from eval.metrics import (
    aggregate,
    key_point_recall,
    mae,
    pearson,
    rmse,
)

# ---------------- 指标计算（纯函数，普通单测） ----------------

def test_mae_basic():
    assert mae([90, 80, 70], [100, 80, 60]) == pytest.approx(20 / 3)


def test_mae_zero_when_perfect():
    assert mae([50, 60, 70], [50, 60, 70]) == 0


def test_rmse_basic():
    assert rmse([100, 100], [80, 60]) == pytest.approx(((20**2 + 40**2) / 2) ** 0.5)


def test_pearson_perfect_positive():
    assert pearson([10, 20, 30], [1, 2, 3]) == pytest.approx(1.0)


def test_pearson_perfect_negative():
    assert pearson([10, 20, 30], [3, 2, 1]) == pytest.approx(-1.0)


def test_pearson_zero_variance():
    """退化场景应返回 0，不抛 ZeroDivisionError。"""
    assert pearson([5, 5, 5], [1, 2, 3]) == 0.0


def test_pearson_too_few_samples():
    assert pearson([1], [1]) == 0.0


def test_key_point_recall_full_hit():
    pred = ["5年Python经验丰富", "FastAPI 实战经验"]
    gt = ["5年经验", "FastAPI 完全匹配"]
    # token 重叠应足够命中
    assert key_point_recall(pred, gt) == pytest.approx(1.0)


def test_key_point_recall_partial():
    pred = ["有 Python 经验"]
    gt = ["熟悉 Python", "熟悉 FastAPI"]
    # Python 命中，FastAPI 不命中 -> 0.5
    assert key_point_recall(pred, gt) == pytest.approx(0.5)


def test_key_point_recall_empty_gt_returns_one():
    # 无标注点视为满分（避免拉低均值）
    assert key_point_recall(["something"], []) == 1.0


def test_key_point_recall_empty_pred_returns_zero():
    assert key_point_recall([], ["有要求"]) == 0.0


def test_aggregate_basic():
    per_sample = [
        {"predicted_score": 90, "target_score": 95, "strengths_recall": 1.0, "gaps_recall": 1.0},
        {"predicted_score": 60, "target_score": 50, "strengths_recall": 0.5, "gaps_recall": 0.5},
    ]
    summ = aggregate(per_sample)
    assert summ["n"] == 2
    assert summ["mae"] == pytest.approx(7.5)
    assert "pearson" in summ
    assert summ["strengths_recall"] == pytest.approx(0.75)


# ---------------- 真实 LLM Eval（标记，需显式跑） ----------------


@pytest.mark.eval
def test_eval_against_golden_dataset_real_llm():
    """对真实 LLM 跑黄金集，断言关键质量门槛。

    门槛（首次基线，可后续按实测调整）：
    - MAE <= 20  匹配分平均误差不超过 20 分
    - Pearson >= 0.6  整体趋势相关性 >= 0.6
    - strengths_recall >= 0.4  优势点召回 >= 40%
    - gaps_recall      >= 0.4  差距点召回 >= 40%

    LLM 不可用时跳过（不在无 key 环境硬失败）。
    """
    from app.utils.llm_client import llm_client

    if not llm_client.available:
        pytest.skip("LLM not configured; eval requires real LLM")

    from eval.runner import render_report, run_eval

    result = run_eval()
    print(render_report(result))  # 输出可读报告，便于排查

    summ = result["summary"]
    assert summ["n"] >= 10, f"expected at least 10 samples, got {summ['n']}"
    assert summ["mae"] <= 20, f"MAE 超阈值: {summ['mae']}"
    assert summ["pearson"] >= 0.6, f"相关性低于阈值: {summ['pearson']}"
    assert summ["strengths_recall"] >= 0.4, f"优势召回偏低: {summ['strengths_recall']}"
    assert summ["gaps_recall"] >= 0.4, f"差距召回偏低: {summ['gaps_recall']}"
