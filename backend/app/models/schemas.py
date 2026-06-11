"""API 请求/响应的 Pydantic Schemas。"""
from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

# ---------- 工作经历 / 项目经历（嵌套结构） ----------

class WorkExperience(BaseModel):
    """工作经历条目。"""

    company: str | None = None
    role: str | None = None
    period: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    highlights: list[str] = Field(default_factory=list)


class ProjectItem(BaseModel):
    """项目经历条目。"""

    name: str | None = None
    description: str | None = None
    role: str | None = None
    period: str | None = None
    technologies: list[str] = Field(default_factory=list)


# ---------- 简历 ----------

class ResumeBase(BaseModel):
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    education_level: str | None = None
    years_of_experience: float | None = None
    skills: list[str] = Field(default_factory=list)


class ResumeCreate(ResumeBase):
    raw_text: str = ""


class ResumeUpdate(BaseModel):
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    education_level: str | None = None
    years_of_experience: float | None = None
    skills: list[str] | None = None
    work_history: list[WorkExperience] | None = None


class ResumeOut(ResumeBase):
    """简历解析输出 Schema。"""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(default_factory=uuid4)
    filename: str | None = None
    raw_text: str = ""
    work_history: list[WorkExperience] = Field(default_factory=list)
    projects: list[ProjectItem] = Field(default_factory=list)
    parse_confidence: float = 0.0
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ---------- 匹配 ----------

class MatchBreakdown(BaseModel):
    skill_match: float = 0.0
    experience_match: float = 0.0
    education_match: float = 0.0


class MatchRequest(BaseModel):
    resume_id: str
    jd: str


class BatchMatchRequest(BaseModel):
    resume_ids: list[str]
    jd: str


class MatchResultOut(BaseModel):
    match_id: UUID = Field(default_factory=uuid4)
    resume_id: str
    overall_score: float = 0.0
    breakdown: MatchBreakdown = Field(default_factory=MatchBreakdown)
    strengths: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class BatchMatchResultOut(BaseModel):
    jd: str
    results: list[MatchResultOut] = Field(default_factory=list)


# ---------- 优化 ----------

class OptimizeRequest(BaseModel):
    resume_id: str
    target_jd: str | None = None


class OptimizeSuggestion(BaseModel):
    category: str
    original: str
    improved: str
    reason: str


class OptimizeResultOut(BaseModel):
    resume_id: str
    suggestions: list[OptimizeSuggestion] = Field(default_factory=list)


class RewriteRequest(BaseModel):
    paragraph: str
    target_role: str | None = None


class RewriteResultOut(BaseModel):
    original: str
    rewritten: str
    highlights: list[str] = Field(default_factory=list)


# ---------- Agent 编排（阶段 3） ----------

class AgentAnalyzeRequest(BaseModel):
    """resume_id 与 raw_text 二选一，至少给一个。"""

    resume_id: str | None = None
    raw_text: str | None = None
    jd: str | None = None
    mode: Literal["match", "optimize", "both"] | None = None
    thread_id: str | None = None


class TraceEntry(BaseModel):
    node: str
    started_at: str
    duration_ms: int = 0
    output_keys: list[str] = Field(default_factory=list)
    error: str | None = None


class AnalysisDetail(BaseModel):
    skills: list[str] = Field(default_factory=list)
    highlights: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    education_score: int = 0
    experience_score: int = 0


class MatchDetail(BaseModel):
    score: float = 0.0
    strengths: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    reasoning: str = ""


class OptimizeDetail(BaseModel):
    suggestions: list[OptimizeSuggestion] = Field(default_factory=list)


class AgentAnalyzeResponse(BaseModel):
    parsed_resume: dict | None = None
    parse_confidence: float = 0.0
    analysis: AnalysisDetail = Field(default_factory=AnalysisDetail)
    match: MatchDetail | None = None
    optimize: OptimizeDetail | None = None
    trace: list[TraceEntry] = Field(default_factory=list)
    thread_id: str
    mode: str
