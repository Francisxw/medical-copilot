# Medical Copilot - AI病历生成助手

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

基于 **LangGraph** 和 **RAG** 的多Agent医疗文书生成系统，通过医患对话自动生成结构化病历（SOAP格式）并进行智能质控。

## 🎯 项目亮点

- **多Agent协作**：使用LangGraph编排4个专业Agent（对话解析、知识检索、病历生成、质控检查）
- **RAG检索增强**：支持向量检索（OpenRouter）和关键词检索两种模式
- **结构化生成**：输出符合医疗标准的SOAP格式病历
- **智能质控**：自动检测缺项、剂量冲突、禁忌症等潜在问题
- **完整闭环**：支持多轮对话积累信息和病历修改完善
- **灵活配置**：可使用DeepSeek、OpenAI、OpenRouter等多种API

## 🏗️ 系统架构

```
┌─────────────────────────────────────────────────────────────────┐
│                         Medical Copilot                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐   │
│  │ Agent 1  │ -> │ Agent 2  │ -> │ Agent 3  │ -> │ Agent 4  │   │
│  │ 对话解析  │    │ 知识检索  │    │ 病历生成  │    │ 质控检查  │   │
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘   │
│       ↓              ↓              ↓              ↓             │
│  提取医疗信息    关键词检索    生成SOAP      缺项/冲突检测      │
│                                                                   │
├─────────────────────────────────────────────────────────────────┤
│  技术栈: FastAPI + LangGraph + DeepSeek API                      │
└─────────────────────────────────────────────────────────────────┘
```

## 📁 项目结构

```
medical-copilot/
├── data/
│   ├── raw/               # i2b2原始数据
│   ├── processed/         # 处理后的训练数据
│   └── guidelines/        # 临床指南知识库
├── src/
│   ├── agents/            # Agent实现
│   │   ├── dialogue_agent.py      # 对话解析Agent
│   │   ├── retrieval_agent.py     # 知识检索Agent
│   │   ├── generation_agent.py    # 病历生成Agent
│   │   └── qa_agent.py            # 质控检查Agent
│   ├── graph/             # LangGraph工作流
│   │   ├── workflow.py            # 主工作流编排
│   │   └── state.py               # 状态定义
│   ├── rag/               # RAG模块
│   │   ├── retriever.py           # 向量检索器
│   │   └── embeddings.py          # 嵌入生成
│   ├── api/               # FastAPI接口
│   │   └── routes.py               # RESTful路由
│   ├── models/            # 数据模型
│   │   └── schemas.py              # Pydantic模型
│   ├── utils/             # 工具函数
│   └── main.py            # 应用入口
├── frontend/
│   └── app.py             # Streamlit演示UI
├── tests/                 # 单元测试
├── requirements.txt       # 依赖列表
└── README.md             # 本文件
```

## 🚀 快速开始

### 检索模式选择

本项目支持两种检索模式：

| 模式 | 启动速度 | API需求 | 适用场景 |
|------|---------|---------|---------|
| **关键词检索** | ⚡ 秒级 | 仅需DeepSeek | 面试demo（推荐） |
| **向量检索** | 🐢 需1-2分钟 | DeepSeek + OpenRouter | 生产环境 |

### 快速启动（关键词检索，推荐）

#### Windows 用户
```bash
start.bat
```

#### 手动启动
```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置 DeepSeek API
cp .env.example .env
# 编辑 .env，填入: OPENAI_API_KEY=sk-xxx

# 3. 准备数据
python scripts/prepare_data.py

# 4. 启动服务
uvicorn src.main:app --reload
streamlit run frontend/app.py
```

### 向量检索模式（完整功能）

需要 [OpenRouter API](https://openrouter.ai/) 用于 Embedding：

```bash
# 1. 配置 .env
USE_VECTOR_RETRIEVAL=true
EMBEDDING_BASE_URL=https://openrouter.ai/api/v1

# 2. 构建向量索引
python scripts/build_vector_index.py

# 3. 启动服务
start_vector.bat
```

详细配置请查看 [SETUP_GUIDE.md](SETUP_GUIDE.md)

访问：
- API文档：http://localhost:8000/docs
- 演示界面：http://localhost:8501

## 💡 使用示例

### API调用

```python
import requests

response = requests.post(
    "http://localhost:8000/api/generate-emr",
    json={
        "conversation": [
            {"role": "doctor", "content": "患者今天有什么不舒服？"},
            {"role": "patient", "content": "我咳嗽已经一周了，伴有发热，体温38.5度"}
        ],
        "patient_info": {
            "age": 35,
            "gender": "男"
        }
    }
)

print(response.json())
```

### 返回结果

```json
{
    "emr": {
        "subjective": "35岁男性患者，咳嗽1周，伴发热，T 38.5℃",
        "objective": "",
        "assessment": "急性上呼吸道感染可能性大",
        "plan": "1. 完善血常规、胸片检查\n2. 对症治疗"
    },
    "qa_report": {
        "issues": [],
        "warnings": ["建议补充体温测量时间"]
    }
}
```

## 🧪 测试

```bash
# 运行所有测试
pytest tests/

# 运行特定测试
pytest tests/test_agents.py -v

# 查看覆盖率
pytest --cov=src tests/
```

## 📊 性能指标

- **平均响应时间**: 30-60秒（包含多轮质控）
- **病历生成准确率**: 85%+ (基于i2b2测试集)
- **质控检测召回率**: 90%+

> ⚠️ **注意**: 由于包含多轮质控（最多3次），完整处理时间可能需要 1-2 分钟。前端已配置 120 秒超时，可在 `frontend/app.py` 中调整 `REQUEST_TIMEOUT` 参数。

## 🔧 技术细节

### Agent设计

1. **DialogueAgent**: 使用LLM提取对话中的医疗实体（症状、时间、程度）
2. **RetrievalAgent**:
   - **关键词模式**: 基于症状关键词匹配临床指南
   - **向量模式**: 基于语义相似度检索（OpenRouter Embedding + Chroma）
3. **GenerationAgent**: 结合对话内容和指南生成结构化病历
4. **QAAgent**: 基于规则和LLM检查病历完整性和合理性

### RAG实现

- **关键词模式**: 基于规则的关键词匹配（快速、免费）
- **向量模式**: Chroma向量数据库 + OpenRouter Embedding API（高精度）
- **数据源**: 本地临床指南JSON文件
- **灵活切换**: 通过 `USE_VECTOR_RETRIEVAL` 环境变量控制

### LangGraph状态管理

```python
class GraphState(TypedDict):
    conversation: List[Dict]
    extracted_info: Dict
    retrieved_guidelines: List[Dict]
    draft_emr: Dict
    final_emr: Dict
    qa_report: Dict
    iteration_count: int
```

## 🛠️ 开发路线图

- [x] 基础Agent实现
- [x] LangGraph工作流编排
- [x] RAG向量检索
- [x] FastAPI接口
- [x] Streamlit演示UI
- [ ] 支持更多病历类型（手术记录、出院小结）
- [ ] 多轮对话状态优化
- [ ] 病历修改反馈循环
- [ ] 更多质控规则

## 💰 成本说明

使用 DeepSeek API 的成本：

- 输入: ¥1/百万tokens
- 输出: ¥2/百万tokens
- 预计单次病历生成: < ¥0.01

## 📄 许可证

MIT License

## 🤝 贡献

欢迎提交Issue和Pull Request！

---

**注意**: 本项目仅用于演示目的，不可用于真实医疗场景。生成的病历需专业医生审核。

**技术栈**: LangGraph + FastAPI + DeepSeek API + Streamlit
