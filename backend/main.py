import os
import json
import re
import time
import tomllib
import unicodedata
from difflib import SequenceMatcher
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

import dropbox
import requests
from fastapi import FastAPI, HTTPException, Query, Request
from openai import OpenAI
from sqlalchemy import create_engine, text


app = FastAPI(title="CRM Ferreinox Backend", version="2026.2")


SECRETS_PATH = Path(__file__).resolve().parent.parent / ".streamlit" / "secrets.toml"
TECHNICAL_DOC_FOLDER = "/data/FICHAS TÉCNICAS Y HOJAS DE SEGURIDAD"
TECHNICAL_DOC_CACHE_TTL_SECONDS = 600
TECHNICAL_DOC_STOPWORDS = {
    "ficha",
    "fichas",
    "tecnica",
    "tecnicas",
    "tecnico",
    "tecnico",
    "hoja",
    "hojas",
    "seguridad",
    "pdf",
    "envia",
    "enviame",
    "enviamelo",
    "manda",
    "mandame",
    "mandamelo",
    "adjunta",
    "adjuntame",
    "anexa",
    "anexame",
    "sirve",
    "sirva",
    "puedes",
    "puede",
    "podrias",
    "podria",
    "quiero",
    "quieres",
    "necesito",
    "enviar",
    "envies",
    "mandar",
    "mandes",
    "archivo",
    "documento",
    "documentacion",
    "tecnica",
    "tecnico",
    "segun",
    "saber",
    "tienes",
    "tiene",
    "tengo",
    "si",
    "es",
    "que",
    "del",
    "de",
    "me",
    "la",
    "el",
}
TECHNICAL_DOC_CACHE = {"loaded_at": 0.0, "entries": []}


PRODUCT_STOPWORDS = {
    "ay",
    "de",
    "del",
    "la",
    "el",
    "los",
    "las",
    "un",
    "una",
    "unos",
    "unas",
    "para",
    "por",
    "con",
    "sin",
    "que",
    "me",
    "mi",
    "necesito",
    "quiero",
    "cotizar",
    "comprar",
    "pedido",
    "favor",
    "informacion",
    "información",
    "sobre",
    "tengo",
    "hay",
    "tienen",
    "inventario",
    "stock",
    "en",
    "este",
    "ano",
    "año",
    "cuanto",
    "debo",
    "codigo",
    "cod",
    "ref",
    "refer",
    "es",
    "producto",
    "marca",
}


PRESENTATION_ALIASES = {
    "cuñete": ["cunete", "cunetes", "cuenete", "cuenetes", "cuñete", "cuñetes", "caneca", "canecas", "cubeta", "cubetas", "18.93l", "18.93", "1/5", "5gl"],
    "galon": ["galon", "galones", "gal", "3.79l", "3.79", "1/1", "1gl"],
    "cuarto": ["cuarto", "cuartos", "0.95l", "0.95", "1/4"],
}


PRESENTATION_LABELS = {
    "cuñete": ("cuñete", "cuñetes"),
    "galon": ("galón", "galones"),
    "cuarto": ("cuarto", "cuartos"),
}


PRESENTATION_SHORTCUTS = {
    "1": "galon",
    "4": "cuarto",
    "5": "cuñete",
}


PRESENTATION_SIZE_MAP = {
    "18.93": "cuñete",
    "18.93l": "cuñete",
    "3.79": "galon",
    "3.79l": "galon",
    "0.95": "cuarto",
    "0.95l": "cuarto",
}


PORTFOLIO_ALIASES = {
    "vinilico": ["vinilico", "viniltex", "vinilo", "vinilica", "viniloco", "vinilico blanco", "viniltex blanco"],
    "viniloco": ["viniloco", "vinilico", "viniltex", "vinilo", "vinilico blanco", "viniltex blanco"],
    "viniltex": ["viniltex", "vinilico", "vinilo", "vtx"],
    "pintulux": ["pintulux", "pintulux 3en1", "pintulux 3 en 1", "pintulux 3-en-1", "3en1", "3 en 1", "3-en-1"],
    "domestico": ["domestico", "doméstico", "vinilico", "viniltex", "economico", "económico"],
    "pintuco": ["pintuco", "viniltex", "p11", "p-11", "p 11"],
    "p11": ["p11", "p-11", "p 11", "pintuco 11"],
    "t11": ["t11", "t-11", "t 11", "pintulux 3en1", "pintulux 3 en 1", "3en1 br blanco 11", "br blanco 11"],
    "p53": ["p53", "p-53", "p 53", "verde esmeral", "verde esmer"],
    "mega": ["mega", "cerradura mega", "sobreponer"],
    "cerradura": ["cerradura", "cerradur", "chapa", "lock"],
    "derecha": ["derecha", "derecho", "der", "derc"],
    "izquierda": ["izquierda", "izquierdo", "izq"],
    "brocha": ["brocha", "brochas", "pincel"],
    "popular": ["popular", "pop"],
    "abracol": ["abracol"],
    "yale": ["yale"],
    "goya": ["goya"],
}


DIRECTION_ALIASES = {
    "derecha": ["derecha", "derecho", "der", "derc"],
    "izquierda": ["izquierda", "izquierdo", "izq"],
}


STORE_CODE_LABELS = {
    "155": "CEDI",
    "156": "Tienda Armenia",
    "157": "Tienda Manizales",
    "158": "Tienda Opalo",
    "189": "Tienda Pereira",
    "238": "Tienda Laures",
    "439": "Tienda Ferrebox",
    "463": "Tienda Cerritos",
}


STORE_ALIASES = {
    "cedi": ["155", "cedi", "centro de distribucion", "centro de distribución"],
    "armenia": ["156", "armenia", "tienda armenia"],
    "manizales": ["157", "manizales", "tienda manizales"],
    "opalo": ["158", "opalo", "ópalo", "tienda opalo", "tienda ópalo"],
    "pereira": ["189", "pereira", "tienda pereira"],
    "laures": ["238", "laures", "laureles", "tienda laures", "tienda laureles"],
    "cerritos": ["463", "cerritos", "tienda cerritos"],
    "ferrebox": ["439", "ferrebox", "tienda ferrebox"],
}


BRAND_ALIASES = {
    "pintuco": ["pintuco", "viniltex", "viniltex adv", "p11", "p-11", "p 11"],
    "abracol": ["abracol"],
    "yale": ["yale"],
    "goya": ["goya"],
}


MONTH_ALIASES = {
    "enero": 1,
    "febrero": 2,
    "marzo": 3,
    "abril": 4,
    "mayo": 5,
    "junio": 6,
    "julio": 7,
    "agosto": 8,
    "septiembre": 9,
    "setiembre": 9,
    "octubre": 10,
    "noviembre": 11,
    "diciembre": 12,
}


PURCHASE_LINE_FILTER = """
COALESCE(valor_venta_neto, 0) > 0
AND COALESCE(unidades_vendidas_netas, 0) > 0
AND COALESCE(nombre_articulo, '') <> ''
AND COALESCE(nombre_articulo, '') NOT ILIKE '%TOTAL%'
AND COALESCE(nombre_articulo, '') NOT ILIKE '%NOTA CREDITO%'
"""


def get_postgrest_url():
    return os.getenv("PGRST_URL", "http://localhost:3000").rstrip("/")


def get_database_url():
    database_url = os.getenv("DATABASE_URL") or os.getenv("POSTGRES_DB_URI")
    if not database_url:
        raise RuntimeError("No se encontró DATABASE_URL o POSTGRES_DB_URI para el backend.")
    return database_url


def get_whatsapp_verify_token():
    return os.getenv("WHATSAPP_VERIFY_TOKEN", "ferreinox-verify-token")


def get_openai_api_key():
    return os.getenv("OPENAI_API_KEY")


def get_openai_model():
    return os.getenv("OPENAI_MODEL", "gpt-4o-mini")


def get_whatsapp_access_token():
    token = os.getenv("WHATSAPP_ACCESS_TOKEN")
    if not token:
        raise RuntimeError("No se encontró WHATSAPP_ACCESS_TOKEN para enviar mensajes.")
    return token


def get_whatsapp_phone_number_id():
    phone_number_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
    if not phone_number_id:
        raise RuntimeError("No se encontró WHATSAPP_PHONE_NUMBER_ID para enviar mensajes.")
    return phone_number_id


def get_openai_client():
    api_key = get_openai_api_key()
    if not api_key:
        raise RuntimeError("No se encontró OPENAI_API_KEY para generar respuestas del agente.")
    return OpenAI(api_key=api_key)


def get_db_engine():
    return create_engine(get_database_url())


def safe_json_dumps(value):
    return json.dumps(value, ensure_ascii=False, default=str)


def load_local_secrets():
    if not SECRETS_PATH.exists():
        return {}
    return tomllib.loads(SECRETS_PATH.read_text(encoding="utf-8"))


def get_dropbox_ventas_config():
    env_config = {
        "app_key": os.getenv("DROPBOX_VENTAS_APP_KEY"),
        "app_secret": os.getenv("DROPBOX_VENTAS_APP_SECRET"),
        "refresh_token": os.getenv("DROPBOX_VENTAS_REFRESH_TOKEN"),
        "folder": os.getenv("DROPBOX_VENTAS_FOLDER") or "/data",
    }
    if env_config["app_key"] and env_config["app_secret"] and env_config["refresh_token"]:
        return env_config

    secrets = load_local_secrets()
    config = secrets.get("dropbox_ventas") or {}
    if config.get("app_key") and config.get("app_secret") and config.get("refresh_token"):
        return config
    raise RuntimeError("No se encontró configuración válida para Dropbox Ventas.")


def get_dropbox_ventas_client():
    config = get_dropbox_ventas_config()
    return dropbox.Dropbox(
        oauth2_refresh_token=config["refresh_token"],
        app_key=config["app_key"],
        app_secret=config["app_secret"],
    )


def list_technical_document_entries(force_refresh: bool = False):
    cache_age = time.time() - float(TECHNICAL_DOC_CACHE.get("loaded_at") or 0)
    if not force_refresh and TECHNICAL_DOC_CACHE.get("entries") and cache_age < TECHNICAL_DOC_CACHE_TTL_SECONDS:
        return TECHNICAL_DOC_CACHE["entries"]

    dbx = get_dropbox_ventas_client()
    entries = []
    result = dbx.files_list_folder(TECHNICAL_DOC_FOLDER, recursive=True)
    while True:
        entries.extend(
            entry for entry in result.entries
            if isinstance(entry, dropbox.files.FileMetadata) and entry.name.lower().endswith(".pdf")
        )
        if not result.has_more:
            break
        result = dbx.files_list_folder_continue(result.cursor)

    TECHNICAL_DOC_CACHE["loaded_at"] = time.time()
    TECHNICAL_DOC_CACHE["entries"] = entries
    return entries


def is_technical_document_message(text_value: Optional[str]):
    normalized = normalize_text_value(text_value)
    if not normalized:
        return False
    return any(
        phrase in normalized
        for phrase in [
            "ficha tecnica",
            "ficha técnicas",
            "ficha tecnica",
            "hoja de seguridad",
            "hoja seguridad",
            "fds",
            "msds",
            "pdf",
        ]
    )


def extract_technical_document_request(text_value: Optional[str], product_request: Optional[dict] = None, conversation_context: Optional[dict] = None):
    normalized = normalize_text_value(text_value)
    request = product_request or extract_product_request(text_value)
    previous_document_request = (conversation_context or {}).get("last_document_request") or {}
    previous_request = (conversation_context or {}).get("last_product_request") or {}

    def collect_terms(source_terms: list[str]):
        collected_terms = []
        for term in source_terms:
            normalized_term = normalize_text_value(term)
            if (
                normalized_term
                and normalized_term not in TECHNICAL_DOC_STOPWORDS
                and normalized_term not in PRODUCT_STOPWORDS
                and not is_store_alias_term(normalized_term)
                and len(normalized_term) >= 3
                and normalized_term not in collected_terms
            ):
                collected_terms.append(normalized_term)
        return collected_terms

    current_terms = collect_terms(request.get("core_terms") or [])
    previous_document_terms = collect_terms(previous_document_request.get("terms") or [])
    previous_product_terms = collect_terms(previous_request.get("core_terms") or [])

    if current_terms:
        terms = current_terms
    elif previous_document_terms:
        terms = previous_document_terms
    else:
        terms = previous_product_terms

    wants_safety_sheet = any(keyword in normalized for keyword in ["hoja de seguridad", "hoja seguridad", "seguridad", "fds", "msds"])
    wants_technical_sheet = any(keyword in normalized for keyword in ["ficha tecnica", "ficha técnica", "ficha", "tecnica", "técnica"])

    return {
        "query": text_value or "",
        "terms": terms[:8],
        "wants_safety_sheet": wants_safety_sheet,
        "wants_technical_sheet": wants_technical_sheet or not wants_safety_sheet,
    }


def search_technical_documents(document_request: dict):
    terms = document_request.get("terms") or []
    if not terms:
        return []

    ranked_documents = []
    for entry in list_technical_document_entries():
        path_value = normalize_text_value(entry.path_lower or entry.name)
        name_value = normalize_text_value(entry.name)
        exact_hits = sum(1 for term in terms if term in path_value)
        if exact_hits == 0 and not any(sequence_similarity(term, name_value) >= 0.74 for term in terms):
            continue

        safety_score = 0
        if document_request.get("wants_safety_sheet"):
            safety_score = 1 if any(token in path_value for token in ["hoja", "seguridad", "fds", "msds"]) else 0
        technical_score = 0
        if document_request.get("wants_technical_sheet"):
            technical_score = 1 if not any(token in path_value for token in ["fds", "msds"]) else 0

        ranked_documents.append(
            {
                "name": entry.name,
                "path_lower": entry.path_lower,
                "exact_hits": exact_hits,
                "safety_score": safety_score,
                "technical_score": technical_score,
                "fuzzy_score": round(max(sequence_similarity(term, name_value) for term in terms), 4),
            }
        )

    ranked_documents.sort(
        key=lambda item: (
            item.get("safety_score") or 0,
            item.get("technical_score") or 0,
            item.get("exact_hits") or 0,
            item.get("fuzzy_score") or 0,
            len(item.get("name") or ""),
        ),
        reverse=True,
    )
    return ranked_documents[:6]


def resolve_technical_document_choice(text_value: Optional[str], document_options: list[dict]):
    normalized = normalize_text_value(text_value)
    if not normalized or not document_options:
        return None

    ordinal_map = {
        "1": 0,
        "uno": 0,
        "primera": 0,
        "primer": 0,
        "primero": 0,
        "2": 1,
        "dos": 1,
        "segunda": 1,
        "segundo": 1,
        "3": 2,
        "tres": 2,
        "tercera": 2,
        "tercero": 2,
        "4": 3,
        "cuatro": 3,
        "cuarta": 3,
        "cuarto": 3,
    }
    if normalized in ordinal_map and ordinal_map[normalized] < len(document_options):
        return document_options[ordinal_map[normalized]]

    for ordinal_text, option_index in ordinal_map.items():
        if option_index >= len(document_options):
            continue
        if re.fullmatch(rf"(?:la|el|opcion|archivo)?\s*{re.escape(ordinal_text)}", normalized):
            return document_options[option_index]

    for option in document_options:
        option_name = normalize_text_value(option.get("name"))
        if option_name and (option_name in normalized or normalized in option_name):
            return option
    return None


def get_dropbox_temporary_link(file_path: str):
    dbx = get_dropbox_ventas_client()
    return dbx.files_get_temporary_link(file_path).link


