"""
LangGraph状态定义
"""
from typing import TypedDict, List, Dict, Any, Optional
from datetime import datetime
from src.models.function_schemas import (
    MedicalInfoExtraction,
    SOAPNote,
    QAReport,
    MedicationInfo
)


class MedicalInfo(TypedDict):
    """提取的医疗信息"""
    symptoms: List[str]  # 症状列表
    duration: Optional[str]  # 病程
    severity: Optional[str]  # 严重程度
    medications: List[Dict[str, str]]  # 用药记录
    allergies: List[str]  # 过敏史
    past_history: List[str]  # 既往史
    family_history: List[str]  # 家族史


class PatientInfo(TypedDict):
    """患者基本信息"""
    age: int
    gender: str
    name: Optional[str]


class SOAPNote(TypedDict):
    """SOAP格式病历"""
    subjective: str  # 主诉、现病史
    objective: str  # 体格检查、实验室检查
    assessment: str  # 评估、诊断
    plan: str  # 计划


class QAIssue(TypedDict):
    """质控问题"""
    type: str  # 问题类型：missing, conflict, warning
    field: str  # 相关字段
    message: str  # 问题描述
    severity: str  # 严重程度：error, warning, info


class QAReport(TypedDict):
    """质控报告"""
    is_complete: bool  # 是否完整
    issues: List[QAIssue]  # 问题列表
    score: float  # 质量评分 0-100


class GraphState(TypedDict):
    """
    主工作流状态
    定义LangGraph中传递的状态结构
    """
    # 输入
    conversation: List[Dict[str, str]]  # 对话历史 [{"role": "doctor/patient", "content": "..."}]
    patient_info: PatientInfo  # 患者信息

    # 中间状态
    extracted_info: MedicalInfo  # Agent 1提取的医疗信息
    retrieved_guidelines: List[Dict[str, Any]]  # Agent 2检索的指南
    draft_emr: Optional[SOAPNote]  # Agent 3生成的草稿病历
    qa_report: Optional[QAReport]  # Agent 4的质控报告

    # 输出
    final_emr: Optional[SOAPNote]  # 最终病历

    # 控制流
    iteration_count: int  # 迭代次数
    needs_revision: bool  # 是否需要修改
    error_message: Optional[str]  # 错误信息

    # 元数据
    timestamp: str  # 生成时间
    session_id: str  # 会话ID
