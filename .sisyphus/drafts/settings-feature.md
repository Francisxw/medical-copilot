# Draft: 前端设置功能

## 项目概况
- 前端框架: Streamlit (Python)
- 后端: FastAPI + LangGraph + DeepSeek API
- 现有配置方式: .env 文件 + 环境变量

## 已确认信息
1. 前端使用 Streamlit，单文件 app.py (750行)
2. 顶部导航栏已有 ⚙️ 设置图标 (line 369)，目前是静态占位符
3. API配置目前从环境变量读取 (os.getenv)

## 用户决策
- **配置范围**: API + 功能配置（API配置 + 检索模式选择 + UI偏好设置）
- **存储方式**: 浏览器 localStorage
- **UI交互**: 弹出式模态框

## 待确认细节 (已确认)
1. **API配置**: API Key + 端点URL、模型名称、请求超时时间
2. **检索模式**: 全部支持 (simple, vector, llamagraph, llamaindex)
3. **UI偏好**: 自动清空对话

## 技术实现要点
- 前端：Streamlit + st.dialog (弹出式模态框)
- 存储：localStorage (通过 streamlit-autorefresh 或自定义 JS)
- 设置项持久化：保存时写入 localStorage，加载时读取

## 现有代码参考
- 顶部导航栏 ⚙️ 图标：app.py line 369
- 环境变量读取：app.py line 23-25 (API_URL, REQUEST_TIMEOUT)
- 设置图标当前是静态HTML占位符
