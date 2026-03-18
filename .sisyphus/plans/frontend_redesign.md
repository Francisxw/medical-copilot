# 前端页面重构 - 参考UI设计实现计划

## TL;DR

> **目标**：将当前 Streamlit 前端重构为专业医疗辅助 Agent UI
>
> **参考设计**：三列布局 + 顶部栏 + 左侧窄边导航
>
> **交付**：`frontend/app.py` - 全新界面
>
> **预计工作量**：Medium（约 3-4 小时）

---

## UI 设计分析

### 1. 页面布局结构

```
┌─────────────────────────────────────────────────────────────────────────┐
│  顶部栏 (Top Bar) - 深蓝色 #2C5282                                     │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────┐  ┌──────────────┐ │
│  │ MediAssist   │  │ Dr. Wang     │  │ 患者: Li Ming│  │ 🔔 ⚙️ 📅    │ │
│  │ Agent        │  │ 医生信息      │  │             │  │ 工具图标     │ │
│  └─────────────┘  └──────────────┘  └─────────────┘  └──────────────┘ │
├────┬──────────────────────────────────────────────────────────────────┤
│    │                                                                   │
│ 侧 │  ┌───────────────┐ ┌─────────────────────┐ ┌─────────────────┐ │
│ 边 │  │ Patient       │ │ RAG Clinical         │ │ SOAP Case       │ │
│ 栏  │  │ Profile       │ │ Decision Support    │ │ Record          │ │
│    │  │               │ │                     │ │                 │ │
│ 图 │  │ 患者档案卡片   │ │ AI 问答问询区域      │ │ SOAP 病历草稿   │ │
│ 标  │  │               │ │                     │ │                 │ │
│    │  ├───────────────┤ ├─────────────────────┤ ├─────────────────┤ │
│ 导 │  │ Conversation  │ │ System Suggestions  │ │ Case Quality   │ │
│ 航  │  │ Record        │ │                     │ │ Check          │ │
│    │  │               │ │ 系统建议列表         │ │ 质量检查报告    │ │
│    │  │ 对话记录区域   │ │                     │ │                │ │
│    │  └───────────────┘ └─────────────────────┘ └─────────────────┘ │
│    │                                                                   │
└────┴──────────────────────────────────────────────────────────────────┘
```

### 2. 颜色方案

| 用途 | 颜色 | Hex |
|------|------|-----|
| 顶部栏背景 | 深蓝色 | #2C5282 |
| 侧边栏背景 | 浅灰蓝 | #EDF2F7 |
| 卡片背景 | 白色 | #FFFFFF |
| 主体背景 | 极浅灰 | #F7FAFC |
| 按钮主色 | 品牌蓝 | #3182CE |
| 成功状态 | 绿色 | #38A169 |
| 警告状态 | 橙色 | #DD6B20 |
| 文字主色 | 深灰 | #2D3748 |
| 文字辅色 | 中灰 | #718096 |

### 3. 核心组件

1. **顶部栏** - 应用名称、医生信息、患者信息、日期、工具图标
2. **侧边导航** - 主页、患者、记录、设置、添加、退出
3. **患者档案卡片** - 姓名、年龄、性别、过敏史等
4. **对话记录区域** - 医患对话气泡流
5. **AI 决策支持** - AI 问答输入框、发送按钮
6. **系统建议** - 诊断建议列表
7. ** SOAP 病历** - Subjective/Objective/Assessment/Plan 四部分
8. **病历质量检查** - 质量评分进度条、问题列表

---

## 工作任务

### Task 1: 基础架构搭建

**目标**：创建新的 Streamlit 页面基础架构

**实现内容**：
- 页面配置（标题、图标、布局）
- 自定义 CSS 样式（参考设计颜色）
- 顶部栏组件
- 左侧导航栏

**代码位置**：`frontend/app.py`

```python
# 页面配置
st.set_page_config(
    page_title="MediAssist Agent - 医疗辅助助手",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 顶部栏 HTML
TOP_BAR_HTML = """
<div class="top-bar">
    <div class="app-title">🏥 MediAssist Agent</div>
    <div class="doctor-info">👨‍⚕️ Dr. Wang</div>
    <div class="patient-info">📋 患者: {patient_name}</div>
    <div class="tool-icons">🔔 ⚙️ 📅</div>
</div>
"""

# 侧边栏
SIDEBAR_ITEMS = [
    ("🏠", "主页", "home"),
    ("👤", "患者", "patients"),
    ("📋", "记录", "records"),
    ("⚙️", "设置", "settings"),
    ("➕", "添加", "add"),
    ("🚪", "退出", "exit"),
]
```

### Task 2: 患者档案组件

