"""Unit tests for the versioned tenant-aware RAG service core."""

from datetime import datetime
from types import SimpleNamespace

import pytest

from src.rag import InMemoryDocumentRepository
from src.rag.repository import DocumentVersionRecord
from src.rag.service import (
    MAX_UPLOAD_BYTES,
    DedupMode,
    RAGCoreServiceError,
    VersionedTenantRAGService,
)


def _doc() -> SimpleNamespace:
    return SimpleNamespace(metadata={})


def _node(text: str, metadata=None) -> SimpleNamespace:
    return SimpleNamespace(text=text, metadata=metadata or {})


@pytest.fixture
def repo():
    return InMemoryDocumentRepository()


@pytest.fixture
def service(repo, mock_llama_index_loader):
    return VersionedTenantRAGService(repository=repo, loader=mock_llama_index_loader)


def test_upload_validates_extension_and_non_empty(service):
    with pytest.raises(RAGCoreServiceError, match="Unsupported file format"):
        service.upload_and_index(
            b"content",
            "bad.md",
            tenant_id="tenant-a",
            kb_id="kb-1",
        )

    with pytest.raises(RAGCoreServiceError, match="Uploaded file is empty"):
        service.upload_and_index(
            b"",
            "good.txt",
            tenant_id="tenant-a",
            kb_id="kb-1",
        )

    with pytest.raises(RAGCoreServiceError, match="exceeds 10MB limit"):
        service.upload_and_index(
            b"a" * (MAX_UPLOAD_BYTES + 1),
            "good.txt",
            tenant_id="tenant-a",
            kb_id="kb-1",
        )


def test_upload_creates_document_version_and_collection_name(service, mock_llama_index_loader):
    mock_llama_index_loader.load_from_directory.return_value = [_doc()]
    mock_llama_index_loader.create_nodes.return_value = [
        _node("chunk-1"),
        _node("chunk-1"),
        _node("chunk-2"),
    ]

    result = service.upload_and_index(
        b"hello world",
        "note.txt",
        tenant_id="tenant-a",
        kb_id="kb-1",
    )

    assert result.filename == "note.txt"
    assert result.chunks == 2
    assert result.collection_name == "tenant_tenant-a__kb_kb-1"
    assert result.dedup_hit is False
    assert result.message == "Upload indexed successfully"

    document = service.repository.get_document(result.document_id)
    assert document is not None
    assert document.logical_name == "note.txt"
    assert document.current_version == 1

    active = service.repository.get_active_version(result.document_id)
    assert active is not None
    assert active.version_id == result.version_id
    assert active.chunk_count == 2
    assert active.collection_name == "tenant_tenant-a__kb_kb-1"

    mock_llama_index_loader.build_index.assert_called_once()
    _, kwargs = mock_llama_index_loader.build_index.call_args
    assert kwargs["collection_name"] == "tenant_tenant-a__kb_kb-1"


def test_upload_resolves_document_by_document_id_and_checks_ownership(
    service, mock_llama_index_loader
):
    mock_llama_index_loader.load_from_directory.return_value = [_doc()]
    mock_llama_index_loader.create_nodes.return_value = [_node("chunk-1")]

    first = service.upload_and_index(
        b"v1",
        "doc.txt",
        tenant_id="tenant-a",
        kb_id="kb-1",
    )

    second = service.upload_and_index(
        b"v2",
        "doc.txt",
        tenant_id="tenant-a",
        kb_id="kb-1",
        document_id=first.document_id,
        dedup_mode=DedupMode.NEW_VERSION,
    )

    assert second.document_id == first.document_id
    assert second.version_id != first.version_id

    with pytest.raises(RAGCoreServiceError, match="does not belong"):
        service.upload_and_index(
            b"v3",
            "doc.txt",
            tenant_id="tenant-b",
            kb_id="kb-1",
            document_id=first.document_id,
        )


def test_dedup_skip_short_circuits_indexing(service, mock_llama_index_loader):
    mock_llama_index_loader.load_from_directory.return_value = [_doc()]
    mock_llama_index_loader.create_nodes.return_value = [_node("chunk-1")]

    first = service.upload_and_index(
        b"same-bytes",
        "doc.txt",
        tenant_id="tenant-a",
        kb_id="kb-1",
    )
    first_build_calls = mock_llama_index_loader.build_index.call_count

    second = service.upload_and_index(
        b"same-bytes",
        "doc.txt",
        tenant_id="tenant-a",
        kb_id="kb-1",
        dedup_mode=DedupMode.SKIP,
    )

    assert second.dedup_hit is True
    assert second.document_id == first.document_id
    assert second.version_id == first.version_id
    assert mock_llama_index_loader.build_index.call_count == first_build_calls


