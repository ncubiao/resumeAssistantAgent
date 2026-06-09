"""简历解析服务单元测试。"""
from __future__ import annotations

import pytest

from app.services.resume_parser import extract_text


def test_extract_text_plain_text():
    raw = "张三\nPython 工程师\n技能：Python, FastAPI".encode("utf-8")
    result = extract_text(raw, "txt")
    assert "张三" in result
    assert "Python" in result


def test_extract_text_unknown_suffix_raises():
    with pytest.raises(ValueError, match="不支持"):
        extract_text(b"hello", "xyz")


def test_extract_text_handles_unicode():
    raw = "测试 📝 简历".encode("utf-8")
    result = extract_text(raw, "txt")
    assert "测试" in result
