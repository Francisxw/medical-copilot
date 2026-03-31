"""Core multi-tenant, version-aware RAG upload service."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
from pathlib import Path
import tempfile
import uuid
from typing import Any, Dict, Iterable, List, Optional

from src.rag.repository import DocumentRepository, DocumentVersionRecord, InMemoryDocumentRepository


SUPPORTED_EXTS = frozenset({".json", ".pdf", ".txt"})
MAX_UPLOAD_BYTES = 10 * 1024 * 1024


class RAGCoreServiceError(Exception):
    """Raised when upload/index processing fails validation or ownership checks."""


class DedupMode(str, Enum):
    """Deduplication behavior when same content hash is detected."""

    SKIP = "skip"
    NEW_VERSION = "new_version"
    REPLACE = "replace"


@dataclass(frozen=True)
class UploadIndexResult:
    """Structured upload/index result aligned with the integration skeleton."""

    document_id: str
    version_id: str
    filename: str
    chunks: int
    collection_name: str
    dedup_hit: bool
    message: str


class VersionedTenantRAGService:
    """Core RAG upload service with tenant isolation and document versioning."""

    def __init__(
        self,
        repository: Optional[DocumentRepository] = None,
        loader: Optional[Any] = None,
    ):
        self._repository = repository or InMemoryDocumentRepository()
        self._loader = loader

    @property
    def repository(self) -> DocumentRepository:
        return self._repository

    @property
    def loader(self) -> Any:
        if self._loader is None:
            from src.utils.llama_index_loader import LlamaIndexDocumentLoader

            self._loader = LlamaIndexDocumentLoader()
        return self._loader

    def upload_and_index(
        self,
        file_bytes: bytes,
        filename: str,
        *,
        tenant_id: str,
        kb_id: str,
        dedup_mode: DedupMode = DedupMode.SKIP,
        document_id: Optional[str] = None,
        logical_name: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> UploadIndexResult:
        ext = Path(filename).suffix.lower()
        self._validate_upload(file_bytes=file_bytes, ext=ext, tenant_id=tenant_id, kb_id=kb_id)

        tenant_id = tenant_id.strip()
        kb_id = kb_id.strip()
        logical_name = (logical_name or filename).strip()

        collection_name = self._collection_name(tenant_id, kb_id)
        content_hash = self._sha256(file_bytes)

        resolved_document = self._resolve_document(
            tenant_id=tenant_id,
            kb_id=kb_id,
            document_id=document_id,
            logical_name=logical_name,
        )

        existing_same_hash = self._find_document_version_by_hash(
            document_id=resolved_document.document_id,
            content_hash=content_hash,
        )
        if existing_same_hash is not None and dedup_mode == DedupMode.SKIP:
            return UploadIndexResult(
                document_id=existing_same_hash.document_id,
                version_id=existing_same_hash.version_id,
                filename=filename,
                chunks=existing_same_hash.chunk_count,
                collection_name=existing_same_hash.collection_name,
                dedup_hit=True,
                message="Duplicate content detected; skipped indexing",
            )

        stored_filename = self._stored_filename(ext)
        service_metadata = {
            "tenant_id": tenant_id,
            "kb_id": kb_id,
            "logical_name": logical_name,
            "document_id": resolved_document.document_id,
            "collection_name": collection_name,
            "content_hash": content_hash,
            "source_filename": filename,
        }
        if metadata:
            service_metadata.update(metadata)

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir) / stored_filename
            tmp_path.write_bytes(file_bytes)

            if ext == ".json":
                documents = self.loader.load_from_json(str(tmp_path))
            else:
                documents = self.loader.load_from_directory(tmp_dir)

            if not documents:
                raise RAGCoreServiceError("No document content could be extracted")

            self._attach_metadata_to_documents(documents, service_metadata)

            raw_nodes = self.loader.create_nodes(documents)
            if not raw_nodes:
                raise RAGCoreServiceError("No chunks generated from uploaded document")

            nodes = self._dedup_nodes_in_upload(raw_nodes)
            self._attach_metadata_to_nodes(nodes, service_metadata)
            self.loader.build_index(nodes, collection_name=collection_name)

        latest = self.repository.get_latest_version(resolved_document.document_id)
        next_version = 1 if latest is None else latest.version + 1
        new_version_id = str(uuid.uuid4())

        active_before = self.repository.get_active_version(resolved_document.document_id)
        if active_before is not None:
            replaced_by = new_version_id if dedup_mode == DedupMode.REPLACE else None
            self.repository.deactivate_version(active_before.version_id, replaced_by)

        version_record = DocumentVersionRecord(
            version_id=new_version_id,
            document_id=resolved_document.document_id,
            tenant_id=tenant_id,
            kb_id=kb_id,
            version=next_version,
            content_hash=content_hash,
            original_filename=filename,
            stored_filename=stored_filename,
            collection_name=collection_name,
            uploaded_at=datetime.now(timezone.utc),
            is_active=True,
            replaced_by=None,
            chunk_count=len(nodes),
            metadata=service_metadata,
        )

        self.repository.create_version(version_record)
        self.repository.set_document_current_version(resolved_document.document_id, next_version)

        dedup_hit = existing_same_hash is not None
        message = (
            "Duplicate content ingested as new version"
            if dedup_hit
            else "Upload indexed successfully"
        )

        return UploadIndexResult(
            document_id=resolved_document.document_id,
            version_id=new_version_id,
            filename=filename,
            chunks=len(nodes),
            collection_name=collection_name,
            dedup_hit=dedup_hit,
            message=message,
        )

    @staticmethod
    def _validate_upload(file_bytes: bytes, ext: str, tenant_id: str, kb_id: str) -> None:
        if ext not in SUPPORTED_EXTS:
            raise RAGCoreServiceError(f"Unsupported file format: {ext}, only {SUPPORTED_EXTS}")
        if not file_bytes:
            raise RAGCoreServiceError("Uploaded file is empty")
        if len(file_bytes) > MAX_UPLOAD_BYTES:
            raise RAGCoreServiceError("Uploaded file exceeds 10MB limit")
        if not tenant_id or not tenant_id.strip():
            raise RAGCoreServiceError("tenant_id is required")
        if not kb_id or not kb_id.strip():
            raise RAGCoreServiceError("kb_id is required")

    def _find_document_version_by_hash(
        self,
        *,
        document_id: str,
        content_hash: str,
    ) -> Optional[DocumentVersionRecord]:
        for version in reversed(self.repository.get_document_versions(document_id)):
            if version.content_hash == content_hash:
                return version
        return None

    @staticmethod
    def _sha256(payload: bytes) -> str:
        return hashlib.sha256(payload).hexdigest()

    @staticmethod
    def _stored_filename(ext: str) -> str:
        return f"{uuid.uuid4()}{ext}"

    @staticmethod
    def _collection_name(tenant_id: str, kb_id: str) -> str:
        return f"tenant_{tenant_id}__kb_{kb_id}"

    def _resolve_document(
        self,
        *,
        tenant_id: str,
        kb_id: str,
        document_id: Optional[str],
        logical_name: str,
    ):
        if document_id:
            existing = self.repository.get_document(document_id)
            if existing is None:
                raise RAGCoreServiceError(f"Document not found: {document_id}")
            if existing.tenant_id != tenant_id or existing.kb_id != kb_id:
                raise RAGCoreServiceError(
                    "document_id does not belong to the provided tenant_id/kb_id"
                )
            return existing

        found = self.repository.find_active_document_by_logical_name(tenant_id, kb_id, logical_name)
        if found is not None:
            return found
        return self.repository.create_document(tenant_id, kb_id, logical_name)

    @staticmethod
    def _attach_metadata_to_documents(documents: Iterable[Any], metadata: Dict[str, Any]) -> None:
        for doc in documents:
            if not hasattr(doc, "metadata"):
                continue
            doc_metadata = getattr(doc, "metadata")
            if isinstance(doc_metadata, dict):
                doc_metadata.update(metadata)
                continue
            setattr(doc, "metadata", dict(metadata))

    @staticmethod
    def _attach_metadata_to_nodes(nodes: Iterable[Any], metadata: Dict[str, Any]) -> None:
        for node in nodes:
            if not hasattr(node, "metadata"):
                continue
            node_metadata = getattr(node, "metadata")
            if isinstance(node_metadata, dict):
                node_metadata.update(metadata)
                continue
            setattr(node, "metadata", dict(metadata))

    @staticmethod
    def _dedup_nodes_in_upload(nodes: List[Any]) -> List[Any]:
        """Deduplicate chunks generated in one upload only while preserving order."""

        seen: dict[str, Any] = {}
        for node in nodes:
            text = getattr(node, "text", "") or ""
            node_metadata = getattr(node, "metadata", {})
            metadata_part = (
                json.dumps(node_metadata, sort_keys=True, ensure_ascii=True)
                if isinstance(node_metadata, dict)
                else str(node_metadata)
            )
            key = f"{text}\n{metadata_part}"
            if key not in seen:
                seen[key] = node
        return list(seen.values())
