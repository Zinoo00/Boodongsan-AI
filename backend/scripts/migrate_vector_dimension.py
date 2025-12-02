#!/usr/bin/env python3
"""
Migrate vector dimensions from 1536 to 1024 for Titan Embed v2.

This script handles all cases:
1. Direct SQL execution (bypasses alembic issues)
2. Updates application tables AND LightRAG tables
3. Works regardless of current alembic state

Usage:
    uv run python scripts/migrate_vector_dimension.py [--check|--migrate|--reset]

Options:
    --check   : Check current vector column dimensions (default)
    --migrate : Perform migration to 1024 dimensions
    --reset   : Drop all LightRAG data and recreate with 1024 dimensions
"""

import argparse
import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from core.config import settings


async def get_engine():
    """Create async database engine."""
    if not settings.DATABASE_URL:
        print("ERROR: DATABASE_URL not set")
        sys.exit(1)
    return create_async_engine(settings.DATABASE_URL, echo=False)


async def check_dimensions():
    """Check current vector column dimensions."""
    print("\n=== Current Vector Column Dimensions ===\n")

    engine = await get_engine()
    async with engine.begin() as conn:
        # Query for all vector columns
        result = await conn.execute(text("""
            SELECT
                t.tablename,
                a.attname as column_name,
                pg_catalog.format_type(a.atttypid, a.atttypmod) as data_type
            FROM pg_tables t
            JOIN pg_class c ON c.relname = t.tablename
            JOIN pg_attribute a ON a.attrelid = c.oid
            WHERE t.schemaname = 'public'
              AND pg_catalog.format_type(a.atttypid, a.atttypmod) LIKE 'vector%'
            ORDER BY t.tablename, a.attname
        """))
        rows = result.fetchall()

        if not rows:
            print("No vector columns found in database.")
            print("Tables will be created when you first insert data.")
        else:
            print(f"{'Table':<30} {'Column':<20} {'Type':<20}")
            print("-" * 70)
            for row in rows:
                print(f"{row[0]:<30} {row[1]:<20} {row[2]:<20}")

        # Check alembic version
        try:
            result = await conn.execute(text("SELECT version_num FROM alembic_version"))
            versions = result.fetchall()
            print(f"\nAlembic versions: {[v[0] for v in versions]}")
        except Exception:
            print("\nAlembic version table not found")

    await engine.dispose()


async def migrate_to_1024():
    """Migrate all vector columns to 1024 dimensions."""
    print("\n=== Migrating to 1024 Dimensions ===\n")

    engine = await get_engine()
    async with engine.begin() as conn:
        # 1. Ensure pgvector extension
        print("1. Ensuring pgvector extension...")
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        print("   OK")

        # 2. Application entities table
        print("2. Updating entities table...")
        await conn.execute(text("ALTER TABLE entities DROP COLUMN IF EXISTS embedding"))
        await conn.execute(text("ALTER TABLE entities ADD COLUMN embedding vector(1024)"))
        print("   OK")

        # 3. LightRAG tables (check actual table names)
        # Tables could be named: BODA_*, lightrag_vdb_*, or other patterns
        lightrag_tables = [
            # Pattern 1: BODA_* (workspace prefix)
            ("BODA_chunks", "__vector__"),
            ("BODA_entities", "__vector__"),
            ("BODA_relationships", "__vector__"),
            # Pattern 2: lightrag_vdb_* (library default)
            ("lightrag_vdb_chunks", "content_vector"),
            ("lightrag_vdb_entity", "content_vector"),
            ("lightrag_vdb_relation", "content_vector"),
        ]

        for table, column in lightrag_tables:
            print(f"3. Checking {table}.{column}...")
            result = await conn.execute(text(f"""
                SELECT EXISTS (
                    SELECT FROM pg_tables
                    WHERE schemaname = 'public' AND tablename = '{table}'
                )
            """))
            exists = result.scalar()

            if exists:
                # Check current dimension
                dim_result = await conn.execute(text(f"""
                    SELECT pg_catalog.format_type(a.atttypid, a.atttypmod)
                    FROM pg_attribute a
                    JOIN pg_class c ON a.attrelid = c.oid
                    WHERE c.relname = '{table}' AND a.attname = '{column}'
                """))
                current_dim = dim_result.scalar()

                if current_dim and '1024' in str(current_dim):
                    print(f"   {table}.{column} already at 1024 - skipping")
                else:
                    await conn.execute(text(f'ALTER TABLE "{table}" DROP COLUMN IF EXISTS "{column}"'))
                    await conn.execute(text(f'ALTER TABLE "{table}" ADD COLUMN "{column}" vector(1024)'))
                    print(f"   Updated {table}.{column}")
            else:
                print(f"   {table} doesn't exist - skipping")

        # 4. Update alembic version
        print("4. Updating alembic version...")
        try:
            await conn.execute(text("""
                INSERT INTO alembic_version (version_num) VALUES ('a1b2c3d4e5f6')
                ON CONFLICT (version_num) DO NOTHING
            """))
            # Also ensure the previous migration is marked
            await conn.execute(text("""
                INSERT INTO alembic_version (version_num) VALUES ('826ddedd5b20')
                ON CONFLICT (version_num) DO NOTHING
            """))
            print("   OK")
        except Exception as e:
            print(f"   Warning: {e}")

    await engine.dispose()

    print("\n=== Migration Complete ===")
    print("\nIMPORTANT: You must now re-index all documents!")
    print("All existing embeddings have been cleared.")


async def reset_lightrag_tables():
    """Drop all LightRAG tables and let them be recreated with correct dimensions."""
    print("\n=== Resetting LightRAG Tables ===\n")
    print("WARNING: This will delete ALL LightRAG data!")

    confirm = input("Type 'YES' to confirm: ")
    if confirm != "YES":
        print("Aborted.")
        return

    engine = await get_engine()
    async with engine.begin() as conn:
        lightrag_tables = [
            "BODA_chunks", "BODA_entities", "BODA_relationships",
            "BODA_kv", "BODA_doc_status", "BODA_llm_response_cache"
        ]

        for table in lightrag_tables:
            print(f"Dropping {table}...")
            await conn.execute(text(f'DROP TABLE IF EXISTS "{table}" CASCADE'))
            print(f"   Dropped {table}")

    await engine.dispose()

    # Also migrate the entities table
    await migrate_to_1024()

    print("\n=== Reset Complete ===")
    print("LightRAG tables will be recreated on next startup with 1024 dimensions.")


async def main():
    parser = argparse.ArgumentParser(description="Migrate vector dimensions to 1024")
    parser.add_argument("--check", action="store_true", help="Check current dimensions")
    parser.add_argument("--migrate", action="store_true", help="Perform migration")
    parser.add_argument("--reset", action="store_true", help="Reset LightRAG tables")

    args = parser.parse_args()

    if args.migrate:
        await migrate_to_1024()
    elif args.reset:
        await reset_lightrag_tables()
    else:
        await check_dimensions()


if __name__ == "__main__":
    asyncio.run(main())
