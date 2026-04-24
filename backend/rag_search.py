"""Capa de Recuperación (RAG) — búsqueda vectorial y armado de contexto técnico.

Extraído de ``backend.main`` durante la Fase C2 (Modularización), Paso 3.

Contiene:
  - Generación de embeddings (Gemini Embedding 2)
  - Inferencia de segmentos de portafolio y pre-filtros de metadata
    (endurecimiento pre-RAG)
  - Consultas pgvector sobre fichas técnicas, guías de solución e índice
    multimodal
  - Empaquetado de chunks en contexto textual para el prompt del agente

Reglas:
  - La matemática vectorial y los thresholds de similitud quedan intactos.
  - ``get_db_engine`` se importa de forma perezosa (lazy) desde ``backend.main``
    para evitar ciclos de import.
  - Las funciones se re-exportan desde ``backend.main`` para preservar la API
    pública (``main.search_technical_chunks(...)`` sigue siendo válido).
"""

from __future__ import annotations

import json
import os
import re
import unicodedata
from typing import Optional

try:
    from gemini_embeddings import generate_query_embedding as generate_gemini_query_embedding
except ImportError:
    from backend.gemini_embeddings import generate_query_embedding as generate_gemini_query_embedding

try:
    from policies import RAG_METADATA_CANONICAL_HINTS, RAG_METADATA_CHEMICAL_HINTS
except ImportError:
    from backend.policies import RAG_METADATA_CANONICAL_HINTS, RAG_METADATA_CHEMICAL_HINTS


# ── Helper local: réplica de normalize_text_value para evitar import desde main ──
def _normalize_text_value(text_value: Optional[str]) -> str:
    if not text_value:
        return ""
    normalized = unicodedata.normalize("NFKD", str(text_value))
    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return normalized.strip().lower()


def _get_db_engine():
    """Lazy import de get_db_engine para romper ciclo con backend.main."""
    try:
        from backend.main import get_db_engine
    except ImportError:
        from main import get_db_engine  # type: ignore
    return get_db_engine()


