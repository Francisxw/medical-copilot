"""
Tests for the legacy RAG upload API endpoint.
"""

import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from src.main import app
from src.api.routes import get_rag_service, get_versioned_rag_service
from src.services.rag_service import RAGServiceError


@pytest.fixture
def mock_legacy_service():
    """Fixture providing a mocked RAGService."""
    mock = MagicMock()
    mock.upload_and_index.return_value = {
        "filename": "test.txt",
        "chunks": 5,
        "collection_name": "user-uploads",
    }
    return mock


@pytest.fixture
def client_with_mock_legacy_service(mock_legacy_service):
    """Fixture providing a TestClient with mocked legacy service."""
    app.dependency_overrides[get_rag_service] = lambda: mock_legacy_service
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_rag_service, None)


def test_legacy_upload_happy_path(client_with_mock_legacy_service, mock_legacy_service):
    """Test successful upload with legacy endpoint."""
    response = client_with_mock_legacy_service.post(
        "/api/rag/upload",
        files={"file": ("test.txt", b"hello world", "text/plain")},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["filename"] == "test.txt"
    assert data["chunks"] == 5
    assert data["collection_name"] == "user-uploads"
    mock_legacy_service.upload_and_index.assert_called_once()
    call_kwargs = mock_legacy_service.upload_and_index.call_args.kwargs
    assert call_kwargs["collection_name"] == "user-uploads"
    assert call_kwargs["filename"] == "test.txt"
    assert call_kwargs["file_bytes"] == b"hello world"


def test_legacy_upload_empty_file(client_with_mock_legacy_service):
    """Test empty file upload returns 400."""
    response = client_with_mock_legacy_service.post(
        "/api/rag/upload",
        files={"file": ("empty.txt", b"", "text/plain")},
    )
    assert response.status_code == 400
    assert "上传的文件为空" in response.json()["detail"]


def test_legacy_upload_service_error(client_with_mock_legacy_service, mock_legacy_service):
    """Test service raising RAGServiceError returns 400."""
    mock_legacy_service.upload_and_index.side_effect = RAGServiceError("Unsupported file format")
    response = client_with_mock_legacy_service.post(
        "/api/rag/upload",
        files={"file": ("bad.md", b"hello", "text/plain")},
    )
    assert response.status_code == 400
    assert "Unsupported file format" in response.json()["detail"]


def test_legacy_upload_unexpected_error(client_with_mock_legacy_service, mock_legacy_service):
    """Test unexpected exception returns 500."""
    mock_legacy_service.upload_and_index.side_effect = RuntimeError("Unexpected")
    response = client_with_mock_legacy_service.post(
        "/api/rag/upload",
        files={"file": ("test.txt", b"hello", "text/plain")},
    )
    assert response.status_code == 500
    assert "文档索引失败" in response.json()["detail"]


def test_legacy_upload_default_collection_name(
    client_with_mock_legacy_service, mock_legacy_service
):
    """Test that legacy route uses centralized default collection name."""
    from src.api.routes import LEGACY_DEFAULT_COLLECTION_NAME

    response = client_with_mock_legacy_service.post(
        "/api/rag/upload",
        files={"file": ("test.txt", b"hello", "text/plain")},
    )
    assert response.status_code == 200
    call_kwargs = mock_legacy_service.upload_and_index.call_args.kwargs
    assert call_kwargs["collection_name"] == LEGACY_DEFAULT_COLLECTION_NAME


def test_both_routes_coexist():
    """Verify both legacy and versioned routes exist in the app."""
    client = TestClient(app)
    routes = [p for route in app.routes if (p := getattr(route, "path", None)) is not None]
    assert "/api/rag/upload" in routes
    assert "/api/rag/upload-versioned" in routes


def test_versioned_route_still_works():
    """Quick sanity check that versioned route still works (mocked)."""
    from src.rag.service import UploadIndexResult

    mock_versioned_service = MagicMock()
    mock_versioned_service.upload_and_index.return_value = UploadIndexResult(
        document_id="doc-123",
        version_id="ver-456",
        filename="test.txt",
        chunks=5,
        collection_name="tenant_tenant-a__kb_kb-1",
        dedup_hit=False,
        message="Upload indexed successfully",
    )
    app.dependency_overrides[get_versioned_rag_service] = lambda: mock_versioned_service
    try:
        client = TestClient(app)
        response = client.post(
            "/api/rag/upload-versioned",
            files={"file": ("test.txt", b"hello world", "text/plain")},
            headers={"X-Tenant-ID": "tenant-a", "X-KB-ID": "kb-1"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["document_id"] == "doc-123"
        assert data["version_id"] == "ver-456"
    finally:
        app.dependency_overrides.pop(get_versioned_rag_service, None)
