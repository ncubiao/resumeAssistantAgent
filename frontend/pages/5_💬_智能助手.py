"""智能助手聊天页：用户上传文件 + 多轮对话，Agent 自动调用工具。"""
from __future__ import annotations

import json
import os

import streamlit as st

from components.api_client import api

st.set_page_config(page_title="智能助手 | 简历小助手", page_icon="💬", layout="wide")

# -------- 会话 / 用户 状态（阶段 7：记忆） --------
# user_id 本期简单处理：进入页面时生成一个稳定 id（未来换登录态）。
if "user_id" not in st.session_state:
    import uuid as _uuid

    st.session_state.user_id = "u-" + _uuid.uuid4().hex[:8]
if "session_id" not in st.session_state:
    st.session_state.session_id = None  # None=新会话，发首条消息后由后端返回
if "messages" not in st.session_state:
    st.session_state.messages = []


def _load_conversation(conv_id: str) -> None:
    """从后端加载一个历史会话，恢复到当前聊天窗口。"""
    detail = api.get_conversation(conv_id)
    if not detail or (isinstance(detail, dict) and detail.get("error")):
        st.error("加载会话失败")
        return
    st.session_state.session_id = detail["id"]
    st.session_state.messages = [
        {"role": m["role"], "content": m["content"], "tool_calls": m.get("tool_calls", [])}
        for m in detail.get("messages", [])
    ]


# 后端地址
default_url = os.environ.get("BACKEND_API_URL", "http://localhost:8000")
with st.sidebar:
    st.subheader("⚙️ 后端配置")
    backend_url = st.text_input("Backend API URL", value=default_url)
    api.base_url = backend_url.rstrip("/")

    if st.button("🔌 检查后端连接", use_container_width=True):
        with st.spinner("Ping 中..."):
            ok, info = api.health_check()
            if ok:
                st.success(f"✅ 后端可用: {info}")
            else:
                st.error(f"❌ 后端不可用: {info}")

    st.divider()
    st.subheader("🗂️ 历史会话")
    st.caption(f"用户: `{st.session_state.user_id}`")
    if st.button("➕ 新会话", use_container_width=True):
        st.session_state.session_id = None
        st.session_state.messages = []
        st.rerun()

    convs = api.list_conversations(st.session_state.user_id)
    if convs:
        for c in convs[:20]:
            label = (c.get("title") or "未命名")[:22]
            is_current = c["id"] == st.session_state.session_id
            prefix = "🟢 " if is_current else "💬 "
            if st.button(f"{prefix}{label}", key=f"conv_{c['id']}", use_container_width=True):
                _load_conversation(c["id"])
                st.rerun()
    else:
        st.caption("（暂无历史会话）")

    st.divider()
    st.subheader("🧠 Agent 记住的关于你")
    memories = api.get_memories(st.session_state.user_id)
    if memories:
        for m in memories[:15]:
            st.caption(f"• [{m.get('kind', 'fact')}] {m.get('content', '')}")
    else:
        st.caption("（还没有长期记忆，多聊几句 Agent 会记住你的画像）")

    st.divider()
    st.caption("💡 使用提示")
    st.caption("1. 先上传简历/JD，或直接提问")
    st.caption("2. 对话自动落库，刷新/重启不丢")
    st.caption("3. Agent 会记住你的画像，跨会话召回")


st.title("💬 简历智能助手")
st.caption("上传简历或岗位描述，用自然语言和 AI 对话：解析、匹配、优化，一次搞定。")

# -------- 身份选择（招聘方 vs 求职者） --------
# 同一套工具，两种系统提示词与视角：招聘方关注"候选人怎么样"，求职者关注"我怎么改进"。
ROLE_LABELS = {
    "recruiter": "🧑‍💼 招聘方（HR / 猎头 / 招聘经理）",
    "candidate": "🧑‍🎓 求职者",
}

if "user_role" not in st.session_state:
    st.session_state.user_role = "recruiter"

selected_label = st.radio(
    "你的身份",
    list(ROLE_LABELS.values()),
    index=list(ROLE_LABELS).index(st.session_state.user_role),
    horizontal=True,
    key="role_radio",
    help="切换身份会改变 Agent 的视角与回答风格。切换后建议清空对话以避免上下文混淆。",
)
new_role = next(k for k, v in ROLE_LABELS.items() if v == selected_label)
if new_role != st.session_state.user_role:
    st.session_state.user_role = new_role
    # 角色切换时提醒清空历史避免上下文错乱
    if st.session_state.get("messages"):
        st.warning("⚠️ 你切换了身份。建议点击下方「清空对话」重新开始，避免上下文与新视角不一致。")

if st.session_state.user_role == "recruiter":
    st.caption("当前视角：**招聘方**。Agent 会以专业、客观的口吻评价候选人。")
    chat_placeholder = "例如：『帮我看看这位候选人是否适合 Python 后端岗位』"
else:
    st.caption("当前视角：**求职者**。Agent 会站在你的角度提供贴心建议。")
    chat_placeholder = "例如：『帮我看看我的简历适合什么岗位、有哪些可以改进』"

