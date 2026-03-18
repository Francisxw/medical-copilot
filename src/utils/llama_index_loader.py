"""
LlamaIndex 文档加载和处理模块
提供完整的文档加载、解析、分块和索引功能
"""

import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from loguru import logger

from llama_index.core import (
    VectorStoreIndex,
    SimpleDirectoryReader,
    Document,
    Settings,
    StorageContext,
)
from llama_index.core.node_parser import (
    SentenceSplitter,
    TokenTextSplitter,
    MarkdownNodeParser,
    HTMLNodeParser,
)
from llama_index.core.schema import Node, BaseNode, NodeWithScore
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.llms.openai import OpenAI
from llama_index.core.embeddings import resolve_embed_model

import chromadb

from src.config import settings


class LlamaIndexDocumentLoader:
    """
    LlamaIndex 文档加载器
    支持多种数据源、自动分块、元数据注入
    """

    def __init__(self, persist_dir: str = "./storage/llamaindex"):
        self.persist_dir = Path(persist_dir)
        self.persist_dir.mkdir(parents=True, exist_ok=True)

        # 配置 LlamaIndex 全局设置
        self._setup_settings()

        logger.info(
            f"[OK] LlamaIndexDocumentLoader 初始化完成，存储路径: {persist_dir}"
        )

    def _setup_settings(self):
        """配置 LlamaIndex 全局设置"""
        # 检查是否是 OpenRouter 或 DeepSeek（非标准 OpenAI）
        base_url = settings.embedding_base_url or settings.openai_base_url
        is_openrouter = "openrouter" in base_url.lower()

        if is_openrouter:
            # 使用 LangChain Embedding 适配器
            from langchain_openai import OpenAIEmbeddings
            from llama_index.embeddings.langchain import LangchainEmbedding

            lc_embed_model = OpenAIEmbeddings(
                model=settings.embedding_model,
                openai_api_key=settings.openai_api_key,
                openai_api_base=base_url,
            )
            embed_model = LangchainEmbedding(lc_embed_model)
            logger.info(
                f"[OK] 使用 LangChain Embedding 适配器: {settings.embedding_model}"
            )
        else:
            # 使用标准 OpenAI Embedding
            embed_model = OpenAIEmbedding(
                model=settings.embedding_model,
                api_key=settings.openai_api_key,
                api_base=base_url,
            )

        Settings.embed_model = embed_model

        # LLM 模型（用于高级 RAG 功能）
        # 同样检查是否需要使用 LangChain 适配器
        if is_openrouter or "deepseek" in settings.openai_model.lower():
            from langchain_openai import ChatOpenAI
            from llama_index.llms.langchain import LangChainLLM

            lc_llm = ChatOpenAI(
                model=settings.openai_model,
                openai_api_key=settings.openai_api_key,
                openai_api_base=settings.openai_base_url,
                temperature=settings.temperature,
            )
            llm = LangChainLLM(llm=lc_llm)
            logger.info(f"[OK] 使用 LangChain LLM 适配器: {settings.openai_model}")
        else:
            llm = OpenAI(
                model=settings.openai_model,
                api_key=settings.openai_api_key,
                api_base=settings.openai_base_url,
                temperature=settings.temperature,
            )

        Settings.llm = llm
   
        logger.info(
            f"[OK] LlamaIndex 设置完成 - Embedding: {settings.embedding_model}, LLM: {settings.openai_model}"
        )

    def load_from_json(
        self, json_path: str, text_key: str = "content", metadata_keys: List[str] = None
    ) -> List[Document]:
        """
        从 JSON 文件加载文档

        Args:
            json_path: JSON 文件路径
            text_key: 作为文档正文的字段名
            metadata_keys: 要包含为元数据的字段名列表

        Returns:
            Document 列表
        """
        logger.info(f"[INFO] 从 JSON 加载文档: {json_path}")

        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        documents = []
        for item in data:
            # 提取正文
            text = item.get(text_key, "")
            if not text:
                continue

            # 构建元数据
            metadata = {"source": json_path}
            if metadata_keys:
                for key in metadata_keys:
                    if key in item:
                        # 处理列表类型的值（如 keywords）
                        value = item[key]
                        if isinstance(value, list):
                            value = ",".join(str(v) for v in value)
                        metadata[key] = value
            else:
                # 默认包含所有非文本字段
                for key, value in item.items():
                    if key != text_key and not isinstance(value, (dict, list)):
                        metadata[key] = value
                    elif key != text_key and isinstance(value, list):
                        metadata[key] = ",".join(str(v) for v in value)

            doc = Document(text=text, metadata=metadata, id_=item.get("id", None))
            documents.append(doc)

        logger.info(f"[OK] 成功加载 {len(documents)} 个文档")
        return documents

    def load_from_directory(
        self, dir_path: str, required_exts: List[str] = None
    ) -> List[Document]:
        """
        从目录批量加载文档（支持多种格式）

        Args:
            dir_path: 目录路径
            required_exts: 需要的文件扩展名列表（如 ['.pdf', '.md']）

        Returns:
            Document 列表
        """
        logger.info(f"[INFO] 从目录加载文档: {dir_path}")

        reader = SimpleDirectoryReader(
            input_dir=dir_path,
            required_exts=required_exts,
            recursive=True,
        )

        documents = reader.load_data()
        logger.info(f"[OK] 成功加载 {len(documents)} 个文档")

        return documents

    def load_medical_guidelines(
        self, guidelines_path: str = "./data/guidelines/clinical_guidelines.json"
    ) -> List[Document]:
        """
        专门加载医疗指南数据

        Args:
            guidelines_path: 指南 JSON 文件路径

        Returns:
            Document 列表
        """
        logger.info(f"[INFO] 加载医疗指南: {guidelines_path}")

        documents = self.load_from_json(
            json_path=guidelines_path,
            text_key="content",
            metadata_keys=["id", "category", "title", "keywords"],
        )

        # 添加额外的医疗领域元数据
        for doc in documents:
            doc.metadata["doc_type"] = "clinical_guideline"
            doc.metadata["domain"] = "medical"

        return documents

    def create_nodes(
        self,
        documents: List[Document],
        chunk_size: int = 512,
        chunk_overlap: int = 50,
        parser_type: str = "sentence",
    ) -> List[BaseNode]:
        """
        将文档切分为节点（分块）

        Args:
            documents: 文档列表
            chunk_size: 分块大小
            chunk_overlap: 块间重叠大小
            parser_type: 解析器类型 ('sentence', 'token', 'markdown')

        Returns:
            Node 列表
        """
        logger.info(
            f"[INFO] 开始分块 - 类型: {parser_type}, 大小: {chunk_size}, 重叠: {chunk_overlap}"
        )

        # 根据类型选择解析器
        if parser_type == "sentence":
            parser = SentenceSplitter(
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
            )
        elif parser_type == "token":
            parser = TokenTextSplitter(
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
            )
        elif parser_type == "markdown":
            parser = MarkdownNodeParser()
        else:
            parser = SentenceSplitter(
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
            )

        # 执行分块
        nodes = parser.get_nodes_from_documents(documents)

        logger.info(f"[OK] 分块完成 - 共 {len(nodes)} 个节点")

        # 显示分块统计
        if nodes:
            avg_length = sum(len(node.text) for node in nodes) / len(nodes)
            logger.info(f"[INFO] 平均节点长度: {avg_length:.0f} 字符")

        return nodes

    def build_index(
        self, nodes: List[BaseNode], collection_name: str = "medical_guidelines"
    ) -> VectorStoreIndex:
        """
        构建向量索引

        Args:
            nodes: 节点列表
            collection_name: ChromaDB 集合名称

        Returns:
            VectorStoreIndex
        """
        logger.info(f"[INFO] 构建向量索引 - 集合: {collection_name}")

        # 初始化 ChromaDB
        chroma_client = chromadb.PersistentClient(path=str(self.persist_dir / "chroma"))
        chroma_collection = chroma_client.get_or_create_collection(collection_name)

        # 创建向量存储
        vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
        storage_context = StorageContext.from_defaults(vector_store=vector_store)

        # 构建索引
        index = VectorStoreIndex(
            nodes=nodes,
            storage_context=storage_context,
        )

        logger.info(f"[OK] 索引构建完成 - 集合: {collection_name}")
        return index

    def load_index(
        self, collection_name: str = "medical_guidelines"
    ) -> Optional[VectorStoreIndex]:
        """
        加载已有的向量索引

        Args:
            collection_name: ChromaDB 集合名称

        Returns:
            VectorStoreIndex 或 None
        """
        try:
            logger.info(f"[INFO] 加载索引 - 集合: {collection_name}")

            # 初始化 ChromaDB
            chroma_client = chromadb.PersistentClient(
                path=str(self.persist_dir / "chroma")
            )
            chroma_collection = chroma_client.get_or_create_collection(collection_name)

            # 创建向量存储
            vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
            storage_context = StorageContext.from_defaults(vector_store=vector_store)

            # 从存储加载索引
            index = VectorStoreIndex.from_vector_store(
                vector_store=vector_store,
                storage_context=storage_context,
            )

            logger.info(f"[OK] 索引加载成功 - 集合: {collection_name}")
            return index

        except Exception as e:
            logger.error(f"[ERROR] 索引加载失败: {e}")
            return None

    def full_pipeline(
        self,
        source_path: str,
        collection_name: str = "medical_guidelines",
        chunk_size: int = 512,
        chunk_overlap: int = 50,
        parser_type: str = "sentence",
    ) -> VectorStoreIndex:
        """
        完整的数据处理流水线

        Args:
            source_path: 数据源路径（文件或目录）
            collection_name: 集合名称
            chunk_size: 分块大小
            chunk_overlap: 块间重叠
            parser_type: 解析器类型

        Returns:
            VectorStoreIndex
        """
        logger.info("=" * 60)
        logger.info("[INFO] 启动 LlamaIndex 完整数据处理流水线")
        logger.info("=" * 60)

        # 1. 加载文档
        source_path = Path(source_path)
        if source_path.is_file() and source_path.suffix == ".json":
            documents = self.load_from_json(str(source_path))
        elif source_path.is_dir():
            documents = self.load_from_directory(str(source_path))
        else:
            # 默认尝试加载医疗指南
            documents = self.load_medical_guidelines(str(source_path))

        if not documents:
            raise ValueError("没有加载到任何文档")

        # 2. 分块
        nodes = self.create_nodes(
            documents=documents,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            parser_type=parser_type,
        )

        if not nodes:
            raise ValueError("分块后没有生成任何节点")

        # 3. 构建索引
        index = self.build_index(nodes, collection_name)

        logger.info("=" * 60)
        logger.info("[OK] LlamaIndex 流水线执行完成")
        logger.info("=" * 60)

        return index


# 便捷函数
def load_documents(source: str, **kwargs) -> List[Document]:
    """便捷函数：加载文档"""
    loader = LlamaIndexDocumentLoader()

    if source.endswith(".json"):
        return loader.load_from_json(source, **kwargs)
    else:
        return loader.load_from_directory(source, **kwargs)


def load_medical_guidelines(
    guidelines_path: str = "./data/guidelines/clinical_guidelines.json",
) -> List[Document]:
    """便捷函数：加载医疗指南"""
    loader = LlamaIndexDocumentLoader()
    return loader.load_medical_guidelines(guidelines_path)


def build_index_from_documents(
    documents: List[Document],
    persist_dir: str = "./storage/llamaindex",
    collection_name: str = "medical_guidelines",
    chunk_size: int = 512,
    chunk_overlap: int = 50,
) -> VectorStoreIndex:
    """便捷函数：从文档构建索引"""
    loader = LlamaIndexDocumentLoader(persist_dir)
    nodes = loader.create_nodes(documents, chunk_size, chunk_overlap)
    return loader.build_index(nodes, collection_name)
