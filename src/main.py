"""
FastAPI应用主入口
使用 lifespan 管理应用生命周期
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
import sys
import os

from src.config import settings, validate_settings
from src.api.routes import router, set_workflow_instance
from src.graph.workflow import MedicalCopilotWorkflow


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

    # 初始化工作流实例
    try:
        workflow = MedicalCopilotWorkflow(retrieval_mode=settings.retrieval_mode)
        set_workflow_instance(workflow)
        logger.info("✅ 工作流初始化完成")
    except Exception as e:
        logger.error(f"❌ 工作流初始化失败: {str(e)}")
        raise

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

logger.add(
    settings.log_file, rotation="500 MB", retention="10 days", level=settings.log_level
)

# 创建FastAPI应用（使用 lifespan）
app = FastAPI(
    title="Medical Copilot API",
    description="基于多Agent协作的医疗文书生成系统",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应限制具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
