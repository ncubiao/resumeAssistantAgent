"""Streamlit 前端入口 - 简历分析 AI Agent。

运行方式:
    streamlit run app.py
"""
from __future__ import annotations

import os
from pathlib import Path

import streamlit as st

from components.api_client import api

# 页面配置
st.set_page_config(
    page_title="简历小助手 | Resume Assistant",
    page_icon="📄",
    layout="wide",
)


def main() -> None:
    st.title("📄 简历小助手 - Resume Assistant")
    st.caption(
        "基于 LangGraph + FastAPI + Streamlit 的简历分析 AI Agent"
    )

    # 侧边栏：后端连通性检查
    with st.sidebar:
        st.subheader("⚙️ 后端配置")
        default_url = os.environ.get("BACKEND_API_URL", "http://localhost:8000")
        backend_url = st.text_input("Backend API URL", value=default_url)
        api.base_url = backend_url.rstrip("/")

        if st.button("🔌 检查后端连接", use_container_width=True):
            with st.spinner("Ping 中..."):
                ok, info = api.health_check()
                if ok:
                    st.success(f"✅ 后端可用: " + str(info))
                else:
                    st.error("❌ 后端不可用: " + info)

    st.divider()

    # 首页欢迎卡片
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("### 📥 简历解析")
        st.caption("上传 PDF/Word/图片，自动结构化提取并入库")
        st.page_link("pages/1_📄_简历解析.py", label="去解析", use_container_width=True)
    with col2:
        st.markdown("### 🎯 岗位匹配")
        st.caption("对比 JD，计算匹配度与优势/差距")
        st.page_link("pages/2_🎯_岗位匹配.py", label="去匹配", use_container_width=True)
    with col3:
        st.markdown("### ✨ 简历优化")
        st.caption("获取简历优化建议与段落改写")
        st.page_link("pages/3_✨_简历优化.py", label="去优化", use_container_width=True)

    col4, col5, col6 = st.columns(3)
    with col4:
        st.markdown("### 📊 候选人对比")
        st.caption("多份简历 vs 一份 JD，批量打分排序")
        st.page_link("pages/4_📊_候选人对比.py", label="去对比", use_container_width=True)
    with col5:
        st.markdown("### 💬 智能助手")
        st.caption("多轮对话，自动调用分析工具")
        st.page_link("pages/5_💬_智能助手.py", label="去对话", use_container_width=True)
    with col6:
        st.markdown("### 🤖 Agent 编排")
        st.caption("LangGraph 多 Agent 工作流 + 执行轨迹可视化")
        st.page_link("pages/6_🤖_Agent编排.py", label="去编排", use_container_width=True)

    st.divider()
    st.markdown(
        """
    #### 🔖 项目信息

    - **后端**: FastAPI + LangGraph（多 Agent 编排 + checkpointer）
    - **前端**: Streamlit
    - **数据库**: SQLite/PostgreSQL + FAISS 向量检索
    - **能力**: 简历解析 · 语义检索 · 岗位匹配 · 简历优化 · Agent 编排
    """
    )


if __name__ == "__main__":
    main()
