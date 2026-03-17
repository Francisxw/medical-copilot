"""
配置管理模块
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional
import os


class Settings(BaseSettings):
    """应用配置"""

    # LLM API (用于对话、生成、质控)
    openai_api_key: str
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-3.5-turbo"

    # Embedding API (用于向量检索)
    embedding_base_url: Optional[str] = None  # 默认使用 openai_base_url
    embedding_model: str = "text-embedding-ada-002"

    # Retrieval mode: simple | vector | llamagraph
    retrieval_mode: str = "simple"

    # LlamaGraph storage
    llamagraph_persist_dir: str = "./storage/llamagraph"

    # Graph store backend: memory | nebula
    graph_store_mode: str = "memory"

    # Vector Database
    chroma_persist_dir: str = "./data/chroma_db"

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_reload: bool = True
    request_timeout: int = 120  # 请求超时时间（秒）

    # Logging
    log_level: str = "INFO"
    log_file: str = "./logs/app.log"

    # Application
    max_conversation_turns: int = 10
    max_revision_iterations: int = 3
    temperature: float = 0.7

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # 忽略额外的环境变量
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # 如果没有单独设置 embedding_base_url，使用 openai_base_url
        if self.embedding_base_url is None:
            self.embedding_base_url = self.openai_base_url


# 全局配置实例
settings = Settings()


def get_settings() -> Settings:
    """获取配置实例"""
    return settings
