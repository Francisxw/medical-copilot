# 实时语音医患录入系统 - 实用化修正计划

## TL;DR

> **目标**：为现有 Streamlit + LangGraph 医疗 Copilot 增 Real-time 语音录入能力
>
> **当前状态**：
> - 前端：Streamlit（非 React！）
> - 后端：FastAPI + LangGraph，batch 模式全流程
> - API：`POST /api/generate-emr` 一次性处理
>
> **核心挑战**：Streamlit 原生不支持 WebSocket，需用替代方案

---

## ⚠️ 原计划关键问题诊断

| 问题 | 原计划假设 | 你的实际 | 风险等级 |
|------|-----------|---------|---------|
| **前端框架** | React + TypeScript | **Streamlit** | 🔴 高 |
| **处理模式** | 增量实时处理 | **全量 batch** | 🟡 中 |
| **实时通信** | WebSocket | **无** | 🟡 中 |
| **Checkpoint** | 已有 MemorySaver | **未实现** | 🟡 中 |
| **语音SDK** | 讯飞医疗版 | **未注册** | 🟢 低 |

---

## 🎯 修正后的实用架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        修正后架构                                   │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  【方案A：Streamlit兼容】(推荐，现有前端改动最小)                      │
│  ┌──────────┐    ┌─────────────┐    ┌──────────────────────────┐   │
│  │ 麦克风按钮 │──▶│ 讯飞Web API │──▶│ Streamlit session_state │   │
│  │(JS注入)   │    │ (HTTP轮询)   │    │ 实时更新 conversation   │   │
│  └──────────┘    └─────────────┘    └──────────────────────────┘   │
│                                                                     │
│  【方案B：全新React前端】(长期推荐，功能最强)                         │
│  ┌──────────┐    ┌─────────────┐    ┌──────────────────────────┐   │
│  │ React UI │◀──▶│ FastAPI +   │◀──▶│ LangGraph Workflow     │   │
│  │ WebRTC   │    │ WebSocket   │    │ (增量/全量)            │   │
│  └──────────┘    └─────────────┘    └──────────────────────────┘   │
│                                                                     │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 📋 推荐方案：渐进式两阶段

### Phase 1：快速上线（Streamlit 兼容方案）

**目标**：2小时内完成麦克风录入，不改前端框架

| 步骤 | 时长 | 操作 |
|------|------|------|
| 1.1 | 10min | 申请讯飞账号 + 获取 API Key |
| 1.2 | 20min | 在 `frontend/app.py` 注入麦克风按钮（HTML+JS） |
| 1.3 | 30min | 接入讯飞实时转写 API（HTTP 轮询方案） |
| 1.4 | 30min | 手动编辑对话气泡（contentEditable） |
| 1.5 | 20min | 集成"生成病历"按钮（复用现有API） |

**Checkpoint**：说一句"胸痛2天"，文字实时上屏 → 可编辑 → 点击生成 → SOAP 出来

**代码位置**：`frontend/app.py`（已重构的中文界面）

---

### Phase 2：增量工作流（可选进阶）

**目标**：支持增量触发 + Checkpoint 恢复

| 步骤 | 时长 | 操作 |
|------|------|------|
| 2.1 | 20min | 安装 `langgraph-checkpoint` |
| 2.2 | 40min | 修改 `MedicalCopilotWorkflow` 支持 `thread_id` |
| 2.3 | 30min | 新增 `POST /api/copilot/incremental` 端点 |
| 2.4 | 30min | 前端轮询增量结果 |

---

### Phase 3：React 重构（长期方案）

**目标**：专业级实时语音 + 流式输出

| 步骤 | 时长 | 操作 |
|------|------|------|
| 3.1 | 60min | 搭建 React + TypeScript 项目 |
| 3.2 | 60min | 实现讯飞 WebSocket 实时转写 |
| 3.3 | 60min | 后端加 WebSocket 支持 |
| 3.4 | 60min | LangGraph 流式输出集成 |

---

## 🔧 Phase 1 详细实现（立即可执行）

### 1.1 讯飞账号准备

```bash
# 所需信息
- AppID: 
- APIKey: 
- APISecret:
- 医疗版服务：wss://rtasr.xfyun.cn/v1/ws (pd=medical)
```

### 1.2 Streamlit 麦克风注入

在 `frontend/app.py` 的对话输入区后添加：

