"""页面 4 - 候选人对比。

多候选人对比排序，招聘视角。
"""
from __future__ import annotations

import streamlit as st

st.set_page_config(page_title="📊 候选人对比", page_icon="📊", layout="wide")

st.header("📊 候选人对比")
st.caption("上传多份简历与一份 JD，系统将为候选人打分并排序列出。")

jd = st.text_area("岗位描述 (JD)", height=150)
resumes = st.file_uploader("上传简历", type=["pdf", "docx", "doc", "txt"], accept_multiple_files=True)

if st.button("🚀 批量匹配并排序", type="primary"):
    st.info("🔧 多候选人对比功能在阶段 4（Matcher Agent + 向量检索）实现。")
