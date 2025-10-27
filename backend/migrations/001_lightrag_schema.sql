-- Migration: LightRAG Knowledge Graph Schema
-- Description: Create tables for LightRAG knowledge graph-based RAG system
-- Author: BODA Development Team
-- Date: 2025-01-22
-- Dependencies: Requires pgvector extension

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ==============================================================================
-- LightRAG Documents Table
-- ==============================================================================
-- Stores raw documents and chunked text units
CREATE TABLE IF NOT EXISTS lightrag_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content TEXT NOT NULL,
    content_hash VARCHAR(64) UNIQUE NOT NULL,  -- SHA256 hash for deduplication
    metadata JSONB DEFAULT '{}',
    source_type VARCHAR(50),  -- 'property', 'policy', 'conversation', 'web'
    source_id UUID,  -- Reference to original source (properties.id, policies.id, etc.)
    chunk_index INTEGER DEFAULT 0,  -- Index if document is chunked
    token_count INTEGER,  -- Approximate token count
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    -- Indexes for performance
    CONSTRAINT valid_source_type CHECK (source_type IN ('property', 'policy', 'conversation', 'web', 'general'))
);

CREATE INDEX idx_lightrag_documents_source ON lightrag_documents(source_type, source_id);
CREATE INDEX idx_lightrag_documents_hash ON lightrag_documents(content_hash);
CREATE INDEX idx_lightrag_documents_created ON lightrag_documents(created_at DESC);
CREATE INDEX idx_lightrag_documents_metadata ON lightrag_documents USING GIN (metadata);

-- ==============================================================================
-- LightRAG Entities Table
-- ==============================================================================
-- Stores extracted entities from documents (Property, Location, Policy, etc.)
CREATE TABLE IF NOT EXISTS lightrag_entities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_type VARCHAR(50) NOT NULL,  -- 'Property', 'Location', 'Policy', etc.
    entity_name VARCHAR(255) NOT NULL,
    entity_name_normalized VARCHAR(255),  -- Normalized for matching (lowercase, no spaces)
    description TEXT,  -- Entity description from extraction
    properties JSONB DEFAULT '{}',  -- Additional entity properties
    source_document_ids UUID[],  -- Documents where this entity was extracted
    extraction_confidence FLOAT DEFAULT 0.0,  -- Confidence score from LLM extraction
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    -- Unique constraint on type + normalized name
    UNIQUE(entity_type, entity_name_normalized),

    -- Constraints
    CONSTRAINT valid_entity_type CHECK (entity_type IN (
        'Property', 'Location', 'Policy', 'Demographic',
        'Institution', 'PriceRange', 'PropertyType', 'Landmark'
    )),
    CONSTRAINT valid_confidence CHECK (extraction_confidence >= 0.0 AND extraction_confidence <= 1.0)
);

CREATE INDEX idx_lightrag_entities_type ON lightrag_entities(entity_type);
CREATE INDEX idx_lightrag_entities_name ON lightrag_entities(entity_name);
CREATE INDEX idx_lightrag_entities_normalized ON lightrag_entities(entity_name_normalized);
CREATE INDEX idx_lightrag_entities_properties ON lightrag_entities USING GIN (properties);

-- ==============================================================================
-- LightRAG Relationships Table
-- ==============================================================================
-- Stores relationships between entities (knowledge graph edges)
CREATE TABLE IF NOT EXISTS lightrag_relationships (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_entity_id UUID NOT NULL REFERENCES lightrag_entities(id) ON DELETE CASCADE,
    target_entity_id UUID NOT NULL REFERENCES lightrag_entities(id) ON DELETE CASCADE,
    relationship_type VARCHAR(50) NOT NULL,  -- 'LOCATED_IN', 'ELIGIBLE_FOR', etc.
    relationship_description TEXT,  -- Textual description of the relationship
    properties JSONB DEFAULT '{}',  -- Additional relationship properties
    weight FLOAT DEFAULT 1.0,  -- Relationship strength/importance
    source_document_ids UUID[],  -- Documents supporting this relationship
    extraction_confidence FLOAT DEFAULT 0.0,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    -- Prevent duplicate relationships
    UNIQUE(source_entity_id, target_entity_id, relationship_type),

    -- Constraints
    CONSTRAINT valid_relationship_type CHECK (relationship_type IN (
        'LOCATED_IN', 'ELIGIBLE_FOR', 'QUALIFIES_FOR', 'TARGETS',
        'NEAR', 'PRICE_TREND', 'ADMINISTERED_BY', 'TYPE_OF',
        'HAS_PROPERTY', 'RELATED_TO', 'PART_OF', 'REQUIRES'
    )),
    CONSTRAINT valid_weight CHECK (weight >= 0.0 AND weight <= 10.0),
    CONSTRAINT valid_confidence_rel CHECK (extraction_confidence >= 0.0 AND extraction_confidence <= 1.0)
);

