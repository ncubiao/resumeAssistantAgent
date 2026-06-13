"""页面 2 - 岗位匹配。"""
from __future__ import annotations

import streamlit as st

from components.api_client import api
from components.resume_selector import resume_selector

st.set_page_config(page_title="岗位匹配", page_icon="📋", layout="wide")

st.title("岗位匹配")
st.caption("评估简历与岗位描述的匹配度，输出优势与差距")

col1, col2 = st.columns([1, 2])
with col1:
    st.subheader("简历")
    resume_id = resume_selector("match")

with col2:
    st.subheader("岗位描述 (JD)")
    jd = st.text_area(
        "JD",
        height=300,
        placeholder="例如：3 年以上 Python 后端开发经验，熟悉 FastAPI / PostgreSQL / Docker...",
        label_visibility="collapsed",
    )

can_run = bool(resume_id) and bool(jd and jd.strip())
if st.button("开始匹配", type="primary", disabled=not can_run, use_container_width=True):
    with st.spinner("匹配中..."):
        result = api.match_single(resume_id, jd)

    if isinstance(result, dict) and "error" in result:
        st.error(f"匹配失败：{result['error']}")
    elif result:
        score = result.get("overall_score", 0)
        st.metric("综合匹配度", f"{score:.0f} / 100")
        st.progress(min(1.0, max(0.0, score / 100)))

        c1, c2 = st.columns(2)
        with c1:
            st.subheader("优势")
            strengths = result.get("strengths") or []
            if strengths:
                for s in strengths:
                    st.markdown(f"- {s}")
            else:
                st.caption("（无）")
        with c2:
            st.subheader("差距")
            gaps = result.get("gaps") or []
            if gaps:
                for g in gaps:
                    st.markdown(f"- {g}")
            else:
                st.caption("（无）")

        with st.expander("完整匹配结果（JSON）", expanded=False):
            st.json(result)
