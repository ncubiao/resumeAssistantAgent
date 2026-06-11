"""页面 4 - 候选人对比。

上传多份简历 + 一份 JD，批量匹配并按分数排序（招聘视角）。
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from components.api_client import api

st.set_page_config(page_title="📊 候选人对比", page_icon="📊", layout="wide")

st.header("📊 候选人对比")
st.caption("上传多份简历与一份 JD，系统为候选人打分并排序。也可勾选已有简历参与对比。")

jd = st.text_area("岗位描述 (JD)", height=150, placeholder="粘贴目标岗位 JD...")

st.subheader("候选人来源")
col1, col2 = st.columns(2)

with col1:
    st.markdown("**上传新简历（可多选）**")
    uploaded_files = st.file_uploader(
        "上传简历",
        type=["pdf", "docx", "doc", "txt", "md", "png", "jpg", "jpeg", "webp"],
        accept_multiple_files=True,
        label_visibility="collapsed",
    )

with col2:
    st.markdown("**或勾选已有简历**")
    existing = api.list_resumes()
    existing_map = {
        f"{r.get('name') or '(未命名)'} · {str(r.get('id'))[:8]}": str(r.get("id"))
        for r in existing
    }
    picked = st.multiselect("已有简历", list(existing_map.keys()), label_visibility="collapsed")

can_run = bool(jd and jd.strip()) and (bool(uploaded_files) or bool(picked))
if st.button("🚀 批量匹配并排序", type="primary", disabled=not can_run):
    resume_ids: list[str] = []
    id_to_label: dict[str, str] = {}

    # 1. 上传的文件先落库拿 id
    if uploaded_files:
        with st.spinner("正在解析上传的简历..."):
            for f in uploaded_files:
                res = api.upload_resume(f.read(), f.name)
                if isinstance(res, dict) and res.get("id"):
                    rid = str(res["id"])
                    resume_ids.append(rid)
                    id_to_label[rid] = res.get("name") or f.name

    # 2. 已有勾选
    for label in picked:
        rid = existing_map[label]
        resume_ids.append(rid)
        id_to_label[rid] = label

    if not resume_ids:
        st.error("没有有效的简历可对比。")
    else:
        with st.spinner(f"AI 正在对比 {len(resume_ids)} 位候选人..."):
            result = api.match_batch(resume_ids, jd)

        if isinstance(result, dict) and "error" in result:
            st.error(f"❌ 批量匹配失败：{result['error']}")
        elif result:
            rows = []
            for r in result.get("results") or []:
                rid = r.get("resume_id")
                rows.append({
                    "候选人": id_to_label.get(rid, str(rid)[:8]),
                    "匹配度": r.get("overall_score", 0),
                    "优势数": len(r.get("strengths") or []),
                    "差距数": len(r.get("gaps") or []),
                })
            if rows:
                df = pd.DataFrame(rows)
                st.subheader("🏆 排名")
                st.dataframe(df, use_container_width=True, hide_index=True)
                st.bar_chart(df.set_index("候选人")["匹配度"])

                with st.expander("🔍 完整结果"):
                    st.json(result)
            else:
                st.info("无匹配结果。")
