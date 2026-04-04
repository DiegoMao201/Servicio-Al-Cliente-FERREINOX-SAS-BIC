#!/usr/bin/env python3
"""
Ingestión de fichas técnicas: Dropbox → PyMuPDF → OpenAI Embeddings → PostgreSQL pgvector.

Uso:
    python backend/ingest_technical_sheets.py               # Ingesta incremental (solo PDFs nuevos)
    python backend/ingest_technical_sheets.py --full         # Re-ingesta completa (borra y recarga todo)
    python backend/ingest_technical_sheets.py --dry-run      # Solo lista PDFs sin procesar

Variables de entorno requeridas:
    DATABASE_URL / POSTGRES_DB_URI
    OPENAI_API_KEY
    DROPBOX_VENTAS_REFRESH_TOKEN, DROPBOX_VENTAS_APP_KEY, DROPBOX_VENTAS_APP_SECRET
    (o .streamlit/secrets.toml con las mismas claves)
"""

import argparse
import io
import json
import logging
import os
import re
import sys
import time
from pathlib import Path

import dropbox
import fitz  # PyMuPDF
from openai import OpenAI
from sqlalchemy import create_engine, text

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
TECHNICAL_DOC_FOLDER = "/data/FICHAS TÉCNICAS Y HOJAS DE SEGURIDAD"
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSIONS = 1536
CHUNK_MAX_CHARS = 2000       # ~500 tokens
CHUNK_OVERLAP_CHARS = 300    # ~75 tokens overlap
BATCH_EMBED_SIZE = 50        # OpenAI batch limit per call
DOC_TYPE_SAFETY_TOKENS = ["hoja de seguridad", "fds", "msds", "safety data"]
BRAND_PATTERNS = [
    "pintuco", "viniltex", "koraza", "pintulux", "domestico", "doméstico",
    "aerocolor", "abracol", "yale", "goya", "mega", "international",
    "interseal", "intergard", "interchar", "interzone", "interthane",
]


# ---------------------------------------------------------------------------
# Secrets / connections (mirrors main.py patterns)
# ---------------------------------------------------------------------------
def load_local_secrets():
    secrets_path = Path(__file__).resolve().parent.parent / ".streamlit" / "secrets.toml"
    if not secrets_path.exists():
        return {}
    try:
        import tomllib
    except ModuleNotFoundError:
        try:
            import tomli as tomllib
        except ModuleNotFoundError:
            return {}
    return tomllib.loads(secrets_path.read_text(encoding="utf-8"))


def get_database_url():
    url = os.getenv("DATABASE_URL") or os.getenv("POSTGRES_DB_URI")
    if url:
        return url
    secrets = load_local_secrets()
    pg = secrets.get("postgres") or {}
    url = pg.get("db_uri") or pg.get("DATABASE_URL")
    if url:
        return url
    raise RuntimeError("No se encontró DATABASE_URL. Configure la variable o .streamlit/secrets.toml")


def get_openai_api_key():
    key = os.getenv("OPENAI_API_KEY")
    if key:
        return key
    secrets = load_local_secrets()
    return (secrets.get("openai") or {}).get("api_key") or secrets.get("OPENAI_API_KEY")


def get_dropbox_client():
    refresh = os.getenv("DROPBOX_VENTAS_REFRESH_TOKEN")
    app_key = os.getenv("DROPBOX_VENTAS_APP_KEY")
    app_secret = os.getenv("DROPBOX_VENTAS_APP_SECRET")
    if not (refresh and app_key and app_secret):
        secrets = load_local_secrets()
        cfg = secrets.get("dropbox_ventas") or {}
        refresh = refresh or cfg.get("refresh_token")
        app_key = app_key or cfg.get("app_key")
        app_secret = app_secret or cfg.get("app_secret")
    if not (refresh and app_key and app_secret):
        raise RuntimeError("Faltan credenciales de Dropbox (DROPBOX_VENTAS_*)")
    return dropbox.Dropbox(oauth2_refresh_token=refresh, app_key=app_key, app_secret=app_secret)


def get_db_engine():
    return create_engine(get_database_url())


def get_openai_client():
    key = get_openai_api_key()
    if not key:
        raise RuntimeError("No se encontró OPENAI_API_KEY")
    return OpenAI(api_key=key)


