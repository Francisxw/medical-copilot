-- Rollback migration script for versioned RAG uploads schema
-- Drops indexes and tables in safe reverse order
-- Idempotent: uses IF EXISTS for all objects
-- Compatible with SQLite (and PostgreSQL with minor adjustments)

-- Drop indexes first (order doesn't matter, but drop all before tables)
DROP INDEX IF EXISTS idx_versions_content_hash;
DROP INDEX IF EXISTS idx_versions_tenant_kb;
DROP INDEX IF EXISTS idx_versions_active;
DROP INDEX IF EXISTS idx_versions_document;

DROP INDEX IF EXISTS idx_documents_logical_name;
DROP INDEX IF EXISTS idx_documents_tenant_kb;

-- Drop document_versions table first (has foreign key to documents)
DROP TABLE IF EXISTS document_versions;

-- Drop documents table
DROP TABLE IF EXISTS documents;

-- Note: This script removes all schema objects created by migrate_forward.sql.
-- It is safe to run multiple times (idempotent).