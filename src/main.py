"""
FastAPI应用主入口
使用 lifespan 管理应用生命周期
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger
import sys
import os

from src.config import settings, validate_settings
from src.api.routes import router
from src.graph.workflow import MedicalCopilotWorkflow
from src.services.asr_service import ASRService
from src.services.rag_service import RAGService
from src.rag.service import VersionedTenantRAGService
from src.exceptions import RetrievalError, GenerationError


def _parse_cors_origins(raw: str) -> list[str]:
    """Parse comma-separated CORS origins, stripping whitespace."""
    return [o.strip() for o in raw.split(",") if o.strip()]


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理：启动时初始化，关闭时清理"""
    # 启动时初始化
    logger.info("=== Medical Copilot API 启动 ===")

    # 配置校验
    warnings = validate_settings()
    for warning in warnings:
        logger.warning(warning)

    logger.info(f"OpenAI模型: {settings.openai_model}")
    logger.info(f"检索模式: {settings.retrieval_mode}")
    logger.info(f"向量数据库: {settings.chroma_persist_dir}")
    logger.info(f"日志级别: {settings.log_level}")

    # Initialize services on app.state so route dependencies read from
    # a single lifecycle-managed source instead of module-level globals.
    try:
        app.state.workflow = MedicalCopilotWorkflow(retrieval_mode=settings.retrieval_mode)
        logger.info("✅ 工作流初始化完成")
    except Exception as e:
        logger.error(f"❌ 工作流初始化失败: {e}")
        raise

    app.state.asr_service = ASRService()
    app.state.rag_service = RAGService()
    app.state.versioned_rag_service = VersionedTenantRAGService()

    yield

    # 关闭时清理
    logger.info("=== Medical Copilot API 关闭 ===")


# 配置日志
logger.remove()  # 移除默认处理器
logger.add(
    sys.stderr,
    level=settings.log_level,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
)

# 确保日志目录存在
log_dir = os.path.dirname(settings.log_file)
if log_dir and not os.path.exists(log_dir):
    os.makedirs(log_dir, exist_ok=True)

logger.add(settings.log_file, rotation="500 MB", retention="10 days", level=settings.log_level)

# 创建FastAPI应用（使用 lifespan）
app = FastAPI(
    title="Medical Copilot API",
    description="基于多Agent协作的医疗文书生成系统",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# --- CORS -------------------------------------------------------------------
# Derive origins from settings instead of hardcoding wildcard+credentials.
# Per the CORS spec, allow_origins=["*"] with allow_credentials=True is
# invalid; browsers will reject it.  When wildcard is desired (development),
# credentials are automatically disabled.
_cors_origins = _parse_cors_origins(settings.cors_origins or settings.frontend_url)
if not _cors_origins:
    _cors_origins = [settings.frontend_url]
_allow_credentials = "*" not in _cors_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Global exception handler -----------------------------------------------
# Preserves the exception chain in logs while returning a sanitized response
# so internal tracebacks never leak to callers.


@app.exception_handler(RetrievalError)
async def _retrieval_error_handler(request: Request, exc: RetrievalError):
    logger.error(
        f"RetrievalError on {request.method} {request.url.path}: {exc}",
        exc_info=True,
    )
    return JSONResponse(
        status_code=502,
        content={"detail": "知识检索服务暂时不可用，请稍后重试"},
    )


@app.exception_handler(GenerationError)
async def _generation_error_handler(request: Request, exc: GenerationError):
    logger.error(
        f"GenerationError on {request.method} {request.url.path}: {exc}",
        exc_info=True,
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "病历生成失败，请稍后重试"},
    )


@app.exception_handler(Exception)
async def _global_exception_handler(request: Request, exc: Exception):
    logger.error(
        f"Unhandled exception on {request.method} {request.url.path}: {exc}",
        exc_info=True,
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "服务器内部错误，请稍后重试"},
    )


# 注册路由
app.include_router(router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.api_reload,
        log_level=settings.log_level.lower(),
    )
