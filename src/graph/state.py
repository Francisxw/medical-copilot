"""
LangGraph状态定义

注意：
- 业务数据模型（MedicalInfoExtraction, SOAPNote, QAReport）统一使用 Pydantic 定义在 src.models.function_schemas
- GraphState 只包含：
  1. 输入/输出的业务数据（通过 Pydantic 模型传递）
  2. 图运行时的控制字段（如 session_id, iteration_count 等）
"""

from typing import TypedDict, List, Dict, Any, Optional
from datetime import datetime

# 导入业务数据模型（Pydantic）- 单一来源
from src.models.function_schemas import (
    MedicalInfoExtraction,
    SOAPNote,
    QAReport,
    MedicationInfo,
    QAIssue,
)


# 运行时状态字段（GraphState 特有，不存在于业务模型中）
class GraphRuntimeState(TypedDict):
    """LangGraph 运行时的控制状态"""

    iteration_count: int  # 迭代次数
    needs_revision: bool  # 是否需要修改
    error_message: Optional[str]  # 错误信息
    timestamp: str  # 生成时间
    session_id: str  # 会话ID


# 业务数据通过 Pydantic 模型传递，这里定义 GraphState 使用模型字段
# 注意：LangGraph TypedDict 要求值类型必须匹配，但我们可以使用 dict 类型来兼容 Pydantic 模型
GraphStateInput = TypedDict(
    "GraphStateInput",
    {
        # 输入
        "conversation": List[Dict[str, str]],  # 对话历史
        "patient_info": Dict[str, Any],  # 患者信息
    },
)


class GraphState(GraphStateInput):
    """
    主工作流状态
    定义LangGraph中传递的状态结构

    分为两部分：
    1. 业务数据：extracted_info, retrieved_guidelines, draft_emr, final_emr, qa_report（使用 dict 兼容 Pydantic）
    2. 运行时状态：iteration_count, needs_revision, error_message, timestamp, session_id
    """

    # 输入（已在 GraphStateInput 中定义）

    # 中间状态（使用 dict 兼容 Pydantic 模型序列化）
    extracted_info: Dict[str, Any]  # Agent 1 提取的医疗信息
    retrieved_guidelines: List[Dict[str, Any]]  # Agent 2 检索的指南
    draft_emr: Optional[Dict[str, Any]]  # Agent 3 生成的草稿病历
    qa_report: Optional[Dict[str, Any]]  # Agent 4 的质控报告

    # 输出
    final_emr: Optional[Dict[str, Any]]  # 最终病历

    # 控制流
    iteration_count: int
    needs_revision: bool
    error_message: Optional[str]

    # 元数据
    timestamp: str
    session_id: str


# 兼容性别名（保留旧名称供迁移期间使用）
MedicalInfo = Dict[str, Any]  # 使用 dict 代替 TypedDict，兼容 Pydantic 模型
PatientInfo = Dict[str, Any]
SOAPNote = Dict[str, Any]
QAIssue = Dict[str, Any]
QAReport = Dict[str, Any]
