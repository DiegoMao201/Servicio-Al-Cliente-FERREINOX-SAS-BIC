#!/usr/bin/env python3
"""
Ingestión de guías de solución JSON locales → OpenAI Embeddings → PostgreSQL pgvector.

Uso:
    python backend/ingest_solution_guides.py              # Ingesta incremental (solo guías nuevas/modificadas)
    python backend/ingest_solution_guides.py --full        # Re-ingesta completa (borra guías previas y recarga)
    python backend/ingest_solution_guides.py --dry-run     # Solo muestra qué haría sin escribir en BD

Cada guía JSON se serializa a texto rico optimizado para búsqueda semántica,
se embebe con text-embedding-3-small y se inserta en agent_technical_doc_chunk
con tipo_documento='guia_solucion' y document_scope='guide'.
"""

import argparse
import glob
import hashlib
import json
import logging
import os
import sys
import time

# Reutilizar infra del ingestor principal
sys.path.insert(0, os.path.dirname(__file__))
from ingest_technical_sheets import (
    EMBEDDING_DIMENSIONS,
    EMBEDDING_MODEL,
    get_database_url,
    get_openai_api_key,
    insert_chunks,
)

from openai import OpenAI
from sqlalchemy import create_engine, text

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

BATCH_EMBED_SIZE = 50
MAX_EMBED_BATCH_ESTIMATED_TOKENS = 180000
GUIDE_FILES_PATTERN = "guias_solucion_seccion_*.json"
SERIALIZED_STANDARD_KEYS = {
    "id", "titulo", "doc_type", "escenario", "palabras_clave_cliente",
    "diagnostico", "sistema_recomendado", "productos_prohibidos",
    "rendimientos_referencia", "alerta_metraje", "errores_comunes",
    "nota_critica", "nota_importante", "nota_tecnica", "nota_especial",
    "regla_critica", "nota_practica", "nota_calculo", "tabla_referencia",
}


# ---------------------------------------------------------------------------
# Serialización: JSON → texto rico para embedding
# ---------------------------------------------------------------------------

