"""
FastAPI路由定义
"""

from fastapi import APIRouter, HTTPException
from loguru import logger
import sys

from src.models.schemas import GenerateEMRRequest, GenerateEMRResponse, HealthResponse
from src.graph.workflow import MedicalCopilotWorkflow
from src.config import get_settings

settings = get_settings()

# 创建路由器
router = APIRouter()

# 初始化工作流
workflow = MedicalCopilotWorkflow(retrieval_mode=settings.retrieval_mode)


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    健康检查端点
    """
    return HealthResponse(status="healthy", version="1.0.0")


@router.post("/api/generate-emr", response_model=GenerateEMRResponse)
async def generate_emr(request: GenerateEMRRequest):
    """
    生成电子病历

    这是核心端点，接收医患对话，返回生成的SOAP格式病历和质控报告。

    Args:
        request: 包含对话历史和患者信息

    Returns:
        GenerateEMRResponse: 生成的病历和质控结果

    Raises:
        HTTPException: 生成失败时抛出
    """
    try:
        logger.info(f"收到病历生成请求: {len(request.conversation)} 轮对话")

        # 转换请求数据为工作流输入格式
        inputs = {
            "conversation": [
                {"role": turn.role, "content": turn.content}
                for turn in request.conversation
            ],
            "patient_info": request.patient_info.model_dump(),
        }

        # 运行工作流
        result = await workflow.run(inputs)

        # 检查是否有错误
        if result.get("error_message"):
            raise HTTPException(status_code=500, detail=result["error_message"])

        # 构建响应
        response = GenerateEMRResponse(
            session_id=result["session_id"],
            timestamp=result["timestamp"],
            patient_info=request.patient_info,
            final_emr=result["final_emr"],
            qa_report=result["qa_report"],
            iteration_count=result["iteration_count"],
        )

        logger.info(f"病历生成成功: {result['session_id']}")
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"生成病历失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"生成病历时发生错误: {str(e)}")


@router.get("/api/workflow/info")
async def workflow_info():
    """
    获取工作流信息
    """
    return {
        "name": "Medical Copilot Workflow",
        "version": "1.0.0",
        "agents": [
            {"name": "DialogueAgent", "description": "从对话中提取医疗信息"},
            {"name": "RetrievalAgent", "description": "检索相关临床指南"},
            {"name": "GenerationAgent", "description": "生成SOAP格式病历"},
            {"name": "QAAgent", "description": "质控检查"},
        ],
        "max_iterations": 3,
        "retrieval_mode": workflow.retrieval_mode,
    }
