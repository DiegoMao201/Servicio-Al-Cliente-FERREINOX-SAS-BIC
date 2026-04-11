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
import hashlib
import io
import json
import logging
import os
import re
import sys
import time
import unicodedata
from collections import defaultdict
from datetime import UTC, datetime
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
PROFILE_EXTRACTION_MODEL = os.getenv("OPENAI_EXTRACTION_MODEL") or os.getenv("OPENAI_MODEL") or "gpt-4o-mini"
DOC_TYPE_SAFETY_TOKENS = ["hoja de seguridad", "hoja seguridad", "fds", "msds", "safety data"]
SECONDARY_DOC_TOKENS = {
    "certificado": ["certificado", "certificacion", "certificación", "certifire", "nsf", "ansi"],
    "catalogo": ["catalogo", "catálogo", "catálogo general"],
    "manual": ["manual", "techdat", "user guide", "handbook"],
    "presentacion": ["presentacion", "presentación", "sales presentation", "webinar", "ppt", "launch"],
    "precio": ["lista de precios", "lista de precio", "price list", "precio"],
}
GUIDE_DOC_TOKENS = [
    "guia", "guía", "preguntas frecuentes", "faq", "soluciones", "sistemas",
    "mantenimiento industria", "maintenance guide", "brochure", "line card",
]
STRONG_GUIDE_DOC_TOKENS = [
    "guia-sistemas", "guia sistemas", "sistemas mantenimiento industria",
    "preguntas frecuentes", "faq", "soluciones de", "brochure koraza",
    "brochure pintura impermeabilizante",
]
PRIMARY_DOC_HINTS = ["ficha tecnica", "ficha técnica", "ficha tecn", "technical data", "tech data", "ft-"]
GENERIC_PRIMARY_BLOCKLIST = [
    "doors and frame",
    "door and frame",
    "l-series",
    "sales presentation",
    "presentation",
    "catalogo general",
    "catalogo",
]
MAX_PRIMARY_CHUNKS = 400
NOISE_NAME_PATTERNS = [
    r"\s*\(\d+\)\s*",
    r"\s*\(copia.*?\)\s*",
    r"\s*-\s*copia\s*",
    r"\s+copy\s*",
    r"\s+actualizada\s*",
    r"\s+final\s*",
    r"\s+version\s*\d+\s*",
    r"\s+versión\s*\d+\s*",
    r"\s+rev\.?\s*\d+\s*",
]
BRAND_PATTERNS = [
    "pintuco", "viniltex", "koraza", "pintulux", "domestico", "doméstico",
    "aerocolor", "abracol", "yale", "goya", "mega", "international",
    "interseal", "intergard", "interchar", "interzone", "interthane",
]
SEGMENT_BRAND_HINTS = {
    "pintuco": "recubrimientos_pinturas",
    "viniltex": "recubrimientos_pinturas",
    "koraza": "recubrimientos_pinturas",
    "pintulux": "recubrimientos_pinturas",
    "aerocolor": "recubrimientos_pinturas",
    "international": "recubrimientos_pinturas",
    "interseal": "recubrimientos_pinturas",
    "intergard": "recubrimientos_pinturas",
    "interchar": "recubrimientos_pinturas",
    "interzone": "recubrimientos_pinturas",
    "interthane": "recubrimientos_pinturas",
    "yale": "herrajes_seguridad",
    "abracol": "herramientas_accesorios",
    "goya": "herramientas_accesorios",
}
PORTFOLIO_SEGMENT_KEYWORDS = {
    "auxiliares_aplicacion": [
        "ajustador", "thinner", "xilol", "varsol", "diluyente", "dilucion", "dilución",
        "solvente", "desengrase", "desengras", "limpieza de superficies", "removedor",
        "catalizador", "endurecedor", "hardener", "activador",
    ],
    "herrajes_seguridad": [
        "cerradura", "cerraduras", "candado", "candados", "bisagra", "bisagras",
        "cerrojo", "picaporte", "manija", "pomo", "cierrapuerta", "cierrapuertas",
        "barra antipánico", "barra antipanico", "cerradero", "falleba", "mirilla",
        "seguridad", "llave", "cilindro", "escuadra yale", "mortise", "deadbolt",
    ],
    "herramientas_accesorios": [
        "brocha", "brochas", "rodillo", "rodillos", "lija", "lijas", "disco flap",
        "disco", "grata", "espatula", "espátula", "llana", "cinta", "pistola",
        "felpa", "abrasiv", "esponja abrasiva", "pulidor", "pulidora",
    ],
    "recubrimientos_pinturas": [
        "pintura", "esmalte", "vinilo", "barniz", "laca", "sellador", "estuco",
        "impermeabil", "recubrimiento", "anticorros", "epox", "epóx", "poliuret",
        "acril", "alquid", "corrotec", "aquablock", "koraza", "viniltex", "interseal",
        "intergard", "interthane", "interchar", "interzone", "pintulux", "primer",
        "imprimante", "fondo", "tráfico", "trafico", "canchas", "madera", "fachada",
    ],
}
STRONG_COATINGS_FILENAME_TOKENS = [
    "altas temperaturas", "arena quarzo", "quarzo", "protective coatings",
    "resina alquid", "resina alquíd", "epox", "epóx", "poliuret", "anticorros",
    "impermeabil", "vinilo", "esmalte", "barniz", "laca", "sellador", "estuco",
]
STRONG_COATINGS_TEXT_TOKENS = [
    "protective coatings", "pintura a base de", "pigmentos especiales", "rendimiento teorico",
    "rendimiento teórico", "espesor recomendado", "solidos en volumen", "sólidos en volumen",
    "tiempo de secado", "metodo de aplicacion", "método de aplicación", "superficies metalicas",
    "superficies metálicas", "pavimentos", "antidesliz", "antiderrap", "recubrimientos de alto espesor",
]
PORTFOLIO_SUBSEGMENT_KEYWORDS = {
    "auxiliares_aplicacion": {
        "diluyentes_y_ajustadores": ["ajustador", "thinner", "xilol", "varsol", "diluyente", "solvente"],
        "limpieza_y_desengrase": ["limpieza de superficies", "desengrase", "removedor", "remover grasa", "remover aceite"],
        "catalizadores_y_endurecedores": ["catalizador", "endurecedor", "hardener", "activador"],
    },
    "herrajes_seguridad": {
        "cerraduras_y_candados": ["cerradura", "candado", "cilindro", "deadbolt", "mortise"],
        "bisagras_y_cierrapuertas": ["bisagra", "cierrapuerta", "cierrapuertas", "pivot", "pivote"],
        "accesorios_seguridad": ["manija", "pomo", "barra antipánico", "barra antipanico", "mirilla", "picaporte"],
    },
    "herramientas_accesorios": {
        "brochas_y_rodillos": ["brocha", "rodillo", "felpa"],
        "abrasivos_y_preparacion": ["lija", "lijas", "abrasiv", "disco flap", "grata", "pulidor"],
        "accesorios_aplicacion": ["espatula", "espátula", "llana", "cinta", "pistola"],
    },
    "recubrimientos_pinturas": {
        "industrial_proteccion": ["interseal", "intergard", "interthane", "interchar", "interzone", "anticorros", "industrial", "epox", "poliuret"],
        "arquitectonico_decorativo": ["viniltex", "koraza", "pintulux", "vinilo", "esmalte", "fachada", "interior", "exterior"],
        "impermeabilizacion_humedad": ["impermeabil", "aquablock", "siliconite", "sellamur", "humedad", "goter", "filtracion", "filtración"],
        "madera_y_barnices": ["barniz", "laca", "madera", "wood stain", "sellador madera"],
        "pisos_y_trafico": ["piso", "trafico", "tráfico", "cancha", "demarcacion", "demarcación"],
        "guias_y_sistemas": ["guia", "guía", "sistema", "soluciones", "faq", "preguntas frecuentes", "brochure"],
    },
}
PORTFOLIO_SEGMENT_PRIORITY = [
    "auxiliares_aplicacion",
    "herrajes_seguridad",
    "herramientas_accesorios",
    "recubrimientos_pinturas",
]
UTILITY_DOC_TOKENS = [
    "ajustador", "thinner", "xilol", "varsol", "limpieza de superficies", "desengrase",
    "solvente", "diluyente", "dilucion", "dilución",
]
GENERIC_LOW_SIGNAL_PATTERNS = [
    "para mas informacion",
    "para más información",
    "consulte la hoja tecnica",
    "consulte la hoja técnica",
    "preparacion de la superficie",
    "preparación de la superficie",
    "preparacion de la",
    "preparación de la",
    "generalidades",
    "condiciones de uso",
    "fuera de nuestro control",
    "compania global de pinturas",
    "compañia global de pinturas",
    "compan~ia global de pinturas",
    "producto fabricado totalmente en colombia",
]
# Paths/filenames to SKIP (not technical sheets)
SKIP_PATH_TOKENS = [
    "socios", "/rut ", "/rut_", "rut ", "cedula", "cédula", "camara de comercio",
    "cámara de comercio", "redam", "certificado bancario", "carta",
    "nit ", "factura", "cotizacion", "cotización", "remision", "remisión",
    "orden de compra", "recibo", "comprobante", "extracto",
    "contrato", "acta", "poder", "autorizacion", "autorización",
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
            tomllib = __import__("tomli")
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


def ensure_profile_table(engine):
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS public.agent_technical_profile (
                id bigserial PRIMARY KEY,
                canonical_family text NOT NULL,
                source_doc_filename text NOT NULL,
                source_doc_path_lower text NOT NULL,
                marca text,
                tipo_documento varchar(30) NOT NULL DEFAULT 'ficha_tecnica',
                profile_json jsonb NOT NULL DEFAULT '{}'::jsonb,
                completeness_score numeric(6,4) NOT NULL DEFAULT 0,
                extraction_method varchar(30) NOT NULL DEFAULT 'hybrid',
                extraction_status varchar(30) NOT NULL DEFAULT 'ready',
                content_hash text,
                text_fingerprint text,
                generated_at timestamptz NOT NULL DEFAULT now(),
                updated_at timestamptz NOT NULL DEFAULT now(),
                CONSTRAINT uq_agent_technical_profile_family UNIQUE (canonical_family)
            )
        """))
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_agent_technical_profile_path
                ON public.agent_technical_profile(source_doc_path_lower)
        """))
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_agent_technical_profile_marca
                ON public.agent_technical_profile(marca)
        """))
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_agent_technical_profile_status
                ON public.agent_technical_profile(extraction_status)
        """))
    logger.info("Tabla agent_technical_profile verificada/creada.")


