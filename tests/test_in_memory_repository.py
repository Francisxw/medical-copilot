"""
单元测试：内存文档仓储实现
验证 InMemoryDocumentRepository 符合 DocumentRepository 协议，
并测试文档创建、查找、版本管理等核心行为。
"""

import pytest
from datetime import datetime

from src.rag.repository import DocumentRecord, DocumentVersionRecord
from src.rag import InMemoryDocumentRepository


@pytest.fixture
def repo():
    """提供一个空的内存仓储实例"""
    return InMemoryDocumentRepository()


@pytest.fixture
def sample_version():
    """提供一个示例版本记录"""
    return DocumentVersionRecord(
        version_id="v1",
        document_id="doc1",
        tenant_id="tenant1",
        kb_id="kb1",
        version=1,
        content_hash="hash123",
        original_filename="test.txt",
        stored_filename="stored_test.txt",
        collection_name="col1",
        uploaded_at=datetime.utcnow(),
        is_active=True,
        replaced_by=None,
        chunk_count=10,
        metadata={"size": 1024},
    )


class TestDocumentCreationAndLookup:
    """测试文档创建和查找功能"""

    def test_create_document(self, repo):
        """创建文档并验证返回的记录"""
        doc = repo.create_document("tenant1", "kb1", "doc1.txt")
        assert doc.document_id is not None
        assert doc.tenant_id == "tenant1"
        assert doc.kb_id == "kb1"
        assert doc.logical_name == "doc1.txt"
        assert doc.current_version == 0
        assert isinstance(doc.created_at, datetime)

    def test_get_document(self, repo):
        """通过ID获取文档"""
        doc = repo.create_document("tenant1", "kb1", "doc1.txt")
        fetched = repo.get_document(doc.document_id)
        assert fetched == doc

    def test_get_document_nonexistent(self, repo):
        """获取不存在的文档返回None"""
        assert repo.get_document("nonexistent") is None

    def test_find_active_document_by_logical_name(self, repo):
        """通过逻辑名称查找活动文档（有活动版本）"""
        doc = repo.create_document("tenant1", "kb1", "doc1.txt")
        # 创建一个活动版本，使用正确的 document_id
        version = DocumentVersionRecord(
            version_id="v1",
            document_id=doc.document_id,
            tenant_id="tenant1",
            kb_id="kb1",
            version=1,
            content_hash="hash123",
            original_filename="test.txt",
            stored_filename="stored_test.txt",
            collection_name="col1",
            uploaded_at=datetime.utcnow(),
            is_active=True,
            replaced_by=None,
            chunk_count=10,
            metadata={"size": 1024},
        )
        repo.create_version(version)
        # 设置文档当前版本
        repo.set_document_current_version(doc.document_id, version.version)
        found = repo.find_active_document_by_logical_name("tenant1", "kb1", "doc1.txt")
        assert found is not None
        assert found.document_id == doc.document_id

    def test_find_active_document_by_logical_name_no_active_version(self, repo):
        """通过逻辑名称查找活动文档（无活动版本）"""
        doc = repo.create_document("tenant1", "kb1", "doc1.txt")
        # 没有创建版本，因此没有活动版本
        found = repo.find_active_document_by_logical_name("tenant1", "kb1", "doc1.txt")
        assert found is None

    def test_find_active_document_by_logical_name_wrong_tenant(self, repo):
        """通过逻辑名称查找活动文档（错误租户）"""
        doc = repo.create_document("tenant1", "kb1", "doc1.txt")
        found = repo.find_active_document_by_logical_name("tenant2", "kb1", "doc1.txt")
        assert found is None

    def test_create_document_duplicate_logical_name(self, repo):
        """创建重复逻辑名称的文档应返回已存在的文档"""
        doc1 = repo.create_document("tenant1", "kb1", "doc1.txt")
        doc2 = repo.create_document("tenant1", "kb1", "doc1.txt")
        assert doc1.document_id == doc2.document_id


