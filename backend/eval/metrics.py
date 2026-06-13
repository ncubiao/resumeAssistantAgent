"""评估指标计算。

设计原则：纯函数 + 无第三方依赖（手写 Pearson 相关系数与 token 重叠召回，
避免引入 numpy/sklearn 让 eval 模块更轻量）。

指标：
- mae: 匹配分平均绝对误差
- rmse: 均方根误差
- pearson: Pearson 相关系数（-1 ~ 1）
- key_point_recall: 关键点召回率（ground truth 提到的 strengths/gaps，
  Agent 输出是否包含——做 token 重叠匹配，非严格字符串相等）
"""
from __future__ import annotations

import math
import re

# 中英文 token 切分
_TOKEN_RE = re.compile(r"[A-Za-z0-9]+|[一-龥]")


def _tokens(text: str) -> set[str]:
    """简单 token 集：英文按词、中文按字。降低对句式差异的敏感度。"""
    return set(t.lower() for t in _TOKEN_RE.findall(text or ""))


def mae(predictions: list[float], targets: list[float]) -> float:
    """平均绝对误差。"""
    if not predictions:
        return 0.0
    return sum(abs(p - t) for p, t in zip(predictions, targets)) / len(predictions)


def rmse(predictions: list[float], targets: list[float]) -> float:
    """均方根误差。"""
    if not predictions:
        return 0.0
    sq = sum((p - t) ** 2 for p, t in zip(predictions, targets))
    return math.sqrt(sq / len(predictions))


def pearson(predictions: list[float], targets: list[float]) -> float:
    """Pearson 相关系数。N<2 或某一序列方差为 0 时返回 0.0。"""
    n = len(predictions)
    if n < 2:
        return 0.0
    mp = sum(predictions) / n
    mt = sum(targets) / n
    cov = sum((p - mp) * (t - mt) for p, t in zip(predictions, targets))
    var_p = sum((p - mp) ** 2 for p in predictions)
    var_t = sum((t - mt) ** 2 for t in targets)
    denom = math.sqrt(var_p * var_t)
    if denom == 0:
        return 0.0
    return cov / denom


def key_point_recall(
    predicted_points: list[str],
    ground_truth_points: list[str],
    overlap_threshold: float = 0.2,
) -> float:
    """关键点召回率：ground truth 中的每条点，是否能在预测里找到 token 重叠率
    >= threshold 的对应条目。返回 0.0 ~ 1.0。

    实现刻意保持简单——LLM 输出的措辞会变（"5年经验" vs "5年Python经验"），
    严格字符串匹配会大幅低估召回。token 集合的 Jaccard 重叠是务实折中。
    """
    if not ground_truth_points:
        return 1.0  # 无标注点 = 默认满分（避免 0 拉低均值）
    if not predicted_points:
        return 0.0

    predicted_token_sets = [_tokens(p) for p in predicted_points]
    hits = 0
    for gt in ground_truth_points:
        gt_tokens = _tokens(gt)
        if not gt_tokens:
            hits += 1
            continue
        # 任一预测项与该 GT 点的 Jaccard ≥ 阈值即算命中
        for pred_tokens in predicted_token_sets:
            if not pred_tokens:
                continue
            overlap = len(gt_tokens & pred_tokens) / len(gt_tokens)
            if overlap >= overlap_threshold:
                hits += 1
                break
    return hits / len(ground_truth_points)


def aggregate(per_sample: list[dict]) -> dict:
    """对每条样本的明细聚合成总指标。

    输入 per_sample 每项含：predicted_score / target_score / strengths_recall / gaps_recall
    """
    if not per_sample:
        return {"n": 0}
    preds = [s["predicted_score"] for s in per_sample]
    tgts = [s["target_score"] for s in per_sample]
    strengths_r = [s["strengths_recall"] for s in per_sample]
    gaps_r = [s["gaps_recall"] for s in per_sample]
    return {
        "n": len(per_sample),
        "mae": round(mae(preds, tgts), 2),
        "rmse": round(rmse(preds, tgts), 2),
        "pearson": round(pearson(preds, tgts), 3),
        "strengths_recall": round(sum(strengths_r) / len(strengths_r), 3),
        "gaps_recall": round(sum(gaps_r) / len(gaps_r), 3),
    }


__all__ = ["mae", "rmse", "pearson", "key_point_recall", "aggregate"]
