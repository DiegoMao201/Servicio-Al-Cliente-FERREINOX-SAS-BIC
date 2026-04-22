CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS public.agent_product_multimodal_index (
    id bigserial PRIMARY KEY,
    canonical_family text NOT NULL,
    source_doc_filename text NOT NULL,
    source_doc_path_lower text NOT NULL,
    marca text,
    summary_text text,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    embedding vector(1536) NOT NULL,
    generated_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_agent_product_multimodal_family UNIQUE (canonical_family)
);

CREATE INDEX IF NOT EXISTS idx_technical_chunks
    ON public.agent_technical_doc_chunk
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

CREATE INDEX IF NOT EXISTS idx_product_multimodal
    ON public.agent_product_multimodal_index
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);
