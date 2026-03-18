"""
向量检索Agent - 使用 OpenRouter Embedding API
基于向量相似度检索临床指南
"""

from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import Chroma
from typing import List, Dict, Any
from loguru import logger
import os
from pathlib import Path

from src.config import get_settings

settings = get_settings()


class VectorRetrievalAgent:
    """
    向量检索Agent - 基于 OpenRouter Embedding API
    """

    def __init__(self):
        # 初始化 Embeddings（支持 OpenRouter / OpenAI）
        self.embeddings = OpenAIEmbeddings(
            model=settings.embedding_model,
            api_key=settings.openai_api_key,
            base_url=settings.embedding_base_url,
        )
        self.vectorstore = None
        self._load_or_create_vectorstore()

    def _load_or_create_vectorstore(self):
        """加载或创建向量数据库"""
        persist_dir = settings.chroma_persist_dir

        # 确保目录存在
        Path(persist_dir).mkdir(parents=True, exist_ok=True)

        if os.path.exists(persist_dir) and os.listdir(persist_dir):
            logger.info(f"加载已有向量数据库: {persist_dir}")
            try:
                self.vectorstore = Chroma(
                    persist_directory=persist_dir,
                    embedding_function=self.embeddings,
                    collection_name="clinical_guidelines",
                )
                logger.info("✅ 向量数据库加载成功")
                return
            except Exception as e:
                logger.warning(f"加载向量数据库失败: {e}")

        logger.info("创建新的向量数据库...")
        self.vectorstore = Chroma(
            embedding_function=self.embeddings,
            collection_name="clinical_guidelines",
            persist_directory=persist_dir,
        )

    async def retrieve(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """
        检索相关临床指南

        Args:
            query: 查询文本
            top_k: 返回前K个结果

        Returns:
            检索到的指南列表
        """
        try:
            if self.vectorstore is None:
                logger.warning("向量数据库未初始化")
                return []

            logger.info(f"向量检索: {query[:50]}...")

            # 执行相似度搜索
            results = self.vectorstore.similarity_search_with_score(
                query=query, k=top_k
            )

            # 格式化结果（Chroma 返回的是距离，需要转换为相似度）
            guidelines = []
            for doc, distance in results:
                # 将距离转换为相似度分数（距离越小，相似度越高）
                similarity_score = 1 / (1 + distance)

                guidelines.append(
                    {
                        "content": doc.page_content,
                        "metadata": doc.metadata,
                        "relevance_score": float(similarity_score),
                    }
                )

            logger.info(f"✅ 检索到 {len(guidelines)} 条指南")
            return guidelines

        except Exception as e:
            logger.error(f"❌ 向量检索失败: {str(e)}")
            return []

    async def retrieve_by_symptoms(
        self, symptoms: List[str], top_k: int = 3
    ) -> List[Dict[str, Any]]:
        """
        基于症状列表检索指南

        Args:
            symptoms: 症状列表
            top_k: 返回前K个结果

        Returns:
            检索到的指南
        """
        # 组合症状为查询文本
        query = " ".join(symptoms)
        return await self.retrieve(query, top_k=top_k)

    def add_guidelines(self, guidelines: List[Dict[str, Any]]):
        """
        添加指南到向量数据库

        Args:
            guidelines: 指南列表
        """
        try:
            if self.vectorstore is None:
                logger.error("向量数据库未初始化")
                return

            texts = [g["content"] for g in guidelines]
            metadatas = [g.get("metadata", {}) for g in guidelines]

            logger.info(f"正在向量化 {len(texts)} 条指南...")

            # 添加到向量数据库
            self.vectorstore.add_texts(texts=texts, metadatas=metadatas)

            # 持久化
            self.vectorstore.persist()

            logger.info(f"✅ 成功添加 {len(guidelines)} 条指南到向量数据库")

        except Exception as e:
            logger.error(f"❌ 添加指南失败: {str(e)}")

    def clear_database(self):
        """清空向量数据库"""
        try:
            import shutil

            persist_dir = settings.chroma_persist_dir
            if os.path.exists(persist_dir):
                shutil.rmtree(persist_dir)
                logger.info("✅ 向量数据库已清空")
        except Exception as e:
            logger.error(f"❌ 清空数据库失败: {str(e)}")


# 测试代码
if __name__ == "__main__":
    import asyncio

    async def test():
        agent = VectorRetrievalAgent()

        # 测试检索
        results = await agent.retrieve_by_symptoms(["咳嗽", "发热"])
        print(f"\n检索到 {len(results)} 条指南:")
        for i, guideline in enumerate(results, 1):
            print(f"\n指南 {i}:")
            print(f"标题: {guideline['metadata'].get('title', 'N/A')}")
            print(f"相关度: {guideline['relevance_score']:.3f}")
            print(f"内容: {guideline['content'][:100]}...")

    asyncio.run(test())