def normalize_text(value: str) -> str:
    text = unicodedata.normalize("NFKD", value or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s\-_/\.]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def normalize_document_name(filename: str) -> str:
    name = re.sub(r"\.pdf$", "", filename or "", flags=re.IGNORECASE).strip()
    for pattern in NOISE_NAME_PATTERNS:
        name = re.sub(pattern, " ", name, flags=re.IGNORECASE)
    name = re.sub(r"[_-]+", " ", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name


def classify_document_kind(filename: str, path_lower: str) -> str:
    combined = normalize_text(f"{filename} {path_lower}")
    if any(tok in combined for tok in DOC_TYPE_SAFETY_TOKENS):
        return "hoja_seguridad"
    if any(tok in combined for tok in STRONG_GUIDE_DOC_TOKENS):
        return "guia_solucion"
    if any(tok in combined for tok in GENERIC_PRIMARY_BLOCKLIST):
        return "manual"
    for kind, tokens in SECONDARY_DOC_TOKENS.items():
        if any(tok in combined for tok in tokens):
            return kind
    if any(tok in combined for tok in GUIDE_DOC_TOKENS):
        return "guia_solucion"
    if any(tok in combined for tok in PRIMARY_DOC_HINTS):
        return "ficha_tecnica"
    return "ficha_tecnica"


def extract_document_year(value: str) -> int:
    matches = re.findall(r"(20\d{2})", value or "")
    if not matches:
        return 0
    return max(int(year) for year in matches)


def build_canonical_family(filename: str, inferred_brand: str | None = None, doc_kind: str | None = None) -> str:
    name = normalize_document_name(filename)
    lowered = normalize_text(name)
    for token in [*DOC_TYPE_SAFETY_TOKENS, *PRIMARY_DOC_HINTS, "hoja seguridad", "ficha tecnica", "ficha técnica"]:
        lowered = lowered.replace(token, " ")
    for tokens in SECONDARY_DOC_TOKENS.values():
        for token in tokens:
            lowered = lowered.replace(token, " ")
    if doc_kind != "guia_solucion":
        for token in GUIDE_DOC_TOKENS:
            lowered = lowered.replace(token, " ")
    lowered = re.sub(r"\bpdf\b", " ", lowered)
    lowered = re.sub(r"\bcol\b", " ", lowered)
    lowered = re.sub(r"\bversion\b", " ", lowered)
    lowered = re.sub(r"\bactualizada\b", " ", lowered)
    lowered = re.sub(r"\s+", " ", lowered).strip(" -_")
    if inferred_brand and inferred_brand.lower() not in lowered:
        lowered = f"{inferred_brand.lower()} {lowered}".strip()
    return lowered.upper() if lowered else normalize_document_name(filename).upper()


def infer_portfolio_segment(filename: str, path_lower: str, clean_text: str = "",
                            doc_kind: str | None = None, inferred_brand: str | None = None) -> tuple[str, str | None]:
    sanitized_path = normalize_text(path_lower or "")
    sanitized_path = sanitized_path.replace("data fichas tecnicas y hojas de seguridad", " ")
    sanitized_path = sanitized_path.replace("fichas tecnicas y hojas de seguridad", " ")
    filename_text = normalize_text(filename or "")
    clean_text_normalized = normalize_text(clean_text[:6000] if clean_text else "")
    combined = normalize_text(" ".join(part for part in [filename, sanitized_path, clean_text[:6000]] if part))

    def _find_subsegment(segment: str) -> str | None:
        for subsegment, tokens in (PORTFOLIO_SUBSEGMENT_KEYWORDS.get(segment) or {}).items():
            if any(token in combined for token in tokens):
                return subsegment
        return None

    if inferred_brand:
        hinted = SEGMENT_BRAND_HINTS.get(normalize_text(inferred_brand))
        if hinted:
            segment = hinted
            subsegment = _find_subsegment(segment)
            if subsegment:
                return segment, subsegment
            if doc_kind == "guia_solucion" and segment == "recubrimientos_pinturas":
                return segment, "guias_y_sistemas"
            return segment, None

    if any(token in filename_text for token in UTILITY_DOC_TOKENS):
        return "auxiliares_aplicacion", _find_subsegment("auxiliares_aplicacion")

    strong_coatings_in_filename = any(token in filename_text for token in STRONG_COATINGS_FILENAME_TOKENS)
    strong_coatings_in_text = sum(1 for token in STRONG_COATINGS_TEXT_TOKENS if token in clean_text_normalized)
    utility_hits_in_text = sum(1 for token in (PORTFOLIO_SEGMENT_KEYWORDS.get("auxiliares_aplicacion") or []) if token in clean_text_normalized)
    if strong_coatings_in_filename or (strong_coatings_in_text >= 2 and utility_hits_in_text < 3):
        subsegment = _find_subsegment("recubrimientos_pinturas")
        return "recubrimientos_pinturas", subsegment

    for segment in PORTFOLIO_SEGMENT_PRIORITY:
        tokens = PORTFOLIO_SEGMENT_KEYWORDS.get(segment) or []
        hay_match = False
        if segment == "auxiliares_aplicacion":
            hay_match = any(token in filename_text or token in sanitized_path for token in tokens)
            if not hay_match:
                utility_hits = sum(1 for token in tokens if token in clean_text_normalized)
                hay_match = utility_hits >= 3 and strong_coatings_in_text == 0
        else:
            hay_match = any(token in combined for token in tokens)
        if hay_match:
            subsegment = _find_subsegment(segment)
            if subsegment:
                return segment, subsegment
            if doc_kind == "guia_solucion" and segment == "recubrimientos_pinturas":
                return segment, "guias_y_sistemas"
            return segment, None
    if doc_kind == "guia_solucion":
        return "recubrimientos_pinturas", "guias_y_sistemas"
    return "portafolio_general", None


def compute_text_fingerprint(text: str) -> str:
    compact = normalize_text(text)
    if len(compact) > 12000:
        compact = compact[:12000]
    return hashlib.sha1(compact.encode("utf-8", errors="ignore")).hexdigest()


def build_family_anchor(canonical_family: str) -> str:
    normalized = normalize_text(canonical_family)
    stopwords = {
        "pintuco", "international", "intergard", "interseal", "interthane",
        "ficha", "tecnica", "ft", "es", "pdf", "base", "agua", "para",
        "the", "and", "de", "del", "la", "el",
    }
    tokens = [token for token in normalized.split() if token and token not in stopwords]
    if not tokens:
        return normalized
    return " ".join(tokens[:4])


def score_document_entry(entry: dict) -> tuple:
    filename = entry["name"]
    normalized_name = normalize_text(filename)
    path_lower = entry["path_lower"]
    year = extract_document_year(filename)
    is_primary = 1 if entry.get("doc_kind") == "ficha_tecnica" else 0
    is_guide = 1 if entry.get("doc_kind") == "guia_solucion" else 0
    has_brand = 1 if entry.get("marca") else 0
    copy_penalty = 0 if any(tok in normalized_name for tok in ["copia", "conflicto", "copy", "conflict"]) else 1
    explicit_sheet_bonus = 1 if any(tok in normalized_name for tok in ["ficha tecnica", "technical data", "ft-"]) else 0
    clean_name_bonus = 1 if normalize_document_name(filename).lower() == re.sub(r"\.pdf$", "", filename, flags=re.IGNORECASE).strip().lower() else 0
    concise_name_bonus = -len(normalize_document_name(filename))
    return (is_primary, is_guide, copy_penalty, clean_name_bonus, explicit_sheet_bonus, has_brand, year, concise_name_bonus, -(entry.get("size") or 0), path_lower)


def build_corpus_report(curated_entries: list[dict], duplicate_groups: list[dict], skipped_entries: list[dict]) -> dict:
    by_kind = defaultdict(int)
    by_brand = defaultdict(int)
    by_segment = defaultdict(int)
    for entry in curated_entries:
        by_kind[entry.get("doc_kind") or "desconocido"] += 1
        by_brand[(entry.get("marca") or "sin_marca").lower()] += 1
        by_segment[entry.get("portfolio_segment") or "portafolio_general"] += 1
    return {
        "curated_documents": len(curated_entries),
        "duplicate_groups": len(duplicate_groups),
        "duplicates_removed": sum(len(group.get("duplicates") or []) for group in duplicate_groups),
        "skipped_documents": len(skipped_entries),
        "documents_by_kind": dict(sorted(by_kind.items())),
        "documents_by_brand": dict(sorted(by_brand.items())),
        "documents_by_segment": dict(sorted(by_segment.items())),
        "curated_documents_detail": [
            {
                "name": entry.get("name"),
                "canonical_family": entry.get("canonical_family"),
                "doc_kind": entry.get("doc_kind"),
                "marca": entry.get("marca"),
                "portfolio_segment": entry.get("portfolio_segment"),
                "portfolio_subsegment": entry.get("portfolio_subsegment"),
            }
            for entry in curated_entries[:250]
        ],
        "duplicate_groups_detail": duplicate_groups[:200],
        "skipped_documents_detail": skipped_entries[:200],
    }


def write_corpus_report(report: dict):
    report_dir = Path(__file__).resolve().parent.parent / "artifacts" / "rag"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / "rag_corpus_rebuild_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Reporte de corpus escrito en: %s", report_path)