def _serialize_guide_to_text(guide: dict) -> str:
    """Convierte una guía JSON en texto rico optimizado para búsqueda semántica.

    Incluye: título, palabras clave del cliente, diagnóstico completo,
    sistema recomendado paso a paso, productos prohibidos, rendimientos,
    alertas y jerarquía de acabados.
    """
    parts = []

    # Título y escenario
    parts.append(f"GUÍA DE SOLUCIÓN: {guide.get('titulo', '')}")
    parts.append(f"ID: {guide.get('id', '')}")
    parts.append(f"Escenario técnico: {guide.get('escenario', '')}")

    # Palabras clave del cliente (crítico para matching semántico)
    keywords = guide.get("palabras_clave_cliente") or []
    if keywords:
        parts.append(f"Palabras clave del cliente: {', '.join(keywords)}")

    # Diagnóstico
    diag = guide.get("diagnostico") or {}
    if diag.get("tipo_problema"):
        parts.append(f"Tipo de problema: {diag['tipo_problema']}")
    signals = diag.get("señales_confirmatorias") or []
    if signals:
        parts.append("Señales confirmatorias: " + " | ".join(signals))
    questions = diag.get("preguntas_obligatorias") or []
    if questions:
        parts.append("Preguntas obligatorias de diagnóstico:")
        for q in questions:
            parts.append(f"  - {q}")

    # Sistema recomendado
    sys_rec = guide.get("sistema_recomendado") or {}
    if sys_rec.get("resumen"):
        parts.append(f"Sistema recomendado: {sys_rec['resumen']}")
    pasos = sys_rec.get("pasos") or []
    if pasos:
        parts.append("Pasos del sistema:")
        for p in pasos:
            line = f"  Paso {p.get('paso', '?')}: {p.get('accion', '')}"
            if p.get("producto"):
                line += f" — Producto: {p['producto']}"
            if p.get("nota_tecnica"):
                line += f" — {p['nota_tecnica']}"
            if p.get("rendimiento"):
                line += f" — Rendimiento: {p['rendimiento']}"
            parts.append(line)
    if sys_rec.get("orden_critico"):
        parts.append(f"ORDEN CRÍTICO: {sys_rec['orden_critico']}")

    # Jerarquía de acabados
    jerarquia = sys_rec.get("jerarquia_acabados") or []
    if jerarquia:
        parts.append("Jerarquía de acabados:")
        for j in jerarquia:
            parts.append(f"  - {j.get('producto', '?')} ({j.get('nivel', '?')}, precio {j.get('precio_relativo', '?')})")

    # Productos prohibidos
    prohibidos = guide.get("productos_prohibidos") or []
    if prohibidos:
        parts.append("PRODUCTOS PROHIBIDOS para este caso:")
        for p in prohibidos:
            parts.append(f"  ⛔ {p.get('producto', '?')}: {p.get('razon', '')}")

    # Rendimientos
    rend = guide.get("rendimientos_referencia") or {}
    if rend:
        parts.append("Rendimientos de referencia:")
        for prod, val in rend.items():
            parts.append(f"  - {prod}: {val}")

    # Alerta de metraje
    if guide.get("alerta_metraje"):
        parts.append(f"ALERTA DE METRAJE: {guide['alerta_metraje']}")

    # Errores comunes
    errores = guide.get("errores_comunes") or []
    if errores:
        parts.append("Errores comunes:")
        for e in errores:
            parts.append(f"  - {e}")

    # Notas adicionales
    for key in ("nota_critica", "nota_importante", "nota_tecnica", "nota_especial",
                "regla_critica", "nota_practica", "nota_calculo"):
        val = guide.get(key)
        if val:
            parts.append(f"{key.upper().replace('_', ' ')}: {val}")

    # Tabla de referencia (section 6 imprimantes, etc.)
    tabla = guide.get("tabla_referencia") or []
    if tabla:
        parts.append("Tabla de referencia:")
        for row in tabla:
            line_parts = [f"{k}: {v}" for k, v in row.items()]
            parts.append(f"  - {' | '.join(line_parts)}")

    # Campos enriquecidos / futuros: serialización genérica para no perder
    # contexto semántico nuevo agregado a las guías.
    for key in sorted(guide.keys()):
        if key in SERIALIZED_STANDARD_KEYS:
            continue
        value = guide.get(key)
        if value in (None, "", [], {}):
            continue
        title = key.upper().replace("_", " ")
        if isinstance(value, str):
            parts.append(f"{title}: {value}")
        elif isinstance(value, list):
            parts.append(f"{title}:")
            for item in value:
                if isinstance(item, dict):
                    line_parts = [f"{k}: {v}" for k, v in item.items() if v not in (None, "", [], {})]
                    if line_parts:
                        parts.append(f"  - {' | '.join(line_parts)}")
                else:
                    parts.append(f"  - {item}")
        elif isinstance(value, dict):
            parts.append(f"{title}:")
            for sub_key, sub_val in value.items():
                if sub_val in (None, "", [], {}):
                    continue
                if isinstance(sub_val, list):
                    joined = " | ".join(str(item) for item in sub_val)
                    parts.append(f"  - {sub_key}: {joined}")
                else:
                    parts.append(f"  - {sub_key}: {sub_val}")

    return "\n".join(parts)


def _extract_marca(guide: dict) -> str:
    """Extrae la marca principal de los productos del sistema."""
    sys_rec = guide.get("sistema_recomendado") or {}
    pasos = sys_rec.get("pasos") or []
    for p in pasos:
        prod = (p.get("producto") or "").lower()
        if any(m in prod for m in ("pintuco", "viniltex", "koraza", "aquablock", "pintucoat")):
            return "Pintuco"
        if any(m in prod for m in ("international", "interseal", "interthane", "interchar")):
            return "International"
        if any(m in prod for m in ("abracol",)):
            return "Abracol"
    return "Pintuco"


