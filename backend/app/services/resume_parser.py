"""文件解析服务：PDF / Word / 纯文本 / 图片（OCR） -> 字符串。

只做 I/O，不做语义分析。语义分析交给 agents.nodes.parser_agent。
"""
from __future__ import annotations

import io

from app.core.logging import get_logger

logger = get_logger("file_parser")

_IMAGE_SUFFIXES = {"png", "jpg", "jpeg", "webp", "bmp", "gif", "tif", "tiff"}


def extract_text(raw: bytes, suffix: str) -> str:
    """根据文件后缀，抽取纯文本。

    Args:
        raw: 文件原始字节
        suffix: 文件后缀（不带点），例如 "pdf", "docx", "txt", "png"

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
    if suffix in _IMAGE_SUFFIXES:
        return _extract_image_ocr(raw, suffix)
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


def _extract_image_ocr(raw: bytes, suffix: str) -> str:
    """用 LLM 视觉模型（如 qwen3-vl-plus）提取图片中的文字内容。

    相比传统 OCR（Tesseract）：
    - 支持中文/英文/表格/代码/手写体混合排版
    - 自动保留段落/换行结构
    - 不需要本地安装 Tesseract 和语言包
    """
    from app.utils.llm_client import llm_client

    if not llm_client.available:
        logger.warning("LLM client not configured, image OCR skipped")
        return ""

    prompt = (
        "请仔细阅读图片中的所有文字内容，并按原格式逐字提取。"
        "要求：\n"
        "1. 逐行输出，保留原有的换行和排版；\n"
        "2. 包括中英文、数字、日期、邮箱、电话、标点符号；\n"
        "3. 表格和列表请用文字形式尽可能还原；\n"
        "4. 不要添加任何解释或前言，直接输出提取到的文字内容。"
    )
    text = llm_client.invoke_vision(
        image_bytes=raw,
        image_format=suffix,
        prompt=prompt,
        system="你是一个精准的文档文本提取助手，只输出图片中的原始文字内容，不添加任何总结和解释。",
    )
    logger.info("image OCR (LLM vision) finished", suffix=suffix, chars=len(text))
    return text
