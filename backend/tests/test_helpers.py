"""工具函数测试。"""
from __future__ import annotations

from app.utils.helpers import clean_text, compute_file_hash, truncate


def test_compute_file_hash_consistent():
    raw = b"hello world"
    assert compute_file_hash(raw) == compute_file_hash(raw)
    assert compute_file_hash(raw) != compute_file_hash(b"hello")


def test_clean_text_collapses_whitespace():
    text = "  这是 \t 一份   简历  \n\n\n\n  正文  "
    cleaned = clean_text(text)
    # 连续空白被折叠为单空格，但行尾换行被保留
    assert "这是 一份 简历" in cleaned
    assert "正文" in cleaned
    # 多余的 4 个换行被折叠为 1 个段落分隔符
    assert "\n\n\n\n" not in cleaned


def test_truncate():
    text = "a" * 10000
    assert len(truncate(text, 100)) == 100
    assert len(truncate(text, 20000)) == 10000
