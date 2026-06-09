# 技术栈清单 (Tech Stack)

## 1. 核心语言 & 运行时

| 技术 | 版本 | 用途 |
|------|------|------|
| Python | 3.11+ | 主语言，静态类型支持 |
| pip | latest | Python 包管理 |

## 2. Web 框架

| 技术 | 版本 | 用途 |
|------|------|------|
| FastAPI | 0.110+ | 高性能 ASGI Web 框架 |
| Uvicorn | latest | ASGI 服务器 |
| Pydantic | 2.x | 数据校验 |
| Streamlit | 1.32+ | 前端 UI |

## 3. Agent 与 LLM

| 技术 | 版本 | 用途 |
|------|------|------|
| LangGraph | latest | Agent 工作流编排 |
| LangChain | latest | LLM 工具链 |
| langchain-openai | latest | OpenAI 兼容接入 |
| OpenAI API | - | LLM 调用 |

## 4. 数据存储

| 技术 | 版本 | 用途 |
|------|------|------|
| PostgreSQL | 15+ | 关系型数据库 |
| SQLAlchemy | 2.x | ORM |
| psycopg2-binary | latest | PostgreSQL 驱动 |
| FAISS (CPU) | latest | 向量相似度检索 |
| faiss-cpu | latest | Python 绑定 |

## 5. 文件解析

| 技术 | 版本 | 用途 |
|------|------|------|
| PyPDF2 | latest | PDF 文本提取 |
| python-docx | latest | Word 文档解析 |
| pdfplumber | latest | 增强 PDF 解析（排版敏感内容 |

## 6. 工程化与测试

| 技术 | 版本 | 用途 |
|------|------|------|
| pytest | latest | 测试框架 |
| pytest-cov | latest | 覆盖率 |
| ruff | latest | lint 代码规范 |
| mypy | latest | 类型检查 |
| httpx | latest | 异步 HTTP 客户端（测试用） |

## 7. 日志与配置

| 技术 | 版本 | 用途 |
|------|------|------|
| structlog | latest | 结构化日志 |
| python-dotenv | latest | .env 文件加载 |
| pydantic-settings | 2.x | 配置管理 |

## 8. 容器与 DevOps

| 技术 | 版本 | 用途 |
|------|------|------|
| Docker | 20+ | 容器化 |
| Docker Compose | v2 | 本地编排 |
| GitHub Actions | - | CI/CD |

## 9. 数据可视化（Frontend 增强）

| 技术 | 版本 | 用途 |
|------|------|------|
| streamlit-antd-components | latest | Ant Design 组件 |
| pandas | latest | 表格展示 |
| plotly | latest | 图表（雷达图等 |

## 10. 完整依赖示例

### backend/requirements.txt

```
fastapi==0.110.0
uvicorn[standard]==0.29.0
pydantic==2.6.4
pydantic-settings==2.2.1
sqlalchemy==2.0.29
psycopg2-binary==2.9.9
langgraph==0.1.5
langchain==0.1.13
langchain-openai==0.1.1
faiss-cpu==1.8.0
PyPDF2==3.0.1
python-docx==1.1.0
pdfplumber==0.11.0
structlog==24.1.0
python-dotenv==1.0.1
httpx==0.27.0
python-multipart==0.0.9
pytest==8.1.1
pytest-cov==5.0.0
ruff==0.3.4
mypy==1.9.0
```

### frontend/requirements.txt

```
streamlit==1.32.2
streamlit-antd-components==0.4.0
requests==2.31.0
pandas==2.2.1
plotly==5.20.0
python-dotenv==1.0.1
```

## 11. 服务端口规划

| 服务 | 端口 | 说明 |
|------|------|------|
| FastAPI backend | 8000 | 后端 API |
| Streamlit frontend | 8501 | 前端 UI |
| PostgreSQL | 5432 | 数据库（容器内） |

## 12. LLM Provider 支持

- **OpenAI** (默认)
  - `gpt-4o-mini`（解析、结构化提取
- **DeepSeek** (备选)
  - 与 OpenAI 兼容 API 风格
