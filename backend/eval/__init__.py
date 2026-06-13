"""Eval 框架：黄金集 + 评估指标 + runner。

不同于普通单测（只验证函数能跑），eval 验证 Agent 输出的**质量**：
匹配分与人工标注的相关性、关键优势/差距的召回率。

本地运行：
    cd backend && python -m eval.runner

集成在 pytest（标记 @pytest.mark.eval，默认不跑，需显式开启）：
    pytest -m eval -v
"""
