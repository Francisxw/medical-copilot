"""
Integration tests for the RAG upload/index flow through the API boundary.

These tests exercise the end-to-end flow using:
- Real service instances (RAGService adapter and VersionedTenantRAGService)
- Shared in-memory repository for stateful verification
- Mocked document loaders to avoid external dependencies
- TestClient for API boundary testing

Test coverage:
1. Legacy /api/rag/upload happy path through adapterized RAGService
2. Versioned /api/rag/upload-versioned with dedup_mode=skip
3. Tenant isolation across versioned uploads
4. Version history progression with dedup_mode=new_version
"""

import pytest
from types import SimpleNamespace
from unittest.mock import MagicMock
from fastapi.testclient import TestClient

from src.main import app
from src.rag import InMemoryDocumentRepository
from src.rag.service import VersionedTenantRAGService, DedupMode, UploadIndexResult
from src.services.rag_service import RAGService
from src.api.routes import get_rag_service, get_versioned_rag_service


def _mock_doc() -> SimpleNamespace:
    """Create a mock document with metadata attribute."""
    return SimpleNamespace(metadata={})


def _mock_node(text: str) -> SimpleNamespace:
    """Create a mock node with text and metadata attributes."""
    return SimpleNamespace(text=text, metadata={})


@pytest.fixture
def shared_repository():
    """Provide a shared in-memory repository for stateful integration tests."""
    return InMemoryDocumentRepository()


@pytest.fixture
def mock_loader():
    """Provide a mocked document loader."""
    mock = MagicMock()
    mock.load_from_json.return_value = [_mock_doc()]
    mock.load_from_directory.return_value = [_mock_doc()]
    mock.create_nodes.return_value = [_mock_node("chunk-1"), _mock_node("chunk-2")]
    mock.build_index.return_value = None
    return mock


@pytest.fixture
def versioned_service(shared_repository, mock_loader):
    """Provide a VersionedTenantRAGService with shared repository and mocked loader."""
    return VersionedTenantRAGService(repository=shared_repository, loader=mock_loader)


@pytest.fixture
def legacy_service(versioned_service):
    """Provide a RAGService adapter pointing at the same core service."""
    service = RAGService()
    service._core_service = versioned_service
    service._loader = versioned_service._loader
    return service


@pytest.fixture
def client_with_real_services(legacy_service, versioned_service):
    """Provide a TestClient with real service instances injected."""
    app.dependency_overrides[get_rag_service] = lambda: legacy_service
    app.dependency_overrides[get_versioned_rag_service] = lambda: versioned_service
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_rag_service, None)
        app.dependency_overrides.pop(get_versioned_rag_service, None)