def _get_problem_class_helpers():
    """Lazy lookup de helpers que pueden no existir aún en main (defensa).

    Devuelve ``(infer_fn, estimate_fn)``; valores None si no existen.
    Preserva el comportamiento original (NameError si el caller los necesita).
    """
    try:
        from backend import main as _main
    except ImportError:
        import main as _main  # type: ignore
    return (
        getattr(_main, "_infer_problem_class_from_rag_query", None),
        getattr(_main, "_estimate_problem_class_confidence", None),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Embeddings
# ─────────────────────────────────────────────────────────────────────────────

def _generate_query_embedding(query_text: str) -> list[float] | None:
    """Generate embedding vector for a search query using Gemini Embedding 2."""
    try:
        return generate_gemini_query_embedding(query_text.strip())
    except Exception:
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Portfolio segment inference
# ─────────────────────────────────────────────────────────────────────────────

PORTFOLIO_SEGMENT_ALIASES = {
    "recubrimientos": "recubrimientos_pinturas",
    "pinturas": "recubrimientos_pinturas",
    "recubrimientos_pinturas": "recubrimientos_pinturas",
    "auxiliares": "auxiliares_aplicacion",
    "auxiliares_aplicacion": "auxiliares_aplicacion",
    "diluyentes": "auxiliares_aplicacion",
    "thinners": "auxiliares_aplicacion",
    "ferreteria": "herrajes_seguridad",
    "herrajes": "herrajes_seguridad",
    "seguridad": "herrajes_seguridad",
    "herrajes_seguridad": "herrajes_seguridad",
    "herramientas": "herramientas_accesorios",
    "accesorios": "herramientas_accesorios",
    "herramientas_accesorios": "herramientas_accesorios",
}
PORTFOLIO_SEGMENT_QUERY_HINTS = {
    "auxiliares_aplicacion": [
        "ajustador", "thinner", "xilol", "varsol", "solvente", "diluyente", "catalizador",
        "endurecedor", "limpieza", "desengrase", "removedor",
    ],
    "herrajes_seguridad": [
        "cerradura", "cerraduras", "candado", "candados", "bisagra", "bisagras", "cerrojo",
        "picaporte", "manija", "pomo", "cierrapuerta", "barra antipanico", "barra antipánico",
        "llave", "cilindro", "yale",
    ],
    "herramientas_accesorios": [
        "brocha", "brochas", "rodillo", "rodillos", "lija", "lijas", "disco flap", "grata",
        "espatula", "espátula", "llana", "pistola", "felpa", "abrasiv",
    ],
    "recubrimientos_pinturas": [
        "pintura", "esmalte", "vinilo", "barniz", "laca", "sellador", "estuco", "impermeabil",
        "anticorros", "epox", "epóx", "poliuret", "corrotec", "aquablock", "koraza", "viniltex",
        "interseal", "intergard", "interthane", "interchar", "interzone", "pintulux", "primer",
        "imprimante", "fondo", "fachada", "humedad", "madera", "piso",
    ],
}


def _normalize_portfolio_segment(value: str | None) -> str | None:
    normalized = _normalize_text_value(value or "")
    if not normalized:
        return None
    return PORTFOLIO_SEGMENT_ALIASES.get(normalized)


def _infer_portfolio_segments_for_query(pregunta: str, producto: str = "", explicit_segment: str | None = None) -> list[str]:
    normalized_explicit = _normalize_portfolio_segment(explicit_segment)
    if normalized_explicit:
        return [normalized_explicit]

    combined = _normalize_text_value(f"{producto} {pregunta}")
    if not combined:
        return []

    detected = []
    for segment, tokens in PORTFOLIO_SEGMENT_QUERY_HINTS.items():
        if any(token in combined for token in tokens):
            detected.append(segment)

    if len(detected) > 1 and "recubrimientos_pinturas" in detected and "auxiliares_aplicacion" in detected and producto:
        product_hint = _normalize_text_value(producto)
        if any(token in product_hint for token in PORTFOLIO_SEGMENT_QUERY_HINTS["auxiliares_aplicacion"]):
            return ["auxiliares_aplicacion"]
        return [segment for segment in detected if segment != "auxiliares_aplicacion"]
    return detected


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values or []:
        normalized = (value or "").strip().lower()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(value)
    return ordered


def _infer_technical_metadata_prefilters(question: str, product: str = "", diagnosis: dict | None = None) -> dict:
    normalized = _normalize_text_value(f"{product} {question}")
    infer_fn, estimate_fn = _get_problem_class_helpers()
    problem_class = (diagnosis or {}).get("problem_class")
    if not problem_class and infer_fn is not None:
        problem_class = infer_fn(question, product)
    confidence = (diagnosis or {}).get("confidence")
    if not confidence and estimate_fn is not None:
        confidence = estimate_fn(problem_class, question, product, 0.0)

    canonical_family_patterns: list[str] = []
    chemical_family_terms: list[str] = []

    explicit_product = _normalize_text_value(product)
    if explicit_product and len(explicit_product) >= 4:
        canonical_family_patterns.append(f"%{explicit_product}%")

    if problem_class and confidence != "baja":
        canonical_family_patterns.extend(RAG_METADATA_CANONICAL_HINTS.get(problem_class, []))
        chemical_family_terms.extend(RAG_METADATA_CHEMICAL_HINTS.get(problem_class, []))

    has_galvanized_signal = any(
        token in normalized
        for token in ["galvanizado", "galvanizada", "lamina zinc", "lámina zinc", "teja zinc", "teja galvanizada", "zinc"]
    )
    has_oxidation_signal = any(token in normalized for token in ["oxido", "óxido", "oxidado", "oxidada", "corrosion", "corrosión"])
    if has_galvanized_signal and not has_oxidation_signal:
        canonical_family_patterns.append("%wash primer%")
        chemical_family_terms.append("wash_primer")
    elif has_galvanized_signal and has_oxidation_signal:
        canonical_family_patterns.extend(["%wash primer%", "%corrotec%", "%pintoxido%"])
        chemical_family_terms.extend(["wash_primer", "anticorrosivo"])

    has_facade_signal = any(token in normalized for token in ["fachada", "muro exterior", "exterior", "intemperie"])
    if has_facade_signal:
        canonical_family_patterns.append("%koraza%")

    return {
        "problem_class": problem_class,
        "confidence": confidence,
        "canonical_family_patterns": _dedupe_preserve_order(canonical_family_patterns),
        "chemical_family_terms": _dedupe_preserve_order(chemical_family_terms),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Búsqueda vectorial pgvector
# ─────────────────────────────────────────────────────────────────────────────

def search_technical_chunks(query: str, top_k: int = 5, marca_filter: str | None = None,
                            segment_filters: list[str] | None = None,
                            metadata_prefilters: dict | None = None) -> list[dict]:
    """Semantic search over vectorized technical sheet chunks using pgvector cosine distance.

    Threshold dinámico (Fase C3 HITO 4):
      Si la variable de entorno ``RAG_PGVECTOR_DISTANCE_THRESHOLD`` está
      definida con un float > 0, se aplica un filtro adicional en SQL
      ``(1 - (embedding <=> :q)) >= threshold`` para descartar chunks
      cuya similitud coseno esté por debajo del umbral.

      Default = 0 = sin filtrado adicional (comportamiento histórico
      preservado). Se recomienda subir gradualmente (ej. 0.30) tras
      tuning empírico contra ``test_global_policy_matrix*.py``.
    """
    embedding = _generate_query_embedding(query)
    if not embedding:
        return []

    embedding_literal = "[" + ",".join(str(v) for v in embedding) + "]"

    where_clauses = [
        "tipo_documento IN ('ficha_tecnica', 'ficha_tecnica_experto')",
        "COALESCE(metadata ->> 'document_scope', 'primary') = 'primary'",
        "COALESCE(metadata ->> 'quality_tier', 'primary') <> 'rejected'",
    ]
    params: list = [embedding_literal]
    if marca_filter:
        where_clauses.append("LOWER(marca) = LOWER(%s)")
        params.append(marca_filter)
    if segment_filters:
        where_clauses.append("COALESCE(metadata ->> 'portfolio_segment', 'portafolio_general') = ANY(%s)")
        params.append(segment_filters)
    canonical_family_patterns = list((metadata_prefilters or {}).get("canonical_family_patterns") or [])
    chemical_family_terms = [term.lower() for term in ((metadata_prefilters or {}).get("chemical_family_terms") or []) if term]
    if canonical_family_patterns and chemical_family_terms:
        where_clauses.append(
            "(LOWER(COALESCE(metadata ->> 'canonical_family', familia_producto)) LIKE ANY(%s) "
            "OR LOWER(COALESCE(metadata ->> 'chemical_family', '')) = ANY(%s))"
        )
        params.append([pattern.lower() for pattern in canonical_family_patterns])
        params.append(chemical_family_terms)
    elif canonical_family_patterns:
        where_clauses.append("LOWER(COALESCE(metadata ->> 'canonical_family', familia_producto)) LIKE ANY(%s)")
        params.append([pattern.lower() for pattern in canonical_family_patterns])
    elif chemical_family_terms:
        where_clauses.append("LOWER(COALESCE(metadata ->> 'chemical_family', '')) = ANY(%s)")
        params.append(chemical_family_terms)

    # Threshold dinámico opt-in vía env var. Default 0.0 = no filtra.
    try:
        distance_threshold = float(os.getenv("RAG_PGVECTOR_DISTANCE_THRESHOLD", "0") or "0")
    except (TypeError, ValueError):
        distance_threshold = 0.0
    if distance_threshold > 0:
        where_clauses.append("(1 - (embedding <=> %s::vector)) >= %s")
        params.append(embedding_literal)
        params.append(distance_threshold)

    params.extend([embedding_literal, top_k])

    try:
        engine = _get_db_engine()
        raw_conn = engine.raw_connection()
        try:
            cur = raw_conn.cursor()
            cur.execute(
                f"""
                  SELECT doc_filename, doc_path_lower, chunk_index, chunk_text,
                      metadata,
                       marca, familia_producto, tipo_documento,
                       1 - (embedding <=> %s::vector) AS similarity
                                FROM public.agent_technical_doc_chunk
                                    WHERE {' AND '.join(where_clauses)}
                ORDER BY embedding <=> %s::vector
                LIMIT %s
                """,
                params,
            )
            columns = [desc[0] for desc in cur.description]
            rows = [dict(zip(columns, row)) for row in cur.fetchall()]
            return rows
        finally:
            raw_conn.close()
    except Exception:
        return []


def search_supporting_technical_guides(query: str, top_k: int = 3, marca_filter: str | None = None,
                                      segment_filters: list[str] | None = None) -> list[dict]:
    embedding = _generate_query_embedding(query)
    if not embedding:
        return []

    embedding_literal = "[" + ",".join(str(v) for v in embedding) + "]"
    where_clauses = [
        "tipo_documento = 'guia_solucion'",
        "COALESCE(metadata ->> 'document_scope', 'guide') = 'guide'",
    ]
    params: list = [embedding_literal]
    if marca_filter:
        where_clauses.append("LOWER(marca) = LOWER(%s)")
        params.append(marca_filter)
    if segment_filters:
        where_clauses.append("COALESCE(metadata ->> 'portfolio_segment', 'portafolio_general') = ANY(%s)")
        params.append(segment_filters)
    params.extend([embedding_literal, top_k])

    try:
        engine = _get_db_engine()
        raw_conn = engine.raw_connection()
        try:
            cur = raw_conn.cursor()
            cur.execute(
                f"""
                  SELECT doc_filename, doc_path_lower, chunk_index, chunk_text,
                      metadata,
                       marca, familia_producto, tipo_documento,
                       1 - (embedding <=> %s::vector) AS similarity
                                FROM public.agent_technical_doc_chunk
                                    WHERE {' AND '.join(where_clauses)}
                ORDER BY embedding <=> %s::vector
                LIMIT %s
                """,
                params,
            )
            columns = [desc[0] for desc in cur.description]
            return [dict(zip(columns, row)) for row in cur.fetchall()]
        finally:
            raw_conn.close()
    except Exception:
        return []


def search_multimodal_product_index(query: str, top_k: int = 3, marca_filter: str | None = None) -> list[dict]:
    embedding = _generate_query_embedding(query)
    if not embedding:
        return []

    embedding_literal = "[" + ",".join(str(v) for v in embedding) + "]"
    params: list = [embedding_literal]
    where_clauses = ["1=1"]
    if marca_filter:
        where_clauses.append("LOWER(marca) = LOWER(%s)")
        params.append(marca_filter)
    params.extend([embedding_literal, top_k])

    try:
        engine = _get_db_engine()
        raw_conn = engine.raw_connection()
        try:
            cur = raw_conn.cursor()
            cur.execute(
                f"""
                    SELECT canonical_family, source_doc_filename, source_doc_path_lower,
                           marca, summary_text, metadata,
                           1 - (embedding <=> %s::vector) AS similarity
                    FROM public.agent_product_multimodal_index
                    WHERE {' AND '.join(where_clauses)}
                    ORDER BY embedding <=> %s::vector
                    LIMIT %s
                """,
                params,
            )
            columns = [desc[0] for desc in cur.description]
            return [dict(zip(columns, row)) for row in cur.fetchall()]
        finally:
            raw_conn.close()
    except Exception:
        return []


def fetch_technical_profiles(canonical_families: list[str], source_files: list[str] | None = None,
                             limit: int = 3, segment_filters: list[str] | None = None) -> list[dict]:
    families = [family for family in canonical_families if family]
    files = [name for name in (source_files or []) if name]
    if not families and not files:
        return []

    try:
        engine = _get_db_engine()
        raw_conn = engine.raw_connection()
        try:
            cur = raw_conn.cursor()
            clauses = []
            params: list = []
            if families:
                clauses.append("canonical_family = ANY(%s)")
                params.append(families)
            if files:
                clauses.append("source_doc_filename = ANY(%s)")
                params.append(files)
            segment_clause = ""
            if segment_filters:
                segment_clause = "AND COALESCE(profile_json -> 'product_identity' ->> 'portfolio_segment', 'portafolio_general') = ANY(%s)"
                params.append(segment_filters)
            cur.execute(
                f"""
                SELECT canonical_family, source_doc_filename, source_doc_path_lower,
                       marca, tipo_documento, completeness_score, extraction_status, profile_json
                FROM public.agent_technical_profile
                WHERE extraction_status = 'ready'
                  AND ({' OR '.join(clauses)})
                  {segment_clause}
                ORDER BY completeness_score DESC, canonical_family
                LIMIT %s
                """,
                [*params, limit],
            )
            columns = [desc[0] for desc in cur.description]
            rows = []
            for row in cur.fetchall():
                item = dict(zip(columns, row))
                profile_json = item.get("profile_json")
                if isinstance(profile_json, str):
                    try:
                        item["profile_json"] = json.loads(profile_json)
                    except Exception:
                        item["profile_json"] = None
                rows.append(item)
            return rows
        finally:
            raw_conn.close()
    except Exception:
        return []


def build_rag_context(chunks: list[dict], max_chunks: int = 4) -> str:
    """Build a textual context from RAG chunks for injection into the agent prompt.

    Skips FDS/HDS (safety data sheet) chunks entirely — they contain chemical
    hazard classifications and transport regulations that add noise and zero
    value for product recommendation.  Only FT (ficha técnica) content is
    useful for advising customers.
    """
    if not chunks:
        return ""
    parts = []
    seen_files = set()
    seen_signatures = set()
    for chunk in chunks[:max_chunks + 4]:  # read more to compensate for FDS skips
        if len(parts) >= max_chunks:
            break
        similarity = chunk.get("similarity", 0)
        if similarity < 0.25:
            continue
        filename = chunk.get("doc_filename", "desconocido")
        # Skip FDS/HDS safety data sheets — no recommendation value
        fn_upper = (filename or "").upper()
        if fn_upper.startswith("FDS") or fn_upper.startswith("HDS"):
            continue
        text_content = (chunk.get("chunk_text") or "").strip()
        if not text_content:
            continue
        metadata = chunk.get("metadata") or {}
        canonical_family = metadata.get("canonical_family") or chunk.get("familia_producto") or filename
        section_match = re.search(r"\[SECCIÓN:\s*([^\]]+)\]", text_content)
        section_name = (section_match.group(1).strip().lower() if section_match else "general")
        signature = f"{canonical_family}|{section_name}"
        if signature in seen_signatures:
            continue
        header = f"[Fuente: {filename}]"
        parts.append(f"{header}\n{text_content}")
        seen_files.add(filename)
        seen_signatures.add(signature)
    if not parts:
        return ""
    return "\n\n---\n\n".join(parts)


__all__ = [
    "PORTFOLIO_SEGMENT_ALIASES",
    "PORTFOLIO_SEGMENT_QUERY_HINTS",
    "_generate_query_embedding",
    "_normalize_portfolio_segment",
    "_infer_portfolio_segments_for_query",
    "_dedupe_preserve_order",
    "_infer_technical_metadata_prefilters",
    "search_technical_chunks",
    "search_supporting_technical_guides",
    "search_multimodal_product_index",
    "fetch_technical_profiles",
    "build_rag_context",
]