def curate_pdf_entries(pdf_entries: list[dict]) -> tuple[list[dict], list[dict], list[dict]]:
    staged_entries = []
    skipped_entries = []
    for raw in pdf_entries:
        combined = normalize_text(f"{raw['name']} {raw['path_lower']}")
        if any(token in combined for token in SKIP_PATH_TOKENS):
            skipped_entries.append({"path_lower": raw["path_lower"], "name": raw["name"], "reason": "skip_path_token"})
            continue

        doc_kind = classify_document_kind(raw["name"], raw["path_lower"])
        marca = infer_brand(raw["name"], raw["path_lower"])
        canonical_family = build_canonical_family(raw["name"], marca, doc_kind)
        portfolio_segment, portfolio_subsegment = infer_portfolio_segment(
            raw["name"],
            raw["path_lower"],
            doc_kind=doc_kind,
            inferred_brand=marca,
        )
        entry = {
            **raw,
            "doc_kind": doc_kind,
            "marca": marca,
            "canonical_family": canonical_family,
            "normalized_name": normalize_document_name(raw["name"]),
            "portfolio_segment": portfolio_segment,
            "portfolio_subsegment": portfolio_subsegment,
        }

        if doc_kind not in {"ficha_tecnica", "guia_solucion"}:
            skipped_entries.append({"path_lower": raw["path_lower"], "name": raw["name"], "reason": f"secondary:{doc_kind}"})
            continue

        staged_entries.append(entry)

    grouped = defaultdict(list)
    for entry in staged_entries:
        family_anchor = build_family_anchor(entry["canonical_family"])
        content_hash = entry.get("content_hash")
        dedup_key = f"hash::{content_hash}::{family_anchor}" if content_hash else f"family::{entry['canonical_family']}"
        grouped[dedup_key].append(entry)

    curated_entries = []
    duplicate_groups = []
    for dedup_key, entries in grouped.items():
        ordered = sorted(entries, key=score_document_entry, reverse=True)
        survivor = ordered[0]
        survivor["duplicate_members"] = [e["name"] for e in ordered]
        survivor["duplicate_count"] = len(ordered) - 1
        curated_entries.append(survivor)
        if len(ordered) > 1:
            duplicate_groups.append({
                "dedup_key": dedup_key,
                "survivor": survivor["name"],
                "canonical_family": survivor["canonical_family"],
                "duplicates": [e["name"] for e in ordered[1:]],
            })

    curated_entries.sort(key=lambda item: item["canonical_family"])
    return curated_entries, duplicate_groups, skipped_entries


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
# PDF → texto (extracción mejorada con soporte para tablas)
# ---------------------------------------------------------------------------
def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """Extract text from PDF preserving table structures using PyMuPDF blocks."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pages = []
    for page in doc:
        # Try table extraction first (PyMuPDF 1.23+)
        page_parts = []
        try:
            tables = page.find_tables()
            if tables and tables.tables:
                # Extract tables as formatted text
                for table in tables:
                    table_data = table.extract()
                    if table_data:
                        formatted_rows = []
                        for row in table_data:
                            clean_cells = [str(cell).strip() if cell else "" for cell in row]
                            # Format as "key: value" for 2-column tables (common in tech sheets)
                            if len(clean_cells) == 2 and clean_cells[0] and clean_cells[1]:
                                formatted_rows.append(f"{clean_cells[0]}: {clean_cells[1]}")
                            elif any(c for c in clean_cells):
                                formatted_rows.append(" | ".join(c for c in clean_cells if c))
                        if formatted_rows:
                            page_parts.append("\n".join(formatted_rows))
        except Exception:
            pass  # find_tables not available or failed, fall back to text

        # Get regular text (non-table content)
        text_content = page.get_text("text")
        if text_content and text_content.strip():
            # If we got tables, merge them with text, avoiding duplication
            if page_parts:
                # Use blocks to get text with position info
                blocks = page.get_text("blocks")
                non_table_text = []
                for block in blocks:
                    if block[6] == 0:  # text block (not image)
                        block_text = block[4].strip()
                        if block_text:
                            non_table_text.append(block_text)
                if non_table_text:
                    page_parts.insert(0, "\n".join(non_table_text))
                pages.append("\n\n".join(page_parts))
            else:
                pages.append(text_content.strip())
    doc.close()
    return "\n\n".join(pages)


def clean_extracted_text(raw_text: str) -> str:
    text = re.sub(r"\n{3,}", "\n\n", raw_text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" \n", "\n", text)
    return text.strip()


def dedupe_list(values: list, max_items: int | None = None) -> list:
    result = []
    seen = set()
    for value in values or []:
        if isinstance(value, dict):
            marker = json.dumps(value, ensure_ascii=False, sort_keys=True)
        else:
            marker = str(value).strip()
        if not marker:
            continue
        if marker in seen:
            continue
        seen.add(marker)
        result.append(value)
        if max_items and len(result) >= max_items:
            break
    return result


def parse_decimal(value: str | None) -> float | None:
    if value is None:
        return None
    cleaned = str(value).strip().replace(" ", "")
    if not cleaned:
        return None
    if "," in cleaned and "." in cleaned:
        if cleaned.rfind(",") > cleaned.rfind("."):
            cleaned = cleaned.replace(".", "").replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")
    else:
        cleaned = cleaned.replace(",", ".")
    cleaned = re.sub(r"[^0-9.\-]", "", cleaned)
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def infer_product_display_name(filename: str, canonical_family: str) -> str:
    cleaned = normalize_document_name(filename)
    if cleaned:
        return cleaned
    return canonical_family.title()


def infer_aliases(display_name: str, canonical_family: str, marca: str | None) -> list[str]:
    aliases = [display_name, canonical_family.title()]
    if marca and display_name.lower().startswith(marca.lower() + " "):
        aliases.append(display_name[len(marca):].strip())
    return dedupe_list([alias for alias in aliases if alias], max_items=6)


def extract_lines_matching(text: str, keywords: list[str], max_lines: int = 8) -> list[str]:
    results = []
    for raw_line in text.splitlines():
        line = raw_line.strip(" -\t")
        if len(line) < 5:
            continue
        normalized_line = normalize_text(line)
        if any(keyword in normalized_line for keyword in keywords):
            results.append(line)
    return dedupe_list(results, max_items=max_lines)


def filter_low_signal_lines(lines: list[str], max_items: int | None = None) -> list[str]:
    cleaned = []
    for line in lines or []:
        normalized_line = normalize_text(line)
        if any(pattern in normalized_line for pattern in GENERIC_LOW_SIGNAL_PATTERNS):
            continue
        if len(normalized_line) < 8:
            continue
        cleaned.append(line)
    return dedupe_list(cleaned, max_items=max_items)


def choose_best_summary(summary_candidates: list[str], display_name: str, utility_document: bool) -> str:
    candidates = filter_low_signal_lines(summary_candidates, max_items=6)
    scored: list[tuple[int, str]] = []
    for line in candidates:
        normalized_line = normalize_text(line)
        score = 0
        if display_name and normalize_text(display_name).split()[0] in normalized_line:
            score += 3
        if any(token in normalized_line for token in ["ideal", "recomend", "protege", "decora", "recubr", "esmalte", "acabado", "diluci", "limpieza", "desengrase"]):
            score += 2
        if len(normalized_line) >= 40:
            score += 1
        scored.append((score, line))
    scored.sort(key=lambda item: (-item[0], len(item[1])))
    if scored and scored[0][0] > 0:
        return scored[0][1][:500].strip()
    if utility_document:
        return f"Producto auxiliar para dilución, ajuste o limpieza del sistema {display_name}."
    return ""


def is_utility_document(filename: str, canonical_family: str) -> bool:
    combined = normalize_text(f"{filename} {canonical_family}")
    return any(token in combined for token in UTILITY_DOC_TOKENS)


def extract_key_value_specs(text: str, max_items: int = 25) -> list[dict]:
    specs = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if len(line) < 4:
            continue
        if ":" in line:
            left, right = line.split(":", 1)
        elif "|" in line:
            parts = [part.strip() for part in line.split("|") if part.strip()]
            if len(parts) != 2:
                continue
            left, right = parts
        else:
            continue
        key = left.strip()
        value = right.strip()
        if len(key) > 80 or len(value) > 220 or not key or not value:
            continue
        if len(key.split()) > 10:
            continue
        specs.append({"key": key, "value": value, "raw": line})
    return dedupe_list(specs, max_items=max_items)


def detect_application_methods(text: str) -> list[str]:
    normalized = normalize_text(text)
    methods = []
    mapping = {
        "brocha": ["brocha"],
        "rodillo": ["rodillo"],
        "pistola convencional": ["pistola convencional"],
        "airless": ["airless"],
        "spray": ["spray", "aspers"],
        "llana": ["llana"],
        "inmersion": ["inmersion", "immers"],
    }
    for label, tokens in mapping.items():
        if any(token in normalized for token in tokens):
            methods.append(label)
    return methods


def detect_surface_tags(text: str) -> list[str]:
    normalized = normalize_text(text)
    tags = []
    mapping = {
        "concreto": ["concreto", "cemento", "mortero"],
        "mamposteria": ["mamposteria", "muro", "pared", "estuco"],
        "metal": ["metal", "acero", "ferroso", "galvanizado", "lamina"],
        "madera": ["madera"],
        "piso": ["piso"],
        "interior": ["interior"],
        "exterior": ["exterior", "intemperie", "uv"],
        "fachada": ["fachada"],
    }
    for label, tokens in mapping.items():
        if any(token in normalized for token in tokens):
            tags.append(label)
    return tags


def extract_numeric_range(text: str, labels: list[str], units_pattern: str) -> tuple[float | None, float | None, str | None]:
    flags = re.IGNORECASE
    label_pattern = "(?:" + "|".join(re.escape(label) for label in labels) + ")"
    patterns = [
        rf"{label_pattern}[^\n]{{0,90}}?(\d+[\.,]?\d*)\s*(?:a|hasta|-)\s*(\d+[\.,]?\d*)\s*{units_pattern}",
        rf"(\d+[\.,]?\d*)\s*(?:a|hasta|-)\s*(\d+[\.,]?\d*)\s*{units_pattern}[^\n]{{0,60}}?{label_pattern}",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags)
        if match:
            return parse_decimal(match.group(1)), parse_decimal(match.group(2)), match.group(0).strip()
    return None, None, None


def extract_numeric_value(text: str, labels: list[str], units_pattern: str) -> tuple[float | None, str | None]:
    flags = re.IGNORECASE
    label_pattern = "(?:" + "|".join(re.escape(label) for label in labels) + ")"
    patterns = [
        rf"{label_pattern}[^\n]{{0,90}}?(\d+[\.,]?\d*)\s*{units_pattern}",
        rf"(\d+[\.,]?\d*)\s*{units_pattern}[^\n]{{0,60}}?{label_pattern}",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags)
        if match:
            return parse_decimal(match.group(1)), match.group(0).strip()
    return None, None


def build_section_map(text: str) -> dict[str, str]:
    section_map = {}
    for header, body in _split_into_sections(text):
        section_map[header] = body
    return section_map


def collect_section_text(section_map: dict[str, str], header_keywords: list[str]) -> str:
    collected = []
    for header, body in section_map.items():
        normalized_header = normalize_text(header)
        if any(keyword in normalized_header for keyword in header_keywords):
            collected.append(body)
    return "\n\n".join(collected)


def limit_text(value: str, max_chars: int = 18000) -> str:
    value = value.strip()
    if len(value) <= max_chars:
        return value
    return value[:max_chars]


def extract_json_object_from_text(value: str) -> dict | None:
    text_value = (value or "").strip()
    if not text_value:
        return None
    try:
        return json.loads(text_value)
    except Exception:
        pass

    start = text_value.find("{")
    end = text_value.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    candidate = text_value[start:end + 1]
    candidate = candidate.replace("\u0000", " ")
    candidate = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", " ", candidate)
    try:
        return json.loads(candidate)
    except Exception:
        return None


def repair_llm_json(openai_client: OpenAI, raw_content: str) -> dict | None:
    try:
        response = openai_client.chat.completions.create(
            model=PROFILE_EXTRACTION_MODEL,
            response_format={"type": "json_object"},
            temperature=0,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Recibes un intento de JSON malformado. Regrésalo como JSON válido, sin inventar campos nuevos. "
                        "Si algo está roto, conserva solo lo recuperable. Devuelve únicamente JSON."
                    ),
                },
                {"role": "user", "content": raw_content[:12000]},
            ],
            max_tokens=1800,
        )
        return extract_json_object_from_text(response.choices[0].message.content or "")
    except Exception:
        return None


def extract_solution_guidance(text: str, section_map: dict[str, str], doc_kind: str) -> dict:
    if doc_kind != "guia_solucion":
        return {
            "diagnostic_questions": [],
            "system_recommendations": [],
            "decision_clues": [],
            "common_failures": [],
        }

    diagnostic_text = collect_section_text(section_map, ["pregunt", "diagnost", "evalu", "inspec", "verific"])
    systems_text = collect_section_text(section_map, ["sistema", "solucion", "solución", "recomend", "aplic"])
    failures_text = collect_section_text(section_map, ["falla", "problema", "error", "patologia", "patología", "restric"])
    base_text = "\n\n".join([diagnostic_text, systems_text, failures_text, text])

    return {
        "diagnostic_questions": extract_lines_matching(base_text, ["pregunt", "verifique", "revise", "determine", "diagnost"], max_lines=12),
        "system_recommendations": extract_lines_matching(base_text, ["sistema", "solucion", "solución", "recomend", "aplique", "paso"], max_lines=16),
        "decision_clues": extract_lines_matching(base_text, ["si ", "cuando", "en caso", "para ", "antes de"], max_lines=14),
        "common_failures": extract_lines_matching(base_text, ["falla", "error", "no aplicar", "evite", "problema"], max_lines=10),
    }


def merge_profile_values(base, extra):
    if extra is None:
        return base
    if isinstance(base, dict) and isinstance(extra, dict):
        merged = dict(base)
        for key, value in extra.items():
            merged[key] = merge_profile_values(merged.get(key), value)
        return merged
    if isinstance(base, list) and isinstance(extra, list):
        return dedupe_list(base + extra)
    if extra in ("", [], {}, None):
        return base
    return extra


def compute_profile_completeness(profile: dict) -> float:
    checks = []
    application = profile.get("application") or {}
    performance = profile.get("performance") or {}
    commercial = profile.get("commercial_context") or {}
    checks.append(bool((commercial.get("summary") or "").strip()))
    checks.append(bool(commercial.get("recommended_uses")))
    checks.append(bool(application.get("surface_preparation")))
    checks.append(bool(application.get("application_methods")))
    checks.append(bool((application.get("dilution") or {}).get("ratio_texts")))
    checks.append(bool((performance.get("coverage") or {}).get("notes") or (performance.get("coverage") or {}).get("min_m2_per_gal")))
    checks.append(bool((application.get("drying") or {}).get("notes")))
    checks.append(bool(profile.get("technical_specs")))
    checks.append(bool((profile.get("alerts") or {}).get("critical")))
    return round(sum(1 for check in checks if check) / max(len(checks), 1), 4)


def build_heuristic_technical_profile(filename: str, path_lower: str, marca: str | None,
                                      canonical_family: str, clean_text: str, pdf_entry: dict,
                                      doc_kind: str = "ficha_tecnica",
                                      portfolio_segment: str | None = None,
                                      portfolio_subsegment: str | None = None) -> tuple[dict, dict[str, str]]:
    display_name = infer_product_display_name(filename, canonical_family)
    aliases = infer_aliases(display_name, canonical_family, marca)
    section_map = build_section_map(clean_text)
    portfolio_segment = portfolio_segment or pdf_entry.get("portfolio_segment") or "portafolio_general"
    portfolio_subsegment = portfolio_subsegment or pdf_entry.get("portfolio_subsegment")

    description_text = collect_section_text(section_map, ["descripcion", "descripción", "uso", "aplic", "general"])
    prep_text = collect_section_text(section_map, ["prepar", "superficie", "limpieza"])
    app_text = collect_section_text(section_map, ["aplic", "metodo", "método", "herramient"])
    dilution_text = collect_section_text(section_map, ["diluc", "mezcla", "thinner", "agua", "solvente", "catalizador"])
    drying_text = collect_section_text(section_map, ["secado", "repinte", "curado", "vida útil", "pot life"])
    restriction_text = collect_section_text(section_map, ["limit", "restric", "nota", "advert", "almacen"])
    solution_guidance = extract_solution_guidance(clean_text, section_map, doc_kind)

    summary_candidates = extract_lines_matching(description_text or clean_text, ["ideal", "recomend", "uso", "aplica", "producto"], max_lines=3)
    recommended_uses = extract_lines_matching(description_text or clean_text, ["ideal", "recomend", "uso", "aplica", "interior", "exterior"], max_lines=8)
    not_recommended = extract_lines_matching(restriction_text or clean_text, ["no ", "evit", "restric", "no recomend", "no aplicar"], max_lines=8)
    preparation = extract_lines_matching(prep_text or clean_text, ["prepar", "limp", "lij", "escarif", "granall", "seca", "libre de"], max_lines=10)
    dilution_lines = extract_lines_matching(dilution_text or clean_text, ["dilu", "mezcl", "agua", "thinner", "solvente", "ajustador", "catalizador"], max_lines=10)
    drying_lines = extract_lines_matching(drying_text or clean_text, ["secad", "tacto", "repinte", "curado", "pot life", "vida util"], max_lines=10)
    alert_lines = extract_lines_matching(restriction_text or clean_text, ["advert", "no ", "oblig", "debe", "evit", "prohib"], max_lines=12)
    summary_candidates = filter_low_signal_lines(summary_candidates, max_items=3)
    recommended_uses = filter_low_signal_lines(recommended_uses, max_items=8)
    not_recommended = filter_low_signal_lines(not_recommended, max_items=8)
    preparation = filter_low_signal_lines(preparation, max_items=10)
    dilution_lines = filter_low_signal_lines(dilution_lines, max_items=10)
    drying_lines = filter_low_signal_lines(drying_lines, max_items=10)
    alert_lines = filter_low_signal_lines(alert_lines, max_items=12)
    utility_document = is_utility_document(filename, canonical_family)

    coverage_min, coverage_max, coverage_text = extract_numeric_range(
        clean_text,
        ["rendimiento", "coverage", "cobertura"],
        r"(?:m2|m²)\s*(?:/|por)\s*(?:gal(?:on)?|galón|l|litro)"
    )
    solids_by_volume, solids_text = extract_numeric_value(clean_text, ["solidos por volumen", "sólidos por volumen", "% volumen sólidos"], r"%")
    voc_value, voc_text = extract_numeric_value(clean_text, ["voc", "c.o.v", "compuestos organicos volatiles", "compuestos orgánicos volátiles"], r"g/?l")
    density_value, density_text = extract_numeric_value(clean_text, ["densidad"], r"kg/?l")
    mix_min, mix_max, mix_text = extract_numeric_range(clean_text, ["relacion de mezcla", "relación de mezcla", "mezcla", "mix ratio"], r"(?:partes?|:|x1)")
    dilution_min, dilution_max, dilution_pct_text = extract_numeric_range(clean_text, ["dilucion", "dilución", "diluir", "ajustador"], r"%")
    if (dilution_min is None or dilution_max is None) and dilution_lines:
        dilution_percentages = [
            parse_decimal(match)
            for match in re.findall(r"(\d+[\.,]?\d*)\s*%", "\n".join(dilution_lines), re.IGNORECASE)
        ]
        dilution_percentages = [value for value in dilution_percentages if value is not None]
        if dilution_percentages:
            dilution_min = min(dilution_percentages)
            dilution_max = max(dilution_percentages)
    touch_dry_value, touch_dry_text = extract_numeric_value(clean_text, ["seco al tacto", "secado al tacto"], r"(?:horas?|h|minutos?|min)")
    recoat_value, recoat_text = extract_numeric_value(clean_text, ["repinte", "recoat", "intervalo de repinte"], r"(?:horas?|h|minutos?|min)")
    cure_value, cure_text = extract_numeric_value(clean_text, ["curado total", "curado completo", "cura total"], r"(?:horas?|h|dias?|días)")
    coats_value, coats_text = extract_numeric_value(clean_text, ["numero de manos", "número de manos", "manos", "capas"], r"(?:manos?|capas?)")

    profile = {
        "schema_version": "2026-04-11.profile.v1",
        "source": {
            "doc_filename": filename,
            "doc_path_lower": path_lower,
            "content_hash": pdf_entry.get("content_hash"),
            "text_fingerprint": compute_text_fingerprint(clean_text),
            "document_scope": "primary" if doc_kind == "ficha_tecnica" else "guide",
            "portfolio_segment": portfolio_segment,
            "portfolio_subsegment": portfolio_subsegment,
            "duplicate_count": pdf_entry.get("duplicate_count", 0),
            "duplicate_members": pdf_entry.get("duplicate_members") or [filename],
        },
        "product_identity": {
            "display_name": display_name,
            "brand": marca,
            "canonical_family": canonical_family,
            "aliases": aliases,
            "document_type": doc_kind,
            "product_role": "ajustador_o_auxiliar" if utility_document else "producto_principal",
            "portfolio_segment": portfolio_segment,
            "portfolio_subsegment": portfolio_subsegment,
        },
        "commercial_context": {
            "summary": choose_best_summary(summary_candidates, display_name, utility_document),
            "recommended_uses": recommended_uses,
            "not_recommended_for": not_recommended,
            "application_contexts": detect_surface_tags(description_text + "\n" + app_text),
            "compatible_surfaces": detect_surface_tags(description_text + "\n" + prep_text),
            "incompatible_surfaces": detect_surface_tags("\n".join(not_recommended)),
        },
        "application": {
            "surface_preparation": preparation,
            "application_methods": detect_application_methods(app_text or clean_text),
            "mixing": [mix_text] if mix_text else [],
            "dilution": {
                "ratio_texts": dilution_lines,
                "min_percent": dilution_min,
                "max_percent": dilution_max,
                "notes": [dilution_pct_text] if dilution_pct_text else [],
            },
            "recommended_coats": int(coats_value) if coats_value and float(coats_value).is_integer() else None,
            "coats_notes": [coats_text] if coats_text else [],
            "drying": {
                "touch_dry": touch_dry_text,
                "recoat": recoat_text,
                "full_cure": cure_text,
                "notes": drying_lines,
            },
        },
        "performance": {
            "coverage": {
                "unit": "m2/gal",
                "min_m2_per_gal": coverage_min,
                "max_m2_per_gal": coverage_max,
                "notes": [coverage_text] if coverage_text else [],
            },
            "solids_by_volume_percent": solids_by_volume,
            "voc_g_l": voc_value,
            "density_kg_l": density_value,
            "metrics_notes": dedupe_list([value for value in [solids_text, voc_text, density_text] if value]),
        },
        "technical_specs": extract_key_value_specs(clean_text),
        "solution_guidance": solution_guidance,
        "portfolio_classification": {
            "segment": portfolio_segment,
            "subsegment": portfolio_subsegment,
        },
        "alerts": {
            "critical": alert_lines,
            "do": extract_lines_matching(clean_text, ["debe", "aplique", "utilice", "asegure"], max_lines=10),
            "dont": extract_lines_matching(clean_text, ["no usar", "no aplicar", "no mezclar", "evite"], max_lines=10),
        },
        "extraction": {
            "strategy": "heuristic",
            "llm_enriched": False,
            "sections_detected": list(section_map.keys())[:30],
            "generated_at": datetime.now(UTC).isoformat(),
        },
    }
    if utility_document:
        profile["commercial_context"]["application_contexts"] = dedupe_list(
            profile["commercial_context"].get("application_contexts") or []
            + ["producto_auxiliar", "sistema_de_aplicacion"],
            max_items=8,
        )
        if not profile["commercial_context"].get("summary"):
            profile["commercial_context"]["summary"] = f"Producto auxiliar para dilución, ajuste o limpieza del sistema {display_name}."
        profile["application"]["surface_preparation"] = [
            step for step in profile["application"].get("surface_preparation") or []
            if "limpieza" in normalize_text(step) or "desengrase" in normalize_text(step) or "remover grasa" in normalize_text(step) or "remover aceite" in normalize_text(step)
        ]
        if not profile["application"]["surface_preparation"]:
            profile["application"]["surface_preparation"] = filter_low_signal_lines(
                extract_lines_matching(clean_text, ["limpieza", "desengrase", "remover grasa", "remover aceite"], max_lines=6),
                max_items=6,
            )
        profile["application"]["application_methods"] = []
        profile["performance"]["coverage"]["notes"] = []
        profile["performance"]["coverage"]["min_m2_per_gal"] = None
        profile["performance"]["coverage"]["max_m2_per_gal"] = None
    profile["extraction"]["field_coverage_score"] = compute_profile_completeness(profile)
    excerpts = {
        "description": limit_text(description_text or clean_text[:3500], 3500),
        "preparation": limit_text(prep_text, 3000),
        "application": limit_text(app_text, 3000),
        "dilution": limit_text(dilution_text, 2500),
        "drying": limit_text(drying_text, 2500),
        "restrictions": limit_text(restriction_text, 2500),
    }
    return profile, excerpts


def extract_llm_profile(openai_client: OpenAI, heuristic_profile: dict, excerpts: dict[str, str]) -> dict | None:
    user_payload = {
        "task": "Extrae y mejora el perfil técnico de una ficha sin inventar datos. Solo usa evidencia textual.",
        "rules": [
            "Devuelve JSON valido solamente.",
            "No inventes compatibilidades, rendimientos, diluciones ni tiempos.",
            "Si un dato no existe, dejalo vacio o no lo agregues.",
            "Mantén listas cortas y útiles para asesoría técnica/comercial.",
        ],
        "current_profile": {
            **heuristic_profile,
            "technical_specs": (heuristic_profile.get("technical_specs") or [])[:12],
        },
        "source_excerpts": excerpts,
        "target_shape": {
            "commercial_context": {
                "summary": "",
                "recommended_uses": [],
                "not_recommended_for": [],
                "application_contexts": [],
                "compatible_surfaces": [],
                "incompatible_surfaces": [],
            },
            "application": {
                "surface_preparation": [],
                "application_methods": [],
                "mixing": [],
                "dilution": {
                    "ratio_texts": [],
                    "min_percent": None,
                    "max_percent": None,
                    "notes": [],
                },
                "recommended_coats": None,
                "coats_notes": [],
                "drying": {
                    "touch_dry": None,
                    "recoat": None,
                    "full_cure": None,
                    "notes": [],
                },
            },
            "performance": {
                "coverage": {
                    "unit": "m2/gal",
                    "min_m2_per_gal": None,
                    "max_m2_per_gal": None,
                    "notes": [],
                },
                "solids_by_volume_percent": None,
                "voc_g_l": None,
                "density_kg_l": None,
                "metrics_notes": [],
            },
            "technical_specs": [],
            "alerts": {
                "critical": [],
                "do": [],
                "dont": [],
            },
        },
    }
    try:
        response = openai_client.chat.completions.create(
            model=PROFILE_EXTRACTION_MODEL,
            response_format={"type": "json_object"},
            temperature=0,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Eres un extractor de fichas tecnicas industriales y arquitectonicas. "
                        "Tu trabajo es convertir evidencia textual en un JSON util para asesoria tecnica y comercial. "
                        "No inventes datos. Si un dato no existe en la evidencia, dejalo vacio."
                    ),
                },
                {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
            ],
            max_tokens=2200,
        )
        content = (response.choices[0].message.content or "{}").strip()
        parsed = extract_json_object_from_text(content)
        if parsed is not None:
            return parsed
        repaired = repair_llm_json(openai_client, content)
        if repaired is not None:
            return repaired
        raise ValueError("No se pudo parsear el JSON del enriquecimiento")
    except Exception as exc:
        logger.warning("  ⚠ No se pudo enriquecer perfil con LLM: %s", exc)
        return None


def build_technical_profile(openai_client: OpenAI, filename: str, path_lower: str, marca: str | None,
                            canonical_family: str, clean_text: str, pdf_entry: dict,
                            doc_kind: str = "ficha_tecnica",
                            portfolio_segment: str | None = None,
                            portfolio_subsegment: str | None = None) -> dict:
    heuristic_profile, excerpts = build_heuristic_technical_profile(
        filename,
        path_lower,
        marca,
        canonical_family,
        clean_text,
        pdf_entry,
        doc_kind,
        portfolio_segment,
        portfolio_subsegment,
    )
    llm_profile = extract_llm_profile(openai_client, heuristic_profile, excerpts)
    merged_profile = merge_profile_values(heuristic_profile, llm_profile or {})
    merged_profile.setdefault("extraction", {})
    merged_profile["extraction"]["strategy"] = "hybrid" if llm_profile else "heuristic"
    merged_profile["extraction"]["llm_enriched"] = bool(llm_profile)
    merged_profile["extraction"]["generated_at"] = datetime.now(UTC).isoformat()
    merged_profile["extraction"]["field_coverage_score"] = compute_profile_completeness(merged_profile)
    return merged_profile


# ---------------------------------------------------------------------------
# Section-aware chunking
# ---------------------------------------------------------------------------
SECTION_HEADER_PATTERNS = [
    r"^[A-ZÁÉÍÓÚÑ\s/]{5,60}$",         # ALL CAPS lines (common section headers)
    r"^(?:\d+[\.\)]\s*)?[A-ZÁÉÍÓÚÑ][\w\s/]+:?\s*$",  # Numbered sections
]

def _is_section_header(line: str) -> bool:
    """Detect if a line is likely a section header in a technical sheet."""
    stripped = line.strip()
    if not stripped or len(stripped) < 4 or len(stripped) > 80:
        return False
    for pattern in SECTION_HEADER_PATTERNS:
        if re.match(pattern, stripped):
            return True
    return False


def _split_into_sections(text: str) -> list[tuple[str, str]]:
    """Split text into (section_header, section_body) tuples."""
    lines = text.split("\n")
    sections = []
    current_header = "GENERAL"
    current_body: list[str] = []

    for line in lines:
        if _is_section_header(line) and line.strip():
            # Save previous section
            if current_body:
                body_text = "\n".join(current_body).strip()
                if body_text:
                    sections.append((current_header, body_text))
            current_header = line.strip()
            current_body = []
        else:
            current_body.append(line)

    # Last section
    if current_body:
        body_text = "\n".join(current_body).strip()
        if body_text:
            sections.append((current_header, body_text))

    return sections if sections else [("GENERAL", text)]


def chunk_text_with_context(text: str, doc_filename: str, marca: str | None,
                             max_chars: int = CHUNK_MAX_CHARS,
                             overlap: int = CHUNK_OVERLAP_CHARS) -> list[str]:
    """Section-aware chunking with document context header in each chunk."""
    if not text:
        return []

    # Build document context header
    product_name = re.sub(r"\.pdf$", "", doc_filename, flags=re.IGNORECASE).strip()
    product_name = re.sub(r"\s*\(.*?\)\s*", " ", product_name).strip()
    context_header = f"[PRODUCTO: {product_name}]"
    if marca:
        context_header += f" [MARCA: {marca}]"

    # Split into sections
    sections = _split_into_sections(text)

    chunks = []
    for section_header, section_body in sections:
        # Prepend context + section header to chunk
        section_prefix = f"{context_header}\n[SECCIÓN: {section_header}]\n\n"
        available_chars = max_chars - len(section_prefix)

        if len(section_body) <= available_chars:
            chunks.append(f"{section_prefix}{section_body}")
        else:
            # Sub-chunk within section
            start = 0
            while start < len(section_body):
                end = start + available_chars
                if end < len(section_body):
                    break_at = section_body.rfind("\n\n", start + available_chars // 2, end)
                    if break_at == -1:
                        break_at = section_body.rfind(". ", start + available_chars // 2, end)
                    if break_at > start:
                        end = break_at + 1
                sub_chunk = section_body[start:end].strip()
                if sub_chunk:
                    chunks.append(f"{section_prefix}{sub_chunk}")
                start = end - overlap if end < len(section_body) else len(section_body)

    # If section splitting produced nothing useful, fall back to simple chunking
    if not chunks:
        simple_prefix = f"{context_header}\n\n"
        available = max_chars - len(simple_prefix)
        start = 0
        while start < len(text):
            end = start + available
            if end < len(text):
                break_at = text.rfind("\n\n", start + available // 2, end)
                if break_at == -1:
                    break_at = text.rfind(". ", start + available // 2, end)
                if break_at > start:
                    end = break_at + 1
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(f"{simple_prefix}{chunk}")
            start = end - overlap if end < len(text) else len(text)

    return chunks


# ---------------------------------------------------------------------------
# Metadata inference from filename/path
# ---------------------------------------------------------------------------
def infer_doc_type(filename: str, path_lower: str) -> str:
    doc_kind = classify_document_kind(filename, path_lower)
    return doc_kind


def infer_brand(filename: str, path_lower: str) -> str | None:
    combined = (filename + " " + path_lower).lower()
    for brand in BRAND_PATTERNS:
        if brand in combined:
            return brand.capitalize()
    return None


def infer_family(filename: str) -> str | None:
    name_clean = normalize_document_name(filename)
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


def get_ingested_doc_index(engine) -> dict[str, str | None]:
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT doc_path_lower, MAX(metadata ->> 'content_hash') AS content_hash
            FROM public.agent_technical_doc_chunk
            GROUP BY doc_path_lower
        """)).fetchall()
    return {row[0]: row[1] for row in rows}