def normalize_text_value(text_value: Optional[str]):
    if not text_value:
        return ""
    normalized = unicodedata.normalize("NFKD", text_value)
    normalized = "".join(character for character in normalized if not unicodedata.combining(character))
    normalized = normalized.lower()
    normalized = re.sub(r"[^a-z0-9./+-]+", " ", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def normalize_reference_value(text_value: Optional[str]):
    normalized = normalize_text_value(text_value)
    if not normalized:
        return ""
    return re.sub(r"[^a-z0-9]+", "", normalized)


def parse_numeric_value(raw_value):
    if raw_value is None:
        return None
    if isinstance(raw_value, (int, float)):
        return float(raw_value)

    cleaned = str(raw_value).strip()
    if not cleaned:
        return None

    cleaned = re.sub(r"[^0-9,.-]", "", cleaned)
    if not cleaned:
        return None

    if "," in cleaned and "." in cleaned:
        cleaned = cleaned.replace(".", "").replace(",", ".")
    elif "," in cleaned:
        cleaned = cleaned.replace(",", ".")

    try:
        return float(cleaned)
    except ValueError:
        return None


def sequence_similarity(left_value: Optional[str], right_value: Optional[str]):
    left_normalized = normalize_text_value(left_value)
    right_normalized = normalize_text_value(right_value)
    if not left_normalized or not right_normalized:
        return 0.0
    return SequenceMatcher(None, left_normalized, right_normalized).ratio()


def has_keyword_or_similar(text_value: Optional[str], keywords: list[str], threshold: float = 0.84):
    normalized = normalize_text_value(text_value)
    if not normalized:
        return False
    if any(keyword in normalized for keyword in keywords):
        return True
    tokens = re.findall(r"[a-z0-9.-]+", normalized)
    for token in tokens:
        for keyword in keywords:
            if SequenceMatcher(None, token, normalize_text_value(keyword)).ratio() >= threshold:
                return True
    return False


def get_presentation_label(unit_value: Optional[str], quantity_value: Optional[float] = None):
    if not unit_value:
        return ""
    singular_label, plural_label = PRESENTATION_LABELS.get(unit_value, (unit_value, f"{unit_value}s"))
    if quantity_value is not None and float(quantity_value) == 1:
        return singular_label
    return plural_label


def should_store_learning_phrase(text_value: Optional[str]):
    normalized = normalize_text_value(text_value)
    if not normalized:
        return False
    if is_product_code_message(normalized):
        return False
    return len(normalized) >= 4


def build_learning_phrase_candidates(product_request: Optional[dict]):
    if not product_request:
        return []

    generic_terms = set(PRODUCT_STOPWORDS)
    for alias_group in PRESENTATION_ALIASES.values():
        generic_terms.update(normalize_text_value(alias) for alias in alias_group)
    for alias_group in STORE_ALIASES.values():
        generic_terms.update(normalize_text_value(alias) for alias in alias_group)

    phrases = []

    def add_phrase(raw_phrase: Optional[str]):
        normalized_phrase = normalize_text_value(raw_phrase)
        if not normalized_phrase or not should_store_learning_phrase(normalized_phrase):
            return
        if normalized_phrase not in phrases:
            phrases.append(normalized_phrase)

    add_phrase(product_request.get("original_query"))
    add_phrase(" ".join(product_request.get("core_terms") or []))

    specific_terms = []
    for term in product_request.get("core_terms") or []:
        normalized_term = normalize_text_value(term)
        if not normalized_term or normalized_term in generic_terms:
            continue
        if normalized_term not in specific_terms:
            specific_terms.append(normalized_term)

    if specific_terms:
        add_phrase(" ".join(specific_terms))
        if product_request.get("requested_unit"):
            add_phrase(" ".join(specific_terms + [product_request.get("requested_unit")]))
        if product_request.get("brand_filters"):
            for brand_name in product_request.get("brand_filters")[:2]:
                add_phrase(" ".join(specific_terms + [brand_name]))

    return phrases[:8]


def select_reliable_learning_rows(product_request: Optional[dict], product_context: list[dict]):
    if not product_request or not product_context:
        return []

    if product_request.get("product_codes"):
        return product_context[:1]

    if len(product_context) == 1:
        return product_context[:1]

    top_row = product_context[0]
    second_row = product_context[1] if len(product_context) > 1 else None
    top_specific = top_row.get("specific_score") or 0
    top_match = top_row.get("match_score") or 0
    top_brand = top_row.get("brand_score") or 0
    top_size = top_row.get("size_score") or 0
    second_specific = second_row.get("specific_score") or 0 if second_row else 0
    second_match = second_row.get("match_score") or 0 if second_row else 0

    if top_size > 0 and top_match >= 2:
        return [top_row]
    if top_brand > 0 and top_match >= 2:
        return [top_row]
    if top_specific >= 2 and (top_specific > second_specific or top_match > second_match):
        return [top_row]
    if top_match >= 3 and top_match > second_match:
        return [top_row]
    return []


def is_learned_reference_relevant(product_request: Optional[dict], learned_row: dict):
    if not product_request:
        return False

    description_text = normalize_text_value(learned_row.get("canonical_description"))
    brand_text = normalize_text_value(learned_row.get("canonical_brand"))
    combined_text = f"{description_text} {brand_text}".strip()
    specific_terms = get_specific_product_terms(product_request)
    if specific_terms and not any(term in combined_text for term in specific_terms):
        return False

    requested_unit = product_request.get("requested_unit")
    learned_presentation = normalize_text_value(learned_row.get("canonical_presentation"))
    if requested_unit and learned_presentation and requested_unit != learned_presentation:
        return False

    brand_filters = product_request.get("brand_filters") or []
    if brand_filters:
        matches_brand = False
        for brand_name in brand_filters:
            if brand_name in combined_text:
                matches_brand = True
                break
            for alias in BRAND_ALIASES.get(brand_name, []):
                if normalize_text_value(alias) in combined_text:
                    matches_brand = True
                    break
            if matches_brand:
                break
        if not matches_brand:
            return False

    return True


def ensure_product_learning_table():
    engine = get_db_engine()
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS public.agent_product_learning (
                    id bigserial PRIMARY KEY,
                    normalized_phrase text NOT NULL,
                    raw_phrase text NOT NULL,
                    canonical_reference text NOT NULL,
                    canonical_description text,
                    canonical_brand text,
                    canonical_presentation text,
                    source_conversation_id bigint REFERENCES public.agent_conversation(id) ON DELETE SET NULL,
                    source_message text,
                    confidence numeric(5,4) NOT NULL DEFAULT 0.7500,
                    usage_count integer NOT NULL DEFAULT 1,
                    created_at timestamptz NOT NULL DEFAULT now(),
                    updated_at timestamptz NOT NULL DEFAULT now(),
                    CONSTRAINT uq_agent_product_learning UNIQUE (normalized_phrase, canonical_reference)
                )
                """
            )
        )
        connection.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS idx_agent_product_learning_phrase
                ON public.agent_product_learning(normalized_phrase)
                """
            )
        )


def learn_product_resolution(conversation_id: Optional[int], product_request: Optional[dict], product_context: list[dict], conversation_context: Optional[dict] = None):
    if not product_request or not product_context:
        return

    reliable_rows = select_reliable_learning_rows(product_request, product_context)
    if not reliable_rows:
        return

    phrases = []
    previous_product_request = (conversation_context or {}).get("last_product_request") or {}
    for candidate_phrase in build_learning_phrase_candidates(product_request) + build_learning_phrase_candidates(previous_product_request):
        if candidate_phrase not in phrases:
            phrases.append(candidate_phrase)

    if not phrases:
        return

    ensure_product_learning_table()
    engine = get_db_engine()
    with engine.begin() as connection:
        for phrase in phrases[:6]:
            for row in reliable_rows:
                reference_value = row.get("referencia") or row.get("codigo_articulo")
                if not reference_value:
                    continue
                canonical_presentation = None
                description_value = normalize_text_value(row.get("descripcion") or row.get("nombre_articulo"))
                for size_token, unit_name in PRESENTATION_SIZE_MAP.items():
                    if size_token in description_value:
                        canonical_presentation = unit_name
                        break
                connection.execute(
                    text(
                        """
                        INSERT INTO public.agent_product_learning (
                            normalized_phrase,
                            raw_phrase,
                            canonical_reference,
                            canonical_description,
                            canonical_brand,
                            canonical_presentation,
                            source_conversation_id,
                            source_message,
                            confidence,
                            usage_count,
                            created_at,
                            updated_at
                        )
                        VALUES (
                            :normalized_phrase,
                            :raw_phrase,
                            :canonical_reference,
                            :canonical_description,
                            :canonical_brand,
                            :canonical_presentation,
                            :source_conversation_id,
                            :source_message,
                            :confidence,
                            1,
                            now(),
                            now()
                        )
                        ON CONFLICT (normalized_phrase, canonical_reference)
                        DO UPDATE SET
                            canonical_description = COALESCE(EXCLUDED.canonical_description, public.agent_product_learning.canonical_description),
                            canonical_brand = COALESCE(EXCLUDED.canonical_brand, public.agent_product_learning.canonical_brand),
                            canonical_presentation = COALESCE(EXCLUDED.canonical_presentation, public.agent_product_learning.canonical_presentation),
                            source_conversation_id = COALESCE(EXCLUDED.source_conversation_id, public.agent_product_learning.source_conversation_id),
                            source_message = COALESCE(EXCLUDED.source_message, public.agent_product_learning.source_message),
                            confidence = GREATEST(public.agent_product_learning.confidence, EXCLUDED.confidence),
                            usage_count = public.agent_product_learning.usage_count + 1,
                            updated_at = now()
                        """
                    ),
                    {
                        "normalized_phrase": phrase,
                        "raw_phrase": phrase,
                        "canonical_reference": str(reference_value),
                        "canonical_description": row.get("descripcion") or row.get("nombre_articulo"),
                        "canonical_brand": row.get("marca") or row.get("marca_producto"),
                        "canonical_presentation": canonical_presentation,
                        "source_conversation_id": conversation_id,
                        "source_message": product_request.get("original_query"),
                        "confidence": 0.95 if product_request.get("product_codes") else 0.82,
                    },
                )


def fetch_learned_product_references(product_request: Optional[dict]):
    if not product_request:
        return []

    if product_request.get("product_codes"):
        return []

    phrases = build_learning_phrase_candidates(product_request)

    if not phrases:
        return []

    ensure_product_learning_table()
    engine = get_db_engine()
    learned_rows = []
    with engine.connect() as connection:
        for index, phrase in enumerate(phrases[:4]):
            row_set = connection.execute(
                text(
                    """
                    SELECT canonical_reference, canonical_description, canonical_brand, canonical_presentation,
                           MAX(confidence) AS confidence, SUM(usage_count) AS total_hits
                    FROM public.agent_product_learning
                    WHERE normalized_phrase = :normalized_phrase
                    GROUP BY canonical_reference, canonical_description, canonical_brand, canonical_presentation
                    ORDER BY MAX(confidence) DESC, SUM(usage_count) DESC
                    LIMIT 5
                    """
                ),
                {"normalized_phrase": phrase},
            ).mappings().all()
            learned_rows.extend(row for row in row_set if is_learned_reference_relevant(product_request, row))

    ordered_references = []
    seen_references = set()
    for row in learned_rows:
        reference_value = row.get("canonical_reference")
        if reference_value and reference_value not in seen_references:
            seen_references.add(reference_value)
            ordered_references.append(reference_value)
    return ordered_references[:5]


def extract_product_codes(text_value: Optional[str]):
    normalized = normalize_text_value(text_value)
    if not normalized:
        return []

    excluded_codes = {"3en1", "p11", "t11", "p53", "1gl", "5gl"}
    codes = []
    seen_codes = set()
    for raw_code in re.findall(r"\b[a-z]?\d[a-z0-9-]{1,14}\b|\b\d{4,10}\b", normalized):
        cleaned_code = normalize_reference_value(raw_code)
        if len(cleaned_code) < 3 or cleaned_code in seen_codes or cleaned_code in excluded_codes:
            continue
        seen_codes.add(cleaned_code)
        codes.append(cleaned_code)
    return codes


def is_product_code_message(text_value: Optional[str]):
    normalized = normalize_text_value(text_value)
    if not normalized:
        return False
    if re.fullmatch(r"[a-z]?\d[a-z0-9-]{1,14}", normalized):
        return True
    return bool(re.fullmatch(r"\d{4,10}", normalized))


def extract_store_filters(text_value: Optional[str]):
    normalized = normalize_text_value(text_value)
    if not normalized:
        return []

    matched_codes = []
    seen_codes = set()
    for store_aliases in STORE_ALIASES.values():
        for alias in store_aliases:
            alias_normalized = normalize_text_value(alias)
            if not alias_normalized:
                continue
            if alias_normalized.isdigit():
                matched = bool(re.search(rf"\b{re.escape(alias_normalized)}\b", normalized))
            else:
                matched = bool(re.search(rf"\b{re.escape(alias_normalized)}\b", normalized))
            if matched:
                code = next((candidate for candidate in store_aliases if candidate.isdigit()), None)
                if code and code not in seen_codes:
                    seen_codes.add(code)
                    matched_codes.append(code)
                break
    return matched_codes


def is_store_alias_term(term_value: Optional[str]):
    normalized = normalize_text_value(term_value)
    if not normalized:
        return False
    for store_aliases in STORE_ALIASES.values():
        for alias in store_aliases:
            if normalize_text_value(alias) == normalized:
                return True
    return False


def extract_brand_filters(text_value: Optional[str]):
    normalized = normalize_text_value(text_value)
    if not normalized:
        return []

    matched_brands = []
    for brand_name, aliases in BRAND_ALIASES.items():
        for alias in aliases:
            alias_normalized = normalize_text_value(alias)
            if alias_normalized and re.search(rf"\b{re.escape(alias_normalized)}\b", normalized):
                if brand_name not in matched_brands:
                    matched_brands.append(brand_name)
                break
    return matched_brands


def extract_direction_filters(text_value: Optional[str]):
    normalized = normalize_text_value(text_value)
    if not normalized:
        return []

    matched_directions = []
    for direction_name, aliases in DIRECTION_ALIASES.items():
        for alias in aliases:
            alias_normalized = normalize_text_value(alias)
            if alias_normalized and re.search(rf"\b{re.escape(alias_normalized)}\b", normalized):
                matched_directions.append(direction_name)
                break
    return matched_directions


def infer_product_presentation_from_row(product_row: dict):
    description_value = normalize_text_value(product_row.get("descripcion") or product_row.get("nombre_articulo"))
    for size_token, unit_name in PRESENTATION_SIZE_MAP.items():
        if size_token in description_value:
            return unit_name
    return None


def extract_size_filters(text_value: Optional[str]):
    if not text_value:
        return []

    normalized_sizes = []
    seen_sizes = set()
    for raw_match in re.findall(r"\b(\d+(?:\s+\d/\d)?)(?=\s*(?:\"|pulgadas?|pulg))", text_value, flags=re.IGNORECASE):
        size_value = re.sub(r"\s+", " ", raw_match.strip())
        if size_value and size_value not in seen_sizes:
            seen_sizes.add(size_value)
            normalized_sizes.append(size_value)
    return normalized_sizes


def infer_product_size_from_row(product_row: dict):
    raw_description = str(product_row.get("descripcion") or product_row.get("nombre_articulo") or "")
    size_match = re.search(r"\b(\d+(?:/\d+)?(?:\s+\d/\d+)?)(?=\")", raw_description)
    if size_match:
        return re.sub(r"\s+", " ", size_match.group(1).strip())

    normalized_description = normalize_text_value(raw_description)
    for size_value in ["2 1/2", "1 1/2", "3 1/2", "4 1/2", "1/2"]:
        if size_value in normalized_description:
            return size_value
    standalone_match = re.search(r"\b(\d+(?:\s+\d/\d)?)\b", normalized_description)
    if standalone_match and any(keyword in normalized_description for keyword in ["brocha", "rodillo", "cerradura", "bisagra", "pasador", "portacandado"]):
        return standalone_match.group(1)
    return None


def infer_product_direction_from_row(product_row: dict):
    description_value = normalize_text_value(product_row.get("descripcion") or product_row.get("nombre_articulo"))
    for direction_name, aliases in DIRECTION_ALIASES.items():
        if any(normalize_text_value(alias) in description_value for alias in aliases):
            return direction_name
    return None


def infer_product_brand_from_row(product_row: dict):
    brand_text = normalize_text_value(product_row.get("marca") or product_row.get("marca_producto") or "")
    if re.fullmatch(r"\d+", brand_text or ""):
        brand_text = ""
    description_value = normalize_text_value(product_row.get("descripcion") or product_row.get("nombre_articulo"))
    combined_value = f"{brand_text} {description_value}".strip()
    for brand_name, aliases in BRAND_ALIASES.items():
        if any(alias and normalize_text_value(alias) in combined_value for alias in aliases):
            return brand_name
    return brand_text or None


def summarize_product_option(product_row: dict):
    reference_value = product_row.get("referencia") or product_row.get("codigo_articulo") or "sin referencia"
    description_value = product_row.get("descripcion") or product_row.get("nombre_articulo") or reference_value
    stock_value = product_row.get("stock_total") if product_row.get("stock_total") is not None else product_row.get("stock")
    presentation_value = infer_product_presentation_from_row(product_row)
    brand_value = infer_product_brand_from_row(product_row)
    department_value = product_row.get("departamentos") or product_row.get("categoria_producto")
    summary_parts = [description_value]
    if presentation_value:
        summary_parts.append(get_presentation_label(presentation_value, 1))
    if brand_value:
        summary_parts.append(str(brand_value).upper())
    if department_value and str(department_value).strip().upper() != "NULL":
        summary_parts.append(str(department_value))
    if stock_value is not None:
        summary_parts.append(f"stock {format_quantity(stock_value)}")
    return f"{reference_value}: {' | '.join(summary_parts)}"


def should_ask_product_clarification(product_request: Optional[dict], product_context: list[dict]):
    if not product_request or not product_context or product_request.get("product_codes"):
        return False

    top_candidates = product_context[:4]
    unique_references = {row.get("referencia") or row.get("codigo_articulo") for row in top_candidates if row.get("referencia") or row.get("codigo_articulo")}
    if len(unique_references) < 2:
        return False

    presentation_values = {infer_product_presentation_from_row(row) for row in top_candidates}
    brand_values = {infer_product_brand_from_row(row) for row in top_candidates}
    direction_values = {infer_product_direction_from_row(row) for row in top_candidates}
    presentation_values.discard(None)
    brand_values.discard(None)
    direction_values.discard(None)

    if not product_request.get("requested_unit") and len(presentation_values) >= 2:
        return True
    if len(brand_values) >= 2:
        return True
    if not (product_request.get("direction_filters") or []) and len(direction_values) >= 2:
        return True
    return False


def filter_rows_by_requested_presentation(product_rows: list[dict], product_request: Optional[dict]):
    if not product_request or not product_request.get("requested_unit"):
        return product_rows
    exact_rows = [row for row in product_rows if infer_product_presentation_from_row(row) == product_request.get("requested_unit")]
    return exact_rows or product_rows


def filter_rows_by_requested_size(product_rows: list[dict], product_request: Optional[dict]):
    requested_sizes = (product_request or {}).get("size_filters") or []
    if not requested_sizes:
        return product_rows
    exact_rows = [row for row in product_rows if infer_product_size_from_row(row) in requested_sizes]
    return exact_rows or product_rows


def resolve_product_clarification_choice(text_value: Optional[str], clarification_options: list[dict]):
    normalized = normalize_text_value(text_value)
    if not normalized or not clarification_options:
        return None

    ordinal_map = {
        "1": 0,
        "uno": 0,
        "primera": 0,
        "primer": 0,
        "primero": 0,
        "2": 1,
        "dos": 1,
        "segunda": 1,
        "segundo": 1,
        "3": 2,
        "tres": 2,
        "tercera": 2,
        "tercero": 2,
        "4": 3,
        "cuatro": 3,
        "cuarta": 3,
        "cuarto": 3,
    }
    if normalized in ordinal_map and ordinal_map[normalized] < len(clarification_options):
        return clarification_options[ordinal_map[normalized]]

    for option in clarification_options:
        reference_value = normalize_reference_value(option.get("referencia") or option.get("codigo_articulo"))
        if reference_value and reference_value in normalize_reference_value(normalized):
            return option
    return None


def expand_product_terms(search_terms: list[str]):
    expanded_terms = []
    seen_terms = set()

    def add_term(raw_term: Optional[str]):
        normalized_term = normalize_text_value(raw_term)
        if not normalized_term or normalized_term in seen_terms:
            return
        seen_terms.add(normalized_term)
        expanded_terms.append(normalized_term)

    for term in search_terms:
        add_term(term)
        normalized_key = normalize_reference_value(term)
        if normalized_key in PORTFOLIO_ALIASES:
            for alias_term in PORTFOLIO_ALIASES[normalized_key]:
                add_term(alias_term)

    return expanded_terms


def get_specific_product_terms(product_request: Optional[dict]):
    if not product_request:
        return []

    generic_terms = set()
    for aliases in PRESENTATION_ALIASES.values():
        generic_terms.update(normalize_text_value(alias) for alias in aliases)

    specific_terms = []
    for term in product_request.get("core_terms") or []:
        normalized_term = normalize_text_value(term)
        if not normalized_term or normalized_term in generic_terms or normalized_term in PRODUCT_STOPWORDS:
            continue
        if normalized_term not in specific_terms:
            specific_terms.append(normalized_term)
        normalized_key = normalize_reference_value(term)
        if normalized_key in PORTFOLIO_ALIASES:
            for alias_term in PORTFOLIO_ALIASES[normalized_key]:
                normalized_alias = normalize_text_value(alias_term)
                if (
                    normalized_alias
                    and normalized_alias not in generic_terms
                    and normalized_alias not in PRODUCT_STOPWORDS
                    and len(normalized_alias) >= 4
                    and normalized_alias not in specific_terms
                ):
                    specific_terms.append(normalized_alias)
    return specific_terms[:5]


