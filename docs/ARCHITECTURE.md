# 架构设计文档 (Architecture)

## 1. 分层架构

```
┌─────────────────────────────────────────────────┐
│              Presentation Layer (UI)            │
│   Streamlit - 多页面、用户交互、结果展示        │
├─────────────────────────────────────────────────┤
│              API Layer (FastAPI)                │
│   REST 路由层：/api/resume  /api/match  /etc    │
│   依赖注入（Depends）：数据库 Session、LLM 客户端│
├─────────────────────────────────────────────────┤
│              Service Layer                      │
│   业务逻辑：ResumeParser / Matcher / Optimizer  │
│   无状态，纯函数风格，便于测试                   │
├─────────────────────────────────────────────────┤
│              Agent Layer (LangGraph)            │
│   StateGraph - 多节点 Agent 协作                │
│   Parser | Analyzer | Optimizer | Matcher       │
├─────────────────────────────────────────────────┤
│              Data Layer                         │
│   SQLAlchemy ORM + FAISS 向量索引               │
└─────────────────────────────────────────────────┘
```

## 2. 模块依赖方向

```
Streamlit (frontend)
    └──► FastAPI (backend/app/api)
              └──► Services (backend/app/services)
                    ├──► Models (backend/app/models)
                    ├──► Agents (backend/app/agents)
                    │     └──► Prompts (backend/app/agents/prompts)
                    └──► Utils (backend/app/utils)
```

## 3. Agent 状态图（LangGraph StateGraph）

### 3.1 ResumeAnalysisState

```python
class ResumeAnalysisState(TypedDict):
    raw_text: str                    # 原始文本
    parsed_resume: Resume | None     # 结构化简历
    skills: list[str]                # 提取的技能
    work_experience_years: float
    education_score: int
    highlights: list[str]
    weaknesses: list[str]
    jd: str | None
    match_score: float | None
    match_reasons: list[str]
    optimize_suggestions: list[str]
    current_node: str
```

### 3.2 工作流

```
START
  │
  ▼
[Parser Agent] ──► 从 raw_text 提取结构化 Resume
  │
  ▼
[Analyzer Agent] ──► 评分 + 亮点/不足分析
  │
  ▼
├─────────── 有 JD ? ───────────┐
│                               │
是                             否
│                               │
▼                               ▼
[Matcher Agent]              [Optimizer Agent]
│ 计算匹配度 + 理由           │ 生成优化建议
│                               │
└───────────► END ◄──────────────┘
```

## 4. 数据模型设计

### 4.1 Resume（简历）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| filename | str | 原始文件名 |
| file_hash | str | 文件哈希去重 |
| raw_text | text | 全文文本 |
| name | str | 姓名 |
| email | str | 邮箱 |
| phone | str | 电话 |
| education_level | str | 最高学历 |
| years_of_experience | float | 工作年限 |
| skills | JSONB | 技能列表 |
| work_history | JSONB | 工作经历数组 |
| projects | JSONB | 项目经历数组 |
| created_at | datetime | |
| updated_at | datetime | |

### 4.2 MatchResult（匹配结果）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| resume_id | UUID | 外键 |
| jd_text | text | JD 文本 |
| overall_score | float | 总分 0-100 |
| skill_match | float | 技能匹配度 |
| experience_match | float | 经验匹配度 |
| education_match | float | 学历匹配度 |
| strengths | JSONB | 优势 |
| gaps | JSONB | 差距 |
| created_at | datetime | |

## 5. 配置管理

使用 `Pydantic Settings` + `.env` 文件：

- `APP_ENV`: dev / test / prod
- `DATABASE_URL`: PostgreSQL 连接串
- `LLM_PROVIDER`: openai / deepseek
- `LLM_API_KEY`: API Key
- `LLM_MODEL`: gpt-4o-mini 等
- `VECTOR_INDEX_PATH`: FAISS 索引路径

## 6. 日志与监控

- structlog 结构化 JSON 日志
- 每个请求带 request_id
- 关键路径：Agent 每一步都记日志
- Docker Compose 模式下可接入 Prometheus（后续扩展）