def get_ingested_profile_index(engine) -> dict[str, str | None]:
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT source_doc_path_lower, MAX(content_hash) AS content_hash
            FROM public.agent_technical_profile
            GROUP BY source_doc_path_lower
        """)).fetchall()
    return {row[0]: row[1] for row in rows}


def delete_doc_chunks(engine, path_lower: str):
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM public.agent_technical_doc_chunk WHERE doc_path_lower = :p"), {"p": path_lower})


def delete_technical_profile(engine, path_lower: str):
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM public.agent_technical_profile WHERE source_doc_path_lower = :p"), {"p": path_lower})


def insert_chunks(engine, chunks_data: list[dict]):
    """Insert chunks using raw psycopg2 to avoid SQLAlchemy text() issues with ::vector cast."""
    raw_conn = engine.raw_connection()
    try:
        cur = raw_conn.cursor()
        for chunk in chunks_data:
            embedding_str = "[" + ",".join(str(v) for v in chunk["embedding"]) + "]"
            metadata_json = json.dumps(chunk.get("metadata") or {}, ensure_ascii=False)
            cur.execute("""
                INSERT INTO public.agent_technical_doc_chunk
                    (doc_filename, doc_path_lower, chunk_index, chunk_text,
                     marca, familia_producto, tipo_documento, metadata,
                     embedding, token_count)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::vector, %s)
                ON CONFLICT (doc_path_lower, chunk_index) DO UPDATE SET
                    chunk_text = EXCLUDED.chunk_text,
                    marca = EXCLUDED.marca,
                    familia_producto = EXCLUDED.familia_producto,
                    tipo_documento = EXCLUDED.tipo_documento,
                    metadata = EXCLUDED.metadata,
                    embedding = EXCLUDED.embedding,
                    token_count = EXCLUDED.token_count,
                    ingested_at = now()
            """, (
                chunk["doc_filename"],
                chunk["doc_path_lower"],
                chunk["chunk_index"],
                chunk["chunk_text"],
                chunk["marca"],
                chunk["familia_producto"],
                chunk["tipo_documento"],
                metadata_json,
                embedding_str,
                chunk.get("token_count"),
            ))
        raw_conn.commit()
    except Exception:
        raw_conn.rollback()
        raise
    finally:
        raw_conn.close()


def upsert_technical_profile(engine, profile_record: dict):
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO public.agent_technical_profile (
                canonical_family,
                source_doc_filename,
                source_doc_path_lower,
                marca,
                tipo_documento,
                profile_json,
                completeness_score,
                extraction_method,
                extraction_status,
                content_hash,
                text_fingerprint,
                generated_at,
                updated_at
            ) VALUES (
                :canonical_family,
                :source_doc_filename,
                :source_doc_path_lower,
                :marca,
                :tipo_documento,
                CAST(:profile_json AS jsonb),
                :completeness_score,
                :extraction_method,
                :extraction_status,
                :content_hash,
                :text_fingerprint,
                now(),
                now()
            )
            ON CONFLICT (canonical_family) DO UPDATE SET
                source_doc_filename = EXCLUDED.source_doc_filename,
                source_doc_path_lower = EXCLUDED.source_doc_path_lower,
                marca = EXCLUDED.marca,
                tipo_documento = EXCLUDED.tipo_documento,
                profile_json = EXCLUDED.profile_json,
                completeness_score = EXCLUDED.completeness_score,
                extraction_method = EXCLUDED.extraction_method,
                extraction_status = EXCLUDED.extraction_status,
                content_hash = EXCLUDED.content_hash,
                text_fingerprint = EXCLUDED.text_fingerprint,
                updated_at = now()
        """), {
            "canonical_family": profile_record["canonical_family"],
            "source_doc_filename": profile_record["source_doc_filename"],
            "source_doc_path_lower": profile_record["source_doc_path_lower"],
            "marca": profile_record.get("marca"),
            "tipo_documento": profile_record.get("tipo_documento") or "ficha_tecnica",
            "profile_json": json.dumps(profile_record["profile_json"], ensure_ascii=False),
            "completeness_score": profile_record.get("completeness_score") or 0,
            "extraction_method": profile_record.get("extraction_method") or "hybrid",
            "extraction_status": profile_record.get("extraction_status") or "ready",
            "content_hash": profile_record.get("content_hash"),
            "text_fingerprint": profile_record.get("text_fingerprint"),
        })


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

    marca = pdf_entry.get("marca") or infer_brand(filename, path_lower)
    familia = pdf_entry.get("canonical_family") or infer_family(filename)
    tipo_doc = infer_doc_type(filename, path_lower)
    portfolio_segment = pdf_entry.get("portfolio_segment")
    portfolio_subsegment = pdf_entry.get("portfolio_subsegment")
    refined_segment, refined_subsegment = infer_portfolio_segment(
        filename,
        path_lower,
        clean_text=clean_text,
        doc_kind=tipo_doc,
        inferred_brand=marca,
    )
    if not portfolio_segment or portfolio_segment == "portafolio_general":
        portfolio_segment = refined_segment
    if not portfolio_subsegment and refined_segment == portfolio_segment:
        portfolio_subsegment = refined_subsegment
    text_fingerprint = compute_text_fingerprint(clean_text)
    technical_profile = build_technical_profile(
        openai_client,
        filename,
        path_lower,
        marca,
        familia,
        clean_text,
        pdf_entry,
        tipo_doc,
        portfolio_segment,
        portfolio_subsegment,
    )

    chunks = chunk_text_with_context(clean_text, filename, marca)
    if not chunks:
        return 0

    normalized_name = normalize_text(filename)
    has_primary_hint = any(tok in normalized_name for tok in [normalize_text(tok) for tok in PRIMARY_DOC_HINTS])
    if tipo_doc == "ficha_tecnica" and len(chunks) > MAX_PRIMARY_CHUNKS and not has_primary_hint:
        logger.warning(
            "  ⚠ Documento omitido por ser demasiado extenso para índice primario: %s (%s chunks)",
            filename,
            len(chunks),
        )
        return 0

    logger.info(f"  {len(chunks)} chunks generados, generando embeddings...")
    embeddings = generate_embeddings(openai_client, chunks)

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
            "metadata": {
                "content_hash": pdf_entry.get("content_hash"),
                "size": pdf_entry.get("size"),
                "doc_kind": pdf_entry.get("doc_kind") or tipo_doc,
                "canonical_family": familia,
                "normalized_name": pdf_entry.get("normalized_name") or normalize_document_name(filename),
                "duplicate_count": pdf_entry.get("duplicate_count", 0),
                "duplicate_members": pdf_entry.get("duplicate_members") or [filename],
                "text_fingerprint": text_fingerprint,
                "document_scope": "primary" if tipo_doc == "ficha_tecnica" else "guide",
                "quality_tier": "primary" if tipo_doc == "ficha_tecnica" else "supporting",
                "portfolio_segment": portfolio_segment,
                "portfolio_subsegment": portfolio_subsegment,
            },
            "embedding": embedding,
            "token_count": len(chunk_text_val) // 4,
        })

    delete_doc_chunks(engine, path_lower)
    insert_chunks(engine, chunks_data)
    upsert_technical_profile(engine, {
        "canonical_family": familia,
        "source_doc_filename": filename,
        "source_doc_path_lower": path_lower,
        "marca": marca,
        "tipo_documento": tipo_doc,
        "profile_json": technical_profile,
        "completeness_score": technical_profile.get("extraction", {}).get("field_coverage_score") or 0,
        "extraction_method": technical_profile.get("extraction", {}).get("strategy") or "hybrid",
        "extraction_status": "ready",
        "content_hash": pdf_entry.get("content_hash"),
        "text_fingerprint": text_fingerprint,
    })
    logger.info(f"  ✅ {filename}: {len(chunks_data)} chunks insertados")
    return len(chunks_data)


