"""简历相关 API 路由。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel

from app.agents.nodes.parser_agent import run as run_parser
from app.core.logging import get_logger
from app.models.schemas import ResumeCreate, ResumeOut, ResumeUpdate
from app.services.resume_parser import extract_text

logger = get_logger("api.resume")
router = APIRouter()

_SUPPORTED_SUFFIXES = {"pdf", "docx", "doc", "txt", "md", "png", "jpg", "jpeg", "webp", "bmp", "gif", "tif", "tiff"}


class ParseTextRequest(BaseModel):
    text: str


@router.post(
    "/upload",
    response_model=ResumeOut,
    status_code=status.HTTP_201_CREATED,
    summary="上传并解析简历（PDF/Word/TXT/图片）",
)
async def upload_resume(file: UploadFile = File(...)) -> ResumeOut:
    """上传简历文件 -> 提取文本 -> Parser Agent 结构化。"""
    if not file.filename:
        raise HTTPException(status_code=400, detail="无效文件名")

    suffix = file.filename.rsplit(".", 1)[-1].lower()
    if suffix not in _SUPPORTED_SUFFIXES:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件格式 .{suffix}（支持 {', '.join(sorted(_SUPPORTED_SUFFIXES))}）",
        )

    logger.info("processing resume upload", filename=file.filename, suffix=suffix)

    contents = await file.read()
    raw_text = extract_text(contents, suffix)
    return _build_resume_out(file.filename, raw_text)


@router.post(
    "/parse-text",
    response_model=ResumeOut,
    status_code=status.HTTP_201_CREATED,
    summary="直接传入简历文本进行解析",
)
async def parse_text(payload: ParseTextRequest) -> ResumeOut:
    """方便调试 / 测试：直接上传简历文本内容。"""
    if not payload.text or not payload.text.strip():
        raise HTTPException(status_code=400, detail="text 不能为空")
    return _build_resume_out("plain_text.txt", payload.text)


def _build_resume_out(filename: str, raw_text: str) -> ResumeOut:
    """统一调用 Parser Agent 并把结果组装成 ResumeOut。"""
    parser_result: dict[str, Any] = run_parser(raw_text) or {}
    parsed = parser_result.get("parsed_resume") or {}
    confidence = float(parser_result.get("parse_confidence") or 0.0)
    provider = parser_result.get("provider") or "unknown"

    out = ResumeOut(
        filename=filename,
        raw_text=raw_text[:4000],
        name=parsed.get("name"),
        email=parsed.get("email"),
        phone=parsed.get("phone"),
        education_level=parsed.get("education_level"),
        years_of_experience=_to_float(parsed.get("years_of_experience")),
        skills=parsed.get("skills") or [],
        work_history=parsed.get("work_history") or [],
        projects=parsed.get("projects") or [],
        parse_confidence=confidence,
    )
    logger.info(
        "resume parsed",
        filename=filename,
        confidence=confidence,
        provider=provider,
        skills_count=len(out.skills),
        jobs_count=len(out.work_history),
    )
    return out


def _to_float(v) -> float | None:
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return float(str(v))
    except (TypeError, ValueError):
        return None


# ---------- 以下接口仍是占位，等阶段 2 接入数据库 ----------

@router.get("", response_model=list[ResumeOut], summary="获取简历列表")
async def list_resumes() -> list[ResumeOut]:
    return []


@router.get("/{resume_id}", response_model=ResumeOut, summary="获取简历详情")
async def get_resume(resume_id: str) -> ResumeOut:
    raise HTTPException(status_code=501, detail="数据库持久化功能在阶段 2 实现")


@router.put("/{resume_id}", response_model=ResumeOut, summary="更新简历信息")
async def update_resume(resume_id: str, payload: ResumeUpdate) -> ResumeOut:
    raise HTTPException(status_code=501, detail="数据库持久化功能在阶段 2 实现")


@router.delete("/{resume_id}", status_code=200, summary="删除简历")
async def delete_resume(resume_id: str) -> dict:
    raise HTTPException(status_code=501, detail="数据库持久化功能在阶段 2 实现")
