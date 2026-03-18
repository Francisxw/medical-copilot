#!/usr/bin/env python
"""测试 Embedding API 配置"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import settings
from loguru import logger


def test_embedding():
    """测试 Embedding API"""
    logger.info("测试 Embedding 配置...")

    # 直接读取环境变量
    import os
    from dotenv import load_dotenv

    load_dotenv()

    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("EMBEDDING_BASE_URL") or os.getenv("OPENAI_BASE_URL")
    model = os.getenv("EMBEDDING_MODEL", "text-embedding-ada-002")

    logger.info(f"API Key from env: {api_key[:10] if api_key else 'None'}...")
    logger.info(f"API Key from settings: {settings.openai_api_key[:10]}...")
    logger.info(f"Base URL: {base_url}")
    logger.info(f"Model: {model}")

    from langchain_openai import OpenAIEmbeddings

    embed_model = OpenAIEmbeddings(
        model=model,
        openai_api_key=api_key,
        openai_api_base=base_url,
    )

    # 测试嵌入
    test_texts = ["这是一个测试", "另一个测试"]
    try:
        embeddings = embed_model.embed_documents(test_texts)
        logger.info(f"✅ Embedding 测试成功！生成了 {len(embeddings)} 个嵌入向量")
        logger.info(f"向量维度: {len(embeddings[0])}")
    except Exception as e:
        logger.error(f"❌ Embedding 测试失败: {e}")


if __name__ == "__main__":
    test_embedding()
