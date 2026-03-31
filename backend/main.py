import os
import json
import re
import time
import tomllib
import unicodedata
from difflib import SequenceMatcher
from datetime import date, timedelta
from html import escape
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


CLAIM_KEYWORDS = [
    "reclamo",
    "reclamacion",
    "reclamación",
    "garantia",
    "garantía",
    "calidad",
    "no funcion",
    "no funciono",
    "no funcionó",
    "no cubre",
    "no cubrio",
    "no cubrió",
    "defecto",
    "falla",
    "dañado",
    "danado",
    "problema con",
]


QUOTE_KEYWORDS = [
    "cotizacion",
    "cotización",
    "cotizar",
    "presupuesto",
    "propuesta comercial",
]


ORDER_KEYWORDS = [
    "montar pedido",
    "montar un pedido",
    "hacer pedido",
    "hacer un pedido",
    "generar pedido",
    "generar un pedido",
    "realizar pedido",
    "realizar un pedido",
    "orden de compra",
    "confirmar pedido",
]


NON_PRODUCT_SERVICE_KEYWORDS = [
    "cartera",
    "saldo",
    "deuda",
    "debo",
    "compras",
    "compra",
    "estado de cuenta",
    "factura",
    "facturas",
    "reclamo",
    "garantia",
    "garantía",
    "calidad",
    "cotizacion",
    "cotización",
    "cotizar",
    "pedido",
    "correo",
    "email",
    "ficha tecnica",
    "ficha técnica",
    "hoja de seguridad",
]


