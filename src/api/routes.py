"""
FastAPI路由定义
依赖注入方式获取工作流实例
"""

from fastapi import APIRouter, HTTPException, Depends, File, UploadFile, Header, Query, Request
from fastapi.concurrency import run_in_threadpool
from loguru import logger
from typing import TYPE_CHECKING

from src.models.schemas import (
    AudioTranscriptionResponse,
    GenerateEMRRequest,
    GenerateEMRResponse,
    HealthResponse,
    RAGUploadResponse,
    RAGVersionedUploadResponse,
)
from src.graph.workflow import MedicalCopilotWorkflow
from src.services.asr_service import ASRService, ASRServiceError
from src.services.rag_service import RAGService, RAGServiceError
from src.rag.service import (
    MAX_UPLOAD_BYTES,
    VersionedTenantRAGService,
    DedupMode,
    RAGCoreServiceError,
)

# 使用 TYPE_CHECKING 避免循环导入
if TYPE_CHECKING:
    from src.config import Settings

# Backward compatibility scope for the legacy route.
LEGACY_DEFAULT_SCOPE = "user-uploads"
LEGACY_DEFAULT_COLLECTION_NAME = LEGACY_DEFAULT_SCOPE

# 创建路由器
router = APIRouter()

# ---------------------------------------------------------------------------
# Upload size limit helpers
# ---------------------------------------------------------------------------
# Maximum upload body size for file endpoints.
MAX_UPLOAD_SIZE = MAX_UPLOAD_BYTES


async def _read_upload_bounded(
    upload: UploadFile,
    max_size: int = MAX_UPLOAD_SIZE,
) -> bytes:
    """Read an upload in bounded chunks to avoid unbounded memory consumption.

    Reads up to ``max_size + 1`` bytes so we can detect overshoot without
    buffering the entire (potentially huge) file.
    """
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await upload.read(1024 * 1024)  # 1 MB at a time
        if not chunk:
            break
        total += len(chunk)
        if total > max_size:
            raise HTTPException(
                status_code=413,
                detail=f"上传文件过大，最大允许 {max_size // (1024 * 1024)}MB",
            )
        chunks.append(chunk)
    return b"".join(chunks)


# ---------------------------------------------------------------------------
# Service getters — read from app.state (lifespan-managed) with lazy fallback
# ---------------------------------------------------------------------------


def get_workflow(request: Request) -> "MedicalCopilotWorkflow":
    """依赖函数：通过 app.state 获取工作流实例"""
    workflow = getattr(request.app.state, "workflow", None)
    if workflow is None:
        raise RuntimeError("工作流未初始化，请确保应用已启动")
    return workflow


def get_asr_service(request: Request) -> ASRService:
    """获取语音识别服务实例。"""
    svc = getattr(request.app.state, "asr_service", None)
    if svc is None:
        raise RuntimeError("语音识别服务未初始化，请确保应用已启动")
    return svc


def get_rag_service(request: Request) -> RAGService:
    """获取RAG服务实例。"""
    svc = getattr(request.app.state, "rag_service", None)
    if svc is None:
        raise RuntimeError("RAG 服务未初始化，请确保应用已启动")
    return svc


def get_versioned_rag_service(request: Request) -> VersionedTenantRAGService:
    """获取版本化多租户RAG服务实例。"""
    svc = getattr(request.app.state, "versioned_rag_service", None)
    if svc is None:
        raise RuntimeError("版本化 RAG 服务未初始化，请确保应用已启动")
    return svc


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    健康检查端点
    """
    return HealthResponse(status="healthy", version="1.0.0")


@router.post("/api/generate-emr", response_model=GenerateEMRResponse)
async def generate_emr(
    request: GenerateEMRRequest,
    workflow: MedicalCopilotWorkflow = Depends(get_workflow),
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
    logger.info(f"收到病历生成请求: {len(request.conversation)} 轮对话")

    # 转换请求数据为工作流输入格式
    inputs = {
        "conversation": [
            {"role": turn.role, "content": turn.content} for turn in request.conversation
        ],
        "patient_info": request.patient_info.model_dump(),
    }

    # 运行工作流 — unexpected exceptions propagate to the global handler.
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


@router.post("/api/transcribe-audio", response_model=AudioTranscriptionResponse)
async def transcribe_audio(
    asr_service: ASRService = Depends(get_asr_service),
    audio: UploadFile = File(...),
):
    """将上传的音频转写为文本。"""
    audio_bytes = await _read_upload_bounded(audio)
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="上传的音频为空")

    try:
        transcript = await asr_service.transcribe_audio(
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


@router.get("/api/workflow/info")
async def workflow_info(
    workflow: MedicalCopilotWorkflow = Depends(get_workflow),
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


@router.post("/api/rag/upload", response_model=RAGUploadResponse)
async def upload_rag_document(
    file: UploadFile = File(...),
    rag_service: RAGService = Depends(get_rag_service),
):
    """
    上传单个文档并索引到 RAG 向量存储。

    使用线程池执行同步的索引操作，避免阻塞事件循环。
    """
    file_bytes = await _read_upload_bounded(file)
    if not file_bytes:
        raise HTTPException(status_code=400, detail="上传的文件为空")

    collection_name = LEGACY_DEFAULT_SCOPE

    try:
        # 在线程池中执行同步的索引操作
        result = await run_in_threadpool(
            rag_service.upload_and_index,
            file_bytes=file_bytes,
            filename=file.filename or "document",
            collection_name=collection_name,
        )

        return RAGUploadResponse(
            status="success",
            filename=result["filename"],
            chunks=result["chunks"],
            collection_name=result["collection_name"],
        )

    except HTTPException:
        raise
    except RAGServiceError as exc:
        # 用户输入错误 -> 400
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        # 后端处理错误 -> 500，但不暴露原始异常细节
        logger.error(f"RAG 上传索引失败: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail="文档索引失败，请稍后重试") from exc


@router.post("/api/rag/upload-versioned", response_model=RAGVersionedUploadResponse)
async def upload_rag_document_versioned(
    file: UploadFile = File(...),
    x_tenant_id: str = Header(..., alias="X-Tenant-ID"),
    x_kb_id: str = Header(..., alias="X-KB-ID"),
    dedup_mode: DedupMode = Query(
        DedupMode.SKIP, description="去重模式: skip, new_version, replace"
    ),
    versioned_rag_service: VersionedTenantRAGService = Depends(get_versioned_rag_service),
):
    """
    上传单个文档并索引到版本化多租户 RAG 向量存储。

    使用线程池执行同步的索引操作，避免阻塞事件循环。
    支持租户隔离和文档版本控制。
    """
    file_bytes = await _read_upload_bounded(file)
    if not file_bytes:
        raise HTTPException(status_code=400, detail="上传的文件为空")

    try:
        # 在线程池中执行同步的索引操作
        result = await run_in_threadpool(
            versioned_rag_service.upload_and_index,
            file_bytes=file_bytes,
            filename=file.filename or "document",
            tenant_id=x_tenant_id,
            kb_id=x_kb_id,
            dedup_mode=dedup_mode,
        )

        return RAGVersionedUploadResponse(
            document_id=result.document_id,
            version_id=result.version_id,
            filename=result.filename,
            chunks=result.chunks,
            collection_name=result.collection_name,
            dedup_hit=result.dedup_hit,
            message=result.message,
        )

    except HTTPException:
        raise
    except RAGCoreServiceError as exc:
        # 用户输入错误 -> 400
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        # 后端处理错误 -> 500，但不暴露原始异常细节
        logger.error(f"RAG 版本化上传索引失败: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail="文档索引失败，请稍后重试") from exc
