"""Eval runner：跑黄金集 + 输出对比报告。

用法：
  作为脚本：python -m eval.runner
  作为函数：from eval.runner import run_eval; results = run_eval()

直接调用 matcher_tool（绕过 LangGraph，eval 关注的是 LLM 决策质量本身），
对比 ground truth 的 score / strengths / gaps，输出每条明细 + 聚合指标。
"""
from __future__ import annotations

import json
from typing import Any

from app.agents.tools.match_tools import match_resume_to_jd
from eval.fixtures.golden_dataset import get_golden_dataset
from eval.metrics import aggregate, key_point_recall


def _run_one(sample: dict) -> dict:
    """对单条样本调用 matcher，返回明细。"""
    raw = match_resume_to_jd(sample["resume_text"], sample["jd"])
    try:
        pred = json.loads(raw)
    except (TypeError, ValueError):
        pred = {}

    pred_score = float(pred.get("overall_score") or 0)
    pred_strengths = [str(s) for s in (pred.get("strengths") or [])]
    pred_gaps = [str(g) for g in (pred.get("gaps") or [])]

    gt = sample["ground_truth"]
    return {
        "id": sample["id"],
        "predicted_score": pred_score,
        "target_score": float(gt["score"]),
        "delta": pred_score - float(gt["score"]),
        "predicted_strengths": pred_strengths,
        "predicted_gaps": pred_gaps,
        "target_strengths": list(gt.get("strengths") or []),
        "target_gaps": list(gt.get("gaps") or []),
        "strengths_recall": key_point_recall(pred_strengths, gt.get("strengths") or []),
        "gaps_recall": key_point_recall(pred_gaps, gt.get("gaps") or []),
    }


def run_eval(samples: list[dict] | None = None) -> dict[str, Any]:
    """跑全量 eval，返回 {per_sample, summary}。"""
    samples = samples or get_golden_dataset()
    per_sample = [_run_one(s) for s in samples]
    summary = aggregate(per_sample)
    return {"per_sample": per_sample, "summary": summary}


def render_report(result: dict[str, Any]) -> str:
    """把 eval 结果渲染成可读文本报告。"""
    lines = ["", "=" * 76, "Resume-JD Match Eval Report", "=" * 76]
    lines.append(
        f"{'sample':<28} {'pred':>6} {'target':>7} {'Δ':>7} {'str_r':>6} {'gap_r':>6}"
    )
    lines.append("-" * 76)
    for s in result["per_sample"]:
        lines.append(
            f"{s['id']:<28} {s['predicted_score']:>6.0f} {s['target_score']:>7.0f} "
            f"{s['delta']:>+7.0f} {s['strengths_recall']:>6.2f} {s['gaps_recall']:>6.2f}"
        )
    lines.append("-" * 76)
    summ = result["summary"]
    lines.append(
        f"N={summ.get('n', 0)}  MAE={summ.get('mae')}  RMSE={summ.get('rmse')}  "
        f"Pearson={summ.get('pearson')}  "
        f"strengths_recall={summ.get('strengths_recall')}  "
        f"gaps_recall={summ.get('gaps_recall')}"
    )
    lines.append("=" * 76)
    return "\n".join(lines)


def main() -> None:
    result = run_eval()
    print(render_report(result))


if __name__ == "__main__":
    main()