def run_ingestion(full_mode: bool = False, dry_run: bool = False):
    logger.info("=" * 60)
    logger.info("INGESTIÓN DE FICHAS TÉCNICAS → pgvector")
    logger.info("=" * 60)

    engine = get_db_engine()
    ensure_chunk_table(engine)
    ensure_profile_table(engine)

    dbx = get_dropbox_client()
    openai_client = get_openai_client()

    logger.info(f"Listando PDFs en Dropbox: {TECHNICAL_DOC_FOLDER}")
    pdf_entries = list_dropbox_pdfs(dbx)
    logger.info(f"  Encontrados: {len(pdf_entries)} PDFs")

    curated_entries, duplicate_groups, skipped_entries = curate_pdf_entries(pdf_entries)
    report = build_corpus_report(curated_entries, duplicate_groups, skipped_entries)
    write_corpus_report(report)
    logger.info(
        "  Corpus curado: %s fichas primarias | %s grupos duplicados | %s omitidos",
        len(curated_entries),
        len(duplicate_groups),
        len(skipped_entries),
    )

    if full_mode:
        logger.info("Modo COMPLETO: borrando índice técnico Dropbox anterior...")
        with engine.begin() as conn:
            conn.execute(
                text("DELETE FROM public.agent_technical_doc_chunk WHERE doc_path_lower LIKE :prefix"),
                {"prefix": f"{TECHNICAL_DOC_FOLDER.lower()}%"},
            )
            conn.execute(
                text("DELETE FROM public.agent_technical_profile WHERE source_doc_path_lower LIKE :prefix"),
                {"prefix": f"{TECHNICAL_DOC_FOLDER.lower()}%"},
            )
        already_ingested = set()
        existing_index = {}
        existing_profile_index = {}
    else:
        already_ingested = get_ingested_paths(engine)
        existing_index = get_ingested_doc_index(engine)
        existing_profile_index = get_ingested_profile_index(engine)
        logger.info(f"  Ya ingestados: {len(already_ingested)} documentos")

    survivor_paths = {entry["path_lower"] for entry in curated_entries}
    existing_dropbox_paths = {path for path in already_ingested if path.startswith(TECHNICAL_DOC_FOLDER.lower())}
    stale_paths = sorted(existing_dropbox_paths - survivor_paths)
    if stale_paths:
        logger.info("  Paths obsoletos a eliminar del índice: %s", len(stale_paths))
        for stale_path in stale_paths:
            delete_doc_chunks(engine, stale_path)
            delete_technical_profile(engine, stale_path)

    pending = []
    for entry in curated_entries:
        existing_hash = existing_index.get(entry["path_lower"])
        existing_profile_hash = existing_profile_index.get(entry["path_lower"])
        profile_missing = entry["path_lower"] not in existing_profile_index
        if (
            full_mode
            or entry["path_lower"] not in already_ingested
            or (entry.get("content_hash") and entry.get("content_hash") != existing_hash)
            or profile_missing
            or (entry.get("content_hash") and entry.get("content_hash") != existing_profile_hash)
        ):
            pending.append(entry)
    logger.info(f"  Pendientes de reingesta: {len(pending)} fichas técnicas canónicas")

    if dry_run:
        for entry in pending:
            logger.info(
                "    [DRY-RUN] %s | familia=%s | duplicados=%s",
                entry["name"],
                entry.get("canonical_family"),
                entry.get("duplicate_count", 0),
            )
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