class TestVersionManagement:
    """测试版本管理功能"""

    def test_create_version(self, repo, sample_version):
        """创建版本并验证存储"""
        repo.create_version(sample_version)
        # 通过内容哈希查找
        found = repo.find_version_by_hash("tenant1", "kb1", "hash123")
        assert found == sample_version

    def test_get_active_version(self, repo, sample_version):
        """获取活动版本"""
        repo.create_version(sample_version)
        active = repo.get_active_version(sample_version.document_id)
        assert active == sample_version

    def test_get_active_version_none(self, repo):
        """获取活动版本（无版本）"""
        assert repo.get_active_version("doc1") is None

    def test_get_latest_version(self, repo):
        """获取最新版本（按版本号）"""
        doc = repo.create_document("tenant1", "kb1", "doc1.txt")
        v1 = DocumentVersionRecord(
            version_id="v1",
            document_id=doc.document_id,
            tenant_id="tenant1",
            kb_id="kb1",
            version=1,
            content_hash="hash1",
            original_filename="test.txt",
            stored_filename="stored1.txt",
            collection_name="col1",
            uploaded_at=datetime.utcnow(),
            is_active=False,
            replaced_by=None,
            chunk_count=5,
            metadata={},
        )
        v2 = DocumentVersionRecord(
            version_id="v2",
            document_id=doc.document_id,
            tenant_id="tenant1",
            kb_id="kb1",
            version=2,
            content_hash="hash2",
            original_filename="test.txt",
            stored_filename="stored2.txt",
            collection_name="col1",
            uploaded_at=datetime.utcnow(),
            is_active=True,
            replaced_by=None,
            chunk_count=10,
            metadata={},
        )
        repo.create_version(v1)
        repo.create_version(v2)
        latest = repo.get_latest_version(doc.document_id)
        assert latest == v2

    def test_find_version_by_hash(self, repo, sample_version):
        """通过内容哈希查找版本"""
        repo.create_version(sample_version)
        found = repo.find_version_by_hash("tenant1", "kb1", "hash123")
        assert found == sample_version

    def test_find_version_by_hash_nonexistent(self, repo):
        """查找不存在的哈希返回None"""
        assert repo.find_version_by_hash("tenant1", "kb1", "nonexistent") is None

    def test_deactivate_version(self, repo, sample_version):
        """停用版本并设置replaced_by"""
        repo.create_version(sample_version)
        repo.deactivate_version(sample_version.version_id, "v2")
        # 重新获取版本
        found = repo.find_version_by_hash("tenant1", "kb1", "hash123")
        assert found.is_active is False
        assert found.replaced_by == "v2"

    def test_set_document_current_version(self, repo):
        """设置文档的当前版本号"""
        doc = repo.create_document("tenant1", "kb1", "doc1.txt")
        assert doc.current_version == 0
        repo.set_document_current_version(doc.document_id, 5)
        updated = repo.get_document(doc.document_id)
        assert updated.current_version == 5