def normalize_phone(phone_number: Optional[str]):
    if not phone_number:
        return None
    digits = "".join(character for character in phone_number if character.isdigit())
    if not digits:
        return None
    return digits if digits.startswith("+") else f"+{digits}"


def ensure_contact_and_conversation(phone_number: str, profile_name: Optional[str]):
    engine = get_db_engine()
    normalized_phone = normalize_phone(phone_number)
    if not normalized_phone:
        raise RuntimeError("No fue posible normalizar el teléfono recibido.")

    with engine.begin() as connection:
        contact_row = connection.execute(
            text(
                """
                INSERT INTO public.whatsapp_contacto (telefono_e164, nombre_visible, ultima_interaccion_at, updated_at)
                VALUES (:telefono_e164, :nombre_visible, now(), now())
                ON CONFLICT (telefono_e164)
                DO UPDATE SET
                    nombre_visible = COALESCE(EXCLUDED.nombre_visible, public.whatsapp_contacto.nombre_visible),
                    ultima_interaccion_at = now(),
                    updated_at = now()
                RETURNING id, cliente_id, telefono_e164, nombre_visible
                """
            ),
            {"telefono_e164": normalized_phone, "nombre_visible": profile_name},
        ).mappings().one()

        conversation_row = connection.execute(
            text(
                """
                SELECT id, cliente_id
                FROM public.agent_conversation
                WHERE contacto_id = :contacto_id AND estado IN ('abierta', 'pendiente')
                ORDER BY updated_at DESC
                LIMIT 1
                """
            ),
            {"contacto_id": contact_row["id"]},
        ).mappings().one_or_none()

        if conversation_row is None:
            conversation_row = connection.execute(
                text(
                    """
                    INSERT INTO public.agent_conversation (contacto_id, cliente_id, canal, estado, started_at, last_message_at, updated_at)
                    VALUES (:contacto_id, :cliente_id, 'whatsapp', 'abierta', now(), now(), now())
                    RETURNING id, cliente_id
                    """
                ),
                {"contacto_id": contact_row["id"], "cliente_id": contact_row["cliente_id"]},
            ).mappings().one()
        else:
            connection.execute(
                text(
                    """
                    UPDATE public.agent_conversation
                    SET last_message_at = now(), updated_at = now()
                    WHERE id = :conversation_id
                    """
                ),
                {"conversation_id": conversation_row["id"]},
            )

    return {
        "contact_id": contact_row["id"],
        "cliente_id": contact_row["cliente_id"],
        "conversation_id": conversation_row["id"],
        "telefono_e164": contact_row["telefono_e164"],
        "nombre_visible": contact_row["nombre_visible"],
    }


def store_inbound_message(
    conversation_id: int,
    provider_message_id: Optional[str],
    message_type: str,
    content: Optional[str],
    payload: dict,
):
    engine = get_db_engine()
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO public.agent_message (
                    conversation_id,
                    provider_message_id,
                    direction,
                    message_type,
                    contenido,
                    payload,
                    estado,
                    created_at
                )
                VALUES (
                    :conversation_id,
                    :provider_message_id,
                    'inbound',
                    :message_type,
                    :contenido,
                    CAST(:payload AS jsonb),
                    'recibido',
                    now()
                )
                ON CONFLICT DO NOTHING
                """
            ),
            {
                "conversation_id": conversation_id,
                "provider_message_id": provider_message_id,
                "message_type": message_type,
                "contenido": content,
                "payload": safe_json_dumps(payload),
            },
        )


def inbound_message_already_processed(provider_message_id: Optional[str]):
    if not provider_message_id:
        return False

    engine = get_db_engine()
    with engine.connect() as connection:
        row = connection.execute(
            text(
                """
                SELECT id
                FROM public.agent_message
                WHERE provider_message_id = :provider_message_id
                  AND direction = 'inbound'
                LIMIT 1
                """
            ),
            {"provider_message_id": provider_message_id},
        ).mappings().one_or_none()
    return row is not None


def store_outbound_message(
    conversation_id: int,
    provider_message_id: Optional[str],
    message_type: str,
    content: Optional[str],
    payload: dict,
    intent_detectado: Optional[str] = None,
):
    engine = get_db_engine()
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO public.agent_message (
                    conversation_id,
                    provider_message_id,
                    direction,
                    message_type,
                    intent_detectado,
                    contenido,
                    payload,
                    estado,
                    created_at
                )
                VALUES (
                    :conversation_id,
                    :provider_message_id,
                    'outbound',
                    :message_type,
                    :intent_detectado,
                    :contenido,
                    CAST(:payload AS jsonb),
                    'respondido',
                    now()
                )
                """
            ),
            {
                "conversation_id": conversation_id,
                "provider_message_id": provider_message_id,
                "message_type": message_type,
                "intent_detectado": intent_detectado,
                "contenido": content,
                "payload": safe_json_dumps(payload),
            },
        )


def load_recent_conversation_messages(conversation_id: int, limit: int = 12):
    engine = get_db_engine()
    with engine.connect() as connection:
        rows = connection.execute(
            text(
                """
                SELECT direction, message_type, contenido, created_at
                FROM public.agent_message
                WHERE conversation_id = :conversation_id
                ORDER BY created_at DESC
                LIMIT :limit
                """
            ),
            {"conversation_id": conversation_id, "limit": limit},
        ).mappings().all()
    return list(reversed(rows))


def get_conversation_snapshot(conversation_id: int):
    engine = get_db_engine()
    with engine.connect() as connection:
        row = connection.execute(
            text(
                """
                SELECT id, cliente_id, resumen, contexto
                FROM public.agent_conversation
                WHERE id = :conversation_id
                """
            ),
            {"conversation_id": conversation_id},
        ).mappings().one()
    return row


def find_cliente_contexto_by_phone(phone_number: str):
    normalized_digits = "".join(character for character in phone_number if character.isdigit())
    if normalized_digits.startswith("57"):
        normalized_digits = normalized_digits[2:]

    if not normalized_digits:
        return None

    engine = get_db_engine()
    with engine.connect() as connection:
        row = connection.execute(
            text(
                """
                SELECT cod_cliente, nombre_cliente, telefono1, telefono2, email
                FROM public.vw_estado_cartera
                WHERE regexp_replace(COALESCE(telefono1, ''), '[^0-9]', '', 'g') LIKE :phone_pattern
                   OR regexp_replace(COALESCE(telefono2, ''), '[^0-9]', '', 'g') LIKE :phone_pattern
                ORDER BY dias_vencido DESC NULLS LAST, fecha_documento DESC NULLS LAST
                LIMIT 1
                """
            ),
            {"phone_pattern": f"%{normalized_digits}"},
        ).mappings().one_or_none()

    if not row or not row["cod_cliente"]:
        return None

    try:
        return get_cliente_contexto(row["cod_cliente"])
    except HTTPException:
        return {
            "cliente_codigo": row["cod_cliente"],
            "nombre_cliente": row["nombre_cliente"],
        }


def find_cliente_contexto_by_document(document_number: str):
    normalized_document = re.sub(r"\D", "", document_number or "")
    if not normalized_document:
        return None

    engine = get_db_engine()
    with engine.connect() as connection:
        row = connection.execute(
            text(
                """
                SELECT cod_cliente, nombre_cliente, nit
                FROM public.vw_estado_cartera
                WHERE regexp_replace(COALESCE(nit, ''), '[^0-9]', '', 'g') = :document_number
                LIMIT 1
                """
            ),
            {"document_number": normalized_document},
        ).mappings().one_or_none()

        if row is None:
            row = connection.execute(
                text(
                    """
                    SELECT codigo AS cod_cliente, nombre_legal AS nombre_cliente, numero_documento AS nit
                    FROM public.cliente
                    WHERE regexp_replace(COALESCE(numero_documento, ''), '[^0-9]', '', 'g') = :document_number
                    LIMIT 1
                    """
                ),
                {"document_number": normalized_document},
            ).mappings().one_or_none()

    if not row or not row["cod_cliente"]:
        return None

    try:
        contexto = get_cliente_contexto(row["cod_cliente"])
    except HTTPException:
        contexto = {
            "cliente_codigo": row["cod_cliente"],
            "nombre_cliente": row["nombre_cliente"],
        }

    contexto["verified_document"] = normalized_document
    return contexto


def find_cliente_contexto_in_sales(customer_code: Optional[str] = None, name_value: Optional[str] = None):
    engine = get_db_engine()

    if customer_code:
        normalized_code = normalize_reference_value(customer_code)
        if not normalized_code:
            return None
        with engine.connect() as connection:
            row = connection.execute(
                text(
                    """
                    SELECT cliente_id AS cod_cliente, nombre_cliente
                    FROM public.raw_ventas_detalle
                    WHERE regexp_replace(lower(COALESCE(cliente_id, '')), '[^a-z0-9]', '', 'g') = :customer_code
                    GROUP BY 1, 2
                    ORDER BY COUNT(*) DESC, nombre_cliente ASC
                    LIMIT 1
                    """
                ),
                {"customer_code": normalized_code},
            ).mappings().one_or_none()
        if not row:
            return None
        return {
            "cliente_codigo": row["cod_cliente"],
            "nombre_cliente": row["nombre_cliente"],
            "verified_cliente_codigo": row["cod_cliente"],
            "verified_source": "raw_sales",
        }

    normalized_name = normalize_text_value(name_value)
    tokens = [token for token in normalized_name.split() if len(token) >= 3]
    if len(tokens) < 2:
        return None

    primary_pattern = f"%{tokens[0]}%"
    with engine.connect() as connection:
        rows = connection.execute(
            text(
                """
                SELECT cliente_id AS cod_cliente, nombre_cliente
                FROM public.raw_ventas_detalle
                WHERE regexp_replace(lower(COALESCE(nombre_cliente, '')), '[^a-z0-9 ]', '', 'g') ILIKE :pattern
                GROUP BY 1, 2
                ORDER BY COUNT(*) DESC, nombre_cliente ASC
                LIMIT 20
                """
            ),
            {"pattern": primary_pattern},
        ).mappings().all()

    candidates = []
    for row in rows:
        candidate_name = normalize_text_value(row.get("nombre_cliente"))
        if not candidate_name:
            continue
        token_hits = sum(1 for token in tokens if token in candidate_name)
        similarity = sequence_similarity(normalized_name, candidate_name)
        exact_phrase = 1 if normalized_name in candidate_name or candidate_name in normalized_name else 0
        if token_hits < max(2, len(tokens) - 1) and similarity < 0.82:
            continue
        candidates.append(
            {
                "cod_cliente": row["cod_cliente"],
                "nombre_cliente": row.get("nombre_cliente"),
                "score": token_hits * 2 + exact_phrase * 3 + similarity,
            }
        )

    if not candidates:
        return None

    best_match = sorted(candidates, key=lambda item: item["score"], reverse=True)[0]
    return {
        "cliente_codigo": best_match["cod_cliente"],
        "nombre_cliente": best_match.get("nombre_cliente"),
        "verified_cliente_codigo": best_match["cod_cliente"],
        "verified_source": "raw_sales",
    }


def find_cliente_contexto_by_customer_code(customer_code: str):
    normalized_code = normalize_reference_value(customer_code)
    if not normalized_code:
        return None

    engine = get_db_engine()
    with engine.connect() as connection:
        row = connection.execute(
            text(
                """
                SELECT cod_cliente, nombre_cliente, nit
                FROM public.vw_estado_cartera
                WHERE regexp_replace(lower(COALESCE(cod_cliente::text, '')), '[^a-z0-9]', '', 'g') = :customer_code
                LIMIT 1
                """
            ),
            {"customer_code": normalized_code},
        ).mappings().one_or_none()

        if row is None:
            row = connection.execute(
                text(
                    """
                    SELECT codigo AS cod_cliente, nombre_legal AS nombre_cliente, numero_documento AS nit
                    FROM public.cliente
                    WHERE regexp_replace(lower(COALESCE(codigo::text, '')), '[^a-z0-9]', '', 'g') = :customer_code
                    LIMIT 1
                    """
                ),
                {"customer_code": normalized_code},
            ).mappings().one_or_none()

    if not row or not row["cod_cliente"]:
        return find_cliente_contexto_in_sales(customer_code=normalized_code)

    try:
        contexto = get_cliente_contexto(row["cod_cliente"])
    except HTTPException:
        contexto = {
            "cliente_codigo": row["cod_cliente"],
            "nombre_cliente": row["nombre_cliente"],
        }

    contexto["verified_cliente_codigo"] = row["cod_cliente"]
    return contexto


def find_cliente_contexto_by_name(name_value: str):
    normalized_name = normalize_text_value(name_value)
    tokens = [token for token in normalized_name.split() if len(token) >= 3]
    if len(tokens) < 2:
        return None

    primary_pattern = f"%{tokens[0]}%"
    engine = get_db_engine()
    candidates = []
    with engine.connect() as connection:
        cartera_rows = connection.execute(
            text(
                """
                SELECT cod_cliente, nombre_cliente, nit
                FROM public.vw_estado_cartera
                WHERE regexp_replace(lower(COALESCE(nombre_cliente, '')), '[^a-z0-9 ]', '', 'g') ILIKE :pattern
                ORDER BY fecha_documento DESC NULLS LAST
                LIMIT 20
                """
            ),
            {"pattern": primary_pattern},
        ).mappings().all()

        client_rows = connection.execute(
            text(
                """
                SELECT codigo AS cod_cliente, nombre_legal AS nombre_cliente, numero_documento AS nit
                FROM public.cliente
                WHERE regexp_replace(lower(COALESCE(nombre_legal, '')), '[^a-z0-9 ]', '', 'g') ILIKE :pattern
                LIMIT 20
                """
            ),
            {"pattern": primary_pattern},
        ).mappings().all()

    seen_codes = set()
    for row in list(cartera_rows) + list(client_rows):
        customer_code = row.get("cod_cliente")
        if not customer_code or customer_code in seen_codes:
            continue
        seen_codes.add(customer_code)

        candidate_name = normalize_text_value(row.get("nombre_cliente"))
        if not candidate_name:
            continue

        token_hits = sum(1 for token in tokens if token in candidate_name)
        similarity = sequence_similarity(normalized_name, candidate_name)
        exact_phrase = 1 if normalized_name in candidate_name or candidate_name in normalized_name else 0
        if token_hits < max(2, len(tokens) - 1) and similarity < 0.82:
            continue

        candidates.append(
            {
                "cod_cliente": customer_code,
                "nombre_cliente": row.get("nombre_cliente"),
                "score": token_hits * 2 + exact_phrase * 3 + similarity,
            }
        )

    if not candidates:
        return find_cliente_contexto_in_sales(name_value=name_value)

    best_match = sorted(candidates, key=lambda item: item["score"], reverse=True)[0]
    try:
        contexto = get_cliente_contexto(best_match["cod_cliente"])
    except HTTPException:
        contexto = {
            "cliente_codigo": best_match["cod_cliente"],
            "nombre_cliente": best_match.get("nombre_cliente"),
        }

    contexto["verified_cliente_codigo"] = best_match["cod_cliente"]
    return contexto


def update_contact_cliente(contact_id: int, cliente_codigo: Optional[str]):
    if not cliente_codigo:
        return

    engine = get_db_engine()
    with engine.begin() as connection:
        cliente_row = connection.execute(
            text(
                """
                SELECT id
                FROM public.cliente
                WHERE codigo = :codigo
                LIMIT 1
                """
            ),
            {"codigo": cliente_codigo},
        ).mappings().one_or_none()

        if not cliente_row:
            return

        connection.execute(
            text(
                """
                UPDATE public.whatsapp_contacto
                SET cliente_id = :cliente_id, updated_at = now()
                WHERE id = :contact_id
                """
            ),
            {"cliente_id": cliente_row["id"], "contact_id": contact_id},
        )

        connection.execute(
            text(
                """
                UPDATE public.agent_conversation
                SET cliente_id = :cliente_id, updated_at = now()
                WHERE contacto_id = :contact_id AND estado IN ('abierta', 'pendiente')
                """
            ),
            {"cliente_id": cliente_row["id"], "contact_id": contact_id},
        )

    return cliente_row["id"]


def update_conversation_context(conversation_id: int, context_updates: dict, summary: Optional[str] = None):
    engine = get_db_engine()
    with engine.begin() as connection:
        existing_row = connection.execute(
            text(
                """
                SELECT contexto, resumen
                FROM public.agent_conversation
                WHERE id = :conversation_id
                """
            ),
            {"conversation_id": conversation_id},
        ).mappings().one()

        merged_context = dict(existing_row["contexto"] or {})
        merged_context.update(context_updates or {})
        connection.execute(
            text(
                """
                UPDATE public.agent_conversation
                SET resumen = :summary,
                    contexto = CAST(:context_payload AS jsonb),
                    updated_at = now(),
                    last_message_at = now()
                WHERE id = :conversation_id
                """
            ),
            {
                "summary": summary if summary is not None else existing_row["resumen"],
                "context_payload": safe_json_dumps(merged_context),
                "conversation_id": conversation_id,
            },
        )


def close_conversation(conversation_id: int, context_updates: dict, summary: Optional[str] = None):
    engine = get_db_engine()
    with engine.begin() as connection:
        existing_row = connection.execute(
            text(
                """
                SELECT contexto, resumen
                FROM public.agent_conversation
                WHERE id = :conversation_id
                """
            ),
            {"conversation_id": conversation_id},
        ).mappings().one()

        merged_context = dict(existing_row["contexto"] or {})
        merged_context.update(context_updates or {})
        merged_context["final_status"] = "gestionado"

        connection.execute(
            text(
                """
                UPDATE public.agent_conversation
                SET estado = 'cerrada',
                    resumen = :summary,
                    contexto = CAST(:context_payload AS jsonb),
                    updated_at = now(),
                    last_message_at = now()
                WHERE id = :conversation_id
                """
            ),
            {
                "summary": summary if summary is not None else existing_row["resumen"],
                "context_payload": safe_json_dumps(merged_context),
                "conversation_id": conversation_id,
            },
        )