def test_dedup_skip_does_not_merge_different_logical_documents(service, mock_llama_index_loader):
    mock_llama_index_loader.load_from_directory.return_value = [_doc()]
    mock_llama_index_loader.create_nodes.return_value = [_node("chunk-1")]

    first = service.upload_and_index(
        b"same-bytes",
        "doc-a.txt",
        tenant_id="tenant-a",
        kb_id="kb-1",
    )
    second = service.upload_and_index(
        b"same-bytes",
        "doc-b.txt",
        tenant_id="tenant-a",
        kb_id="kb-1",
        dedup_mode=DedupMode.SKIP,
    )

    assert second.dedup_hit is False
    assert second.document_id != first.document_id
    assert second.version_id != first.version_id
    assert mock_llama_index_loader.build_index.call_count == 2


def test_dedup_replace_deactivates_previous_active_version(service, mock_llama_index_loader):
    mock_llama_index_loader.load_from_directory.return_value = [_doc()]
    mock_llama_index_loader.create_nodes.return_value = [_node("chunk-1")]

    first = service.upload_and_index(
        b"bytes-v1",
        "doc.txt",
        tenant_id="tenant-a",
        kb_id="kb-1",
    )

    replaced = service.upload_and_index(
        b"bytes-v1",
        "doc.txt",
        tenant_id="tenant-a",
        kb_id="kb-1",
        dedup_mode=DedupMode.REPLACE,
        document_id=first.document_id,
    )

    assert replaced.document_id == first.document_id
    assert replaced.version_id != first.version_id
    assert replaced.dedup_hit is True

    old_version = service.repository.find_version_by_hash(
        "tenant-a",
        "kb-1",
        service._sha256(b"bytes-v1"),
    )
    assert old_version is not None
    assert old_version.version_id == replaced.version_id

    current_active = service.repository.get_active_version(first.document_id)
    assert current_active is not None
    assert current_active.version_id == replaced.version_id

    historical = service.repository.get_document_versions(first.document_id)
    old_records = [v for v in historical if v.version_id == first.version_id]
    assert len(old_records) == 1
    assert old_records[0].is_active is False
    assert old_records[0].replaced_by == replaced.version_id


def test_json_upload_uses_json_loader(service, mock_llama_index_loader):
    mock_llama_index_loader.load_from_json.return_value = [_doc()]
    mock_llama_index_loader.create_nodes.return_value = [_node("chunk-json")]

    result = service.upload_and_index(
        b'[{"content": "hello"}]',
        "guideline.json",
        tenant_id="tenant-a",
        kb_id="kb-1",
    )

    assert result.chunks == 1
    mock_llama_index_loader.load_from_json.assert_called_once()
    mock_llama_index_loader.load_from_directory.assert_not_called()


def test_upload_with_existing_active_document_resolves_by_logical_name(
    repo, mock_llama_index_loader
):
    existing_doc = repo.create_document("tenant-a", "kb-1", "same.txt")
    existing_version = DocumentVersionRecord(
        version_id="ver-existing",
        document_id=existing_doc.document_id,
        tenant_id="tenant-a",
        kb_id="kb-1",
        version=1,
        content_hash="hash-existing",
        original_filename="same.txt",
        stored_filename="stored-existing.txt",
        collection_name="tenant_tenant-a__kb_kb-1",
        uploaded_at=datetime.utcnow(),
        is_active=True,
        replaced_by=None,
        chunk_count=1,
        metadata={},
    )
    repo.create_version(existing_version)
    repo.set_document_current_version(existing_doc.document_id, 1)

    mock_llama_index_loader.load_from_directory.return_value = [_doc()]
    mock_llama_index_loader.create_nodes.return_value = [_node("new chunk")]

    service = VersionedTenantRAGService(repository=repo, loader=mock_llama_index_loader)
    result = service.upload_and_index(
        b"new-bytes",
        "same.txt",
        tenant_id="tenant-a",
        kb_id="kb-1",
        dedup_mode=DedupMode.NEW_VERSION,
    )

    assert result.document_id == existing_doc.document_id
    assert result.version_id != existing_version.version_id