**目标**：实现患者信息展示卡片

**实现内容**：
- 患者基本信息（姓名、年龄、性别）
- 过敏史展示
- 就诊历史摘要

```python
def render_patient_profile(patient_info: dict):
    """渲染患者档案卡片"""
    with st.container():
        st.markdown("### 👤 患者档案")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"**姓名**: {patient_info.get('name', '未知')}")
            st.markdown(f"**年龄**: {patient_info.get('age', '-')} 岁")
        with col2:
            st.markdown(f"**性别**: {patient_info.get('gender', '未知')}")
            st.markdown(f"**就诊号**: {patient_info.get('patient_id', '-')}")
        
        # 过敏史
        allergies = patient_info.get('allergies', [])
        if allergies:
            st.markdown("**过敏史**: " + ", ".join(allergies))
```

### Task 3: 对话记录组件

**目标**：实现医患对话记录展示

**实现内容**：
- 对话气泡样式
- 医生/患者角色区分
- 时间戳显示

```python
def render_conversation(conversation: list):
    """渲染对话记录"""
    st.markdown("### 💬 对话记录")
    
    for turn in conversation:
        role = turn.get('role', 'patient')
        content = turn.get('content', '')
        
        if role == 'doctor':
            st.markdown(f"""
            <div class="chat-bubble doctor">
                <div class="role-label">👨‍⚕️ 医生</div>
                <div class="content">{content}</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div class="chat-bubble patient">
                <div class="role-label">👤 患者</div>
                <div class="content">{content}</div>
            </div>
            """, unsafe_allow_html=True)
```

### Task 4: AI 决策支持组件

**目标**：实现 AI 问答交互区域

**实现内容**：
- 文本输入框
- 发送按钮
- AI 回复展示

```python
def render_ai_decision_support():
    """渲染 AI 决策支持区域"""
    st.markdown("### 🤖 AI 决策支持")
    
    # AI 问答输入
    query = st.text_area(
        "向 AI 助手提问...",
        height=100,
        placeholder="例如：患者的症状可能是什么疾病？",
        key="ai_query"
    )
    
    col1, col2 = st.columns([1, 5])
    with col1:
        send_btn = st.button("🚀 发送", type="primary")
    with col2:
        clear_btn = st.button("🗑️ 清空")
    
    # AI 回复区域
    if 'ai_response' in st.session_state:
        st.markdown("""
        <div class="ai-response">
            {}
        </div>
        """.format(st.session_state.ai_response), unsafe_allow_html=True)
```

### Task 5: 系统建议组件

**目标**：实现诊断建议列表

**实现内容**：
- 编号列表样式
- 建议类型标签

```python
def render_system_suggestions(suggestions: list):
    """渲染系统建议"""
    st.markdown("### 💡 系统建议")
    
    for i, suggestion in enumerate(suggestions, 1):
        st.markdown(f"""
        <div class="suggestion-item">
            <span class="number">{i}</span>
            <span class="text">{suggestion}</span>
        </div>
        """, unsafe_allow_html=True)
```

### Task 6: SOAP 病历组件

**目标**：实现 SOAP 病历展示

**实现内容**：
- 四部分结构化展示（S/O/A/P）
- 各部分标签样式
- 草稿状态提示

```python
def render_soap_note(emr: dict):
    """渲染 SOAP 病历"""
    st.markdown("### 📋 SOAP 病历")
    
    # 状态标签
    status = emr.get('status', 'drafting')
    status_color = {'drafting': '#DD6B20', 'completed': '#38A169'}.get(status, '#718096')
    st.markdown(f'<span class="status-badge" style="background:{status_color}">{status.upper()}</span>', 
                unsafe_allow_html=True)
    
    # Subjective
    with st.expander("📝 Subjective (主诉)", expanded=True):
        st.markdown(emr.get('subjective', ''))
    
    # Objective
    with st.expander("🔍 Objective (客观检查)", expanded=True):
        st.markdown(emr.get('objective', ''))
    
    # Assessment
    with st.expander("💡 Assessment (评估)", expanded=True):
        st.markdown(emr.get('assessment', ''))
    
    # Plan
    with st.expander("📋 Plan (计划)", expanded=True):
        st.markdown(emr.get('plan', ''))
```

### Task 7: 病历质量检查组件

**目标**：实现病历质量评估展示

**实现内容**：
- 质量评分进度条
- 问题列表（缺失/冲突/警告）

