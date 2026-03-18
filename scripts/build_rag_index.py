"""
构建RAG向量索引
将临床指南向量化并存入Chroma数据库
"""

import json
import os
from pathlib import Path
from loguru import logger
from dotenv import load_dotenv

import sys

sys.path.append(str(Path(__file__).parent.parent))

from src.agents.retrieval_agent_vector import VectorRetrievalAgent
from src.config import settings

# 加载环境变量
load_dotenv()


def load_guidelines():
    """加载临床指南数据"""
    guide_file = Path("data/guidelines/clinical_guidelines.json")

    if not guide_file.exists():
        logger.error(f"指南文件不存在: {guide_file}")
        logger.info("请先运行: python scripts/prepare_data.py")
        return []

    with open(guide_file, "r", encoding="utf-8") as f:
        guidelines = json.load(f)

    logger.info(f"已加载 {len(guidelines)} 条指南")
    return guidelines


def prepare_documents(guidelines):
    """准备向量化文档"""
    documents = []

    for guide in guidelines:
        # 每个指南作为一个文档
        documents.append(
            {
                "content": guide["content"],
                "metadata": {
                    "id": guide["id"],
                    "category": guide["metadata"]["category"],
                    "title": guide["title"],
                    "keywords": ",".join(guide["keywords"]),
                },
            }
        )

    logger.info(f"准备向量化 {len(documents)} 个文档")
    return documents


def build_index(documents):
    """构建向量索引"""
    logger.info("开始构建向量索引...")

    # 初始化检索Agent（会自动创建或加载向量数据库）
    retrieval_agent = VectorRetrievalAgent()

    # 添加文档到向量数据库
    retrieval_agent.add_guidelines(documents)

    logger.info(f"✅ 向量索引构建完成!")
    logger.info(f"索引保存位置: {settings.chroma_persist_dir}")


def test_search():
    """测试检索功能"""
    logger.info("\n测试向量检索功能...")

    retrieval_agent = VectorRetrievalAgent()

    # 测试查询
    test_queries = [["咳嗽", "发热"], ["心慌", "心跳快"], ["腹痛"]]

    for symptoms in test_queries:
        logger.info(f"\n查询症状: {symptoms}")
        import asyncio

        results = asyncio.run(retrieval_agent.retrieve_by_symptoms(symptoms, top_k=2))

        for i, result in enumerate(results, 1):
            logger.info(f"  结果{i}: {result['metadata'].get('title', 'N/A')}")
            logger.info(f"    相关度: {result.get('relevance_score', 0):.3f}")


def main():
    """主函数"""
    print("=" * 50)
    print("构建RAG向量索引")
    print("=" * 50)

    # 检查API密钥
    if not os.getenv("OPENAI_API_KEY"):
        logger.error("❌ 未设置 OPENAI_API_KEY 环境变量")
        logger.info("请在 .env 文件中设置 API 密钥")
        return

    # 加载指南数据
    guidelines = load_guidelines()
    if not guidelines:
        return

    # 准备文档
    documents = prepare_documents(guidelines)

    # 构建索引
    build_index(documents)

    # 测试检索
    test_search()

    print("\n" + "=" * 50)
    print("索引构建完成！")
    print("=" * 50)
    print(f"\n向量数据库位置: {settings.chroma_persist_dir}")
    print("\n现在可以启动服务:")
    print("  后端: uvicorn src.main:app --reload")
    print("  前端: streamlit run frontend/app.py")


if __name__ == "__main__":
    main()
