"""
Scaffold tests for RAG service integration.
These tests verify that the test infrastructure works and that key modules can be imported.
They do not test actual behavior, only that the scaffolding is in place.
"""

import pytest


def test_rag_service_import():
    """Verify that RAGService can be imported without error."""
    from src.services.rag_service import RAGService

    assert RAGService is not None


def test_rag_service_with_mock_loader(rag_service_with_mock_loader):
    """Verify that the mocked RAGService can be instantiated and has expected attributes."""
    service = rag_service_with_mock_loader
    assert hasattr(service, "upload_and_index")
    assert hasattr(service, "loader")
    # The loader should be our mock
    assert service.loader.load_from_json.called is False  # not called yet


def test_document_repository_import():
    """Verify that DocumentRepository protocol can be imported."""
    from src.rag.repository import DocumentRepository

    assert DocumentRepository is not None


def test_document_repository_methods():
    """Check that DocumentRepository defines expected methods."""
    from src.rag.repository import DocumentRepository

    expected_methods = [
        "get_document",
        "find_active_document_by_logical_name",
        "create_document",
        "get_active_version",
        "get_latest_version",
        "find_version_by_hash",
        "create_version",
        "deactivate_version",
        "set_document_current_version",
    ]
    for method in expected_methods:
        assert hasattr(DocumentRepository, method), f"Missing method: {method}"


def test_schemas_import():
    """Verify that API schemas can be imported."""
    from src.models.schemas import RAGUploadResponse

    assert RAGUploadResponse is not None
