"""
Tests for the versioned RAG upload API endpoint.
"""

import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from src.main import app
from src.rag.service import UploadIndexResult, DedupMode


@pytest.fixture
def mock_versioned_service():
    """Fixture providing a mocked VersionedTenantRAGService."""
    mock = MagicMock()
    mock.upload_and_index.return_value = UploadIndexResult(
        document_id="doc-123",
        version_id="ver-456",
        filename="test.txt",
        chunks=5,
        collection_name="tenant_tenant-a__kb_kb-1",
        dedup_hit=False,
        message="Upload indexed successfully",
    )
    return mock


@pytest.fixture
def client_with_mock_service(mock_versioned_service):
    """Fixture providing a TestClient with mocked versioned service."""
    with patch("src.api.routes.get_versioned_rag_service", return_value=mock_versioned_service):
        yield TestClient(app)


def test_versioned_upload_happy_path(client_with_mock_service, mock_versioned_service):
    """Test successful upload with required headers."""
    response = client_with_mock_service.post(
        "/api/rag/upload-versioned",
        files={"file": ("test.txt", b"hello world", "text/plain")},
        headers={"X-Tenant-ID": "tenant-a", "X-KB-ID": "kb-1"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["document_id"] == "doc-123"
    assert data["version_id"] == "ver-456"
    assert data["filename"] == "test.txt"
    assert data["chunks"] == 5
    assert data["collection_name"] == "tenant_tenant-a__kb_kb-1"
    assert data["dedup_hit"] is False
    assert data["message"] == "Upload indexed successfully"
    mock_versioned_service.upload_and_index.assert_called_once()
    call_kwargs = mock_versioned_service.upload_and_index.call_args.kwargs
    assert call_kwargs["tenant_id"] == "tenant-a"
    assert call_kwargs["kb_id"] == "kb-1"
    assert call_kwargs["dedup_mode"] == DedupMode.SKIP


def test_versioned_upload_missing_tenant_header(client_with_mock_service):
    """Test missing X-Tenant-ID header returns 422."""
    response = client_with_mock_service.post(
        "/api/rag/upload-versioned",
        files={"file": ("test.txt", b"hello", "text/plain")},
        headers={"X-KB-ID": "kb-1"},
    )
    assert response.status_code == 422


def test_versioned_upload_missing_kb_header(client_with_mock_service):
    """Test missing X-KB-ID header returns 422."""
    response = client_with_mock_service.post(
        "/api/rag/upload-versioned",
        files={"file": ("test.txt", b"hello", "text/plain")},
        headers={"X-Tenant-ID": "tenant-a"},
    )
    assert response.status_code == 422


def test_versioned_upload_empty_file(client_with_mock_service):
    """Test empty file upload returns 400."""
    response = client_with_mock_service.post(
        "/api/rag/upload-versioned",
        files={"file": ("empty.txt", b"", "text/plain")},
        headers={"X-Tenant-ID": "tenant-a", "X-KB-ID": "kb-1"},
    )
    assert response.status_code == 400
    assert "上传的文件为空" in response.json()["detail"]


def test_versioned_upload_invalid_dedup_mode(client_with_mock_service):
    """Test invalid dedup_mode query parameter returns 422 via enum validation."""
    response = client_with_mock_service.post(
        "/api/rag/upload-versioned?dedup_mode=invalid",
        files={"file": ("test.txt", b"hello", "text/plain")},
        headers={"X-Tenant-ID": "tenant-a", "X-KB-ID": "kb-1"},
    )
    assert response.status_code == 422


def test_versioned_upload_dedup_mode_new_version(client_with_mock_service, mock_versioned_service):
    """Test dedup_mode=new_version is passed correctly."""
    response = client_with_mock_service.post(
        "/api/rag/upload-versioned?dedup_mode=new_version",
        files={"file": ("test.txt", b"hello", "text/plain")},
        headers={"X-Tenant-ID": "tenant-a", "X-KB-ID": "kb-1"},
    )
    assert response.status_code == 200
    call_kwargs = mock_versioned_service.upload_and_index.call_args.kwargs
    assert call_kwargs["dedup_mode"] == DedupMode.NEW_VERSION


def test_versioned_upload_dedup_mode_replace(client_with_mock_service, mock_versioned_service):
    """Test dedup_mode=replace is passed correctly."""
    response = client_with_mock_service.post(
        "/api/rag/upload-versioned?dedup_mode=replace",
        files={"file": ("test.txt", b"hello", "text/plain")},
        headers={"X-Tenant-ID": "tenant-a", "X-KB-ID": "kb-1"},
    )
    assert response.status_code == 200
    call_kwargs = mock_versioned_service.upload_and_index.call_args.kwargs
    assert call_kwargs["dedup_mode"] == DedupMode.REPLACE


def test_versioned_upload_dedup_hit_response(client_with_mock_service, mock_versioned_service):
    """Test dedup_hit=True in response."""
    mock_versioned_service.upload_and_index.return_value = UploadIndexResult(
        document_id="doc-123",
        version_id="ver-456",
        filename="test.txt",
        chunks=5,
        collection_name="tenant_tenant-a__kb_kb-1",
        dedup_hit=True,
        message="Duplicate content detected; skipped indexing",
    )
    response = client_with_mock_service.post(
        "/api/rag/upload-versioned",
        files={"file": ("test.txt", b"hello", "text/plain")},
        headers={"X-Tenant-ID": "tenant-a", "X-KB-ID": "kb-1"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["dedup_hit"] is True
    assert data["message"] == "Duplicate content detected; skipped indexing"


def test_versioned_upload_service_error(client_with_mock_service, mock_versioned_service):
    """Test service raising RAGCoreServiceError returns 400."""
    from src.rag.service import RAGCoreServiceError

    mock_versioned_service.upload_and_index.side_effect = RAGCoreServiceError(
        "Unsupported file format"
    )
    response = client_with_mock_service.post(
        "/api/rag/upload-versioned",
        files={"file": ("bad.md", b"hello", "text/plain")},
        headers={"X-Tenant-ID": "tenant-a", "X-KB-ID": "kb-1"},
    )
    assert response.status_code == 400
    assert "Unsupported file format" in response.json()["detail"]


def test_versioned_upload_unexpected_error(client_with_mock_service, mock_versioned_service):
    """Test unexpected exception returns 500."""
    mock_versioned_service.upload_and_index.side_effect = RuntimeError("Unexpected")
    response = client_with_mock_service.post(
        "/api/rag/upload-versioned",
        files={"file": ("test.txt", b"hello", "text/plain")},
        headers={"X-Tenant-ID": "tenant-a", "X-KB-ID": "kb-1"},
    )
    assert response.status_code == 500
    assert "文档索引失败" in response.json()["detail"]


def test_legacy_upload_route_still_present():
    """Verify the legacy /api/rag/upload endpoint is still present and importable."""
    from src.api.routes import upload_rag_document

    assert upload_rag_document is not None
    # Ensure the route exists in the app
    client = TestClient(app)
    # We cannot call it without mocking the legacy service, but we can check the route exists
    routes = [p for route in app.routes if (p := getattr(route, "path", None)) is not None]
    assert "/api/rag/upload" in routes
    assert "/api/rag/upload-versioned" in routes
