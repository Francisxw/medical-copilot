"""
LlamaIndex 检索 Agent
基于 LlamaIndex RAG Pipeline 的检索实现
"""

from typing import Any, Dict, List, Optional
from loguru import logger

from llama_index.core import VectorStoreIndex
from llama_index.core.postprocessor.types import BaseNodePostprocessor
from llama_index.core.retrievers import VectorIndexRetriever
from llama_index.core.query_engine import RetrieverQueryEngine
from llama_index.core.postprocessor import SimilarityPostprocessor
from llama_index.core.schema import NodeWithScore

from src.utils.llama_index_loader import LlamaIndexDocumentLoader
from src.retrieval import BaseRetrievalStrategy
from src.exceptions import RetrievalError


class LlamaIndexRetrievalAgent(BaseRetrievalStrategy):
    """
    LlamaIndex 检索 Agent

    使用 LlamaIndex 的完整 RAG Pipeline:
    1. 向量检索 (Vector Retrieval)
    2. 重排序 (Reranking)
    3. 后处理 (Post-processing)
    """

    def __init__(
        self,
        collection_name: str = "medical_guidelines",
        persist_dir: str = "./storage/llamaindex",
    ):
        """
        初始化检索 Agent

        Args:
            collection_name: ChromaDB 集合名称
            persist_dir: 索引存储路径
        """
        self.collection_name = collection_name
        self.persist_dir = persist_dir
        self.loader = LlamaIndexDocumentLoader(persist_dir)
        self.index: Optional[VectorStoreIndex] = None
        self.retriever: Optional[VectorIndexRetriever] = None
        self.query_engine: Optional[RetrieverQueryEngine] = None

        logger.info(f"[OK] LlamaIndexRetrievalAgent 初始化 - 集合: {collection_name}")

    async def initialize(self, build_if_missing: bool = True):
        """
        初始化索引和检索器

        Args:
            build_if_missing: 如果索引不存在是否自动构建
        """
        logger.info("[INFO] 初始化 LlamaIndex 索引...")

        # 尝试加载已有索引
        self.index = self.loader.load_index(self.collection_name)

        if self.index is None and build_if_missing:
            logger.info("[INFO] 索引不存在，开始构建新索引...")
            # 从医疗指南构建索引
            self.index = self.loader.full_pipeline(
                source_path="./data/guidelines/clinical_guidelines.json",
                collection_name=self.collection_name,
            )

        if self.index is None:
            raise ValueError("索引加载失败且 build_if_missing=False")

        # 配置检索器
        self._setup_retriever()

        logger.info("[OK] LlamaIndex 检索 Agent 初始化完成")

    def _setup_retriever(self, similarity_top_k: int = 5):
        """
        配置检索器

        Args:
            similarity_top_k: 返回的最相似结果数量
        """
        if self.index is None:
            raise RetrievalError("LlamaIndex 索引尚未初始化")

        index = self.index

        # 创建向量检索器
        self.retriever = VectorIndexRetriever(
            index=index,
            similarity_top_k=similarity_top_k,
        )

        # 配置后处理器（相似度过滤）
        node_postprocessors: list[BaseNodePostprocessor] = [
            SimilarityPostprocessor(similarity_cutoff=0.7)
        ]

        # 创建查询引擎
        self.query_engine = RetrieverQueryEngine(
            retriever=self.retriever,
            node_postprocessors=node_postprocessors,
        )

        logger.info(f"[OK] 检索器配置完成 - top_k: {similarity_top_k}")

    async def retrieve(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        执行检索

        Args:
            query: 查询文本
            top_k: 返回结果数量

        Returns:
            检索结果列表，每个结果包含 content, metadata, score
        """
        if self.query_engine is None:
            await self.initialize()
        if self.query_engine is None:
            raise RetrievalError("LlamaIndex 查询引擎初始化失败")

        query_engine = self.query_engine

        logger.info(f"[INFO] 执行检索 - 查询: {query[:50]}...")

        try:
            # 执行检索
            response = query_engine.query(query)

            # 提取源节点
            source_nodes: List[NodeWithScore] = response.source_nodes

            # 格式化结果
            results = []
            for node_with_score in source_nodes[:top_k]:
                node = node_with_score.node
                score = node_with_score.score

                result = {
                    "content": node.get_content(),
                    "metadata": node.metadata,
                    "score": float(score) if score is not None else 0.0,
                    "node_id": node.id_,
                }
                results.append(result)

            logger.info(f"[OK] 检索完成 - 找到 {len(results)} 个结果")
            return results

        except Exception as e:
            logger.error(f"[ERROR] 检索失败: {e}")
            raise RetrievalError(f"LlamaIndex retrieval failed: {e}") from e

    async def retrieve_by_symptoms(
        self, symptoms: List[str], top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        根据症状列表检索相关指南

        Args:
            symptoms: 症状列表
            top_k: 返回结果数量

        Returns:
            检索结果列表
        """
        # 构建查询文本
        if len(symptoms) == 1:
            query = f"患者症状：{symptoms[0]}"
        else:
            query = f"患者症状：{', '.join(symptoms)}"

        return await self.retrieve(query, top_k)

    async def retrieve_with_filter(
        self, query: str, filters: Dict[str, Any], top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        带过滤条件的检索

        Args:
            query: 查询文本
            filters: 元数据过滤条件，如 {"category": "呼吸系统"}
            top_k: 返回结果数量

        Returns:
            检索结果列表
        """
        if self.retriever is None:
            await self.initialize()
        if self.retriever is None:
            raise RetrievalError("LlamaIndex 检索器初始化失败")

        retriever = self.retriever

        logger.info(f"[INFO] 执行过滤检索 - 查询: {query[:50]}..., 过滤: {filters}")

        try:
            # 构建元数据过滤器
            from llama_index.core.vector_stores import MetadataFilters, ExactMatchFilter

            metadata_filters = MetadataFilters(
                filters=[ExactMatchFilter(key=key, value=value) for key, value in filters.items()]
            )

            # 使用过滤器执行检索
            nodes_with_scores = retriever.retrieve(query)

            # 手动应用过滤器（因为某些向量存储可能不完全支持元数据过滤）
            filtered_results = []
            for node_with_score in nodes_with_scores:
                node = node_with_score.node
                score = node_with_score.score

                # 检查是否满足所有过滤条件
                match = all(node.metadata.get(key) == value for key, value in filters.items())

                if match:
                    filtered_results.append(
                        {
                            "content": node.get_content(),
                            "metadata": node.metadata,
                            "score": float(score) if score is not None else 0.0,
                            "node_id": node.id_,
                        }
                    )

                if len(filtered_results) >= top_k:
                    break

            logger.info(f"[OK] 过滤检索完成 - 找到 {len(filtered_results)} 个结果")
            return filtered_results

        except Exception as e:
            logger.error(f"[ERROR] 过滤检索失败: {e}")
            raise RetrievalError(f"LlamaIndex filtered retrieval failed: {e}") from e

    def get_stats(self) -> Dict[str, Any]:
        """
        获取索引统计信息

        Returns:
            统计信息字典
        """
        if self.index is None:
            return {"status": "uninitialized"}

        try:
            # 获取向量存储
            vector_store = self.index.vector_store

            stats = {
                "status": "ready",
                "collection_name": self.collection_name,
                "persist_dir": self.persist_dir,
            }

            return stats

        except Exception as e:
            logger.error(f"[ERROR] 获取统计信息失败: {e}")
            return {"status": "error", "error": str(e)}

    async def rebuild_index(self, source_path: str = "./data/guidelines/clinical_guidelines.json"):
        """
        重建索引

        Args:
            source_path: 数据源路径
        """
        logger.info("[INFO] 开始重建索引...")

        try:
            self.index = self.loader.full_pipeline(
                source_path=source_path, collection_name=self.collection_name
            )

            self._setup_retriever()

            logger.info("[OK] 索引重建完成")

        except Exception as e:
            logger.error(f"[ERROR] 索引重建失败: {e}")
            raise


# 便捷函数
async def create_llamaindex_retriever(
    collection_name: str = "medical_guidelines",
) -> LlamaIndexRetrievalAgent:
    """便捷函数：创建并初始化 LlamaIndex 检索器"""
    agent = LlamaIndexRetrievalAgent(collection_name)
    await agent.initialize()
    return agent