PRODUCT_STOPWORDS = {
    "ay",
    "ahi",
    "alli",
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
    "compro",
    "compras",
    "hacer",
    "hace",
    "hago",
    "montar",
    "monto",
    "armar",
    "armo",
    "pasar",
    "pasame",
    "pasarme",
    "enviar",
    "enviame",
    "enviarme",
    "mandar",
    "mandame",
    "mandamelo",
    "mandarmelo",
    "pedir",
    "pedido",
    "correo",
    "email",
    "mail",
    "aqui",
    "aca",
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


def get_sendgrid_config():
    env_config = {
        "api_key": os.getenv("SENDGRID_API_KEY"),
        "from_email": os.getenv("SENDGRID_FROM_EMAIL"),
        "from_name": os.getenv("SENDGRID_FROM_NAME") or "Ferreinox S.A.S. BIC",
        "reclamos_to_email": os.getenv("SENDGRID_RECLAMOS_TO_EMAIL") or os.getenv("SENDGRID_QUALITY_TO_EMAIL"),
        "ventas_to_email": os.getenv("SENDGRID_VENTAS_TO_EMAIL"),
        "contabilidad_to_email": os.getenv("SENDGRID_CONTABILIDAD_TO_EMAIL"),
    }
    if env_config["api_key"] and env_config["from_email"]:
        return env_config

    secrets = load_local_secrets()
    config = secrets.get("sendgrid") or {}
    if config.get("api_key") and config.get("from_email"):
        return {
            "api_key": config.get("api_key"),
            "from_email": config.get("from_email"),
            "from_name": config.get("from_name") or "Ferreinox S.A.S. BIC",
            "reclamos_to_email": config.get("reclamos_to_email") or config.get("quality_to_email") or config.get("from_email"),
            "ventas_to_email": config.get("ventas_to_email"),
            "contabilidad_to_email": config.get("contabilidad_to_email"),
        }
    return None


def send_sendgrid_email(to_email: str, subject: str, html_content: str, text_content: str, reply_to: Optional[str] = None):
    config = get_sendgrid_config()
    if not config:
        raise RuntimeError("SendGrid no está configurado.")

    payload = {
        "personalizations": [{"to": [{"email": to_email}], "subject": subject}],
        "from": {
            "email": config["from_email"],
            "name": config.get("from_name") or "Ferreinox S.A.S. BIC",
        },
        "content": [
            {"type": "text/plain", "value": text_content},
            {"type": "text/html", "value": html_content},
        ],
    }
    if reply_to:
        payload["reply_to"] = {"email": reply_to}

    response = requests.post(
        "https://api.sendgrid.com/v3/mail/send",
        headers={
            "Authorization": f"Bearer {config['api_key']}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=20,
    )
    if response.status_code >= 400:
        try:
            error_payload = response.json()
        except Exception:
            error_payload = {"raw": response.text}
        raise RuntimeError(f"SendGrid devolvió {response.status_code}: {safe_json_dumps(error_payload)}")
    return True


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


def upsert_commercial_draft(
    intent: str,
    conversation_id: int,
    contact_id: Optional[int],
    cliente_id: Optional[int],
    commercial_draft: dict,
):
    if intent not in {"pedido", "cotizacion"}:
        return None

    matched_items = [item for item in (commercial_draft.get("items") or []) if item.get("status") == "matched" and item.get("matched_product")]
    store_filters = commercial_draft.get("store_filters") or []
    store_code = store_filters[0] if store_filters else None
    store_name = STORE_CODE_LABELS.get(store_code) if store_code else None
    summary = f"Borrador de {'pedido' if intent == 'pedido' else 'cotización'} con {len(commercial_draft.get('items') or [])} líneas conversacionales"
    header_table = "agent_order" if intent == "pedido" else "agent_quote"
    line_table = "agent_order_line" if intent == "pedido" else "agent_quote_line"
    foreign_key = "order_id" if intent == "pedido" else "quote_id"
    draft_id = commercial_draft.get("draft_id")

    engine = get_db_engine()
    with engine.begin() as connection:
        if draft_id:
            connection.execute(
                text(
                    f"""
                    UPDATE public.{header_table}
                    SET contacto_id = :contact_id,
                        cliente_id = :cliente_id,
                        almacen_codigo = :store_code,
                        almacen_nombre = :store_name,
                        resumen = :summary,
                        metadata = CAST(:metadata AS jsonb),
                        updated_at = now()
                    WHERE id = :draft_id
                    """
                ),
                {
                    "draft_id": draft_id,
                    "contact_id": contact_id,
                    "cliente_id": cliente_id,
                    "store_code": store_code,
                    "store_name": store_name,
                    "summary": summary,
                    "metadata": safe_json_dumps(commercial_draft),
                },
            )
        else:
            draft_id = connection.execute(
                text(
                    f"""
                    INSERT INTO public.{header_table} (
                        conversation_id,
                        contacto_id,
                        cliente_id,
                        almacen_codigo,
                        almacen_nombre,
                        resumen,
                        metadata,
                        created_at,
                        updated_at
                    )
                    VALUES (
                        :conversation_id,
                        :contact_id,
                        :cliente_id,
                        :store_code,
                        :store_name,
                        :summary,
                        CAST(:metadata AS jsonb),
                        now(),
                        now()
                    )
                    RETURNING id
                    """
                ),
                {
                    "conversation_id": conversation_id,
                    "contact_id": contact_id,
                    "cliente_id": cliente_id,
                    "store_code": store_code,
                    "store_name": store_name,
                    "summary": summary,
                    "metadata": safe_json_dumps(commercial_draft),
                },
            ).scalar_one()

        connection.execute(text(f"DELETE FROM public.{line_table} WHERE {foreign_key} = :draft_id"), {"draft_id": draft_id})

        for line_number, item in enumerate(matched_items, start=1):
            product = item.get("matched_product") or {}
            product_request = item.get("product_request") or {}
            quantity_value = parse_numeric_value(product_request.get("requested_quantity")) or 1
            stock_value = parse_numeric_value(product.get("stock_total") if product.get("stock_total") is not None else product.get("stock"))
            connection.execute(
                text(
                    f"""
                    INSERT INTO public.{line_table} (
                        {foreign_key},
                        line_number,
                        producto_codigo,
                        referencia,
                        descripcion,
                        marca,
                        presentacion,
                        almacen_codigo,
                        almacen_nombre,
                        cantidad,
                        stock_confirmado,
                        metadata,
                        created_at,
                        updated_at
                    )
                    VALUES (
                        :draft_id,
                        :line_number,
                        :producto_codigo,
                        :referencia,
                        :descripcion,
                        :marca,
                        :presentacion,
                        :almacen_codigo,
                        :almacen_nombre,
                        :cantidad,
                        :stock_confirmado,
                        CAST(:metadata AS jsonb),
                        now(),
                        now()
                    )
                    """
                ),
                {
                    "draft_id": draft_id,
                    "line_number": line_number,
                    "producto_codigo": product.get("producto_codigo") or product.get("codigo_articulo"),
                    "referencia": product.get("referencia") or product.get("codigo_articulo"),
                    "descripcion": product.get("descripcion") or product.get("nombre_articulo") or item.get("original_text"),
                    "marca": infer_product_brand_from_row(product),
                    "presentacion": infer_product_presentation_from_row(product),
                    "almacen_codigo": store_code,
                    "almacen_nombre": store_name,
                    "cantidad": quantity_value,
                    "stock_confirmado": stock_value,
                    "metadata": safe_json_dumps(item),
                },
            )

    return draft_id


def extract_document_candidate(text_value: Optional[str]):
    if not text_value:
        return None
    matches = re.findall(r"\b\d{6,15}\b", text_value)
    return matches[0] if matches else None


def extract_email_address(text_value: Optional[str]):
    if not text_value:
        return None
    match = re.search(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", text_value, flags=re.IGNORECASE)
    return match.group(0).strip() if match else None


def extract_delivery_channel(text_value: Optional[str]):
    normalized = normalize_text_value(text_value)
    if not normalized:
        return None
    if extract_email_address(text_value) or re.search(r"\b(correo|email|mail)\b", normalized):
        return "email"
    if any(phrase in normalized for phrase in ["whatsapp", "wpp", "chat", "por aqui", "por aquí", "aca", "acá"]):
        return "chat"
    return None


def summarize_commercial_item(item: dict):
    product_request = item.get("product_request") or {}
    matched_product = item.get("matched_product") or {}
    description_value = matched_product.get("descripcion") or matched_product.get("nombre_articulo") or item.get("original_text") or "producto"
    requested_quantity = parse_numeric_value(product_request.get("requested_quantity")) or 1
    requested_unit = product_request.get("requested_unit")
    if requested_unit:
        quantity_label = f"{format_quantity(requested_quantity)} {get_presentation_label(requested_unit, requested_quantity)} de "
    elif requested_quantity > 1:
        quantity_label = f"{format_quantity(requested_quantity)} unidades de "
    else:
        quantity_label = ""
    return f"{quantity_label}{description_value}".strip()


def summarize_commercial_items(items: list[dict]):
    labels = [summarize_commercial_item(item) for item in items[:6] if item.get("status") == "matched"]
    if not labels:
        return ""
    if len(labels) == 1:
        return labels[0]
    if len(labels) == 2:
        return f"{labels[0]} y {labels[1]}"
    return ", ".join(labels[:-1]) + f" y {labels[-1]}"


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
        candidate_intent = detect_business_intent(text_value)
        strong_product_signal = bool(
            product_request.get("product_codes")
            or product_request.get("requested_unit")
            or product_request.get("requested_quantity")
            or product_request.get("store_filters")
            or product_request.get("brand_filters")
        )
        if candidate_intent not in {"consulta_general", "consulta_cartera", "consulta_compras"}:
            return None
        if 2 <= len(tokens) <= 6 and not strong_product_signal and candidate_intent == "consulta_general":
            return {"type": "name_lookup", "value": text_value.strip()}
        if candidate_intent == "consulta_general" and not looks_like_product_query(text_value, product_request) and 2 <= len(tokens) <= 6:
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


def has_non_product_business_signal(text_value: Optional[str]):
    normalized = normalize_text_value(text_value)
    if not normalized:
        return False
    return any(keyword in normalized for keyword in NON_PRODUCT_SERVICE_KEYWORDS)


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
    return "Con mucho gusto. Quedo atento por aquí para lo que necesites de Ferreinox."


def should_continue_claim_flow(conversation_context: Optional[dict], detected_intent: Optional[str], text_value: Optional[str]):
    claim_case = dict((conversation_context or {}).get("claim_case") or {})
    if not claim_case.get("active") or claim_case.get("submitted"):
        return False

    normalized = normalize_text_value(text_value)
    if not normalized:
        return False

    if extract_email_address(text_value):
        return True
    if detected_intent in {"pedido", "cotizacion", "consulta_cartera", "consulta_compras", "consulta_documentacion"}:
        return False
    if any(keyword in normalized for keyword in ["inventario", "stock", "precio", "cotizar", "cotizacion", "pedido", "cartera", "compras"]):
        return False
    return True


def should_continue_commercial_flow(conversation_context: Optional[dict], detected_intent: Optional[str], text_value: Optional[str]):
    context = conversation_context or {}
    active_intent = context.get("last_direct_intent")
    commercial_draft = dict(context.get("commercial_draft") or {})
    if active_intent not in {"pedido", "cotizacion"}:
        return False
    if commercial_draft and commercial_draft.get("intent") not in {None, active_intent}:
        return False
    if detected_intent in {"consulta_cartera", "consulta_compras", "consulta_documentacion", "reclamo_servicio"}:
        return False

    normalized = normalize_text_value(text_value)
    if not normalized:
        return False

    if extract_store_filters(text_value) or extract_email_address(text_value):
        return True
    if is_product_intent_message(text_value):
        return True
    if len(split_commercial_line_items(text_value)) >= 2:
        return True
    return bool(re.search(r"\b\d+\s*/\s*(1|4|5)\b", normalized))


def split_commercial_line_items(text_value: Optional[str]):
    if not text_value:
        return []

    prepared_text = re.sub(r"[;|]+", "\n", text_value)
    raw_lines = [line.strip(" -*•\t") for line in prepared_text.splitlines()]
    lines = [line for line in raw_lines if line]
    if len(lines) >= 2:
        return lines

    normalized = normalize_text_value(text_value)
    if re.search(r"\b\d+\s*/\s*(1|4|5)\b", normalized):
        split_candidates = [segment.strip() for segment in re.split(r"\s{2,}|,(?=\s*\d)|(?<=\")\s+(?=\d)", text_value) if segment.strip()]
        if len(split_candidates) >= 2:
            return split_candidates

    return lines if lines else [text_value.strip()]


def merge_store_filters(product_request: dict, inherited_store_filters: list[str]):
    merged_request = dict(product_request or {})
    if inherited_store_filters and not merged_request.get("store_filters"):
        merged_request["store_filters"] = list(inherited_store_filters)
    return merged_request


def describe_commercial_item_need(item: dict):
    request = item.get("product_request") or {}
    if request.get("product_codes"):
        return request["product_codes"][0]
    if request.get("core_terms"):
        return " ".join(request.get("core_terms")[:4])
    return item.get("original_text") or "ese producto"


def build_commercial_item_result(raw_line: str, inherited_store_filters: list[str], mode: str):
    product_request = merge_store_filters(extract_product_request(raw_line), inherited_store_filters)
    product_rows = lookup_product_context(raw_line, product_request)
    requested_store_codes = product_request.get("store_filters") or []
    requested_store_label = STORE_CODE_LABELS.get(requested_store_codes[0]) if len(requested_store_codes) == 1 else None

    item_result = {
        "original_text": raw_line,
        "product_request": product_request,
        "matches": product_rows,
        "status": "missing",
        "message": "",
        "matched_product": None,
    }

    if not product_rows:
        item_result["message"] = f"{describe_commercial_item_need(item_result)}: necesito una referencia más precisa o la presentación exacta para dejarlo bien." 
        return item_result

    if should_ask_product_clarification(product_request, product_rows):
        options = []
        for row in product_rows[:3]:
            options.append(f"{row.get('referencia') or row.get('codigo_articulo')}: {row.get('descripcion') or row.get('nombre_articulo')}")
        item_result["status"] = "ambiguous"
        item_result["message"] = (
            f"{describe_commercial_item_need(item_result)}: necesito confirmarte cuál es la correcta. "
            f"Las más cercanas son {', '.join(options)}."
        )
        return item_result

    top_row = dict(product_rows[0])
    item_result["status"] = "matched"
    item_result["matched_product"] = top_row
    description_value = top_row.get("descripcion") or top_row.get("nombre_articulo") or top_row.get("referencia") or top_row.get("codigo_articulo")
    reference_value = top_row.get("referencia") or top_row.get("codigo_articulo") or "sin referencia"
    stock_value = parse_numeric_value(top_row.get("stock_total") if top_row.get("stock_total") is not None else top_row.get("stock")) or 0
    requested_quantity = parse_numeric_value(product_request.get("requested_quantity"))
    requested_unit = product_request.get("requested_unit")
    quantity_label = None
    if requested_quantity and requested_unit:
        quantity_label = f"{format_quantity(requested_quantity)} {get_presentation_label(requested_unit, requested_quantity)}"

    if requested_store_label:
        if stock_value <= 0:
            item_result["message"] = f"{description_value} ({reference_value}): en {requested_store_label} no lo veo disponible en este momento."
        else:
            item_result["message"] = f"{description_value} ({reference_value}): sí lo tengo disponible en {requested_store_label}"
            if quantity_label:
                availability = "y te alcanza para lo que pides" if stock_value >= requested_quantity else "pero no alcanza para toda la cantidad"
                item_result["message"] += f", con {format_quantity(stock_value)} unidades confirmadas {availability}"
            item_result["message"] += "."
    else:
        if stock_value <= 0:
            item_result["message"] = f"{description_value} ({reference_value}): en este momento no veo existencias disponibles."
        else:
            item_result["message"] = f"{description_value} ({reference_value}): sí lo tengo disponible"
            if quantity_label:
                availability = "y sí alcanza para lo que pides" if stock_value >= requested_quantity else "pero la cantidad disponible no alcanza para todo"
                item_result["message"] += f", {availability}"
            elif top_row.get("stock_por_tienda"):
                item_result["message"] += ", con existencias en varias sedes"
            item_result["message"] += "."

    return item_result


def build_commercial_flow_reply(intent: str, profile_name: Optional[str], user_message: Optional[str], conversation_context: Optional[dict]):
    context = conversation_context or {}
    existing_draft = dict(context.get("commercial_draft") or {})
    last_intent = context.get("last_direct_intent")
    incoming_store_filters = extract_store_filters(user_message)
    incoming_email = extract_email_address(user_message)
    incoming_delivery_channel = extract_delivery_channel(user_message)
    inherited_store_filters = incoming_store_filters or existing_draft.get("store_filters") or []
    current_lines = split_commercial_line_items(user_message)
    has_existing_items = bool(existing_draft.get("items"))
    has_contextual_followup = bool(incoming_store_filters or incoming_email or incoming_delivery_channel)

    has_explicit_items = any(
        extract_product_request(line).get("product_codes")
        or extract_product_request(line).get("core_terms")
        or extract_product_request(line).get("requested_unit")
        for line in current_lines
    )

    if has_existing_items and (incoming_email or incoming_delivery_channel) and not incoming_store_filters:
        current_lines = []
        has_explicit_items = False

    if not has_explicit_items and not has_existing_items and not has_contextual_followup:
        summary_label = "cotización" if intent == "cotizacion" else "pedido"
        intro_label = "la cotización" if intent == "cotizacion" else "el pedido"
        return {
            "tono": "consultivo",
            "intent": intent,
            "priority": "alta" if intent == "pedido" else "media",
            "summary": f"Inicio de {summary_label}",
            "response_text": (
                f"Con mucho gusto te ayudo con {intro_label}. "
                "Pásame las referencias o productos como los manejas normalmente y, si ya sabes la tienda o ciudad de entrega, me la dejas de una vez."
            ),
            "should_create_task": last_intent != intent,
            "task_type": intent,
            "task_summary": f"Solicitud de {summary_label} iniciada por WhatsApp",
            "task_detail": {"mensaje": user_message, "mode": intent},
            "conversation_context_updates": {
                "commercial_draft": {
                    "intent": intent,
                    "store_filters": inherited_store_filters,
                    "delivery_channel": incoming_delivery_channel,
                    "contact_email": incoming_email,
                    "items": existing_draft.get("items") or [],
                }
            },
        }

    draft_items = []
    if existing_draft.get("intent") == intent:
        draft_items = list(existing_draft.get("items") or [])

    if draft_items and incoming_store_filters and not has_explicit_items:
        current_lines = [item.get("original_text") for item in draft_items if item.get("original_text")]
        draft_items = []
    elif draft_items and not has_explicit_items and has_contextual_followup:
        current_lines = []

    if draft_items and len(current_lines) == 1 and (incoming_store_filters or extract_product_request(user_message).get("product_codes")):
        base_lines = [item.get("original_text") for item in draft_items if item.get("original_text")]
        if base_lines:
            refined_lines = list(base_lines)
            incoming_codes = extract_product_request(user_message).get("product_codes") or []
            if incoming_codes:
                refined_lines[0] = f"{refined_lines[0]} {user_message}".strip()
            current_lines = refined_lines
            draft_items = []

    if draft_items and len(current_lines) == 1 and extract_product_request(user_message).get("product_codes"):
        unresolved_index = next((index for index, item in enumerate(draft_items) if item.get("status") != "matched"), None)
        if unresolved_index is not None:
            base_text = draft_items[unresolved_index].get("original_text") or ""
            current_lines = [f"{base_text} {user_message}".strip()]
            draft_items = [item for index, item in enumerate(draft_items) if index != unresolved_index]

    resolved_items = list(draft_items)
    for raw_line in current_lines:
        if not raw_line:
            continue
        resolved_items.append(build_commercial_item_result(raw_line, inherited_store_filters, intent))

    matched_items = [item for item in resolved_items if item.get("status") == "matched"]
    ambiguous_items = [item for item in resolved_items if item.get("status") == "ambiguous"]
    missing_items = [item for item in resolved_items if item.get("status") == "missing"]
    store_label = STORE_CODE_LABELS.get(inherited_store_filters[0]) if len(inherited_store_filters) == 1 else None
    delivery_channel = incoming_delivery_channel or existing_draft.get("delivery_channel")
    contact_email = incoming_email or existing_draft.get("contact_email")
    internal_notified = bool(existing_draft.get("internal_notified"))
    customer_email_sent = bool(existing_draft.get("customer_email_sent"))

    matched_text = " ".join(item.get("message") for item in matched_items[:8] if item.get("message"))
    pending_text_parts = [item.get("message") for item in ambiguous_items[:4] if item.get("message")] + [item.get("message") for item in missing_items[:4] if item.get("message")]
    pending_text = " ".join(pending_text_parts)
    compact_summary = summarize_commercial_items(matched_items)
    has_store = bool(inherited_store_filters)
    ready_to_close = bool(matched_items) and not ambiguous_items and not missing_items and has_store

    if not ready_to_close:
        closing_parts = []
        if not has_store:
            closing_parts.append("¿En qué tienda o ciudad lo necesitas para cerrarte todo bien?")
        elif pending_text_parts:
            closing_parts.append("Apenas me confirmes esos puntos te dejo el consolidado completo.")
        else:
            closing_parts.append("Si quieres, cuando lo dejemos cerrado te lo confirmo por aquí o te lo mando al correo.")

        response_parts = []
        if matched_text:
            response_parts.append(matched_text)
        if pending_text:
            response_parts.append(pending_text)
        response_parts.extend(closing_parts)

        draft_state = {
            "intent": intent,
            "store_filters": inherited_store_filters,
            "delivery_channel": delivery_channel,
            "contact_email": contact_email,
            "internal_notified": internal_notified,
            "customer_email_sent": customer_email_sent,
            "items": resolved_items,
        }

        return {
            "tono": "consultivo",
            "intent": intent,
            "priority": "alta" if intent == "pedido" else "media",
            "summary": "Consolidado comercial multiproducto",
            "response_text": " ".join(part for part in response_parts if part).strip(),
            "should_create_task": last_intent != intent,
            "task_type": intent,
            "task_summary": "Seguimiento a solicitud comercial por WhatsApp",
            "task_detail": {"items": resolved_items, "store_filters": inherited_store_filters, "mode": intent},
            "conversation_context_updates": {"commercial_draft": draft_state},
            "commercial_draft": draft_state,
        }

    request_label = "cotización" if intent == "cotizacion" else "pedido"
    destination_label = store_label or "la sede indicada"
    if not delivery_channel:
        response_text = (
            f"Perfecto, ya te dejé organizada la solicitud de {request_label} para {destination_label} con {compact_summary}. "
            "¿Prefieres que te la confirme por aquí o que te la envíe al correo?"
        )
    elif delivery_channel == "email" and not contact_email:
        response_text = (
            f"Perfecto, ya tengo lista la solicitud de {request_label} para {destination_label} con {compact_summary}. "
            "Regálame el correo y te la envío bien presentada."
        )
    elif delivery_channel == "email":
        response_text = (
            f"Perfecto, ya te dejé lista la solicitud de {request_label} para {destination_label} con {compact_summary}. "
            f"Te la envío al correo {contact_email} para que te quede formalizada."
        )
    else:
        response_text = (
            f"Perfecto, ya te dejé lista la solicitud de {request_label} para {destination_label} con {compact_summary}. "
            "Te queda confirmada por aquí y si luego quieres también te la mando al correo."
        )

    final_confirmation_ready = ready_to_close and (delivery_channel == "chat" or (delivery_channel == "email" and bool(contact_email)))
    should_notify_internal = final_confirmation_ready and not internal_notified
    should_send_customer_email = final_confirmation_ready and delivery_channel == "email" and bool(contact_email) and not customer_email_sent
    draft_state = {
        "intent": intent,
        "store_filters": inherited_store_filters,
        "delivery_channel": delivery_channel,
        "contact_email": contact_email,
        "ready_to_close": ready_to_close,
        "internal_notified": internal_notified or should_notify_internal,
        "customer_email_sent": customer_email_sent or should_send_customer_email,
        "items": resolved_items,
    }

    return {
        "tono": "consultivo",
        "intent": intent,
        "priority": "alta" if intent == "pedido" else "media",
        "summary": "Consolidado comercial multiproducto",
        "response_text": response_text,
        "should_create_task": last_intent != intent or should_notify_internal,
        "task_type": intent,
        "task_summary": f"Solicitud de {request_label} lista para seguimiento",
        "task_detail": {"items": resolved_items, "store_filters": inherited_store_filters, "mode": intent, "delivery_channel": delivery_channel, "contact_email": contact_email},
        "conversation_context_updates": {"commercial_draft": draft_state},
        "commercial_draft": draft_state,
        "email_route": "ventas" if should_notify_internal else None,
        "email_detail": draft_state if should_notify_internal else None,
        "commercial_customer_email_confirmation": draft_state if should_send_customer_email else None,
    }


def build_technical_document_reply(profile_name: Optional[str], document_request: dict, document_options: list[dict]):
    requested_label = "hoja de seguridad" if document_request.get("wants_safety_sheet") else "ficha técnica"
    if not document_options:
        return {
            "tono": "informativo",
            "intent": "consulta_documentacion",
            "priority": "media",
            "summary": "Consulta de documentación sin coincidencia clara",
            "response_text": (
                f"Revisé la carpeta de {requested_label} y no encontré una coincidencia clara con ese nombre. "
                "Si quieres, dime la referencia, la línea o el nombre comercial y te muestro las opciones más cercanas."
            ),
            "document_options": [],
            "awaiting_document_choice": False,
        }

    option_lines = [f"{index}. {row['name']}" for index, row in enumerate(document_options[:4], start=1)]
    intro = f"Esto fue lo que encontré en {requested_label}:"
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
    if any(keyword in lowered for keyword in CLAIM_KEYWORDS):
        return "reclamo_servicio"
    if any(keyword in lowered for keyword in QUOTE_KEYWORDS):
        return "cotizacion"
    if any(keyword in lowered for keyword in ORDER_KEYWORDS):
        return "pedido"
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
    if has_non_product_business_signal(text_value) and not (
        request.get("product_codes")
        or request.get("brand_filters")
        or request.get("requested_unit")
        or request.get("requested_quantity")
        or request.get("store_filters")
    ):
        return False
    if request.get("product_codes"):
        return True
    if request.get("brand_filters") or request.get("requested_unit") or request.get("size_filters"):
        return True
    meaningful_terms = [term for term in (request.get("core_terms") or []) if not is_store_alias_term(term)]
    return len(meaningful_terms) >= 2


def detect_context_switch(conversation_context: Optional[dict], detected_intent: Optional[str], identity_verification_message: bool):
    context = conversation_context or {}
    previous_intent = context.get("last_direct_intent") or context.get("intent")
    if identity_verification_message or context.get("awaiting_verification"):
        return False
    if not previous_intent or not detected_intent or detected_intent == "consulta_general":
        return False
    if previous_intent == detected_intent:
        return False
    tracked_intents = {
        "consulta_productos",
        "consulta_documentacion",
        "consulta_cartera",
        "consulta_compras",
        "reclamo_servicio",
        "cotizacion",
        "pedido",
    }
    return previous_intent in tracked_intents and detected_intent in tracked_intents


def summarize_claim_product(product_request: Optional[dict], conversation_context: Optional[dict]):
    request = product_request or {}
    previous_request = (conversation_context or {}).get("last_product_request") or {}
    search_terms = list(request.get("core_terms") or request.get("search_terms") or [])
    if not search_terms:
        search_terms = list(previous_request.get("core_terms") or previous_request.get("search_terms") or [])
    claim_noise = {
        "hacer",
        "pintura",
        "tenia",
        "tenía",
        "cubrimiento",
        "bajo",
        "su",
        "alcanzo",
        "alcanzó",
        "no",
        "bien",
        "cubrio",
        "cubrió",
        "funciono",
        "funcionó",
        "reclamo",
        "problema",
        "falla",
        "montar",
        "poner",
        "quiero",
        "necesito",
        "caso",
        "ayuda",
        "cunete",
        "cunetes",
        "cuñete",
        "cuñetes",
    }
    filtered_terms = []
    for term in search_terms:
        normalized_term = normalize_text_value(term)
        if (
            normalized_term
            and normalized_term not in PRODUCT_STOPWORDS
            and normalized_term not in NON_PRODUCT_SERVICE_KEYWORDS
            and normalized_term not in claim_noise
            and normalized_term not in filtered_terms
        ):
            filtered_terms.append(normalized_term)
    if not filtered_terms:
        return None
    product_label = " ".join(filtered_terms[:4])
    quantity_expression = request.get("quantity_expression") or previous_request.get("quantity_expression")
    if quantity_expression and quantity_expression not in product_label:
        product_label = f"{product_label} {quantity_expression}".strip()
    return product_label


def is_weak_claim_product_label(product_label: Optional[str]):
    normalized = normalize_text_value(product_label)
    return normalized in {"", "hacer", "reclamo", "problema", "caso", "ayuda"}


def extract_claim_case_details(text_value: Optional[str], conversation_context: Optional[dict], product_request: Optional[dict]):
    existing_case = dict((conversation_context or {}).get("claim_case") or {})
    normalized = normalize_text_value(text_value)
    raw_text = (text_value or "").strip()
    email_address = extract_email_address(text_value) or existing_case.get("contact_email")
    evidence_note = existing_case.get("evidence_note")
    current_step = existing_case.get("step") or "awaiting_product"
    notes = list(existing_case.get("notes") or [])
    if raw_text and raw_text not in notes and not is_greeting_message(text_value):
        notes.append(raw_text[:600])

    detected_product_label = summarize_claim_product(product_request, conversation_context)
    product_label = existing_case.get("product_label")
    if detected_product_label and (not product_label or is_weak_claim_product_label(product_label)):
        product_label = detected_product_label
    issue_summary = existing_case.get("issue_summary")
    generic_openers = {
        "necesito montar un reclamo",
        "necesito hacer un reclamo",
        "quiero montar un reclamo",
        "quiero hacer un reclamo",
        "quiero poner un reclamo",
        "necesito poner un reclamo",
        "tengo un reclamo",
        "montar un reclamo",
        "hacer un reclamo",
        "quiero abrir un reclamo",
        "necesito abrir un reclamo",
    }
    if raw_text and normalized not in generic_openers and not extract_email_address(text_value):
        has_claim_signal = any(keyword in normalized for keyword in CLAIM_KEYWORDS)
        if current_step in {"awaiting_product", "awaiting_detail"} and (has_claim_signal or existing_case.get("active")):
            issue_summary = raw_text[:600]
        elif current_step == "awaiting_evidence":
            evidence_note = raw_text[:600]

    if not evidence_note and re.search(r"\b(lote|foto|fotos|adjunto|adjunta|imagen|imagenes)\b", normalized):
        evidence_note = raw_text[:600]

    store_name = existing_case.get("store_name")
    store_filters = (product_request or {}).get("store_filters") or []
    if store_filters:
        store_name = STORE_CODE_LABELS.get(store_filters[0]) or store_filters[0]

    missing_fields = []
    if not product_label:
        missing_fields.append("producto")
    if not issue_summary:
        missing_fields.append("detalle")
    if not evidence_note:
        missing_fields.append("evidencia")
    if not email_address:
        missing_fields.append("correo")

    if missing_fields:
        if "producto" in missing_fields:
            next_step = "awaiting_product"
        elif "detalle" in missing_fields:
            next_step = "awaiting_detail"
        elif "evidencia" in missing_fields:
            next_step = "awaiting_evidence"
        else:
            next_step = "awaiting_email"
    else:
        next_step = "ready_to_submit"

    severity = existing_case.get("severity") or (
        "critica" if any(keyword in normalized for keyword in ["no funciono", "no funcionó", "dañado", "danado", "garantia", "garantía"]) else "alta"
    )

    return {
        **existing_case,
        "active": True,
        "product_label": product_label,
        "issue_summary": issue_summary,
        "evidence_note": evidence_note,
        "contact_email": email_address,
        "store_name": store_name,
        "notes": notes[-8:],
        "severity": severity,
        "step": next_step,
        "missing_fields": missing_fields,
        "ready_to_submit": not missing_fields,
    }


def build_claim_reply(profile_name: Optional[str], claim_case: dict, cliente_contexto: Optional[dict]):
    if claim_case.get("submitted"):
        return {
            "tono": "empatico",
            "intent": "reclamo_servicio",
            "priority": claim_case.get("severity") or "alta",
            "summary": f"Seguimiento a reclamo de {claim_case.get('product_label') or 'cliente'}",
            "response_text": (
                "Tu caso ya quedó radicado y sigue en seguimiento. "
                "Si quieres, todavía puedo agregar más detalle, fotos, lote o la tienda donde ocurrió para que el área técnica lo reciba mejor documentado."
            ),
            "should_create_task": False,
            "task_type": "reclamo_calidad",
            "task_summary": "Seguimiento a reclamo existente",
            "task_detail": claim_case,
            "conversation_context_updates": {"claim_case": claim_case},
        }
    if claim_case.get("ready_to_submit"):
        cliente_label = None
        if cliente_contexto:
            cliente_label = cliente_contexto.get("nombre_cliente") or cliente_contexto.get("cliente_codigo")
        response_text = (
            f"Perfecto. Ya dejé radicado el caso de {claim_case.get('product_label')}. "
            "Lo voy a escalar con el área técnica y en unos minutos te llegará al correo la constancia con el detalle para que tengas seguimiento."
        )
        return {
            "tono": "empatico",
            "intent": "reclamo_servicio",
            "priority": claim_case.get("severity") or "alta",
            "summary": f"Reclamo radicado de {claim_case.get('product_label')}",
            "response_text": response_text,
            "should_create_task": True,
            "task_type": "reclamo_calidad",
            "task_summary": f"Reclamo de calidad o funcionamiento: {claim_case.get('product_label')}",
            "task_detail": {**claim_case, "cliente": cliente_label},
            "conversation_context_updates": {"claim_case": {**claim_case, "submitted": True, "active": False, "step": "submitted"}},
            "email_route": "reclamos",
            "email_detail": {**claim_case, "cliente": cliente_label},
            "customer_email_confirmation": {**claim_case, "cliente": cliente_label},
        }

    missing_fields = claim_case.get("missing_fields") or []
    if "producto" in missing_fields:
        response_text = "Claro que sí, lamento el inconveniente. Cuéntame, ¿con qué producto tuviste el problema y qué pasó exactamente?"
    elif "detalle" in missing_fields:
        response_text = (
            f"Entiendo, el caso va sobre {claim_case.get('product_label')}. "
            "Cuéntame qué pasó exactamente para dejarlo bien sustentado, por ejemplo si no cubrió, cambió el tono o presentó alguna falla."
        )
    elif "evidencia" in missing_fields:
        response_text = "Entiendo. ¿De casualidad tienes el número de lote o alguna foto que me puedas compartir?"
    else:
        response_text = "Perfecto. Por favor regálame un correo electrónico para enviarte el número de radicado y hacerle seguimiento."

    return {
        "tono": "empatico",
        "intent": "reclamo_servicio",
        "priority": claim_case.get("severity") or "alta",
        "summary": "Toma de datos para reclamo",
        "response_text": response_text,
        "should_create_task": False,
        "task_type": "reclamo_calidad",
        "task_summary": "Toma inicial de reclamo",
        "task_detail": claim_case,
        "conversation_context_updates": {"claim_case": claim_case},
    }


def build_operational_email_payload(intent: str, profile_name: Optional[str], cliente_contexto: Optional[dict], detail: dict, recent_messages: list[dict]):
    config = get_sendgrid_config()
    if not config:
        return None

    route_map = {
        "reclamos": config.get("reclamos_to_email") or config.get("from_email"),
        "ventas": config.get("ventas_to_email") or config.get("from_email"),
        "contabilidad": config.get("contabilidad_to_email") or config.get("from_email"),
    }
    to_email = route_map.get(intent)
    if not to_email:
        return None

    cliente_label = (cliente_contexto or {}).get("nombre_cliente") or profile_name or "Cliente Ferreinox"
    cliente_codigo = (cliente_contexto or {}).get("cliente_codigo") or "sin_codigo"
    transcript_rows = []
    for row in recent_messages[-8:]:
        direction = "Cliente" if row.get("direction") == "inbound" else "Agente"
        contenido = (row.get("contenido") or "").strip()
        if contenido:
            transcript_rows.append((direction, contenido[:1200]))

    transcript_html = "".join(
        f"<tr><td style='padding:8px;border-bottom:1px solid #e5e7eb;font-weight:600'>{escape(direction)}</td><td style='padding:8px;border-bottom:1px solid #e5e7eb'>{escape(contenido)}</td></tr>"
        for direction, contenido in transcript_rows
    ) or "<tr><td colspan='2' style='padding:8px'>Sin historial disponible.</td></tr>"
    transcript_text = "\n".join(f"{direction}: {contenido}" for direction, contenido in transcript_rows) or "Sin historial disponible."

    if intent == "ventas":
        request_label = "Pedido" if detail.get("intent") == "pedido" else "Cotización"
        store_filters = detail.get("store_filters") or []
        store_name = STORE_CODE_LABELS.get(store_filters[0]) if len(store_filters) == 1 else (", ".join(STORE_CODE_LABELS.get(code, code) for code in store_filters) if store_filters else "Pendiente")
        items_html = "".join(
            f"<li style='margin:0 0 8px 0'>{escape(summarize_commercial_item(item))}</li>"
            for item in (detail.get("items") or [])
            if item.get("status") == "matched"
        ) or "<li>Sin líneas confirmadas.</li>"
        items_text = "\n".join(
            f"- {summarize_commercial_item(item)}"
            for item in (detail.get("items") or [])
            if item.get("status") == "matched"
        ) or "- Sin líneas confirmadas."
        subject = f"Ferreinox CRM | {request_label} cliente {cliente_label}"
        html_content = (
            "<div style='font-family:Segoe UI,Arial,sans-serif;color:#111827;background:#f3f4f6;padding:24px'>"
            "<div style='max-width:900px;margin:0 auto;background:#ffffff;border-radius:18px;overflow:hidden;border:1px solid #e5e7eb'>"
            "<div style='background:#111827;color:#ffffff;padding:24px 28px'>"
            f"<h1 style='margin:0;font-size:24px'>{request_label} preparado desde CRM Ferreinox</h1>"
            "<p style='margin:8px 0 0 0;color:#d1d5db'>Solicitud comercial consolidada desde el agente conversacional.</p>"
            "</div>"
            "<div style='padding:28px'>"
            f"<p><strong>Cliente:</strong> {escape(cliente_label)}</p>"
            f"<p><strong>Código cliente:</strong> {escape(str(cliente_codigo))}</p>"
            f"<p><strong>Tienda/Ciudad:</strong> {escape(store_name)}</p>"
            f"<p><strong>Canal solicitado:</strong> {escape(detail.get('delivery_channel') or 'chat')}</p>"
            f"<p><strong>Correo cliente:</strong> {escape(detail.get('contact_email') or (cliente_contexto or {}).get('email') or 'Pendiente')}</p>"
            "<h2 style='margin-top:28px;font-size:18px'>Líneas consolidadas</h2>"
            f"<ul style='padding-left:20px'>{items_html}</ul>"
            "<p style='margin-top:20px;color:#4b5563'>Esta solicitud quedó lista para revisión comercial. Por ahora no incluye precios automáticos desde PostgREST.</p>"
            "<h2 style='margin-top:28px;font-size:18px'>Historial reciente</h2>"
            "<table style='width:100%;border-collapse:collapse;font-size:14px'>"
            f"{transcript_html}"
            "</table>"
            "</div></div></div>"
        )
        text_content = (
            f"{request_label} preparado desde CRM Ferreinox\n\n"
            f"Cliente: {cliente_label}\n"
            f"Código cliente: {cliente_codigo}\n"
            f"Tienda/Ciudad: {store_name}\n"
            f"Canal solicitado: {detail.get('delivery_channel') or 'chat'}\n"
            f"Correo cliente: {detail.get('contact_email') or (cliente_contexto or {}).get('email') or 'Pendiente'}\n\n"
            f"Líneas consolidadas:\n{items_text}\n\n"
            "Esta solicitud quedó lista para revisión comercial. Por ahora no incluye precios automáticos desde PostgREST.\n\n"
            f"Historial reciente:\n{transcript_text}"
        )
        return {"to_email": to_email, "subject": subject, "html_content": html_content, "text_content": text_content}

    subject = f"Ferreinox CRM | Reclamo cliente {cliente_label} | {detail.get('product_label') or 'sin producto'}"
    html_content = (
        "<div style='font-family:Segoe UI,Arial,sans-serif;color:#111827;background:#f3f4f6;padding:24px'>"
        "<div style='max-width:900px;margin:0 auto;background:#ffffff;border-radius:18px;overflow:hidden;border:1px solid #e5e7eb'>"
        "<div style='background:#111827;color:#ffffff;padding:24px 28px'>"
        "<h1 style='margin:0;font-size:24px'>Caso radicado desde CRM Ferreinox</h1>"
        "<p style='margin:8px 0 0 0;color:#d1d5db'>Reclamo de calidad o funcionamiento generado por el agente conversacional.</p>"
        "</div>"
        "<div style='padding:28px'>"
        f"<p><strong>Cliente:</strong> {escape(cliente_label)}</p>"
        f"<p><strong>Código cliente:</strong> {escape(str(cliente_codigo))}</p>"
        f"<p><strong>Producto reportado:</strong> {escape(detail.get('product_label') or 'Pendiente')}</p>"
        f"<p><strong>Tienda/Ciudad:</strong> {escape(detail.get('store_name') or 'Pendiente')}</p>"
        f"<p><strong>Resumen:</strong> {escape(detail.get('issue_summary') or 'Pendiente de ampliar')}</p>"
        "<h2 style='margin-top:28px;font-size:18px'>Historial reciente</h2>"
        "<table style='width:100%;border-collapse:collapse;font-size:14px'>"
        f"{transcript_html}"
        "</table>"
        "</div></div></div>"
    )
    text_content = (
        f"Caso radicado desde CRM Ferreinox\n\n"
        f"Cliente: {cliente_label}\n"
        f"Código cliente: {cliente_codigo}\n"
        f"Producto reportado: {detail.get('product_label') or 'Pendiente'}\n"
        f"Tienda/Ciudad: {detail.get('store_name') or 'Pendiente'}\n"
        f"Resumen: {detail.get('issue_summary') or 'Pendiente de ampliar'}\n\n"
        f"Historial reciente:\n{transcript_text}"
    )
    return {"to_email": to_email, "subject": subject, "html_content": html_content, "text_content": text_content}


def build_customer_claim_confirmation_email(conversation_id: int, profile_name: Optional[str], cliente_contexto: Optional[dict], detail: dict):
    to_email = detail.get("contact_email")
    if not to_email:
        return None

    cliente_label = (cliente_contexto or {}).get("nombre_cliente") or detail.get("cliente") or profile_name or "Cliente Ferreinox"
    cliente_codigo = (cliente_contexto or {}).get("cliente_codigo") or "sin_codigo"
    case_reference = detail.get("case_reference") or f"CRM-{conversation_id}"
    product_label = detail.get("product_label") or "Producto pendiente"
    issue_summary = detail.get("issue_summary") or "Pendiente de ampliar"
    evidence_note = detail.get("evidence_note") or "Pendiente de recibir"
    store_name = detail.get("store_name") or "Pendiente"

    subject = f"Ferreinox | Solicitud radicada {case_reference}"
    html_content = (
        "<div style='font-family:Segoe UI,Arial,sans-serif;background:#f4f6f8;padding:32px;color:#111827'>"
        "<div style='max-width:760px;margin:0 auto;background:#ffffff;border:1px solid #e5e7eb;border-radius:22px;overflow:hidden'>"
        "<div style='background:#111827;padding:28px 32px;color:#ffffff'>"
        "<div style='font-size:12px;letter-spacing:0.18em;text-transform:uppercase;color:#d1d5db'>Ferreinox S.A.S. BIC</div>"
        "<h1 style='margin:10px 0 0 0;font-size:28px;line-height:1.2'>Tu solicitud ya quedó radicada</h1>"
        f"<p style='margin:10px 0 0 0;color:#d1d5db'>Radicado {escape(case_reference)} | Área técnica y servicio</p>"
        "</div>"
        "<div style='padding:32px'>"
        f"<p style='margin:0 0 18px 0'>Hola, {escape(str(cliente_label))}. Ya registramos tu solicitud y nuestro equipo hará seguimiento con esta información:</p>"
        "<div style='background:#f9fafb;border:1px solid #e5e7eb;border-radius:16px;padding:20px'>"
        f"<p style='margin:0 0 10px 0'><strong>Cliente:</strong> {escape(str(cliente_label))}</p>"
        f"<p style='margin:0 0 10px 0'><strong>Código cliente:</strong> {escape(str(cliente_codigo))}</p>"
        f"<p style='margin:0 0 10px 0'><strong>Producto reportado:</strong> {escape(str(product_label))}</p>"
        f"<p style='margin:0 0 10px 0'><strong>Tienda o ciudad:</strong> {escape(str(store_name))}</p>"
        f"<p style='margin:0 0 10px 0'><strong>Detalle del caso:</strong> {escape(str(issue_summary))}</p>"
        f"<p style='margin:0'><strong>Evidencia recibida:</strong> {escape(str(evidence_note))}</p>"
        "</div>"
        "<p style='margin:22px 0 0 0'>Si necesitas ampliar el caso, responde a este correo o escríbenos por WhatsApp y lo anexamos al mismo radicado.</p>"
        "<p style='margin:22px 0 0 0'>Gracias por confiar en Ferreinox.</p>"
        "</div>"
        "</div>"
        "</div>"
    )
    text_content = (
        f"Tu solicitud ya quedó radicada en Ferreinox.\n\n"
        f"Radicado: {case_reference}\n"
        f"Cliente: {cliente_label}\n"
        f"Código cliente: {cliente_codigo}\n"
        f"Producto reportado: {product_label}\n"
        f"Tienda o ciudad: {store_name}\n"
        f"Detalle del caso: {issue_summary}\n"
        f"Evidencia recibida: {evidence_note}\n\n"
        "Si necesitas ampliar el caso, responde este correo o escríbenos por WhatsApp y lo anexamos al mismo radicado."
    )
    return {"to_email": to_email, "subject": subject, "html_content": html_content, "text_content": text_content}


def build_customer_commercial_confirmation_email(conversation_id: int, profile_name: Optional[str], cliente_contexto: Optional[dict], detail: dict):
    to_email = detail.get("contact_email") or (cliente_contexto or {}).get("email")
    if not to_email:
        return None

    request_label = "pedido" if detail.get("intent") == "pedido" else "cotización"
    request_label_title = "Pedido" if detail.get("intent") == "pedido" else "Cotización"
    cliente_label = (cliente_contexto or {}).get("nombre_cliente") or profile_name or "Cliente Ferreinox"
    cliente_codigo = (cliente_contexto or {}).get("cliente_codigo") or "sin_codigo"
    case_reference = f"CRM-{conversation_id}"
    store_filters = detail.get("store_filters") or []
    store_name = STORE_CODE_LABELS.get(store_filters[0]) if len(store_filters) == 1 else (", ".join(STORE_CODE_LABELS.get(code, code) for code in store_filters) if store_filters else "Pendiente")
    items_html = "".join(
        f"<li style='margin:0 0 8px 0'>{escape(summarize_commercial_item(item))}</li>"
        for item in (detail.get("items") or [])
        if item.get("status") == "matched"
    ) or "<li>Sin líneas confirmadas.</li>"
    items_text = "\n".join(
        f"- {summarize_commercial_item(item)}"
        for item in (detail.get("items") or [])
        if item.get("status") == "matched"
    ) or "- Sin líneas confirmadas."

    subject = f"Ferreinox | {request_label_title} preparado {case_reference}"
    html_content = (
        "<div style='font-family:Segoe UI,Arial,sans-serif;background:#f4f6f8;padding:32px;color:#111827'>"
        "<div style='max-width:760px;margin:0 auto;background:#ffffff;border:1px solid #e5e7eb;border-radius:22px;overflow:hidden'>"
        "<div style='background:#111827;padding:28px 32px;color:#ffffff'>"
        "<div style='font-size:12px;letter-spacing:0.18em;text-transform:uppercase;color:#d1d5db'>Ferreinox S.A.S. BIC</div>"
        f"<h1 style='margin:10px 0 0 0;font-size:28px;line-height:1.2'>{request_label_title} preparado</h1>"
        f"<p style='margin:10px 0 0 0;color:#d1d5db'>Solicitud {case_reference}</p>"
        "</div>"
        "<div style='padding:32px'>"
        f"<p style='margin:0 0 18px 0'>Te comparto el resumen de la solicitud de {request_label} que dejamos lista para seguimiento comercial.</p>"
        "<div style='background:#f9fafb;border:1px solid #e5e7eb;border-radius:16px;padding:20px'>"
        f"<p style='margin:0 0 10px 0'><strong>Cliente:</strong> {escape(str(cliente_label))}</p>"
        f"<p style='margin:0 0 10px 0'><strong>Código cliente:</strong> {escape(str(cliente_codigo))}</p>"
        f"<p style='margin:0 0 10px 0'><strong>Tienda o ciudad:</strong> {escape(store_name)}</p>"
        f"<p style='margin:0 0 10px 0'><strong>Canal solicitado:</strong> {escape(detail.get('delivery_channel') or 'chat')}</p>"
        "<div style='margin-top:16px'><strong>Líneas solicitadas:</strong><ul style='margin:10px 0 0 0;padding-left:20px'>"
        f"{items_html}"
        "</ul></div>"
        "</div>"
        "<p style='margin:22px 0 0 0'>Nuestro equipo comercial revisará esta solicitud y continuará el proceso contigo. Por ahora este resumen no incluye precios automáticos.</p>"
        "<p style='margin:22px 0 0 0'>Gracias por confiar en Ferreinox.</p>"
        "</div>"
        "</div>"
        "</div>"
    )
    text_content = (
        f"Ferreinox | {request_label_title} preparado\n\n"
        f"Solicitud: {case_reference}\n"
        f"Cliente: {cliente_label}\n"
        f"Código cliente: {cliente_codigo}\n"
        f"Tienda o ciudad: {store_name}\n"
        f"Canal solicitado: {detail.get('delivery_channel') or 'chat'}\n\n"
        f"Líneas solicitadas:\n{items_text}\n\n"
        "Nuestro equipo comercial revisará esta solicitud y continuará el proceso contigo. Por ahora este resumen no incluye precios automáticos."
    )
    return {"to_email": to_email, "subject": subject, "html_content": html_content, "text_content": text_content}


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
                    f"Ya te identifiqué como {cliente_contexto.get('nombre_cliente') or cliente_contexto.get('cliente_codigo')}, "
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
                    f"Tienes {int(overdue_info['totals'].get('documentos_vencidos') or 0)} facturas vencidas por {overdue_total}. "
                    f"Estas son las principales: {doc_lines}."
                )
            else:
                response_text = (
                    f"Tu cartera vencida es {overdue_total}. "
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
                f"Tu saldo de cartera actual es {saldo}. "
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
                    "response_text": "No encontré una compra registrada para este cliente.",
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
                    f"Tu última compra fue el {latest_purchase.get('fecha_venta')} por {format_currency(totals.get('valor_total'))}. "
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
            response_text = "No encontré compras registradas en los últimos 12 meses para este cliente."
        else:
            top_summary = "; ".join(
                f"{row['nombre_articulo']} ({format_currency(row['valor'])}, {int(float(row['unidades'] or 0))} unidades)"
                for row in product_rows[:5]
            ) or "sin productos destacados"
            if purchase_query.get("has_time_filter"):
                response_text = (
                    f"En {purchase_query.get('label')} compraste {format_currency(totals.get('valor_total'))}. "
                    f"Fueron {int(totals.get('lineas') or 0)} líneas y {int(float(totals.get('unidades_totales') or 0))} unidades. "
                    f"Productos principales: {top_summary}."
                )
            else:
                response_text = (
                    f"En los últimos 12 meses registras compras por {format_currency(totals.get('valor_total'))}. "
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

    if intent == "reclamo_servicio":
        claim_case = extract_claim_case_details(user_message, conversation_context, product_request)
        return build_claim_reply(profile_name, claim_case, cliente_contexto)

    if intent == "cotizacion":
        return build_commercial_flow_reply(intent, profile_name, user_message, conversation_context)

    if intent == "pedido":
        return build_commercial_flow_reply(intent, profile_name, user_message, conversation_context)

    if intent == "consulta_productos":
        if not product_context:
            referencia_solicitada = ", ".join((product_request or {}).get("search_terms") or [])
            return {
                "tono": "informativo",
                "intent": intent,
                "priority": "media",
                "summary": "Consulta de productos sin coincidencia exacta",
                "response_text": (
                    f"Revisé {referencia_solicitada or 'esa referencia'} y no la pude amarrar con una coincidencia clara en inventario. "
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
            direct_response = f"Te confirmé esta referencia: {top_description} ({top_reference})."
            if top_stock is not None and parse_numeric_value(top_stock) and parse_numeric_value(top_stock) > 0:
                direct_response += " La veo disponible"
                if top_row.get("stock_por_tienda"):
                    direct_response += " y con existencias en tienda"
                direct_response += "."
            else:
                direct_response += " En este momento no la veo con existencias disponibles."
            direct_response += " Si quieres, también te reviso otra presentación o una sede puntual."
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
                    "Veo varias opciones muy cercanas. Respóndeme con el número o la referencia y te confirmo la exacta:\n"
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
    cliente_codigo = (cliente_contexto or {}).get("cliente_codigo")
    cliente_nombre = (cliente_contexto or {}).get("nombre_cliente")
    return (
        "Perfecto, ya te pude ubicar"
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
                "Eres el asesor comercial y de servicio al cliente de Ferreinox. Responde en espanol claro, humano, comercial y resolutivo. "
                "Saluda solo en el primer mensaje de la conversacion. Despues conversa con naturalidad, sin repetir el nombre del cliente en cada turno ni usar frases roboticas como 'Resumen del caso' o 'Si necesitas algo mas'. "
                "Mantén una sola intención activa por turno: si el cliente cambia de tema, responde solo sobre el tema nuevo y no mezcles cartera, compras, productos o reclamos en el mismo mensaje. "
                "Debes detectar tono del cliente, intencion principal y prioridad. Usa el contexto ERP disponible para responder con precision. "
                "Si el cliente envía varios productos o una lista, debes procesarlos todos antes de responder y devolver un solo mensaje consolidado. "
                "Nunca vomites la base de datos ni enumeres stock de todas las tiendas si el cliente ya dijo una sede; responde con lenguaje humano y conciso. "
                "En reclamos actua con empatia, pide los datos faltantes uno por uno y solo confirma el radicado cuando ya tengas producto, problema y correo. "
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
                if should_continue_claim_flow(conversation_context, detected_intent, content):
                    detected_intent = "reclamo_servicio"
                if should_continue_commercial_flow(conversation_context, detected_intent, content):
                    detected_intent = conversation_context.get("last_direct_intent")
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

                if detect_context_switch(conversation_context, detected_intent, identity_verification_message):
                    reset_updates = {
                        "pending_product_clarification": None,
                        "pending_document_options": None,
                    }
                    if detected_intent != "reclamo_servicio":
                        reset_updates["claim_case"] = None
                    if detected_intent not in {"pedido", "cotizacion"}:
                        reset_updates["commercial_draft"] = None
                    update_conversation_context(
                        context["conversation_id"],
                        reset_updates,
                        summary=f"Cambio de contexto hacia {detected_intent}",
                    )
                    conversation_context.update(reset_updates)

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
                    response_text = "Hola, ¿en qué te puedo ayudar hoy?"
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
                        caption_text = f"Te comparto el archivo {filename}."
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
                                f"Encontré el archivo {filename}, "
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

                if detected_intent in {"reclamo_servicio", "cotizacion", "pedido"}:
                    direct_result = build_direct_reply(
                        detected_intent,
                        cliente_contexto,
                        [],
                        context.get("nombre_visible"),
                        product_request,
                        content,
                        conversation_context,
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
                            f"No fue posible enviar respuesta operativa: {exc}",
                            {"error": str(exc), "response_text": response_text},
                            intent_detectado=direct_result.get("intent"),
                        )

                    context_updates = {
                        "last_direct_intent": direct_result.get("intent"),
                        "pending_document_options": None,
                        "pending_product_clarification": None,
                        "awaiting_verification": False,
                    }
                    context_updates.update(direct_result.get("conversation_context_updates") or {})

                    commercial_draft = direct_result.get("commercial_draft")
                    if commercial_draft:
                        try:
                            draft_id = upsert_commercial_draft(
                                direct_result.get("intent"),
                                context["conversation_id"],
                                context.get("contact_id"),
                                context.get("cliente_id"),
                                commercial_draft,
                            )
                            context_updates["commercial_draft"] = {
                                **commercial_draft,
                                "draft_id": draft_id,
                            }
                        except Exception as exc:
                            store_outbound_message(
                                context["conversation_id"],
                                None,
                                "system",
                                f"No fue posible guardar borrador comercial: {exc}",
                                {"error": str(exc), "intent": direct_result.get("intent")},
                                intent_detectado=f"borrador_{direct_result.get('intent')}_error",
                            )

                    update_conversation_context(
                        context["conversation_id"],
                        context_updates,
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

                    email_payload = None
                    if direct_result.get("email_route") and not (conversation_context.get("claim_case") or {}).get("submitted"):
                        email_payload = build_operational_email_payload(
                            direct_result.get("email_route"),
                            context.get("nombre_visible"),
                            cliente_contexto,
                            direct_result.get("email_detail") or {},
                            recent_messages,
                        )
                    if email_payload:
                        try:
                            send_sendgrid_email(
                                email_payload["to_email"],
                                email_payload["subject"],
                                email_payload["html_content"],
                                email_payload["text_content"],
                                reply_to=(direct_result.get("email_detail") or {}).get("contact_email") or (cliente_contexto or {}).get("email"),
                            )
                            store_outbound_message(
                                context["conversation_id"],
                                None,
                                "system",
                                f"Correo operativo enviado a {email_payload['to_email']}",
                                {"email_to": email_payload["to_email"], "subject": email_payload["subject"]},
                                intent_detectado=f"correo_{direct_result.get('intent')}",
                            )
                        except Exception as exc:
                            store_outbound_message(
                                context["conversation_id"],
                                None,
                                "system",
                                f"No fue posible enviar correo operativo: {exc}",
                                {"error": str(exc), "email_to": email_payload["to_email"], "subject": email_payload["subject"]},
                                intent_detectado=f"correo_{direct_result.get('intent')}",
                            )

                    customer_email_payload = None
                    if direct_result.get("customer_email_confirmation"):
                        customer_email_payload = build_customer_claim_confirmation_email(
                            context["conversation_id"],
                            context.get("nombre_visible"),
                            cliente_contexto,
                            {
                                **(direct_result.get("customer_email_confirmation") or {}),
                                "case_reference": f"CRM-{context['conversation_id']}",
                            },
                        )
                    elif direct_result.get("commercial_customer_email_confirmation"):
                        customer_email_payload = build_customer_commercial_confirmation_email(
                            context["conversation_id"],
                            context.get("nombre_visible"),
                            cliente_contexto,
                            direct_result.get("commercial_customer_email_confirmation") or {},
                        )
                    if customer_email_payload:
                        try:
                            send_sendgrid_email(
                                customer_email_payload["to_email"],
                                customer_email_payload["subject"],
                                customer_email_payload["html_content"],
                                customer_email_payload["text_content"],
                            )
                            store_outbound_message(
                                context["conversation_id"],
                                None,
                                "system",
                                f"Correo de constancia enviado a {customer_email_payload['to_email']}",
                                {"email_to": customer_email_payload["to_email"], "subject": customer_email_payload["subject"]},
                                intent_detectado="correo_constancia_reclamo",
                            )
                        except Exception as exc:
                            store_outbound_message(
                                context["conversation_id"],
                                None,
                                "system",
                                f"No fue posible enviar constancia al cliente: {exc}",
                                {"error": str(exc), "email_to": customer_email_payload["to_email"], "subject": customer_email_payload["subject"]},
                                intent_detectado="correo_constancia_reclamo",
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