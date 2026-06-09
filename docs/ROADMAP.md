# 开发路线图 (Roadmap)

> 本文档记录项目的阶段目标与 TODO 清单，便于跟踪与迭代。

## 阶段 1：项目骨架 ✅
- [x] 项目目录结构
- [x] FastAPI + Streamlit 骨架
- [x] Docker 配置
- [x] 规划文档 & 架构文档

## 阶段 2：数据库 & 向量检索
- [ ] PostgreSQL 建表 SQL 脚本
- [ ] SQLAlchemy ORM 模型（Resume / MatchResult）
- [ ] 数据库连接池 & Session 管理
- [ ] FAISS 索引封装（VectorStore 类）
- [ ] 简历 CRUD API
- [ ] 单元测试（database / vector_store）

## 阶段 3：简历解析模块
- [ ] PDF 文件文本提取（PyPDF2 / pdfplumber）
- [ ] Word 文件文本提取（python-docx）
- [ ] LLM 结构化提取（Parser Agent + Pydantic Output Parser）
- [ ] 去重（文件 hash）
- [ ] 缓存（避免重复解析同一份文件）
- [ ] 解析单元测试

## 阶段 4：核心 Agent
- [ ] LangGraph StateGraph 搭建
- [ ] Analyzer Agent（打分 + 亮点/不足）
- [ ] Matcher Agent（JD 匹配）
- [ ] Optimizer Agent（优化建议）
- [ ] 条件路由
- [ ] Prompt 模板调优
- [ ] Agent 集成测试

## 阶段 5：前端 UI
- [ ] 简历上传页面
- [ ] 结构化结果展示
- [ ] JD 匹配页面
- [ ] 候选人对比页面（表格 + 雷达图）
- [ ] 优化建议页面
- [ ] 历史记录页面

## 阶段 6：工程化
- [ ] GitHub Actions CI（lint + test）
- [ ] pytest 覆盖率提升到 >= 60%
- [ ] Docker Compose 一键启动
- [ ] 健康检查接口
- [ ] 结构化日志
- [ ] 示例数据脚本
- [ ] README 使用指南完善

## 后续扩展（可选项）
- [ ] 图片简历 OCR
- [ ] 英文简历支持
- [ ] 面试问题自动生成
- [ ] RAG 知识库（JD 模板、行业标准）
- [ ] Prometheus 监控指标
- [ ] 用户 & 权限系统