# ---------------------------------------------------------------------------
# Table bootstrap
# ---------------------------------------------------------------------------
def ensure_chunk_table(engine):
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.execute(text("""
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
            )
        """))
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_agent_doc_chunk_embedding
                ON public.agent_technical_doc_chunk
                USING hnsw (embedding vector_cosine_ops)
                WITH (m = 16, ef_construction = 64)
        """))
    logger.info("Tabla agent_technical_doc_chunk verificada/creada.")


# ---------------------------------------------------------------------------
# Dropbox: list PDFs
# ---------------------------------------------------------------------------
def list_dropbox_pdfs(dbx) -> list[dict]:
    entries = []
    result = dbx.files_list_folder(TECHNICAL_DOC_FOLDER, recursive=True)
    while True:
        for entry in result.entries:
            if isinstance(entry, dropbox.files.FileMetadata) and entry.name.lower().endswith(".pdf"):
                entries.append({
                    "name": entry.name,
                    "path_lower": entry.path_lower,
                    "size": entry.size,
                    "content_hash": entry.content_hash,
                })
        if not result.has_more:
            break
        result = dbx.files_list_folder_continue(result.cursor)
    return entries


def download_pdf_bytes(dbx, path_lower: str) -> bytes:
    _, response = dbx.files_download(path_lower)
    return response.content


# ---------------------------------------------------------------------------
# PDF → texto
# ---------------------------------------------------------------------------
def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pages = []
    for page in doc:
        text_content = page.get_text("text")
        if text_content and text_content.strip():
            pages.append(text_content.strip())
    doc.close()
    return "\n\n".join(pages)


def clean_extracted_text(raw_text: str) -> str:
    text = re.sub(r"\n{3,}", "\n\n", raw_text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" \n", "\n", text)
    return text.strip()


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------
def chunk_text(text: str, max_chars: int = CHUNK_MAX_CHARS, overlap: int = CHUNK_OVERLAP_CHARS) -> list[str]:
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = start + max_chars
        if end < len(text):
            # Try to break at paragraph or sentence
            break_at = text.rfind("\n\n", start + max_chars // 2, end)
            if break_at == -1:
                break_at = text.rfind(". ", start + max_chars // 2, end)
            if break_at > start:
                end = break_at + 1
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start = end - overlap if end < len(text) else len(text)
    return chunks


# ---------------------------------------------------------------------------
# Metadata inference from filename/path
# ---------------------------------------------------------------------------
def infer_doc_type(filename: str, path_lower: str) -> str:
    combined = (filename + " " + path_lower).lower()
    if any(tok in combined for tok in DOC_TYPE_SAFETY_TOKENS):
        return "hoja_seguridad"
    return "ficha_tecnica"


def infer_brand(filename: str, path_lower: str) -> str | None:
    combined = (filename + " " + path_lower).lower()
    for brand in BRAND_PATTERNS:
        if brand in combined:
            return brand.capitalize()
    return None


def infer_family(filename: str) -> str | None:
    name_clean = re.sub(r"\.pdf$", "", filename, flags=re.IGNORECASE).strip()
    name_clean = re.sub(r"\s*\(.*?\)\s*", " ", name_clean)
    name_clean = re.sub(r"_+", " ", name_clean).strip()
    if name_clean:
        return name_clean
    return None


# ---------------------------------------------------------------------------
# Embeddings
# ---------------------------------------------------------------------------
def generate_embeddings(client: OpenAI, texts: list[str]) -> list[list[float]]:
    all_embeddings = []
    for i in range(0, len(texts), BATCH_EMBED_SIZE):
        batch = texts[i:i + BATCH_EMBED_SIZE]
        response = client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=batch,
            dimensions=EMBEDDING_DIMENSIONS,
        )
        batch_embeddings = [item.embedding for item in sorted(response.data, key=lambda x: x.index)]
        all_embeddings.extend(batch_embeddings)
        if i + BATCH_EMBED_SIZE < len(texts):
            time.sleep(0.25)
    return all_embeddings


# ---------------------------------------------------------------------------
# DB: check already ingested, insert chunks
# ---------------------------------------------------------------------------
def get_ingested_paths(engine) -> set[str]:
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT DISTINCT doc_path_lower FROM public.agent_technical_doc_chunk")).fetchall()
    return {row[0] for row in rows}


def delete_doc_chunks(engine, path_lower: str):
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM public.agent_technical_doc_chunk WHERE doc_path_lower = :p"), {"p": path_lower})


def insert_chunks(engine, chunks_data: list[dict]):
    with engine.begin() as conn:
        for chunk in chunks_data:
            embedding_literal = "[" + ",".join(str(v) for v in chunk["embedding"]) + "]"
            conn.execute(
                text("""
                    INSERT INTO public.agent_technical_doc_chunk
                        (doc_filename, doc_path_lower, chunk_index, chunk_text,
                         marca, familia_producto, tipo_documento, metadata,
                         embedding, token_count)
                    VALUES
                        (:filename, :path_lower, :chunk_index, :chunk_text,
                         :marca, :familia, :tipo_doc, :metadata::jsonb,
                         :embedding::vector, :token_count)
                    ON CONFLICT (doc_path_lower, chunk_index) DO UPDATE SET
                        chunk_text = EXCLUDED.chunk_text,
                        marca = EXCLUDED.marca,
                        familia_producto = EXCLUDED.familia_producto,
                        tipo_documento = EXCLUDED.tipo_documento,
                        metadata = EXCLUDED.metadata,
                        embedding = EXCLUDED.embedding,
                        token_count = EXCLUDED.token_count,
                        ingested_at = now()
                """),
                {
                    "filename": chunk["doc_filename"],
                    "path_lower": chunk["doc_path_lower"],
                    "chunk_index": chunk["chunk_index"],
                    "chunk_text": chunk["chunk_text"],
                    "marca": chunk["marca"],
                    "familia": chunk["familia_producto"],
                    "tipo_doc": chunk["tipo_documento"],
                    "metadata": json.dumps(chunk.get("metadata") or {}, ensure_ascii=False),
                    "embedding": embedding_literal,
                    "token_count": chunk.get("token_count"),
                },
            )


# ---------------------------------------------------------------------------
# Main ingestion pipeline
# ---------------------------------------------------------------------------
def ingest_pdf(dbx, openai_client, engine, pdf_entry: dict) -> int:
    filename = pdf_entry["name"]
    path_lower = pdf_entry["path_lower"]
    logger.info(f"  Descargando: {filename} ...")

    pdf_bytes = download_pdf_bytes(dbx, path_lower)
    raw_text = extract_text_from_pdf(pdf_bytes)
    if not raw_text or len(raw_text.strip()) < 50:
        logger.warning(f"  ⚠ PDF sin texto extraíble: {filename} (puede ser imagen/escaneo)")
        return 0

    clean_text = clean_extracted_text(raw_text)
    chunks = chunk_text(clean_text)
    if not chunks:
        return 0

    logger.info(f"  {len(chunks)} chunks generados, generando embeddings...")
    embeddings = generate_embeddings(openai_client, chunks)

    marca = infer_brand(filename, path_lower)
    familia = infer_family(filename)
    tipo_doc = infer_doc_type(filename, path_lower)

    chunks_data = []
    for idx, (chunk_text_val, embedding) in enumerate(zip(chunks, embeddings)):
        chunks_data.append({
            "doc_filename": filename,
            "doc_path_lower": path_lower,
            "chunk_index": idx,
            "chunk_text": chunk_text_val,
            "marca": marca,
            "familia_producto": familia,
            "tipo_documento": tipo_doc,
            "metadata": {"content_hash": pdf_entry.get("content_hash"), "size": pdf_entry.get("size")},
            "embedding": embedding,
            "token_count": len(chunk_text_val) // 4,
        })

    delete_doc_chunks(engine, path_lower)
    insert_chunks(engine, chunks_data)
    logger.info(f"  ✅ {filename}: {len(chunks_data)} chunks insertados")
    return len(chunks_data)


def run_ingestion(full_mode: bool = False, dry_run: bool = False):
    logger.info("=" * 60)
    logger.info("INGESTIÓN DE FICHAS TÉCNICAS → pgvector")
    logger.info("=" * 60)

    engine = get_db_engine()
    ensure_chunk_table(engine)

    dbx = get_dropbox_client()
    openai_client = get_openai_client()

    logger.info(f"Listando PDFs en Dropbox: {TECHNICAL_DOC_FOLDER}")
    pdf_entries = list_dropbox_pdfs(dbx)
    logger.info(f"  Encontrados: {len(pdf_entries)} PDFs")

    if full_mode:
        logger.info("Modo COMPLETO: borrando datos anteriores...")
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM public.agent_technical_doc_chunk"))
        already_ingested = set()
    else:
        already_ingested = get_ingested_paths(engine)
        logger.info(f"  Ya ingestados: {len(already_ingested)} documentos")

    pending = [e for e in pdf_entries if e["path_lower"] not in already_ingested]
    logger.info(f"  Pendientes: {len(pending)} PDFs nuevos")

    if dry_run:
        for entry in pending:
            logger.info(f"    [DRY-RUN] {entry['name']} ({entry['size']} bytes)")
        logger.info("Dry-run completado. No se procesó nada.")
        return

    total_chunks = 0
    errors = 0
    for i, entry in enumerate(pending, 1):
        try:
            logger.info(f"[{i}/{len(pending)}] Procesando: {entry['name']}")
            n = ingest_pdf(dbx, openai_client, engine, entry)
            total_chunks += n
        except Exception as exc:
            logger.error(f"  ✗ Error en {entry['name']}: {exc}")
            errors += 1
            continue

    logger.info("=" * 60)
    logger.info(f"RESULTADO: {len(pending) - errors}/{len(pending)} PDFs procesados, {total_chunks} chunks totales, {errors} errores")
    logger.info("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingestión de fichas técnicas a pgvector")
    parser.add_argument("--full", action="store_true", help="Re-ingesta completa (borra todo y recarga)")
    parser.add_argument("--dry-run", action="store_true", help="Solo lista PDFs pendientes sin procesar")
    args = parser.parse_args()
    run_ingestion(full_mode=args.full, dry_run=args.dry_run)
