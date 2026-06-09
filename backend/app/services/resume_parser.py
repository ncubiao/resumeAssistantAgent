"""简历文件解析服务。

当前实现（阶段 1 骨架）：
- 支持从 PDF / Word / 纯文本文件提取原始文本
- 返回结构化 ResumeOut 占位信息
- 真正的 LLM 结构化提取在阶段 3（Parser Agent）实现

Usage:
    parsed = parse_resume_file(raw_bytes, filename, suffix)
"""
from __future__ import annotations

import io
from typing import BinaryIO

from app.core.logging import get_logger
from app.models.schemas import ResumeOut

logger = get_logger("resume_parser")


def _extract_pdf(raw: bytes) -> str:
    """从 PDF 提取文本。"""
    try:
        import pdfplumber  # type: ignore

        with pdfplumber.open(io.BytesIO(raw)) as pdf:
            return "\n".join(
                page.extract_text() or "" for page in pdf.pages
            ).strip()
    except Exception as exc:  # noqa: BLE001
        logger.warning("pdfplumber failed, fallback to PyPDF2", error=str(exc))
    try:
        from PyPDF2 import PdfReader  # type: ignore

        reader = PdfReader(io.BytesIO(raw))
        return "\n".join(page.extract_text() or "" for page in reader.pages).strip()
    except Exception as exc:  # noqa: BLE001
        logger.error("pdf extraction failed", error=str(exc))
        return ""


def _extract_docx(raw: bytes) -> str:
    """从 Word 提取文本。"""
    try:
        from docx import Document  # type: ignore

        doc = Document(io.BytesIO(raw))
        return "\n".join(p.text for p in doc.paragraphs).strip()
    except Exception as exc:  # noqa: BLE001
        logger.error("docx extraction failed", error=str(exc))
        return ""


def extract_text(raw: bytes, suffix: str) -> str:
    """根据文件后缀提取纯文本内容。"""
    suffix = suffix.lower()
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


def parse_resume_file(raw: bytes, filename: str, suffix: str) -> ResumeOut:
    """解析简历文件并返回结构化结果。

    Args:
        raw: 原始字节内容
        filename: 原始文件名
        suffix: 文件后缀（pdf / docx / doc）

    Returns:
        ResumeOut 结构化结果（当前阶段仅含 raw_text，后续阶段会填充字段）
    """
    text = extract_text(raw, suffix)
    logger.info(
        "resume text extracted",
        filename=filename,
        char_count=len(text),
    )

    # 阶段 1 骨架：返回基础结果
    # 阶段 3 将调用 Parser Agent 进行 LLM 结构化提取
    return ResumeOut(
        filename=filename,
        raw_text=text[:5000],  # 截断避免 Swagger 过大
        parse_confidence=0.0,  # 占位：未接入 LLM
    )
