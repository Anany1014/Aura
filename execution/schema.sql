-- Aura: Core Schema Graph Traversal using PostgreSQL & pgvector

-- Enable vector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Enable uuid-ossp for UUID generation
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Table for graph nodes representing parsed academic/enterprise data
CREATE TABLE IF NOT EXISTS public.nodes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title VARCHAR(255) NOT NULL,
    domain VARCHAR(100) NOT NULL,        -- e.g. "biotech", "fintech", "materials", "nlp"
    type VARCHAR(50) NOT NULL,          -- e.g. "paper", "patent", "startup", "code"
    summary TEXT NOT NULL,              -- Short summary to feed Claude during synthesis
    embedding vector(1536),             -- OpenAI text-embedding-3-small dimensions (1536)
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Table for graph edges representing semantic relationships
CREATE TABLE IF NOT EXISTS public.edges (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_node_id UUID NOT NULL REFERENCES public.nodes(id) ON DELETE CASCADE,
    target_node_id UUID NOT NULL REFERENCES public.nodes(id) ON DELETE CASCADE,
    relationship_type VARCHAR(50) NOT NULL,  -- e.g. "references", "implements", "competes_with"
    semantic_distance DOUBLE PRECISION NOT NULL, -- cosine distance (1 - cosine_similarity)
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_edge UNIQUE (source_node_id, target_node_id, relationship_type)
);

-- Table for Cognee tracking (architectural decisions, heuristics, failed patterns)
CREATE TABLE IF NOT EXISTS public.cognee_metadata (
    key VARCHAR(255) PRIMARY KEY,
    value JSONB NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Performance Indexes
CREATE INDEX IF NOT EXISTS idx_nodes_domain ON public.nodes (domain);
CREATE INDEX IF NOT EXISTS idx_nodes_type ON public.nodes (type);
CREATE INDEX IF NOT EXISTS idx_edges_source ON public.edges (source_node_id);
CREATE INDEX IF NOT EXISTS idx_edges_target ON public.edges (target_node_id);
CREATE INDEX IF NOT EXISTS idx_edges_semantic_distance ON public.edges (semantic_distance);

-- Vector HNSW index for rapid cosine similarity searches
CREATE INDEX IF NOT EXISTS idx_nodes_embedding_cosine ON public.nodes USING hnsw (embedding vector_cosine_ops);