CREATE INDEX idx_lightrag_relationships_source ON lightrag_relationships(source_entity_id);
CREATE INDEX idx_lightrag_relationships_target ON lightrag_relationships(target_entity_id);
CREATE INDEX idx_lightrag_relationships_type ON lightrag_relationships(relationship_type);
CREATE INDEX idx_lightrag_relationships_both ON lightrag_relationships(source_entity_id, target_entity_id);
CREATE INDEX idx_lightrag_relationships_weight ON lightrag_relationships(weight DESC);

-- ==============================================================================
-- LightRAG Embeddings Table
-- ==============================================================================
-- Stores vector embeddings for documents and text units
CREATE TABLE IF NOT EXISTS lightrag_embeddings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID REFERENCES lightrag_documents(id) ON DELETE CASCADE,
    entity_id UUID REFERENCES lightrag_entities(id) ON DELETE CASCADE,
    embedding vector(1536),  -- AWS Bedrock Titan Embed Text v1 dimension
    embedding_model VARCHAR(100) DEFAULT 'amazon.titan-embed-text-v1',
    embedding_type VARCHAR(50) DEFAULT 'document',  -- 'document', 'entity', 'relationship'
    created_at TIMESTAMP DEFAULT NOW(),

    -- Either document_id or entity_id must be set, not both
    CONSTRAINT embedding_reference CHECK (
        (document_id IS NOT NULL AND entity_id IS NULL) OR
        (document_id IS NULL AND entity_id IS NOT NULL)
    ),

    -- Unique embeddings per document/entity
    UNIQUE(document_id, embedding_model),
    UNIQUE(entity_id, embedding_model)
);

-- Vector similarity search index (IVFFlat for faster approximate search)
CREATE INDEX idx_lightrag_embeddings_vector ON lightrag_embeddings
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

CREATE INDEX idx_lightrag_embeddings_document ON lightrag_embeddings(document_id);
CREATE INDEX idx_lightrag_embeddings_entity ON lightrag_embeddings(entity_id);
CREATE INDEX idx_lightrag_embeddings_model ON lightrag_embeddings(embedding_model);

-- ==============================================================================
-- LightRAG Query Cache Table
-- ==============================================================================
-- Stores cached query results for performance optimization
CREATE TABLE IF NOT EXISTS lightrag_query_cache (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    query_text TEXT NOT NULL,
    query_hash VARCHAR(64) UNIQUE NOT NULL,  -- SHA256 of normalized query
    query_mode VARCHAR(20) NOT NULL,  -- 'local', 'global', 'hybrid', 'naive'
    result_text TEXT NOT NULL,
    result_entities UUID[],  -- Entity IDs in the result
    result_documents UUID[],  -- Document IDs in the result
    query_params JSONB DEFAULT '{}',  -- QueryParam settings used
    hit_count INTEGER DEFAULT 0,  -- Number of times this cache was used
    created_at TIMESTAMP DEFAULT NOW(),
    last_accessed_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP,  -- Optional expiration

    CONSTRAINT valid_query_mode CHECK (query_mode IN ('local', 'global', 'hybrid', 'naive', 'mix', 'bypass'))
);

CREATE INDEX idx_lightrag_query_cache_hash ON lightrag_query_cache(query_hash);
CREATE INDEX idx_lightrag_query_cache_mode ON lightrag_query_cache(query_mode);
CREATE INDEX idx_lightrag_query_cache_accessed ON lightrag_query_cache(last_accessed_at DESC);
CREATE INDEX idx_lightrag_query_cache_expires ON lightrag_query_cache(expires_at);

-- ==============================================================================
-- LightRAG Pipeline Status Table
-- ==============================================================================
-- Tracks indexing and processing pipeline status
CREATE TABLE IF NOT EXISTS lightrag_pipeline_status (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pipeline_type VARCHAR(50) NOT NULL,  -- 'indexing', 'extraction', 'embedding', 'graph_build'
    status VARCHAR(20) NOT NULL,  -- 'pending', 'running', 'completed', 'failed'
    total_items INTEGER DEFAULT 0,
    processed_items INTEGER DEFAULT 0,
    failed_items INTEGER DEFAULT 0,
    error_messages JSONB DEFAULT '[]',
    metadata JSONB DEFAULT '{}',
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    CONSTRAINT valid_pipeline_type CHECK (pipeline_type IN ('indexing', 'extraction', 'embedding', 'graph_build', 'migration')),
    CONSTRAINT valid_status CHECK (status IN ('pending', 'running', 'completed', 'failed', 'cancelled'))
);

CREATE INDEX idx_lightrag_pipeline_type ON lightrag_pipeline_status(pipeline_type);
CREATE INDEX idx_lightrag_pipeline_status ON lightrag_pipeline_status(status);
CREATE INDEX idx_lightrag_pipeline_created ON lightrag_pipeline_status(created_at DESC);

-- ==============================================================================
-- LightRAG Metrics Table
-- ==============================================================================
-- Stores performance and quality metrics
CREATE TABLE IF NOT EXISTS lightrag_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    metric_type VARCHAR(50) NOT NULL,  -- 'query_performance', 'extraction_quality', 'graph_quality'
    metric_name VARCHAR(100) NOT NULL,
    metric_value FLOAT NOT NULL,
    metadata JSONB DEFAULT '{}',
    recorded_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_lightrag_metrics_type ON lightrag_metrics(metric_type);
