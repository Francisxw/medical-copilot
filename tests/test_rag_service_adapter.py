"""
Tests for RAGService adapter functionality.

These tests verify that the legacy RAGService correctly delegates to VersionedTenantRAGService
while maintaining backward compatibility.
"""

import pytest
from unittest.mock import MagicMock, patch, call
from pathlib import Path

from src.services.rag_service import RAGService, RAGServiceError
from src.rag.service import VersionedTenantRAGService, UploadIndexResult


class TestRAGServiceAdapter:
    """Test suite for RAGService adapter functionality."""

    def test_legacy_response_shape(self):
        """Verify that the legacy response shape is preserved."""
        # Create a mock core service
        mock_core_service = MagicMock()
        mock_core_service.upload_and_index.return_value = UploadIndexResult(
            document_id="doc123",
            version_id="ver456",
            filename="test.txt",
            chunks=5,
            collection_name="tenant_user1__kb_kb1",
            dedup_hit=False,
            message="Upload indexed successfully",
        )

        # Create RAGService with mocked core service
        service = RAGService()
        service._core_service = mock_core_service

        # Mock the loader to avoid actual file processing
        mock_loader = MagicMock()
        mock_loader.load_from_directory.return_value = [MagicMock()]
        mock_loader.create_nodes.return_value = [MagicMock() for _ in range(5)]
        service._loader = mock_loader

        # Call the legacy method
        result = service.upload_and_index(
            file_bytes=b"test content",
            filename="test.txt",
            collection_name="user-uploads",
        )

        # Verify legacy response shape
        assert isinstance(result, dict)
        assert "filename" in result
        assert "chunks" in result
        assert "collection_name" in result
        assert result["filename"] == "test.txt"
        assert result["chunks"] == 5
        assert result["collection_name"] == "user-uploads"  # Original collection_name preserved

    def test_canonical_collection_name_parsing(self):
        """Verify that canonical collection names are parsed correctly."""
        service = RAGService()

        # Test canonical format
        tenant_id, kb_id = service._map_legacy_scope_to_tenant_kb("tenant_user1__kb_kb1")
        assert tenant_id == "user1"
        assert kb_id == "kb1"

        # Test another canonical format
        tenant_id, kb_id = service._map_legacy_scope_to_tenant_kb("tenant_tenant-123__kb_kb-456")
        assert tenant_id == "tenant-123"
        assert kb_id == "kb-456"

    def test_non_canonical_collection_name_fallback(self):
        """Verify that non-canonical collection names use deterministic fallback."""
        service = RAGService()

        # Test non-canonical format
        tenant_id, kb_id = service._map_legacy_scope_to_tenant_kb("user-uploads")
        assert tenant_id == "user-uploads"
        assert kb_id == "default"

        # Test another non-canonical format
        tenant_id, kb_id = service._map_legacy_scope_to_tenant_kb("my-collection")
        assert tenant_id == "my-collection"
        assert kb_id == "default"

    def test_core_delegation_invoked(self):
        """Verify that the core service is actually invoked."""
        # Create a mock core service
        mock_core_service = MagicMock()
        mock_core_service.upload_and_index.return_value = UploadIndexResult(
            document_id="doc123",
            version_id="ver456",
            filename="test.txt",
            chunks=5,
            collection_name="tenant_user1__kb_kb1",
            dedup_hit=False,
            message="Upload indexed successfully",
        )

        # Create RAGService with mocked core service
        service = RAGService()
        service._core_service = mock_core_service

        # Mock the loader to avoid actual file processing
        mock_loader = MagicMock()
        mock_loader.load_from_directory.return_value = [MagicMock()]
        mock_loader.create_nodes.return_value = [MagicMock() for _ in range(5)]
        service._loader = mock_loader

        # Call the legacy method
        result = service.upload_and_index(
            file_bytes=b"test content",
            filename="test.txt",
            collection_name="user-uploads",
        )

        # Verify core service was called with correct parameters
        mock_core_service.upload_and_index.assert_called_once()
        call_kwargs = mock_core_service.upload_and_index.call_args[1]
        assert call_kwargs["tenant_id"] == "user-uploads"
        assert call_kwargs["kb_id"] == "default"
        assert call_kwargs["metadata"]["legacy_collection_name"] == "user-uploads"

    def test_core_delegation_with_canonical_name(self):
        """Verify that canonical collection names are parsed and passed correctly."""
        # Create a mock core service
        mock_core_service = MagicMock()
        mock_core_service.upload_and_index.return_value = UploadIndexResult(
            document_id="doc123",
            version_id="ver456",
            filename="test.txt",
            chunks=5,
            collection_name="tenant_user1__kb_kb1",
            dedup_hit=False,
            message="Upload indexed successfully",
        )

        # Create RAGService with mocked core service
        service = RAGService()
        service._core_service = mock_core_service

        # Mock the loader to avoid actual file processing
        mock_loader = MagicMock()
        mock_loader.load_from_directory.return_value = [MagicMock()]
        mock_loader.create_nodes.return_value = [MagicMock() for _ in range(5)]
        service._loader = mock_loader

        # Call the legacy method with canonical collection name
        result = service.upload_and_index(
            file_bytes=b"test content",
            filename="test.txt",
            collection_name="tenant_user1__kb_kb1",
        )

        # Verify core service was called with parsed parameters
        mock_core_service.upload_and_index.assert_called_once()
        call_kwargs = mock_core_service.upload_and_index.call_args[1]
        assert call_kwargs["tenant_id"] == "user1"
        assert call_kwargs["kb_id"] == "kb1"
        assert call_kwargs["metadata"]["legacy_collection_name"] == "tenant_user1__kb_kb1"

    def test_error_handling(self):
        """Verify that errors from core service are properly wrapped."""
        from src.rag.service import RAGCoreServiceError

        # Create a mock core service that raises an error
        mock_core_service = MagicMock()
        mock_core_service.upload_and_index.side_effect = RAGCoreServiceError("Test error")

        # Create RAGService with mocked core service
        service = RAGService()
        service._core_service = mock_core_service

        # Mock the loader to avoid actual file processing
        mock_loader = MagicMock()
        mock_loader.load_from_directory.return_value = [MagicMock()]
        mock_loader.create_nodes.return_value = [MagicMock() for _ in range(5)]
        service._loader = mock_loader

        # Verify that RAGServiceError is raised
        with pytest.raises(RAGServiceError) as exc_info:
            service.upload_and_index(
                file_bytes=b"test content",
                filename="test.txt",
                collection_name="user-uploads",
            )

        assert "Test error" in str(exc_info.value)

    def test_lazy_loader_injection(self):
        """Verify that lazy loader injection still works."""
        # Create a mock loader
        mock_loader = MagicMock()

        # Create RAGService with injected loader
        service = RAGService(loader=mock_loader)

        # Verify that the loader is used
        assert service._loader is mock_loader
        assert service.document_loader is mock_loader

    def test_lazy_core_service_creation(self):
        """Verify that core service is lazily created."""
        service = RAGService()

        # Core service should not be created yet
        assert service._core_service is None

        # Access core service property
        core_service = service.core_service

        # Core service should now be created
        assert service._core_service is not None
        assert isinstance(core_service, VersionedTenantRAGService)

    def test_validation_preserved(self):
        """Verify that validation logic is preserved."""
        service = RAGService()

        # Test empty file
        with pytest.raises(RAGServiceError) as exc_info:
            service.upload_and_index(
                file_bytes=b"",
                filename="test.txt",
                collection_name="user-uploads",
            )
        assert "上传的文件为空" in str(exc_info.value)

        # Test unsupported file type
        with pytest.raises(RAGServiceError) as exc_info:
            service.upload_and_index(
                file_bytes=b"test content",
                filename="test.exe",
                collection_name="user-uploads",
            )
        assert "不支持的文件格式" in str(exc_info.value)

        # Test file too large
        large_content = b"x" * (11 * 1024 * 1024)  # 11MB
        with pytest.raises(RAGServiceError) as exc_info:
            service.upload_and_index(
                file_bytes=large_content,
                filename="test.txt",
                collection_name="user-uploads",
            )
        assert "文件过大" in str(exc_info.value)

    def test_filename_sanitization_preserved(self):
        """Verify that filename sanitization is preserved."""
        service = RAGService()

        # Test path traversal attempt - should extract just the filename
        safe_name = service._sanitize_filename("../../../etc/passwd")
        assert safe_name == "passwd"  # Path.name extracts just the filename

        # Test normal filename
        safe_name = service._sanitize_filename("path/to/test.txt")
        assert safe_name == "test.txt"

        # Test empty filename
        with pytest.raises(RAGServiceError) as exc_info:
            service._sanitize_filename("")
        assert "非法文件名" in str(exc_info.value)

        # Test special path
        with pytest.raises(RAGServiceError) as exc_info:
            service._sanitize_filename(".")
        assert "非法文件名" in str(exc_info.value)
