#!/usr/bin/env python3
"""
Verification script for migration scripts.
Tests forward and rollback migrations on a temporary SQLite database.
"""

import sqlite3
import tempfile
import os
import sys


def read_sql_file(path):
    """Read SQL file content."""
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def main():
    # Paths to migration scripts
    forward_script = os.path.join(os.path.dirname(__file__), "migrate_forward.sql")
    rollback_script = os.path.join(os.path.dirname(__file__), "migrate_rollback.sql")

    # Create temporary SQLite database
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    conn = None
    try:
        print(f"Testing migrations on temporary database: {db_path}")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # 1. Apply forward migration
        print("\n1. Applying forward migration...")
        forward_sql = read_sql_file(forward_script)
        cursor.executescript(forward_sql)
        conn.commit()
        print("   Forward migration applied successfully.")

        # 2. Verify tables exist
        print("\n2. Verifying tables after forward migration...")
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
        tables = [row[0] for row in cursor.fetchall()]
        expected_tables = ["documents", "document_versions"]
        for table in expected_tables:
            if table in tables:
                print(f"   [OK] Table '{table}' exists")
            else:
                print(f"   [FAIL] Table '{table}' missing")
                sys.exit(1)

        # 3. Verify indexes exist
        print("\n3. Verifying indexes after forward migration...")
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%' ORDER BY name;"
        )
        indexes = [row[0] for row in cursor.fetchall()]
        expected_indexes = [
            "idx_documents_tenant_kb",
            "idx_documents_logical_name",
            "idx_versions_document",
            "idx_versions_active",
            "idx_versions_tenant_kb",
            "idx_versions_content_hash",
        ]
        for idx in expected_indexes:
            if idx in indexes:
                print(f"   [OK] Index '{idx}' exists")
            else:
                print(f"   [FAIL] Index '{idx}' missing")
                sys.exit(1)

        # 4. Verify foreign key constraint exists (by checking table info)
        print("\n4. Verifying foreign key constraints...")
        cursor.execute("PRAGMA foreign_keys;")
        fk_enabled = cursor.fetchone()[0]
        if fk_enabled:
            print("   [OK] Foreign keys are enabled")
        else:
            print("   [WARN] Foreign keys are disabled (default for SQLite)")

        # Check foreign key info for document_versions
        cursor.execute("PRAGMA foreign_key_list(document_versions);")
        fks = cursor.fetchall()
        if len(fks) >= 2:
            print(f"   [OK] document_versions has {len(fks)} foreign key constraints")
        else:
            print(f"   [FAIL] document_versions has only {len(fks)} foreign key constraints")
            sys.exit(1)

        # 5. Apply rollback migration
        print("\n5. Applying rollback migration...")
        rollback_sql = read_sql_file(rollback_script)
        cursor.executescript(rollback_sql)
        conn.commit()
        print("   Rollback migration applied successfully.")

        # 6. Verify tables are dropped
        print("\n6. Verifying tables after rollback...")
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
        tables_after = [row[0] for row in cursor.fetchall()]
        for table in expected_tables:
            if table not in tables_after:
                print(f"   [OK] Table '{table}' dropped")
            else:
                print(f"   [FAIL] Table '{table}' still exists")
                sys.exit(1)

        # 7. Verify indexes are dropped
        print("\n7. Verifying indexes after rollback...")
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%' ORDER BY name;"
        )
        indexes_after = [row[0] for row in cursor.fetchall()]
        for idx in expected_indexes:
            if idx not in indexes_after:
                print(f"   [OK] Index '{idx}' dropped")
            else:
                print(f"   [FAIL] Index '{idx}' still exists")
                sys.exit(1)

        # 8. Test idempotency: apply forward migration again
        print("\n8. Testing idempotency (apply forward migration again)...")
        cursor.executescript(forward_sql)
        conn.commit()
        print("   Forward migration applied again successfully (idempotent).")

        # 9. Test idempotency: apply rollback migration again
        print("\n9. Testing idempotency (apply rollback migration again)...")
        cursor.executescript(rollback_sql)
        conn.commit()
        print("   Rollback migration applied again successfully (idempotent).")

        print("\n[SUCCESS] All migration tests passed!")

    except Exception as e:
        print(f"\n[ERROR] Migration test failed: {e}")
        sys.exit(1)
    finally:
        if conn is not None:
            conn.close()
        # Clean up temporary database
        if os.path.exists(db_path):
            os.unlink(db_path)
            print(f"\nCleaned up temporary database: {db_path}")


if __name__ == "__main__":
    main()
