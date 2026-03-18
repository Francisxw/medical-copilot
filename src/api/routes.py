"""
FastAPI路由定义
依赖注入方式获取工作流实例
"""

from fastapi import APIRouter, HTTPException, Depends, File, UploadFile
from loguru import logger
from typing import TYPE_CHECKING, Annotated

from src.models.schemas import (
    AudioTranscriptionResponse,
    GenerateEMRRequest,
    GenerateEMRResponse,
    HealthResponse,
)
from src.graph.workflow import MedicalCopilotWorkflow
from src.services.asr_service import ASRService, ASRServiceError

# 使用 TYPE_CHECKING 避免循环导入
if TYPE_CHECKING:
    from src.config import Settings


# 创建路由器
router = APIRouter()

# 存储工作流实例的容器（通过依赖注入访问）
_workflow_instance: "MedicalCopilotWorkflow | None" = None
_asr_service_instance: ASRService | None = None


def set_workflow_instance(workflow: "MedicalCopilotWorkflow") -> None:
    """设置工作流实例（由 main.py 在 lifespan 中调用）"""
    global _workflow_instance
    _workflow_instance = workflow


def get_workflow() -> "MedicalCopilotWorkflow":
    """依赖函数：通过 app.state 获取工作流实例"""
    if _workflow_instance is None:
        raise RuntimeError("工作流未初始化，请确保应用已启动")
    return _workflow_instance


def get_asr_service() -> ASRService:
    """获取语音识别服务实例。"""
    global _asr_service_instance

    if _asr_service_instance is None:
        _asr_service_instance = ASRService()

    return _asr_service_instance


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    健康检查端点
    """
    return HealthResponse(status="healthy", version="1.0.0")


@router.post("/api/generate-emr", response_model=GenerateEMRResponse)
async def generate_emr(
    request: GenerateEMRRequest,
    workflow: Annotated[MedicalCopilotWorkflow, Depends(get_workflow)],
):
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
            error_message=result.get("error_message"),
        )

        logger.info(f"病历生成成功: {result['session_id']}")
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"生成病历失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"生成病历时发生错误: {str(e)}")


@router.post("/api/transcribe-audio", response_model=AudioTranscriptionResponse)
async def transcribe_audio(audio: UploadFile = File(...)):
    """将上传的音频转写为文本。"""
    try:
        audio_bytes = await audio.read()
        if not audio_bytes:
            raise HTTPException(status_code=400, detail="上传的音频为空")

        transcript = await get_asr_service().transcribe_audio(
            audio_bytes=audio_bytes,
            mime_type=audio.content_type or "application/octet-stream",
            filename=audio.filename or "audio.wav",
        )
        return AudioTranscriptionResponse(text=transcript)
    except HTTPException:
        raise
    except ASRServiceError as exc:
        logger.warning(f"音频转写失败: {exc}")
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        logger.error(f"音频转写接口异常: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail="音频转写时发生未知错误") from exc


@router.get("/api/workflow/info")
async def workflow_info(
    workflow: Annotated[MedicalCopilotWorkflow, Depends(get_workflow)],
):
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
