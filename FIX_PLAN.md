# Medical Copilot 完整修复优化计划

> **基于**: 全量源码 9 维度代码审查  
> **创建时间**: 2026-03-30  
> **总问题数**: 42 项  
> **预估总工时**: 8-12 天

---

## 目录

1. [Phase 0: 安全阻断（1-2天）](#phase-0-安全阻断)
2. [Phase 1: 核心功能闭环（2-3天）](#phase-1-核心功能闭环)
3. [Phase 2: 类型系统统一（1-2天）](#phase-2-类型系统统一)
4. [Phase 3: 测试覆盖（2-3天）](#phase-3-测试覆盖)
5. [Phase 4: 架构改善（1-2天）](#phase-4-架构改善)
6. [Phase 5: 性能与细节（1天）](#phase-5-性能与细节)
7. [附录: 问题索引表](#附录-问题索引表)

---

## Phase 0: 安全阻断

> **目标**: 消除所有可被外部利用的安全漏洞  
> **阻断条件**: 未完成不得上线

### P0-1: CORS 配置收紧

**文件**: `src/main.py:77-83`  
**问题**: `allow_origins=["*"]` + `allow_credentials=True` 是 OWASP 明确禁止的组合  
**风险**: 任意网站可发起跨域请求，CSRF 攻击

```python
# === 修改前 ===
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# === 修改后 ===
import os

_allowed = os.getenv("ALLOWED_ORIGINS", "http://localhost:8501")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _allowed.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-Tenant-ID", "X-KB-ID"],
)
```

同步修改: `.env.example` 添加 `ALLOWED_ORIGINS=http://localhost:8501`

---

### P0-2: 全局变量替换为 app.state

**文件**: `src/api/routes.py:36-80`, `src/main.py:34-41`  
**问题**: 5 个 `global` 变量懒加载，无锁保护，竞态条件  
**风险**: 并发请求下可能创建多个服务实例，资源泄漏

```python
# === 修改前 (routes.py) ===
_workflow_instance: "MedicalCopilotWorkflow | None" = None
_asr_service_instance: ASRService | None = None

def get_workflow() -> "MedicalCopilotWorkflow":
    global _workflow_instance
    if _workflow_instance is None:
        raise RuntimeError("工作流未初始化")
    return _workflow_instance

def get_asr_service() -> ASRService:
    global _asr_service_instance
    if _asr_service_instance is None:
        _asr_service_instance = ASRService()
    return _asr_service_instance

# === 修改后 (routes.py) ===
from fastapi import Request

def get_workflow(request: Request) -> MedicalCopilotWorkflow:
    workflow = getattr(request.app.state, "workflow", None)
    if workflow is None:
        raise RuntimeError("工作流未初始化")
    return workflow

def get_asr_service(request: Request) -> ASRService:
    svc = getattr(request.app.state, "asr_service", None)
    if svc is None:
        svc = ASRService()
        request.app.state.asr_service = svc
    return svc

# === 修改后 (main.py lifespan) ===
async def lifespan(app: FastAPI):
    # 启动
    workflow = MedicalCopilotWorkflow(retrieval_mode=settings.retrieval_mode)
    app.state.workflow = workflow
    app.state.asr_service = ASRService()
    app.state.rag_service = RAGService()
    app.state.versioned_rag_service = VersionedTenantRAGService()
    yield
    # 关闭 - 清理资源
```

删除: `routes.py` 中所有 `global` 变量和 `set_workflow_instance` 函数

---

### P0-3: 文件上传大小预检

**文件**: `src/api/routes.py:156,205,253`  
**问题**: `await audio.read()` 全部读入内存后才校验大小  
**风险**: 大文件导致 OOM

```python
# === 修改后 ===
MAX_UPLOAD_BYTES = 10 * 1024 * 1024

@router.post("/api/transcribe-audio")
async def transcribe_audio(
    request: Request,
    audio: UploadFile = File(...),
):
    # 先检查 Content-Length header
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="文件过大，超过 10MB 限制")
    
    audio_bytes = await audio.read()
    if len(audio_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="文件过大，超过 10MB 限制")
```

---

### P0-4: API Key 校验增强

**文件**: `src/config.py:214-215`  
**问题**: 仅检查占位符字符串，不验证格式  
**风险**: 错误的 key 导致运行时才报错

```python
# === 修改后 ===
def validate(self) -> List[str]:
    warnings = []
    if not self.openai_api_key:
        warnings.append("OPENAI_API_KEY 未设置")
    elif len(self.openai_api_key) < 20:
        warnings.append("OPENAI_API_KEY 格式异常（长度不足）")
    elif self.openai_api_key.startswith("sk-") and len(self.openai_api_key) < 40:
        warnings.append("OPENAI_API_KEY 格式异常（OpenAI key 长度不足）")
    # ...
```

---

### P0-5: XSS 防护

**文件**: `frontend/app.py:555`  
**问题**: `unsafe_allow_html=True` 与用户输入拼接  
**风险**: 注入恶意脚本

```python
# === 修改前 ===
content = html.escape(turn["content"])
chat_html += f'<div class="chat-bubble patient">{content}</div>'

# === 修改后 ===
import bleach

ALLOWED_TAGS = []  # 不允许任何 HTML 标签
content = bleach.clean(turn["content"], tags=ALLOWED_TAGS, strip=True)
chat_html += f'<div class="chat-bubble patient">{content}</div>'
```

或更安全的方案：完全不使用 `unsafe_allow_html=True`，改用 Streamlit 原生组件。

---

### P0-6: 异常链保留

**文件**: `src/graph/workflow.py:288-293`  
**问题**: catch-all 异常丢失原始上下文  
**风险**: 生产环境无法定位根因

```python
# === 修改前 ===
except Exception as e:
    logger.error(f"工作流执行失败: {str(e)}")
    return {"error_message": f"工作流执行失败: {str(e)}", ...}

# === 修改后 ===
except Exception as e:
    logger.error(f"工作流执行失败: {e}", exc_info=True)
    raise  # 让 FastAPI 全局异常处理器处理
```

同时在 `routes.py` 添加全局异常处理器：

```python
from fastapi.responses import JSONResponse

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"未处理异常: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": "InternalError", "message": "服务内部错误"},
    )
```

---

## Phase 1: 核心功能闭环

> **目标**: 补全 `_revise_emr_node` 空实现，让质控循环真正工作

### P1-1: 实现病历修改 Agent

**文件**: `src/graph/workflow.py:182-204`  
**问题**: 质控修改节点直接 `needs_revision = False`，质控循环形同虚设

**新增文件**: `src/agents/revision_agent.py`

```python
"""
Agent 5: 病历修改Agent
根据质控报告自动修改病历
"""
from typing import Dict, List
from loguru import logger

from src.config import get_settings
from src.models.function_schemas import SOAPNote, QAReport, QAIssue
from src.utils.llm_adapter import StructuredOutputAdapter

settings = get_settings()


class RevisionAgent:
    """病历修改Agent - 根据质控问题修改病历"""

    def __init__(self):
        self.adapter = StructuredOutputAdapter(
            response_model=SOAPNote,
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
            model=settings.openai_model,
            temperature=0.3,
        )

    async def revise(
        self,
        original_emr: SOAPNote,
        qa_report: QAReport,
        medical_info: Dict,
    ) -> SOAPNote:
        """
        根据质控报告修改病历

        Args:
            original_emr: 原始病历
            qa_report: 质控报告（含问题列表）
            medical_info: 原始医疗信息

        Returns:
            修改后的SOAP病历
        """
        issues_text = self._format_issues(qa_report.issues)

        messages = [
            {
                "role": "system",
                "content": "你是一个专业的病历修改助手。请根据质控意见修改病历，只修改有问题的部分，保持其他内容不变。",
            },
            {
                "role": "user",
                "content": f"""请根据以下质控意见修改SOAP病历：

原病历：
Subjective: {original_emr.subjective}
Objective: {original_emr.objective}
Assessment: {original_emr.assessment}
Plan: {original_emr.plan}

质控意见：
{issues_text}

请输出修改后的完整SOAP病历。""",
            },
        ]

        revised = await self.adapter.ainvoke(messages)
        logger.info(f"[OK] 病历修改完成，处理了 {len(qa_report.issues)} 个问题")
        return revised

    @staticmethod
    def _format_issues(issues: List[QAIssue]) -> str:
        if not issues:
            return "无质控问题"
        return "\n".join(
            f"- [{issue.severity}] {issue.field}: {issue.message}"
            for issue in issues
        )
```

**修改**: `src/graph/workflow.py`

```python
# === 修改后 _revise_emr_node ===
async def _revise_emr_node(self, state: GraphState) -> GraphState:
    """节点5: 根据质控意见修改病历"""
    logger.info("=== Agent 5: 病历修改 ===")

    qa_report = state.get("qa_report")
    draft_emr = state.get("draft_emr")
    medical_info = state.get("extracted_info", {})
    patient_info = state.get("patient_info", {})

    # 提取问题列表
    if hasattr(qa_report, "issues"):
        issues = qa_report.issues or []
    elif isinstance(qa_report, dict):
        issues = qa_report.get("issues", [])
    else:
        issues = []

    if not issues:
        logger.info("无质控问题，跳过修改")
        state["needs_revision"] = False
        return state

    logger.info(f"开始修改病历，处理 {len(issues)} 个质控问题")

    try:
        # 确保 revision_agent 已初始化
        if not hasattr(self, "revision_agent"):
            from src.agents.revision_agent import RevisionAgent
            self.revision_agent = RevisionAgent()

        # 调用修改 Agent
        revised_emr = await self.revision_agent.revise(
            original_emr=draft_emr,
            qa_report=qa_report,
            medical_info=medical_info,
        )

        state["draft_emr"] = revised_emr
        state["needs_revision"] = False  # 修改后重新质控由 _should_revise 控制
        logger.info("[OK] 病历修改完成")

    except Exception as e:
        logger.error(f"病历修改失败: {e}", exc_info=True)
        state["needs_revision"] = False  # 修改失败则终止循环

    return state
```

---

### P1-2: 检索 Agent 接口统一

**文件**: `src/agents/retrieval_agent_simple.py`, `retrieval_agent_vector.py`, `retrieval_agent_llamagraph.py`, `retrieval_agent_llamaindex.py`  
**问题**: 4 个 Agent 无统一接口，工厂用字符串动态导入

**新增文件**: `src/agents/base_retrieval.py`

```python
"""
检索 Agent 基类
定义统一接口，所有检索策略必须实现
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any


class BaseRetrievalAgent(ABC):
    """检索 Agent 抽象基类"""

    @abstractmethod
    async def retrieve_by_symptoms(
        self, symptoms: List[str], top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """根据症状检索临床指南"""
        ...

    @abstractmethod
    async def retrieve(
        self, query: str, top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """根据查询文本检索"""
        ...
```

修改每个检索 Agent 继承 `BaseRetrievalAgent`，工厂函数返回类型改为 `BaseRetrievalAgent`。

---

### P1-3: 错误处理模式统一

**问题**: 4 种错误处理模式混用

| 模块 | 当前行为 | 应改为 |
|------|---------|--------|
| `dialogue_agent.py:82` | catch + re-raise | ✅ 保留，但加 `from e` |
| `retrieval_agent_llamaindex.py:141` | catch + return `[]` | 抛出 `RetrievalError` |
| `qa_agent.py:146` | catch + return fallback | ✅ 保留（质控不应阻断流程） |
| `generation_agent.py:113` | catch + re-raise | ✅ 保留，但加 `from e` |

**新增文件**: `src/exceptions.py`

```python
"""项目自定义异常层级"""


class MedicalCopilotError(Exception):
    """项目基础异常"""
    pass


class RetrievalError(MedicalCopilotError):
    """检索失败"""
    pass


class GenerationError(MedicalCopilotError):
    """病历生成失败"""
    pass


class ASRError(MedicalCopilotError):
    """语音识别失败"""
    pass


class RAGError(MedicalCopilotError):
    """RAG 服务失败"""
    pass
```

修改检索 Agent:
```python
# retrieval_agent_llamaindex.py
from src.exceptions import RetrievalError

async def retrieve(self, query: str, top_k: int = 5) -> List[Dict]:
    try:
        response = self.query_engine.query(query)
        # ...
        return results
    except Exception as e:
        logger.error(f"检索失败: {e}")
        raise RetrievalError(f"LlamaIndex 检索失败: {e}") from e
```

修改 `routes.py` 统一捕获:
```python
from src.exceptions import RetrievalError, GenerationError

@app.exception_handler(RetrievalError)
async def retrieval_error_handler(request: Request, exc: RetrievalError):
    return JSONResponse(status_code=503, content={"error": "RetrievalError", "message": str(exc)})
```

---

## Phase 2: 类型系统统一

> **目标**: 消除 Pydantic 模型与 Dict 混用，删除所有 `hasattr`/`isinstance` 防御代码

### P2-1: 删除 state.py 中的遮蔽别名

**文件**: `src/graph/state.py:79-83`  
**问题**: `SOAPNote = Dict[str, Any]` 遮蔽了 import 的 Pydantic `SOAPNote`

```python
# === 修改前 ===
from src.models.function_schemas import (
    MedicalInfoExtraction,
    SOAPNote,  # Pydantic 模型
    QAReport,
)
# ... 文件底部
SOAPNote = Dict[str, Any]  # ❌ 遮蔽了上面的 import
QAReport = Dict[str, Any]

# === 修改后 ===
# 删除文件底部 79-83 行的所有类型别名
# GraphState 中的字段类型直接使用 Pydantic 模型
```

---

### P2-2: GraphState 字段类型改为 Pydantic

**文件**: `src/graph/state.py:47-75`

```python
# === 修改后 ===
from src.models.function_schemas import (
    MedicalInfoExtraction,
    SOAPNote,
    QAReport,
)

class GraphState(TypedDict):
    conversation: List[Dict[str, str]]
    patient_info: Dict[str, Any]
    extracted_info: MedicalInfoExtraction          # ← 从 Dict 改为 Pydantic
    retrieved_guidelines: List[Dict[str, Any]]
    draft_emr: Optional[SOAPNote]                  # ← 从 Dict 改为 Pydantic
    final_emr: Optional[SOAPNote]                  # ← 从 Dict 改为 Pydantic
    qa_report: Optional[QAReport]                  # ← 从 Dict 改为 Pydantic
    iteration_count: int
    needs_revision: bool
    error_message: Optional[str]
    timestamp: str
    session_id: str
```

---

### P2-3: 删除 workflow.py 中的 hasattr/isinstance 检查

**文件**: `src/graph/workflow.py:121-126, 171-176, 188-193, 263-272`

```python
# === 修改前 ===
if hasattr(extracted_info, "symptoms"):
    symptoms = extracted_info.symptoms or []
elif isinstance(extracted_info, dict):
    symptoms = extracted_info.get("symptoms", [])

# === 修改后 ===
symptoms = extracted_info.symptoms or []
```

同理删除 `_qa_check_node`、`_revise_emr_node`、`run` 方法中的所有类型检查。

---

### P2-4: QAIssue.type 和 severity 改为 Enum

**文件**: `src/models/function_schemas.py:69-78`

```python
from enum import Enum
from pydantic import BaseModel, Field

class QAIssueType(str, Enum):
    MISSING = "missing"
    CONFLICT = "conflict"
    WARNING = "warning"

class QAIssueSeverity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"

class QAIssue(BaseModel):
    type: QAIssueType = Field(description="问题类型")
    field: str = Field(description="相关字段")
    message: str = Field(description="问题描述")
    severity: QAIssueSeverity = Field(description="严重程度")
```

同步删除 `src/models/schemas.py` 中重复的 `QAIssueResponse`、`QAReportResponse`、`SOAPNoteResponse`，改用 `function_schemas.py` 中的模型。

---

### P2-5: MedicationInfo 增强校验

**文件**: `src/models/function_schemas.py:9-12`

```python
class MedicationInfo(BaseModel):
    name: str = Field(min_length=1, description="药物名称")
    dosage: Optional[str] = Field(default=None, description="剂量和用法")
```

---

## Phase 3: 测试覆盖

> **目标**: 核心路径测试覆盖率达到 60%+

### P3-1: Agent 单元测试

**新增文件**: `tests/test_dialogue_agent.py`

```python
import pytest
from unittest.mock import AsyncMock, patch
from src.agents.dialogue_agent import DialogueAgent
from src.models.function_schemas import MedicalInfoExtraction


class TestDialogueAgent:
    @pytest.fixture
    def agent(self):
        with patch("src.agents.dialogue_agent.StructuredOutputAdapter"):
            return DialogueAgent()

    @pytest.mark.asyncio
    async def test_extract_returns_medical_info(self, agent):
        mock_result = MedicalInfoExtraction(
            symptoms=["咳嗽", "发热"],
            duration="1周",
        )
        agent.adapter.ainvoke = AsyncMock(return_value=mock_result)

        conversation = [
            {"role": "doctor", "content": "有什么不舒服？"},
            {"role": "patient", "content": "咳嗽一周了，还发热"},
        ]
        result = await agent.extract(conversation)

        assert result.symptoms == ["咳嗽", "发热"]
        assert result.duration == "1周"

    @pytest.mark.asyncio
    async def test_extract_empty_conversation(self, agent):
        agent.adapter.ainvoke = AsyncMock(
            return_value=MedicalInfoExtraction()
        )
        result = await agent.extract([])
        assert result.symptoms == []

    @pytest.mark.asyncio
    async def test_extract_llm_failure_propagates(self, agent):
        agent.adapter.ainvoke = AsyncMock(side_effect=RuntimeError("API down"))
        with pytest.raises(RuntimeError, match="API down"):
            await agent.extract([{"role": "patient", "content": "test"}])
```

**新增文件**: `tests/test_generation_agent.py`, `tests/test_qa_agent.py`, `tests/test_revision_agent.py` — 同理。

---

### P3-2: 工作流集成测试

**新增文件**: `tests/test_workflow.py`

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestMedicalCopilotWorkflow:
    @pytest.fixture
    def mock_agents(self):
        with patch.multiple(
            "src.graph.workflow",
            DialogueAgent=MagicMock,
            GenerationAgent=MagicMock,
            QAAgent=MagicMock,
        ):
            from src.graph.workflow import MedicalCopilotWorkflow
            wf = MedicalCopilotWorkflow(
                retrieval_agent=MagicMock(),
            )
            return wf

    @pytest.mark.asyncio
    async def test_full_workflow_success(self, mock_agents):
        mock_agents.dialogue_agent.extract = AsyncMock(
            return_value=MagicMock(symptoms=["咳嗽"])
        )
        mock_agents.generation_agent.generate = AsyncMock(
            return_value=MagicMock(subjective="咳嗽1周", objective="", assessment="感冒", plan="休息")
        )
        mock_agents.qa_agent.check = AsyncMock(
            return_value=MagicMock(is_complete=True, issues=[], score=95.0)
        )

        result = await mock_agents.run({
            "conversation": [{"role": "patient", "content": "咳嗽"}],
            "patient_info": {"age": 30, "gender": "男"},
        })

        assert result.get("error_message") is None
        assert result["iteration_count"] == 1
```

---

### P3-3: API 端点测试

**新增文件**: `tests/test_api_generate_emr.py`

```python
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, MagicMock, patch
from src.main import app


class TestGenerateEMREndpoint:
    @pytest.mark.asyncio
    async def test_generate_emr_success(self):
        mock_workflow = MagicMock()
        mock_workflow.run = AsyncMock(return_value={
            "session_id": "test-123",
            "timestamp": "2026-01-01T00:00:00",
            "final_emr": {"subjective": "test", "objective": "", "assessment": "", "plan": ""},
            "qa_report": {"is_complete": True, "issues": [], "score": 90.0},
            "iteration_count": 1,
            "error_message": None,
        })
        app.state.workflow = mock_workflow

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/generate-emr", json={
                "conversation": [{"role": "doctor", "content": "你好"}],
                "patient_info": {"age": 30, "gender": "男"},
            })

        assert resp.status_code == 200
        data = resp.json()
        assert data["session_id"] == "test-123"

    @pytest.mark.asyncio
    async def test_generate_emr_empty_conversation_rejected(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/generate-emr", json={
                "conversation": [],
                "patient_info": {"age": 30, "gender": "男"},
            })
        assert resp.status_code == 422  # Pydantic validation
```

---

### P3-4: 安全测试

**新增文件**: `tests/test_security.py`

```python
import pytest


class TestSecurity:
    @pytest.mark.asyncio
    async def test_path_traversal_blocked(self):
        from src.services.rag_service import RAGService
        svc = RAGService()
        with pytest.raises(Exception):
            svc._sanitize_filename("../../../etc/passwd")

    @pytest.mark.asyncio
    async def test_oversized_upload_rejected(self):
        from src.rag.service import VersionedTenantRAGService, RAGCoreServiceError
        svc = VersionedTenantRAGService()
        big_data = b"x" * (11 * 1024 * 1024)
        with pytest.raises(RAGCoreServiceError, match="exceeds"):
            svc._validate_upload(big_data, ".txt", "t1", "kb1")

    @pytest.mark.asyncio
    async def test_empty_tenant_id_rejected(self):
        from src.rag.service import VersionedTenantRAGService, RAGCoreServiceError
        svc = VersionedTenantRAGService()
        with pytest.raises(RAGCoreServiceError, match="tenant_id"):
            svc._validate_upload(b"data", ".txt", "", "kb1")
```

---

## Phase 4: 架构改善

> **目标**: 消除重复代码，统一常量，改善可维护性

### P4-1: 合并重复的 Schema 定义

**文件**: `src/models/schemas.py` 和 `src/models/function_schemas.py`  
**问题**: `SOAPNoteResponse` ≈ `SOAPNote`，`QAIssueResponse` ≈ `QAIssue`

**方案**: 删除 `schemas.py` 中的 `SOAPNoteResponse`、`QAIssueResponse`、`QAReportResponse`，统一使用 `function_schemas.py` 的模型。`schemas.py` 仅保留 API 请求/响应的包装模型。

```python
# schemas.py 修改后
from src.models.function_schemas import SOAPNote, QAReport  # 复用

class GenerateEMRResponse(BaseModel):
    session_id: str
    timestamp: str
    patient_info: PatientInfoRequest
    final_emr: Optional[SOAPNote] = None      # ← 直接用 function_schemas 的模型
    qa_report: Optional[QAReport] = None
    iteration_count: int
    error_message: Optional[str] = None
```

---

### P4-2: 合并重复的常量定义

**文件**: `src/services/rag_service.py:19-21` 和 `src/rag/service.py:18-19`  
**问题**: `SUPPORTED_EXTS` 和 `MAX_UPLOAD_BYTES` 各定义一份

**方案**: 提取到 `src/constants.py`

```python
"""项目全局常量"""

SUPPORTED_EXTENSIONS = frozenset({".json", ".pdf", ".txt"})
MAX_UPLOAD_SIZE_BYTES = 10 * 1024 * 1024  # 10MB
DEFAULT_RETRIEVAL_TOP_K = 5
MAX_REVISION_ITERATIONS = 3
```

两个 service 文件统一 import。

---

### P4-3: datetime.utcnow() 替换

**文件**: `src/rag/repository.py:224`, `src/rag/service.py:168`  
**问题**: `datetime.utcnow()` 在 Python 3.12 已弃用

```python
# === 修改前 ===
now = datetime.utcnow()

# === 修改后 ===
from datetime import datetime, timezone
now = datetime.now(timezone.utc)
```

全局搜索替换所有 `datetime.utcnow()` 调用。

---

### P4-4: 删除 __main__ 测试代码

**文件**: `src/agents/dialogue_agent.py:95-118`, `src/agents/qa_agent.py:253-279`, `src/agents/generation_agent.py:159-179`, `src/graph/workflow.py:296-314`, `src/agents/retrieval_agent_simple.py:151-167`

**操作**: 删除所有 `if __name__ == "__main__"` 块，测试逻辑移至 `tests/`。

---

### P4-5: 提取检索 Agent 公共 fallback 逻辑

**文件**: `src/agents/retrieval_agent_llamagraph.py:184-189, 200-205`  
**问题**: 相同的 SimpleRetrievalAgent fallback 初始化重复出现

```python
# === 提取为基类方法 ===
class BaseRetrievalAgent(ABC):
    _simple_fallback: Optional["SimpleRetrievalAgent"] = None

    def _get_simple_fallback(self) -> "SimpleRetrievalAgent":
        if self._simple_fallback is None:
            from src.agents.retrieval_agent_simple import SimpleRetrievalAgent
            self._simple_fallback = SimpleRetrievalAgent()
        return self._simple_fallback
```

---

### P4-6: Config 拆分

**文件**: `src/config.py:148-203`  
**问题**: `Settings.__init__` 40+ 行属性赋值，违反 SRP

```python
# === 修改后 ===
class Settings:
    def __init__(self):
        self.llm = LLMConfig()
        self.retrieval = RetrievalConfig()
        self.api = APIConfig()
        self.asr = ASRConfig()
        self.app = AppConfig()

    # 删除所有快捷属性，统一通过 self.llm.xxx 访问
    # 或使用 __getattr__ 代理
    def __getattr__(self, name: str):
        """代理到子配置，保持向后兼容"""
        for sub in (self.llm, self.retrieval, self.api, self.asr, self.app):
            if hasattr(sub, name):
                return getattr(sub, name)
        raise AttributeError(f"Settings has no attribute '{name}'")
```

---

## Phase 5: 性能与细节

### P5-1: SimpleRetrievalAgent 字符串匹配优化

**文件**: `src/agents/retrieval_agent_simple.py:46-59`  
**问题**: 嵌套循环 O(symptoms × keywords × guidelines)

```python
# === 修改后 ===
def _calculate_relevance(self, symptoms: List[str], guideline: Dict) -> float:
    guideline_keywords = set(guideline.get("keywords", []))
    guideline_content = guideline.get("content", "")
    guideline_title = guideline.get("title", "")

    score = 0.0
    symptom_set = set(symptoms)

    # 关键词匹配（用集合交集替代嵌套循环）
    score += len(symptom_set & guideline_keywords) * 2.0

    # 标题和内容匹配
    for symptom in symptom_set:
        if symptom in guideline_title:
            score += 1.0
        if symptom in guideline_content:
            score += 0.5

    return score
```

---

### P5-2: InMemoryDocumentRepository 版本查询优化

**文件**: `src/rag/repository.py:247-258`  
**问题**: `get_latest_version` 线性搜索

```python
# === 修改后 ===
def __init__(self):
    # ... 现有索引
    self._latest_version_cache: Dict[str, str] = {}  # document_id -> latest version_id

def get_latest_version(self, document_id: str) -> Optional[DocumentVersionRecord]:
    version_ids = self._document_versions_index.get(document_id, [])
    if not version_ids:
        return None
    # 直接取最后创建的版本（create_version 总是 append）
    return self._versions.get(version_ids[-1])
```

---

### P5-3: LLM 调用增加超时

**文件**: `src/utils/llm_adapter.py:138,114`

```python
# === 修改后 ===
response = await self.client.chat.completions.create(
    model=self.model,
    messages=messages,
    tools=[self.tool_def],
    tool_choice={"type": "function", "function": {"name": "extract_structured_data"}},
    temperature=self.temperature,
    timeout=60.0,  # ← 新增
)
```

---

### P5-4: QA Agent 症状匹配大小写不敏感

**文件**: `src/agents/qa_agent.py:246`

```python
# === 修改前 ===
symptom_mentioned = any(symptom in emr.subjective for symptom in symptoms)

# === 修改后 ===
subjective_lower = emr.subjective.lower()
symptom_mentioned = any(
    symptom.lower() in subjective_lower for symptom in symptoms
)
```

---

### P5-5: 性能测试增加阈值断言

**文件**: `tests/test_performance_upload_flow.py`

```python
# === 修改后 ===
def test_upload_latency(self):
    start = time.perf_counter()
    result = self.service.upload_and_index(...)
    elapsed = time.perf_counter() - start
    assert elapsed < 5.0, f"上传耗时 {elapsed:.2f}s 超过 5s 阈值"
    assert result.chunks > 0
```

---

## 附录: 问题索引表

| ID | Phase | 严重度 | 文件 | 行号 | 问题描述 | 状态 |
|----|-------|--------|------|------|---------|------|
| P0-1 | 0 | Critical | main.py | 77 | CORS allow_origins=["*"] | ⬜ |
| P0-2 | 0 | Critical | routes.py | 36-80 | 全局变量无锁 | ⬜ |
| P0-3 | 0 | Critical | routes.py | 156,205,253 | 文件上传无大小预检 | ⬜ |
| P0-4 | 0 | Critical | config.py | 214 | API Key 校验不足 | ⬜ |
| P0-5 | 0 | Critical | app.py | 555 | XSS unsafe_allow_html | ⬜ |
| P0-6 | 0 | Critical | workflow.py | 288 | 异常链丢失 | ⬜ |
| P1-1 | 1 | High | workflow.py | 182-204 | _revise_emr_node 空实现 | ⬜ |
| P1-2 | 1 | High | retrieval/*.py | - | 检索 Agent 无统一接口 | ⬜ |
| P1-3 | 1 | High | 多文件 | - | 错误处理模式不统一 | ⬜ |
| P2-1 | 2 | High | state.py | 79-83 | 类型别名遮蔽 import | ⬜ |
| P2-2 | 2 | High | state.py | 60-66 | GraphState 用 Dict 代替 Pydantic | ⬜ |
| P2-3 | 2 | High | workflow.py | 121-176 | hasattr/isinstance 防御代码 | ⬜ |
| P2-4 | 2 | Medium | function_schemas.py | 71,76 | QAIssue.type/severity 未用 Enum | ⬜ |
| P2-5 | 2 | Medium | function_schemas.py | 11 | MedicationInfo.name 无 min_length | ⬜ |
| P3-1 | 3 | High | tests/ | - | Agent 单元测试缺失 | ⬜ |
| P3-2 | 3 | High | tests/ | - | 工作流集成测试缺失 | ⬜ |
| P3-3 | 3 | High | tests/ | - | API 端点测试缺失 | ⬜ |
| P3-4 | 3 | Medium | tests/ | - | 安全测试缺失 | ⬜ |
| P4-1 | 4 | Medium | schemas.py | 50-74 | Schema 双重定义 | ⬜ |
| P4-2 | 4 | Medium | rag_service.py | 19-21 | 常量重复定义 | ⬜ |
| P4-3 | 4 | Medium | repository.py | 224 | datetime.utcnow() 弃用 | ⬜ |
| P4-4 | 4 | Low | 多文件 | - | __main__ 测试代码残留 | ⬜ |
| P4-5 | 4 | Medium | llamagraph.py | 184-205 | Fallback 逻辑重复 | ⬜ |
| P4-6 | 4 | Medium | config.py | 148-203 | Settings.__init__ 过长 | ⬜ |
| P5-1 | 5 | Low | simple.py | 46-59 | 嵌套循环 O(n*m) | ⬜ |
| P5-2 | 5 | Low | repository.py | 247 | 版本查询线性搜索 | ⬜ |
| P5-3 | 5 | Medium | llm_adapter.py | 138 | LLM 调用无超时 | ⬜ |
| P5-4 | 5 | Low | qa_agent.py | 246 | 症状匹配区分大小写 | ⬜ |
| P5-5 | 5 | Low | test_performance.py | - | 性能测试无阈值断言 | ⬜ |

**状态图例**: ⬜ 待处理 | 🔄 进行中 | ✅ 已完成

---

## 执行建议

1. **Phase 0 必须先做** — 安全漏洞不修复不得上线
2. **Phase 1 和 2 可并行** — 功能闭环和类型统一互不阻塞
3. **Phase 3 在 Phase 1 完成后做** — 测试需要可工作的功能
4. **Phase 4 和 5 可穿插进行** — 重构类任务适合在开发间隙做
5. **每个 Phase 完成后运行 `pytest tests/`** — 确保不引入回归
