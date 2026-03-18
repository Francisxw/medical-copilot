"""
构建向量索引脚本 - 使用 OpenRouter Embedding API
将临床指南向量化并存入 Chroma 数据库
"""

import json
import os
import sys
from pathlib import Path
from loguru import logger
from dotenv import load_dotenv

# 添加项目路径
sys.path.append(str(Path(__file__).parent.parent))

from src.config import settings

# 加载环境变量
load_dotenv()


def check_api_config():
    """检查 API 配置"""
    logger.info("检查 API 配置...")

    if not os.getenv("OPENAI_API_KEY"):
        logger.error("❌ 未设置 OPENAI_API_KEY 环境变量")
        logger.info("\n请编辑 .env 文件，填入你的 OpenRouter API 密钥:")
        logger.info("OPENAI_API_KEY=sk-or-v1-xxxxx")
        logger.info("EMBEDDING_BASE_URL=https://openrouter.ai/api/v1")
        logger.info("EMBEDDING_MODEL=openai/text-embedding-ada-002")
        return False

    logger.info(f"✅ API 密钥已配置")
    logger.info(
        f"📍 Embedding API: {os.getenv('EMBEDDING_BASE_URL', settings.openai_base_url)}"
    )
    logger.info(f"🤖 模型: {os.getenv('EMBEDDING_MODEL', 'text-embedding-ada-002')}")

    return True


def load_guidelines():
    """加载临床指南数据"""
    guide_file = Path("data/guidelines/clinical_guidelines.json")

    if not guide_file.exists():
        logger.error(f"❌ 指南文件不存在: {guide_file}")
        logger.info("请先运行: python scripts/prepare_data.py")
        return []

    with open(guide_file, "r", encoding="utf-8") as f:
        guidelines = json.load(f)

    logger.info(f"✅ 已加载 {len(guidelines)} 条指南")
    return guidelines


def prepare_documents(guidelines):
    """准备向量化文档"""
    documents = []

    for guide in guidelines:
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
    logger.info("\n" + "=" * 50)
    logger.info("开始构建向量索引")
    logger.info("=" * 50)

    # 动态导入（避免在导入时就检查配置）
    from src.agents.retrieval_agent_vector import VectorRetrievalAgent

    # 初始化检索Agent
    retrieval_agent = VectorRetrievalAgent()

    # 清空旧数据（如果需要重新构建）
    logger.info("\n是否清空旧数据重新构建？")
    logger.info("如果向量数据库已存在，建议先清空")

    # 添加文档到向量数据库
    logger.info(f"\n正在向量化 {len(documents)} 条指南...")
    logger.info("这可能需要 1-2 分钟，请稍候...")

    retrieval_agent.add_guidelines(documents)

    logger.info("\n" + "=" * 50)
    logger.info("✅ 向量索引构建完成！")
    logger.info("=" * 50)
    logger.info(f"\n向量数据库位置: {settings.chroma_persist_dir}")


def test_search():
    """测试检索功能"""
    logger.info("\n" + "=" * 50)
    logger.info("测试向量检索功能")
    logger.info("=" * 50)

    from src.agents.retrieval_agent_vector import VectorRetrievalAgent

    retrieval_agent = VectorRetrievalAgent()

    import asyncio

    # 测试查询
    test_queries = [["咳嗽", "发热"], ["心慌", "心跳快"], ["腹痛", "呕吐"]]

    for symptoms in test_queries:
        logger.info(f"\n查询症状: {symptoms}")
        results = asyncio.run(retrieval_agent.retrieve_by_symptoms(symptoms, top_k=2))

        if results:
            for i, result in enumerate(results, 1):
                logger.info(f"  📄 结果{i}: {result['metadata']['title']}")
                logger.info(f"     相似度: {result['relevance_score']:.3f}")
        else:
            logger.warning("  ⚠️  未检索到相关指南")


def main():
    """主函数"""
    print("\n" + "=" * 50)
    print("构建向量索引 - OpenRouter Embedding")
    print("=" * 50 + "\n")

    # 检查配置
    if not check_api_config():
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
    print("全部完成！")
    print("=" * 50)
    print(f"\n向量数据库: {settings.chroma_persist_dir}")
    print("\n下一步:")
    print("  启动后端: uvicorn src.main:app --reload")
    print("  启动前端: streamlit run frontend/app.py")


if __name__ == "__main__":
    main()
