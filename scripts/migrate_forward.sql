-- Forward migration script for versioned RAG uploads schema
-- Creates documents and document_versions tables with indexes
-- Idempotent: uses IF NOT EXISTS for all objects
-- Compatible with SQLite (and PostgreSQL with minor adjustments)

-- Create documents table
CREATE TABLE IF NOT EXISTS documents (
    document_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    kb_id TEXT NOT NULL,
    logical_name TEXT NOT NULL,
    current_version INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(tenant_id, kb_id, logical_name)
);

-- Create document_versions table
CREATE TABLE IF NOT EXISTS document_versions (
    version_id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL,
    tenant_id TEXT NOT NULL,
    kb_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    content_hash TEXT NOT NULL,
    original_filename TEXT NOT NULL,
    stored_filename TEXT NOT NULL,
    collection_name TEXT NOT NULL,
    uploaded_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN NOT NULL DEFAULT 1,
    replaced_by TEXT,
    chunk_count INTEGER NOT NULL DEFAULT 0,
    metadata TEXT,
    FOREIGN KEY (document_id) REFERENCES documents(document_id) ON DELETE CASCADE,
    FOREIGN KEY (replaced_by) REFERENCES document_versions(version_id) ON DELETE SET NULL,
    UNIQUE(document_id, version)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_documents_tenant_kb ON documents(tenant_id, kb_id);
CREATE INDEX IF NOT EXISTS idx_documents_logical_name ON documents(tenant_id, kb_id, logical_name);

CREATE INDEX IF NOT EXISTS idx_versions_document ON document_versions(document_id);
CREATE INDEX IF NOT EXISTS idx_versions_active ON document_versions(document_id, is_active);
CREATE INDEX IF NOT EXISTS idx_versions_tenant_kb ON document_versions(tenant_id, kb_id);
CREATE INDEX IF NOT EXISTS idx_versions_content_hash ON document_versions(tenant_id, kb_id, content_hash);  -- For application-level dedup lookups (skip/new_version/replace)

-- Note: No UNIQUE constraint on (tenant_id, kb_id, content_hash) because deduplication is application-level.
-- The idx_versions_content_hash index supports fast lookups for dedup strategies.