class TestLegacyUploadIntegration:
    """Integration tests for the legacy /api/rag/upload endpoint."""

    def test_legacy_upload_happy_path(self, client_with_real_services, shared_repository):
        """Test successful upload through legacy endpoint with real service chain."""
        response = client_with_real_services.post(
            "/api/rag/upload",
            files={"file": ("test.txt", b"hello world content", "text/plain")},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["filename"] == "test.txt"
        assert data["chunks"] == 2  # From mock_loader returning 2 nodes
        assert data["collection_name"] == "user-uploads"

        # Verify the current legacy compatibility mapping in the adapter.
        docs = list(shared_repository._documents.values())
        assert len(docs) == 1
        doc = docs[0]
        assert doc.tenant_id == "user-uploads"
        assert doc.kb_id == "default"
        assert doc.logical_name == "test.txt"
        assert doc.current_version == 1

    def test_legacy_upload_creates_version_record(
        self, client_with_real_services, shared_repository
    ):
        """Test that legacy upload creates a version record in the repository."""
        response = client_with_real_services.post(
            "/api/rag/upload",
            files={"file": ("document.txt", b"test content", "text/plain")},
        )

        assert response.status_code == 200

        # Verify version record exists
        docs = list(shared_repository._documents.values())
        assert len(docs) == 1
        active_version = shared_repository.get_active_version(docs[0].document_id)
        assert active_version is not None
        assert active_version.is_active is True
        assert active_version.chunk_count == 2
        assert active_version.collection_name == "tenant_user-uploads__kb_default"


class TestVersionedUploadDedupIntegration:
    """Integration tests for versioned upload with deduplication behavior."""

    def test_versioned_upload_first_then_skip_duplicate(
        self, client_with_real_services, shared_repository, mock_loader
    ):
        """Test first upload succeeds, second upload with same content skips indexing."""
        file_content = b"identical content for dedup test"

        # First upload
        response1 = client_with_real_services.post(
            "/api/rag/upload-versioned",
            files={"file": ("doc.txt", file_content, "text/plain")},
            headers={"X-Tenant-ID": "tenant-a", "X-KB-ID": "kb-1"},
        )

        assert response1.status_code == 200
        data1 = response1.json()
        assert data1["dedup_hit"] is False
        assert data1["message"] == "Upload indexed successfully"
        first_doc_id = data1["document_id"]
        first_version_id = data1["version_id"]
        first_build_calls = mock_loader.build_index.call_count

        # Second upload with identical content and dedup_mode=skip (default)
        response2 = client_with_real_services.post(
            "/api/rag/upload-versioned",
            files={"file": ("doc.txt", file_content, "text/plain")},
            headers={"X-Tenant-ID": "tenant-a", "X-KB-ID": "kb-1"},
        )

        assert response2.status_code == 200
        data2 = response2.json()
        assert data2["dedup_hit"] is True
        assert data2["message"] == "Duplicate content detected; skipped indexing"
        assert data2["document_id"] == first_doc_id
        assert data2["version_id"] == first_version_id

        # Verify build_index was not called again (short-circuited)
        assert mock_loader.build_index.call_count == first_build_calls

        # Verify repository state: still only one version
        doc = shared_repository.get_document(first_doc_id)
        assert doc.current_version == 1
        versions = shared_repository.get_document_versions(first_doc_id)
        assert len(versions) == 1

    def test_versioned_upload_different_content_creates_new_version(
        self, client_with_real_services, shared_repository
    ):
        """Test uploading different content to same logical name creates new version."""
        # First upload
        response1 = client_with_real_services.post(
            "/api/rag/upload-versioned",
            files={"file": ("doc.txt", b"version 1 content", "text/plain")},
            headers={"X-Tenant-ID": "tenant-a", "X-KB-ID": "kb-1"},
        )

        assert response1.status_code == 200
        data1 = response1.json()
        first_doc_id = data1["document_id"]
        first_version_id = data1["version_id"]

        # Second upload with different content
        response2 = client_with_real_services.post(
            "/api/rag/upload-versioned",
            files={"file": ("doc.txt", b"version 2 content", "text/plain")},
            headers={"X-Tenant-ID": "tenant-a", "X-KB-ID": "kb-1"},
            params={"dedup_mode": "new_version"},
        )

        assert response2.status_code == 200
        data2 = response2.json()
        assert data2["dedup_hit"] is False  # Different content, not a dedup hit
        assert data2["document_id"] == first_doc_id  # Same document
        assert data2["version_id"] != first_version_id  # Different version

        # Verify repository state: two versions
        doc = shared_repository.get_document(first_doc_id)
        assert doc.current_version == 2
        versions = shared_repository.get_document_versions(first_doc_id)
        assert len(versions) == 2
        assert versions[0].version == 1
        assert versions[1].version == 2


class TestTenantIsolationIntegration:
    """Integration tests for tenant isolation across versioned uploads."""

    def test_same_content_different_tenants_creates_separate_documents(
        self, client_with_real_services, shared_repository
    ):
        """Test that same content uploaded to different tenants creates separate documents."""
        file_content = b"shared medical guideline content"

        # Upload to tenant-a
        response_a = client_with_real_services.post(
            "/api/rag/upload-versioned",
            files={"file": ("guideline.txt", file_content, "text/plain")},
            headers={"X-Tenant-ID": "tenant-a", "X-KB-ID": "kb-1"},
        )

        assert response_a.status_code == 200
        data_a = response_a.json()

        # Upload same content to tenant-b
        response_b = client_with_real_services.post(
            "/api/rag/upload-versioned",
            files={"file": ("guideline.txt", file_content, "text/plain")},
            headers={"X-Tenant-ID": "tenant-b", "X-KB-ID": "kb-1"},
        )

        assert response_b.status_code == 200
        data_b = response_b.json()

        # Verify different document IDs (tenant isolation)
        assert data_a["document_id"] != data_b["document_id"]

        # Verify different collection names
        assert data_a["collection_name"] == "tenant_tenant-a__kb_kb-1"
        assert data_b["collection_name"] == "tenant_tenant-b__kb_kb-1"

        # Verify both have dedup_hit=False (different tenants, no cross-tenant dedup)
        assert data_a["dedup_hit"] is False
        assert data_b["dedup_hit"] is False

        # Verify repository state: two separate documents
        doc_a = shared_repository.get_document(data_a["document_id"])
        doc_b = shared_repository.get_document(data_b["document_id"])
        assert doc_a.tenant_id == "tenant-a"
        assert doc_b.tenant_id == "tenant-b"
        assert doc_a.kb_id == "kb-1"
        assert doc_b.kb_id == "kb-1"

    def test_same_tenant_different_kbs_creates_separate_documents(
        self, client_with_real_services, shared_repository
    ):
        """Test that same content uploaded to different KBs within same tenant creates separate documents."""
        file_content = b"knowledge base content"

        # Upload to kb-1
        response_kb1 = client_with_real_services.post(
            "/api/rag/upload-versioned",
            files={"file": ("kb_doc.txt", file_content, "text/plain")},
            headers={"X-Tenant-ID": "tenant-a", "X-KB-ID": "kb-1"},
        )

        assert response_kb1.status_code == 200
        data_kb1 = response_kb1.json()

        # Upload same content to kb-2
        response_kb2 = client_with_real_services.post(
            "/api/rag/upload-versioned",
            files={"file": ("kb_doc.txt", file_content, "text/plain")},
            headers={"X-Tenant-ID": "tenant-a", "X-KB-ID": "kb-2"},
        )

        assert response_kb2.status_code == 200
        data_kb2 = response_kb2.json()

        # Verify different document IDs (KB isolation)
        assert data_kb1["document_id"] != data_kb2["document_id"]

        # Verify different collection names
        assert data_kb1["collection_name"] == "tenant_tenant-a__kb_kb-1"
        assert data_kb2["collection_name"] == "tenant_tenant-a__kb_kb-2"

    def test_dedup_is_scoped_to_tenant_kb(self, client_with_real_services, shared_repository):
        """Test that dedup detection is scoped to tenant and KB."""
        file_content = b"content for scoped dedup test"

        # Upload to tenant-a/kb-1
        response1 = client_with_real_services.post(
            "/api/rag/upload-versioned",
            files={"file": ("doc.txt", file_content, "text/plain")},
            headers={"X-Tenant-ID": "tenant-a", "X-KB-ID": "kb-1"},
        )
        assert response1.status_code == 200
        data1 = response1.json()
        assert data1["dedup_hit"] is False

        # Upload same content to tenant-a/kb-2 (different KB, should not dedup)
        response2 = client_with_real_services.post(
            "/api/rag/upload-versioned",
            files={"file": ("doc.txt", file_content, "text/plain")},
            headers={"X-Tenant-ID": "tenant-a", "X-KB-ID": "kb-2"},
        )
        assert response2.status_code == 200
        data2 = response2.json()
        assert data2["dedup_hit"] is False  # Different KB, no dedup
        assert data2["document_id"] != data1["document_id"]

        # Upload same content to tenant-b/kb-1 (different tenant, should not dedup)
        response3 = client_with_real_services.post(
            "/api/rag/upload-versioned",
            files={"file": ("doc.txt", file_content, "text/plain")},
            headers={"X-Tenant-ID": "tenant-b", "X-KB-ID": "kb-1"},
        )
        assert response3.status_code == 200
        data3 = response3.json()
        assert data3["dedup_hit"] is False  # Different tenant, no dedup
        assert data3["document_id"] != data1["document_id"]

        # Upload same content to tenant-a/kb-1 again (should dedup)
        response4 = client_with_real_services.post(
            "/api/rag/upload-versioned",
            files={"file": ("doc.txt", file_content, "text/plain")},
            headers={"X-Tenant-ID": "tenant-a", "X-KB-ID": "kb-1"},
        )
        assert response4.status_code == 200
        data4 = response4.json()
        assert data4["dedup_hit"] is True  # Same tenant+KB, dedup detected
        assert data4["document_id"] == data1["document_id"]

    def test_same_content_different_logical_names_stay_separate_documents(
        self, client_with_real_services, shared_repository
    ):
        """Test identical content does not collapse two logical documents in the same tenant/KB."""
        file_content = b"same content, different filenames"

        response_a = client_with_real_services.post(
            "/api/rag/upload-versioned",
            files={"file": ("alpha.txt", file_content, "text/plain")},
            headers={"X-Tenant-ID": "tenant-a", "X-KB-ID": "kb-1"},
        )
        response_b = client_with_real_services.post(
            "/api/rag/upload-versioned",
            files={"file": ("beta.txt", file_content, "text/plain")},
            headers={"X-Tenant-ID": "tenant-a", "X-KB-ID": "kb-1"},
        )

        assert response_a.status_code == 200
        assert response_b.status_code == 200

        data_a = response_a.json()
        data_b = response_b.json()

        assert data_a["dedup_hit"] is False
        assert data_b["dedup_hit"] is False
        assert data_a["document_id"] != data_b["document_id"]

        doc_a = shared_repository.get_document(data_a["document_id"])
        doc_b = shared_repository.get_document(data_b["document_id"])
        assert doc_a is not None
        assert doc_b is not None
        assert doc_a.logical_name == "alpha.txt"
        assert doc_b.logical_name == "beta.txt"


class TestVersionHistoryProgressionIntegration:
    """Integration tests for version history progression with repeated uploads."""

    def test_version_history_progression_with_new_version_mode(
        self, client_with_real_services, shared_repository
    ):
        """Test that repeated uploads with dedup_mode=new_version create sequential versions.

        Note: The service deactivates the previous active version when creating a new version,
        regardless of dedup_mode. Only the REPLACE mode sets replaced_by.
        """
        tenant_id = "tenant-history"
        kb_id = "kb-history"

        # Upload version 1
        response1 = client_with_real_services.post(
            "/api/rag/upload-versioned",
            files={"file": ("history.txt", b"content v1", "text/plain")},
            headers={"X-Tenant-ID": tenant_id, "X-KB-ID": kb_id},
            params={"dedup_mode": "new_version"},
        )
        assert response1.status_code == 200
        data1 = response1.json()
        doc_id = data1["document_id"]
        v1_id = data1["version_id"]

        # Upload version 2
        response2 = client_with_real_services.post(
            "/api/rag/upload-versioned",
            files={"file": ("history.txt", b"content v2", "text/plain")},
            headers={"X-Tenant-ID": tenant_id, "X-KB-ID": kb_id},
            params={"dedup_mode": "new_version"},
        )
        assert response2.status_code == 200
        data2 = response2.json()
        assert data2["document_id"] == doc_id
        assert data2["version_id"] != data1["version_id"]
        v2_id = data2["version_id"]

        # Upload version 3
        response3 = client_with_real_services.post(
            "/api/rag/upload-versioned",
            files={"file": ("history.txt", b"content v3", "text/plain")},
            headers={"X-Tenant-ID": tenant_id, "X-KB-ID": kb_id},
            params={"dedup_mode": "new_version"},
        )
        assert response3.status_code == 200
        data3 = response3.json()
        assert data3["document_id"] == doc_id
        v3_id = data3["version_id"]

        # Verify version history in repository
        doc = shared_repository.get_document(doc_id)
        assert doc.current_version == 3

        versions = shared_repository.get_document_versions(doc_id)
        assert len(versions) == 3
        assert versions[0].version == 1
        assert versions[1].version == 2
        assert versions[2].version == 3

        # Verify version states: only the latest is active
        # Previous versions are deactivated with replaced_by=None (not REPLACE mode)
        v1_record = next(v for v in versions if v.version_id == v1_id)
        v2_record = next(v for v in versions if v.version_id == v2_id)
        v3_record = next(v for v in versions if v.version_id == v3_id)

        assert v1_record.is_active is False
        assert v1_record.replaced_by is None  # Not REPLACE mode

        assert v2_record.is_active is False
        assert v2_record.replaced_by is None  # Not REPLACE mode

        assert v3_record.is_active is True
        assert v3_record.replaced_by is None

        # Verify active version is the latest
        active = shared_repository.get_active_version(doc_id)
        assert active.version_id == v3_id
        assert active.version == 3

    def test_version_history_with_replace_mode(self, client_with_real_services, shared_repository):
        """Test that replace mode deactivates previous active version."""
        tenant_id = "tenant-replace"
        kb_id = "kb-replace"

        # Upload version 1
        response1 = client_with_real_services.post(
            "/api/rag/upload-versioned",
            files={"file": ("replace.txt", b"original content", "text/plain")},
            headers={"X-Tenant-ID": tenant_id, "X-KB-ID": kb_id},
        )
        assert response1.status_code == 200
        data1 = response1.json()
        doc_id = data1["document_id"]
        v1_id = data1["version_id"]

        # Upload with replace mode (same content triggers dedup, but replace creates new version)
        response2 = client_with_real_services.post(
            "/api/rag/upload-versioned",
            files={"file": ("replace.txt", b"original content", "text/plain")},
            headers={"X-Tenant-ID": tenant_id, "X-KB-ID": kb_id},
            params={"dedup_mode": "replace"},
        )
        assert response2.status_code == 200
        data2 = response2.json()
        assert data2["dedup_hit"] is True
        v2_id = data2["version_id"]

        # Verify version history
        versions = shared_repository.get_document_versions(doc_id)
        assert len(versions) == 2

        # Find v1 and v2
        v1_record = next(v for v in versions if v.version_id == v1_id)
        v2_record = next(v for v in versions if v.version_id == v2_id)

        # v1 should be deactivated with replaced_by pointing to v2
        assert v1_record.is_active is False
        assert v1_record.replaced_by == v2_id

        # v2 should be active
        assert v2_record.is_active is True
        assert v2_record.replaced_by is None

        # Active version should be v2
        active = shared_repository.get_active_version(doc_id)
        assert active.version_id == v2_id

    def test_mixed_dedup_modes_across_uploads(self, client_with_real_services, shared_repository):
        """Test mixing different dedup modes across multiple uploads."""
        tenant_id = "tenant-mixed"
        kb_id = "kb-mixed"

        # Upload v1 (default skip mode)
        response1 = client_with_real_services.post(
            "/api/rag/upload-versioned",
            files={"file": ("mixed.txt", b"content A", "text/plain")},
            headers={"X-Tenant-ID": tenant_id, "X-KB-ID": kb_id},
        )
        assert response1.status_code == 200
        data1 = response1.json()
        doc_id = data1["document_id"]

        # Upload v2 with new content (new_version mode)
        response2 = client_with_real_services.post(
            "/api/rag/upload-versioned",
            files={"file": ("mixed.txt", b"content B", "text/plain")},
            headers={"X-Tenant-ID": tenant_id, "X-KB-ID": kb_id},
            params={"dedup_mode": "new_version"},
        )
        assert response2.status_code == 200
        data2 = response2.json()

        # Upload v3 with new content (replace mode)
        response3 = client_with_real_services.post(
            "/api/rag/upload-versioned",
            files={"file": ("mixed.txt", b"content C", "text/plain")},
            headers={"X-Tenant-ID": tenant_id, "X-KB-ID": kb_id},
            params={"dedup_mode": "replace"},
        )
        assert response3.status_code == 200
        data3 = response3.json()

        # Verify version history
        versions = shared_repository.get_document_versions(doc_id)
        assert len(versions) == 3

        # Verify version progression
        assert versions[0].version == 1
        assert versions[1].version == 2
        assert versions[2].version == 3

        # Verify active states based on replace mode behavior
        # v1 and v2 should be inactive (replaced by subsequent versions)
        # v3 should be active
        active = shared_repository.get_active_version(doc_id)
        assert active.version_id == data3["version_id"]


class TestCrossRouteCompatibility:
    """Integration tests verifying legacy and versioned routes coexist and interact correctly."""

    def test_legacy_and_versioned_routes_use_different_collection_naming(
        self, client_with_real_services, shared_repository
    ):
        """Test that legacy and versioned routes produce different collection name patterns."""
        # Upload via legacy route
        response_legacy = client_with_real_services.post(
            "/api/rag/upload",
            files={"file": ("legacy.txt", b"legacy content", "text/plain")},
        )
        assert response_legacy.status_code == 200
        legacy_data = response_legacy.json()

        # Upload via versioned route
        response_versioned = client_with_real_services.post(
            "/api/rag/upload-versioned",
            files={"file": ("versioned.txt", b"versioned content", "text/plain")},
            headers={"X-Tenant-ID": "tenant-c", "X-KB-ID": "kb-3"},
        )
        assert response_versioned.status_code == 200
        versioned_data = response_versioned.json()

        # Verify different collection name patterns
        assert legacy_data["collection_name"] == "user-uploads"
        assert versioned_data["collection_name"] == "tenant_tenant-c__kb_kb-3"

        # Verify both created documents in repository
        docs = list(shared_repository._documents.values())
        assert len(docs) == 2

        # Verify tenant isolation between routes
        legacy_doc = next(d for d in docs if d.logical_name == "legacy.txt")
        versioned_doc = next(d for d in docs if d.logical_name == "versioned.txt")

        assert legacy_doc.tenant_id == "user-uploads"
        assert legacy_doc.kb_id == "default"
        assert versioned_doc.tenant_id == "tenant-c"
        assert versioned_doc.kb_id == "kb-3"