class TestTenantIsolation:
    """测试租户隔离"""

    def test_content_hash_scoped_by_tenant_kb(self, repo):
        """内容哈希查找应受租户/知识库限制"""
        v1 = DocumentVersionRecord(
            version_id="v1",
            document_id="doc1",
            tenant_id="tenant1",
            kb_id="kb1",
            version=1,
            content_hash="hash123",
            original_filename="test.txt",
            stored_filename="stored1.txt",
            collection_name="col1",
            uploaded_at=datetime.utcnow(),
            is_active=True,
            replaced_by=None,
            chunk_count=5,
            metadata={},
        )
        v2 = DocumentVersionRecord(
            version_id="v2",
            document_id="doc2",
            tenant_id="tenant2",
            kb_id="kb1",
            version=1,
            content_hash="hash123",  # 相同哈希
            original_filename="test.txt",
            stored_filename="stored2.txt",
            collection_name="col2",
            uploaded_at=datetime.utcnow(),
            is_active=True,
            replaced_by=None,
            chunk_count=5,
            metadata={},
        )
        repo.create_version(v1)
        repo.create_version(v2)
        # 查找租户1的版本
        found1 = repo.find_version_by_hash("tenant1", "kb1", "hash123")
        assert found1.version_id == "v1"
        # 查找租户2的版本
        found2 = repo.find_version_by_hash("tenant2", "kb1", "hash123")
        assert found2.version_id == "v2"
        # 查找不存在的租户
        assert repo.find_version_by_hash("tenant3", "kb1", "hash123") is None

    def test_logical_name_scoped_by_tenant_kb(self, repo):
        """逻辑名称查找应受租户/知识库限制"""
        doc1 = repo.create_document("tenant1", "kb1", "doc.txt")
        doc2 = repo.create_document("tenant2", "kb1", "doc.txt")
        # 创建活动版本
        v1 = DocumentVersionRecord(
            version_id="v1",
            document_id=doc1.document_id,
            tenant_id="tenant1",
            kb_id="kb1",
            version=1,
            content_hash="hash1",
            original_filename="test.txt",
            stored_filename="stored1.txt",
            collection_name="col1",
            uploaded_at=datetime.utcnow(),
            is_active=True,
            replaced_by=None,
            chunk_count=5,
            metadata={},
        )
        repo.create_version(v1)
        repo.set_document_current_version(doc1.document_id, 1)
        # 查找租户1的文档
        found1 = repo.find_active_document_by_logical_name("tenant1", "kb1", "doc.txt")
        assert found1.document_id == doc1.document_id
        # 查找租户2的文档（无活动版本）
        found2 = repo.find_active_document_by_logical_name("tenant2", "kb1", "doc.txt")
        assert found2 is None