def upsert_agent_task(conversation_id: int, cliente_id: Optional[int], task_type: str, summary: str, detail: dict, priority: str):
    engine = get_db_engine()
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO public.agent_task (
                    conversation_id,
                    cliente_id,
                    tipo_tarea,
                    prioridad,
                    estado,
                    resumen,
                    detalle,
                    created_at,
                    updated_at
                )
                VALUES (
                    :conversation_id,
                    :cliente_id,
                    :task_type,
                    :priority,
                    'pendiente',
                    :summary,
                    CAST(:detail AS jsonb),
                    now(),
                    now()
                )
                """
            ),
            {
                "conversation_id": conversation_id,
                "cliente_id": cliente_id,
                "task_type": task_type,
                "priority": priority,
                "summary": summary,
                "detail": safe_json_dumps(detail),
            },
        )


def extract_document_candidate(text_value: Optional[str]):
    if not text_value:
        return None
    matches = re.findall(r"\b\d{6,15}\b", text_value)
    return matches[0] if matches else None


def extract_identity_lookup_candidate(text_value: Optional[str], conversation_context: Optional[dict], allow_unprompted: bool = False):
    if not text_value:
        return None

    context = conversation_context or {}
    verification_flow_active = bool(
        context.get("awaiting_verification")
        or context.get("pending_intent") in {"consulta_cartera", "consulta_compras"}
    )
    if not verification_flow_active and not allow_unprompted:
        return None

    normalized_text = normalize_text_value(text_value)
    if not normalized_text:
        return None

    numeric_matches = re.findall(r"\b\d{4,15}\b", normalized_text)
    remaining_text = re.sub(r"\b\d{4,15}\b", " ", normalized_text)
    remaining_tokens = [token for token in remaining_text.split() if token]
    allowed_code_tokens = {"mi", "codigo", "cod", "cliente", "es", "el", "del", "de"}
    if numeric_matches and len(numeric_matches) == 1 and all(token in allowed_code_tokens for token in remaining_tokens):
        return {"type": "numeric_lookup", "value": numeric_matches[0]}

    if not verification_flow_active:
        return None

    if any(character.isalpha() for character in text_value):
        product_request = extract_product_request(text_value)
        tokens = [token for token in normalized_text.split() if len(token) >= 3]
        strong_product_signal = bool(
            product_request.get("product_codes")
            or product_request.get("requested_unit")
            or product_request.get("requested_quantity")
            or product_request.get("store_filters")
            or product_request.get("brand_filters")
        )
        if 2 <= len(tokens) <= 6 and not strong_product_signal:
            return {"type": "name_lookup", "value": text_value.strip()}
        if not looks_like_product_query(text_value, product_request) and 2 <= len(tokens) <= 6:
            return {"type": "name_lookup", "value": text_value.strip()}

    return None


def resolve_identity_candidate(identity_candidate: Optional[dict], phone_number: Optional[str] = None):
    if not identity_candidate:
        return None, None

    candidate_type = identity_candidate.get("type")
    candidate_value = identity_candidate.get("value")
    verified_context = None
    verified_by = None

    if candidate_type == "numeric_lookup":
        verified_context = find_cliente_contexto_by_document(candidate_value)
        if verified_context:
            verified_by = "document"
        else:
            verified_context = find_cliente_contexto_by_customer_code(candidate_value)
            if verified_context:
                verified_by = "customer_code"
    elif candidate_type == "name_lookup":
        verified_context = find_cliente_contexto_by_name(candidate_value)
        if verified_context:
            verified_by = "name"

    if not verified_context and phone_number:
        verified_context = find_cliente_contexto_by_phone(phone_number)
        if verified_context:
            verified_by = "phone"

    return verified_context, verified_by


def build_identity_not_found_reply(identity_candidate: Optional[dict]):
    candidate_value = (identity_candidate or {}).get("value") or "ese dato"
    candidate_type = (identity_candidate or {}).get("type")
    if candidate_type == "name_lookup":
        return (
            f"No pude ubicar el nombre {candidate_value} en nuestro registro. "
            "Envíame por favor tu cédula, NIT o código de cliente y con eso te valido de una vez."
        )
    return (
        f"No pude validar {candidate_value} ni como cédula/NIT ni como código de cliente. "
        "Si quieres, envíame tu nombre completo registrado y te ayudo a ubicarlo."
    )


def is_identity_verification_message(text_value: Optional[str], conversation_context: Optional[dict]):
    return extract_identity_lookup_candidate(text_value, conversation_context) is not None


def is_sensitive_intent_message(text_value: Optional[str]):
    if not text_value:
        return False
    lowered = normalize_text_value(text_value)
    sensitive_keywords = [
        "cartera",
        "saldo",
        "debo",
        "deuda",
        "cupo",
        "credito",
        "vencid",
        "factura",
        "facturas",
        "pago",
        "pagos",
        "estado de cuenta",
        "ventas",
        "compras",
        "recaudo",
    ]
    return any(keyword in lowered for keyword in sensitive_keywords) or has_keyword_or_similar(lowered, ["factura", "facturas", "vencida", "vencidas"])


def is_product_intent_message(text_value: Optional[str]):
    if not text_value:
        return False
    lowered = normalize_text_value(text_value)
    product_keywords = [
        "producto",
        "productos",
        "referencia",
        "inventario",
        "stock",
        "marca",
        "articulo",
        "precio",
        "viniltex",
        "vinilico",
        "vinilux",
        "pintulux",
        "3en1",
        "cerradura",
        "cerradur",
        "brocha",
        "rodillo",
        "bisagra",
        "pasador",
        "domestico",
        "pintuco",
        "abracol",
        "yale",
        "goya",
        "galon",
        "galones",
        "cuarto",
        "cuartos",
        "cunete",
        "cunetes",
        "cuñete",
        "cuñetes",
        "caneca",
        "canecas",
        "cubeta",
        "cubetas",
        "p-11",
        "p11",
        "t-11",
        "t11",
    ]
    has_keyword = any(keyword in lowered for keyword in product_keywords)
    quantity_format = bool(re.search(r"\b\d+(?:[.,]\d+)?\s*(galones?|galon|cuartos?|cunetes?|cuñetes?|canecas?|cubetas?)\b", lowered))
    shorthand_format = bool(re.search(r"\b\d+\s*/\s*\d+\b", lowered))
    code_with_stock = bool(re.search(r"\b\d{4,10}\b", lowered)) and any(kw in lowered for kw in ["stock", "inventario", "hay", "precio", "cuanto", "producto"])
    fuzzy_keyword = has_keyword_or_similar(lowered, ["pintulux", "cerradura", "brocha", "rodillo", "domestico", "vinilico", "viniltex", "pintulux", "goya", "p11", "t11", "mega"], threshold=0.78)
    return has_keyword or quantity_format or shorthand_format or code_with_stock or fuzzy_keyword


def is_greeting_message(text_value: Optional[str]):
    lowered = normalize_text_value(text_value)
    if not lowered:
        return False
    exact_greetings = {"hola", "buen dia", "buenos dias", "buenas tardes", "buenas noches", "hello", "hi", "hey"}
    if lowered in exact_greetings:
        return True
    greeting_candidates = ["hola", "buen dia", "buenos dias", "buenas tardes", "buenas noches", "hello", "hi", "hey"]
    if len(lowered.split()) <= 4 and max(sequence_similarity(lowered, candidate) for candidate in greeting_candidates) >= 0.82:
        return True
    tokens = lowered.split()
    if tokens and max(sequence_similarity(tokens[0], candidate) for candidate in ["hola", "hello", "hi", "hey"]) >= 0.8:
        remaining_text = " ".join(tokens[1:]).strip()
        if not remaining_text:
            return True
        if max(sequence_similarity(remaining_text, candidate) for candidate in ["buen dia", "buenos dias", "buenas tardes", "buenas noches"]) >= 0.72:
            return True
    return bool(re.match(
        r"^(hola|hey|buenas?|buenos?\s+dias?|buenas?\s+tardes?|buenas?\s+noches?)"
        r"(\s+(como estas|como esta|que tal|buen dia|buenos dias|buenas tardes|buenas noches))?"
        r"[.!?,\s]*$",
        lowered,
    ))


def is_thanks_or_closing_message(text_value: Optional[str]):
    lowered = normalize_text_value(text_value)
    if not lowered:
        return False

    gratitude_patterns = [
        r"^(gracias|muchas gracias|mil gracias|genial gracias|super gracias|perfecto gracias)[.!?,\s]*$",
        r"^(genial|perfecto|listo|excelente|super|buenisimo|buenisima)(\s+(muchas\s+)?gracias)?[.!?,\s]*$",
        r"^(ok|okay|vale|dale|entendido|comprendido)(\s+(muchas\s+)?gracias)?[.!?,\s]*$",
        r"^(quedo atento|quedo atenta|te aviso|te escribo luego|eso era|nada mas|nada mas gracias)[.!?,\s]*$",
    ]
    return any(re.match(pattern, lowered) for pattern in gratitude_patterns)


def build_conversation_closing_reply(profile_name: Optional[str]):
    nombre = profile_name or "cliente"
    return f"Con mucho gusto, {nombre}. Desde Ferreinox SAS BIC te deseamos un feliz día y aquí estamos para atenderte cuando lo necesites."


def build_technical_document_reply(profile_name: Optional[str], document_request: dict, document_options: list[dict]):
    nombre = profile_name or "cliente"
    requested_label = "hoja de seguridad" if document_request.get("wants_safety_sheet") else "ficha técnica"
    if not document_options:
        return {
            "tono": "informativo",
            "intent": "consulta_documentacion",
            "priority": "media",
            "summary": "Consulta de documentación sin coincidencia clara",
            "response_text": (
                f"Hola, {nombre}. Revisé la carpeta de {requested_label} y no encontré una coincidencia clara con ese nombre. "
                "Si quieres, dime la referencia, la línea o el nombre comercial y te muestro las opciones más cercanas."
            ),
            "document_options": [],
            "awaiting_document_choice": False,
        }

    option_lines = [f"{index}. {row['name']}" for index, row in enumerate(document_options[:4], start=1)]
    intro = f"Hola, {nombre}. Esto fue lo que encontré en {requested_label}:"
    outro = "Respóndeme con el número o con el nombre del archivo y te lo envío por WhatsApp."
    return {
        "tono": "consultivo",
        "intent": "consulta_documentacion",
        "priority": "media",
        "summary": "Consulta de documentación técnica",
        "response_text": intro + "\n" + "\n".join(option_lines) + "\n" + outro,
        "document_options": document_options[:4],
        "awaiting_document_choice": True,
    }


def detect_business_intent(text_value: Optional[str]):
    if not text_value:
        return "consulta_general"

    lowered = normalize_text_value(text_value)
    if is_technical_document_message(text_value):
        return "consulta_documentacion"
    if any(keyword in lowered for keyword in ["cartera", "saldo", "deuda", "debo", "vencid", "estado de cuenta", "cupo", "credito", "cuanto debo", "cuánto debo", "documentos"]):
        return "consulta_cartera"
    if has_keyword_or_similar(text_value, ["factura", "facturas", "vencida", "vencidas"]):
        return "consulta_cartera"
    if any(
        keyword in lowered
        for keyword in [
            "ultima compra",
            "última compra",
            "ultimo pedido",
            "último pedido",
            "compra",
            "que he comprado",
            "qué he comprado",
            "que productos compre",
            "qué productos compré",
            "que compre ese dia",
            "qué compré ese día",
            "ese pedido",
            "esa compra",
            "he comprado",
            "comprado",
            "compras",
            "historial de compras",
            "este ano",
            "este año",
            "ultimo ano",
            "ultimo año",
            "último año",
            "ultimos 12 meses",
            "últimos 12 meses",
            "ventas",
        ]
    ):
        return "consulta_compras"
    if is_product_intent_message(text_value):
        return "consulta_productos"
    return "consulta_general"


def format_currency(value):
    try:
        number = float(value or 0)
    except Exception:
        number = 0.0
    return f"${number:,.0f}".replace(",", ".")


def format_quantity(value):
    number = parse_numeric_value(value)
    if number is None:
        return str(value)
    return f"{int(number)}" if float(number).is_integer() else f"{number:g}"


def format_days(value):
    total_days = int(parse_numeric_value(value) or 0)
    return f"{total_days} día" if total_days == 1 else f"{total_days} días"


def format_stock_by_store(stock_by_store: Optional[str]):
    if not stock_by_store:
        return stock_by_store
    return re.sub(
        r":\s*(-?\d+(?:\.\d+)?)",
        lambda match: f": {format_quantity(match.group(1))}",
        str(stock_by_store),
    )


def extract_product_request(text_value: Optional[str]):
    normalized = normalize_text_value(text_value)
    if not normalized:
        return {
            "core_terms": [],
            "search_terms": [],
            "requested_quantity": None,
            "requested_unit": None,
            "quantity_expression": None,
            "product_codes": [],
            "brand_filters": [],
            "direction_filters": [],
            "size_filters": [],
            "store_filters": [],
            "original_query": "",
        }

    requested_quantity = None
    requested_unit = None
    quantity_expression = None

    quantity_match = re.search(r"(?<![a-z0-9-])(\d+(?:[.,]\d+)?)\s*(galones?|galon|cuartos?|cunetes?|cuñetes?|canecas?|cubetas?)\b", normalized)
    if quantity_match:
        requested_quantity = parse_numeric_value(quantity_match.group(1))
        raw_unit = quantity_match.group(2)
        if raw_unit in PRESENTATION_ALIASES["galon"]:
            requested_unit = "galon"
        elif raw_unit in PRESENTATION_ALIASES["cuñete"]:
            requested_unit = "cuñete"
        elif raw_unit in PRESENTATION_ALIASES["cuarto"]:
            requested_unit = "cuarto"

    quantity_match_reversed = re.search(r"\b(galones?|galon|cuartos?|cunetes?|cuñetes?|canecas?|cubetas?)\s*(\d+(?:[.,]\d+)?)\b", normalized)
    if quantity_match_reversed and requested_quantity is None:
        raw_unit = quantity_match_reversed.group(1)
        requested_quantity = parse_numeric_value(quantity_match_reversed.group(2))
        if raw_unit in PRESENTATION_ALIASES["galon"]:
            requested_unit = "galon"
        elif raw_unit in PRESENTATION_ALIASES["cuñete"]:
            requested_unit = "cuñete"
        elif raw_unit in PRESENTATION_ALIASES["cuarto"]:
            requested_unit = "cuarto"

    shorthand_match = re.search(r"\b(\d+(?:[.,]\d+)?)\s*/\s*(1|4|5)\b", normalized)
    if shorthand_match:
        quantity_expression = f"{shorthand_match.group(1)}/{shorthand_match.group(2)}"
        if requested_quantity is None:
            requested_quantity = parse_numeric_value(shorthand_match.group(1))
        if requested_unit is None:
            requested_unit = PRESENTATION_SHORTCUTS.get(shorthand_match.group(2))

    if requested_unit is None:
        for size_token, unit_name in PRESENTATION_SIZE_MAP.items():
            if re.search(rf"\b{re.escape(size_token)}\b", normalized):
                requested_unit = unit_name
                break

    tokens = [token for token in re.findall(r"[a-z0-9.-]+", normalized) if len(token) >= 2]
    search_terms = []
    for token in tokens:
        if token in PRODUCT_STOPWORDS:
            continue
        if is_store_alias_term(token):
            continue
        if re.fullmatch(r"\d+(?:[./]\d+)?", token):
            continue
        search_terms.append(token)

    if requested_unit in PRESENTATION_ALIASES:
        search_terms.extend(PRESENTATION_ALIASES[requested_unit])

    if requested_unit is None:
        for candidate_unit, aliases in PRESENTATION_ALIASES.items():
            if any(term in search_terms for term in aliases):
                requested_unit = candidate_unit
                search_terms.extend(aliases)
                break

    product_codes = extract_product_codes(text_value)
    if requested_quantity and requested_quantity >= 1000 and product_codes:
        requested_quantity = None
        quantity_expression = None

    core_terms = []
    seen_core_terms = set()
    for term in search_terms:
        normalized_term = normalize_text_value(term)
        if not normalized_term or normalized_term in seen_core_terms:
            continue
        seen_core_terms.add(normalized_term)
        core_terms.append(normalized_term)

    deduped_terms = expand_product_terms(core_terms)

    return {
        "core_terms": core_terms[:8],
        "search_terms": deduped_terms[:8],
        "requested_quantity": requested_quantity,
        "requested_unit": requested_unit,
        "quantity_expression": quantity_expression,
        "product_codes": product_codes,
        "brand_filters": extract_brand_filters(text_value),
        "direction_filters": extract_direction_filters(text_value),
        "size_filters": extract_size_filters(text_value),
        "store_filters": extract_store_filters(text_value),
        "original_query": text_value or "",
    }


def month_date_range(year: int, month: int):
    start_date = date(year, month, 1)
    if month == 12:
        end_date = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        end_date = date(year, month + 1, 1) - timedelta(days=1)
    return start_date, end_date


def extract_purchase_query(text_value: Optional[str]):
    normalized = normalize_text_value(text_value)
    today = date.today()
    result = {
        "start_date": None,
        "end_date": None,
        "label": "los ultimos 12 meses",
        "wants_last_purchase": any(keyword in normalized for keyword in ["ultima compra", "última compra", "ultimo pedido", "último pedido"]),
        "wants_products": any(keyword in normalized for keyword in ["producto", "productos", "que compre", "que productos", "qué compré", "qué productos"]),
        "has_time_filter": False,
    }

    exact_match = re.search(r"\b(\d{1,2})\s+de\s+([a-záéíóú]+)\s+de\s+(\d{4}|este ano|este año)\b", normalized)
    if exact_match:
        day_value = int(exact_match.group(1))
        month_value = MONTH_ALIASES.get(exact_match.group(2))
        year_token = exact_match.group(3)
        year_value = today.year if year_token in {"este ano", "este año"} else int(year_token)
        if month_value:
            exact_date = date(year_value, month_value, day_value)
            result.update(
                {
                    "start_date": exact_date,
                    "end_date": exact_date,
                    "label": exact_date.isoformat(),
                    "wants_products": True,
                    "has_time_filter": True,
                }
            )
            return result

    for month_name, month_value in MONTH_ALIASES.items():
        if month_name in normalized:
            year_value = today.year
            year_match = re.search(rf"{month_name}\s+de\s+(\d{{4}}|este ano|este año)", normalized)
            if year_match:
                year_token = year_match.group(1)
                year_value = today.year if year_token in {"este ano", "este año"} else int(year_token)
            start_date, end_date = month_date_range(year_value, month_value)
            result.update(
                {
                    "start_date": start_date,
                    "end_date": end_date,
                    "label": f"{month_name} de {year_value}",
                    "has_time_filter": True,
                }
            )
            return result

    return result


def extract_cartera_query(text_value: Optional[str]):
    normalized = normalize_text_value(text_value)
    return {
        "wants_overdue_only": "vencid" in normalized or has_keyword_or_similar(normalized, ["vencida", "vencidas", "vencido", "vencidos"]),
        "wants_invoice_list": any(keyword in normalized for keyword in ["cuales", "cuáles", "que facturas", "qué facturas", "documentos"]) or has_keyword_or_similar(normalized, ["factura", "facturas", "facrura", "facruras"]),
    }


def has_temporal_reference(text_value: Optional[str]):
    purchase_query = extract_purchase_query(text_value)
    return bool(purchase_query.get("has_time_filter"))


def looks_like_product_query(text_value: Optional[str], product_request: Optional[dict]):
    if is_product_intent_message(text_value):
        return True
    request = product_request or extract_product_request(text_value)
    if request.get("product_codes"):
        return True
    if request.get("brand_filters") or request.get("requested_unit") or request.get("size_filters"):
        return True
    meaningful_terms = [term for term in (request.get("core_terms") or []) if not is_store_alias_term(term)]
    return len(meaningful_terms) >= 2


def is_purchase_followup_message(text_value: Optional[str], conversation_context: Optional[dict]):
    normalized = normalize_text_value(text_value)
    if not normalized:
        return False
    if (conversation_context or {}).get("last_direct_intent") != "consulta_compras":
        return False

    followup_phrases = [
        "ese dia",
        "ese pedido",
        "esa compra",
        "esa fecha",
        "que productos compre",
        "que productos compre ese dia",
        "que compre ese dia",
        "que compre ese pedido",
        "productos compre",
        "productos comprados",
    ]
    return any(phrase in normalized for phrase in followup_phrases)


def fetch_last_year_purchase_summary(cliente_codigo: Optional[str]):
    if not cliente_codigo:
        return None

    engine = get_db_engine()
    with engine.connect() as connection:
        totals = connection.execute(
            text(
                """
                SELECT
                    COUNT(*) AS lineas,
                    COALESCE(SUM(valor_venta_neto), 0) AS valor_total,
                    COALESCE(SUM(unidades_vendidas_netas), 0) AS unidades_totales,
                    MAX(fecha_venta) AS ultima_compra
                FROM public.vw_ventas_netas
                WHERE cliente_id = :cliente_codigo
                  AND fecha_venta >= CURRENT_DATE - INTERVAL '365 days'
                """
            ),
            {"cliente_codigo": cliente_codigo},
        ).mappings().one()

        top_products = connection.execute(
            text(
                """
                SELECT nombre_articulo, codigo_articulo,
                       COALESCE(SUM(unidades_vendidas_netas), 0) AS unidades,
                       COALESCE(SUM(valor_venta_neto), 0) AS valor
                FROM public.vw_ventas_netas
                WHERE cliente_id = :cliente_codigo
                  AND fecha_venta >= CURRENT_DATE - INTERVAL '365 days'
                GROUP BY 1, 2
                ORDER BY valor DESC NULLS LAST
                LIMIT 5
                """
            ),
            {"cliente_codigo": cliente_codigo},
        ).mappings().all()

    return {"totals": dict(totals), "top_products": [dict(row) for row in top_products]}


def fetch_purchase_summary(
    cliente_codigo: Optional[str],
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
):
    if not cliente_codigo:
        return None

    if start_date and end_date:
        where_clause = "fecha_venta BETWEEN :start_date AND :end_date"
        params = {"cliente_codigo": cliente_codigo, "start_date": start_date, "end_date": end_date}
    else:
        where_clause = "fecha_venta >= CURRENT_DATE - INTERVAL '365 days'"
        params = {"cliente_codigo": cliente_codigo}

    engine = get_db_engine()
    with engine.connect() as connection:
        totals = connection.execute(
            text(
                f"""
                SELECT
                    COUNT(*) AS lineas,
                    COALESCE(SUM(valor_venta_neto), 0) AS valor_total,
                    COALESCE(SUM(unidades_vendidas_netas), 0) AS unidades_totales,
                    MIN(fecha_venta) AS primera_compra,
                    MAX(fecha_venta) AS ultima_compra
                FROM public.vw_ventas_netas
                WHERE cliente_id = :cliente_codigo
                                    AND {where_clause}
                                    AND {PURCHASE_LINE_FILTER}
                """
            ),
            params,
        ).mappings().one()

        product_rows = connection.execute(
            text(
                f"""
                SELECT
                    fecha_venta,
                    codigo_articulo,
                    nombre_articulo,
                    COALESCE(SUM(unidades_vendidas_netas), 0) AS unidades,
                    COALESCE(SUM(valor_venta_neto), 0) AS valor
                FROM public.vw_ventas_netas
                WHERE cliente_id = :cliente_codigo
                                    AND {where_clause}
                                    AND {PURCHASE_LINE_FILTER}
                GROUP BY 1, 2, 3
                ORDER BY fecha_venta DESC, valor DESC NULLS LAST
                LIMIT 12
                """
            ),
            params,
        ).mappings().all()

    return {"totals": dict(totals), "products": [dict(row) for row in product_rows]}


def fetch_latest_purchase_detail(cliente_codigo: Optional[str]):
    if not cliente_codigo:
        return None

    engine = get_db_engine()
    with engine.connect() as connection:
        latest_row = connection.execute(
            text(
                f"""
                SELECT MAX(fecha_venta) AS fecha_venta
                FROM public.vw_ventas_netas
                WHERE cliente_id = :cliente_codigo
                  AND {PURCHASE_LINE_FILTER}
                """
            ),
            {"cliente_codigo": cliente_codigo},
        ).mappings().one()

        latest_date = latest_row.get("fecha_venta")
        if not latest_date:
            return None

        totals = connection.execute(
            text(
                f"""
                SELECT
                    COUNT(*) AS lineas,
                    COALESCE(SUM(valor_venta_neto), 0) AS valor_total,
                    COALESCE(SUM(unidades_vendidas_netas), 0) AS unidades_totales
                FROM public.vw_ventas_netas
                WHERE cliente_id = :cliente_codigo
                  AND fecha_venta = :latest_date
                                    AND {PURCHASE_LINE_FILTER}
                """
            ),
            {"cliente_codigo": cliente_codigo, "latest_date": latest_date},
        ).mappings().one()

        products = connection.execute(
            text(
                f"""
                SELECT codigo_articulo, nombre_articulo,
                       COALESCE(SUM(unidades_vendidas_netas), 0) AS unidades,
                       COALESCE(SUM(valor_venta_neto), 0) AS valor
                FROM public.vw_ventas_netas
                WHERE cliente_id = :cliente_codigo
                  AND fecha_venta = :latest_date
                                    AND {PURCHASE_LINE_FILTER}
                GROUP BY 1, 2
                ORDER BY valor DESC NULLS LAST
                LIMIT 10
                """
            ),
            {"cliente_codigo": cliente_codigo, "latest_date": latest_date},
        ).mappings().all()

    return {"fecha_venta": latest_date, "totals": dict(totals), "products": [dict(row) for row in products]}


def fetch_overdue_documents(cliente_codigo: Optional[str]):
    if not cliente_codigo:
        return None

    engine = get_db_engine()
    with engine.connect() as connection:
        totals = connection.execute(
            text(
                """
                SELECT
                    COALESCE(SUM(importe_normalizado), 0) AS saldo_vencido,
                    COUNT(*) AS documentos_vencidos,
                    COALESCE(MAX(dias_vencido), 0) AS max_dias_vencido
                FROM public.vw_estado_cartera
                WHERE cod_cliente = :cliente_codigo
                  AND COALESCE(dias_vencido, 0) > 0
                  AND COALESCE(importe_normalizado, 0) > 0
                """
            ),
            {"cliente_codigo": cliente_codigo},
        ).mappings().one()

        documents = connection.execute(
            text(
                """
                SELECT numero_documento, fecha_documento, fecha_vencimiento, importe_normalizado, dias_vencido
                FROM public.vw_estado_cartera
                WHERE cod_cliente = :cliente_codigo
                  AND COALESCE(dias_vencido, 0) > 0
                  AND COALESCE(importe_normalizado, 0) > 0
                ORDER BY dias_vencido DESC NULLS LAST, fecha_vencimiento ASC NULLS LAST
                LIMIT 8
                """
            ),
            {"cliente_codigo": cliente_codigo},
        ).mappings().all()

    return {"totals": dict(totals), "documents": [dict(row) for row in documents]}


def build_direct_reply(
    intent: str,
    cliente_contexto: Optional[dict],
    product_context: list[dict],
    profile_name: Optional[str],
    product_request: Optional[dict] = None,
    user_message: Optional[str] = None,
    conversation_context: Optional[dict] = None,
):
    nombre = profile_name or "cliente"

    if intent == "consulta_cartera":
        if not cliente_contexto:
            return None
        if cliente_contexto.get("verified_source") == "raw_sales" and not any(
            cliente_contexto.get(field_name) is not None for field_name in ["saldo_cartera", "documentos_vencidos", "max_dias_vencido"]
        ):
            return {
                "tono": "informativo",
                "intent": intent,
                "priority": "media",
                "summary": f"Cliente identificado sin cartera consolidada para {cliente_contexto.get('cliente_codigo')}",
                "response_text": (
                    f"Hola, {nombre}. Ya te identifiqué como {cliente_contexto.get('nombre_cliente') or cliente_contexto.get('cliente_codigo')}, "
                    "pero en la base actual no veo cartera consolidada para ese cliente. "
                    "Si quieres, te reviso compras recientes o dejo el caso escalado a contabilidad para validarlo."
                ),
                "should_create_task": True,
                "task_type": "validacion_cartera",
                "task_summary": "Validar cliente sin cartera consolidada en CRM",
                "task_detail": cliente_contexto,
            }
        cartera_query = extract_cartera_query(user_message)
        saldo = format_currency(cliente_contexto.get("saldo_cartera"))
        dias = cliente_contexto.get("max_dias_vencido") or 0
        vencidos = cliente_contexto.get("documentos_vencidos") or 0
        vendedor = cliente_contexto.get("vendedor") or "tu asesor comercial"
        overdue_info = None
        if cartera_query.get("wants_overdue_only") or cartera_query.get("wants_invoice_list"):
            overdue_info = fetch_overdue_documents(cliente_contexto.get("cliente_codigo"))

        if overdue_info and (cartera_query.get("wants_overdue_only") or cartera_query.get("wants_invoice_list")):
            overdue_total = format_currency(overdue_info["totals"].get("saldo_vencido"))
            documents = overdue_info.get("documents") or []
            if cartera_query.get("wants_invoice_list") and documents:
                doc_lines = "; ".join(
                    f"factura {row['numero_documento']} por {format_currency(row['importe_normalizado'])}, vence {row['fecha_vencimiento']}, {format_days(row['dias_vencido'])} vencida"
                    for row in documents[:5]
                )
                response_text = (
                    f"Hola, {nombre}. Tienes {int(overdue_info['totals'].get('documentos_vencidos') or 0)} facturas vencidas por {overdue_total}. "
                    f"Estas son las principales: {doc_lines}."
                )
            else:
                response_text = (
                    f"Hola, {nombre}. Tu cartera vencida es {overdue_total}. "
                    f"Tienes {int(overdue_info['totals'].get('documentos_vencidos') or 0)} documentos vencidos y el mayor atraso es de {format_days(overdue_info['totals'].get('max_dias_vencido'))}."
                )
            return {
                "tono": "informativo",
                "intent": intent,
                "priority": "alta",
                "summary": f"Consulta de cartera vencida de {cliente_contexto.get('cliente_codigo')}",
                "response_text": response_text,
                "should_create_task": bool(int(overdue_info['totals'].get('max_dias_vencido') or 0) > 30),
                "task_type": "seguimiento_cartera",
                "task_summary": "Revisar cliente con cartera vencida",
                "task_detail": overdue_info,
            }

        return {
            "tono": "informativo",
            "intent": intent,
            "priority": "alta" if dias and int(dias) > 0 else "media",
            "summary": f"Consulta de cartera de {cliente_contexto.get('cliente_codigo')}",
            "response_text": (
                f"Hola, {nombre}. Tu saldo de cartera actual es {saldo}. "
                f"Tienes {vencidos} documentos vencidos y el mayor atraso es de {format_days(dias)}. "
                f"Tu asesor asignado es {vendedor}."
            ),
            "should_create_task": bool(dias and int(dias) > 30),
            "task_type": "seguimiento_cartera" if dias and int(dias) > 30 else "seguimiento_cliente",
            "task_summary": "Revisar cliente con cartera vencida" if dias and int(dias) > 30 else "Seguimiento a consulta de cartera",
            "task_detail": cliente_contexto,
        }

    if intent == "consulta_compras":
        if not cliente_contexto or not cliente_contexto.get("cliente_codigo"):
            return None
        purchase_query = extract_purchase_query(user_message)
        if not purchase_query.get("has_time_filter") and purchase_query.get("wants_products"):
            context_purchase_date = (conversation_context or {}).get("last_purchase_date")
            if context_purchase_date:
                purchase_query["start_date"] = context_purchase_date
                purchase_query["end_date"] = context_purchase_date
                purchase_query["label"] = str(context_purchase_date)
                purchase_query["has_time_filter"] = True
        if purchase_query.get("wants_last_purchase"):
            latest_purchase = fetch_latest_purchase_detail(cliente_contexto.get("cliente_codigo"))
            if not latest_purchase or not latest_purchase.get("fecha_venta"):
                return {
                    "tono": "informativo",
                    "intent": intent,
                    "priority": "media",
                    "summary": f"Consulta de ultima compra de {cliente_contexto.get('cliente_codigo')}",
                    "response_text": f"Hola, {nombre}. No encontré una compra registrada para este cliente.",
                    "should_create_task": False,
                    "task_type": "seguimiento_cliente",
                    "task_summary": "Consulta de ultima compra",
                    "task_detail": {},
                }

            product_summary = "; ".join(
                f"{row['nombre_articulo']} ({format_currency(row['valor'])}, {int(float(row['unidades'] or 0))} unidades)"
                for row in latest_purchase.get("products", [])[:6]
            ) or "sin detalle de productos"
            totals = latest_purchase.get("totals") or {}
            return {
                "tono": "informativo",
                "intent": intent,
                "priority": "media",
                "summary": f"Consulta de ultima compra de {cliente_contexto.get('cliente_codigo')}",
                "response_text": (
                    f"Hola, {nombre}. Tu última compra fue el {latest_purchase.get('fecha_venta')} por {format_currency(totals.get('valor_total'))}. "
                    f"Incluyó {int(totals.get('lineas') or 0)} líneas y {int(float(totals.get('unidades_totales') or 0))} unidades. "
                    f"Productos principales: {product_summary}."
                ),
                "should_create_task": False,
                "task_type": "seguimiento_cliente",
                "task_summary": "Consulta de ultima compra",
                "task_detail": latest_purchase,
            }

        purchases = fetch_purchase_summary(
            cliente_contexto.get("cliente_codigo"),
            purchase_query.get("start_date"),
            purchase_query.get("end_date"),
        )
        totals = purchases["totals"] if purchases else {}
        product_rows = purchases["products"] if purchases else []
        if not totals or not totals.get("ultima_compra"):
            response_text = f"Hola, {nombre}. No encontré compras registradas en los últimos 12 meses para este cliente."
        else:
            top_summary = "; ".join(
                f"{row['nombre_articulo']} ({format_currency(row['valor'])}, {int(float(row['unidades'] or 0))} unidades)"
                for row in product_rows[:5]
            ) or "sin productos destacados"
            if purchase_query.get("has_time_filter"):
                response_text = (
                    f"Hola, {nombre}. En {purchase_query.get('label')} compraste {format_currency(totals.get('valor_total'))}. "
                    f"Fueron {int(totals.get('lineas') or 0)} líneas y {int(float(totals.get('unidades_totales') or 0))} unidades. "
                    f"Productos principales: {top_summary}."
                )
            else:
                response_text = (
                    f"Hola, {nombre}. En los últimos 12 meses registras compras por {format_currency(totals.get('valor_total'))}. "
                    f"Acumulas {int(totals.get('lineas') or 0)} líneas y {int(float(totals.get('unidades_totales') or 0))} unidades. "
                    f"Tu última compra fue el {totals.get('ultima_compra')}. Productos destacados: {top_summary}."
                )
        return {
            "tono": "informativo",
            "intent": intent,
            "priority": "media",
            "summary": f"Consulta de compras de {purchase_query.get('label')} para {cliente_contexto.get('cliente_codigo')}",
            "response_text": response_text,
            "should_create_task": False,
            "task_type": "seguimiento_cliente",
            "task_summary": "Consulta de compras recientes",
            "task_detail": purchases or {},
        }

    if intent == "consulta_productos":
        if not product_context:
            referencia_solicitada = ", ".join((product_request or {}).get("search_terms") or [])
            return {
                "tono": "informativo",
                "intent": intent,
                "priority": "media",
                "summary": "Consulta de productos sin coincidencia exacta",
                "response_text": (
                    f"Hola, {nombre}. Revisé *{referencia_solicitada or 'esa referencia'}* y no la pude amarrar con una referencia clara en inventario. "
                    "Si quieres, dame uno de estos datos y te la ubico mejor:\n"
                    "• La referencia o código del producto\n"
                    "• La marca o línea del portafolio Ferreinox: Pintuco, Abracol, Yale o Goya\n"
                    "• La presentación (galón, cuñete, cuarto, 1/1, 1/5, 1/4)\n"
                    "• La tienda que te interesa (CEDI, Armenia, Manizales, Opalo, Pereira, Laures, Cerritos o Ferrebox)\n"
                    "Con eso te respondo más fino."
                ),
                "should_create_task": False,
                "task_type": "seguimiento_cliente",
                "task_summary": "Consulta de productos sin match exacto",
                "task_detail": {"product_request": product_request or {}},
            }

        if len(product_context) == 1:
            top_row = product_context[0]
            top_reference = top_row.get("referencia") or top_row.get("codigo_articulo") or "sin referencia"
            top_description = top_row.get("descripcion") or top_row.get("nombre_articulo") or top_reference
            top_stock = top_row.get("stock_total") if top_row.get("stock_total") is not None else top_row.get("stock")
            direct_response = f"Hola, {nombre}. Encontré esta referencia para tu consulta: {top_description} ({top_reference})."
            if top_stock is not None:
                direct_response += f" Stock total aproximado: {format_quantity(top_stock)} unidades."
            if top_row.get("stock_por_tienda"):
                direct_response += f" Disponible en: {format_stock_by_store(top_row.get('stock_por_tienda'))}."
            direct_response += " Si quieres, te ayudo a revisar otra presentación o una tienda específica."
            return {
                "tono": "informativo",
                "intent": intent,
                "priority": "media",
                "summary": "Consulta de producto con coincidencia directa",
                "response_text": direct_response,
                "should_create_task": False,
                "task_type": "seguimiento_cliente",
                "task_summary": "Consulta de producto resuelta",
                "task_detail": {"products": product_context, "product_request": product_request or {}},
            }

        if should_ask_product_clarification(product_request, product_context):
            clarification_options = []
            clarification_lines = []
            for index, row in enumerate(product_context[:4], start=1):
                option_payload = {
                    "referencia": row.get("referencia") or row.get("codigo_articulo"),
                    "descripcion": row.get("descripcion") or row.get("nombre_articulo"),
                    "marca": infer_product_brand_from_row(row),
                    "presentacion": infer_product_presentation_from_row(row),
                    "departamentos": row.get("departamentos") or row.get("categoria_producto"),
                    "stock_total": row.get("stock_total") if row.get("stock_total") is not None else row.get("stock"),
                    "stock_por_tienda": row.get("stock_por_tienda"),
                }
                clarification_options.append(option_payload)
                clarification_lines.append(f"{index}. {summarize_product_option(row)}")

            return {
                "tono": "consultivo",
                "intent": intent,
                "priority": "media",
                "summary": "Consulta de productos con necesidad de aclaracion",
                "response_text": (
                    f"Hola, {nombre}. Veo varias opciones muy cercanas. Respóndeme con el número o la referencia y te confirmo la exacta:\n"
                    + "\n".join(clarification_lines)
                    + "\nAsí te confirmo la correcta sin hacerte dar más vueltas."
                ),
                "should_create_task": False,
                "task_type": "seguimiento_cliente",
                "task_summary": "Aclaracion de producto",
                "task_detail": {
                    "product_request": product_request or {},
                    "clarification_options": clarification_options,
                },
                "awaiting_product_clarification": True,
                "clarification_options": clarification_options,
            }

        product_lines = []
        quantity_note = None
        requested_store_codes = (product_request or {}).get("store_filters") or []
        requested_store_label = STORE_CODE_LABELS.get(requested_store_codes[0]) if len(requested_store_codes) == 1 else None
        if product_request:
            requested_quantity = product_request.get("requested_quantity")
            requested_unit = product_request.get("requested_unit")
            quantity_expression = product_request.get("quantity_expression")
            if requested_quantity and requested_unit:
                quantity_note = f"Entendí una solicitud de {requested_quantity:g} {get_presentation_label(requested_unit, requested_quantity)}"
            elif quantity_expression:
                quantity_note = f"Tomé la referencia de cantidad {quantity_expression} para orientarte mejor"

        if requested_store_label and product_context:
            top_row = product_context[0]
            top_reference = top_row.get("referencia") or top_row.get("codigo_articulo") or "sin referencia"
            top_description = top_row.get("descripcion") or top_row.get("nombre_articulo") or top_reference
            top_stock = top_row.get("stock_total") if top_row.get("stock_total") is not None else top_row.get("stock")
            top_presentation = infer_product_presentation_from_row(top_row)
            store_response = (
                f"Hola, {nombre}. "
                f"Sí, en {requested_store_label} hay {format_quantity(top_stock)} unidades de {top_description} ({top_reference})"
                f"{f', presentación {get_presentation_label(top_presentation, 1)}' if top_presentation else ''}."
            )
            if quantity_note:
                store_response += f" {quantity_note}."
            store_response += " Si quieres, también te reviso otra presentación o otra tienda."
            return {
                "tono": "informativo",
                "intent": intent,
                "priority": "media",
                "summary": "Consulta de producto con tienda especifica",
                "response_text": store_response,
                "should_create_task": False,
                "task_type": "seguimiento_cliente",
                "task_summary": "Consulta de producto por tienda",
                "task_detail": {"products": product_context, "product_request": product_request or {}},
            }

        for row in product_context[:3]:
            descripcion = row.get("descripcion") or row.get("nombre_articulo") or row.get("referencia") or row.get("codigo_articulo")
            referencia = row.get("referencia") or row.get("codigo_articulo") or "sin referencia"
            stock = row.get("stock_total") if row.get("stock_total") is not None else row.get("stock")
            stock_value = parse_numeric_value(stock)
            line = f"{descripcion} ({referencia})"
            if stock is not None:
                line += f", stock total aproximado {format_quantity(stock)}"
            category_value = row.get("departamentos") or row.get("categoria_producto")
            if category_value and str(category_value).strip().upper() != "NULL":
                line += f", categoria {category_value}"
            if row.get("stock_por_tienda"):
                line += f", disponible en {format_stock_by_store(row.get('stock_por_tienda'))}"
            if product_request and product_request.get("requested_quantity") and stock_value is not None:
                requested_quantity = float(product_request["requested_quantity"])
                availability = "si alcanza" if stock_value >= requested_quantity else "stock insuficiente"
                line += f", para {requested_quantity:g} unidades {availability}"
            product_lines.append(line)
        return {
            "tono": "informativo",
            "intent": intent,
            "priority": "media",
            "summary": "Consulta de productos",
            "response_text": (
                f"Hola, {nombre}. "
                f"{quantity_note + '. ' if quantity_note else ''}"
                f"Te encontré estas opciones relacionadas: {'; '.join(product_lines)}. "
                "Si quieres, te cierro la búsqueda con la más probable o te reviso una tienda puntual."
            ),
            "should_create_task": False,
            "task_type": "seguimiento_cliente",
            "task_summary": "Consulta de productos",
            "task_detail": {"products": product_context, "product_request": product_request or {}},
        }

    return None


def build_verification_success_reply(profile_name: Optional[str], cliente_contexto: Optional[dict]):
    nombre = profile_name or "cliente"
    cliente_codigo = (cliente_contexto or {}).get("cliente_codigo")
    cliente_nombre = (cliente_contexto or {}).get("nombre_cliente")
    return (
        f"Perfecto, {nombre}. Tu identidad quedó validada"
        f"{' para el cliente ' + str(cliente_nombre or cliente_codigo) if (cliente_nombre or cliente_codigo) else ''}"
        f"{' (' + str(cliente_codigo) + ')' if cliente_nombre and cliente_codigo else ''}. "
        "Ahora ya puedo ayudarte con cartera, compras del último año y consultas relacionadas con tu historial comercial."
    )


def fetch_products_from_catalog(connection, where_clause: str, params: dict, match_score_sql: str, limit: int = 25):
    return connection.execute(
        text(
            f"""
            SELECT producto_codigo, referencia, descripcion, marca, departamentos, stock_total, costo_promedio_und, stock_por_tienda,
                   ({match_score_sql}) AS match_score
            FROM public.productos
            WHERE {where_clause}
            ORDER BY match_score DESC, stock_total DESC NULLS LAST, descripcion ASC NULLS LAST
            LIMIT {int(limit)}
            """
        ),
        params,
    ).mappings().all()


def fetch_products_from_store_inventory(connection, where_clause: str, params: dict, match_score_sql: str, limit: int = 25):
    return connection.execute(
        text(
            f"""
            SELECT referencia, descripcion, marca, departamentos, stock_total, costo_promedio_und, stock_por_tienda,
                   ({match_score_sql}) AS match_score
            FROM (
                SELECT
                    referencia,
                    descripcion,
                    marca,
                    STRING_AGG(DISTINCT departamento, ', ' ORDER BY departamento) AS departamentos,
                    COALESCE(SUM(stock_disponible), 0) AS stock_total,
                    AVG(costo_promedio_und) AS costo_promedio_und,
                    STRING_AGG(
                        almacen_nombre || ': ' || COALESCE(stock_disponible::text, '0'),
                        '; '
                        ORDER BY almacen_nombre
                    ) FILTER (WHERE COALESCE(stock_disponible, 0) > 0) AS stock_por_tienda,
                    MAX(search_blob) AS search_blob,
                    public.fn_keep_alnum(
                        COALESCE(MAX(descripcion), '') || ' ' ||
                        COALESCE(MAX(referencia), '') || ' ' ||
                        COALESCE(MAX(marca), '')
                    ) AS search_compact,
                    MAX(referencia_normalizada) AS referencia_normalizada
                FROM public.vw_inventario_agente
                WHERE {where_clause}
                GROUP BY referencia, descripcion, marca
            ) inventory
            ORDER BY match_score DESC, stock_total DESC NULLS LAST, descripcion ASC NULLS LAST
            LIMIT {int(limit)}
            """
        ),
        params,
    ).mappings().all()


def fetch_reference_product_rows(connection, references: list[str], store_filters: list[str], match_score: int):
    if not references:
        return []

    params = {}
    catalog_reference_filters = []
    inventory_reference_filters = []
    for index, reference_value in enumerate(references[:5]):
        params[f"reference_{index}"] = normalize_reference_value(reference_value)
        catalog_reference_filters.append(f"producto_codigo = :reference_{index}")
        inventory_reference_filters.append(f"referencia_normalizada = :reference_{index}")

    if store_filters:
        store_filters_sql = []
        for store_index, store_code in enumerate(store_filters):
            params[f"store_{store_index}"] = store_code
            store_filters_sql.append(f"cod_almacen = :store_{store_index}")
        return fetch_products_from_store_inventory(
            connection,
            f"({' OR '.join(inventory_reference_filters)}) AND ({' OR '.join(store_filters_sql)})",
            params,
            str(match_score),
            limit=5,
        )

    return fetch_products_from_catalog(
        connection,
        f"({' OR '.join(catalog_reference_filters)})",
        params,
        str(match_score),
        limit=5,
    )


def fetch_code_product_rows(connection, product_codes: list[str], store_filters: list[str]):
    if not product_codes:
        return []

    params = {}
    code_filters = []
    score_terms = []
    for index, code in enumerate(product_codes[:3]):
        params[f"code_like_{index}"] = f"%{code}%"
        params[f"code_compact_{index}"] = f"%{normalize_reference_value(code)}%"
        code_filters.append(f"producto_codigo LIKE :code_like_{index}")
        code_filters.append(f"search_blob ILIKE :code_like_{index}")
        code_filters.append(f"search_compact LIKE :code_compact_{index}")
        score_terms.append(
            f"CASE WHEN producto_codigo LIKE :code_like_{index} OR search_blob ILIKE :code_like_{index} OR search_compact LIKE :code_compact_{index} THEN 1 ELSE 0 END"
        )

    if store_filters:
        store_code_filters = []
        store_score_terms = []
        for index, code in enumerate(product_codes[:3]):
            store_code_filters.append(f"referencia_normalizada LIKE :code_like_{index}")
            store_code_filters.append(f"search_blob ILIKE :code_like_{index}")
            store_score_terms.append(
                f"CASE WHEN referencia_normalizada LIKE :code_like_{index} OR search_blob ILIKE :code_like_{index} THEN 1 ELSE 0 END"
            )
        store_filters_sql = []
        for store_index, store_code in enumerate(store_filters):
            params[f"store_{store_index}"] = store_code
            store_filters_sql.append(f"cod_almacen = :store_{store_index}")
        return fetch_products_from_store_inventory(
            connection,
            f"({' OR '.join(store_code_filters)}) AND ({' OR '.join(store_filters_sql)})",
            params,
            " + ".join(store_score_terms) if store_score_terms else "0",
            limit=5,
        )

    where_clause = f"({' OR '.join(code_filters)})"
    match_score_sql = " + ".join(score_terms) if score_terms else "0"
    return fetch_products_from_catalog(connection, where_clause, params, match_score_sql, limit=5)


def fetch_term_product_rows(connection, query_terms: list[str], store_filters: list[str]):
    if not query_terms:
        return []

    params = {}
    search_filters = []
    score_terms = []
    for index, term in enumerate(query_terms[:5]):
        params[f"pattern_{index}"] = f"%{term}%"
        compact_term = normalize_reference_value(term)
        params[f"compact_{index}"] = f"%{compact_term}%"
        search_filters.append(f"search_blob ILIKE :pattern_{index}")
        if compact_term:
            search_filters.append(f"search_compact LIKE :compact_{index}")
        score_terms.append(
            f"CASE WHEN search_blob ILIKE :pattern_{index} OR search_compact LIKE :compact_{index} THEN 1 ELSE 0 END"
        )

    if store_filters:
        store_search_filters = []
        store_score_terms = []
        for index, term in enumerate(query_terms[:5]):
            store_search_filters.append(f"search_blob ILIKE :pattern_{index}")
            store_score_terms.append(f"CASE WHEN search_blob ILIKE :pattern_{index} THEN 1 ELSE 0 END")
        store_filters_sql = []
        for store_index, store_code in enumerate(store_filters):
            params[f"store_{store_index}"] = store_code
            store_filters_sql.append(f"cod_almacen = :store_{store_index}")
        return fetch_products_from_store_inventory(
            connection,
            f"({' OR '.join(store_search_filters)}) AND ({' OR '.join(store_filters_sql)})",
            params,
            " + ".join(store_score_terms) if store_score_terms else "0",
            limit=25,
        )

    where_clause = f"({' OR '.join(search_filters)})"
    match_score_sql = " + ".join(score_terms) if score_terms else "0"
    return fetch_products_from_catalog(connection, where_clause, params, match_score_sql, limit=25)


def lookup_product_context(text_value: Optional[str], product_request: Optional[dict] = None):
    product_request = product_request or extract_product_request(text_value)
    core_terms = product_request.get("core_terms") or []
    terms = product_request.get("search_terms") or []
    product_codes = product_request.get("product_codes") or []
    learned_references = fetch_learned_product_references(product_request)
    store_filters = product_request.get("store_filters") or []
    brand_filters = product_request.get("brand_filters") or []
    normalized_query = normalize_text_value(text_value)

    if not terms and not product_codes and not learned_references:
        return []

    try:
        engine = get_db_engine()
        with engine.connect() as connection:
            if learned_references:
                learned_rows = fetch_reference_product_rows(connection, learned_references, store_filters, 90)
                if learned_rows:
                    return filter_rows_by_requested_presentation([dict(row) for row in learned_rows], product_request)

            if product_codes:
                code_rows = fetch_code_product_rows(connection, product_codes, store_filters)
                if code_rows:
                    return filter_rows_by_requested_presentation([dict(row) for row in code_rows], product_request)

            if not terms:
                return []

            query_terms = []
            for term in list(core_terms) + list(terms):
                if term not in query_terms:
                    query_terms.append(term)
                if len(query_terms) == 5:
                    break
            rows = fetch_term_product_rows(connection, query_terms, store_filters)

            if rows:
                ranked_rows = []
                primary_term = normalize_reference_value(core_terms[0]) if core_terms else ""
                preferred_family_terms = expand_product_terms([primary_term]) if primary_term else []
                specific_terms = get_specific_product_terms(product_request)
                for row in rows:
                    candidate = dict(row)
                    candidate_text = " ".join(
                        value
                        for value in [candidate.get("descripcion"), candidate.get("referencia"), candidate.get("marca")]
                        if value
                    )
                    normalized_candidate_text = normalize_text_value(candidate_text)
                    candidate_presentation = infer_product_presentation_from_row(candidate)
                    candidate_brand = infer_product_brand_from_row(candidate)
                    candidate_size = infer_product_size_from_row(candidate)
                    candidate_direction = infer_product_direction_from_row(candidate)
                    candidate["fuzzy_score"] = round(sequence_similarity(normalized_query, candidate_text), 4)
                    candidate["family_score"] = 1 if any(term and term in normalized_candidate_text for term in preferred_family_terms[:5]) else 0
                    candidate["specific_score"] = sum(1 for term in specific_terms if term and term in normalized_candidate_text)
                    candidate["presentation_score"] = 1 if product_request.get("requested_unit") and candidate_presentation == product_request.get("requested_unit") else 0
                    candidate["brand_score"] = 1 if brand_filters and candidate_brand in brand_filters else 0
                    candidate["size_score"] = 1 if (product_request.get("size_filters") or []) and candidate_size in (product_request.get("size_filters") or []) else 0
                    candidate["direction_score"] = 1 if (product_request.get("direction_filters") or []) and candidate_direction in (product_request.get("direction_filters") or []) else 0
                    ranked_rows.append(candidate)
                ranked_rows.sort(
                    key=lambda item: (
                        item.get("direction_score") or 0,
                        item.get("size_score") or 0,
                        item.get("presentation_score") or 0,
                        item.get("brand_score") or 0,
                        item.get("specific_score") or 0,
                        item.get("family_score") or 0,
                        item.get("match_score") or 0,
                        item.get("fuzzy_score") or 0,
                        parse_numeric_value(item.get("stock_total")) or 0,
                    ),
                    reverse=True,
                )
                top_specific_score = ranked_rows[0].get("specific_score") or 0 if ranked_rows else 0
                if top_specific_score > 0:
                    ranked_rows = [item for item in ranked_rows if (item.get("specific_score") or 0) > 0]
                top_match_score = ranked_rows[0].get("match_score") or 0 if ranked_rows else 0
                if top_match_score >= 2:
                    ranked_rows = [
                        item for item in ranked_rows
                        if (item.get("match_score") or 0) >= max(2, top_match_score - 1)
                        or (item.get("size_score") or 0) > 0
                        or (item.get("brand_score") or 0) > 0
                        or (item.get("family_score") or 0) > 0
                    ]
                if product_request.get("requested_unit"):
                    exact_presentation_rows = [
                        item for item in ranked_rows
                        if infer_product_presentation_from_row(item) == product_request.get("requested_unit")
                    ]
                    if exact_presentation_rows:
                        ranked_rows = exact_presentation_rows
                ranked_rows = filter_rows_by_requested_size(ranked_rows, product_request)
                if any((parse_numeric_value(item.get("stock_total")) or 0) > 0 for item in ranked_rows):
                    ranked_rows = [item for item in ranked_rows if (parse_numeric_value(item.get("stock_total")) or 0) > 0]
                return ranked_rows[:5]

            sales_filters = []
            sales_scores = []
            sales_params = {}
            for index, term in enumerate(query_terms):
                sales_params[f"pattern_{index}"] = f"%{term}%"
                sales_filters.append(f"search_blob ILIKE :pattern_{index}")
                sales_scores.append(f"CASE WHEN search_blob ILIKE :pattern_{index} THEN 1 ELSE 0 END")

            sales_rows = connection.execute(
                text(
                    f"""
                    SELECT codigo_articulo, nombre_articulo, marca_producto, categoria_producto,
                           SUM(unidades_vendidas_netas) AS unidades_vendidas,
                           SUM(valor_venta_neto) AS valor_vendido,
                           MAX(match_score) AS match_score
                    FROM (
                        SELECT
                            codigo_articulo,
                            nombre_articulo,
                            marca_producto,
                            categoria_producto,
                            unidades_vendidas_netas,
                            valor_venta_neto,
                            ({' + '.join(sales_scores)}) AS match_score,
                            translate(lower(
                                COALESCE(nombre_articulo, '') || ' ' ||
                                COALESCE(codigo_articulo, '') || ' ' ||
                                COALESCE(marca_producto, '') || ' ' ||
                                COALESCE(categoria_producto, '')
                            ), 'áéíóúàèìòùâêîôûäëïöüñ', 'aeiouaeiouaeiouaeioun') AS search_blob
                        FROM public.vw_ventas_netas
                    ) sales
                    WHERE {' OR '.join(sales_filters)}
                    GROUP BY 1, 2, 3, 4
                    ORDER BY match_score DESC, valor_vendido DESC NULLS LAST
                    LIMIT 5
                    """
                ),
                sales_params,
            ).mappings().all()

            return [dict(row) for row in sales_rows]
    except Exception:
        return []


def build_verification_challenge():
    return (
        "Para revisar cartera, ventas u otra informacion sensible necesito validar tu identidad. "
        "Por favor enviame tu cedula, NIT o codigo de cliente. Si prefieres, tambien puedes escribirme el nombre registrado."
    )


def build_agent_prompt(
    profile_name: Optional[str],
    cliente_contexto: Optional[dict],
    recent_messages: list[dict],
    user_message: str,
    verification_state: dict,
    product_context: list[dict],
):
    nombre = profile_name or "cliente"
    contexto_cliente = safe_json_dumps(cliente_contexto or {})
    historial = json.dumps(
        [
            {
                "direction": row["direction"],
                "message_type": row["message_type"],
                "content": row["contenido"],
            }
            for row in recent_messages
            if row.get("contenido")
        ],
        ensure_ascii=False,
    )
    verification_json = safe_json_dumps(verification_state or {})
    product_json = safe_json_dumps(product_context or [])

    return [
        {
            "role": "system",
            "content": (
                "Eres el agente de servicio al cliente de Ferreinox. Responde en espanol claro, util y profesional. "
                "Debes detectar tono del cliente, intencion principal y prioridad. Usa el contexto ERP disponible para responder con precision. "
                "El portafolio comercial valido para orientar respuestas incluye principalmente Pintuco, Abracol, Yale, Goya y las categorias reales del ERP. "
                "No inventes marcas fuera del portafolio y no sugieras Corona como marca comercial de Ferreinox. "
                "Interpreta lenguaje ferretero y comercial como: 18.93 = cuñete, 3.79 = galon, 0.95 = cuarto, 1/1 = galon, 1/5 = cuñete, 1/4 = cuarto, 5/1 = cinco galones. "
                "Nunca reveles cartera, saldos, ventas historicas o datos privados si verification_state.verified es falso. En ese caso pide cedula, NIT, codigo de cliente o nombre registrado. "
                "Si no tienes un dato seguro, dilo claramente y ofrece el siguiente paso. Nunca inventes saldos, fechas o datos comerciales. "
                "Devuelve JSON valido con estas claves exactas: tono, intent, priority, summary, response_text, should_create_task, task_type, task_summary, task_detail."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Nombre visible del contacto: {nombre}\n"
                f"Estado de verificacion: {verification_json}\n"
                f"Contexto ERP del posible cliente: {contexto_cliente}\n"
                f"Contexto de productos: {product_json}\n"
                f"Historial reciente: {historial}\n"
                f"Mensaje actual del cliente: {user_message}"
            ),
        },
    ]


def normalize_agent_result(agent_result: dict, user_message: str):
    return {
        "tono": agent_result.get("tono") or "neutral",
        "intent": agent_result.get("intent") or "consulta_general",
        "priority": agent_result.get("priority") or "media",
        "summary": agent_result.get("summary") or user_message[:200],
        "response_text": agent_result.get("response_text") or "Gracias por escribirnos. Ya estamos revisando tu mensaje.",
        "should_create_task": bool(agent_result.get("should_create_task")),
        "task_type": agent_result.get("task_type") or "seguimiento_cliente",
        "task_summary": agent_result.get("task_summary") or "Revisar conversacion de WhatsApp",
        "task_detail": agent_result.get("task_detail") or {"mensaje": user_message},
    }


def extract_json_object(raw_text: str):
    if not raw_text:
        raise ValueError("La respuesta del modelo llegó vacía.")

    raw_text = raw_text.strip()
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        start = raw_text.find("{")
        end = raw_text.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(raw_text[start : end + 1])
        raise


def generate_agent_reply(
    profile_name: Optional[str],
    cliente_contexto: Optional[dict],
    recent_messages: list[dict],
    user_message: str,
    verification_state: dict,
    product_context: list[dict],
):
    client = get_openai_client()
    response = client.responses.create(
        model=get_openai_model(),
        input=build_agent_prompt(profile_name, cliente_contexto, recent_messages, user_message, verification_state, product_context),
        temperature=0.3,
        text={"format": {"type": "json_object"}},
    )
    content = response.output_text
    parsed = extract_json_object(content)
    return normalize_agent_result(parsed, user_message)


def build_fallback_agent_result(user_message: str, error_message: str):
    return {
        "tono": "neutral",
        "intent": "consulta_general",
        "priority": "media",
        "summary": user_message[:200] if user_message else "Consulta entrante",
        "response_text": "Gracias por escribirnos. Recibimos tu mensaje y un asesor lo revisará en breve.",
        "should_create_task": True,
        "task_type": "revision_manual",
        "task_summary": "Revisar conversacion con falla en respuesta automatica",
        "task_detail": {"mensaje": user_message, "error": error_message},
    }


def send_whatsapp_text_message(to_phone: str, body: str):
    response = requests.post(
        f"https://graph.facebook.com/v22.0/{get_whatsapp_phone_number_id()}/messages",
        headers={
            "Authorization": f"Bearer {get_whatsapp_access_token()}",
            "Content-Type": "application/json",
        },
        json={
            "messaging_product": "whatsapp",
            "to": to_phone.lstrip("+"),
            "type": "text",
            "text": {"preview_url": False, "body": body},
        },
        timeout=20,
    )
    if response.status_code >= 400:
        try:
            error_payload = response.json()
        except Exception:
            error_payload = {"raw": response.text}
        raise RuntimeError(
            f"WhatsApp Cloud API devolvió {response.status_code}: {safe_json_dumps(error_payload)}"
        )
    return response.json()


def send_whatsapp_document_message(to_phone: str, document_link: str, filename: str, caption: Optional[str] = None):
    payload = {
        "messaging_product": "whatsapp",
        "to": to_phone.lstrip("+"),
        "type": "document",
        "document": {
            "link": document_link,
            "filename": filename,
        },
    }
    if caption:
        payload["document"]["caption"] = caption

    response = requests.post(
        f"https://graph.facebook.com/v22.0/{get_whatsapp_phone_number_id()}/messages",
        headers={
            "Authorization": f"Bearer {get_whatsapp_access_token()}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=30,
    )
    if response.status_code >= 400:
        try:
            error_payload = response.json()
        except Exception:
            error_payload = {"raw": response.text}
        raise RuntimeError(
            f"WhatsApp Cloud API devolvió {response.status_code}: {safe_json_dumps(error_payload)}"
        )
    return response.json()


@app.get("/")
def read_root():
    return {
        "estado": "Sistema CRM Ferreinox Activo",
        "version": "2026.2",
        "postgrest_url": get_postgrest_url(),
        "endpoints": [
            "/health",
            "/agent/clientes/{cliente_codigo}/contexto",
            "/webhooks/whatsapp",
        ],
    }


@app.get("/health")
def health_check():
    postgrest_url = get_postgrest_url()
    try:
        response = requests.get(f"{postgrest_url}/", timeout=5)
        response.raise_for_status()
        return {"backend": "ok", "postgrest": "ok", "postgrest_url": postgrest_url}
    except Exception as exc:
        return {"backend": "ok", "postgrest": "error", "postgrest_url": postgrest_url, "detail": str(exc)}


@app.get("/agent/clientes/{cliente_codigo}/contexto")
def get_cliente_contexto(cliente_codigo: str):
    postgrest_url = get_postgrest_url()
    try:
        response = requests.get(
            f"{postgrest_url}/vw_cliente_contexto_agente",
            params={"cliente_codigo": f"eq.{cliente_codigo}", "select": "*", "limit": 1},
            timeout=10,
        )
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"No fue posible consultar PostgREST: {exc}") from exc

    if not payload:
        raise HTTPException(status_code=404, detail=f"No se encontró contexto para el cliente {cliente_codigo}")

    return payload[0]


@app.get("/webhooks/whatsapp")
def verify_whatsapp_webhook(
    hub_mode: str = Query(alias="hub.mode"),
    hub_verify_token: str = Query(alias="hub.verify_token"),
    hub_challenge: str = Query(alias="hub.challenge"),
):
    if hub_mode == "subscribe" and hub_verify_token == get_whatsapp_verify_token():
        return int(hub_challenge)
    raise HTTPException(status_code=403, detail="Token de verificación inválido")


@app.post("/webhooks/whatsapp")
async def receive_whatsapp_webhook(request: Request):
    payload = await request.json()
    processed_messages = []

    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            contacts = value.get("contacts", [])
            messages = value.get("messages", [])

            profile_name = None
            wa_id = None
            if contacts:
                contact = contacts[0]
                profile_name = contact.get("profile", {}).get("name")
                wa_id = contact.get("wa_id")

            for message in messages:
                from_number = message.get("from") or wa_id
                context = ensure_contact_and_conversation(from_number, profile_name)
                message_type = message.get("type", "text")
                if inbound_message_already_processed(message.get("id")):
                    processed_messages.append(
                        {
                            "conversation_id": context["conversation_id"],
                            "telefono": context["telefono_e164"],
                            "message_type": message_type,
                            "provider_message_id": message.get("id"),
                            "duplicate_skipped": True,
                        }
                    )
                    continue

                content = None
                if message_type == "text":
                    content = message.get("text", {}).get("body")
                elif message_type == "button":
                    content = message.get("button", {}).get("text")
                elif message_type == "interactive":
                    content = __import__("json").dumps(message.get("interactive", {}), ensure_ascii=False)

                store_inbound_message(
                    context["conversation_id"],
                    message.get("id"),
                    message_type,
                    content,
                    message,
                )

                recent_messages = load_recent_conversation_messages(context["conversation_id"])
                conversation_snapshot = get_conversation_snapshot(context["conversation_id"])
                conversation_context = dict(conversation_snapshot.get("contexto") or {})
                verified_context = None
                detected_intent = detect_business_intent(content)
                identity_candidate = extract_identity_lookup_candidate(
                    content,
                    conversation_context,
                    allow_unprompted=detected_intent != "consulta_productos",
                )
                identity_verification_message = identity_candidate is not None
                if identity_verification_message:
                    detected_intent = conversation_context.get("pending_intent") or detected_intent
                if detected_intent == "consulta_general" and is_product_code_message(content):
                    previous_product_request = conversation_context.get("last_product_request") or {}
                    if conversation_context.get("last_direct_intent") == "consulta_productos" or previous_product_request.get("search_terms"):
                        detected_intent = "consulta_productos"
                if detected_intent in {"consulta_general", "consulta_productos"} and is_purchase_followup_message(content, conversation_context):
                    detected_intent = "consulta_compras"
                if detected_intent == "consulta_general" and has_temporal_reference(content):
                    previous_intent = conversation_context.get("last_direct_intent") or conversation_context.get("intent")
                    if previous_intent in {"consulta_compras", "consulta_cartera"}:
                        detected_intent = previous_intent
                product_request = extract_product_request(content)
                if detected_intent == "consulta_general" and looks_like_product_query(content, product_request):
                    detected_intent = "consulta_productos"
                pending_product_clarification = conversation_context.get("pending_product_clarification") or []
                pending_document_options = conversation_context.get("pending_document_options") or []
                selected_document_option = None
                if pending_product_clarification:
                    selected_option = resolve_product_clarification_choice(content, pending_product_clarification)
                    if selected_option:
                        detected_intent = "consulta_productos"
                        merged_core_terms = list((conversation_context.get("last_product_request") or {}).get("core_terms") or [])
                        merged_terms = list((conversation_context.get("last_product_request") or {}).get("search_terms") or [])
                        merged_codes = list(product_request.get("product_codes") or [])
                        selected_reference = selected_option.get("referencia") or selected_option.get("codigo_articulo")
                        if selected_reference and normalize_reference_value(selected_reference) not in merged_codes:
                            merged_codes.append(normalize_reference_value(selected_reference))
                        product_request["core_terms"] = merged_core_terms[:8]
                        product_request["search_terms"] = expand_product_terms(merged_terms or merged_core_terms)[:8]
                        product_request["product_codes"] = merged_codes[:4]
                if pending_document_options and conversation_context.get("last_direct_intent") == "consulta_documentacion":
                    selected_document_option = resolve_technical_document_choice(content, pending_document_options)
                    if selected_document_option:
                        detected_intent = "consulta_documentacion"
                    else:
                        pending_document_request = extract_technical_document_request(content, product_request, conversation_context)
                        if pending_document_request.get("terms"):
                            detected_intent = "consulta_documentacion"
                if detected_intent == "consulta_productos" and is_product_code_message(content):
                    previous_product_request = conversation_context.get("last_product_request") or {}
                    merged_core_terms = list(previous_product_request.get("core_terms") or [])
                    merged_terms = list(previous_product_request.get("search_terms") or [])
                    merged_codes = list(previous_product_request.get("product_codes") or [])
                    for term in product_request.get("core_terms") or []:
                        if term not in merged_core_terms:
                            merged_core_terms.append(term)
                    for term in product_request.get("search_terms") or []:
                        if term not in merged_terms:
                            merged_terms.append(term)
                    for code in product_request.get("product_codes") or []:
                        if code not in merged_codes:
                            merged_codes.append(code)
                    product_request["core_terms"] = merged_core_terms[:8]
                    product_request["search_terms"] = expand_product_terms(merged_terms)[:8]
                    product_request["product_codes"] = merged_codes[:4]

                if identity_candidate:
                    try:
                        verified_context, verified_by = resolve_identity_candidate(identity_candidate, context["telefono_e164"])
                    except Exception:
                        verified_context, verified_by = None, None
                    if verified_context:
                        cliente_id = update_contact_cliente(context["contact_id"], verified_context.get("cliente_codigo"))
                        context["cliente_id"] = cliente_id
                        update_conversation_context(
                            context["conversation_id"],
                            {
                                "verified": True,
                                "verified_document": identity_candidate.get("value") if verified_by == "document" else None,
                                "verified_by": verified_by,
                                "verified_cliente_codigo": verified_context.get("cliente_codigo"),
                            },
                        )
                        conversation_context.update(
                            {
                                "verified": True,
                                "verified_document": identity_candidate.get("value") if verified_by == "document" else None,
                                "verified_by": verified_by,
                                "verified_cliente_codigo": verified_context.get("cliente_codigo"),
                                "awaiting_verification": False,
                            }
                        )
                    else:
                        invalid_identity_text = (
                            build_identity_not_found_reply(identity_candidate)
                            + " Mientras tanto, puedo ayudarte con inventario, productos y documentación técnica."
                        )
                        outbound_payload = None
                        try:
                            outbound_payload = send_whatsapp_text_message(context["telefono_e164"], invalid_identity_text)
                            provider_message_id = None
                            if outbound_payload.get("messages"):
                                provider_message_id = outbound_payload["messages"][0].get("id")
                            store_outbound_message(
                                context["conversation_id"],
                                provider_message_id,
                                "text",
                                invalid_identity_text,
                                outbound_payload,
                                intent_detectado="identidad_no_validada",
                            )
                        except Exception as exc:
                            store_outbound_message(
                                context["conversation_id"],
                                None,
                                "system",
                                f"No fue posible enviar respuesta de identidad no validada: {exc}",
                                {"error": str(exc), "response_text": invalid_identity_text},
                                intent_detectado="identidad_no_validada",
                            )
                        processed_messages.append(
                            {
                                "conversation_id": context["conversation_id"],
                                "telefono": context["telefono_e164"],
                                "message_type": message_type,
                                "provider_message_id": message.get("id"),
                                "ai_response_sent": bool(outbound_payload),
                                "verification_required": True,
                            }
                        )
                        continue

                cliente_contexto = verified_context
                if cliente_contexto is None:
                    verified_cliente_codigo = conversation_context.get("verified_cliente_codigo")
                    if verified_cliente_codigo:
                        try:
                            cliente_contexto = get_cliente_contexto(verified_cliente_codigo)
                        except HTTPException:
                            cliente_contexto = None

                if cliente_contexto is None:
                    cliente_contexto = find_cliente_contexto_by_phone(context["telefono_e164"])

                if cliente_contexto:
                    cliente_id = update_contact_cliente(context["contact_id"], cliente_contexto.get("cliente_codigo"))
                    context["cliente_id"] = cliente_id

                sensitive_request = is_sensitive_intent_message(content)
                verified_cliente_codigo = conversation_context.get("verified_cliente_codigo")
                if not verified_cliente_codigo and verified_context:
                    verified_cliente_codigo = verified_context.get("cliente_codigo")
                verification_state = {
                    "verified": bool(conversation_context.get("verified") or verified_context),
                    "verified_document": conversation_context.get("verified_document"),
                    "verified_cliente_codigo": verified_cliente_codigo,
                    "sensitive_request": sensitive_request,
                }

                if is_greeting_message(content):
                    response_text = f"Hola, {context.get('nombre_visible') or 'cliente'}. ¿En qué puedo ayudarte hoy?"
                    outbound_payload = None
                    try:
                        outbound_payload = send_whatsapp_text_message(context["telefono_e164"], response_text)
                        provider_message_id = None
                        if outbound_payload.get("messages"):
                            provider_message_id = outbound_payload["messages"][0].get("id")
                        store_outbound_message(
                            context["conversation_id"],
                            provider_message_id,
                            "text",
                            response_text,
                            outbound_payload,
                            intent_detectado="saludo",
                        )
                    except Exception as exc:
                        store_outbound_message(
                            context["conversation_id"],
                            None,
                            "system",
                            f"No fue posible enviar saludo: {exc}",
                            {"error": str(exc), "response_text": response_text},
                            intent_detectado="saludo",
                        )

                    update_conversation_context(
                        context["conversation_id"],
                        {"intent": "saludo", "awaiting_verification": False},
                        summary="Saludo inicial",
                    )
                    processed_messages.append(
                        {
                            "conversation_id": context["conversation_id"],
                            "telefono": context["telefono_e164"],
                            "message_type": message_type,
                            "provider_message_id": message.get("id"),
                            "ai_response_sent": bool(outbound_payload),
                            "greeting_reply": True,
                        }
                    )
                    continue

                if detected_intent == "consulta_documentacion":
                    document_request = extract_technical_document_request(content, product_request, conversation_context)
                    if selected_document_option:
                        filename = selected_document_option.get("name") or "documento.pdf"
                        caption_text = (
                            f"Hola, {context.get('nombre_visible') or 'cliente'}. Te comparto el archivo {filename}."
                        )
                        outbound_payload = None
                        temporary_link = None
                        try:
                            temporary_link = get_dropbox_temporary_link(selected_document_option.get("path_lower"))
                            outbound_payload = send_whatsapp_document_message(
                                context["telefono_e164"],
                                temporary_link,
                                filename,
                                caption=caption_text,
                            )
                            provider_message_id = None
                            if outbound_payload.get("messages"):
                                provider_message_id = outbound_payload["messages"][0].get("id")
                            store_outbound_message(
                                context["conversation_id"],
                                provider_message_id,
                                "document",
                                caption_text,
                                outbound_payload,
                                intent_detectado="consulta_documentacion",
                            )
                        except Exception as exc:
                            fallback_text = (
                                f"Hola, {context.get('nombre_visible') or 'cliente'}. Encontré el archivo {filename}, "
                                "pero en este momento no pude adjuntarlo por WhatsApp. Escríbeme de nuevo en un momento y lo intento otra vez."
                            )
                            try:
                                outbound_payload = send_whatsapp_text_message(context["telefono_e164"], fallback_text)
                                provider_message_id = None
                                if outbound_payload.get("messages"):
                                    provider_message_id = outbound_payload["messages"][0].get("id")
                                store_outbound_message(
                                    context["conversation_id"],
                                    provider_message_id,
                                    "text",
                                    fallback_text,
                                    outbound_payload,
                                    intent_detectado="consulta_documentacion",
                                )
                            except Exception as text_exc:
                                store_outbound_message(
                                    context["conversation_id"],
                                    None,
                                    "system",
                                    f"No fue posible enviar documento tecnico: {exc}",
                                    {
                                        "error": str(exc),
                                        "fallback_error": str(text_exc),
                                        "document_name": filename,
                                        "temporary_link": temporary_link,
                                    },
                                    intent_detectado="consulta_documentacion",
                                )

                        update_conversation_context(
                            context["conversation_id"],
                            {
                                "last_direct_intent": "consulta_documentacion",
                                "last_document_request": document_request,
                                "pending_document_options": None,
                                "pending_product_clarification": None,
                                "awaiting_verification": False,
                            },
                            summary=f"Documento enviado: {filename}",
                        )
                        processed_messages.append(
                            {
                                "conversation_id": context["conversation_id"],
                                "telefono": context["telefono_e164"],
                                "message_type": message_type,
                                "provider_message_id": message.get("id"),
                                "ai_response_sent": bool(outbound_payload),
                                "document_sent": True,
                            }
                        )
                        continue

                    document_options = search_technical_documents(document_request)
                    direct_result = build_technical_document_reply(
                        context.get("nombre_visible"),
                        document_request,
                        document_options,
                    )
                    response_text = direct_result["response_text"]
                    outbound_payload = None
                    try:
                        outbound_payload = send_whatsapp_text_message(context["telefono_e164"], response_text)
                        provider_message_id = None
                        if outbound_payload.get("messages"):
                            provider_message_id = outbound_payload["messages"][0].get("id")
                        store_outbound_message(
                            context["conversation_id"],
                            provider_message_id,
                            "text",
                            response_text,
                            outbound_payload,
                            intent_detectado=direct_result.get("intent"),
                        )
                    except Exception as exc:
                        store_outbound_message(
                            context["conversation_id"],
                            None,
                            "system",
                            f"No fue posible enviar respuesta de documentacion: {exc}",
                            {"error": str(exc), "response_text": response_text},
                            intent_detectado=direct_result.get("intent"),
                        )

                    update_conversation_context(
                        context["conversation_id"],
                        {
                            "last_direct_intent": direct_result.get("intent"),
                            "last_document_request": document_request,
                            "pending_document_options": direct_result.get("document_options") if direct_result.get("awaiting_document_choice") else None,
                            "pending_product_clarification": None,
                            "awaiting_verification": False,
                        },
                        summary=direct_result.get("summary") or content,
                    )

                    processed_messages.append(
                        {
                            "conversation_id": context["conversation_id"],
                            "telefono": context["telefono_e164"],
                            "message_type": message_type,
                            "provider_message_id": message.get("id"),
                            "ai_response_sent": bool(outbound_payload),
                            "document_reply": True,
                        }
                    )
                    continue

                if is_thanks_or_closing_message(content):
                    response_text = build_conversation_closing_reply(context.get('nombre_visible'))
                    outbound_payload = None
                    try:
                        outbound_payload = send_whatsapp_text_message(context["telefono_e164"], response_text)
                        provider_message_id = None
                        if outbound_payload.get("messages"):
                            provider_message_id = outbound_payload["messages"][0].get("id")
                        store_outbound_message(
                            context["conversation_id"],
                            provider_message_id,
                            "text",
                            response_text,
                            outbound_payload,
                            intent_detectado="cierre_conversacion",
                        )
                    except Exception as exc:
                        store_outbound_message(
                            context["conversation_id"],
                            None,
                            "system",
                            f"No fue posible enviar cierre de conversacion: {exc}",
                            {"error": str(exc), "response_text": response_text},
                            intent_detectado="cierre_conversacion",
                        )

                    close_conversation(
                        context["conversation_id"],
                        {
                            "intent": "cierre_conversacion",
                            "last_direct_intent": conversation_context.get("last_direct_intent"),
                            "pending_product_clarification": None,
                            "pending_document_options": None,
                            "awaiting_verification": False,
                        },
                        summary="Cierre conversacional",
                    )
                    processed_messages.append(
                        {
                            "conversation_id": context["conversation_id"],
                            "telefono": context["telefono_e164"],
                            "message_type": message_type,
                            "provider_message_id": message.get("id"),
                            "ai_response_sent": bool(outbound_payload),
                            "closing_reply": True,
                        }
                    )
                    continue

                if detected_intent == "consulta_productos":
                    try:
                        product_context_result = lookup_product_context(content, product_request)
                        direct_result = build_direct_reply(
                            detected_intent,
                            cliente_contexto,
                            product_context_result,
                            context.get("nombre_visible"),
                            product_request,
                            content,
                            conversation_context,
                        )
                    except Exception:
                        product_context_result = []
                        direct_result = {
                            "tono": "informativo",
                            "intent": "consulta_productos",
                            "priority": "media",
                            "summary": "Consulta de productos con error interno",
                            "response_text": (
                                f"Hola, {context.get('nombre_visible') or 'cliente'}. "
                                "Tuve un problema buscando ese producto en el sistema. "
                                "¿Podrías darme la referencia exacta, el código o la marca para intentar de nuevo?"
                            ),
                            "should_create_task": False,
                            "task_type": "seguimiento_cliente",
                            "task_summary": "Error en consulta de productos",
                            "task_detail": {"mensaje": content},
                        }
                    if product_context_result and not direct_result.get("awaiting_product_clarification"):
                        try:
                            learn_product_resolution(
                                context["conversation_id"],
                                product_request,
                                product_context_result,
                                conversation_context,
                            )
                        except Exception:
                            pass
                    outbound_payload = None
                    response_text = direct_result["response_text"]
                    try:
                        outbound_payload = send_whatsapp_text_message(context["telefono_e164"], response_text)
                        provider_message_id = None
                        if outbound_payload.get("messages"):
                            provider_message_id = outbound_payload["messages"][0].get("id")
                        store_outbound_message(
                            context["conversation_id"],
                            provider_message_id,
                            "text",
                            response_text,
                            outbound_payload,
                            intent_detectado=direct_result.get("intent"),
                        )
                    except Exception as exc:
                        store_outbound_message(
                            context["conversation_id"],
                            None,
                            "system",
                            f"No fue posible enviar respuesta de producto: {exc}",
                            {"error": str(exc), "response_text": response_text},
                            intent_detectado=direct_result.get("intent"),
                        )

                    update_conversation_context(
                        context["conversation_id"],
                        {
                            "last_direct_intent": direct_result.get("intent"),
                            "last_product_request": product_request,
                            "pending_product_clarification": direct_result.get("clarification_options") if direct_result.get("awaiting_product_clarification") else None,
                            "pending_document_options": None,
                            "last_purchase_date": (direct_result.get("task_detail") or {}).get("fecha_venta") or ((direct_result.get("task_detail") or {}).get("totals") or {}).get("ultima_compra"),
                            "awaiting_verification": False,
                        },
                        summary=direct_result.get("summary") or content,
                    )

                    processed_messages.append(
                        {
                            "conversation_id": context["conversation_id"],
                            "telefono": context["telefono_e164"],
                            "message_type": message_type,
                            "provider_message_id": message.get("id"),
                            "ai_response_sent": bool(outbound_payload),
                            "direct_reply": True,
                        }
                    )
                    continue

                if verified_context and conversation_context.get("pending_intent") in {"consulta_cartera", "consulta_compras"}:
                    direct_result = build_direct_reply(
                        conversation_context.get("pending_intent"),
                        cliente_contexto,
                        [],
                        context.get("nombre_visible"),
                        product_request,
                        content,
                        conversation_context,
                    )
                    product_followup_result = None
                    pending_product_question = conversation_context.get("pending_product_question")
                    pending_product_request = conversation_context.get("pending_product_request") or {}
                    if pending_product_question and looks_like_product_query(pending_product_question, pending_product_request):
                        product_followup_result = build_direct_reply(
                            "consulta_productos",
                            cliente_contexto,
                            lookup_product_context(pending_product_question, pending_product_request),
                            context.get("nombre_visible"),
                            pending_product_request,
                            pending_product_question,
                            conversation_context,
                        )
                    response_text = build_verification_success_reply(context.get("nombre_visible"), cliente_contexto)
                    if direct_result:
                        response_text = f"{response_text} {direct_result['response_text']}"
                    if product_followup_result:
                        response_text = f"{response_text} {product_followup_result['response_text']}"
                    outbound_payload = None
                    try:
                        outbound_payload = send_whatsapp_text_message(context["telefono_e164"], response_text)
                        provider_message_id = None
                        if outbound_payload.get("messages"):
                            provider_message_id = outbound_payload["messages"][0].get("id")
                        store_outbound_message(
                            context["conversation_id"],
                            provider_message_id,
                            "text",
                            response_text,
                            outbound_payload,
                            intent_detectado=conversation_context.get("pending_intent"),
                        )
                    except Exception as exc:
                        store_outbound_message(
                            context["conversation_id"],
                            None,
                            "system",
                            f"No fue posible enviar respuesta tras validacion: {exc}",
                            {"error": str(exc), "response_text": response_text},
                            intent_detectado=conversation_context.get("pending_intent"),
                        )

                    update_conversation_context(
                        context["conversation_id"],
                        {
                            "verified": True,
                            "verified_document": conversation_context.get("verified_document"),
                            "verified_cliente_codigo": cliente_contexto.get("cliente_codigo") if cliente_contexto else None,
                            "awaiting_verification": False,
                            "pending_intent": None,
                            "pending_question": None,
                            "pending_product_question": None,
                            "pending_product_request": None,
                            "last_direct_intent": conversation_context.get("pending_intent"),
                            "cliente_contexto": cliente_contexto,
                        },
                        summary="Cliente validado y respuesta directa entregada",
                    )
                    processed_messages.append(
                        {
                            "conversation_id": context["conversation_id"],
                            "telefono": context["telefono_e164"],
                            "message_type": message_type,
                            "provider_message_id": message.get("id"),
                            "ai_response_sent": bool(outbound_payload),
                            "verified_now": True,
                        }
                    )
                    continue

                if verification_state["verified"]:
                    direct_result = build_direct_reply(
                        detected_intent,
                        cliente_contexto,
                        lookup_product_context(content, product_request) if detected_intent == "consulta_productos" else [],
                        context.get("nombre_visible"),
                        product_request,
                        content,
                        conversation_context,
                    )
                    if direct_result:
                        outbound_payload = None
                        response_text = direct_result["response_text"]
                        try:
                            outbound_payload = send_whatsapp_text_message(context["telefono_e164"], response_text)
                            provider_message_id = None
                            if outbound_payload.get("messages"):
                                provider_message_id = outbound_payload["messages"][0].get("id")
                            store_outbound_message(
                                context["conversation_id"],
                                provider_message_id,
                                "text",
                                response_text,
                                outbound_payload,
                                intent_detectado=direct_result.get("intent"),
                            )
                        except Exception as exc:
                            store_outbound_message(
                                context["conversation_id"],
                                None,
                                "system",
                                f"No fue posible enviar respuesta directa: {exc}",
                                {"error": str(exc), "response_text": response_text},
                                intent_detectado=direct_result.get("intent"),
                            )

                        update_conversation_context(
                            context["conversation_id"],
                            {
                                "verified": True,
                                "verified_document": verification_state.get("verified_document"),
                                "verified_cliente_codigo": verification_state.get("verified_cliente_codigo"),
                                "last_direct_intent": direct_result.get("intent"),
                                "pending_document_options": None,
                                "last_purchase_date": (direct_result.get("task_detail") or {}).get("fecha_venta") or ((direct_result.get("task_detail") or {}).get("totals") or {}).get("ultima_compra"),
                                "awaiting_verification": False,
                            },
                            summary=direct_result.get("summary") or content,
                        )

                        if direct_result.get("should_create_task"):
                            upsert_agent_task(
                                context["conversation_id"],
                                context.get("cliente_id"),
                                direct_result.get("task_type") or "seguimiento_cliente",
                                direct_result.get("task_summary") or "Revisar conversacion de WhatsApp",
                                direct_result.get("task_detail") or {"mensaje": content},
                                direct_result.get("priority") or "media",
                            )

                        processed_messages.append(
                            {
                                "conversation_id": context["conversation_id"],
                                "telefono": context["telefono_e164"],
                                "message_type": message_type,
                                "provider_message_id": message.get("id"),
                                "ai_response_sent": bool(outbound_payload),
                                "direct_reply": True,
                            }
                        )
                        continue

                if sensitive_request and not verification_state["verified"]:
                    challenge_text = build_verification_challenge()
                    outbound_payload = None
                    try:
                        outbound_payload = send_whatsapp_text_message(context["telefono_e164"], challenge_text)
                        provider_message_id = None
                        if outbound_payload.get("messages"):
                            provider_message_id = outbound_payload["messages"][0].get("id")
                        store_outbound_message(
                            context["conversation_id"],
                            provider_message_id,
                            "text",
                            challenge_text,
                            outbound_payload,
                            intent_detectado="solicitud_verificacion",
                        )
                    except Exception as exc:
                        store_outbound_message(
                            context["conversation_id"],
                            None,
                            "system",
                            f"No fue posible enviar solicitud de verificacion: {exc}",
                            {"error": str(exc), "response_text": challenge_text},
                            intent_detectado="solicitud_verificacion",
                        )

                    update_conversation_context(
                        context["conversation_id"],
                        {
                            "awaiting_verification": True,
                            "verified": False,
                            "last_requested_verification_at": "now",
                            "pending_intent": detected_intent,
                            "pending_question": content,
                            "pending_product_question": content if looks_like_product_query(content, product_request) else None,
                            "pending_product_request": product_request if looks_like_product_query(content, product_request) else None,
                        },
                        summary="Pendiente verificacion de identidad",
                    )
                    processed_messages.append(
                        {
                            "conversation_id": context["conversation_id"],
                            "telefono": context["telefono_e164"],
                            "message_type": message_type,
                            "provider_message_id": message.get("id"),
                            "ai_response_sent": bool(outbound_payload),
                            "verification_required": True,
                        }
                    )
                    continue

                product_context = lookup_product_context(content, product_request) if looks_like_product_query(content, product_request) else []

                ai_result = None
                outbound_payload = None
                if content and message_type in {"text", "button", "interactive"}:
                    try:
                        ai_result = generate_agent_reply(
                            context.get("nombre_visible"),
                            cliente_contexto,
                            recent_messages,
                            content,
                            verification_state,
                            product_context,
                        )
                    except Exception as exc:
                        ai_result = build_fallback_agent_result(content, str(exc))

                    response_text = ai_result.get("response_text") or "Gracias por escribirnos. Ya estamos revisando tu caso."

                    try:
                        outbound_payload = send_whatsapp_text_message(context["telefono_e164"], response_text)
                        provider_message_id = None
                        if outbound_payload.get("messages"):
                            provider_message_id = outbound_payload["messages"][0].get("id")

                        store_outbound_message(
                            context["conversation_id"],
                            provider_message_id,
                            "text",
                            response_text,
                            outbound_payload,
                            intent_detectado=ai_result.get("intent"),
                        )
                    except Exception as exc:
                        store_outbound_message(
                            context["conversation_id"],
                            None,
                            "system",
                            f"No fue posible enviar respuesta automatica: {exc}",
                            {"error": str(exc), "response_text": response_text},
                            intent_detectado=ai_result.get("intent"),
                        )

                    update_conversation_context(
                        context["conversation_id"],
                        {
                            "tone": ai_result.get("tono"),
                            "intent": ai_result.get("intent"),
                            "priority": ai_result.get("priority"),
                            "verified": verification_state.get("verified", False),
                            "verified_document": verification_state.get("verified_document"),
                            "verified_cliente_codigo": verification_state.get("verified_cliente_codigo"),
                            "cliente_contexto": cliente_contexto,
                            "product_context": product_context,
                            "pending_document_options": None,
                            "awaiting_verification": False,
                        },
                        summary=ai_result.get("summary") or content,
                    )

                    if ai_result.get("should_create_task"):
                        upsert_agent_task(
                            context["conversation_id"],
                            context.get("cliente_id"),
                            ai_result.get("task_type") or "seguimiento_cliente",
                            ai_result.get("task_summary") or "Revisar conversacion de WhatsApp",
                            ai_result.get("task_detail") or {"mensaje": content},
                            ai_result.get("priority") or "media",
                        )

                processed_messages.append(
                    {
                        "conversation_id": context["conversation_id"],
                        "telefono": context["telefono_e164"],
                        "message_type": message_type,
                        "provider_message_id": message.get("id"),
                        "ai_response_sent": bool(outbound_payload),
                    }
                )

    return {"status": "ok", "processed_messages": processed_messages}