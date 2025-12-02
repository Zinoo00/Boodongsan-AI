-- ============================================================================
-- Migration: Change vector dimensions from 1536 to 1024
-- For AWS Titan Embed v2 (supports 256, 512, 1024 dimensions)
-- ============================================================================
--
-- Run this script directly on PostgreSQL if alembic has issues:
--   psql $DATABASE_URL -f scripts/migrate_to_1024_dimensions.sql
--
-- WARNING: This will DROP all existing embeddings!
-- You must re-index all documents after running this migration.
-- ============================================================================

-- Ensure pgvector extension exists
CREATE EXTENSION IF NOT EXISTS vector;

-- ============================================================================
-- 1. Application tables (defined in database/models.py)
-- ============================================================================

-- entities table - embedding column
ALTER TABLE entities DROP COLUMN IF EXISTS embedding;
ALTER TABLE entities ADD COLUMN embedding vector(1024);

-- ============================================================================
-- 2. LightRAG internal tables (created by LightRAG library)
-- Workspace: BODA (from settings.LIGHTRAG_WORKSPACE)
-- ============================================================================

-- BODA_chunks table
DO $$
BEGIN
    IF EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = 'BODA_chunks') THEN
        ALTER TABLE "BODA_chunks" DROP COLUMN IF EXISTS "__vector__";
        ALTER TABLE "BODA_chunks" ADD COLUMN "__vector__" vector(1024);
        RAISE NOTICE 'Updated BODA_chunks.__vector__ to 1024 dimensions';
    ELSE
        RAISE NOTICE 'Table BODA_chunks does not exist (will be created on first insert)';
    END IF;
END $$;

-- BODA_entities table
DO $$
BEGIN
    IF EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = 'BODA_entities') THEN
        ALTER TABLE "BODA_entities" DROP COLUMN IF EXISTS "__vector__";
        ALTER TABLE "BODA_entities" ADD COLUMN "__vector__" vector(1024);
        RAISE NOTICE 'Updated BODA_entities.__vector__ to 1024 dimensions';
    ELSE
        RAISE NOTICE 'Table BODA_entities does not exist (will be created on first insert)';
    END IF;
END $$;

-- BODA_relationships table
DO $$
BEGIN
    IF EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = 'BODA_relationships') THEN
        ALTER TABLE "BODA_relationships" DROP COLUMN IF EXISTS "__vector__";
        ALTER TABLE "BODA_relationships" ADD COLUMN "__vector__" vector(1024);
        RAISE NOTICE 'Updated BODA_relationships.__vector__ to 1024 dimensions';
    ELSE
        RAISE NOTICE 'Table BODA_relationships does not exist (will be created on first insert)';
    END IF;
END $$;

-- ============================================================================
-- 3. Update alembic version (mark migration as complete)
-- ============================================================================

-- Insert or update alembic version
INSERT INTO alembic_version (version_num)
VALUES ('a1b2c3d4e5f6')
ON CONFLICT (version_num) DO NOTHING;

-- Verify current state
DO $$
BEGIN
    RAISE NOTICE '============================================';
    RAISE NOTICE 'Migration complete!';
    RAISE NOTICE 'All vector columns updated to 1024 dimensions';
    RAISE NOTICE '============================================';
    RAISE NOTICE 'IMPORTANT: You must now re-index all documents';
    RAISE NOTICE 'Run: python scripts/load_data.py';
    RAISE NOTICE '============================================';
END $$;

-- Show current vector column dimensions
SELECT
    t.tablename,
    a.attname as column_name,
    pg_catalog.format_type(a.atttypid, a.atttypmod) as data_type
FROM pg_tables t
JOIN pg_class c ON c.relname = t.tablename
JOIN pg_attribute a ON a.attrelid = c.oid
WHERE t.schemaname = 'public'
  AND pg_catalog.format_type(a.atttypid, a.atttypmod) LIKE 'vector%'
ORDER BY t.tablename, a.attname;
