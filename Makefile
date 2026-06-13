# Makefile - resumeAssistantAgent

.PHONY: help install install-backend install-frontend dev dev-backend dev-frontend \
	test eval eval-report lint typecheck docker-up docker-down docker-build db-init clean format

PYTHON := python3
VENV := .venv

# 默认 target
.DEFAULT_GOAL := help

help: ## 显示帮助信息
	@echo "resumeAssistantAgent - 简历分析 AI Agent 项目"
	@echo "============================================"
	@echo ""
	@echo "可用命令:"
	@awk 'BEGIN {FS = ":.*## "}; /^[a-zA-Z_-]+:.*## / {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

## --- 安装 ---

install: install-backend install-frontend ## 安装所有依赖

install-backend: ## 安装后端依赖
	cd backend && $(PYTHON) -m venv $(VENV) && \
	source $(VENV)/bin/activate && pip install --upgrade pip && \
	pip install -r requirements.txt

install-frontend: ## 安装前端依赖
	cd frontend && pip install -r requirements.txt

## --- 开发 ---

dev: docker-up-dev ## 启动所有服务（需要 docker-compose）

dev-backend: ## 启动后端开发服务器（本地）
	cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

dev-frontend: ## 启动前端开发服务器（本地）
	cd frontend && streamlit run app.py

## --- 测试 & 代码质量 ---

test: ## 运行测试（不含 eval）
	cd backend && pytest -v --cov=app --cov-report=term-missing

eval: ## 运行 Agent 质量评测（需真实 LLM Key）
	cd backend && pytest -m eval -v -s

eval-report: ## 直接打印 eval 详细对比报告（不走 pytest）
	cd backend && python -m eval.runner

lint: ## 运行 ruff 代码检查
	cd backend && ruff check app/ tests/ eval/
	cd frontend && ruff check app.py pages/ components/

format: ## 使用 ruff 格式化
	cd backend && ruff format app/
	cd frontend && ruff format app.py pages/ components/

typecheck: ## 运行 mypy 类型检查
	cd backend && mypy app/

## --- Docker ---

docker-up: ## docker-compose 启动（构建）
	docker-compose up --build

docker-up-dev: ## docker-compose 启动（开发模式，不重建）
	docker-compose up

docker-down: ## docker-compose 停止
	docker-compose down

docker-build: ## 仅构建镜像
	docker-compose build

## --- 数据库 ---

db-init: ## 初始化数据库
	cd backend && $(PYTHON) -m app.core.init_db

## --- 清理 ---

clean: ## 清理缓存文件
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name .pytest_cache -exec rm -rf {} +
	find . -type d -name .ruff_cache -exec rm -rf {} +
	rm -rf backend/.venv frontend/.venv
	rm -rf htmlcov/ .coverage