CREATE INDEX idx_lightrag_metrics_name ON lightrag_metrics(metric_name);
CREATE INDEX idx_lightrag_metrics_recorded ON lightrag_metrics(recorded_at DESC);

-- ==============================================================================
-- Functions and Triggers
-- ==============================================================================

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply updated_at trigger to relevant tables
CREATE TRIGGER update_lightrag_documents_updated_at
    BEFORE UPDATE ON lightrag_documents
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_lightrag_entities_updated_at
    BEFORE UPDATE ON lightrag_entities
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_lightrag_relationships_updated_at
    BEFORE UPDATE ON lightrag_relationships
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_lightrag_pipeline_status_updated_at
    BEFORE UPDATE ON lightrag_pipeline_status
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Function to normalize entity names
CREATE OR REPLACE FUNCTION normalize_entity_name(name TEXT)
RETURNS TEXT AS $$
BEGIN
    -- Normalize: lowercase, remove extra spaces, trim
    RETURN LOWER(TRIM(REGEXP_REPLACE(name, '\s+', ' ', 'g')));
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Trigger to auto-normalize entity names
CREATE OR REPLACE FUNCTION auto_normalize_entity_name()
RETURNS TRIGGER AS $$
BEGIN
    NEW.entity_name_normalized = normalize_entity_name(NEW.entity_name);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER normalize_entity_name_trigger
    BEFORE INSERT OR UPDATE ON lightrag_entities
    FOR EACH ROW EXECUTE FUNCTION auto_normalize_entity_name();

-- Function to calculate content hash
CREATE OR REPLACE FUNCTION calculate_content_hash(content TEXT)
RETURNS VARCHAR(64) AS $$
BEGIN
    RETURN encode(digest(content, 'sha256'), 'hex');
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Trigger to auto-calculate content hash
CREATE OR REPLACE FUNCTION auto_calculate_content_hash()
RETURNS TRIGGER AS $$
BEGIN
    NEW.content_hash = calculate_content_hash(NEW.content);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER calculate_content_hash_trigger
    BEFORE INSERT OR UPDATE ON lightrag_documents
    FOR EACH ROW EXECUTE FUNCTION auto_calculate_content_hash();

-- ==============================================================================
-- Helper Views
-- ==============================================================================

-- View: Entity relationship graph overview
CREATE OR REPLACE VIEW lightrag_graph_overview AS
SELECT
    e1.entity_type AS source_type,
    e1.entity_name AS source_name,
    r.relationship_type,
    e2.entity_type AS target_type,
    e2.entity_name AS target_name,
    r.weight,
    r.extraction_confidence
FROM lightrag_relationships r
JOIN lightrag_entities e1 ON r.source_entity_id = e1.id
JOIN lightrag_entities e2 ON r.target_entity_id = e2.id
ORDER BY r.weight DESC, r.extraction_confidence DESC;

-- View: Entity with embedding count
CREATE OR REPLACE VIEW lightrag_entities_with_embeddings AS
SELECT
    e.*,
    COUNT(emb.id) AS embedding_count
FROM lightrag_entities e
LEFT JOIN lightrag_embeddings emb ON e.id = emb.entity_id
GROUP BY e.id;

-- View: Document processing status
CREATE OR REPLACE VIEW lightrag_document_status AS
SELECT
    d.id,
    d.source_type,
    d.source_id,
    d.created_at,
    COUNT(DISTINCT emb.id) AS has_embeddings,
    COUNT(DISTINCT e.id) AS extracted_entities,
    CASE
        WHEN COUNT(DISTINCT emb.id) > 0 AND COUNT(DISTINCT e.id) > 0 THEN 'processed'
        WHEN COUNT(DISTINCT emb.id) > 0 THEN 'embedded'
        ELSE 'pending'
    END AS processing_status
FROM lightrag_documents d
LEFT JOIN lightrag_embeddings emb ON d.id = emb.document_id
LEFT JOIN lightrag_entities e ON d.id = ANY(e.source_document_ids)
GROUP BY d.id;

-- ==============================================================================
-- Grants (adjust based on your security model)
-- ==============================================================================

-- Grant access to application role (adjust role name as needed)
-- GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO your_app_role;
-- GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO your_app_role;
-- GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO your_app_role;

-- ==============================================================================
-- Migration Complete
-- ==============================================================================

COMMENT ON TABLE lightrag_documents IS 'Stores raw documents and text chunks for LightRAG indexing';
COMMENT ON TABLE lightrag_entities IS 'Knowledge graph entities extracted from documents (Property, Location, Policy, etc.)';
COMMENT ON TABLE lightrag_relationships IS 'Knowledge graph relationships between entities (edges in the graph)';
COMMENT ON TABLE lightrag_embeddings IS 'Vector embeddings for semantic search (documents and entities)';
COMMENT ON TABLE lightrag_query_cache IS 'Cached query results for performance optimization';
COMMENT ON TABLE lightrag_pipeline_status IS 'Tracks indexing and processing pipeline status';
COMMENT ON TABLE lightrag_metrics IS 'Performance and quality metrics for LightRAG system';
