"""
Streamlit演示UI
用于面试时演示Medical Copilot功能
"""

import streamlit as st
import requests
import json
import os
from typing import List, Dict

# 页面配置
st.set_page_config(
    page_title="Medical Copilot - AI病历生成助手", page_icon="🏥", layout="wide"
)

# 配置 - 支持动态端口配置
BACKEND_PORT = os.getenv("BACKEND_PORT", "8000")
API_URL = f"http://localhost:{BACKEND_PORT}"
REQUEST_TIMEOUT = 120  # 增加超时时间到 120 秒（2 分钟）

# 自定义CSS
st.markdown(
    """
<style>
    .main-header {
        font-size: 3rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .success-box {
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        border-radius: 5px;
        padding: 1rem;
        margin: 1rem 0;
    }
    .warning-box {
        background-color: #fff3cd;
        border: 1px solid #ffeaa7;
        border-radius: 5px;
        padding: 1rem;
        margin: 1rem 0;
    }
    .soap-section {
        background-color: #f8f9fa;
        border-left: 4px solid #007bff;
        padding: 1rem;
        margin: 0.5rem 0;
        border-radius: 3px;
    }
</style>
""",
    unsafe_allow_html=True,
)


def init_session_state():
    """初始化会话状态"""
    if "conversation" not in st.session_state:
        st.session_state.conversation = []
    if "emr_result" not in st.session_state:
        st.session_state.emr_result = None
    if "api_connected" not in st.session_state:
        st.session_state.api_connected = False


def check_api_connection() -> bool:
    """检查API连接"""
    try:
        response = requests.get(f"{API_URL}/health", timeout=2)
        return response.status_code == 200
    except:
        return False


def add_message(role: str, content: str):
    """添加消息到对话历史"""
    st.session_state.conversation.append({"role": role, "content": content})


def display_conversation():
    """显示对话历史"""
    if not st.session_state.conversation:
        st.info("暂无对话记录，请开始对话")
        return

    for i, turn in enumerate(st.session_state.conversation):
        role = "👨‍⚕️ 医生" if turn["role"] == "doctor" else "👤 患者"
        with st.chat_message(
            role.split()[0].replace("👨‍⚕️", "doctor").replace("👤", "user")
        ):
            st.markdown(f"**{role}**")
            st.markdown(turn["content"])


def display_soap_note(emr: Dict):
    """显示SOAP病历"""
    st.subheader("📋 生成的SOAP病历")

    col1, col2 = st.columns(2)

    with col1:
        with st.container():
            st.markdown('<div class="soap-section">', unsafe_allow_html=True)
            st.markdown("**📝 Subjective（主诉/现病史）**")
            st.write(emr.get("subjective", "无"))
            st.markdown("</div>", unsafe_allow_html=True)

        with st.container():
            st.markdown('<div class="soap-section">', unsafe_allow_html=True)
            st.markdown("**🔍 Objective（客观检查）**")
            st.write(emr.get("objective", "无"))
            st.markdown("</div>", unsafe_allow_html=True)

    with col2:
        with st.container():
            st.markdown('<div class="soap-section">', unsafe_allow_html=True)
            st.markdown("**💡 Assessment（评估诊断）**")
            st.write(emr.get("assessment", "无"))
            st.markdown("</div>", unsafe_allow_html=True)

        with st.container():
            st.markdown('<div class="soap-section">', unsafe_allow_html=True)
            st.markdown("**📋 Plan（诊疗计划）**")
            st.write(emr.get("plan", "无"))
            st.markdown("</div>", unsafe_allow_html=True)


def display_qa_report(qa_report: Dict):
    """显示质控报告"""
    st.subheader("✅ 质控报告")

    # 评分
    score = qa_report.get("score", 0)
    is_complete = qa_report.get("is_complete", False)

    col1, col2, col3 = st.columns(3)

    with col1:
        if is_complete:
            st.success("✅ 完整性检查: 通过")
        else:
            st.warning("⚠️ 完整性检查: 未通过")

    with col2:
        st.metric("质量评分", f"{score:.1f}/100")

    with col3:
        if score >= 90:
            st.info("等级: 优秀")
        elif score >= 70:
            st.info("等级: 良好")
        elif score >= 60:
            st.warning("等级: 及格")
        else:
            st.error("等级: 需改进")

    # 问题列表
    issues = qa_report.get("issues", [])
    if issues:
        st.write("**发现的问题:**")
        for i, issue in enumerate(issues, 1):
            severity = issue.get("severity", "info")
            emoji = {"error": "❌", "warning": "⚠️", "info": "ℹ️"}.get(severity, "•")

            st.markdown(f"{emoji} **{i}. {issue.get('message', '未知问题')}**")
            st.caption(f"  - 字段: {issue.get('field', 'N/A')}")
            st.caption(f"  - 类型: {issue.get('type', 'N/A')}")
    else:
        st.success("🎉 未发现问题，病历质量良好！")


