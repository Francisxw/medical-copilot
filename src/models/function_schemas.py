"""
Function Calling 的 Pydantic 模型定义
用于结构化输出的类型定义
"""
from pydantic import BaseModel, Field
from typing import List, Optional


class MedicationInfo(BaseModel):
    """药物信息"""
    name: str = Field(description="药物名称")
    dosage: Optional[str] = Field(default=None, description="剂量和用法")


class MedicalInfoExtraction(BaseModel):
    """
    医疗信息提取结果
    从对话中提取的结构化医疗信息
    """
    symptoms: List[str] = Field(
        default_factory=list,
        description="患者提到的所有症状"
    )
    duration: Optional[str] = Field(
        default=None,
        description="症状持续的时间"
    )
    severity: Optional[str] = Field(
        default=None,
        description="症状的严重程度（如轻微、中等、严重）"
    )
    medications: List[MedicationInfo] = Field(
        default_factory=list,
        description="当前用药记录"
    )
    allergies: List[str] = Field(
        default_factory=list,
        description="过敏史"
    )
    past_history: List[str] = Field(
        default_factory=list,
        description="既往病史"
    )
    family_history: List[str] = Field(
        default_factory=list,
        description="家族史"
    )


class SOAPNote(BaseModel):
    """
    SOAP格式病历
    结构化的电子病历
    """
    subjective: str = Field(
        description="主诉和现病史：患者的主要症状、持续时间、起病情况等"
    )
    objective: str = Field(
        description="客观检查：体格检查建议、实验室/影像学检查建议"
    )
    assessment: str = Field(
        description="评估：初步诊断、鉴别诊断、病情严重程度评估"
    )
    plan: str = Field(
        description="计划：进一步检查计划、治疗方案建议、健康教育"
    )


class QAIssue(BaseModel):
    """质控问题"""
    type: str = Field(
        description="问题类型：missing（缺失）/ conflict（冲突）/ warning（警告）"
    )
    field: str = Field(description="相关字段")
    message: str = Field(description="问题描述")
    severity: str = Field(
        description="严重程度：error（错误）/ warning（警告）/ info（信息）"
    )


class QAReport(BaseModel):
    """
    质控报告
    病历质量检查结果
    """
    is_complete: bool = Field(
        description="病历是否完整（没有error级别的问题）"
    )
    issues: List[QAIssue] = Field(
        default_factory=list,
        description="发现的所有问题列表"
    )
    score: float = Field(
        ge=0.0,
        le=100.0,
        description="质量分数（0-100分）"
    )
