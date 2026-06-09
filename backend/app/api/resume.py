"""简历相关 API 路由。"""
from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, UploadFile, status

from app.core.logging import get_logger
from app.models.schemas import ResumeCreate, ResumeOut, ResumeUpdate
from app.services.resume_parser import parse_resume_file

logger = get_logger("api.resume")
router = APIRouter()


@router.post(
    "/upload",
    response_model=ResumeOut,
    status_code=status.HTTP_201_CREATED,
    summary="上传并解析简历",
)
async def upload_resume(file: UploadFile = File(...)) -> ResumeOut:
    """上传简历文件（PDF/Word），自动解析为结构化信息。

    - **file**: PDF 或 Word 简历文件
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="无效文件名")

    suffix = file.filename.rsplit(".", 1)[-1].lower()
    if suffix not in {"pdf", "docx", "doc"}:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件格式 .{suffix}，支持 pdf/docx/doc",
        )

    logger.info("processing resume upload", filename=file.filename, size=file.size)

    try:
        contents = await file.read()
        parsed = parse_resume_file(contents, file.filename, suffix)
    except Exception as exc:  # noqa: BLE001
        logger.exception("resume parse failed", error=str(exc))
        raise HTTPException(status_code=500, detail=f"解析失败: {exc}") from exc

    return parsed


@router.get("", response_model=list[ResumeOut], summary="获取简历列表")
async def list_resumes() -> list[ResumeOut]:
    """占位：返回简历列表（当前未持久化数据库，返回空）。"""
    # TODO: 阶段 2 - 从 PostgreSQL 读取
    return []


@router.get("/{resume_id}", response_model=ResumeOut, summary="获取简历详情")
async def get_resume(resume_id: str) -> ResumeOut:
    """占位：根据 ID 获取单份简历。"""
    raise HTTPException(status_code=501, detail="数据库持久化功能在阶段 2 实现")


@router.put("/{resume_id}", response_model=ResumeOut, summary="更新简历信息")
async def update_resume(resume_id: str, payload: ResumeUpdate) -> ResumeOut:
    """占位：人工修正简历解析结果。"""
    raise HTTPException(status_code=501, detail="数据库持久化功能在阶段 2 实现")


@router.delete("/{resume_id}", status_code=204, summary="删除简历")
async def delete_resume(resume_id: str) -> None:
    """占位：删除简历。"""
    raise HTTPException(status_code=501, detail="数据库持久化功能在阶段 2 实现")
