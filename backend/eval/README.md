# Agent Quality Eval Framework

端到端质量评测：对真实 LLM 跑黄金数据集，对比人工标注，验证 Agent 输出质量。

## 为什么需要 Eval

普通单测只验证"代码能跑"，Eval 验证 **LLM 决策质量**：
- 匹配分与人工标注的相关性（Pearson）
- 匹配分的平均误差（MAE）
- 关键优势/差距的召回率

当你改 prompt、换 LLM、改 tools 逻辑时，跑 eval 能量化告诉你"变好了还是变坏了"。

## 目录结构

```
eval/
├── fixtures/
│   └── golden_dataset.py   # 10 条简历+JD+人工标注
├── metrics.py              # MAE / Pearson / 关键点召回率（零依赖）
├── runner.py               # eval 跑通器 + 对比报告渲染
└── README.md
```

## 快速开始

### 1. 直接打印报告（不走 pytest）
```bash
cd backend
python -m eval.runner
```

输出样例：
```
============================================================================
Resume-JD Match Eval Report
============================================================================
sample                         pred  target       Δ  str_r  gap_r
----------------------------------------------------------------------------
high_match_backend               95      95      +0   1.00   1.00
mid_match_frontend               65      60      +5   1.00   1.00
low_match_skill_mismatch         20      25      -5   1.00   1.00
...
----------------------------------------------------------------------------
N=10  MAE=3.8  RMSE=5.78  Pearson=0.982  strengths_recall=0.975  gaps_recall=0.883
============================================================================
```

### 2. 通过 pytest 运行（含门槛断言）
```bash
cd backend
pytest -m eval -v -s
```

**默认 pytest 不跑 eval**（需真实 LLM Key）。上述命令显式用 `-m eval` 触发。

### 3. Makefile 快捷命令
```bash
make eval         # pytest 运行，含断言
make eval-report  # 直接打印报告
```

## 指标含义

| 指标 | 含义 | 当前门槛 | 说明 |
|---|---|---|---|
| **MAE** | 匹配分平均绝对误差 | ≤ 20 | 越小越好；实测 ~4 |
| **RMSE** | 均方根误差 | — | 对大偏差更敏感 |
| **Pearson** | 相关系数 | ≥ 0.6 | -1~1，越接近 1 越好；实测 ~0.98 |
| **strengths_recall** | 优势点召回率 | ≥ 0.4 | GT 提到的优势，Agent 是否也抓到（token 重叠匹配）；实测 ~0.97 |
| **gaps_recall** | 差距点召回率 | ≥ 0.4 | 同上；实测 ~0.88 |

门槛设在保守基线，确保低级失误会被挡住。**Pearson > 0.9** 说明 Agent 给分趋势与人类高度一致。

## CI 集成

### 普通 CI（自动跑）
`ci.yml` **不跑 eval**（无 LLM Key）。只跑功能测试 + lint + 覆盖率。

### Eval CI（手动触发）
`.github/workflows/eval.yml` 需手动触发或每周一定时跑（如配了 `LLM_API_KEY` secret）：
- Actions → Agent Quality Eval → Run workflow
- 需在 repo Settings → Secrets 配置 `LLM_API_KEY` / `LLM_MODEL` / `LLM_BASE_URL`

## 黄金数据集设计

`fixtures/golden_dataset.py` 含 10 条样本，覆盖：
- 高匹配（技能+经验完美）
- 中匹配（部分技能对应）
- 低匹配（技能栈不符 / 应届生 vs 3年岗）
- 边界场景（过度资深 / 转岗 / UI设计师 vs 前端）

每条含：
- `resume_text`: 简历原文
- `jd`: 岗位描述
- `ground_truth`: `{"score": 0-100, "strengths": [...], "gaps": [...]}`

## 扩展黄金集

修改 `fixtures/golden_dataset.py`，追加新样本。格式：
```python
{
    "id": "your_case_id",
    "resume_text": "...",
    "jd": "...",
    "ground_truth": {
        "score": 75,
        "strengths": ["关键优势1", "关键优势2"],
        "gaps": ["关键差距1"]
    }
}
```

## 注意事项

1. **LLM 非确定性**：同一输入多次跑，分数可能略有浮动（±5 分），这是正常现象。Eval 关注的是**整体趋势相关性**，而非逐条精确相等。
2. **召回率匹配策略**：用 token 集合的 Jaccard 重叠（阈值 0.2），而非严格字符串相等。"5年Python经验" 与 "5年经验" token 重叠度 ≥ 20% 即算命中。这避免措辞变化导致的低估。
3. **门槛可调**：首次设的是保守基线（MAE ≤ 20），实际跑出 ~4。后续可收紧门槛，让回归更敏感。

## 进一步改进方向

- **扩展数据集**：10 条 → 50+ 条，更全面覆盖行业/岗位
- **多指标细分**：按样本类型（高/中/低匹配）分组统计 MAE
- **对抗样本**：故意制造歧义简历（如"5年经验，其中2年非本岗"），验证 Agent 鲁棒性
- **A/B 对比**：换 prompt 或 model 后，新旧指标对比（Δ MAE / Δ Pearson）
