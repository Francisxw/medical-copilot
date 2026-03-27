"""
Pydantic数据模型
用于API请求/响应验证
"""

from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime


# ==================== 请求模型 ====================


class PatientInfoRequest(BaseModel):
    """患者基本信息"""

    age: int = Field(..., ge=0, le=150, description="患者年龄")
    gender: str = Field(..., pattern="^(男|女)$", description="患者性别")
    name: Optional[str] = Field(None, description="患者姓名")


class ConversationTurn(BaseModel):
    """对话轮次"""

    role: str = Field(..., pattern="^(doctor|patient)$", description="角色")
    content: str = Field(..., min_length=1, description="对话内容")


class GenerateEMRRequest(BaseModel):
    """生成病历请求"""

    conversation: List[ConversationTurn] = Field(..., min_length=1, description="医患对话历史")
    patient_info: PatientInfoRequest = Field(..., description="患者信息")

    class Config:
        json_schema_extra = {
            "example": {
                "conversation": [
                    {"role": "doctor", "content": "你好，今天有什么不舒服？"},
                    {"role": "patient", "content": "我咳嗽已经一周了，还有点发热"},
                ],
                "patient_info": {"age": 35, "gender": "男"},
            }
        }


# ==================== 响应模型 ====================


class SOAPNoteResponse(BaseModel):
    """SOAP病历响应"""

    subjective: str = Field(..., description="主诉/现病史")
    objective: str = Field(..., description="客观检查")
    assessment: str = Field(..., description="评估诊断")
    plan: str = Field(..., description="诊疗计划")


class QAIssueResponse(BaseModel):
    """质控问题响应"""

    type: str = Field(..., description="问题类型")
    field: str = Field(..., description="相关字段")
    message: str = Field(..., description="问题描述")
    severity: str = Field(..., description="严重程度")


class QAReportResponse(BaseModel):
    """质控报告响应"""

    is_complete: bool = Field(..., description="是否完整")
    issues: List[QAIssueResponse] = Field(default_factory=list, description="问题列表")
    score: float = Field(..., ge=0, le=100, description="质量评分")


class GenerateEMRResponse(BaseModel):
    """生成病历响应"""

    session_id: str = Field(..., description="会话ID")
    timestamp: str = Field(..., description="生成时间")
    patient_info: PatientInfoRequest = Field(..., description="患者信息")
    final_emr: Optional[SOAPNoteResponse] = Field(None, description="最终病历")
    qa_report: Optional[QAReportResponse] = Field(None, description="质控报告")
    iteration_count: int = Field(..., description="迭代次数")
    error_message: Optional[str] = Field(None, description="错误信息")


class AudioTranscriptionResponse(BaseModel):
    """音频转写响应。"""

    text: str = Field(..., description="识别出的文本")


class RAGUploadResponse(BaseModel):
    """RAG文档上传响应。"""

    status: str = Field(..., description="处理状态")
    filename: str = Field(..., description="清理后的文件名")
    chunks: int = Field(..., description="文档分块数量")
    collection_name: str = Field(..., description="目标向量集合名称")


class RAGVersionedUploadResponse(BaseModel):
    """RAG版本化文档上传响应。"""

    document_id: str = Field(..., description="文档ID")
    version_id: str = Field(..., description="版本ID")
    filename: str = Field(..., description="原始文件名")
    chunks: int = Field(..., description="文档分块数量")
    collection_name: str = Field(..., description="目标向量集合名称")
    dedup_hit: bool = Field(..., description="是否命中去重")
    message: str = Field(..., description="处理消息")


# ==================== 通用响应 ====================

class HealthResponse(BaseModel):
    """健康检查响应"""

    status: str = Field(
        ..., 
        description="服务状态",
        examples=["healthy"]
    )
    
    version: str = Field(
        ..., 
        description="版本号",
        examples=["1.0.0"]
    )
    
    timestamp: datetime = Field(
        default_factory=datetime.now, 
        description="时间戳"
    )



class ErrorResponse(BaseModel):
    """错误响应"""

    error: str = Field(..., description="错误类型")
    message: str = Field(..., description="错误信息")
    detail: Optional[str] = Field(None, description="详细信息")
