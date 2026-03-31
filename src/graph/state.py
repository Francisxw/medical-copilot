"""
LangGraph状态定义。

业务数据在图节点间统一通过 Pydantic 模型传递，
运行时控制字段保留为简单标量类型。
"""

from typing import Any, Dict, List, Optional, TypedDict

from src.models.function_schemas import MedicalInfoExtraction, QAReport, SOAPNote


class GraphState(TypedDict):
    """LangGraph 主工作流状态。"""

    # 输入
    conversation: List[Dict[str, str]]
    patient_info: Dict[str, Any]

    # 中间状态
    extracted_info: MedicalInfoExtraction
    retrieved_guidelines: List[Dict[str, Any]]
    draft_emr: Optional[SOAPNote]
    qa_report: Optional[QAReport]

    # 输出
    final_emr: Optional[SOAPNote]

    # 控制流
    iteration_count: int
    needs_revision: bool
    error_message: Optional[str]

    # 元数据
    timestamp: str
    session_id: str
