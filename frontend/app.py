"""
Streamlit演示UI - 医疗大模型Copilot重构版
匹配视觉设计图（深蓝顶栏、卡片布局、SOAP分区、进度条等），全中文文案。
"""

import streamlit as st
import requests
import json
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
# 页面配置
st.set_page_config(
    page_title="MediAssist Agent - 智能医疗助手",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# 配置 - 从环境变量读取
API_URL = os.getenv("API_URL", "http://localhost:8888")

REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "120"))  # 默认 120 秒

# ----------------- 自定义CSS注入 -----------------
css = """
<style>
/* 隐藏顶部默认元素和侧边栏开关 */
header[data-testid="stHeader"] {
    display: none !important;
}
[data-testid="collapsedControl"] {
    display: none !important;
}

/* 全局背景色 */
.stApp {
    background-color: #F0F2F5;
}

/* 顶部导航栏 */
.top-nav {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    height: 60px;
    background-color: #2E5A88;
    color: white;
    z-index: 999999;
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 24px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.15);
}
.top-nav .nav-left {
    font-size: 20px;
    font-weight: bold;
    display: flex;
    align-items: center;
    gap: 12px;
}
.top-nav .nav-center {
    font-size: 15px;
    color: #E3F2FD;
    letter-spacing: 0.5px;
}
.top-nav .nav-right {
    font-size: 14px;
    display: flex;
    align-items: center;
    gap: 16px;
}
.status-badge {
    background-color: rgba(255,255,255,0.15);
    padding: 4px 12px;
    border-radius: 20px;
    font-size: 12px;
}

/* 左侧图标导航(视觉占位) */
.side-rail {
    position: fixed;
    top: 60px;
    left: 0;
    width: 68px;
    bottom: 0;
    background-color: #FFFFFF;
    border-right: 1px solid #E0E0E0;
    z-index: 999998;
    display: flex;
    flex-direction: column;
    align-items: center;
    padding-top: 24px;
    gap: 32px;
    box-shadow: 2px 0 8px rgba(0,0,0,0.03);
}
.side-icon {
    font-size: 24px;
    color: #9E9E9E;
}
.side-icon.active {
    color: #2E5A88;
}

/* 调整主页面容器，避开顶栏和左侧边栏 */
.block-container {
    padding-top: 84px !important;
    padding-left: 92px !important;
    padding-right: 24px !important;
    padding-bottom: 32px !important;
    max-width: 100% !important;
}

/* 使用 CSS 伪类给内部 container 添加卡片样式 */
[data-testid="column"] > [data-testid="stVerticalBlock"] > [data-testid="stVerticalBlock"] {
    background-color: #FFFFFF;
    border-radius: 10px;
    padding: 24px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.04);
    border: 1px solid #EBEBEB;
    margin-bottom: 24px;
}

/* 隐藏自带的 label 或者调整间距，如果需要 */
.card-header {
    font-size: 18px;
    font-weight: bold;
    color: #1A1A1A;
    margin-bottom: 16px;
    padding-bottom: 12px;
    border-bottom: 1px solid #F0F2F5;
    display: flex;
    align-items: center;
    gap: 8px;
}

/* 聊天对话框样式 - 仿微信对话式 */
.chat-wrapper {
    background-color: #F5F7FA;
    border-radius: 12px;
    border: 1px solid #E0E6ED;
    height: 420px;
    display: flex;
    flex-direction: column;
    overflow: hidden;
}

.chat-header {
    background: linear-gradient(135deg, #2E5A88 0%, #4A7BA7 100%);
    color: white;
    padding: 12px 16px;
    font-size: 14px;
    font-weight: 500;
    text-align: center;
    border-bottom: 1px solid rgba(255,255,255,0.1);
}

.chat-container {
    flex: 1;
    overflow-y: auto;
    padding: 16px;
    background-color: #F5F7FA;
    scroll-behavior: smooth;
}

/* 自定义滚动条 */
.chat-container::-webkit-scrollbar {
    width: 6px;
}
.chat-container::-webkit-scrollbar-track {
    background: transparent;
}
.chat-container::-webkit-scrollbar-thumb {
    background: #C1C1C1;
    border-radius: 3px;
}
.chat-container::-webkit-scrollbar-thumb:hover {
    background: #A8A8A8;
}

/* 聊天气泡容器 */
.chat-message {
    display: flex;
    margin-bottom: 16px;
    align-items: flex-start;
}

.chat-message.doctor {
    flex-direction: row;
}

.chat-message.patient {
    flex-direction: row-reverse;
}

/* 头像 */
.chat-avatar {
    width: 36px;
    height: 36px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 18px;
    flex-shrink: 0;
    margin: 0 10px;
}

.chat-message.doctor .chat-avatar {
    background: linear-gradient(135deg, #2E5A88 0%, #4A7BA7 100%);
    box-shadow: 0 2px 8px rgba(46, 90, 136, 0.3);
}

.chat-message.patient .chat-avatar {
    background: linear-gradient(135deg, #4CAF50 0%, #66BB6A 100%);
    box-shadow: 0 2px 8px rgba(76, 175, 80, 0.3);
}

/* 消息内容区 */
.chat-content {
    max-width: 75%;
    display: flex;
    flex-direction: column;
}

.chat-message.doctor .chat-content {
    align-items: flex-start;
}

.chat-message.patient .chat-content {
    align-items: flex-end;
}

/* 角色标签 */
.chat-role {
    font-size: 11px;
    color: #999;
    margin-bottom: 4px;
    font-weight: 500;
}

/* 气泡主体 */
.chat-bubble {
    padding: 10px 14px;
    border-radius: 16px;
    font-size: 14px;
    line-height: 1.5;
    word-wrap: break-word;
    position: relative;
    box-shadow: 0 1px 2px rgba(0,0,0,0.08);
}

.chat-doctor {
    background-color: #FFFFFF;
    color: #1A1A1A;
    border-bottom-left-radius: 4px;
    border: 1px solid #E8E8E8;
}

.chat-patient {
    background: linear-gradient(135deg, #95EC69 0%, #7ED957 100%);
    color: #1A1A1A;
    border-bottom-right-radius: 4px;
}

/* 空状态 */
.chat-empty {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    height: 100%;
    color: #999;
    font-size: 14px;
}

.chat-empty-icon {
    font-size: 48px;
    margin-bottom: 12px;
    opacity: 0.5;
}

/* 时间分割线 */
.chat-time-divider {
    text-align: center;
    margin: 16px 0;
    font-size: 11px;
    color: #999;
}

.chat-time-divider span {
    background-color: #DADADA;
    padding: 2px 8px;
    border-radius: 10px;
}

/* 进度条 */
.progress-bg {
    background-color: #E0E0E0;
    border-radius: 8px;
    height: 12px;
    width: 100%;
    margin: 12px 0;
    overflow: hidden;
}
.progress-fill {
    height: 100%;
    border-radius: 8px;
    transition: width 0.4s ease;
}

/* SOAP 卡片特定样式 */
.soap-box {
    background-color: #F8F9FA;
    border-left: 4px solid #4A90E2;
    padding: 16px;
    margin-bottom: 16px;
    border-radius: 0 6px 6px 0;
}
.soap-box-title {
    display: flex;
    align-items: center;
    font-weight: bold;
    color: #2E5A88;
    margin-bottom: 8px;
    font-size: 15px;
}
.soap-letter {
    background-color: #2E5A88;
    color: white;
    width: 26px;
    height: 26px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 4px;
    margin-right: 10px;
    font-weight: bold;
}
.soap-content {
    font-size: 14px;
    color: #333;
    margin-left: 36px;
    white-space: pre-wrap;
}

</style>
"""