```python
# === Phase 1: 语音录入模块 ===
st.markdown("""
<div id="voice-panel" style="margin: 16px 0;">
    <button id="record-btn" style="
        background: linear-gradient(135deg, #2E5A88 0%, #4A90E2 100%);
        color: white; border: none; padding: 12px 24px;
        border-radius: 8px; font-size: 16px; cursor: pointer;
        display: flex; align-items: center; gap: 8px;
    ">
        <span id="mic-icon">🎤</span>
        <span id="btn-text">开始语音录入</span>
    </button>
    <div id="voice-status" style="margin-top: 8px; color: #666; font-size: 14px;"></div>
</div>

<script>
// 讯飞鉴权（需后端生成签名）
const XFYUN_APPID = 'YOUR_APPID';
const XFYUN_APIKEY = 'YOUR_APIKEY';

// 签名生成函数（需后端提供）
async function getSignature(ts) {
    const response = await fetch('/api/voice/signature?ts=' + ts);
    return await response.json();
}

let ws = null;
let isRecording = false;

document.getElementById('record-btn').addEventListener('click', async function() {
    if (!isRecording) {
        // 开始录音
        const ts = Math.floor(Date.now() / 1000);
        const {signa} = await getSignature(ts);
        
        const wsUrl = `wss://rtasr.xfyun.cn/v1/ws?appid=${XFYUN_APPID}&ts=${ts}&signa=${signa}&pd=medical`;
        ws = new WebSocket(wsUrl);
        
        ws.onopen = () => {
            isRecording = true;
            document.getElementById('mic-icon').textContent = '⏹️';
            document.getElementById('btn-text').textContent = '停止录音';
            document.getElementById('voice-status').textContent = '🎙️ 正在录音...';
            
            // 发送音频（需MediaRecorder）
            startAudioCapture(ws);
        };
        
        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            if (data.action === 'result') {
                const text = data.data;
                // 通过 Streamlit 事件机制回传
                window.parent.postMessage({
                    type: 'streamlit:setComponentValue',
                    value: text
                }, '*');
            }
        };
    } else {
        // 停止录音
        if (ws) ws.close();
        isRecording = false;
        document.getElementById('mic-icon').textContent = '🎤';
        document.getElementById('btn-text').textContent = '开始语音录入';
        document.getElementById('voice-status').textContent = '';
    }
});

function startAudioCapture(ws) {
    navigator.mediaDevices.getUserMedia({audio: true})
        .then(stream => {
            const recorder = new MediaRecorder(stream);
            recorder.ondataavailable = e => {
                if (e.data.size > 0 && ws.readyState === 1) {
                    ws.send(e.data);
                }
            };
            recorder.start(200);
        });
}
</script>
""", unsafe_allow_html=True)
```

### 1.3 后端签名服务（FastAPI）

新增 `src/api/voice.py`：

```python
import hmac
import hashlib
import base64
import time
from fastapi import APIRouter

router = APIRouter()

@router.get("/api/voice/signature")
async def get_voice_signature(ts: int):
    """生成讯飞鉴权签名"""
    api_secret = os.getenv("XFYUN_API_SECRET")
    
    # 鉴权签名计算
    signature_origin = f"host: rtasr.xfyun.cn\ndate: {ts}\nGET /v1/ws"
    signature_sha = hmac.new(
        api_secret.encode('utf-8'),
        signature_origin.encode('utf-8'),
        digestmod=hashlib.sha1
    ).digest()
    signa = base64.b64encode(signature_sha).decode('utf-8')
    
    return {"signa": signa}
```

---

## ✅ 修正计划核对清单

- [ ] 确认使用 **Streamlit 兼容方案**（Phase 1）
- [ ] 讯飞账号 + API Key 已获取
- [ ] 后端签名接口 `/api/voice/signature` 已实现
- [ ] 前端麦克风按钮 + WebSocket 逻辑已注入
- [ ] 对话手动编辑功能保留（现有 `conversation` 数组）
- [ ] "生成病历"按钮复用现有 `/api/generate-emr`

---

## 🛡️ 风险提示

1. **Streamlit + WebSocket 局限**：浏览器兼容性可能有问题，建议先用 HTTP 轮询
2. **讯飞医疗版**：需要企业认证，个人可能只能用水话版
3. **手动编辑**：当前对话气泡是 HTML 渲染，需确保编辑后能写回 `conversation` 状态

---

## 📦 交付文件

| 文件 | 操作 |
|------|------|
| `frontend/app.py` | 添加语音模块 HTML+JS |
| `src/api/voice.py` | 新建签名服务 |
| `src/main.py` | 注册 voice 路由 |

---

## 🎯 下一步

**确认请回复**：
1. 你想先尝试 Phase 1（Streamlit 快速方案）还是直接跳到 Phase 3（React 重构）？
2. 讯飞账号是否已准备好？

确认后我立刻给出 **Phase 1 完整代码**（复制粘贴即用）。