class TestVersionHistoryRetrieval:
    """测试版本历史检索功能"""

    def test_get_document_versions_empty(self, repo):
        """获取不存在文档的版本历史应返回空列表"""
        versions = repo.get_document_versions("nonexistent")
        assert versions == []

    def test_get_document_versions_single(self, repo):
        """获取单个版本的文档历史"""
        doc = repo.create_document("tenant1", "kb1", "doc1.txt")
        v1 = DocumentVersionRecord(
            version_id="v1",
            document_id=doc.document_id,
            tenant_id="tenant1",
            kb_id="kb1",
            version=1,
            content_hash="hash1",
            original_filename="test.txt",
            stored_filename="stored1.txt",
            collection_name="col1",
            uploaded_at=datetime.utcnow(),
            is_active=True,
            replaced_by=None,
            chunk_count=5,
            metadata={},
        )
        repo.create_version(v1)
        versions = repo.get_document_versions(doc.document_id)
        assert len(versions) == 1
        assert versions[0] == v1

    def test_get_document_versions_ordered(self, repo):
        """版本历史应按版本号升序排列"""
        doc = repo.create_document("tenant1", "kb1", "doc1.txt")
        # 创建多个版本，按乱序添加
        v3 = DocumentVersionRecord(
            version_id="v3",
            document_id=doc.document_id,
            tenant_id="tenant1",
            kb_id="kb1",
            version=3,
            content_hash="hash3",
            original_filename="test.txt",
            stored_filename="stored3.txt",
            collection_name="col1",
            uploaded_at=datetime.utcnow(),
            is_active=True,
            replaced_by=None,
            chunk_count=15,
            metadata={},
        )
        v1 = DocumentVersionRecord(
            version_id="v1",
            document_id=doc.document_id,
            tenant_id="tenant1",
            kb_id="kb1",
            version=1,
            content_hash="hash1",
            original_filename="test.txt",
            stored_filename="stored1.txt",
            collection_name="col1",
            uploaded_at=datetime.utcnow(),
            is_active=False,
            replaced_by="v2",
            chunk_count=5,
            metadata={},
        )
        v2 = DocumentVersionRecord(
            version_id="v2",
            document_id=doc.document_id,
            tenant_id="tenant1",
            kb_id="kb1",
            version=2,
            content_hash="hash2",
            original_filename="test.txt",
            stored_filename="stored2.txt",
            collection_name="col1",
            uploaded_at=datetime.utcnow(),
            is_active=False,
            replaced_by="v3",
            chunk_count=10,
            metadata={},
        )
        # 按乱序添加
        repo.create_version(v3)
        repo.create_version(v1)
        repo.create_version(v2)
        versions = repo.get_document_versions(doc.document_id)
        assert len(versions) == 3
        # 验证按版本号升序排列
        assert versions[0].version_id == "v1"
        assert versions[1].version_id == "v2"
        assert versions[2].version_id == "v3"
        # 验证版本号顺序
        assert versions[0].version == 1
        assert versions[1].version == 2
        assert versions[2].version == 3

    def test_get_document_versions_complete_history(self, repo):
        """版本历史应包含所有版本，无论活动状态"""
        doc = repo.create_document("tenant1", "kb1", "doc1.txt")
        v1 = DocumentVersionRecord(
            version_id="v1",
            document_id=doc.document_id,
            tenant_id="tenant1",
            kb_id="kb1",
            version=1,
            content_hash="hash1",
            original_filename="test.txt",
            stored_filename="stored1.txt",
            collection_name="col1",
            uploaded_at=datetime.utcnow(),
            is_active=False,
            replaced_by="v2",
            chunk_count=5,
            metadata={},
        )
        v2 = DocumentVersionRecord(
            version_id="v2",
            document_id=doc.document_id,
            tenant_id="tenant1",
            kb_id="kb1",
            version=2,
            content_hash="hash2",
            original_filename="test.txt",
            stored_filename="stored2.txt",
            collection_name="col1",
            uploaded_at=datetime.utcnow(),
            is_active=True,
            replaced_by=None,
            chunk_count=10,
            metadata={},
        )
        repo.create_version(v1)
        repo.create_version(v2)
        versions = repo.get_document_versions(doc.document_id)
        assert len(versions) == 2
        # 验证包含所有版本
        version_ids = {v.version_id for v in versions}
        assert version_ids == {"v1", "v2"}
        # 验证包含活动和非活动版本
        active_versions = [v for v in versions if v.is_active]
        inactive_versions = [v for v in versions if not v.is_active]
        assert len(active_versions) == 1
        assert len(inactive_versions) == 1

    def test_get_document_versions_different_documents(self, repo):
        """不同文档的版本历史应独立"""
        doc1 = repo.create_document("tenant1", "kb1", "doc1.txt")
        doc2 = repo.create_document("tenant1", "kb1", "doc2.txt")
        v1_doc1 = DocumentVersionRecord(
            version_id="v1_doc1",
            document_id=doc1.document_id,
            tenant_id="tenant1",
            kb_id="kb1",
            version=1,
            content_hash="hash1",
            original_filename="test1.txt",
            stored_filename="stored1.txt",
            collection_name="col1",
            uploaded_at=datetime.utcnow(),
            is_active=True,
            replaced_by=None,
            chunk_count=5,
            metadata={},
        )
        v1_doc2 = DocumentVersionRecord(
            version_id="v1_doc2",
            document_id=doc2.document_id,
            tenant_id="tenant1",
            kb_id="kb1",
            version=1,
            content_hash="hash2",
            original_filename="test2.txt",
            stored_filename="stored2.txt",
            collection_name="col1",
            uploaded_at=datetime.utcnow(),
            is_active=True,
            replaced_by=None,
            chunk_count=5,
            metadata={},
        )
        repo.create_version(v1_doc1)
        repo.create_version(v1_doc2)
        # 获取doc1的版本历史
        versions_doc1 = repo.get_document_versions(doc1.document_id)
        assert len(versions_doc1) == 1
        assert versions_doc1[0].version_id == "v1_doc1"
        # 获取doc2的版本历史
        versions_doc2 = repo.get_document_versions(doc2.document_id)
        assert len(versions_doc2) == 1
        assert versions_doc2[0].version_id == "v1_doc2"