```python
def render_quality_check(qa_report: dict):
    """渲染病历质量检查"""
    st.markdown("### ✅ 病历质量检查")
    
    # 评分进度条
    score = qa_report.get('score', 0)
    st.markdown(f"**质量评分**: {score}/100")
    
    progress_color = '#38A169' if score >= 80 else '#DD6B20' if score >= 60 else '#E53E3E'
    st.markdown(f"""
    <div class="progress-bar">
        <div class="progress-fill" style="width:{score}%;background:{progress_color}"></div>
    </div>
    """, unsafe_allow_html=True)
    
    # 问题列表
    issues = qa_report.get('issues', [])
    for issue in issues:
        severity = issue.get('severity', 'info')
        icon = {'error': '❌', 'warning': '⚠️', 'info': 'ℹ️'}.get(severity, '•')
        st.markdown(f"{icon} **{issue.get('field', '')}**: {issue.get('message', '')}")
```

### Task 8: 集成与测试

**目标**：整合所有组件并测试

**实现内容**：
- 三列布局整合
- 与后端 API 对接
- 示例数据填充

```python
def main():
    """主函数"""
    # 顶部栏
    render_top_bar()
    
    # 侧边栏
    render_sidebar()
    
    # 三列主体内容
    col1, col2, col3 = st.columns([1, 1, 1])
    
    with col1:
        # 患者档案 + 对话记录
        render_patient_profile(patient_info)
        render_conversation(conversation)
    
    with col2:
        # AI 决策支持 + 系统建议
        render_ai_decision_support()
        render_system_suggestions(suggestions)
    
    with col3:
        # SOAP 病历 + 质量检查
        render_soap_note(emr)
        render_quality_check(qa_report)
```

---

## CSS 样式定义

```css
/* 顶部栏 */
.top-bar {
    background: linear-gradient(135deg, #2C5282 0%, #2B6CB0 100%);
    color: white;
    padding: 1rem 2rem;
    display: flex;
    align-items: center;
    justify-content: space-between;
    border-radius: 0 0 12px 12px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}

/* 卡片样式 */
.card {
    background: white;
    border-radius: 12px;
    padding: 1.5rem;
    box-shadow: 0 2px 8px rgba(0,0,0,0.08);
    margin-bottom: 1rem;
}

/* 对话气泡 */
.chat-bubble {
    padding: 0.75rem 1rem;
    border-radius: 12px;
    margin: 0.5rem 0;
    max-width: 85%;
}
.chat-bubble.doctor {
    background: #EBF8FF;
    margin-left: auto;
}
.chat-bubble.patient {
    background: #F7FAFC;
}

/* SOAP 标签 */
.soap-badge {
    display: inline-block;
    padding: 0.25rem 0.75rem;
    border-radius: 6px;
    font-weight: bold;
    font-size: 0.85rem;
}
.soap-badge.S { background: #FED7D7; color: #C53030; }
.soap-badge.O { background: #C6F6D5; color: #276749; }
.soap-badge.A { background: #FEEBC8; color: #C05621; }
.soap-badge.P { background: #BEE3F8; color: #2B6CB0; }

/* 进度条 */
.progress-bar {
    height: 12px;
    background: #E2E8F0;
    border-radius: 6px;
    overflow: hidden;
    margin: 0.5rem 0;
}
.progress-fill {
    height: 100%;
    border-radius: 6px;
    transition: width 0.3s ease;
}

/* 按钮 */
.stButton > button {
    border-radius: 8px;
    font-weight: 500;
    transition: all 0.2s;
}
.stButton > button:hover {
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(0,0,0,0.15);
}
```

---

## 验证方案

### 场景 1: 页面加载

```bash
streamlit run frontend/app.py
```

**预期结果**：
- [ ] 顶部栏显示深蓝色背景，应用名称
- [ ] 左侧导航栏显示图标
- [ ] 主体区域显示三列布局
- [ ] 各个卡片正确渲染

### 场景 2: 对话功能

**操作**：添加对话消息

**预期结果**：
- [ ] 对话气泡正确显示
- [ ] 医生/患者角色区分明显

### 场景 3: API 对接

**操作**：调用后端 API 生成病历

**预期结果**：
- [ ] SOAP 病历正确展示
- [ ] 质量评分进度条显示
- [ ] 问题列表正确显示

---

## 文件变更清单

| 文件 | 操作 |
|------|------|
| `frontend/app.py` | **重构** - 全新界面实现 |
| `.env` | **可选** - 添加 `STREAMLIT_THEME` 配置 |

---

## 成功标准

- [ ] 页面布局与参考设计一致（三列 + 顶部栏 + 侧边栏）
- [ ] 颜色方案符合医疗专业风格
- [ ] 所有 7 个功能组件正确实现
- [ ] 与后端 API 正常对接
- [ ] 响应式布局在不同屏幕宽度下正常显示
- [ ] 交互流畅，无明显卡顿