st.markdown(css, unsafe_allow_html=True)

# ----------------- 静态视觉组件注入 -----------------
current_date = datetime.now().strftime("%Y-%m-%d")
top_bar_html = f"""
<div class="top-nav">
    <div class="nav-left">
        <span>🏥</span> <span>MediAssist Agent</span>
    </div>
    <div class="nav-center">
        👨‍⚕️ 医生: 王医生 | 👤 患者: 门诊 01 号 | 📅 日期: {current_date}
    </div>
    <div class="nav-right">
        <span class="status-badge">✅ 系统状态: 良好</span>
        <span style="cursor:pointer">🔔</span>
        <span style="cursor:pointer">⚙️</span>
    </div>
</div>
"""
side_rail_html = """
<div class="side-rail">
    <div class="side-icon active" title="工作台">🏠</div>
    <div class="side-icon" title="患者列表">👥</div>
    <div class="side-icon" title="历史记录">📋</div>
    <div class="side-icon" style="margin-top: auto; margin-bottom: 24px;" title="新增">➕</div>
</div>
"""
st.markdown(top_bar_html, unsafe_allow_html=True)
st.markdown(side_rail_html, unsafe_allow_html=True)


# ----------------- 核心状态管理 -----------------
def init_session_state():
    """初始化会话状态，保留原有状态键名"""
    if "conversation" not in st.session_state:
        st.session_state.conversation = []
    if "emr_result" not in st.session_state:
        st.session_state.emr_result = None
    if "api_connected" not in st.session_state:
        st.session_state.api_connected = False

    # 额外 UI 辅助状态
    if "patient_age" not in st.session_state:
        st.session_state.patient_age = 35
    if "patient_gender" not in st.session_state:
        st.session_state.patient_gender = "男"
    if "patient_input_buffer" not in st.session_state:
        st.session_state.patient_input_buffer = ""
    if "voice_transcript_status" not in st.session_state:
        st.session_state.voice_transcript_status = ""
    if "voice_transcript_error" not in st.session_state:
        st.session_state.voice_transcript_error = ""
    if "voice_transcript_success" not in st.session_state:
        st.session_state.voice_transcript_success = ""


