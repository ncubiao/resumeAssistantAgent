"""通用工具函数。"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path


def compute_file_hash(raw: bytes) -> str:
    """计算文件 SHA256 哈希，用于去重。"""
    return hashlib.sha256(raw).hexdigest()


def ensure_dir(path: str) -> Path:
    """确保目录存在，返回 Path 对象。"""
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def clean_text(text: str) -> str:
    """清理文本多余空白与控制字符。"""
    if not text:
        return ""
    text = re.sub(r"\r\n|\r", "\n", text)
    text = re.sub(r"[ \t\u3000]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def truncate(text: str, max_len: int = 5000) -> str:
    """截断文本到指定长度。"""
    return text[:max_len] if len(text) > max_len else text
