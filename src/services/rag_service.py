"""RAG 文档上传与索引服务（适配器模式）。

此模块提供向后兼容的 RAGService 类，内部委托给 VersionedTenantRAGService。
保持原有公共接口不变，同时利用新的多租户、版本控制功能。
"""

from __future__ import annotations
from dataclasses import asdict, dataclass
from pathlib import Path
import re
from typing import Optional, Tuple

from loguru import logger

from src.rag.service import VersionedTenantRAGService, RAGCoreServiceError


# 支持的文件扩展名
SUPPORTED_EXTS = frozenset({".json", ".pdf", ".txt"})
# 最大上传文件大小：10MB
MAX_UPLOAD_BYTES = 10 * 1024 * 1024


class RAGServiceError(Exception):
    """RAG 服务异常基类。"""

    pass


@dataclass(frozen=True)
class RAGUploadResult:
    """RAG 上传结果数据类。"""

    filename: str
    chunks: int
    collection_name: str


class RAGService:
    """RAG 文档上传与索引服务（适配器）。

    保持原有公共接口不变，内部委托给 VersionedTenantRAGService。
    支持将 legacy scope 映射到 tenant_id 和 kb_id。
    """

    def __init__(self, loader=None):
        self._loader = loader
        self._core_service: Optional[VersionedTenantRAGService] = None

    @property
    def document_loader(self):
        """懒加载文档加载器（保持向后兼容）。"""
        if self._loader is None:
            from src.utils.llama_index_loader import LlamaIndexDocumentLoader

            self._loader = LlamaIndexDocumentLoader()
        return self._loader

    @property
    def loader(self):
        """向后兼容的 loader 属性。"""
        return self.document_loader

    @property
    def core_service(self) -> VersionedTenantRAGService:
        """懒加载核心服务。"""
        if self._core_service is None:
            self._core_service = VersionedTenantRAGService(loader=self._loader)
        return self._core_service

    def upload_and_index(
        self,
        file_bytes: bytes,
        filename: str,
        collection_name: str,
    ) -> dict:
        """
        上传文件并建立向量索引（向后兼容接口）。

        Args:
            file_bytes: 文件二进制内容
            filename: 原始文件名（会被清理）
            collection_name: 目标向量集合名称

        Returns:
            包含文件名、分块数、集合名的字典

        Raises:
            RAGServiceError: 验证失败或处理错误
        """
        # 1. 清理文件名，防止路径穿越
        safe_name = self._sanitize_filename(filename)
        ext = Path(safe_name).suffix.lower()

        # 2. 验证上传内容
        self._validate_upload(file_bytes, ext)

        # 3. 将 legacy scope 映射到 tenant_id 和 kb_id
        tenant_id, kb_id = self._map_legacy_scope_to_tenant_kb(collection_name)

        # 4. 委托给核心服务
        try:
            result = self.core_service.upload_and_index(
                file_bytes=file_bytes,
                filename=safe_name,
                tenant_id=tenant_id,
                kb_id=kb_id,
                metadata={"legacy_collection_name": collection_name},
            )
        except RAGCoreServiceError as e:
            raise RAGServiceError(str(e)) from e

        # 5. 转换为 legacy 响应格式，保留原始 collection_name
        legacy_result = RAGUploadResult(
            filename=safe_name,
            chunks=result.chunks,
            collection_name=collection_name,  # 保持调用方提供的 collection_name
        )
        logger.info("RAG 索引完成（适配器）: {}", legacy_result)
        return asdict(legacy_result)

    @staticmethod
    def _map_legacy_scope_to_tenant_kb(collection_name: str) -> Tuple[str, str]:
        """
        将 legacy scope 映射为 tenant_id 和 kb_id。

        如果 collection_name 匹配 canonical 格式 `tenant_{tenant_id}__kb_{kb_id}`，
        则直接解析；否则使用确定性映射。

        Args:
            collection_name: legacy scope 或 canonical collection 名称

        Returns:
            (tenant_id, kb_id) 元组
        """
        pattern = r"^tenant_(.+)__kb_(.+)$"
        match = re.match(pattern, collection_name)
        if match:
            tenant_id, kb_id = match.groups()
            return tenant_id, kb_id

        return collection_name, "default"

    @staticmethod
    def _parse_collection_name(collection_name: str) -> Tuple[str, str]:
        """Backward-compatible wrapper for older tests and callers."""

        return RAGService._map_legacy_scope_to_tenant_kb(collection_name)

    def _validate_upload(self, file_bytes: bytes, ext: str) -> None:
        """
        验证上传文件。

        Raises:
            RAGServiceError: 验证失败
        """
        if not file_bytes:
            raise RAGServiceError("上传的文件为空")
        if len(file_bytes) > MAX_UPLOAD_BYTES:
            raise RAGServiceError("文件过大，超过 10MB 限制")
        if ext not in SUPPORTED_EXTS:
            raise RAGServiceError(f"不支持的文件格式: {ext}，仅支持 {SUPPORTED_EXTS}")

    def _sanitize_filename(self, filename: str) -> str:
        """
        清理文件名，防止路径穿越攻击。

        只保留 basename，丢弃所有路径成分。
        如果清理后文件名为空或是特殊路径，抛出异常。

        Args:
            filename: 原始文件名

        Returns:
            清理后的安全文件名

        Raises:
            RAGServiceError: 文件名非法
        """
        # 只保留文件名，丢弃路径成分
        safe_name = Path(filename).name
        if not safe_name or safe_name in {".", ".."}:
            raise RAGServiceError("非法文件名")
        return safe_name
