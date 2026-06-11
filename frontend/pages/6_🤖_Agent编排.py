"""页面 6 - Agent 编排（LangGraph 可视化）。

调用 /agent/analyze 一次跑完 parser → analyzer → matcher/optimizer 完整工作流，
并把每个节点的执行 trace（耗时、输出、错误）可视化出来。这是本项目的技术亮点页。
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from components.api_client import api
from components.resume_selector import resume_selector

st.set_page_config(page_title="🤖 Agent 编排", page_icon="🤖", layout="wide")

st.header("🤖 Agent 编排（LangGraph）")
st.caption(
    "一次请求驱动多 Agent 工作流：解析 → 分析 → 匹配/优化。"
    "下方展示每个节点的执行轨迹（trace），体现 Agent 的可观测性。"
)

col1, col2 = st.columns([1, 1])
with col1:
    st.subheader("📄 简历")
    resume_id = resume_selector("agent")
with col2:
    st.subheader("⚙️ 编排选项")
    mode = st.radio(
        "执行模式",
        ["both", "match", "optimize"],
        format_func=lambda m: {
            "both": "both（匹配 + 优化）",
            "match": "match（仅匹配，需 JD）",
            "optimize": "optimize（仅优化）",
        }[m],
        horizontal=False,
    )
    jd = st.text_area("目标岗位 JD（match / both 模式需要）", height=120)
    thread_id = st.text_input("thread_id（可选，复用同一会话会累积 trace）")

can_run = bool(resume_id)
if st.button("🚀 运行 Agent 工作流", type="primary", disabled=not can_run):
    with st.spinner("Agent 工作流执行中（可能串行调用多个 LLM）..."):
        result = api.agent_analyze(
            resume_id=resume_id,
            jd=jd or None,
            mode=mode,
            thread_id=thread_id or None,
        )

    if isinstance(result, dict) and "error" in result:
        st.error(f"❌ 执行失败：{result['error']}")
    elif result:
        st.success(f"✅ 完成 · 模式={result.get('mode')} · thread={result.get('thread_id', '')[:8]}")

        # ---- Trace 时间线 ----
        st.subheader("⏱️ 执行轨迹 (Trace)")
        trace = result.get("trace") or []
        if trace:
            tdf = pd.DataFrame([
                {
                    "节点": t.get("node"),
                    "耗时(ms)": t.get("duration_ms", 0),
                    "输出字段": ", ".join(t.get("output_keys") or []),
                    "错误": t.get("error") or "—",
                }
                for t in trace
            ])
            st.dataframe(tdf, use_container_width=True, hide_index=True)
            st.bar_chart(tdf.set_index("节点")["耗时(ms)"])

        # ---- 分析结果 ----
        st.subheader("📊 分析")
        analysis = result.get("analysis") or {}
        a1, a2, a3 = st.columns(3)
        a1.metric("学历分", analysis.get("education_score", 0))
        a2.metric("经验分", analysis.get("experience_score", 0))
        a3.metric("技能数", len(analysis.get("skills") or []))
        if analysis.get("skills"):
            st.write("**技能**：" + "、".join(analysis["skills"]))
        if analysis.get("highlights"):
            st.write("**亮点**：")
            for h in analysis["highlights"]:
                st.markdown(f"- {h}")
        if analysis.get("weaknesses"):
            st.write("**弱项**：")
            for w in analysis["weaknesses"]:
                st.markdown(f"- {w}")

        # ---- 匹配 ----
        if result.get("match"):
            st.subheader("🎯 匹配")
            m = result["match"]
            st.metric("匹配度", f"{m.get('score', 0):.0f} / 100")
            if m.get("strengths"):
                st.write("**优势**：" + "；".join(m["strengths"]))
            if m.get("gaps"):
                st.write("**差距**：" + "；".join(m["gaps"]))

        # ---- 优化 ----
        if result.get("optimize"):
            st.subheader("✨ 优化建议")
            for i, sug in enumerate(result["optimize"].get("suggestions") or [], 1):
                with st.container(border=True):
                    st.markdown(f"**{i}. 【{sug.get('category', '其他')}】** {sug.get('improved', '')}")
                    st.caption(f"💡 {sug.get('reason', '')}")

        with st.expander("🔍 完整响应 JSON"):
            st.json(result)

if not resume_id:
    st.info("👆 请先选择或上传一份简历。")