def _extract_familia(guide: dict) -> str:
    """Extrae la familia de producto principal."""
    escenario = (guide.get("escenario") or "").lower()
    if "humedad" in escenario or "capilaridad" in escenario:
        return "impermeabilizantes"
    if "fachada" in escenario or "exterior" in escenario:
        return "exteriores"
    if "metal" in escenario or "anticorrosivo" in escenario:
        return "anticorrosivos"
    if "piso" in escenario:
        return "pisos"
    if "madera" in escenario:
        return "maderas"
    if "drywall" in escenario or "textura" in escenario:
        return "interiores"
    if "industrial" in escenario or "intumesc" in escenario or "temp" in escenario:
        return "industrial"
    if "aerosol" in escenario:
        return "aerosoles"
    if "automotriz" in escenario:
        return "automotriz"
    if "silicona" in escenario or "sellador" in escenario:
        return "selladores"
    return "general"


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Core: load, serialize, embed, insert
# ---------------------------------------------------------------------------

def load_all_guides(workspace_root: str) -> list[dict]:
    """Carga todas las guías de los 9 archivos JSON."""
    pattern = os.path.join(workspace_root, GUIDE_FILES_PATTERN)
    files = sorted(glob.glob(pattern))
    if not files:
        logger.warning(f"No se encontraron archivos con patrón: {pattern}")
        return []

    all_guides = []
    for filepath in files:
        logger.info(f"Cargando: {os.path.basename(filepath)}")
        with open(filepath, "r", encoding="utf-8") as f:
            guides = json.load(f)
        if isinstance(guides, list):
            all_guides.extend(guides)
        else:
            all_guides.append(guides)
        logger.info(f"  → {len(guides) if isinstance(guides, list) else 1} guías")

    logger.info(f"Total guías cargadas: {len(all_guides)}")
    return all_guides


def prepare_chunks(guides: list[dict]) -> list[dict]:
    """Prepara los chunks para inserción en la BD."""
    chunks = []
    for guide in guides:
        guide_id = guide.get("id", "UNKNOWN")
        text = _serialize_guide_to_text(guide)
        doc_filename = f"guia_solucion_{guide_id}.json"
        doc_path = f"local://guias_solucion/{guide_id}"

        chunk = {
            "doc_filename": doc_filename,
            "doc_path_lower": doc_path.lower(),
            "chunk_index": 0,
            "chunk_text": text,
            "marca": _extract_marca(guide),
            "familia_producto": _extract_familia(guide),
            "tipo_documento": "guia_solucion",
            "metadata": {
                "content_hash": _content_hash(text),
                "doc_kind": "guia_solucion",
                "document_scope": "guide",
                "quality_tier": "supporting",
                "guide_id": guide_id,
                "escenario": guide.get("escenario", ""),
                "portfolio_segment": _extract_familia(guide),
                "source_file": "local_json",
                "palabras_clave": guide.get("palabras_clave_cliente", []),
            },
            "token_count": len(text.split()),
            "_text_for_embedding": text,
        }
        chunks.append(chunk)
    return chunks


def generate_embeddings_batch(client: OpenAI, texts: list[str]) -> list[list[float]]:
    """Genera embeddings en lotes."""
    all_embeddings = []
    batches: list[list[str]] = []
    current_batch: list[str] = []
    current_estimated_tokens = 0

    for text_value in texts:
        # Aproximación suficiente para evitar superar 300k tokens/request.
        estimated_tokens = max(1, int(len(text_value.split()) * 1.35))
        if current_batch and (
            len(current_batch) >= BATCH_EMBED_SIZE
            or current_estimated_tokens + estimated_tokens > MAX_EMBED_BATCH_ESTIMATED_TOKENS
        ):
            batches.append(current_batch)
            current_batch = []
            current_estimated_tokens = 0
        current_batch.append(text_value)
        current_estimated_tokens += estimated_tokens
    if current_batch:
        batches.append(current_batch)

    for i, batch in enumerate(batches, start=1):
        logger.info(f"  Embedding batch {i} ({len(batch)} textos)...")
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


