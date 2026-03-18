#!/usr/bin/env python
"""
构建 LlamaIndex 向量索引
使用 LlamaIndex 的完整 RAG Pipeline 构建医疗指南索引
"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger
from src.utils.llama_index_loader import LlamaIndexDocumentLoader
from src.config import settings


def check_api_config():
    """检查 API 配置"""
    logger.info("检查 API 配置...")

    if not settings.openai_api_key:
        logger.error("❌ OPENAI_API_KEY 未设置")
        return False

    logger.info(f"✅ LLM API: {settings.openai_model}")
    logger.info(f"✅ Embedding API: {settings.embedding_model}")
    logger.info(f"✅ API Base URL: {settings.openai_base_url}")

    return True


def build_index():
    """构建 LlamaIndex 向量索引"""
    logger.info("=" * 70)
    logger.info("开始构建 LlamaIndex 向量索引")
    logger.info("=" * 70)

    # 检查配置
    if not check_api_config():
        logger.error("配置检查失败，请检查 .env 文件")
        return False

    try:
        # 创建文档加载器
        loader = LlamaIndexDocumentLoader(persist_dir=settings.llamaindex_persist_dir)

        # 构建完整流水线
        index = loader.full_pipeline(
            source_path="./data/guidelines/clinical_guidelines.json",
            collection_name=settings.llamaindex_collection_name,
            chunk_size=settings.llamaindex_chunk_size,
            chunk_overlap=settings.llamaindex_chunk_overlap,
            parser_type="sentence",  # 使用句子分块
        )

        logger.info("=" * 70)
        logger.info("✅ LlamaIndex 索引构建完成！")
        logger.info("=" * 70)
        logger.info(f"存储路径: {settings.llamaindex_persist_dir}")
        logger.info(f"集合名称: {settings.llamaindex_collection_name}")

        return True

    except FileNotFoundError:
        logger.error("❌ 未找到医疗指南数据文件")
        logger.info("请先运行: python scripts/prepare_data.py")
        return False

    except Exception as e:
        logger.error(f"❌ 索引构建失败: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_search():
    """测试检索功能"""
    logger.info("\n" + "=" * 70)
    logger.info("测试 LlamaIndex 检索功能")
    logger.info("=" * 70)

    from src.agents.retrieval_agent_llamaindex import LlamaIndexRetrievalAgent

    async def do_test():
        agent = LlamaIndexRetrievalAgent(
            collection_name=settings.llamaindex_collection_name,
            persist_dir=settings.llamaindex_persist_dir,
        )

        # 初始化（加载已有索引）
        await agent.initialize(build_if_missing=False)

        # 测试查询
        test_queries = [
            ["咳嗽", "发热"],
            ["心悸", "胸闷"],
            ["腹痛", "恶心"],
        ]

        for symptoms in test_queries:
            logger.info(f"\n测试查询: {symptoms}")
            results = await agent.retrieve_by_symptoms(symptoms, top_k=2)

            if results:
                for i, result in enumerate(results, 1):
                    logger.info(
                        f"  {i}. {result['metadata'].get('title', 'Unknown')} | 得分: {result['score']:.3f}"
                    )
            else:
                logger.info("  未找到相关结果")

    try:
        asyncio.run(do_test())
        logger.info("\n✅ 检索测试完成")
    except Exception as e:
        logger.error(f"❌ 检索测试失败: {e}")


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="构建 LlamaIndex 向量索引")
    parser.add_argument("--test", action="store_true", help="构建后测试检索功能")
    parser.add_argument("--skip-build", action="store_true", help="跳过构建，仅测试")

    args = parser.parse_args()

    # 构建索引
    if not args.skip_build:
        success = build_index()
        if not success:
            sys.exit(1)

    # 测试检索
    if args.test or args.skip_build:
        test_search()


if __name__ == "__main__":
    main()