def main():
    """主函数"""
    # 初始化
    init_session_state()

    # 标题
    st.markdown(
        '<h1 class="main-header">🏥 Medical Copilot</h1>', unsafe_allow_html=True
    )
    st.markdown(
        "<p style='text-align: center; color: #666;'>基于多Agent协作的AI病历生成助手</p>",
        unsafe_allow_html=True,
    )
    st.markdown("---")

    # 检查API连接
    if not st.session_state.api_connected:
        with st.spinner("正在连接API服务..."):
            st.session_state.api_connected = check_api_connection()

    if not st.session_state.api_connected:
        st.error(
            "❌ 无法连接到API服务！请确保后端服务已启动 (uvicorn src.main:app --reload)"
        )
        st.info("启动命令: `uvicorn src.main:app --reload --host 0.0.0.0 --port 8000`")
        return

    st.success("✅ API服务已连接")

    # 侧边栏：患者信息
    with st.sidebar:
        st.header("👤 患者信息")

        patient_age = st.number_input("年龄", min_value=0, max_value=150, value=35)
        patient_gender = st.selectbox("性别", ["男", "女"])

        st.markdown("---")

        st.header("⚙️ 设置")
        auto_generate = st.checkbox("对话后自动生成病历", value=False)

        st.markdown("---")
        st.markdown("### 技术栈")
        st.markdown("""
        - **LangGraph**: 多Agent编排
        - **RAG**: 向量检索
        - **FastAPI**: 后端服务
        - **Chroma**: 向量数据库
        """)

    # 主要内容区
    tab1, tab2 = st.tabs(["💬 对话模式", "📊 结果展示"])

    with tab1:
        st.header("医患对话模拟")

        # 显示对话历史
        display_conversation()

        # 对话输入
        col1, col2 = st.columns([3, 1])

        with col1:
            doctor_input = st.text_input(
                "医生", placeholder="输入医生的话...", key="doctor_input"
            )
            patient_input = st.text_input(
                "患者", placeholder="输入患者的话...", key="patient_input"
            )

        with col2:
            st.write("")  # 占位
            st.write("")  # 占位
            if st.button("发送医生话术", use_container_width=True):
                if doctor_input:
                    add_message("doctor", doctor_input)
                    st.rerun()

            if st.button("发送患者话术", use_container_width=True):
                if patient_input:
                    add_message("patient", patient_input)
                    st.rerun()

        st.markdown("---")

        # 操作按钮
        col1, col2, col3 = st.columns(3)

        with col1:
            if st.button("🧹 清空对话", use_container_width=True):
                st.session_state.conversation = []
                st.session_state.emr_result = None
                st.rerun()

        with col2:
            if st.button("📋 生成病历", use_container_width=True, type="primary"):
                if not st.session_state.conversation:
                    st.warning("请先进行对话！")
                else:
                    # 显示处理进度提示
                    progress_info = st.info(
                        "⏳ 正在生成病历，这可能需要 1-2 分钟，请耐心等待..."
                    )

                    try:
                        request_data = {
                            "conversation": st.session_state.conversation,
                            "patient_info": {
                                "age": patient_age,
                                "gender": patient_gender,
                            },
                        }

                        response = requests.post(
                            f"{API_URL}/api/generate-emr",
                            json=request_data,
                            timeout=REQUEST_TIMEOUT,
                        )

                        # 清除进度提示
                        progress_info.empty()

                        if response.status_code == 200:
                            st.session_state.emr_result = response.json()
                            st.success(
                                "✅ 病历生成成功！请切换到“结果展示”标签查看结果"
                            )
                        else:
                            st.error(f"生成失败: {response.text}")

                    except requests.exceptions.Timeout:
                        progress_info.empty()
                        st.error(
                            f"⏱️ 请求超时（超过 {REQUEST_TIMEOUT} 秒）。后端可能仍在处理，请稍后重试或检查后端日志。"
                        )
                    except requests.exceptions.ConnectionError:
                        progress_info.empty()
                        st.error("❌ 无法连接到 API 服务。请确保后端服务正在运行。")
                    except Exception as e:
                        progress_info.empty()
                        st.error(f"请求失败: {str(e)}")

        with col3:
            if st.button("🎯 示例对话", use_container_width=True):
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

    with tab2:
        if st.session_state.emr_result:
            result = st.session_state.emr_result

            # 会话信息
            st.markdown(f"**会话ID**: `{result.get('session_id', 'N/A')}`")
            st.markdown(f"**生成时间**: {result.get('timestamp', 'N/A')}")
            st.markdown(f"**迭代次数**: {result.get('iteration_count', 0)}")

            st.markdown("---")

            # SOAP病历
            if result.get("final_emr"):
                display_soap_note(result["final_emr"])

            st.markdown("---")

            # 质控报告
            if result.get("qa_report"):
                display_qa_report(result["qa_report"])

            # 下载按钮
            st.markdown("---")
            col1, col2 = st.columns(2)

            with col1:
                if st.button("📥 下载JSON", use_container_width=True):
                    st.download_button(
                        label="点击下载",
                        data=json.dumps(result, ensure_ascii=False, indent=2),
                        file_name=f"emr_{result.get('session_id', 'unknown')}.json",
                        mime="application/json",
                    )

            with col2:
                if st.button("📋 复制到剪贴板", use_container_width=True):
                    # 生成可读的文本格式
                    emr_text = f"""
SOAP病历

Subjective:
{result["final_emr"]["subjective"]}

Objective:
{result["final_emr"]["objective"]}

Assessment:
{result["final_emr"]["assessment"]}

Plan:
{result["final_emr"]["plan"]}
                    """
                    st.code(emr_text, language="text")
        else:
            st.info("请先在对话模式中进行对话并生成病历")


if __name__ == "__main__":
    main()
