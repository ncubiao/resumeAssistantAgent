"""简历智能助手 —— 首页（导航）。

简约风：纯文字、网格卡片、侧栏最小化。
"""
import os

import streamlit as st

from components.api_client import api

st.set_page_config(page_title="简历智能助手", page_icon="📋", layout="wide")

# -------- 后端配置（侧栏高级设置） --------
default_url = os.environ.get("BACKEND_API_URL", "http://localhost:8000")
if "backend_url" not in st.session_state:
    st.session_state.backend_url = default_url

with st.sidebar:
    with st.expander("高级设置", expanded=False):
        new_url = st.text_input(
            "后端 API 地址", value=st.session_state.backend_url, label_visibility="collapsed"
        )
        if new_url != st.session_state.backend_url:
            st.session_state.backend_url = new_url
            api.base_url = new_url.rstrip("/")
        if st.button("测试连接", use_container_width=True):
            ok, info = api.health_check()
            if ok:
                st.success(f"后端可用: {info}")
            else:
                st.error(f"后端不可用: {info}")

# -------- 主区域 --------
st.title("简历智能助手")
st.caption("AI 驱动的简历解析、岗位匹配、优化建议与候选人对比 —— 一站式招聘/求职工具")
st.divider()

# 功能导航卡片（2x3 网格）
col1, col2, col3 = st.columns(3)

with col1:
    st.page_link("pages/1_简历解析.py", label="简历解析", use_container_width=True)
    st.caption("上传简历文件，自动结构化解析姓名、技能、工作经历")
    st.page_link("pages/4_候选人对比.py", label="候选人对比", use_container_width=True)
    st.caption("批量上传简历与一份 JD，为候选人打分并排序")

with col2:
    st.page_link("pages/2_岗位匹配.py", label="岗位匹配", use_container_width=True)
    st.caption("评估简历与岗位描述的匹配度，输出优势与差距")
    st.page_link("pages/5_智能助手.py", label="智能助手", use_container_width=True)
    st.caption("多轮对话 Agent，自动调用工具、记住你的画像")

with col3:
    st.page_link("pages/3_简历优化.py", label="简历优化", use_container_width=True)
    st.caption("生成针对性优化建议，或对单个段落进行润色重写")
    st.page_link("pages/6_Agent编排.py", label="Agent 编排", use_container_width=True)
    st.caption("LangGraph 多步编排演示，展示 Agent 决策过程")
