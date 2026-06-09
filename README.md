# resumeAssistantAgent

简历小助手 - 基于 LangGraph + FastAPI + Streamlit 的简历分析 AI Agent 项目

> 练手项目，技术栈完整，效果可打磨

## 🎯 项目简介

面向招聘方（简历筛选、JD 匹配、候选人对比）与求职方（简历解析、简历优化建议）双视角的智能简历分析平台。

## 🏗️ 技术架构

```
                    ┌────────────────────────────────────────────┐
                    │           Streamlit 前端 UI                  │
                    │  (简历上传 / JD 输入 / 结果展示)               │
                    └────────────────┬───────────────────────────┘
                                     │ HTTP REST API
                    ┌────────────────▼─────────────────────────┐
                    │          FastAPI 后端服务                    │
                    │   /api/resume/* /api/match/* /api/optimize/* │
                    └────────┬──────────────────────┬────────────┘
                             │                      │
                  ┌──────────▼──────────┐  ┌────────▼──────────────┐
                  │    数据库 & 向量存储  │  │     LangGraph Agent      │
                  │ PostgreSQL + FAISS   │  │  (多 Agent 编排工作流)     │
                  │   · 简历元数据        │  │                         │
                  │   · 技能向量索引      │  │  Parser Agent            │
                  │   · 解析结果缓存      │  │  Analyzer Agent          │
                  └─────────────────────┘  │  Optimizer Agent         │
                                           │  Matcher Agent           │
                                           └─────────────────────────┘
                                                         │
                                                  ┌──────▼──────┐
                                                  │   LLM API    │
                                                  │ (OpenAI /    │
                                                  │  DeepSeek)   │
                                                  └─────────────┘
```

## 🧰 技术栈清单

### 后端
- **FastAPI** - 高性能 Python Web 框架，自动生成 Swagger 文档
- **Python 3.11+** - 主语言
- **Pydantic Settings** - 配置管理
- **SQLAlchemy 2.0** - ORM 数据操作
- **PostgreSQL** - 关系型数据库
- **FAISS** - 向量相似度检索
- **LangGraph** - Agent 编排（状态图、多节点工作流）
- **LangChain** - LLM 应用组件
- **PyPDF2 / python-docx** - 简历文件解析
- **structlog** - 结构化日志

### 前端
- **Streamlit** - 快速搭建数据/AI 应用 UI
- **streamlit-antd-components** - 增强组件

### 工程化
- **Docker + Docker Compose** - 容器化部署
- **GitHub Actions** - CI/CD 流水线
- **pytest + coverage.py** - 单元/集成测试 + 覆盖率
- **ruff + mypy** - 代码规范检查与类型检查
- **Makefile** - 快捷命令

## 📁 目录结构

```
resumeAssistantAgent/
├── .github/workflows/       # CI/CD 流水线
├── docker/                  # Dockerfile
├── docker-compose.yml
├── backend/                 # FastAPI 后端
│   ├── app/
│   │   ├── main.py          # FastAPI 入口
│   │   ├── api/             # API 路由层
│   │   ├── core/            # 配置/日志
│   │   ├── models/          # Pydantic Schemas + SQLAlchemy ORM
│   │   ├── services/        # 业务逻辑服务
│   │   ├── agents/          # LangGraph Agents
│   │   │   ├── graph.py     # StateGraph 定义
│   │   │   ├── nodes/       # 各 Agent 节点
│   │   │   └── prompts/     # Prompt 模板
│   │   ├── tests/           # 测试
│   │   └── utils/           # 工具函数
│   └── requirements.txt
├── frontend/                # Streamlit 前端
│   ├── app.py               # 入口页面
│   ├── pages/               # 多页面
│   ├── components/          # 可复用组件
│   └── requirements.txt
├── data/                    # 示例数据 & 向量索引
├── scripts/                 # 初始化脚本
├── docs/                    # 项目规划文档
└── tests/                   # 端到端测试
```

## 🚀 快速开始

### 方式一：Docker Compose（推荐）

```bash
cp .env.example .env
# 修改 .env 中的 LLM API Key
docker-compose up --build
```

- 前端 UI: http://localhost:8501
- 后端 API: http://localhost:8000
- API 文档: http://localhost:8000/docs

### 方式二：本地开发

```bash
# 后端
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 前端（新终端）
cd frontend
pip install -r requirements.txt
streamlit run app.py
```

## 🧪 运行测试

```bash
cd backend
pytest -v --cov=app --cov-report=html
```

## 📖 详细文档

- [项目完整计划](docs/PROJECT_PLAN.md)
- [架构设计](docs/ARCHITECTURE.md)
- [技术栈详情](docs/TECH_STACK.md)
- [API 设计](docs/API_DESIGN.md)
- [Agent 工作流](docs/AGENT_WORKFLOW.md)
- [开发路线图](docs/ROADMAP.md)

## 📝 License

MIT
