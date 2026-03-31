"""
文档仓储接口定义
定义文档和版本管理的仓储契约，支持多租户隔离和版本控制
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Protocol, Any


@dataclass(frozen=True)
class DocumentRecord:
    """文档记录数据类"""

    document_id: str
    tenant_id: str
    kb_id: str
    logical_name: str
    current_version: int
    created_at: datetime


@dataclass(frozen=True)
class DocumentVersionRecord:
    """文档版本记录数据类"""

    version_id: str
    document_id: str
    tenant_id: str
    kb_id: str
    version: int
    content_hash: str
    original_filename: str
    stored_filename: str
    collection_name: str
    uploaded_at: datetime
    is_active: bool
    replaced_by: Optional[str] = None
    chunk_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


class DocumentRepository(Protocol):
    """文档仓储协议 - 定义文档和版本管理的统一接口"""

    def get_document(self, document_id: str) -> Optional[DocumentRecord]:
        """
        获取文档记录

        Args:
            document_id: 文档ID

        Returns:
            文档记录，不存在则返回None
        """
        ...

    def find_active_document_by_logical_name(
        self, tenant_id: str, kb_id: str, logical_name: str
    ) -> Optional[DocumentRecord]:
        """
        通过逻辑名称查找活动文档

        Args:
            tenant_id: 租户ID
            kb_id: 知识库ID
            logical_name: 逻辑名称

        Returns:
            活动文档记录，不存在则返回None
        """
        ...

    def create_document(self, tenant_id: str, kb_id: str, logical_name: str) -> DocumentRecord:
        """
        创建新文档

        Args:
            tenant_id: 租户ID
            kb_id: 知识库ID
            logical_name: 逻辑名称

        Returns:
            创建的文档记录
        """
        ...

    def get_active_version(self, document_id: str) -> Optional[DocumentVersionRecord]:
        """
        获取文档的当前活动版本

        Args:
            document_id: 文档ID

        Returns:
            活动版本记录，不存在则返回None
        """
        ...

    def get_latest_version(self, document_id: str) -> Optional[DocumentVersionRecord]:
        """
        获取文档的最新版本（无论是否活动）

        Args:
            document_id: 文档ID

        Returns:
            最新版本记录，不存在则返回None
        """
        ...

    def find_version_by_hash(
        self, tenant_id: str, kb_id: str, content_hash: str
    ) -> Optional[DocumentVersionRecord]:
        """
        通过内容哈希查找版本

        Args:
            tenant_id: 租户ID
            kb_id: 知识库ID
            content_hash: 内容哈希值

        Returns:
            版本记录，不存在则返回None
        """
        ...

    def create_version(self, version: DocumentVersionRecord) -> None:
        """
        创建新版本

        Args:
            version: 版本记录
        """
        ...

    def deactivate_version(self, version_id: str, replaced_by: Optional[str]) -> None:
        """
        停用指定版本

        Args:
            version_id: 版本ID
            replaced_by: 替换版本ID
        """
        ...

    def set_document_current_version(self, document_id: str, version: int) -> None:
        """
        设置文档的当前版本号

        Args:
            document_id: 文档ID
            version: 版本号
        """
        ...

    def get_document_versions(self, document_id: str) -> List[DocumentVersionRecord]:
        """
        获取文档的所有版本记录，按版本号升序排列

        Args:
            document_id: 文档ID

        Returns:
            版本记录列表，按版本号升序排列；文档不存在时返回空列表
        """
        ...


class InMemoryDocumentRepository:
    """
    内存文档仓储实现。
    使用字典存储文档和版本记录，支持多租户隔离和版本控制。
    """

    def __init__(self):
        # 存储文档记录，键为 document_id
        self._documents: Dict[str, DocumentRecord] = {}
        # 存储版本记录，键为 version_id
        self._versions: Dict[str, DocumentVersionRecord] = {}
        # 辅助索引：按租户/知识库/逻辑名称查找文档
        self._logical_name_index: Dict[
            tuple[str, str, str], str
        ] = {}  # (tenant_id, kb_id, logical_name) -> document_id
        # 辅助索引：按租户/知识库/内容哈希查找版本
        self._content_hash_index: Dict[
            tuple[str, str, str], str
        ] = {}  # (tenant_id, kb_id, content_hash) -> version_id
        # 辅助索引：文档ID到版本ID列表
        self._document_versions_index: Dict[str, List[str]] = {}  # document_id -> [version_id, ...]
        # 辅助索引：文档ID到最新版本ID
        self._latest_version_index: Dict[str, str] = {}

    def get_document(self, document_id: str) -> Optional[DocumentRecord]:
        """获取文档记录，不存在则返回None"""
        return self._documents.get(document_id)

    def find_active_document_by_logical_name(
        self, tenant_id: str, kb_id: str, logical_name: str
    ) -> Optional[DocumentRecord]:
        """通过逻辑名称查找活动文档"""
        key = (tenant_id, kb_id, logical_name)
        document_id = self._logical_name_index.get(key)
        if not document_id:
            return None
        document = self._documents.get(document_id)
        if not document:
            return None
        # 检查是否有活动版本
        active_version = self.get_active_version(document_id)
        if active_version is None:
            return None
        return document

    def create_document(self, tenant_id: str, kb_id: str, logical_name: str) -> DocumentRecord:
        """创建新文档"""
        # 检查是否已存在相同逻辑名称的文档
        key = (tenant_id, kb_id, logical_name)
        existing_doc_id = self._logical_name_index.get(key)
        if existing_doc_id:
            # 返回已存在的文档
            return self._documents[existing_doc_id]

        document_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        document = DocumentRecord(
            document_id=document_id,
            tenant_id=tenant_id,
            kb_id=kb_id,
            logical_name=logical_name,
            current_version=0,  # 初始版本为0，直到创建第一个版本
            created_at=now,
        )
        self._documents[document_id] = document
        self._logical_name_index[key] = document_id
        self._document_versions_index[document_id] = []
        return document

    def get_active_version(self, document_id: str) -> Optional[DocumentVersionRecord]:
        """获取文档的当前活动版本"""
        version_ids = self._document_versions_index.get(document_id, [])
        for version_id in version_ids:
            version = self._versions.get(version_id)
            if version and version.is_active:
                return version
        return None

    def get_latest_version(self, document_id: str) -> Optional[DocumentVersionRecord]:
        """获取文档的最新版本（无论是否活动）"""
        latest_version_id = self._latest_version_index.get(document_id)
        if latest_version_id is not None:
            latest_version = self._versions.get(latest_version_id)
            if latest_version is not None:
                return latest_version

        version_ids = self._document_versions_index.get(document_id, [])
        if not version_ids:
            return None

        versions = [self._versions[vid] for vid in version_ids if vid in self._versions]
        if not versions:
            return None

        latest_version = max(versions, key=lambda v: v.version)
        self._latest_version_index[document_id] = latest_version.version_id
        return latest_version

    def find_version_by_hash(
        self, tenant_id: str, kb_id: str, content_hash: str
    ) -> Optional[DocumentVersionRecord]:
        """通过内容哈希查找版本"""
        key = (tenant_id, kb_id, content_hash)
        version_id = self._content_hash_index.get(key)
        if not version_id:
            return None
        return self._versions.get(version_id)

    def create_version(self, version: DocumentVersionRecord) -> None:
        """创建新版本"""
        latest_before = self.get_latest_version(version.document_id)

        # 存储版本记录
        self._versions[version.version_id] = version
        # 更新文档版本索引
        if version.document_id not in self._document_versions_index:
            self._document_versions_index[version.document_id] = []
        self._document_versions_index[version.document_id].append(version.version_id)
        if latest_before is None or version.version >= latest_before.version:
            self._latest_version_index[version.document_id] = version.version_id
        elif version.document_id not in self._latest_version_index:
            self._latest_version_index[version.document_id] = latest_before.version_id
        # 更新内容哈希索引
        key = (version.tenant_id, version.kb_id, version.content_hash)
        self._content_hash_index[key] = version.version_id
        # 如果这是第一个版本，更新文档的当前版本号
        document = self._documents.get(version.document_id)
        if document and document.current_version == 0:
            # 创建新的DocumentRecord，因为frozen=True
            new_document = DocumentRecord(
                document_id=document.document_id,
                tenant_id=document.tenant_id,
                kb_id=document.kb_id,
                logical_name=document.logical_name,
                current_version=version.version,
                created_at=document.created_at,
            )
            self._documents[version.document_id] = new_document

    def deactivate_version(self, version_id: str, replaced_by: Optional[str]) -> None:
        """停用指定版本"""
        version = self._versions.get(version_id)
        if not version:
            return
        # 创建新的版本记录，因为frozen=True
        new_version = DocumentVersionRecord(
            version_id=version.version_id,
            document_id=version.document_id,
            tenant_id=version.tenant_id,
            kb_id=version.kb_id,
            version=version.version,
            content_hash=version.content_hash,
            original_filename=version.original_filename,
            stored_filename=version.stored_filename,
            collection_name=version.collection_name,
            uploaded_at=version.uploaded_at,
            is_active=False,
            replaced_by=replaced_by,
            chunk_count=version.chunk_count,
            metadata=version.metadata,
        )
        self._versions[version_id] = new_version

    def set_document_current_version(self, document_id: str, version: int) -> None:
        """设置文档的当前版本号"""
        document = self._documents.get(document_id)
        if not document:
            return
        # 创建新的DocumentRecord
        new_document = DocumentRecord(
            document_id=document.document_id,
            tenant_id=document.tenant_id,
            kb_id=document.kb_id,
            logical_name=document.logical_name,
            current_version=version,
            created_at=document.created_at,
        )
        self._documents[document_id] = new_document

    def get_document_versions(self, document_id: str) -> List[DocumentVersionRecord]:
        """获取文档的所有版本记录，按版本号升序排列"""
        version_ids = self._document_versions_index.get(document_id, [])
        if not version_ids:
            return []
        # 获取所有版本记录
        versions = []
        for version_id in version_ids:
            version = self._versions.get(version_id)
            if version:
                versions.append(version)
        # 按版本号升序排序
        versions.sort(key=lambda v: v.version)
        return versions
