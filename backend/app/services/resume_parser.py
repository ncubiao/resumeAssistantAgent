"""文件解析服务：PDF / Word / 纯文本 -> 字符串。

只做 I/O，不做语义分析。语义分析交给 agents.nodes.parser_agent。
"""
from __future__ import annotations

import io

from app.core.logging import get_logger

logger = get_logger("file_parser")


def extract_text(raw: bytes, suffix: str) -> str:
    """根据文件后缀，抽取纯文本。

    Args:
        raw: 文件原始字节
        suffix: 文件后缀（不带点），例如 "pdf", "docx", "txt"

    Raises:
        ValueError: 不支持的后缀
    """
    suffix = (suffix or "").lower()
    if suffix == "pdf":
        return _extract_pdf(raw)
    if suffix in {"docx", "doc"}:
        return _extract_docx(raw)
    if suffix in {"txt", "md"}:
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError:
            return raw.decode("utf-8", errors="ignore")
    raise ValueError(f"不支持的文件格式: .{suffix}")


def _extract_pdf(raw: bytes) -> str:
    try:
        import pdfplumber  # type: ignore

        with pdfplumber.open(io.BytesIO(raw)) as pdf:
            return "\n".join(page.extract_text() or "" for page in pdf.pages).strip()
    except Exception as exc:  # noqa: BLE001
        logger.warning("pdfplumber failed, fallback to PyPDF2", error=str(exc))
    try:
        from PyPDF2 import PdfReader  # type: ignore

        reader = PdfReader(io.BytesIO(raw))
        return "\n".join(page.extract_text() or "" for page in reader.pages).strip()
    except Exception as exc:  # noqa: BLE001
        logger.error("pdf extraction finally failed", error=str(exc))
        return ""


def _extract_docx(raw: bytes) -> str:
    try:
        from docx import Document  # type: ignore

        doc = Document(io.BytesIO(raw))
        return "\n".join(p.text for p in doc.paragraphs).strip()
    except Exception as exc:  # noqa: BLE001
        logger.error("docx extraction failed", error=str(exc))
        return ""