def delete_existing_guide_chunks(engine):
    """Elimina todos los chunks de guías locales existentes."""
    with engine.begin() as conn:
        result = conn.execute(text(
            "DELETE FROM public.agent_technical_doc_chunk "
            "WHERE doc_path_lower LIKE 'local://guias_solucion/%'"
        ))
        logger.info(f"Eliminados {result.rowcount} chunks de guías previas")


def get_existing_guide_hashes(engine) -> dict[str, str]:
    """Retorna {doc_path_lower: content_hash} de guías ya ingeridas."""
    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT doc_path_lower, metadata ->> 'content_hash' AS content_hash "
            "FROM public.agent_technical_doc_chunk "
            "WHERE doc_path_lower LIKE 'local://guias_solucion/%'"
        )).fetchall()
    return {row[0]: row[1] for row in rows}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Ingestar guías de solución JSON al RAG")
    parser.add_argument("--full", action="store_true", help="Re-ingesta completa (borra guías previas)")
    parser.add_argument("--dry-run", action="store_true", help="Solo muestra qué haría")
    args = parser.parse_args()

    workspace_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    logger.info(f"Workspace: {workspace_root}")

    # 1. Cargar guías
    guides = load_all_guides(workspace_root)
    if not guides:
        logger.error("No se encontraron guías. Abortando.")
        return

    # 2. Preparar chunks
    chunks = prepare_chunks(guides)
    logger.info(f"Chunks preparados: {len(chunks)}")

    if args.dry_run:
        logger.info("=== DRY RUN — No se escribirá en BD ===")
        for c in chunks:
            logger.info(f"  {c['doc_path_lower']} — {c['token_count']} tokens — {c['familia_producto']}")
        return

    # 3. Conexión a BD
    engine = create_engine(get_database_url())
    logger.info("Conexión a BD establecida")

    # 4. Determinar qué ingestar
    if args.full:
        delete_existing_guide_chunks(engine)
        to_ingest = chunks
    else:
        existing = get_existing_guide_hashes(engine)
        to_ingest = []
        for c in chunks:
            path = c["doc_path_lower"]
            new_hash = c["metadata"]["content_hash"]
            if path not in existing or existing[path] != new_hash:
                to_ingest.append(c)
            else:
                logger.info(f"  Skip (sin cambios): {c['doc_filename']}")
        if not to_ingest:
            logger.info("Todas las guías están actualizadas. Nada que ingestar.")
            return

    logger.info(f"Guías a ingestar: {len(to_ingest)}")

    # 5. Generar embeddings
    api_key = get_openai_api_key()
    client = OpenAI(api_key=api_key)
    texts = [c.pop("_text_for_embedding") for c in to_ingest]
    logger.info("Generando embeddings...")
    embeddings = generate_embeddings_batch(client, texts)
    for chunk, emb in zip(to_ingest, embeddings):
        chunk["embedding"] = emb
    logger.info(f"Embeddings generados: {len(embeddings)}")

    # 6. Insertar en BD
    logger.info("Insertando chunks en BD...")
    insert_chunks(engine, to_ingest)
    logger.info(f"✅ {len(to_ingest)} guías de solución ingeridas exitosamente")

    # 7. Resumen
    with engine.connect() as conn:
        count = conn.execute(text(
            "SELECT COUNT(*) FROM public.agent_technical_doc_chunk "
            "WHERE tipo_documento = 'guia_solucion' AND doc_path_lower LIKE 'local://guias_solucion/%'"
        )).scalar()
    logger.info(f"Total guías de solución en RAG: {count}")


if __name__ == "__main__":
    main()
