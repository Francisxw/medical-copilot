"""
配置管理模块

采用分域配置策略：
- LLMConfig: 大语言模型相关配置
- RetrievalConfig: 检索相关配置
- APIConfig: API 服务相关配置
- AppConfig: 应用通用配置

统一从环境变量读取，提供启动校验
"""

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional, List
from pathlib import Path
from loguru import logger
import os


# ==================== 分域配置类 ====================


class LLMConfig(BaseSettings):
    """LLM 大语言模型配置"""

    # LLM API (用于对话、生成、质控)
    openai_api_key: str
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-3.5-turbo"

    # Embedding API (用于向量检索)
    embedding_base_url: Optional[str] = None  # 默认使用 openai_base_url
    embedding_model: str = "text-embedding-ada-002"

    # Generation settings
    temperature: float = 0.7

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if self.embedding_base_url is None:
            self.embedding_base_url = self.openai_base_url


class RetrievalConfig(BaseSettings):
    """检索相关配置"""

    # Retrieval mode: simple | vector | llamagraph | llamaindex
    retrieval_mode: str = "simple"

    # LlamaGraph storage
    llamagraph_persist_dir: str = "./storage/llamagraph"

    # LlamaIndex storage
    llamaindex_persist_dir: str = "./storage/llamaindex"
    llamaindex_collection_name: str = "medical_guidelines"
    llamaindex_chunk_size: int = 512
    llamaindex_chunk_overlap: int = 50

    # Graph store backend: memory | nebula
    graph_store_mode: str = "memory"

    # Vector Database
    chroma_persist_dir: str = "./data/chroma_db"

    # Guidelines path
    guidelines_path: str = "./data/guidelines/clinical_guidelines.json"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


class APIConfig(BaseSettings):
    """API 服务配置"""

    api_host: str = "0.0.0.0"
    api_port: int = 8888
    api_reload: bool = True
    request_timeout: int = 120  # 请求超时时间（秒）

    # Frontend URL (用于 CORS)
    frontend_url: str = "http://localhost:8501"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


class ASRConfig(BaseSettings):
    """语音识别配置。"""

    asr_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("ASR_API_KEY", "DASHSCOPE_API_KEY"),
    )
    asr_region: str = "singapore"
    asr_language: str = "zh"
    asr_sample_rate: int = 16000
    asr_model: str = "qwen3-asr-flash-realtime"
    asr_file_model: str = "qwen3-asr-flash"
    asr_timeout_seconds: int = 20
    enable_medical_terms: bool = True

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


class AppConfig(BaseSettings):
    """应用通用配置"""

    # Logging
    log_level: str = "INFO"
    log_file: str = "./logs/app.log"

    # Application
    max_conversation_turns: int = 10
    max_revision_iterations: int = 3

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


# ==================== 统一配置类 ====================


class Settings:
    """
    统一配置入口

    聚合所有分域配置，提供统一访问接口
    支持懒加载和运行时校验
    """

    def __init__(self):
        # 初始化各分域配置
        self.llm = LLMConfig()
        self.retrieval = RetrievalConfig()
        self.api = APIConfig()
        self.asr = ASRConfig()
        self.app = AppConfig()

        # 快捷访问属性（保持向后兼容）
        self.openai_api_key = self.llm.openai_api_key
        self.openai_base_url = self.llm.openai_base_url
        self.openai_model = self.llm.openai_model
        self.embedding_base_url = self.llm.embedding_base_url
        self.embedding_model = self.llm.embedding_model
        self.temperature = self.llm.temperature

        self.retrieval_mode = self.retrieval.retrieval_mode
        self.llamagraph_persist_dir = self.retrieval.llamagraph_persist_dir
        self.llamaindex_persist_dir = self.retrieval.llamaindex_persist_dir
        self.llamaindex_collection_name = self.retrieval.llamaindex_collection_name
        self.llamaindex_chunk_size = self.retrieval.llamaindex_chunk_size
        self.llamaindex_chunk_overlap = self.retrieval.llamaindex_chunk_overlap
        self.graph_store_mode = self.retrieval.graph_store_mode
        self.chroma_persist_dir = self.retrieval.chroma_persist_dir

        self.api_host = self.api.api_host
        self.api_port = self.api.api_port
        self.api_reload = self.api.api_reload
        self.request_timeout = self.api.request_timeout

        self.asr_api_key = self.asr.asr_api_key
        self.asr_region = self.asr.asr_region
        self.asr_language = self.asr.asr_language
        self.asr_sample_rate = self.asr.asr_sample_rate
        self.asr_model = self.asr.asr_model
        self.asr_file_model = self.asr.asr_file_model
        self.asr_timeout_seconds = self.asr.asr_timeout_seconds
        self.enable_medical_terms = self.asr.enable_medical_terms

        self.log_level = self.app.log_level
        self.log_file = self.app.log_file
        self.max_conversation_turns = self.app.max_conversation_turns
        self.max_revision_iterations = self.app.max_revision_iterations

        # 额外属性
        self.guidelines_path = self.retrieval.guidelines_path
        self.frontend_url = self.api.frontend_url

    def validate(self) -> List[str]:
        """
        启动校验

        Returns:
            警告信息列表
        """
        warnings = []

        # 检查 API key
        if not self.openai_api_key or self.openai_api_key == "your-api-key-here":
            warnings.append("⚠️ OPENAI_API_KEY 未设置或为默认值")

        if not self.asr_api_key:
            warnings.append(
                "⚠️ ASR_API_KEY / DASHSCOPE_API_KEY 未设置，语音识别功能将不可用"
            )

        # 检查目录是否存在
        project_root = Path(".").resolve()

        # 检查数据目录
        guidelines_path = Path(self.guidelines_path)
        if not guidelines_path.exists():
            warnings.append(f"⚠️ 指南文件不存在: {guidelines_path}")

        # 检查日志目录
        log_dir = Path(self.log_file).parent
        if not log_dir.exists():
            warnings.append(f"⚠️ 日志目录不存在: {log_dir}，将自动创建")

        return warnings

    def get_retrieval_mode(self) -> str:
        """获取检索模式"""
        return self.retrieval_mode.lower()


# 全局配置实例
settings = Settings()


def get_settings() -> Settings:
    """获取配置实例"""
    return settings


def validate_settings() -> List[str]:
    """运行配置校验"""
    return settings.validate()