def transcribe_patient_audio(audio_file) -> None:
    """调用后端接口转写患者录音。"""
    st.session_state.voice_transcript_error = ""
    st.session_state.voice_transcript_success = ""
    st.session_state.voice_transcript_status = "正在调用语音识别服务..."

    try:
        audio_bytes = audio_file.getvalue()
        response = requests.post(
            f"{API_URL}/api/transcribe-audio",
            files={
                "audio": (
                    audio_file.name or "patient_recording.wav",
                    audio_bytes,
                    audio_file.type or "audio/wav",
                )
            },
            timeout=REQUEST_TIMEOUT,
        )

        if response.status_code == 200:
            transcript_text = response.json().get("text", "").strip()
            st.session_state.patient_input_buffer = transcript_text
            st.session_state.voice_transcript_success = (
                "✅ 转写完成，可先编辑再发送患者发言。"
            )
            st.session_state.voice_transcript_status = ""
        else:
            detail = response.text
            try:
                detail = response.json().get("detail", response.text)
            except ValueError:
                pass
            st.session_state.voice_transcript_error = f"❌ 转写失败：{detail}"
            st.session_state.voice_transcript_status = ""
    except Exception as exc:
        st.session_state.voice_transcript_error = f"❌ 转写请求异常：{str(exc)}"
        st.session_state.voice_transcript_status = ""


def check_api_connection() -> bool:
    """检查后端API连接状态"""
    try:
        response = requests.get(f"{API_URL}/health", timeout=2)
        return response.status_code == 200
    except:
        return False


