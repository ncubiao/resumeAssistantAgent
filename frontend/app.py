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
        st.caption("上传 PDF/Word，自动结构化提取")
        st.page_link("pages/1_📄_简历解析.py", label="去解析", use_container_width=True)
    with col2:
        st.markdown("### 🎯 岗位匹配")
        st.caption("对比 JD，计算匹配度")
        st.page_link("pages/2_🎯_岗位匹配.py", label="去匹配", use_container_width=True)
    with col3:
        st.markdown("### ✨ 简历优化")
        st.caption("获取简历优化建议与改写")
        st.page_link("pages/3_✨_简历优化.py", label="去优化", use_container_width=True)

    st.divider()
    st.markdown(
        """
    #### 🔖 项目信息

    - **后端**: FastAPI + LangGraph
    - **前端**: Streamlit
    - **数据库**: PostgreSQL + FAISS
    - **阶段**: 1 项目骨架 ✅
    """
    )

    st.info(
        "当前为阶段 1 骨架版本，真正的 LLM 解析 & 优化功能会在后续阶段接入。"
    )


if __name__ == "__main__":
    main()
