-- ============================================================
-- SETUP PGVECTOR + TABLAS NUEVAS — Ejecutar UNA SOLA VEZ
-- en la terminal de PostgreSQL de Coolify:
--   psql -U postgres -d postgres
--   \i SETUP_PGVECTOR_COOLIFY.sql   (o pegar todo el contenido)
--   \q
-- ============================================================

-- 1. Habilitar extensión pgvector
CREATE EXTENSION IF NOT EXISTS vector;

-- 2. Tabla de chunks vectorizados de fichas técnicas (RAG)
CREATE TABLE IF NOT EXISTS public.agent_technical_doc_chunk (
    id bigserial PRIMARY KEY,
    doc_filename text NOT NULL,
    doc_path_lower text NOT NULL,
    chunk_index integer NOT NULL DEFAULT 0,
    chunk_text text NOT NULL,
    marca text,
    familia_producto text,
    tipo_documento varchar(30) NOT NULL DEFAULT 'ficha_tecnica',
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    embedding vector(1536) NOT NULL,
    token_count integer,
    ingested_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_agent_doc_chunk UNIQUE (doc_path_lower, chunk_index)
);

CREATE INDEX IF NOT EXISTS idx_agent_doc_chunk_filename ON public.agent_technical_doc_chunk(doc_filename);
CREATE INDEX IF NOT EXISTS idx_agent_doc_chunk_marca ON public.agent_technical_doc_chunk(marca);
CREATE INDEX IF NOT EXISTS idx_agent_doc_chunk_familia ON public.agent_technical_doc_chunk(familia_producto);
CREATE INDEX IF NOT EXISTS idx_agent_doc_chunk_tipo ON public.agent_technical_doc_chunk(tipo_documento);
CREATE INDEX IF NOT EXISTS idx_agent_doc_chunk_embedding
    ON public.agent_technical_doc_chunk
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- 3. Tabla de productos complementarios (catalizadores, diluyentes, etc.)
CREATE TABLE IF NOT EXISTS public.agent_product_companion (
    id bigserial PRIMARY KEY,
    producto_referencia text NOT NULL,
    producto_descripcion text,
    companion_referencia text NOT NULL,
    companion_descripcion text,
    tipo_relacion varchar(60) NOT NULL,
    proporcion text,
    notas text,
    source_conversation_id bigint REFERENCES public.agent_conversation(id) ON DELETE SET NULL,
    confidence numeric(5,4) NOT NULL DEFAULT 0.9500,
    activo boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_agent_product_companion UNIQUE (producto_referencia, companion_referencia, tipo_relacion)
);

CREATE INDEX IF NOT EXISTS idx_agent_product_companion_ref ON public.agent_product_companion(producto_referencia);
CREATE INDEX IF NOT EXISTS idx_agent_product_companion_companion ON public.agent_product_companion(companion_referencia);

-- ============================================================
-- ✅ PASO 1 COMPLETADO — Las tablas ya están creadas.
-- ============================================================
--
-- ============================================================
-- PASO 2: TERMINAL DEL BACKEND PYTHON EN COOLIFY
-- ============================================================
--
-- 1. En Coolify, ve a tu proyecto → click en "Terminal" (menú superior)
-- 2. Selecciona el contenedor del BACKEND (el de Python/FastAPI,
--    NO el de PostgreSQL ni el de frontend)
-- 3. Una vez dentro de la terminal del backend, ejecuta:
--
--    PRUEBA EN SECO (solo lista los PDFs sin procesarlos):
--
--        python ingest_technical_sheets.py --dry-run
--
--    Si ves la lista de PDFs sin errores, lanza la ingestión real:
--
--        python ingest_technical_sheets.py --full
--
--    Esto descargará ~1000 PDFs de Dropbox, extraerá el texto,
--    generará embeddings con OpenAI, y los guardará en PostgreSQL.
--    Puede tardar 15-30 minutos dependiendo del servidor.
--
-- ============================================================
-- ⚠️  SI SE CAYÓ LA TERMINAL durante la ingestión --full:
--     Los chunks ya insertados NO se pierden.
--     Ejecuta el modo INCREMENTAL para retomar donde quedó:
--
--        python ingest_technical_sheets.py
--
--     (sin --full). Solo procesará los PDFs que faltan.
-- ============================================================
--
-- 4. Cuando termine, verifica que hay datos:
--    (vuelve a la terminal de PostgreSQL)
--
--        psql -U postgres -d postgres
--        SELECT COUNT(*) FROM public.agent_technical_doc_chunk;
--        SELECT doc_filename, COUNT(*) as chunks FROM public.agent_technical_doc_chunk GROUP BY doc_filename LIMIT 10;
--        \q
--
-- ============================================================