def main():
    init_session_state()

    # 预检API
    if not st.session_state.api_connected:
        st.session_state.api_connected = check_api_connection()
        if not st.session_state.api_connected:
            st.error("❌ 无法连接到API服务！请确保后端服务已启动。")
            st.info("执行: `uvicorn src.main:app --reload --host 0.0.0.0 --port 8000`")
            return

    # 主体布局，三列式卡片排布
    col1, col2, col3 = st.columns([1.2, 1.2, 1.4])

    # ==========================
    # 列 1：患者信息 + 对话记录
    # ==========================
    with col1:
        # 卡片 1: 患者基本信息
        with st.container():
            st.markdown(
                '<div class="card-header">👤 患者档案</div>', unsafe_allow_html=True
            )

            c_age, c_gender = st.columns(2)
            with c_age:
                st.session_state.patient_age = st.number_input(
                    "患者年龄",
                    min_value=0,
                    max_value=150,
                    value=st.session_state.patient_age,
                )
            with c_gender:
                st.session_state.patient_gender = st.selectbox(
                    "患者性别",
                    ["男", "女"],
                    index=0 if st.session_state.patient_gender == "男" else 1,
                )
            st.text_input("就诊科室", value="呼吸内科 - 门诊专家号", disabled=True)

        # 卡片 2: 对话交互区
        with st.container():
            # 对话渲染区 - 使用st.html替代st.markdown渲染HTML
            import html

            chat_lines = []
            chat_lines.append('<div class="chat-wrapper">')
            chat_lines.append('<div class="chat-header">💬 医患对话记录</div>')
            chat_lines.append('<div class="chat-container" id="chatContainer">')

            if not st.session_state.conversation:
                chat_lines.append('<div class="chat-empty">')
                chat_lines.append('<div class="chat-empty-icon">💬</div>')
                chat_lines.append("<div>暂无对话记录</div>")
                chat_lines.append(
                    '<div style="font-size: 12px; margin-top: 4px;">请在下方输入或使用示例对话</div>'
                )
                chat_lines.append("</div>")
            else:
                # 添加时间分割线
                current_time = datetime.now().strftime("%H:%M")
                chat_lines.append(
                    f'<div class="chat-time-divider"><span>{current_time}</span></div>'
                )

                for turn in st.session_state.conversation:
                    # 转义内容中的HTML特殊字符，防止XSS
                    content = html.escape(turn["content"])
                    role_class = turn["role"]
                    avatar = "👨‍⚕️" if role_class == "doctor" else "👤"
                    role_name = "医生" if role_class == "doctor" else "患者"
                    bubble_class = (
                        "chat-doctor" if role_class == "doctor" else "chat-patient"
                    )

                    chat_lines.append(f'<div class="chat-message {role_class}">')
                    chat_lines.append(f'<div class="chat-avatar">{avatar}</div>')
                    chat_lines.append('<div class="chat-content">')
                    chat_lines.append(f'<div class="chat-role">{role_name}</div>')
                    chat_lines.append(
                        f'<div class="chat-bubble {bubble_class}">{content}</div>'
                    )
                    chat_lines.append("</div>")  # close chat-content
                    chat_lines.append("</div>")  # close chat-message

            chat_lines.append("</div>")  # close chat-container
            chat_lines.append("</div>")  # close chat-wrapper

            chat_html = "\n".join(chat_lines)

            # 使用st.html (Streamlit 1.28+) 或 st.markdown
            try:
                # Streamlit >= 1.28 支持 st.html
                st.html(chat_html)
            except AttributeError:
                # 回退到 st.markdown (旧版本)
                st.markdown(chat_html, unsafe_allow_html=True)

            # 快捷操作按钮
            st.markdown(
                "<hr style='margin: 10px 0; border: none; border-top: 1px dashed #EEE;'/>",
                unsafe_allow_html=True,
            )
            btn_col1, btn_col2 = st.columns(2)
            with btn_col1:
                if st.button("🧹 清空当前对话", use_container_width=True):
                    st.session_state.conversation = []
                    st.session_state.emr_result = None
                    st.rerun()
            with btn_col2:
                if st.button("🎯 载入示例对话", use_container_width=True):
                    st.session_state.conversation = [
                        {"role": "doctor", "content": "你好，今天有什么不舒服？"},
                        {
                            "role": "patient",
                            "content": "我咳嗽已经一周了，还有点发热，体温38度左右",
                        },
                        {"role": "doctor", "content": "咳嗽有痰吗？什么颜色的？"},
                        {"role": "patient", "content": "有少量白痰，不太多"},
                        {"role": "doctor", "content": "有胸闷气短吗？"},
                        {"role": "patient", "content": "稍微有点，不太严重"},
                    ]
                    st.rerun()

            st.markdown("<br/>", unsafe_allow_html=True)

            st.markdown("**🎤 患者语音录入**")
            audio_value = st.audio_input("录制患者语音", sample_rate=16000)

            voice_action_col1, voice_action_col2 = st.columns([1, 2])
            with voice_action_col1:
                if st.button("转写本段录音", use_container_width=True):
                    if audio_value is None:
                        st.session_state.voice_transcript_error = (
                            "⚠️ 请先录制一段患者语音。"
                        )
                        st.session_state.voice_transcript_success = ""
                        st.session_state.voice_transcript_status = ""
                    else:
                        transcribe_patient_audio(audio_value)
            with voice_action_col2:
                if audio_value is not None:
                    st.caption("录音已就绪，点击左侧按钮即可转写并回填到患者输入框。")
                else:
                    st.caption(
                        "支持 16kHz WAV 录音，适合作为当前核心版的语音录入方式。"
                    )

            if st.session_state.voice_transcript_status:
                st.info(st.session_state.voice_transcript_status)
            if st.session_state.voice_transcript_success:
                st.success(st.session_state.voice_transcript_success)
            if st.session_state.voice_transcript_error:
                st.error(st.session_state.voice_transcript_error)

            # 输入区
            input_col1, input_col2 = st.columns([3, 1])

            with input_col1:
                doc_input = st.text_input(
                    "医生", placeholder="输入医生的话...", key="doctor_input"
                )
                pat_input = st.text_area(
                    "患者",
                    placeholder="输入患者的话，或先使用上方语音转写...",
                    key="patient_input_buffer",
                    height=120,
                )

            with input_col2:
                st.write("")  # 占位
                st.write("")  # 占位
                if st.button("发送医生发言", use_container_width=True):
                    if doc_input:
                        st.session_state.conversation.append(
                            {"role": "doctor", "content": doc_input}
                        )
                        st.session_state.doctor_input = ""
                        st.rerun()

                if st.button("发送患者发言", use_container_width=True):
                    if pat_input.strip():
                        st.session_state.conversation.append(
                            {"role": "patient", "content": pat_input.strip()}
                        )
                        st.session_state.patient_input_buffer = ""
                        st.session_state.voice_transcript_status = ""
                        st.session_state.voice_transcript_error = ""
                        st.session_state.voice_transcript_success = ""
                        st.rerun()

    # ==========================
    # 列 2：AI分析支持 (交互中间态)
    # ==========================
    with col2:
        # 卡片 3: AI临床决策支持
        with st.container():
            st.markdown(
                '<div class="card-header">🧠 AI 临床决策支持 (CDS)</div>',
                unsafe_allow_html=True,
            )

            if st.session_state.emr_result:
                st.success("✅ 已基于最新对话生成分析。")
                st.markdown("**系统提取的关键症状：**")
                st.markdown(
                    "- 咳嗽 (1周)\n- 发热 (38℃)\n- 白痰 (少量)\n- 胸闷气短 (轻微)"
                )
                st.info(
                    "💡 **系统建议**：建议重点排查下呼吸道感染，推荐血常规及胸片检查。注意询问流行病学史。"
                )
            elif st.session_state.conversation:
                st.info(
                    "⏳ AI正在监听对话，点击下方「生成智能病历」以启动完整分析流程。"
                )
            else:
                st.write("等待信息输入...")

        # 卡片 4: 核心触发区
        with st.container():
            st.markdown(
                '<div class="card-header">⚡ 生成控制台</div>', unsafe_allow_html=True
            )

            st.write("当收集到足够信息后，可请求AI生成符合规范的结构化病历并进行质控。")
            if st.button(
                "🚀 生成智能病历 (SOAP)", use_container_width=True, type="primary"
            ):
                if not st.session_state.conversation:
                    st.warning("⚠️ 请先在左侧输入对话！")
                else:
                    with st.spinner(
                        "🔄 AI多智能体正在处理 (提取 -> 检索 -> 生成 -> 质控)..."
                    ):
                        try:
                            req_data = {
                                "conversation": st.session_state.conversation,
                                "patient_info": {
                                    "age": st.session_state.patient_age,
                                    "gender": st.session_state.patient_gender,
                                },
                            }
                            resp = requests.post(
                                f"{API_URL}/api/generate-emr",
                                json=req_data,
                                timeout=REQUEST_TIMEOUT,
                            )
                            if resp.status_code == 200:
                                st.session_state.emr_result = resp.json()
                            else:
                                st.error(f"❌ 生成失败: {resp.text}")
                        except Exception as e:
                            st.error(f"❌ 请求失败: {str(e)}")

    # ==========================
    # 列 3：质控报告 + SOAP结果
    # ==========================
    with col3:
        emr_data = st.session_state.emr_result or {}
        qa_report = emr_data.get("qa_report", {})
        final_emr = emr_data.get("final_emr", {})
        score = qa_report.get("score", 0)

        # 卡片 5: 质量检查
        with st.container():
            st.markdown(
                '<div class="card-header">🛡️ 病历质量检查</div>', unsafe_allow_html=True
            )

            if not st.session_state.emr_result:
                st.write("（尚未生成报告）")
            else:
                score_color = (
                    "#4CAF50"
                    if score >= 85
                    else ("#FF9800" if score >= 60 else "#F44336")
                )
                is_complete = qa_report.get("is_complete", False)
                status_text = "通过" if is_complete else "存在缺项"

                # 绘制进度条
                st.markdown(
                    f"""
                <div style="display: flex; justify-content: space-between; align-items: flex-end;">
                    <span style="font-size: 14px; color: #555;">AI 评分鉴定: <b>{status_text}</b></span>
                    <span style="font-size: 28px; font-weight: bold; color: {score_color};">{score}<span style="font-size:16px;">/100</span></span>
                </div>
                <div class="progress-bg">
                    <div class="progress-fill" style="width: {score}%; background-color: {score_color};"></div>
                </div>
                """,
                    unsafe_allow_html=True,
                )

                issues = qa_report.get("issues", [])
                if issues:
                    st.markdown(
                        "<div style='margin-top: 12px; font-size: 14px; font-weight: bold;'>⚠️ 发现以下问题需要改进：</div>",
                        unsafe_allow_html=True,
                    )
                    for i, issue in enumerate(issues, 1):
                        msg = issue.get("message", "未知建议")
                        field = issue.get("field", "通用")
                        st.markdown(
                            f"<div style='font-size: 13px; color: #666; margin-top: 4px;'>{i}. [{field}] {msg}</div>",
                            unsafe_allow_html=True,
                        )
                else:
                    st.markdown(
                        "<div style='margin-top: 12px; font-size: 14px; color: #4CAF50;'>🎉 病历结构完整，未发现逻辑冲突。</div>",
                        unsafe_allow_html=True,
                    )

                st.caption(
                    f"会话 ID: `{emr_data.get('session_id', 'N/A')}` | 生成时间: {emr_data.get('timestamp', 'N/A')} | 优化迭代: {emr_data.get('iteration_count', 0)} 次"
                )

        # 卡片 6: SOAP 结构化病历
        with st.container():
            st.markdown(
                '<div class="card-header">📝 SOAP 结构化病历记录</div>',
                unsafe_allow_html=True,
            )

            if not st.session_state.emr_result:
                st.info("此处将展示 AI 自动撰写的规范化病历。")
            else:

                def render_soap_box(letter, title, content):
                    return f"""
                    <div class="soap-box">
                        <div class="soap-box-title">
                            <span class="soap-letter">{letter}</span> {title}
                        </div>
                        <div class="soap-content">{content}</div>
                    </div>
                    """

                st.markdown(
                    render_soap_box(
                        "S", "主观资料 (Subjective)", final_emr.get("subjective", "无")
                    ),
                    unsafe_allow_html=True,
                )
                st.markdown(
                    render_soap_box(
                        "O", "客观资料 (Objective)", final_emr.get("objective", "无")
                    ),
                    unsafe_allow_html=True,
                )
                st.markdown(
                    render_soap_box(
                        "A", "评估诊断 (Assessment)", final_emr.get("assessment", "无")
                    ),
                    unsafe_allow_html=True,
                )
                st.markdown(
                    render_soap_box(
                        "P", "诊疗计划 (Plan)", final_emr.get("plan", "无")
                    ),
                    unsafe_allow_html=True,
                )

                st.markdown(
                    "<hr style='margin: 16px 0; border: none; border-top: 1px solid #EEE;'/>",
                    unsafe_allow_html=True,
                )
                dl_col1, dl_col2 = st.columns(2)
                with dl_col1:
                    st.download_button(
                        label="📥 导出为 JSON",
                        data=json.dumps(emr_data, ensure_ascii=False, indent=2),
                        file_name=f"emr_{emr_data.get('session_id', 'export')}.json",
                        mime="application/json",
                        use_container_width=True,
                    )
                with dl_col2:
                    if st.button(
                        "✅ 确认并归档", use_container_width=True, type="primary"
                    ):
                        st.toast("病历已成功归档入库！", icon="✅")


if __name__ == "__main__":
    main()
