# resumeAssistantAgent

简历小助手 - 基于 LangGraph + FastAPI + Streamlit 的简历分析 AI Agent 项目

> 练手项目，技术栈完整，效果可打磨。  
> 默认使用 **阿里云 DashScope（通义千问 / Qwen）** 的 OpenAI 兼容模式作为 LLM，
> 同时支持 OpenAI / DeepSeek。

## 🏗️ 架构一览

```
┌───────────────────────────────┐
│  Streamlit 前端（多页面 UI）     │
└──────────┬────────────────────┘
           │ HTTP JSON API
┌──────────▼────────────────────┐
│  FastAPI 后端服务               │
│  /api/v1/resumes/*              │
│  /api/v1/llm/{health,test}      │
└──┬──────────────────┬──────────┘
   │ 文件解析         │ Agent 编排
   │ PDF/DOCX/TXT    │ LangGraph
   │                  │ Parser / Matcher / Optimizer
   ▼                  ▼
 ┌────────────┐   ┌─────────────────────┐
 │ PostgreSQL │   │  阿里云 DashScope    │
 │ (可选)     │   │  Qwen / OpenAI 兼容  │
 └────────────┘   └─────────────────────┘
```

## ✨ 功能（已实现 / 规划）

- ✅ **简历解析** —— 上传 PDF/Word/TXT → LLM 结构化 JSON
- ✅ **LLM 支持** —— DashScope (Qwen) / OpenAI / DeepSeek，均可切换
- ✅ **LLM 健康检查** —— `/api/v1/llm/health`、`/api/v1/llm/test`
- ✅ **Fallback 机制** —— LLM 未配置时，走启发式关键字解析，不报错
- ✅ **完整测试套件** —— pytest，`backend/tests/`
- ✅ **Docker Compose** —— `docker-compose up --build` 一键起
- 🚧 **JD 匹配 & 排序** —— Matcher Agent（阶段 4）
- 🚧 **简历优化建议** —— Optimizer Agent（阶段 4）
- 🚧 **多候选人对比 UI** —— Streamlit（阶段 5）

## 🧰 技术栈

- **后端** —— Python 3.11 + FastAPI + Pydantic v2
- **Agent** —— LangGraph（状态图）+ LangChain
- **LLM** —— OpenAI 兼容协议（DashScope / OpenAI / DeepSeek）
- **文件解析** —— pdfplumber / PyPDF2 / python-docx
- **日志** —— structlog（降级时走标准 logging）
- **测试** —— pytest + coverage
- **前端** —— Streamlit
- **容器** —— Docker + Docker Compose

## 🚀 快速开始

### 方式 1：本地开发（最常用，推荐调试/开发）

```bash
# 1) 克隆 & 安装后端依赖
cd backend
python -m venv venv
# Windows: venv\Scripts\activate
source venv/bin/activate
pip install -r requirements.txt

# 2) 配置 LLM（必选）
cp ../.env.example ../.env
# 编辑 ../.env，填入 LLM_API_KEY（DASHSCOPE_API_KEY）
#   LLM_PROVIDER=dashscope
#   LLM_API_KEY=sk-xxxxxxxxxxxxxxxx
#   LLM_MODEL=qwen3-vl-plus
#   LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1

# 3) 启动后端
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
# 浏览器打开 http://localhost:8000/docs 可查看 Swagger

# 4) 另开一个终端，启动前端
cd frontend
pip install -r requirements.txt
streamlit run app.py
# 浏览器打开 http://localhost:8501
```

### 方式 2：Docker Compose

```bash
cp .env.example .env
# 编辑 .env 中 LLM_API_KEY
docker-compose up --build
# 后端: http://localhost:8000
# 前端: http://localhost:8501
```

## 🔑 配置 LLM（关键步骤）

项目支持 **3 种提供商**，通过 `.env` 文件切换。

### ✅ 推荐：阿里云 DashScope（国内稳定，Qwen）

1. 到 [阿里云 DashScope 控制台](https://dashscope.console.aliyun.com/) 创建 API Key
2. 修改 `.env`：

```dotenv
LLM_PROVIDER=dashscope
LLM_API_KEY=sk-你的dashscope_api_key
LLM_MODEL=qwen3-vl-plus
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_TEMPERATURE=0.2
LLM_MAX_TOKENS=2048
```

常用模型（都走 OpenAI 兼容模式，无需改代码）：

- `qwen-plus` —— 性价比最高（推荐）
- `qwen-turbo` —— 最便宜，响应最快
- `qwen-max` —— 最强能力
- `qwen3-vl-plus` —— 多模态（本项目只用文本，也可跑通）

### 备选：OpenAI

```dotenv
LLM_PROVIDER=openai
LLM_API_KEY=sk-你的key
LLM_MODEL=gpt-4o-mini
LLM_BASE_URL=https://api.openai.com/v1
```

### 备选：DeepSeek

```dotenv
LLM_PROVIDER=deepseek
LLM_API_KEY=sk-你的key
LLM_MODEL=deepseek-chat
LLM_BASE_URL=https://api.deepseek.com/v1
```

### 验证配置是否生效

```bash
# CLI 快速检查
python -m scripts.test_llm info
python -m scripts.test_llm ping

# 或 curl
curl -s http://localhost:8000/api/v1/llm/health | python -m json.tool
curl -s -X POST http://localhost:8000/api/v1/llm/test \
     -H "Content-Type: application/json" \
     -d '{"prompt":"请用一句话介绍你自己"}'

# 或直接解析一份示例简历
curl -s -X POST http://localhost:8000/api/v1/resumes/parse-text \
     -H "Content-Type: application/json" \
     -d '{"text":"张三，email: zs@x.com，5 年 Python 后端经验，熟悉 FastAPI、PostgreSQL、Docker。"}' \
     | python -m json.tool
```

## 📂 目录结构

```
resumeAssistantAgent/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI 入口
│   │   ├── api/                 # REST 路由
│   │   ├── core/                # 配置、日志、数据库
│   │   ├── models/              # Pydantic + SQLAlchemy
│   │   ├── services/            # 业务服务层
│   │   ├── agents/              # LangGraph 节点 + prompts
│   │   └── utils/               # helpers + LLM 客户端
│   └── tests/                   # pytest
├── frontend/                    # Streamlit 多页面 UI
├── data/samples/                # 示例简历 & JD
├── scripts/test_llm.py          # LLM 调试脚本
├── docker/                      # Dockerfile
├── docker-compose.yml
├── .env.example
└── docs/                        # 架构 / 规划文档
```

## 🧪 测试

```bash
cd backend
pip install pytest pytest-cov
python -m pytest tests/ -v --cov=app --cov-report=term-missing
```

所有测试在 **无 LLM key** 的环境也能跑通，因为 Parser Agent 有启发式 fallback。

## 🎯 下一步

- 阶段 2：PostgreSQL 接入 + 简历持久化
- 阶段 3：更精细的 prompt 调优 + 结构化 JSON 校验
- 阶段 4：Matcher / Optimizer Agent 接入
- 阶段 5：Streamlit 候选人对比 UI
- 阶段 6：CI/CD + 日志收集 + 指标监控

## 📖 详细文档

- `docs/PROJECT_PLAN.md` —— 项目阶段划分与目标
- `docs/ARCHITECTURE.md` —— 架构设计
- `docs/TECH_STACK.md` —— 技术栈详情
- `docs/AGENT_WORKFLOW.md` —— LangGraph Agent 工作流
- `docs/API_DESIGN.md` —— API 设计

## 📝 License

MIT