# -------- 上传区 --------
with st.expander("📎 上传文件（可选）", expanded=True):
    col1, col2 = st.columns(2)
    with col1:
        resume_uploaded = st.file_uploader(
            "上传简历（PDF / Word / TXT / MD / 图片 PNG JPG WEBP）",
            type=["pdf", "docx", "doc", "txt", "md", "png", "jpg", "jpeg", "webp", "bmp", "gif", "tif", "tiff"],
            accept_multiple_files=False,
            key="resume_upload",
        )
    with col2:
        jd_uploaded = st.file_uploader(
            "上传岗位描述 JD（PDF / Word / TXT / MD / 图片 PNG JPG WEBP）",
            type=["pdf", "docx", "doc", "txt", "md", "png", "jpg", "jpeg", "webp", "bmp", "gif", "tif", "tiff"],
            accept_multiple_files=False,
            key="jd_upload",
        )

    if resume_uploaded is not None:
        st.success(f"✅ 已准备简历: {resume_uploaded.name}")
    if jd_uploaded is not None:
        st.success(f"✅ 已准备 JD: {jd_uploaded.name}")


# -------- 聊天消息状态 --------
# （user_id / session_id / messages 已在顶部初始化）

if st.button("🧹 清空对话（开新会话）", type="secondary"):
    st.session_state.messages = []
    st.session_state.session_id = None
    st.rerun()

# 渲染已有消息
for msg in st.session_state.messages:
    role = msg["role"]
    with st.chat_message(role):
        st.markdown(msg["content"])
        # 若是 assistant 且带有 tool_calls，再把工具过程折叠展示
        for tc in msg.get("tool_calls", []):
            with st.expander(f"🛠️ 调用了工具：{tc.get('tool_name')}"):
                st.markdown("**输入参数：**")
                try:
                    parsed = json.loads(tc.get("tool_input", "{}"))
                    # 长文本截断显示
                    for k, v in parsed.items():
                        val = str(v)
                        if len(val) > 300:
                            val = val[:300] + "..."
                        st.write(f"- `{k}`: {val}")
                except Exception:
                    st.code(tc.get("tool_input", ""))
                st.markdown("**返回结果（节选）：**")
                out = tc.get("tool_output") or tc.get("truncated_output") or ""
                st.code(out[:2000], language="json")

# 用户输入
if user_input := st.chat_input(chat_placeholder):
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    # 准备发送给后端
    resume_bytes = None
    resume_name = None
    if resume_uploaded is not None:
        resume_bytes = resume_uploaded.read()
        resume_name = resume_uploaded.name

    jd_bytes = None
    jd_name = None
    if jd_uploaded is not None:
        jd_bytes = jd_uploaded.read()
        jd_name = jd_uploaded.name

    # 只保留最近 10 条历史，避免 prompt 过长
    history = [
        {"role": m["role"], "content": m["content"]} for m in st.session_state.messages[-10:-1]
    ]

    with st.chat_message("assistant"):
        with st.spinner("Agent 正在思考并调用工具..."):
            result = api.chat(
                message=user_input,
                resume_file=resume_bytes,
                resume_filename=resume_name,
                jd_file=jd_bytes,
                jd_filename=jd_name,
                history=history,
                user_role=st.session_state.user_role,
                user_id=st.session_state.user_id,
                session_id=st.session_state.session_id,
            )

        if result is None or isinstance(result, dict) and result.get("error"):
            msg = result.get("error", "调用失败，请检查后端是否启动。") if isinstance(result, dict) else "调用失败"
            st.error(msg)
            st.session_state.messages.append({"role": "assistant", "content": f"⚠️ {msg}"})
        else:
            # 记住后端返回的 session_id（首条消息后会话才建立）
            if result.get("session_id"):
                st.session_state.session_id = result["session_id"]

            answer = result.get("answer", "") or "(空回答)"
            tool_calls = result.get("tool_calls", []) or []
            used_tools = result.get("used_tools", False)
            recalled = result.get("recalled_memories") or []

            st.markdown(answer)

            if recalled:
                with st.expander(f"🧠 召回了 {len(recalled)} 条关于你的记忆"):
                    for m in recalled:
                        st.caption(f"• {m}")

            if used_tools and tool_calls:
                for tc in tool_calls:
                    with st.expander(f"🛠️ 调用了工具：{tc.get('tool_name')}"):
                        st.markdown("**输入参数：**")
                        try:
                            parsed = json.loads(tc.get("tool_input", "{}"))
                            for k, v in parsed.items():
                                val = str(v)
                                if len(val) > 300:
                                    val = val[:300] + "..."
                                st.write(f"- `{k}`: {val}")
                        except Exception:
                            st.code(tc.get("tool_input", ""))
                        st.markdown("**返回结果（节选）：**")
                        out = tc.get("tool_output") or tc.get("truncated_output") or ""
                        st.code(out[:2000], language="json")

            # 写入会话状态
            assistant_msg = {"role": "assistant", "content": answer, "tool_calls": tool_calls}
            st.session_state.messages.append(assistant_msg)
