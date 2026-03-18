"""
LlamaIndex Property Graph Index 医疗指南检索 Agent。
使用 GraphRAG 实现混合检索（向量 + 知识图谱）。
"""

from typing import List, Dict, Any, Optional
from loguru import logger
from pathlib import Path
import json

from src.config import get_settings

settings = get_settings()


class LlamaGraphRAGAgent:
    """基于 LlamaIndex Property Graph Index 的医疗指南检索。"""

    def __init__(self):
        self.index = None
        self._initialized = False
        self.persist_dir = Path(settings.llamagraph_persist_dir)
        self._simple_fallback = None

    @staticmethod
    def _normalize_embedding_model(model_name: str) -> str:
        """规范化 embedding 模型名，兼容 provider/model 写法。"""
        candidate = (model_name or "").strip()
        if "/" in candidate:
            candidate = candidate.split("/")[-1]
        return candidate or "text-embedding-3-small"

    async def initialize(self):
        """初始化或加载已有索引。"""
        if self._initialized:
            return

        if self.persist_dir.exists() and any(self.persist_dir.iterdir()):
            try:
                self.index = self._load_index(self.persist_dir)
                self._initialized = True
                logger.info("[OK] 加载已有 LlamaGraph 索引")
                return
            except Exception as e:
                logger.warning(f"加载 LlamaGraph 索引失败，将尝试重建: {str(e)}")

        logger.info("未检测到可用 LlamaGraph 索引，等待首次构建")

    def _load_index(self, index_path: Path):
        """从存储加载索引。"""
        from llama_index.core import StorageContext, load_index_from_storage

        storage_context = StorageContext.from_defaults(persist_dir=str(index_path))
        return load_index_from_storage(storage_context)

    def _load_guidelines_from_file(self) -> List[Dict[str, Any]]:
        """从默认指南文件读取数据。"""
        guide_file = Path("data/guidelines/clinical_guidelines.json")
        if not guide_file.exists():
            logger.warning("指南文件不存在，请先运行: python scripts/prepare_data.py")
            return []

        with open(guide_file, "r", encoding="utf-8") as f:
            return json.load(f)

    async def load_guidelines(self, guidelines: List[Dict[str, Any]]):
        """加载医疗指南并构建 Property Graph Index。"""
        if not guidelines:
            logger.warning("传入的指南为空，跳过构建")
            return

        try:
            from llama_index.core import Document
            from llama_index.core.indices.property_graph import PropertyGraphIndex
            from llama_index.llms.openai import OpenAI
            from llama_index.embeddings.openai import OpenAIEmbedding
        except Exception as e:
            logger.error(f"LlamaIndex 依赖未安装或导入失败: {str(e)}")
            return

        logger.info(f"开始构建 LlamaGraph 索引，共 {len(guidelines)} 条指南")

        documents = []
        for guideline in guidelines:
            metadata = guideline.get("metadata", {})
            doc = Document(
                text=guideline.get("content", ""),
                metadata={
                    "id": guideline.get("id"),
                    "title": guideline.get("title"),
                    "category": guideline.get("category") or metadata.get("category"),
                    "keywords": guideline.get("keywords", []),
                },
            )
            documents.append(doc)

        try:
            llm = OpenAI(
                model=settings.openai_model,
                api_key=settings.openai_api_key,
                api_base=settings.openai_base_url,
                temperature=0.1,
            )

            embed_model = OpenAIEmbedding(
                model=self._normalize_embedding_model(settings.embedding_model),
                api_key=settings.openai_api_key,
                api_base=settings.embedding_base_url,
            )
        except Exception as e:
            logger.error(f"初始化 LLM/Embedding 失败，使用关键词检索降级: {str(e)}")
            self.index = None
            self._initialized = False
            return

        self.persist_dir.mkdir(parents=True, exist_ok=True)

        try:
            import asyncio

            self.index = await asyncio.to_thread(
                PropertyGraphIndex.from_documents,
                documents,
                llm=llm,
                embed_model=embed_model,
                show_progress=False,
            )
        except Exception as e:
            logger.error(f"构建 LlamaGraph 索引失败: {str(e)}")
            self.index = None
            self._initialized = False
            return

        self.index.storage_context.persist(persist_dir=str(self.persist_dir))
        self._initialized = True
        logger.info("[OK] LlamaGraph 索引构建完成并已持久化")

    async def _ensure_index(self):
        """确保索引可用：优先加载，缺失则自动构建。"""
        await self.initialize()
        if self.index is not None:
            return

        guidelines = self._load_guidelines_from_file()
        if not guidelines:
            return

        await self.load_guidelines(guidelines)

    def _retrieve_nodes(self, query: str, top_k: int):
        """执行检索，优先混合模式，失败时降级到相似度检索。"""
        retriever = None

        try:
            retriever = self.index.as_retriever(
                mode="hybrid",
                similarity_top_k=top_k,
                graph_store_query_depth=2,
            )
        except Exception:
            try:
                retriever = self.index.as_retriever(similarity_top_k=top_k)
            except Exception:
                retriever = self.index.as_retriever()

        return retriever.retrieve(query)

    async def retrieve_by_symptoms(
        self,
        symptoms: List[str],
        top_k: int = 3,
    ) -> List[Dict[str, Any]]:
        """基于症状列表进行 GraphRAG 检索。"""
        if not symptoms:
            return []

        await self._ensure_index()
        if self.index is None:
            logger.warning("LlamaGraph 索引不可用，降级到关键词检索")
            if self._simple_fallback is None:
                from src.agents.retrieval_agent_simple import SimpleRetrievalAgent

                self._simple_fallback = SimpleRetrievalAgent()
            results = await self._simple_fallback.retrieve_by_symptoms(
                symptoms, top_k=top_k
            )
            for item in results:
                item["source"] = "fallback_simple"
            return results

        query = f"患者症状: {', '.join(symptoms)}。请查找相关诊断和治疗方案。"

        try:
            nodes = self._retrieve_nodes(query=query, top_k=top_k)
        except Exception as e:
            logger.error(f"LlamaGraph 检索失败，降级到关键词检索: {str(e)}")
            if self._simple_fallback is None:
                from src.agents.retrieval_agent_simple import SimpleRetrievalAgent

                self._simple_fallback = SimpleRetrievalAgent()
            results = await self._simple_fallback.retrieve_by_symptoms(
                symptoms, top_k=top_k
            )
            for item in results:
                item["source"] = "fallback_simple"
            return results

        results: List[Dict[str, Any]] = []
        for node in nodes:
            text = ""
            metadata: Dict[str, Any] = {}
            score = getattr(node, "score", 1.0)

            wrapped_node: Optional[Any] = getattr(node, "node", None)
            if wrapped_node is not None:
                text = getattr(wrapped_node, "text", "") or ""
                metadata = getattr(wrapped_node, "metadata", {}) or {}
            else:
                text = getattr(node, "text", "") or ""
                metadata = getattr(node, "metadata", {}) or {}

            if not text:
                continue

            results.append(
                {
                    "content": text,
                    "metadata": metadata,
                    "relevance_score": float(score),
                    "source": "llamagraph_hybrid",
                }
            )

        logger.info(f"GraphRAG 检索到 {len(results)} 条相关指南")
        return results[:top_k]
