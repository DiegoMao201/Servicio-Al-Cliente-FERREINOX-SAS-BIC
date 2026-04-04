import os
import json
import re
import time
import base64
import tomllib
import unicodedata
import io
import uuid
import hmac
import hashlib
import secrets
from difflib import SequenceMatcher
from datetime import date, timedelta, datetime
from html import escape
from pathlib import Path
from typing import Optional

import dropbox
import pandas as pd
import requests
from fastapi import FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from openai import OpenAI
from openpyxl import Workbook
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, text


app = FastAPI(title="CRM Ferreinox Backend", version="2026.3")


INTERNAL_ROLES = {"empleado", "vendedor", "gerente", "operador", "administrador"}
INTERNAL_SCOPE_TYPES = {"cliente", "vendedor_codigo", "vendedor_nombre", "zona", "almacen"}
INTERNAL_SESSION_TTL_HOURS = int(os.getenv("INTERNAL_AUTH_SESSION_TTL_HOURS", "12"))
INTERNAL_PASSWORD_ITERATIONS = int(os.getenv("INTERNAL_AUTH_PASSWORD_ITERATIONS", "390000"))
INTERNAL_LOGIN_PATTERN = re.compile(r"^\s*login\s+([a-z0-9._-]{3,80})\s+(.+?)\s*$", re.IGNORECASE)
INTERNAL_CEDULA_PATTERN = re.compile(r"\b(\d{6,15})\b")
INTERNAL_LOGOUT_PATTERNS = {
    "logout",
    "salir",
    "cerrar sesion",
    "cerrar sesión",
    "salir interno",
    "logout interno",
}
TRANSFER_REQUEST_MUTATING_ROLES = {"gerente", "operador", "administrador"}
ORDER_DISPATCH_ACTIVE_STATUSES = {"pendiente", "en_transito"}
EMPLOYEE_DIRECTORY_PATH = Path(__file__).resolve().parent.parent / "datos_empleados.xlsx"
EMPLOYEE_DIRECTORY_CACHE_TTL_SECONDS = int(os.getenv("EMPLOYEE_DIRECTORY_CACHE_TTL_SECONDS", "300"))
EMPLOYEE_DIRECTORY_CACHE = {"loaded_at": 0.0, "records": []}
DEFAULT_EMPLOYEE_SEDE_STORE_MAP = {
    "cedi": "155",
    "parque olaya": "189",
    "san antonio": "157",
    "san francisco": "156",
    "opalo": "158",
    "laureles": "238",
    "ferrebox": "439",
    "cerritos": "463",
}
DEFAULT_TRANSFER_DESTINATION_EMAILS = {
    "189": "tiendapintucopereira@ferreinox.co",
    "157": "tiendapintucomanizales@ferreinox.co",
    "158": "tiendapintucodosquebradas@ferreinox.co",
    "156": "tiendapintucoarmenia@ferreinox.co",
    "463": "tiendapintucocerritos@ferreinox.co",
    "238": "tiendapintucolaureles@ferreinox.co",
}
DEFAULT_TRANSFER_CC_EMAILS = ["compras@ferreinox.co"]
CORPORATE_BRAND = {
    "company_name": "FERREINOX S.A.S. BIC",
    "nit": "800.224.617-8",
    "address": "CR 13 19-26, Pereira, Risaralda, Colombia",
    "website": "https://www.ferreinox.co",
    "service_email": "hola@ferreinox.co",
    "pqrs_email": "contacto@ferreinox.co",
    "phone_landline": "(606) 333 0101",
    "phone_mobile": "+57 310 830 5302",
    "phone_mobile_alt": "+57 323 232 8249",
    "brand_dark": "#111827",
    "brand_accent": "#F59E0B",
    "brand_light": "#F9FAFB",
    "brand_border": "#E5E7EB",
}
CORPORATE_LOGO_PATH = Path(__file__).resolve().parent.parent / "LOGO FERREINOX SAS BIC 2024.png"
DEFAULT_FACTURADOR_ROUTING = {
    "155": {"name": "Paula", "phone": "+573102368346"},
    "156": {"name": "Jaime", "phone": "+573165219904"},
    "157": {"name": "Lorena", "phone": "+573136086232"},
    "158": {"name": "M. Paula", "phone": "+573108561506"},
    "189": {"name": "Paula", "phone": "+573102368346"},
    "439": {"name": "Manuel", "phone": "+573209559031"},
    "463": {"name": "Jose Aurelio", "phone": "+573104739586"},
}


class InternalUserScopeInput(BaseModel):
    scope_type: str
    scope_value: str
    scope_label: Optional[str] = None


class InternalBootstrapUserRequest(BaseModel):
    username: str
    password: str
    role: str
    full_name: str
    phone_number: Optional[str] = None
    email: Optional[str] = None
    scopes: list[InternalUserScopeInput] = Field(default_factory=list)


class InternalLoginRequest(BaseModel):
    username: str
    password: str


SECRETS_PATH = Path(__file__).resolve().parent.parent / ".streamlit" / "secrets.toml"
ARTIFACTS_PATH = Path(__file__).resolve().parent.parent / "artifacts"
PRODUCT_NLU_PROMPT_PATH = ARTIFACTS_PATH / "SYSTEM_PROMPT_NLU_EXTRACCION_PRODUCTO.md"
PRODUCT_NLU_PROMPT_FALLBACK = """Eres un extractor NLU para pedidos ferreteros. Devuelve solo JSON válido con las claves cantidad_inferida, presentacion_canonica_inferida, producto_base, color y acabado. Si no sabes un valor, devuelve null. Interpreta 1/5 como cuñete, 1/1 como galon y 1/4 como cuarto. Conserva colores compuestos como verde bronce y no inventes acabados."""
PRODUCT_NLU_PROMPT_CACHE: Optional[str] = None
PRODUCT_NLU_CACHE_MAX_ITEMS = 256
PRODUCT_NLU_CACHE: dict[str, dict] = {}
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


TECHNICAL_ADVISORY_KEYWORDS = [
    "como aplicar",
    "cómo aplicar",
    "como aplico",
    "cómo aplico",
    "como se aplica",
    "cómo se aplica",
    "como pinto",
    "cómo pinto",
    "como pintar",
    "cómo pintar",
    "que rodillo",
    "qué rodillo",
    "que brocha",
    "qué brocha",
    "tiempo de secado",
    "cuanto seca",
    "cuánto seca",
    "cuanto demora",
    "cuánto demora",
    "se puede mezclar",
    "se puede combinar",
    "rendimiento",
    "cuanto rinde",
    "cuánto rinde",
    "manos de pintura",
    "cuantas manos",
    "cuántas manos",
    "preparar la pared",
    "preparar la superficie",
    "lijado",
    "lijar",
    "impermeabilizar",
    "impermeabilizante",
    "diluir",
    "diluyente",
    "que disolvente",
    "qué disolvente",
    "thinner",
    "estuco",
    "estucar",
    "sellar",
    "sellador",
    "para exterior",
    "para interior",
    "anticorrosivo",
    "fondo",
    "imprimante",
    "para madera",
    "para metal",
    "para hierro",
    "para ladrillo",
    "para concreto",
    "diferencia entre",
    "cual es mejor",
    "cuál es mejor",
    "que me recomiendas",
    "qué me recomiendas",
    "que sirve para",
    "qué sirve para",
    "como proteger",
    "cómo proteger",
    "como limpiar",
    "cómo limpiar",
]


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
    "necesito pedido",
    "necesito un pedido",
    "quiero pedido",
    "quiero un pedido",
    "quiero hacer",
    "necesito hacer",
    "a ser un pedido",
    "aser un pedido",
    "acer un pedido",
    "acer pedido",
    "pedir productos",
    "pedir producto",
    "armar pedido",
    "armar un pedido",
    "pasar pedido",
    "pasar un pedido",
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
    "agregale",
    "agregame",
    "agregalo",
    "agrega",
    "ponle",
    "ponme",
    "ponlo",
    "pon",
    "sumale",
    "sumame",
    "suma",
    "quitale",
    "quitame",
    "quita",
    "otro",
    "otra",
    "otros",
    "otras",
    "optro",
    "optra",
    "nuevo",
    "nueva",
    "nuevos",
    "nuevas",
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
    "smith": ["smith", "cinta smith", "tirro smith"],
    "afix": ["afix", "silicona afix", "espuma afix", "epoxi afix"],
    "segurex": ["segurex"],
    "pl285": ["pl285", "pl 285", "pegante pl285", "pegante madera"],
    "koraza": ["koraza"],
}


DIRECTION_ALIASES = {
    "derecha": ["derecha", "derecho", "der", "derc"],
    "izquierda": ["izquierda", "izquierdo", "izq"],
}


STORE_CODE_LABELS = {
    "155": "CEDI",
    "156": "San Francisco - Armenia",
    "157": "San Antonio - Manizales",
    "158": "Ópalo - Dosquebradas",
    "189": "Parque Olaya - Pereira",
    "238": "Laureles",
    "439": "FerreBOX - Pereira",
    "463": "Cerritos",
}


STORE_ALIASES = {
    "cedi": ["155", "cedi", "centro de distribucion", "centro de distribución", "pereira cedi"],
    "armenia": ["156", "armenia", "tienda armenia", "san francisco"],
    "manizales": ["157", "manizales", "tienda manizales", "san antonio"],
    "opalo": ["158", "opalo", "ópalo", "tienda opalo", "tienda ópalo", "dosquebradas"],
    "pereira": ["189", "pereira", "tienda pereira", "parque olaya", "olaya"],
    "laures": ["238", "laures", "laureles", "tienda laures", "tienda laureles"],
    "cerritos": ["463", "cerritos", "tienda cerritos"],
    "ferrebox": ["439", "ferrebox", "ferre box", "tienda ferrebox"],
}


BRAND_ALIASES = {
    "viniltex": ["viniltex", "viniltex adv", "vtx"],
    "domestico": ["domestico", "doméstico", "blanca economica", "blanca económica", "vinilo barato", "p11", "p-11", "p 11"],
    "pintulux": ["pintulux", "pintulux 3en1", "pintulux 3 en 1", "t11", "t-11", "t 11"],
    "koraza": ["koraza"],
    "pintuco": ["pintuco", "viniltex", "domestico", "doméstico", "pintulux", "koraza"],
    "abracol": ["abracol"],
    "yale": ["yale"],
    "goya": ["goya"],
    "smith": ["smith"],
    "afix": ["afix"],
    "segurex": ["segurex"],
    "artecola": ["artecola", "pl285", "pl 285"],
    "montana": ["montana", "montana 94"],
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


def get_product_nlu_system_prompt():
    global PRODUCT_NLU_PROMPT_CACHE
    if PRODUCT_NLU_PROMPT_CACHE is not None:
        return PRODUCT_NLU_PROMPT_CACHE

    try:
        PRODUCT_NLU_PROMPT_CACHE = PRODUCT_NLU_PROMPT_PATH.read_text(encoding="utf-8").strip()
    except Exception:
        PRODUCT_NLU_PROMPT_CACHE = PRODUCT_NLU_PROMPT_FALLBACK

    if not PRODUCT_NLU_PROMPT_CACHE:
        PRODUCT_NLU_PROMPT_CACHE = PRODUCT_NLU_PROMPT_FALLBACK
    return PRODUCT_NLU_PROMPT_CACHE


def normalize_nullable_phrase(raw_value):
    normalized = normalize_text_value(raw_value)
    if normalized in {"", "null", "none", "ninguno", "ninguna", "n/a", "na", "sin", "no aplica"}:
        return None
    return normalized


def canonicalize_presentation_value(raw_value):
    normalized = normalize_text_value(raw_value)
    if not normalized:
        return None
    for canonical_value, aliases in PRESENTATION_ALIASES.items():
        alias_values = {normalize_text_value(alias) for alias in aliases}
        alias_values.add(normalize_text_value(canonical_value))
        if normalized in alias_values:
            return canonical_value
    return None


def merge_unique_terms(*term_groups):
    merged_terms = []
    seen_terms = set()
    for group in term_groups:
        if not group:
            continue
        if isinstance(group, str):
            candidates = [group]
        else:
            candidates = list(group)
        for value in candidates:
            normalized = normalize_text_value(value)
            if not normalized or normalized in seen_terms:
                continue
            seen_terms.add(normalized)
            merged_terms.append(normalized)
    return merged_terms


def tokenize_search_phrase(text_value: Optional[str]):
    normalized = normalize_text_value(text_value)
    if not normalized:
        return []
    return [
        token
        for token in re.findall(r"[a-z0-9.-]+", normalized)
        if len(token) >= 2 and token not in PRODUCT_STOPWORDS and not is_store_alias_term(token)
    ]


def apply_deterministic_product_alias_rules(text_value: Optional[str], prepared_request: dict):
    normalized = normalize_text_value(text_value)
    alias_rules = [
        {
            "pattern": r"\b(blanca economica|blanca economica|la economica|vinilo barato|p11|p-11|p 11)\b",
            "canonical_product": "domestico blanco",
            "brand_filters": ["domestico", "pintuco"],
            "core_terms": ["domestico", "blanco"],
            "color_filters": ["blanco"],
        },
        {
            "pattern": r"\b(t11|t-11|t 11)\b",
            "canonical_product": "pintulux blanco",
            "brand_filters": ["pintulux", "pintuco"],
            "core_terms": ["pintulux", "blanco"],
            "color_filters": ["blanco"],
        },
        {
            "pattern": r"\b(p53|p-53|p 53)\b",
            "canonical_product": "domestico verde esmeralda",
            "brand_filters": ["domestico", "pintuco"],
            "core_terms": ["domestico", "verde esmeralda"],
            "color_filters": ["verde esmeralda"],
        },
        {
            "pattern": r"\b(pl285|pl 285)\b",
            "canonical_product": "pegante pl285 madera",
            "brand_filters": ["artecola"],
            "core_terms": ["pl285", "madera"],
        },
        {
            "pattern": r"\b(pintulux)\b.*\bverde\s+bronce\b|\bverde\s+bronce\b.*\b(pintulux)\b",
            "canonical_product": "pintulux verde bronce",
            "brand_filters": ["pintulux", "pintuco"],
            "core_terms": ["pintulux", "verde bronce"],
            "color_filters": ["verde bronce"],
        },
        {
            "pattern": r"\b(candado\s+yale)\b",
            "canonical_product": "candado yale",
            "brand_filters": ["yale"],
            "core_terms": ["candado", "yale"],
        },
    ]

    for rule in alias_rules:
        if not re.search(rule["pattern"], normalized):
            continue
        if rule.get("canonical_product") and not prepared_request.get("canonical_product"):
            prepared_request["canonical_product"] = rule["canonical_product"]
        prepared_request["brand_filters"] = merge_unique_terms(prepared_request.get("brand_filters"), rule.get("brand_filters"))
        prepared_request["core_terms"] = merge_unique_terms(prepared_request.get("core_terms"), rule.get("core_terms"))
        prepared_request["color_filters"] = merge_unique_terms(prepared_request.get("color_filters"), rule.get("color_filters"))

    if "verde bronce" in normalized:
        prepared_request["color_filters"] = merge_unique_terms(prepared_request.get("color_filters"), ["verde bronce"])
    elif "blanco puro" in normalized:
        prepared_request["color_filters"] = merge_unique_terms(prepared_request.get("color_filters"), ["blanco puro"])
    elif "transparente" in normalized:
        prepared_request["color_filters"] = merge_unique_terms(prepared_request.get("color_filters"), ["transparente"])

    if "mate" in normalized:
        prepared_request["finish_filters"] = merge_unique_terms(prepared_request.get("finish_filters"), ["mate"])
    elif "brillante" in normalized:
        prepared_request["finish_filters"] = merge_unique_terms(prepared_request.get("finish_filters"), ["brillante"])

    yale_size_match = re.search(r"\bcandado\s+yale\b.*?\b(30|40|50|60|70)\s*mm\b", normalized)
    if yale_size_match:
        yale_terms = ["candado", "yale", yale_size_match.group(1)]
        if yale_size_match.group(1) in {"30", "40", "50", "60"}:
            yale_terms.append("italiano")
        prepared_request["canonical_product"] = prepared_request.get("canonical_product") or "candado yale"
        prepared_request["brand_filters"] = merge_unique_terms(prepared_request.get("brand_filters"), ["yale"])
        prepared_request["core_terms"] = merge_unique_terms(prepared_request.get("core_terms"), yale_terms)

    prepared_request["search_terms"] = expand_product_terms(
        merge_unique_terms(
            prepared_request.get("search_terms"),
            prepared_request.get("core_terms"),
            prepared_request.get("color_filters"),
            prepared_request.get("finish_filters"),
        )
    )[:14]
    return prepared_request


def should_attempt_product_nlu(text_value: Optional[str], base_request: Optional[dict]):
    normalized = normalize_text_value(text_value)
    request = base_request or {}
    if not normalized or len(normalized) < 3:
        return False
    if is_technical_document_message(text_value) or is_technical_advisory_message(text_value):
        return False
    if has_non_product_business_signal(text_value) and not (
        request.get("product_codes")
        or request.get("brand_filters")
        or request.get("requested_unit")
        or request.get("requested_quantity")
    ):
        return False

    meaningful_terms = [term for term in (request.get("core_terms") or []) if not is_store_alias_term(term)]
    if request.get("product_codes"):
        return True
    if request.get("brand_filters") or request.get("requested_unit") or request.get("requested_quantity"):
        return True
    if len(meaningful_terms) >= 2:
        return True
    return bool(re.search(r"\b\d+\s*/\s*(1|4|5)\b", normalized))


def extract_product_entities_with_llm(text_value: Optional[str], base_request: Optional[dict] = None):
    normalized = normalize_text_value(text_value)
    if not should_attempt_product_nlu(text_value, base_request):
        return {}
    if not get_openai_api_key():
        return {}
    if normalized in PRODUCT_NLU_CACHE:
        return dict(PRODUCT_NLU_CACHE[normalized])

    try:
        response = get_openai_client().responses.create(
            model=get_openai_model(),
            input=[
                {"role": "system", "content": get_product_nlu_system_prompt()},
                {"role": "user", "content": text_value or ""},
            ],
            temperature=0,
            text={"format": {"type": "json_object"}},
        )
        parsed = extract_json_object(response.output_text)
    except Exception:
        return {}

    nlu_payload = {
        "cantidad_inferida": parse_numeric_value(parsed.get("cantidad_inferida")),
        "presentacion_canonica_inferida": canonicalize_presentation_value(parsed.get("presentacion_canonica_inferida")),
        "producto_base": normalize_nullable_phrase(parsed.get("producto_base")),
        "color": normalize_nullable_phrase(parsed.get("color")),
        "acabado": normalize_nullable_phrase(parsed.get("acabado")),
    }
    if not any(nlu_payload.values()):
        return {}

    if len(PRODUCT_NLU_CACHE) >= PRODUCT_NLU_CACHE_MAX_ITEMS:
        PRODUCT_NLU_CACHE.pop(next(iter(PRODUCT_NLU_CACHE)))
    PRODUCT_NLU_CACHE[normalized] = dict(nlu_payload)
    return nlu_payload


def prepare_product_request_for_search(text_value: Optional[str], product_request: Optional[dict] = None):
    prepared_request = dict(product_request or extract_product_request(text_value))
    if prepared_request.get("nlu_processed"):
        return prepared_request

    prepared_request.setdefault("color_filters", [])
    prepared_request.setdefault("finish_filters", [])
    prepared_request = apply_deterministic_product_alias_rules(text_value, prepared_request)

    nlu_payload = extract_product_entities_with_llm(text_value, prepared_request)
    prepared_request["nlu_processed"] = True
    prepared_request["nlu_extraction"] = nlu_payload or None

    if not nlu_payload:
        return prepared_request

    canonical_product = nlu_payload.get("producto_base")
    canonical_color = nlu_payload.get("color")
    canonical_finish = nlu_payload.get("acabado")
    canonical_presentation = nlu_payload.get("presentacion_canonica_inferida")
    inferred_quantity = nlu_payload.get("cantidad_inferida")

    if inferred_quantity is not None and prepared_request.get("requested_quantity") is None:
        prepared_request["requested_quantity"] = inferred_quantity
    if canonical_presentation and not prepared_request.get("requested_unit"):
        prepared_request["requested_unit"] = canonical_presentation

    if canonical_product:
        prepared_request["canonical_product"] = canonical_product
    if canonical_color:
        prepared_request["color_filters"] = merge_unique_terms(prepared_request.get("color_filters"), [canonical_color], tokenize_search_phrase(canonical_color))
    if canonical_finish:
        prepared_request["finish_filters"] = merge_unique_terms(prepared_request.get("finish_filters"), [canonical_finish], tokenize_search_phrase(canonical_finish))

    merged_core_terms = merge_unique_terms(
        prepared_request.get("core_terms"),
        [canonical_product] if canonical_product else [],
        tokenize_search_phrase(canonical_product),
        prepared_request.get("color_filters"),
        prepared_request.get("finish_filters"),
    )
    prepared_request["core_terms"] = merged_core_terms[:10]

    merged_search_terms = merge_unique_terms(
        prepared_request.get("search_terms"),
        merged_core_terms,
        [canonical_presentation] if canonical_presentation else [],
    )
    prepared_request["search_terms"] = expand_product_terms(merged_search_terms)[:14]

    derived_brand_filters = extract_brand_filters(
        " ".join(
            value
            for value in [canonical_product, canonical_color, canonical_finish]
            if value
        )
    )
    prepared_request["brand_filters"] = merge_unique_terms(prepared_request.get("brand_filters"), derived_brand_filters)
    return prepared_request


def get_db_engine():
    return create_engine(get_database_url())


def safe_json_dumps(value):
    return json.dumps(value, ensure_ascii=False, default=str)


def normalize_internal_username(username: Optional[str]):
    normalized = (username or "").strip().lower()
    if not re.fullmatch(r"[a-z0-9._-]{3,80}", normalized):
        raise HTTPException(status_code=400, detail="El usuario interno debe usar solo letras, números, punto, guion o guion bajo.")
    return normalized


def normalize_phone_e164(phone_number: Optional[str]):
    digits = "".join(character for character in str(phone_number or "") if character.isdigit())
    if not digits:
        return None
    if digits.startswith("57") and len(digits) >= 12:
        return f"+{digits}"
    if len(digits) == 10:
        return f"+57{digits}"
    return f"+{digits}"


def normalize_employee_header(value: Optional[str]):
    return normalize_text_value(value).replace("�", "")


def parse_employee_document(value: Optional[str]):
    digits = "".join(character for character in str(value or "") if character.isdigit())
    return digits or None


def parse_employee_phone(value: Optional[str]):
    return normalize_phone_e164(value)


def load_employee_sede_store_map():
    configured = {}
    raw_json = os.getenv("EMPLOYEE_SEDE_STORE_MAP_JSON")
    if raw_json:
        try:
            configured = json.loads(raw_json)
        except Exception as exc:
            raise RuntimeError(f"EMPLOYEE_SEDE_STORE_MAP_JSON inválido: {exc}")
    merged = {**DEFAULT_EMPLOYEE_SEDE_STORE_MAP}
    for raw_key, raw_value in (configured or {}).items():
        key = normalize_text_value(raw_key)
        store_code = normalize_store_code(str(raw_value)) or str(raw_value).strip()
        if key and store_code:
            merged[key] = store_code
    return merged


def resolve_store_code_from_employee_sede(sede_value: Optional[str]):
    normalized_sede = normalize_text_value(sede_value)
    if not normalized_sede:
        return None
    mapped_code = load_employee_sede_store_map().get(normalized_sede)
    if mapped_code:
        return normalize_store_code(mapped_code) or mapped_code
    return normalize_store_code(normalized_sede)


def derive_internal_role_from_employee(record: dict):
    cargo = normalize_text_value(record.get("cargo"))
    if not cargo:
        return "empleado"
    if "administr" in cargo or "director" in cargo or ("lider" in cargo and "compras" in cargo):
        return "administrador"
    if "gerente" in cargo:
        return "gerente"
    if any(token in cargo for token in ["vendedor", "asesor comercial", "representante de ventas", "mostrador"]):
        return "vendedor"
    if any(token in cargo for token in ["lider", "líder", "facturacion", "facturación", "logistica", "logística", "inventario", "cartera", "tesoreria", "tesorería", "compras"]):
        return "operador"
    return "empleado"


def employee_has_advanced_access(record: dict):
    role = derive_internal_role_from_employee(record)
    return role in {"vendedor", "gerente", "operador", "administrador"}


def employee_can_manage_transfers(record: dict):
    cargo = normalize_text_value(record.get("cargo"))
    return any(
        token in cargo
        for token in [
            "lider de tienda",
            "líder de tienda",
            "lider logistica",
            "líder logística",
            "lider de inventario",
            "líder de inventario",
            "facturacion y despachos",
            "facturación y despachos",
            "auxiliar de mostrador y facturacion",
            "auxiliar de mostrador y facturación",
            "auxiliar logistico",
            "auxiliar logístico",
            "gestor logistico",
            "gestor logístico",
        ]
    )


def load_employee_directory(force_refresh: bool = False):
    cache_age = time.time() - float(EMPLOYEE_DIRECTORY_CACHE.get("loaded_at") or 0)
    if not force_refresh and EMPLOYEE_DIRECTORY_CACHE.get("records") and cache_age < EMPLOYEE_DIRECTORY_CACHE_TTL_SECONDS:
        return EMPLOYEE_DIRECTORY_CACHE["records"]

    if not EMPLOYEE_DIRECTORY_PATH.exists():
        EMPLOYEE_DIRECTORY_CACHE.update({"loaded_at": time.time(), "records": []})
        return []

    dataframe = pd.read_excel(EMPLOYEE_DIRECTORY_PATH)
    normalized_columns = {normalize_employee_header(column): column for column in dataframe.columns}

    def get_column(*aliases):
        for alias in aliases:
            column = normalized_columns.get(normalize_employee_header(alias))
            if column:
                return column
        return None

    full_name_column = get_column("nombre completo", "nombre", "nombre empleado")
    document_column = get_column("cedula", "cédula")
    sede_column = get_column("sede")
    cargo_column = get_column("cargo")
    phone_column = get_column("telefono", "teléfono")
    email_column = get_column("correo electronico", "correo electrónico", "correo")

    if not full_name_column or not document_column:
        raise RuntimeError(f"datos_empleados.xlsx no tiene columnas mínimas esperadas. Columnas detectadas: {list(dataframe.columns)}")

    records = []
    for _, row in dataframe.iterrows():
        full_name = str(row.get(full_name_column) or "").strip()
        cedula = parse_employee_document(row.get(document_column))
        if not full_name or not cedula:
            continue
        sede = str(row.get(sede_column) or "").strip() if sede_column else ""
        cargo = str(row.get(cargo_column) or "").strip() if cargo_column else ""
        phone_e164 = parse_employee_phone(row.get(phone_column)) if phone_column else None
        email = str(row.get(email_column) or "").strip().lower() if email_column else None
        role = derive_internal_role_from_employee({"cargo": cargo})
        store_code = resolve_store_code_from_employee_sede(sede)
        records.append(
            {
                "full_name": full_name,
                "cedula": cedula,
                "sede": sede,
                "cargo": cargo,
                "phone_e164": phone_e164,
                "email": email,
                "store_code": store_code,
                "role": role,
                "advanced_access": employee_has_advanced_access({"cargo": cargo}),
                "is_facturador": employee_can_manage_transfers({"cargo": cargo}),
            }
        )

    EMPLOYEE_DIRECTORY_CACHE.update({"loaded_at": time.time(), "records": records})
    return records


def find_employee_record_by_phone(phone_e164: Optional[str]):
    normalized_phone = normalize_phone_e164(phone_e164)
    if not normalized_phone:
        return None
    for record in load_employee_directory():
        if record.get("phone_e164") == normalized_phone:
            return record
    fallback_record = fetch_internal_employee_record_by_phone(normalized_phone)
    if fallback_record:
        return fallback_record
    return None


def find_employee_record_by_cedula(document_value: Optional[str]):
    normalized_document = parse_employee_document(document_value)
    if not normalized_document:
        return None
    for record in load_employee_directory():
        if record.get("cedula") == normalized_document:
            return record
    fallback_record = fetch_internal_employee_record_by_cedula(normalized_document)
    if fallback_record:
        return fallback_record
    return None


def build_employee_username(record: dict):
    return f"cedula.{record.get('cedula')}"


def extract_internal_cedula_candidate(content: Optional[str]):
    raw_content = (content or "").strip()
    if not raw_content:
        return None

    normalized = normalize_text_value(raw_content)
    if any(fragment in normalized for fragment in ["login ", "pedido", "cotizacion", "cotización", "traslado", "galon", "galón", "cunete", "cuñete"]):
        labeled_match = re.search(r"(?:cedula|cédula|documento|doc)\s*(?:es|:)?\s*([0-9][0-9.\s-]{5,})", raw_content, re.IGNORECASE)
        if labeled_match:
            labeled_digits = parse_employee_document(labeled_match.group(1))
            if labeled_digits and 6 <= len(labeled_digits) <= 15:
                return labeled_digits
        compact_digits = parse_employee_document(raw_content)
        if compact_digits and 6 <= len(compact_digits) <= 15 and re.fullmatch(r"[0-9.\s-]+", raw_content):
            return compact_digits
        return None

    match = INTERNAL_CEDULA_PATTERN.search(raw_content)
    if match:
        return match.group(1)
    digits = parse_employee_document(raw_content)
    if digits and 6 <= len(digits) <= 15:
        return digits
    return None


def build_employee_record_from_internal_user_row(user_row: Optional[dict]):
    if not user_row:
        return None
    metadata = dict(user_row.get("metadata") or {})
    cedula = parse_employee_document(metadata.get("cedula"))
    if not cedula:
        username_match = re.fullmatch(r"cedula\.(\d{6,15})", str(user_row.get("username") or ""))
        cedula = username_match.group(1) if username_match else None
    if not cedula:
        return None
    role_value = user_row.get("role") or derive_internal_role_from_employee({"cargo": metadata.get("cargo")})
    return {
        "full_name": user_row.get("full_name"),
        "cedula": cedula,
        "sede": metadata.get("sede"),
        "cargo": metadata.get("cargo"),
        "phone_e164": normalize_phone_e164(user_row.get("phone_e164") or metadata.get("telefono")),
        "email": (user_row.get("email") or metadata.get("email") or "").strip().lower() or None,
        "store_code": normalize_store_code(metadata.get("store_code")),
        "role": role_value,
        "advanced_access": bool(metadata.get("advanced_access", role_value in {"vendedor", "gerente", "operador", "administrador"})),
        "is_facturador": bool(metadata.get("is_facturador", role_value == "administrador")),
        "auth_source": metadata.get("auth_source") or "agent_user",
    }


def fetch_internal_employee_record_by_phone(phone_e164: Optional[str]):
    normalized_phone = normalize_phone_e164(phone_e164)
    if not normalized_phone:
        return None
    ensure_internal_auth_tables()
    engine = get_db_engine()
    with engine.connect() as connection:
        row = connection.execute(
            text(
                """
                SELECT id, username, full_name, role, phone_e164, email, metadata
                FROM public.agent_user
                WHERE is_active = true
                  AND phone_e164 = :phone_e164
                ORDER BY updated_at DESC
                LIMIT 1
                """
            ),
            {"phone_e164": normalized_phone},
        ).mappings().one_or_none()
    return build_employee_record_from_internal_user_row(dict(row) if row else None)


def fetch_internal_employee_record_by_cedula(document_value: Optional[str]):
    normalized_document = parse_employee_document(document_value)
    if not normalized_document:
        return None
    ensure_internal_auth_tables()
    engine = get_db_engine()
    with engine.connect() as connection:
        row = connection.execute(
            text(
                """
                SELECT id, username, full_name, role, phone_e164, email, metadata
                FROM public.agent_user
                WHERE is_active = true
                  AND (
                    metadata ->> 'cedula' = :cedula
                    OR username = :username
                  )
                ORDER BY updated_at DESC
                LIMIT 1
                """
            ),
            {"cedula": normalized_document, "username": f"cedula.{normalized_document}"},
        ).mappings().one_or_none()
    return build_employee_record_from_internal_user_row(dict(row) if row else None)


def hash_password_with_salt(password: str, salt_hex: str):
    return hashlib.pbkdf2_hmac(
        "sha256",
        (password or "").encode("utf-8"),
        bytes.fromhex(salt_hex),
        INTERNAL_PASSWORD_ITERATIONS,
    ).hex()


def build_password_credentials(password: str):
    if not password or len(password) < 8:
        raise HTTPException(status_code=400, detail="La contraseña interna debe tener al menos 8 caracteres.")
    salt_hex = secrets.token_hex(16)
    return salt_hex, hash_password_with_salt(password, salt_hex)


def verify_password_hash(password: str, salt_hex: str, expected_hash: str):
    calculated_hash = hash_password_with_salt(password, salt_hex)
    return hmac.compare_digest(calculated_hash, expected_hash)


def hash_session_token(raw_token: str):
    return hashlib.sha256((raw_token or "").encode("utf-8")).hexdigest()


def ensure_internal_auth_tables():
    engine = get_db_engine()
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS public.agent_user (
                    id bigserial PRIMARY KEY,
                    username varchar(80) NOT NULL,
                    full_name varchar(180) NOT NULL,
                    role varchar(30) NOT NULL,
                    password_salt varchar(128) NOT NULL,
                    password_hash varchar(256) NOT NULL,
                    phone_e164 varchar(30),
                    email varchar(180),
                    is_active boolean NOT NULL DEFAULT true,
                    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
                    created_at timestamptz NOT NULL DEFAULT now(),
                    updated_at timestamptz NOT NULL DEFAULT now(),
                    CONSTRAINT uq_agent_user_username UNIQUE (username),
                    CONSTRAINT uq_agent_user_phone UNIQUE (phone_e164)
                )
                """
            )
        )
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS public.agent_user_scope (
                    id bigserial PRIMARY KEY,
                    user_id bigint NOT NULL REFERENCES public.agent_user(id) ON DELETE CASCADE,
                    scope_type varchar(40) NOT NULL,
                    scope_value varchar(180) NOT NULL,
                    scope_label varchar(180),
                    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
                    created_at timestamptz NOT NULL DEFAULT now(),
                    updated_at timestamptz NOT NULL DEFAULT now(),
                    CONSTRAINT uq_agent_user_scope UNIQUE (user_id, scope_type, scope_value)
                )
                """
            )
        )
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS public.agent_user_session (
                    id bigserial PRIMARY KEY,
                    user_id bigint NOT NULL REFERENCES public.agent_user(id) ON DELETE CASCADE,
                    token_hash varchar(128) NOT NULL,
                    channel varchar(30) NOT NULL DEFAULT 'api',
                    contact_id bigint REFERENCES public.whatsapp_contacto(id) ON DELETE SET NULL,
                    phone_e164 varchar(30),
                    expires_at timestamptz NOT NULL,
                    last_used_at timestamptz,
                    revoked_at timestamptz,
                    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
                    created_at timestamptz NOT NULL DEFAULT now(),
                    updated_at timestamptz NOT NULL DEFAULT now(),
                    CONSTRAINT uq_agent_user_session_token UNIQUE (token_hash)
                )
                """
            )
        )
        connection.execute(text("ALTER TABLE public.agent_user DROP CONSTRAINT IF EXISTS chk_agent_user_role"))
        connection.execute(
            text(
                """
                ALTER TABLE public.agent_user
                ADD CONSTRAINT chk_agent_user_role
                CHECK (role IN ('empleado', 'vendedor', 'gerente', 'operador', 'administrador'))
                """
            )
        )
        connection.execute(text("ALTER TABLE public.agent_user_scope DROP CONSTRAINT IF EXISTS chk_agent_user_scope_type"))
        connection.execute(
            text(
                """
                ALTER TABLE public.agent_user_scope
                ADD CONSTRAINT chk_agent_user_scope_type
                CHECK (scope_type IN ('cliente', 'vendedor_codigo', 'vendedor_nombre', 'zona', 'almacen'))
                """
            )
        )
        connection.execute(text("ALTER TABLE public.agent_user_session DROP CONSTRAINT IF EXISTS chk_agent_user_session_channel"))
        connection.execute(
            text(
                """
                ALTER TABLE public.agent_user_session
                ADD CONSTRAINT chk_agent_user_session_channel
                CHECK (channel IN ('api', 'whatsapp'))
                """
            )
        )


def fetch_internal_user_scopes(user_id: int):
    ensure_internal_auth_tables()
    engine = get_db_engine()
    with engine.connect() as connection:
        rows = connection.execute(
            text(
                """
                SELECT scope_type, scope_value, scope_label
                FROM public.agent_user_scope
                WHERE user_id = :user_id
                ORDER BY scope_type, scope_value
                """
            ),
            {"user_id": user_id},
        ).mappings().all()
    return [dict(row) for row in rows]


def fetch_internal_user_by_username(username: str):
    ensure_internal_auth_tables()
    normalized_username = normalize_internal_username(username)
    engine = get_db_engine()
    with engine.connect() as connection:
        row = connection.execute(
            text(
                """
                SELECT id, username, full_name, role, password_salt, password_hash,
                       phone_e164, email, is_active, metadata
                FROM public.agent_user
                WHERE username = :username
                LIMIT 1
                """
            ),
            {"username": normalized_username},
        ).mappings().one_or_none()
    if not row:
        return None
    user_payload = dict(row)
    user_payload["scopes"] = fetch_internal_user_scopes(user_payload["id"])
    return user_payload


def fetch_internal_user_by_id(user_id: int):
    ensure_internal_auth_tables()
    engine = get_db_engine()
    with engine.connect() as connection:
        row = connection.execute(
            text(
                """
                SELECT id, username, full_name, role, phone_e164, email, is_active, metadata
                FROM public.agent_user
                WHERE id = :user_id
                LIMIT 1
                """
            ),
            {"user_id": user_id},
        ).mappings().one_or_none()
    if not row:
        return None
    user_payload = dict(row)
    user_payload["scopes"] = fetch_internal_user_scopes(user_payload["id"])
    return user_payload


def sync_internal_user_from_employee_record(record: dict):
    ensure_internal_auth_tables()
    username = build_employee_username(record)
    metadata = {
        "auth_source": "datos_empleados.xlsx",
        "cedula": record.get("cedula"),
        "sede": record.get("sede"),
        "cargo": record.get("cargo"),
        "store_code": record.get("store_code"),
        "advanced_access": bool(record.get("advanced_access")),
        "is_facturador": bool(record.get("is_facturador")),
    }

    engine = get_db_engine()
    with engine.begin() as connection:
        existing_row = connection.execute(
            text(
                """
                SELECT id
                FROM public.agent_user
                WHERE username = :username
                LIMIT 1
                """
            ),
            {"username": username},
        ).mappings().one_or_none()

        if existing_row:
            user_id = existing_row["id"]
            connection.execute(
                text(
                    """
                    UPDATE public.agent_user
                    SET full_name = :full_name,
                        role = :role,
                        phone_e164 = :phone_e164,
                        email = :email,
                        metadata = CAST(:metadata AS jsonb),
                        is_active = true,
                        updated_at = now()
                    WHERE id = :user_id
                    """
                ),
                {
                    "user_id": user_id,
                    "full_name": record.get("full_name"),
                    "role": record.get("role") or "empleado",
                    "phone_e164": record.get("phone_e164"),
                    "email": record.get("email"),
                    "metadata": safe_json_dumps(metadata),
                },
            )
        else:
            salt_hex, password_hash = build_password_credentials(f"ExcelAuth-{record.get('cedula')}-Fx")
            user_id = connection.execute(
                text(
                    """
                    INSERT INTO public.agent_user (
                        username, full_name, role, password_salt, password_hash, phone_e164, email, is_active, metadata, created_at, updated_at
                    )
                    VALUES (
                        :username, :full_name, :role, :password_salt, :password_hash, :phone_e164, :email, true, CAST(:metadata AS jsonb), now(), now()
                    )
                    RETURNING id
                    """
                ),
                {
                    "username": username,
                    "full_name": record.get("full_name"),
                    "role": record.get("role") or "empleado",
                    "password_salt": salt_hex,
                    "password_hash": password_hash,
                    "phone_e164": record.get("phone_e164"),
                    "email": record.get("email"),
                    "metadata": safe_json_dumps(metadata),
                },
            ).scalar_one()

        connection.execute(text("DELETE FROM public.agent_user_scope WHERE user_id = :user_id"), {"user_id": user_id})
        if record.get("store_code"):
            connection.execute(
                text(
                    """
                    INSERT INTO public.agent_user_scope (
                        user_id, scope_type, scope_value, scope_label, created_at, updated_at
                    ) VALUES (
                        :user_id, 'almacen', :scope_value, :scope_label, now(), now()
                    )
                    """
                ),
                {
                    "user_id": user_id,
                    "scope_value": record.get("store_code"),
                    "scope_label": record.get("sede") or record.get("store_code"),
                },
            )

    return fetch_internal_user_by_id(user_id)


def build_internal_auth_context(user_payload: dict, token: str, expires_at: Optional[str]):
    metadata = dict(user_payload.get("metadata") or {})
    return {
        "token": token,
        "user_id": user_payload.get("id"),
        "username": user_payload.get("username"),
        "role": user_payload.get("role"),
        "expires_at": expires_at,
        "employee_context": {
            "full_name": user_payload.get("full_name"),
            "cedula": metadata.get("cedula"),
            "sede": metadata.get("sede"),
            "cargo": metadata.get("cargo"),
            "telefono": user_payload.get("phone_e164"),
            "store_code": metadata.get("store_code"),
            "advanced_access": metadata.get("advanced_access", False),
            "is_facturador": metadata.get("is_facturador", False),
        },
    }


def internal_user_has_advanced_access(user_payload: dict):
    if (user_payload or {}).get("role") in {"vendedor", "gerente", "operador", "administrador"}:
        return True
    metadata = dict((user_payload or {}).get("metadata") or {})
    return bool(metadata.get("advanced_access"))


def internal_user_can_manage_transfers(user_payload: dict):
    if (user_payload or {}).get("role") == "administrador":
        return True
    metadata = dict((user_payload or {}).get("metadata") or {})
    return bool(metadata.get("is_facturador"))


def upsert_internal_user(user_request: InternalBootstrapUserRequest):
    ensure_internal_auth_tables()
    role = (user_request.role or "").strip().lower()
    if role not in INTERNAL_ROLES:
        raise HTTPException(status_code=400, detail="Rol interno inválido.")

    normalized_username = normalize_internal_username(user_request.username)
    phone_e164 = normalize_phone_e164(user_request.phone_number)
    salt_hex, password_hash = build_password_credentials(user_request.password)
    normalized_scopes = []
    for scope in user_request.scopes:
        scope_type = (scope.scope_type or "").strip().lower()
        if scope_type not in INTERNAL_SCOPE_TYPES:
            raise HTTPException(status_code=400, detail=f"Tipo de alcance no válido: {scope.scope_type}")
        scope_value = normalize_text_value(scope.scope_value)
        if not scope_value:
            raise HTTPException(status_code=400, detail="Todos los alcances deben tener un valor válido.")
        normalized_scopes.append(
            {
                "scope_type": scope_type,
                "scope_value": scope_value,
                "scope_label": scope.scope_label,
            }
        )

    engine = get_db_engine()
    with engine.begin() as connection:
        existing_row = connection.execute(
            text(
                """
                SELECT id
                FROM public.agent_user
                WHERE username = :username
                LIMIT 1
                """
            ),
            {"username": normalized_username},
        ).mappings().one_or_none()

        if existing_row:
            user_id = existing_row["id"]
            connection.execute(
                text(
                    """
                    UPDATE public.agent_user
                    SET full_name = :full_name,
                        role = :role,
                        password_salt = :password_salt,
                        password_hash = :password_hash,
                        phone_e164 = :phone_e164,
                        email = :email,
                        is_active = true,
                        updated_at = now()
                    WHERE id = :user_id
                    """
                ),
                {
                    "user_id": user_id,
                    "full_name": user_request.full_name,
                    "role": role,
                    "password_salt": salt_hex,
                    "password_hash": password_hash,
                    "phone_e164": phone_e164,
                    "email": user_request.email,
                },
            )
            connection.execute(text("DELETE FROM public.agent_user_scope WHERE user_id = :user_id"), {"user_id": user_id})
        else:
            user_id = connection.execute(
                text(
                    """
                    INSERT INTO public.agent_user (
                        username, full_name, role, password_salt, password_hash, phone_e164, email, is_active, created_at, updated_at
                    )
                    VALUES (
                        :username, :full_name, :role, :password_salt, :password_hash, :phone_e164, :email, true, now(), now()
                    )
                    RETURNING id
                    """
                ),
                {
                    "username": normalized_username,
                    "full_name": user_request.full_name,
                    "role": role,
                    "password_salt": salt_hex,
                    "password_hash": password_hash,
                    "phone_e164": phone_e164,
                    "email": user_request.email,
                },
            ).scalar_one()

        for scope in normalized_scopes:
            connection.execute(
                text(
                    """
                    INSERT INTO public.agent_user_scope (
                        user_id, scope_type, scope_value, scope_label, created_at, updated_at
                    ) VALUES (
                        :user_id, :scope_type, :scope_value, :scope_label, now(), now()
                    )
                    """
                ),
                {
                    "user_id": user_id,
                    "scope_type": scope["scope_type"],
                    "scope_value": scope["scope_value"],
                    "scope_label": scope["scope_label"],
                },
            )

    return fetch_internal_user_by_id(user_id)


def create_internal_session(user_payload: dict, channel: str = "api", contact_id: Optional[int] = None, phone_e164: Optional[str] = None):
    ensure_internal_auth_tables()
    raw_token = secrets.token_urlsafe(32)
    token_hash = hash_session_token(raw_token)
    expires_at = datetime.utcnow() + timedelta(hours=INTERNAL_SESSION_TTL_HOURS)
    engine = get_db_engine()
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO public.agent_user_session (
                    user_id, token_hash, channel, contact_id, phone_e164, expires_at,
                    last_used_at, created_at, updated_at
                ) VALUES (
                    :user_id, :token_hash, :channel, :contact_id, :phone_e164, :expires_at,
                    now(), now(), now()
                )
                """
            ),
            {
                "user_id": user_payload["id"],
                "token_hash": token_hash,
                "channel": channel,
                "contact_id": contact_id,
                "phone_e164": phone_e164,
                "expires_at": expires_at,
            },
        )
    return {"token": raw_token, "expires_at": expires_at.isoformat()}


def resolve_internal_session(raw_token: Optional[str]):
    if not raw_token:
        return None
    ensure_internal_auth_tables()
    token_hash = hash_session_token(raw_token)
    engine = get_db_engine()
    with engine.begin() as connection:
        row = connection.execute(
            text(
                """
                SELECT s.user_id, s.expires_at, s.channel, s.phone_e164, s.contact_id,
                      u.username, u.full_name, u.role, u.email, u.phone_e164 AS user_phone, u.is_active, u.metadata
                FROM public.agent_user_session s
                JOIN public.agent_user u ON u.id = s.user_id
                WHERE s.token_hash = :token_hash
                  AND s.revoked_at IS NULL
                  AND s.expires_at > now()
                LIMIT 1
                """
            ),
            {"token_hash": token_hash},
        ).mappings().one_or_none()
        if not row or not row["is_active"]:
            return None
        connection.execute(
            text(
                """
                UPDATE public.agent_user_session
                SET last_used_at = now(),
                    updated_at = now()
                WHERE token_hash = :token_hash
                """
            ),
            {"token_hash": token_hash},
        )
    user_payload = {
        "id": row["user_id"],
        "username": row["username"],
        "full_name": row["full_name"],
        "role": row["role"],
        "email": row["email"],
        "phone_e164": row["user_phone"],
        "metadata": row.get("metadata") or {},
        "session_expires_at": row["expires_at"].isoformat() if row.get("expires_at") else None,
        "scopes": fetch_internal_user_scopes(row["user_id"]),
    }
    return user_payload


def revoke_internal_session(raw_token: Optional[str]):
    if not raw_token:
        return
    ensure_internal_auth_tables()
    engine = get_db_engine()
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                UPDATE public.agent_user_session
                SET revoked_at = now(),
                    updated_at = now()
                WHERE token_hash = :token_hash
                  AND revoked_at IS NULL
                """
            ),
            {"token_hash": hash_session_token(raw_token)},
        )


def authenticate_internal_user(username: str, password: str, phone_number: Optional[str] = None):
    user_payload = fetch_internal_user_by_username(username)
    if not user_payload or not user_payload.get("is_active"):
        return None
    if not verify_password_hash(password, user_payload["password_salt"], user_payload["password_hash"]):
        return None
    registered_phone = normalize_phone_e164(user_payload.get("phone_e164"))
    incoming_phone = normalize_phone_e164(phone_number)
    if registered_phone and incoming_phone and registered_phone != incoming_phone:
        raise HTTPException(status_code=403, detail="Este usuario interno solo puede autenticarse desde su número registrado.")
    return user_payload


def extract_bearer_token(authorization: Optional[str]):
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    return token.strip()


def require_internal_user(authorization: Optional[str]):
    token = extract_bearer_token(authorization)
    user_payload = resolve_internal_session(token)
    if not user_payload:
        raise HTTPException(status_code=401, detail="Sesión interna inválida o vencida.")
    return user_payload


def fetch_customer_lookup_row(cliente_codigo: str):
    engine = get_db_engine()
    with engine.connect() as connection:
        row = connection.execute(
            text(
                """
                SELECT cliente_codigo, nombre_cliente, nit, numero_documento, telefono1, telefono2, email,
                       vendedor, vendedor_codigo, zona, ultima_compra, ventas_netas_total,
                       saldo_cartera, max_dias_vencido, documentos_vencidos
                FROM public.vw_agente_clientes_lookup
                WHERE cliente_codigo = :cliente_codigo
                LIMIT 1
                """
            ),
            {"cliente_codigo": cliente_codigo},
        ).mappings().one_or_none()
    return dict(row) if row else None


def search_customer_lookup_rows(search_text: str, limit: int = 5):
    query_text = (search_text or "").strip()
    if not query_text:
        return []
    normalized = normalize_text_value(query_text)
    digits = re.sub(r"\D", "", query_text)
    compact = normalize_reference_value(query_text)
    engine = get_db_engine()
    with engine.connect() as connection:
        rows = connection.execute(
            text(
                """
                SELECT cliente_codigo, nombre_cliente, nit, numero_documento, telefono1, telefono2, email,
                       vendedor, vendedor_codigo, zona, ultima_compra, ventas_netas_total,
                       saldo_cartera, max_dias_vencido, documentos_vencidos
                FROM public.vw_agente_clientes_lookup
                WHERE (
                    :digits <> '' AND (
                        regexp_replace(COALESCE(nit, ''), '[^0-9]', '', 'g') LIKE :digits_pattern
                        OR regexp_replace(COALESCE(numero_documento, ''), '[^0-9]', '', 'g') LIKE :digits_pattern
                        OR regexp_replace(COALESCE(cliente_codigo, ''), '[^0-9]', '', 'g') = :digits
                    )
                )
                OR (
                    :compact IS NOT NULL AND regexp_replace(lower(COALESCE(cliente_codigo, '')), '[^a-z0-9]', '', 'g') = :compact
                )
                OR (
                    :normalized <> '' AND search_blob ILIKE :name_pattern
                )
                ORDER BY
                    CASE
                        WHEN regexp_replace(COALESCE(cliente_codigo, ''), '[^0-9]', '', 'g') = :digits THEN 0
                        WHEN regexp_replace(COALESCE(nit, ''), '[^0-9]', '', 'g') = :digits THEN 1
                        WHEN search_blob ILIKE :name_pattern THEN 2
                        ELSE 3
                    END,
                    max_dias_vencido DESC NULLS LAST,
                    ventas_netas_total DESC NULLS LAST,
                    nombre_cliente ASC
                LIMIT :limit
                """
            ),
            {
                "digits": digits,
                "digits_pattern": f"{digits}%" if digits else "",
                "compact": compact,
                "normalized": normalized,
                "name_pattern": f"%{normalized}%" if normalized else "",
                "limit": limit,
            },
        ).mappings().all()
    return [dict(row) for row in rows]


def internal_user_can_access_customer(user_payload: dict, customer_row: Optional[dict]):
    if not customer_row:
        return False
    role = (user_payload or {}).get("role")
    if role in {"administrador", "gerente", "operador"}:
        return True
    if role != "vendedor":
        return False

    scopes = (user_payload or {}).get("scopes") or []
    if not scopes:
        return False

    customer_code = normalize_text_value(customer_row.get("cliente_codigo"))
    vendor_name = normalize_text_value(customer_row.get("vendedor"))
    vendor_code = normalize_text_value(customer_row.get("vendedor_codigo"))
    zone_name = normalize_text_value(customer_row.get("zona"))

    for scope in scopes:
        scope_type = normalize_text_value(scope.get("scope_type"))
        scope_value = normalize_text_value(scope.get("scope_value"))
        if scope_type == "cliente" and scope_value == customer_code:
            return True
        if scope_type == "vendedor_nombre" and scope_value and vendor_name and scope_value == vendor_name:
            return True
        if scope_type == "vendedor_codigo" and scope_value and vendor_code and scope_value == vendor_code:
            return True
        if scope_type == "zona" and scope_value and zone_name and scope_value == zone_name:
            return True
    return False


def format_internal_customer_summary(customer_row: dict, purchase_summary: Optional[dict] = None):
    customer_name = customer_row.get("nombre_cliente") or customer_row.get("cliente_codigo") or "Cliente"
    customer_code = customer_row.get("cliente_codigo") or "sin código"
    vendor_name = customer_row.get("vendedor") or "sin vendedor asignado"
    zone_name = customer_row.get("zona") or "sin zona"
    balance = format_currency(customer_row.get("saldo_cartera"))
    overdue_docs = customer_row.get("documentos_vencidos") or 0
    overdue_days = customer_row.get("max_dias_vencido") or 0
    last_purchase = customer_row.get("ultima_compra")
    last_purchase_text = str(last_purchase) if last_purchase else "sin compra reciente"
    response_lines = [
        f"{customer_name} ({customer_code})",
        f"Vendedor: {vendor_name}. Zona: {zone_name}.",
        f"Cartera: {balance}. Vencidos: {overdue_docs} doc(s), {overdue_days} día(s).",
        f"Última compra: {last_purchase_text}.",
    ]
    if purchase_summary and purchase_summary.get("top_products"):
        top_product = purchase_summary["top_products"][0]
        response_lines.append(
            f"Top compra reciente: {top_product.get('nombre_articulo') or top_product.get('descripcion') or 'producto'}.")
    return "\n".join(response_lines)


def build_internal_login_reply(content: str, context: dict, conversation_context: dict):
    match = INTERNAL_LOGIN_PATTERN.match(content or "")
    if match:
        username = match.group(1)
        password = match.group(2)
        user_payload = authenticate_internal_user(username, password, context.get("telefono_e164"))
        if not user_payload:
            return {
                "response_text": "No pude autenticarte con ese usuario y contraseña. Revisa el acceso interno.",
                "intent": "internal_auth_login_failed",
                "context_updates": {},
            }
        session_payload = create_internal_session(
            user_payload,
            channel="whatsapp",
            contact_id=context.get("contact_id"),
            phone_e164=context.get("telefono_e164"),
        )
        return {
            "response_text": (
                f"Acceso interno activo para {user_payload.get('full_name')} como {user_payload.get('role')}. "
                "Ya puedes pedir cartera, compras y contexto de tus clientes."
            ),
            "intent": "internal_auth_login",
            "context_updates": {
                "awaiting_internal_auth_cedula": None,
                "internal_auth": build_internal_auth_context(user_payload, session_payload["token"], session_payload["expires_at"]),
            },
        }

    employee_by_phone = find_employee_record_by_phone(context.get("telefono_e164"))
    awaiting_cedula = bool((conversation_context or {}).get("awaiting_internal_auth_cedula"))
    cedula = extract_internal_cedula_candidate(content)
    employee_by_cedula = find_employee_record_by_cedula(cedula) if cedula else None

    if not employee_by_phone and not awaiting_cedula and not employee_by_cedula:
        return None

    if not cedula:
        return {
            "response_text": "Para continuar como colaborador Ferreinox necesito validar tu acceso. Envíame tu número de cédula.",
            "intent": "internal_auth_request_cedula",
            "context_updates": {"awaiting_internal_auth_cedula": True},
        }

    employee_record = employee_by_cedula
    if not employee_record:
        return {
            "response_text": "No encontré esa cédula en la base de colaboradores. Revisa el número o valida con administración.",
            "intent": "internal_auth_login_failed",
            "context_updates": {"awaiting_internal_auth_cedula": True},
        }

    incoming_phone = normalize_phone_e164(context.get("telefono_e164"))
    registered_phone = employee_record.get("phone_e164")
    if registered_phone and incoming_phone and registered_phone != incoming_phone:
        return {
            "response_text": "La cédula existe, pero el número de WhatsApp no coincide con el registrado en datos_empleados. Debes escribir desde tu número autorizado.",
            "intent": "internal_auth_phone_mismatch",
            "context_updates": {"awaiting_internal_auth_cedula": True},
        }

    if employee_by_phone and employee_by_phone.get("cedula") != employee_record.get("cedula"):
        return {
            "response_text": "La cédula enviada no coincide con el colaborador asociado a este número de WhatsApp.",
            "intent": "internal_auth_phone_mismatch",
            "context_updates": {"awaiting_internal_auth_cedula": True},
        }

    user_payload = sync_internal_user_from_employee_record(employee_record)
    session_payload = create_internal_session(
        user_payload,
        channel="whatsapp",
        contact_id=context.get("contact_id"),
        phone_e164=context.get("telefono_e164"),
    )
    role_label = user_payload.get("role") or "empleado"
    return {
        "response_text": (
            f"Acceso interno activo para {employee_record.get('full_name')}. "
            f"Cargo: {employee_record.get('cargo') or 'Sin cargo'} | Sede: {employee_record.get('sede') or 'Sin sede'} | Perfil: {role_label}."
        ),
        "intent": "internal_auth_login",
        "context_updates": {
            "awaiting_internal_auth_cedula": None,
            "internal_auth": build_internal_auth_context(user_payload, session_payload["token"], session_payload["expires_at"]),
        },
    }


def build_internal_logout_reply(conversation_context: dict):
    internal_auth = dict((conversation_context or {}).get("internal_auth") or {})
    if not internal_auth.get("token"):
        return None
    revoke_internal_session(internal_auth.get("token"))
    return {
        "response_text": "La sesión interna quedó cerrada. Si necesitas entrar de nuevo, envíame login usuario clave.",
        "intent": "internal_auth_logout",
        "context_updates": {"internal_auth": None, "awaiting_internal_auth_cedula": None, "internal_transfer_flow": None},
    }


def extract_internal_customer_candidate(text_value: Optional[str]):
    if not text_value:
        return None
    normalized = normalize_text_value(text_value)
    cleaned = normalized
    for fragment in [
        "dame",
        "ver",
        "mostrar",
        "muestreme",
        "muéstrame",
        "consulta",
        "consultar",
        "cartera",
        "compras",
        "compra",
        "cliente",
        "contexto",
        "resumen",
        "del",
        "de",
        "por favor",
        "nit",
        "cedula",
        "cédula",
        "codigo",
        "código",
        "cod",
        "nombre",
        "cuanto",
        "cuánto",
        "compro",
        "compró",
        "suma",
        "suma lo",
        "sumar",
        "total",
        "vencido",
        "vencidos",
        "vencida",
        "vencidas",
        "deuda",
        "debo",
        "debido",
        "ano",
        "año",
        "en",
        "el",
    ]:
        cleaned = re.sub(rf"\b{re.escape(fragment)}\b", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if not cleaned:
        return None
    candidate = extract_identity_lookup_candidate(cleaned, {}, allow_unprompted=True)
    if candidate:
        return candidate
    digits = re.findall(r"\d{6,15}", text_value or "")
    if digits:
        return {"type": "document", "value": digits[0]}
    tokens = [token for token in cleaned.split() if len(token) >= 3]
    if len(tokens) >= 2:
        return {"type": "name", "value": " ".join(tokens[:6])}
    return None


def resolve_internal_customer_context(identity_candidate: Optional[dict], phone_number: Optional[str] = None):
    if not identity_candidate:
        return None
    candidate_type = identity_candidate.get("type")
    candidate_value = identity_candidate.get("value")
    if candidate_type == "document":
        return find_cliente_contexto_by_document(candidate_value)
    if candidate_type == "customer_code":
        return find_cliente_contexto_by_customer_code(candidate_value)
    if candidate_type == "name":
        return find_cliente_contexto_by_name(candidate_value)
    if candidate_type == "phone":
        return find_cliente_contexto_by_phone(phone_number or candidate_value)
    return None


def detect_internal_query_intent(text_value: Optional[str]):
    normalized = normalize_text_value(text_value)
    if not normalized:
        return None
    if any(fragment in normalized for fragment in ["reclamos pendientes", "pendientes de reclamos", "crm pendientes de reclamos", "reclamos crm", "garantias pendientes", "garantías pendientes", "casos pendientes de reclamo"]):
        return "consulta_reclamos_pendientes"
    if any(fragment in normalized for fragment in ["carro va", "carro para", "van para", "va para", "traemos algo", "traemos mercancia", "traemos mercancía", "mercancia para", "mercancía para", "en ruta"]):
        return "consulta_ruta_mercancia"
    if any(fragment in normalized for fragment in ["pendientes despacho", "pendiente despacho", "pendientes por despachar", "por despachar", "pedidos pendientes", "despachos pendientes"]):
        return "consulta_despachos"
    if any(fragment in normalized for fragment in ["pedir algo a", "mandar algo a", "llevar algo a", "mover algo a", "pasar algo a"]):
        return "consulta_traslados"
    if any(fragment in normalized for fragment in ["genera traslado", "genere traslado", "crear traslado", "crea traslado", "solicita traslado", "traslada", "trasladar"]):
        return "crear_traslado"
    if any(fragment in normalized for fragment in ["que hay en", "qué hay en", "que tiene", "qué tiene", "no tenga", "no tiene", "comparar tiendas", "comparar inventario", "cumplir pedidos", "cumplir pedido", "traslados sugeridos", "sugerencia de traslado"]):
        return "consulta_traslados"
    if any(fragment in normalized for fragment in ["cartera", "saldo", "vencid"]):
        return "consulta_cartera"
    if any(fragment in normalized for fragment in ["compras", "compra", "compro", "compró", "ultimo pedido", "último pedido", "ultima compra", "última compra"]):
        return "consulta_compras"
    if any(fragment in normalized for fragment in ["contexto", "resumen", "perfil", "todo del cliente", "info del cliente"]):
        return "consulta_contexto"
    return None


def build_pending_dispatches_response(store_code: Optional[str] = None):
    rows = fetch_pending_dispatches(store_code)
    if not rows:
        store_label = get_store_short_label(store_code)
        if store_label:
            return f"No veo pedidos pendientes por despachar para {store_label}."
        return "No veo pedidos pendientes por despachar en este momento."

    response_lines = ["Pedidos pendientes de facturación/despacho:"]
    for row in rows[:6]:
        contacto = row.get("contacto_nombre") or "cliente sin nombre"
        destino = row.get("destination_store_name") or "sede pendiente"
        archivo = row.get("export_filename") or f"pedido_{row.get('order_id')}"
        estado = (row.get("status") or "pendiente").replace("_", " ")
        response_lines.append(
            f"- Pedido {row.get('order_id')} | {destino} | {contacto} | archivo {archivo} | estado {estado}"
        )
    return "\n".join(response_lines)


def build_internal_route_merchandise_response(content: str, internal_user: dict):
    store_mentions = extract_store_mentions_in_order(content)
    if not store_mentions:
        return "Dime la sede destino del carro o de la ruta y te digo qué pedidos, faltantes o traslados veo para esa ciudad.", None

    destination_store_code = store_mentions[-1]
    destination_label = get_store_short_label(destination_store_code) or STORE_CODE_LABELS.get(destination_store_code) or destination_store_code
    internal_metadata = dict((internal_user or {}).get("metadata") or {})
    preferred_origin_store_code = normalize_store_code(internal_metadata.get("store_code"))
    dispatches = fetch_pending_dispatches(destination_store_code, limit=6)
    flow_payload = build_internal_transfer_flow_payload(destination_store_code, preferred_origin_store_code)

    response_lines = [f"Ruta operativa hacia {destination_label}:"]
    if dispatches:
        response_lines.append(f"Veo {len(dispatches)} despacho(s) pendientes o en tránsito:")
        for row in dispatches[:4]:
            status_label = str(row.get("status") or "pendiente").replace("_", " ")
            contacto = row.get("contacto_nombre") or "cliente sin nombre"
            archivo = row.get("export_filename") or f"pedido_{row.get('order_id')}"
            response_lines.append(
                f"- Pedido {row.get('order_id')} | {contacto} | archivo {archivo} | estado {status_label}"
            )
    else:
        response_lines.append(f"No veo despachos pendientes o en tránsito hacia {destination_label} en este momento.")

    suggestions = flow_payload.get("suggestions") or []
    unresolved = flow_payload.get("unresolved_shortages") or []
    if suggestions:
        response_lines.append("Además puedo cubrir faltantes con estos traslados sugeridos:")
        response_lines.append(summarize_transfer_candidates(suggestions, max_items=4))
    if unresolved:
        response_lines.append("Y estos faltantes tocaría escalarlos a compras:")
        response_lines.append(summarize_transfer_candidates(unresolved, max_items=4))
    if suggestions or unresolved:
        response_lines.append("Si quieres, responde `confirmar traslado`, `compras` o `cancelar` y sigo la guía operativa contigo.")

    return "\n".join(response_lines), (flow_payload if (suggestions or unresolved) else None)


def fetch_pending_agent_tasks(task_types: list[str], limit: int = 6, destination_store_code: Optional[str] = None):
    cleaned_task_types = [str(task_type).strip() for task_type in (task_types or []) if str(task_type).strip()]
    if not cleaned_task_types:
        return []

    where_clauses = ["estado IN ('pendiente', 'abierta', 'en_proceso')"]
    params = {"limit": max(1, int(limit or 6))}
    type_placeholders = []
    for index, task_type in enumerate(cleaned_task_types):
        param_name = f"task_type_{index}"
        params[param_name] = task_type
        type_placeholders.append(f":{param_name}")
    where_clauses.append(f"tipo_tarea IN ({', '.join(type_placeholders)})")

    store_code = normalize_store_code(destination_store_code)
    if store_code:
        where_clauses.append("COALESCE(detalle->>'destination_store_code', '') = :destination_store_code")
        params["destination_store_code"] = store_code

    engine = get_db_engine()
    with engine.connect() as connection:
        rows = connection.execute(
            text(
                f"""
                SELECT
                    id,
                    tipo_tarea,
                    prioridad,
                    estado,
                    resumen,
                    detalle,
                    created_at,
                    updated_at
                FROM public.agent_task
                WHERE {' AND '.join(where_clauses)}
                ORDER BY updated_at DESC NULLS LAST, created_at DESC NULLS LAST, id DESC
                LIMIT :limit
                """
            ),
            params,
        ).mappings().all()
    return [dict(row) for row in rows]


def build_internal_procurement_pending_response(content: str, internal_user: dict):
    store_mentions = extract_store_mentions_in_order(content)
    if not store_mentions:
        return "Dime la sede que quieres revisar para compras pendientes, por ejemplo Pereira o Manizales.", None

    destination_store_code = store_mentions[-1]
    destination_label = get_store_short_label(destination_store_code) or STORE_CODE_LABELS.get(destination_store_code) or destination_store_code
    internal_metadata = dict((internal_user or {}).get("metadata") or {})
    preferred_origin_store_code = normalize_store_code(internal_metadata.get("store_code"))
    flow_payload = build_internal_transfer_flow_payload(destination_store_code, preferred_origin_store_code)
    unresolved = flow_payload.get("unresolved_shortages") or []
    suggestions = flow_payload.get("suggestions") or []
    pending_tasks = fetch_pending_agent_tasks(["abastecimiento_compras"], limit=5, destination_store_code=destination_store_code)

    response_lines = [f"Compras pendientes para {destination_label}:"]
    if unresolved:
        response_lines.append("Estos faltantes no tienen origen interno útil y tocaría gestionarlos por compras:")
        response_lines.append(summarize_transfer_candidates(unresolved, max_items=5))
    else:
        response_lines.append(f"No veo faltantes activos sin origen interno para {destination_label} en este momento.")

    if suggestions:
        response_lines.append("Antes de comprar, sí veo estos traslados posibles para cubrir parte de la necesidad:")
        response_lines.append(summarize_transfer_candidates(suggestions, max_items=4))

    if pending_tasks:
        response_lines.append("Además ya hay seguimientos de compras abiertos:")
        for task in pending_tasks[:4]:
            detail = dict(task.get("detalle") or {})
            shortages = detail.get("shortages") or []
            note_suffix = f" | {len(shortages)} faltante(s)" if shortages else ""
            response_lines.append(
                f"- Caso {task.get('id')} | {task.get('resumen') or 'abastecimiento pendiente'} | prioridad {task.get('prioridad') or 'media'}{note_suffix}"
            )

    if unresolved or suggestions:
        response_lines.append("Si quieres, responde `confirmar traslado` para mover lo transferible o `compras` para escalar faltantes sin origen.")

    return "\n".join(response_lines), (flow_payload if (unresolved or suggestions) else None)


def build_internal_pending_claims_response(limit: int = 6):
    tasks = fetch_pending_agent_tasks(["reclamo_calidad"], limit=limit)
    if not tasks:
        return "No veo reclamos pendientes abiertos en el CRM en este momento."

    response_lines = ["Reclamos pendientes en CRM:"]
    for task in tasks[:limit]:
        detail = dict(task.get("detalle") or {})
        cliente_label = detail.get("cliente") or detail.get("nombre_cliente") or "cliente sin nombre"
        product_label = detail.get("product_label") or detail.get("producto_reclamado") or "producto pendiente"
        store_name = detail.get("store_name") or "sede no indicada"
        response_lines.append(
            f"- Caso {task.get('id')} | {cliente_label} | {product_label} | {store_name} | prioridad {task.get('prioridad') or 'media'}"
        )
    return "\n".join(response_lines)


def build_transfer_suggestions_response(content: str, internal_user: dict):
    store_mentions = extract_store_mentions_in_order(content)
    normalized = normalize_text_value(content)
    internal_metadata = dict((internal_user or {}).get("metadata") or {})
    internal_store_code = normalize_store_code(internal_metadata.get("store_code"))
    if len(store_mentions) >= 2:
        source_store_code, destination_store_code = store_mentions[0], store_mentions[1]
    elif len(store_mentions) == 1:
        source_store_code, destination_store_code = internal_store_code, store_mentions[0]
    else:
        source_store_code, destination_store_code = internal_store_code, None

    if destination_store_code and any(fragment in normalized for fragment in ["cumplir pedidos", "cumplir pedido", "pendiente", "despacho"]):
        suggestions = build_transfer_suggestions_for_pending_dispatches(destination_store_code, source_store_code)
        if not suggestions:
            destination_label = get_store_short_label(destination_store_code) or STORE_CODE_LABELS.get(destination_store_code) or "la sede consultada"
            return f"No encontré faltantes pendientes con traslado útil hacia {destination_label}.", []
        response_lines = ["Sugerencias de traslado para cubrir pedidos pendientes:"]
        for suggestion in suggestions[:6]:
            response_lines.append(
                f"- Pedido {suggestion['order_id']} | {suggestion['reference']} | {suggestion['origin_store_name']} -> {suggestion['destination_store_name']} | sugerido {format_quantity(suggestion['suggested_qty'])} und"
            )
        return "\n".join(response_lines), suggestions

    if source_store_code and destination_store_code:
        gaps = fetch_inventory_gap_between_stores(source_store_code, destination_store_code)
        if not gaps:
            source_label = get_store_short_label(source_store_code) or STORE_CODE_LABELS.get(source_store_code) or source_store_code
            destination_label = get_store_short_label(destination_store_code) or STORE_CODE_LABELS.get(destination_store_code) or destination_store_code
            return f"No veo referencias con stock en {source_label} y quiebre total en {destination_label}.", []
        response_lines = [
            f"Referencias que sí están en {get_store_short_label(source_store_code) or STORE_CODE_LABELS.get(source_store_code)} y no están en {get_store_short_label(destination_store_code) or STORE_CODE_LABELS.get(destination_store_code)}:"
        ]
        for gap in gaps[:8]:
            response_lines.append(
                f"- {gap['referencia']} | {gap.get('descripcion') or 'sin descripción'} | stock origen {format_quantity(gap['stock_origen'])}"
            )
        return "\n".join(response_lines), []

    suggestions = build_transfer_suggestions_for_pending_dispatches(destination_store_code, source_store_code)
    if suggestions:
        response_lines = ["Traslados sugeridos sobre pedidos pendientes:"]
        for suggestion in suggestions[:6]:
            response_lines.append(
                f"- Pedido {suggestion['order_id']} | {suggestion['reference']} | {suggestion['origin_store_name']} -> {suggestion['destination_store_name']} | sugerido {format_quantity(suggestion['suggested_qty'])} und"
            )
        return "\n".join(response_lines), suggestions

    return "Dime la tienda destino o compárame dos tiendas, por ejemplo: 'qué hay en Manizales que Pereira no tenga' o 'traslada a Pereira para cumplir pedidos'.", []


def handle_pending_internal_transfer_flow(content: str, context: dict, conversation_context: dict, internal_user: dict, internal_auth: dict):
    flow_payload = dict((conversation_context or {}).get("internal_transfer_flow") or {})
    if not flow_payload:
        return None

    normalized = normalize_text_value(content)
    if normalized in {"cancelar", "cancelar traslado", "salir", "no"}:
        return {
            "response_text": "Listo, cierro esta guía operativa de traslados y abastecimiento.",
            "intent": "internal_transfer_flow_cancelled",
            "context_updates": {
                "internal_auth": build_internal_auth_context(internal_user, internal_auth.get("token"), internal_user.get("session_expires_at")),
                "internal_transfer_flow": None,
            },
        }

    if flow_payload.get("step") == "awaiting_destination":
        store_mentions = extract_store_mentions_in_order(content)
        destination_store_code = store_mentions[-1] if store_mentions else None
        if not destination_store_code:
            return {
                "response_text": "Todavía me falta la sede destino. Dímela como ciudad o tienda, por ejemplo: Manizales, Armenia, Laureles o Cerritos.",
                "intent": "internal_transfer_flow_destination_missing",
                "context_updates": {
                    "internal_auth": build_internal_auth_context(internal_user, internal_auth.get("token"), internal_user.get("session_expires_at")),
                    "internal_transfer_flow": flow_payload,
                },
            }
        refreshed_payload = build_internal_transfer_flow_payload(destination_store_code, flow_payload.get("origin_store_code"))
        return {
            "response_text": build_internal_transfer_guidance_text(refreshed_payload),
            "intent": "internal_transfer_flow_ready",
            "context_updates": {
                "internal_auth": build_internal_auth_context(internal_user, internal_auth.get("token"), internal_user.get("session_expires_at")),
                "internal_transfer_flow": refreshed_payload,
            },
        }

    selected_indexes = parse_internal_selection_indexes(content, len(flow_payload.get("suggestions") or []))
    suggestions = flow_payload.get("suggestions") or []
    selected_suggestions = [suggestions[index - 1] for index in selected_indexes] if selected_indexes else suggestions
    wants_transfer = any(token in normalized for token in ["confirmar", "crear", "traslado", "si", "sí", "listo"])
    wants_procurement = any(token in normalized for token in ["compras", "abastecimiento", "escalar", "comprar"])

    if wants_transfer and selected_suggestions:
        created_requests = create_transfer_request_records(selected_suggestions[:5], internal_user, notes=content)
        if not created_requests:
            return {
                "response_text": "Las opciones seleccionadas no pertenecen a tu sede de origen o ya no aplican. Puedo recalcular si me dices nuevamente la sede destino.",
                "intent": "internal_transfer_origin_mismatch",
                "context_updates": {
                    "internal_auth": build_internal_auth_context(internal_user, internal_auth.get("token"), internal_user.get("session_expires_at")),
                    "internal_transfer_flow": None,
                },
            }
        notification_result = notify_transfer_requests_by_email(created_requests, internal_user, notes=content)
        upsert_agent_task(
            context["conversation_id"],
            context.get("cliente_id"),
            "traslado_interno",
            "Solicitud interna de traslado generada por guía conversacional",
            {"solicitudes": created_requests, "mensaje": content, "notificacion": notification_result},
            "alta",
        )
        response_lines = ["Traslados creados desde la guía operativa:"]
        response_lines.append(summarize_transfer_candidates(created_requests))
        if notification_result.get("sent"):
            for row in notification_result["sent"]:
                response_lines.append(f"Correo enviado a {row['to_email']} con copia a {', '.join(row.get('cc_emails') or [])}.")
        if notification_result.get("errors"):
            response_lines.append("Errores de notificación: " + "; ".join(notification_result["errors"]))
        return {
            "response_text": "\n".join(response_lines),
            "intent": "crear_traslado",
            "context_updates": {
                "internal_auth": build_internal_auth_context(internal_user, internal_auth.get("token"), internal_user.get("session_expires_at")),
                "internal_transfer_flow": None,
            },
        }

    unresolved = flow_payload.get("unresolved_shortages") or []
    if wants_procurement and unresolved:
        followup = create_procurement_followup(context, internal_user, unresolved[:8], notes=content)
        response_lines = ["Faltantes escalados a compras para abastecimiento:", summarize_transfer_candidates(unresolved)]
        notification = followup.get("notification") or {}
        if notification.get("sent"):
            response_lines.append(f"Correo enviado a {notification.get('to_email')} con adjunto {notification.get('attachment')}.")
        if notification.get("errors"):
            response_lines.append("Errores de notificación: " + "; ".join(notification.get("errors") or []))
        return {
            "response_text": "\n".join([line for line in response_lines if line]),
            "intent": "internal_procurement_escalated",
            "context_updates": {
                "internal_auth": build_internal_auth_context(internal_user, internal_auth.get("token"), internal_user.get("session_expires_at")),
                "internal_transfer_flow": None,
            },
        }

    return {
        "response_text": build_internal_transfer_guidance_text(flow_payload),
        "intent": "internal_transfer_flow_pending",
        "context_updates": {
            "internal_auth": build_internal_auth_context(internal_user, internal_auth.get("token"), internal_user.get("session_expires_at")),
            "internal_transfer_flow": flow_payload,
        },
    }


def handle_internal_whatsapp_message(content: Optional[str], context: dict, conversation_context: dict):
    if not content:
        return None

    internal_auth = dict((conversation_context or {}).get("internal_auth") or {})
    active_internal_user = resolve_internal_session(internal_auth.get("token")) if internal_auth.get("token") else None

    if active_internal_user:
        internal_auth = build_internal_auth_context(
            active_internal_user,
            internal_auth.get("token"),
            active_internal_user.get("session_expires_at"),
        )
        if isinstance(conversation_context, dict):
            conversation_context["internal_auth"] = internal_auth
            conversation_context["awaiting_internal_auth_cedula"] = None
    elif internal_auth.get("token"):
        return {
            "response_text": "La sesión interna venció. Vuelve a ingresar con login usuario clave o envíame tu cédula nuevamente.",
            "intent": "internal_auth_expired",
            "context_updates": {"internal_auth": None, "awaiting_internal_auth_cedula": None, "internal_transfer_flow": None},
        }

    normalized = normalize_text_value(content)
    if not active_internal_user:
        login_reply = build_internal_login_reply(content, context, conversation_context)
        if login_reply:
            return login_reply

    if normalized in INTERNAL_LOGOUT_PATTERNS:
        return build_internal_logout_reply(conversation_context)

    employee_by_phone = find_employee_record_by_phone(context.get("telefono_e164"))
    if employee_by_phone and not internal_auth.get("token"):
        return {
            "response_text": "Antes de seguir necesito validar tu acceso interno. Envíame tu cédula para activar la sesión de colaborador.",
            "intent": "internal_auth_request_cedula",
            "context_updates": {"awaiting_internal_auth_cedula": True},
        }

    if not active_internal_user:
        if detect_internal_query_intent(content):
            return {
                "response_text": "Para consultas internas primero debes iniciar sesión. Si eres colaborador, envíame tu cédula. Si eres usuario técnico legado, puedes escribir login usuario clave.",
                "intent": "internal_auth_required",
                "context_updates": {},
            }
        return None

    internal_user = active_internal_user

    pending_transfer_flow_reply = handle_pending_internal_transfer_flow(content, context, conversation_context, internal_user, internal_auth)
    if pending_transfer_flow_reply:
        return pending_transfer_flow_reply

    intent = detect_internal_query_intent(content)
    if not intent:
        return None

    if intent == "consulta_despachos":
        if not internal_user_has_advanced_access(internal_user):
            return {
                "response_text": "Tu perfil actual puede crear pedidos, pero no consultar despachos ni operación interna completa.",
                "intent": "internal_access_denied",
                "context_updates": {"internal_auth": build_internal_auth_context(internal_user, internal_auth.get("token"), internal_user.get("session_expires_at"))},
            }
        store_mentions = extract_store_mentions_in_order(content)
        store_code = store_mentions[0] if store_mentions else None
        return {
            "response_text": build_pending_dispatches_response(store_code),
            "intent": intent,
            "context_updates": {"internal_auth": build_internal_auth_context(internal_user, internal_auth.get("token"), internal_user.get("session_expires_at"))},
        }

    if intent == "consulta_ruta_mercancia":
        if not internal_user_has_advanced_access(internal_user):
            return {
                "response_text": "Tu perfil actual puede crear pedidos, pero no consultar la operación logística interna completa.",
                "intent": "internal_access_denied",
                "context_updates": {"internal_auth": build_internal_auth_context(internal_user, internal_auth.get("token"), internal_user.get("session_expires_at"))},
            }
        response_text, flow_payload = build_internal_route_merchandise_response(content, internal_user)
        context_updates = {"internal_auth": build_internal_auth_context(internal_user, internal_auth.get("token"), internal_user.get("session_expires_at"))}
        if flow_payload:
            context_updates["internal_transfer_flow"] = flow_payload
        return {
            "response_text": response_text,
            "intent": intent,
            "context_updates": context_updates,
        }

    if intent == "consulta_reclamos_pendientes":
        if not internal_user_has_advanced_access(internal_user):
            return {
                "response_text": "Tu perfil actual puede crear pedidos, pero no consultar la bandeja interna de reclamos.",
                "intent": "internal_access_denied",
                "context_updates": {"internal_auth": build_internal_auth_context(internal_user, internal_auth.get("token"), internal_user.get("session_expires_at"))},
            }
        return {
            "response_text": build_internal_pending_claims_response(),
            "intent": intent,
            "context_updates": {"internal_auth": build_internal_auth_context(internal_user, internal_auth.get("token"), internal_user.get("session_expires_at"))},
        }

    if intent in {"consulta_traslados", "crear_traslado"}:
        if not internal_user_has_advanced_access(internal_user):
            return {
                "response_text": "Tu perfil actual puede tomar pedidos, pero no consultar ni gestionar traslados internos.",
                "intent": "internal_access_denied",
                "context_updates": {"internal_auth": build_internal_auth_context(internal_user, internal_auth.get("token"), internal_user.get("session_expires_at"))},
            }
        response_text, suggestions = build_transfer_suggestions_response(content, internal_user)
        context_updates = {"internal_auth": build_internal_auth_context(internal_user, internal_auth.get("token"), internal_user.get("session_expires_at"))}
        store_mentions = extract_store_mentions_in_order(content)
        requested_destination = store_mentions[-1] if store_mentions else None
        internal_metadata = dict((internal_user or {}).get("metadata") or {})
        default_origin_store = normalize_store_code(internal_metadata.get("store_code"))
        if not requested_destination:
            context_updates["internal_transfer_flow"] = {
                "step": "awaiting_destination",
                "origin_store_code": default_origin_store,
            }
            return {
                "response_text": "¿Para qué sede quieres revisar faltantes o generar traslado? Si no me dices origen, tomaré como origen tu sede autenticada.",
                "intent": "internal_transfer_flow_destination_missing",
                "context_updates": context_updates,
            }

        flow_payload = build_internal_transfer_flow_payload(requested_destination, default_origin_store)
        context_updates["internal_transfer_flow"] = flow_payload
        if intent == "crear_traslado":
            if not internal_user_can_manage_transfers(internal_user):
                return {
                    "response_text": "Solo el facturador de la sede origen puede crear solicitudes de traslado. Debes tener cargo de líder de tienda, líder logístico/inventario o auxiliar de facturación.",
                    "intent": "internal_transfer_forbidden",
                    "context_updates": context_updates,
                }
            if not flow_payload.get("suggestions") and not flow_payload.get("unresolved_shortages"):
                return {
                    "response_text": response_text,
                    "intent": intent,
                    "context_updates": context_updates,
                }
            return {
                "response_text": build_internal_transfer_guidance_text(flow_payload),
                "intent": "internal_transfer_flow_ready",
                "context_updates": context_updates,
            }
        return {
            "response_text": build_internal_transfer_guidance_text(flow_payload) if (flow_payload.get("suggestions") or flow_payload.get("unresolved_shortages")) else response_text,
            "intent": intent,
            "context_updates": context_updates,
        }

    if intent == "consulta_compras":
        candidate = extract_internal_customer_candidate(content)
        store_mentions = extract_store_mentions_in_order(content)
        normalized_content = normalize_text_value(content)
        has_explicit_customer_reference = bool(re.search(r"\b\d{6,15}\b", content or "")) or bool(
            re.search(r"\b(cliente|nit|cedula|cédula|codigo cliente|código cliente)\b", normalized_content)
        )
        if store_mentions and not has_explicit_customer_reference:
            if not internal_user_has_advanced_access(internal_user):
                return {
                    "response_text": "Tu perfil actual puede crear pedidos, pero no consultar compras y faltantes internos.",
                    "intent": "internal_access_denied",
                    "context_updates": {"internal_auth": build_internal_auth_context(internal_user, internal_auth.get("token"), internal_user.get("session_expires_at"))},
                }
            response_text, flow_payload = build_internal_procurement_pending_response(content, internal_user)
            context_updates = {"internal_auth": build_internal_auth_context(internal_user, internal_auth.get("token"), internal_user.get("session_expires_at"))}
            if flow_payload:
                context_updates["internal_transfer_flow"] = flow_payload
            return {
                "response_text": response_text,
                "intent": "consulta_compras_pendientes",
                "context_updates": context_updates,
            }

    candidate = extract_internal_customer_candidate(content)
    last_cliente_codigo = (conversation_context or {}).get("internal_last_cliente_codigo")
    cliente_contexto = resolve_internal_customer_context(candidate, context.get("telefono_e164")) if candidate else None
    if (not cliente_contexto or not cliente_contexto.get("cliente_codigo")) and last_cliente_codigo and not candidate:
        cliente_contexto = fetch_customer_lookup_row(last_cliente_codigo) or {"cliente_codigo": last_cliente_codigo}

    if not cliente_contexto or not cliente_contexto.get("cliente_codigo"):
        if not candidate:
            return {
                "response_text": "Dime el NIT, la cédula, el código o el nombre del cliente y te muestro la información.",
                "intent": "internal_customer_missing",
                "context_updates": {},
            }
        return {
            "response_text": "No encontré ese cliente con la información enviada. Prueba con NIT, código cliente o nombre completo.",
            "intent": "internal_customer_not_found",
            "context_updates": {},
        }

    if not internal_user_has_advanced_access(internal_user):
        return {
            "response_text": "Tu perfil actual puede crear pedidos, pero no consultar cartera, compras ni CRM interno completo.",
            "intent": "internal_access_denied",
            "context_updates": {"internal_auth": build_internal_auth_context(internal_user, internal_auth.get("token"), internal_user.get("session_expires_at"))},
        }

    customer_row = fetch_customer_lookup_row(cliente_contexto.get("cliente_codigo")) or cliente_contexto
    if not internal_user_can_access_customer(internal_user, customer_row):
        return {
            "response_text": "No tienes permisos para consultar ese cliente con tu rol actual.",
            "intent": "internal_access_denied",
            "context_updates": {},
        }

    if intent == "consulta_cartera":
        cartera_query = extract_cartera_query(content)
        overdue_info = fetch_overdue_documents(cliente_contexto.get("cliente_codigo"))
        totals = (overdue_info or {}).get("totals") or {}
        if cartera_query.get("wants_overdue_only"):
            response_text = (
                f"{customer_row.get('nombre_cliente') or cliente_contexto.get('cliente_codigo')}\n"
                f"Cartera vencida: {format_currency(totals.get('saldo_vencido'))}.\n"
                f"Documentos vencidos: {totals.get('documentos_vencidos', customer_row.get('documentos_vencidos') or 0)} | "
                f"máximo atraso: {totals.get('max_dias_vencido', customer_row.get('max_dias_vencido') or 0)} día(s)."
            )
        else:
            response_text = (
                f"{customer_row.get('nombre_cliente') or cliente_contexto.get('cliente_codigo')}\n"
                f"Saldo cartera: {format_currency(customer_row.get('saldo_cartera'))}.\n"
                f"Vencidos: {totals.get('documentos_vencidos', customer_row.get('documentos_vencidos') or 0)} documento(s), "
                f"máximo {totals.get('max_dias_vencido', customer_row.get('max_dias_vencido') or 0)} día(s)."
            )
    elif intent == "consulta_compras":
        purchase_query = extract_purchase_query(content)
        if purchase_query.get("wants_last_purchase"):
            purchase_summary = fetch_latest_purchase_detail(cliente_contexto.get("cliente_codigo"))
            if not purchase_summary:
                response_text = f"No encontré compras recientes para {customer_row.get('nombre_cliente') or cliente_contexto.get('cliente_codigo')}."
            else:
                totals = purchase_summary.get("totals") or {}
                top_products = ", ".join(
                    (item.get("nombre_articulo") or "")
                    for item in (purchase_summary.get("products") or [])[:3]
                    if item.get("nombre_articulo")
                ) or "sin detalle"
                response_text = (
                    f"{customer_row.get('nombre_cliente') or cliente_contexto.get('cliente_codigo')}\n"
                    f"Última compra: {purchase_summary.get('fecha_venta') or 'sin fecha'} por {format_currency(totals.get('valor_total'))}.\n"
                    f"Productos: {top_products}"
                )
        else:
            purchases = fetch_purchase_summary(
                cliente_contexto.get("cliente_codigo"),
                purchase_query.get("start_date"),
                purchase_query.get("end_date"),
            )
            response_text = build_purchase_summary_response_text(
                customer_row.get("nombre_cliente") or cliente_contexto.get("cliente_codigo"),
                purchase_query,
                purchases,
            )
    else:
        purchase_summary = fetch_latest_purchase_detail(cliente_contexto.get("cliente_codigo"))
        response_text = format_internal_customer_summary(customer_row, purchase_summary)

    return {
        "response_text": response_text,
        "intent": intent,
        "context_updates": {
            "internal_auth": build_internal_auth_context(internal_user, internal_auth.get("token"), internal_user.get("session_expires_at")),
            "internal_last_cliente_codigo": cliente_contexto.get("cliente_codigo"),
        },
    }


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


def send_sendgrid_email(
    to_email: str,
    subject: str,
    html_content: str,
    text_content: str,
    reply_to: Optional[str] = None,
    cc_emails: Optional[list[str]] = None,
    attachments: Optional[list[dict]] = None,
):
    config = get_sendgrid_config()
    if not config:
        raise RuntimeError("SendGrid no está configurado.")

    personalization = {"to": [{"email": to_email}], "subject": subject}
    cc_payload = [{"email": email} for email in (cc_emails or []) if email]
    if cc_payload:
        personalization["cc"] = cc_payload

    payload = {
        "personalizations": [personalization],
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
    if attachments:
        payload["attachments"] = attachments

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


def normalize_store_code(store_value: Optional[str]):
    normalized = normalize_text_value(store_value)
    if not normalized:
        return None
    if normalized.isdigit() and normalized in STORE_CODE_LABELS:
        return normalized
    for aliases in STORE_ALIASES.values():
        store_code = next((candidate for candidate in aliases if candidate.isdigit()), None)
        if not store_code:
            continue
        for alias in aliases:
            if normalize_text_value(alias) == normalized:
                return store_code
    return None


def get_store_short_label(store_code: Optional[str]):
    store_code = normalize_store_code(store_code)
    if not store_code:
        return None
    label = STORE_CODE_LABELS.get(store_code) or store_code
    return re.sub(r"^Tienda\s+", "", label, flags=re.IGNORECASE).strip()


def extract_store_stock_from_summary(stock_summary: Optional[str], store_code: Optional[str]):
    normalized_code = normalize_store_code(store_code)
    if not stock_summary or not normalized_code:
        return None

    match_tokens = set()
    for alias in STORE_ALIASES.get(next((key for key, aliases in STORE_ALIASES.items() if normalized_code in aliases), ""), []):
        alias_normalized = normalize_text_value(alias)
        if alias_normalized and not alias_normalized.isdigit():
            match_tokens.add(alias_normalized)
    label_normalized = normalize_text_value(STORE_CODE_LABELS.get(normalized_code) or "")
    if label_normalized:
        match_tokens.add(label_normalized)

    for fragment in str(stock_summary).split(";"):
        left_value, _, right_value = fragment.partition(":")
        left_normalized = normalize_text_value(left_value)
        if any(token and token in left_normalized for token in match_tokens):
            return parse_numeric_value(right_value)
    return None


def filter_previous_product_context(conversation_context: Optional[dict], product_request: Optional[dict]):
    previous_rows = list((conversation_context or {}).get("last_product_context") or [])
    if not previous_rows:
        return []

    filtered_rows = previous_rows
    requested_unit = (product_request or {}).get("requested_unit")
    if requested_unit:
        unit_rows = [row for row in filtered_rows if infer_product_presentation_from_row(row) == requested_unit]
        if unit_rows:
            filtered_rows = unit_rows

    requested_store_codes = (product_request or {}).get("store_filters") or []
    if len(requested_store_codes) == 1:
        requested_store_code = requested_store_codes[0]
        visible_rows = []
        for row in filtered_rows:
            store_stock = extract_store_stock_from_summary(row.get("stock_por_tienda"), requested_store_code)
            row_copy = dict(row)
            row_copy["stock_en_tienda_solicitada"] = store_stock
            row_copy["visibilidad_tienda_exacta"] = store_stock is not None
            visible_rows.append(row_copy)
        filtered_rows = visible_rows

    return filtered_rows[:5]


def extract_store_mentions_in_order(text_value: Optional[str]):
    normalized = normalize_text_value(text_value)
    if not normalized:
        return []

    found_matches = []
    for aliases in STORE_ALIASES.values():
        store_code = next((candidate for candidate in aliases if candidate.isdigit()), None)
        if not store_code:
            continue
        best_pos = None
        for alias in aliases:
            alias_normalized = normalize_text_value(alias)
            if not alias_normalized:
                continue
            match = re.search(rf"\b{re.escape(alias_normalized)}\b", normalized)
            if match and (best_pos is None or match.start() < best_pos):
                best_pos = match.start()
        if best_pos is not None:
            found_matches.append((best_pos, store_code))

    ordered_codes = []
    seen_codes = set()
    for _, store_code in sorted(found_matches, key=lambda item: item[0]):
        if store_code not in seen_codes:
            seen_codes.add(store_code)
            ordered_codes.append(store_code)
    return ordered_codes


def get_dropbox_icg_orders_folder():
    config = get_dropbox_ventas_config()
    base_folder = (config.get("folder") or "/data").rstrip("/") or "/data"
    subfolder = (os.getenv("DROPBOX_VENTAS_PEDIDOS_ICG_SUBFOLDER") or "PedidosICG").strip("/")
    if not subfolder:
        return base_folder
    if base_folder.endswith(f"/{subfolder}"):
        return base_folder
    return f"{base_folder}/{subfolder}"


def sanitize_filename_segment(raw_value: Optional[str], fallback: str):
    raw_text = str(raw_value or "").strip()
    sanitized = "".join(character if character.isalnum() or character in {"_", "-", " "} else "_" for character in raw_text)
    sanitized = re.sub(r"\s+", "_", sanitized).strip("_")
    return sanitized or fallback


def get_employee_facturador_candidates_for_store(store_code: Optional[str]):
    store_code = normalize_store_code(store_code)
    if not store_code:
        return []

    def rank_candidate(record: dict):
        cargo = normalize_text_value(record.get("cargo"))
        if "lider de tienda" in cargo or "líder de tienda" in cargo:
            return 0
        if "lider logistica" in cargo or "líder logística" in cargo or "lider de inventario" in cargo or "líder de inventario" in cargo:
            return 1
        if "facturacion" in cargo or "facturación" in cargo:
            return 2
        return 3

    candidates = []
    for record in load_employee_directory():
        if record.get("store_code") != store_code or not record.get("is_facturador"):
            continue
        if not record.get("email") and not record.get("phone_e164"):
            continue
        candidates.append(record)
    return sorted(candidates, key=rank_candidate)


def get_transfer_destination_email_map():
    configured = {}
    raw_json = os.getenv("TRANSFER_DESTINATION_EMAILS_JSON")
    if raw_json:
        try:
            configured = json.loads(raw_json)
        except Exception as exc:
            raise RuntimeError(f"TRANSFER_DESTINATION_EMAILS_JSON inválido: {exc}")
    normalized_map = {**DEFAULT_TRANSFER_DESTINATION_EMAILS}
    for raw_key, raw_value in (configured or {}).items():
        store_code = normalize_store_code(raw_key)
        email = str(raw_value or "").strip().lower()
        if store_code and email:
            normalized_map[store_code] = email
    return normalized_map


def get_transfer_cc_emails():
    raw_csv = os.getenv("TRANSFER_NOTIFICATION_CC_EMAILS")
    if raw_csv:
        return [email.strip().lower() for email in raw_csv.split(",") if email.strip()]
    return list(DEFAULT_TRANSFER_CC_EMAILS)


def build_brand_email_shell(title: str, body_html: str):
    dark = CORPORATE_BRAND["brand_dark"]
    accent = CORPORATE_BRAND["brand_accent"]
    light = CORPORATE_BRAND["brand_light"]
    border = CORPORATE_BRAND["brand_border"]
    return (
        "<div style='margin:0;padding:24px;background:#f3f4f6;font-family:Segoe UI,Arial,sans-serif;color:#111827;'>"
        f"<div style='max-width:760px;margin:0 auto;background:#ffffff;border:1px solid {border};border-radius:18px;overflow:hidden;'>"
        f"<div style='background:{dark};padding:28px 32px;color:#ffffff;'>"
        f"<div style='font-size:12px;letter-spacing:1.2px;text-transform:uppercase;opacity:.8;'>Ferreinox SAS BIC</div>"
        f"<div style='font-size:30px;font-weight:700;margin-top:6px;'>{escape(title)}</div>"
        f"<div style='margin-top:10px;font-size:13px;color:#d1d5db;'>NIT {escape(CORPORATE_BRAND['nit'])} | {escape(CORPORATE_BRAND['address'])}</div>"
        "</div>"
        f"<div style='padding:28px 32px;background:{light};'>{body_html}</div>"
        f"<div style='padding:22px 32px;background:#ffffff;border-top:1px solid {border};font-size:12px;color:#6b7280;'>"
        f"<strong style='color:#111827;'>{escape(CORPORATE_BRAND['company_name'])}</strong><br>"
        f"Sitio web: <a href='{escape(CORPORATE_BRAND['website'])}' style='color:{accent};'>{escape(CORPORATE_BRAND['website'])}</a><br>"
        f"Correo: {escape(CORPORATE_BRAND['service_email'])} | Tel: {escape(CORPORATE_BRAND['phone_landline'])} | Cel: {escape(CORPORATE_BRAND['phone_mobile'])}"
        "</div></div></div>"
    )


def build_transfer_request_excel_bytes(request_rows: list[dict]):
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Traslado"
    sheet.append(["Referencia", "Descripción del producto", "Cantidad"])
    for row in request_rows:
        sheet.append([
            row.get("reference") or row.get("referencia") or "",
            row.get("description") or row.get("descripcion") or "",
            row.get("suggested_qty") or row.get("quantity_requested") or "",
        ])
    buffer = io.BytesIO()
    workbook.save(buffer)
    buffer.seek(0)
    return buffer.getvalue()


def notify_transfer_requests_by_email(request_rows: list[dict], requested_by_user: dict, notes: Optional[str] = None):
    if not request_rows:
        return {"sent": [], "errors": []}

    grouped_rows = {}
    for row in request_rows:
        destination_store_code = normalize_store_code(row.get("destination_store_code"))
        if not destination_store_code:
            continue
        grouped_rows.setdefault(destination_store_code, []).append(row)

    results = {"sent": [], "errors": []}
    cc_emails = get_transfer_cc_emails()
    requested_by_name = requested_by_user.get("full_name") or "Colaborador Ferreinox"
    requested_by_metadata = dict(requested_by_user.get("metadata") or {})
    requested_by_sede = requested_by_metadata.get("sede") or requested_by_metadata.get("store_code") or "Sede origen"
    requested_by_cargo = requested_by_metadata.get("cargo") or requested_by_user.get("role") or "Perfil interno"
    email_map = get_transfer_destination_email_map()

    for destination_store_code, rows in grouped_rows.items():
        to_email = email_map.get(destination_store_code)
        if not to_email:
            results["errors"].append(f"No existe correo configurado para la sede destino {destination_store_code}.")
            continue

        destination_label = rows[0].get("destination_store_name") or STORE_CODE_LABELS.get(destination_store_code) or destination_store_code
        origin_label = rows[0].get("origin_store_name") or requested_by_sede
        attachment_name = f"traslado_{sanitize_filename_segment(origin_label, 'Origen')}_{sanitize_filename_segment(destination_label, 'Destino')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        attachment_bytes = build_transfer_request_excel_bytes(rows)
        body_html = (
            "<p style='margin:0 0 14px 0;font-size:15px;'>Se generó una nueva solicitud interna de traslado desde WhatsApp.</p>"
            f"<div style='background:#ffffff;border:1px solid {CORPORATE_BRAND['brand_border']};border-radius:14px;padding:18px 20px;margin-bottom:18px;'>"
            f"<p style='margin:0 0 8px 0;'><strong>Solicitante:</strong> {escape(requested_by_name)}</p>"
            f"<p style='margin:0 0 8px 0;'><strong>Cargo:</strong> {escape(str(requested_by_cargo))}</p>"
            f"<p style='margin:0 0 8px 0;'><strong>Sede origen:</strong> {escape(str(origin_label))}</p>"
            f"<p style='margin:0 0 8px 0;'><strong>Sede destino:</strong> {escape(str(destination_label))}</p>"
            f"<p style='margin:0;'><strong>Referencias solicitadas:</strong> {len(rows)}</p>"
            "</div>"
            "<table style='width:100%;border-collapse:collapse;background:#ffffff;border:1px solid #e5e7eb;border-radius:12px;overflow:hidden;'>"
            "<thead><tr style='background:#111827;color:#ffffff;'>"
            "<th style='padding:12px;text-align:left;'>Referencia</th>"
            "<th style='padding:12px;text-align:left;'>Descripción</th>"
            "<th style='padding:12px;text-align:center;'>Cantidad</th>"
            "</tr></thead><tbody>"
            + "".join(
                f"<tr><td style='padding:10px 12px;border-top:1px solid #e5e7eb;'>{escape(str(row.get('reference') or row.get('referencia') or ''))}</td>"
                f"<td style='padding:10px 12px;border-top:1px solid #e5e7eb;'>{escape(str(row.get('description') or row.get('descripcion') or ''))}</td>"
                f"<td style='padding:10px 12px;border-top:1px solid #e5e7eb;text-align:center;'>{escape(str(format_quantity(row.get('suggested_qty') or row.get('quantity_requested') or 0)))}</td></tr>"
                for row in rows
            )
            + "</tbody></table>"
            + (f"<p style='margin-top:18px;'><strong>Observaciones:</strong> {escape(notes)}</p>" if notes else "")
            + "<p style='margin-top:18px;'>Se adjunta archivo Excel de control con el detalle exacto del traslado.</p>"
        )
        html_content = build_brand_email_shell("Solicitud de traslado entre sedes", body_html)
        text_content = (
            f"Solicitud de traslado Ferreinox\n"
            f"Solicitante: {requested_by_name}\n"
            f"Cargo: {requested_by_cargo}\n"
            f"Origen: {origin_label}\n"
            f"Destino: {destination_label}\n"
            f"Referencias: {len(rows)}\n"
            f"Observaciones: {notes or 'Sin observaciones'}"
        )
        try:
            send_sendgrid_email(
                to_email,
                f"Solicitud de traslado | {origin_label} -> {destination_label}",
                html_content,
                text_content,
                cc_emails=cc_emails,
                attachments=[
                    {
                        "content": base64.b64encode(attachment_bytes).decode("ascii"),
                        "filename": attachment_name,
                        "type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        "disposition": "attachment",
                    }
                ],
            )
            results["sent"].append(
                {
                    "destination_store_code": destination_store_code,
                    "destination_store_name": destination_label,
                    "to_email": to_email,
                    "cc_emails": cc_emails,
                    "attachment": attachment_name,
                    "count": len(rows),
                }
            )
        except Exception as exc:
            results["errors"].append(f"{destination_label}: {exc}")

    return results


def notify_procurement_request_by_email(shortages: list[dict], requested_by_user: dict, notes: Optional[str] = None):
    if not shortages:
        return {"sent": False, "errors": []}

    to_email = "compras@ferreinox.co"
    requested_by_name = requested_by_user.get("full_name") or "Colaborador Ferreinox"
    requested_by_metadata = dict(requested_by_user.get("metadata") or {})
    requested_by_sede = requested_by_metadata.get("sede") or requested_by_metadata.get("store_code") or "Sede origen"
    destination_label = shortages[0].get("destination_store_name") or "Sede destino"
    attachment_name = f"abastecimiento_{sanitize_filename_segment(destination_label, 'Destino')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    attachment_bytes = build_transfer_request_excel_bytes(shortages)
    body_html = (
        "<p style='margin:0 0 14px 0;font-size:15px;'>Se detectaron faltantes sin origen interno disponible para cumplir pedidos pendientes.</p>"
        f"<div style='background:#ffffff;border:1px solid {CORPORATE_BRAND['brand_border']};border-radius:14px;padding:18px 20px;margin-bottom:18px;'>"
        f"<p style='margin:0 0 8px 0;'><strong>Solicitante:</strong> {escape(requested_by_name)}</p>"
        f"<p style='margin:0 0 8px 0;'><strong>Sede origen:</strong> {escape(str(requested_by_sede))}</p>"
        f"<p style='margin:0 0 8px 0;'><strong>Sede que necesita abastecimiento:</strong> {escape(str(destination_label))}</p>"
        f"<p style='margin:0;'><strong>Referencias sin origen útil:</strong> {len(shortages)}</p>"
        "</div>"
        "<table style='width:100%;border-collapse:collapse;background:#ffffff;border:1px solid #e5e7eb;border-radius:12px;overflow:hidden;'>"
        "<thead><tr style='background:#111827;color:#ffffff;'>"
        "<th style='padding:12px;text-align:left;'>Referencia</th>"
        "<th style='padding:12px;text-align:left;'>Descripción</th>"
        "<th style='padding:12px;text-align:center;'>Faltante</th>"
        "</tr></thead><tbody>"
        + "".join(
            f"<tr><td style='padding:10px 12px;border-top:1px solid #e5e7eb;'>{escape(str(row.get('reference') or ''))}</td>"
            f"<td style='padding:10px 12px;border-top:1px solid #e5e7eb;'>{escape(str(row.get('description') or ''))}</td>"
            f"<td style='padding:10px 12px;border-top:1px solid #e5e7eb;text-align:center;'>{escape(str(format_quantity(row.get('shortage_qty') or row.get('required_qty') or 0)))}</td></tr>"
            for row in shortages
        )
        + "</tbody></table>"
        + (f"<p style='margin-top:18px;'><strong>Observaciones:</strong> {escape(notes)}</p>" if notes else "")
        + "<p style='margin-top:18px;'>Se adjunta Excel con el detalle para abastecimiento o compra.</p>"
    )
    html_content = build_brand_email_shell("Solicitud de abastecimiento / compras", body_html)
    text_content = (
        f"Solicitud de abastecimiento Ferreinox\n"
        f"Solicitante: {requested_by_name}\n"
        f"Sede origen: {requested_by_sede}\n"
        f"Sede destino: {destination_label}\n"
        f"Referencias: {len(shortages)}\n"
        f"Observaciones: {notes or 'Sin observaciones'}"
    )
    try:
        send_sendgrid_email(
            to_email,
            f"Abastecimiento requerido | {destination_label}",
            html_content,
            text_content,
            cc_emails=get_transfer_cc_emails(),
            attachments=[
                {
                    "content": base64.b64encode(attachment_bytes).decode("ascii"),
                    "filename": attachment_name,
                    "type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    "disposition": "attachment",
                }
            ],
        )
        return {"sent": True, "to_email": to_email, "attachment": attachment_name, "errors": []}
    except Exception as exc:
        return {"sent": False, "errors": [str(exc)]}


def get_facturador_routing_config():
    configured_map = None
    raw_json = os.getenv("FACTURADOR_ROUTING_JSON")
    if raw_json:
        try:
            configured_map = json.loads(raw_json)
        except json.JSONDecodeError:
            configured_map = None
    if configured_map is None:
        secrets = load_local_secrets()
        configured_map = secrets.get("facturadores") or secrets.get("facturador_routing") or {}

    sendgrid_config = get_sendgrid_config() or {}
    fallback_email = sendgrid_config.get("ventas_to_email") or sendgrid_config.get("from_email")
    normalized_map = {}
    source_map = configured_map or DEFAULT_FACTURADOR_ROUTING
    for raw_key, raw_entry in source_map.items():
        store_code = normalize_store_code(raw_key)
        if not store_code:
            continue
        entry = raw_entry or {}
        normalized_map[store_code] = {
            "name": entry.get("name") or entry.get("nombre") or DEFAULT_FACTURADOR_ROUTING.get(store_code, {}).get("name") or "Facturación",
            "email": (entry.get("email") or entry.get("correo") or fallback_email or "").strip() or None,
            "phone": normalize_phone_e164(entry.get("phone") or entry.get("telefono") or entry.get("whatsapp") or DEFAULT_FACTURADOR_ROUTING.get(store_code, {}).get("phone")),
        }
    if fallback_email:
        for store_code, fallback_entry in DEFAULT_FACTURADOR_ROUTING.items():
            normalized_map.setdefault(
                store_code,
                {
                    "name": fallback_entry.get("name") or "Facturación",
                    "email": fallback_email,
                    "phone": normalize_phone_e164(fallback_entry.get("phone")),
                },
            )
    return normalized_map


def get_facturador_route_for_store(store_code: Optional[str]):
    store_code = normalize_store_code(store_code)
    if not store_code:
        return None
    employee_candidates = get_employee_facturador_candidates_for_store(store_code)
    if employee_candidates:
        top_candidate = employee_candidates[0]
        return {
            "name": top_candidate.get("full_name") or top_candidate.get("cargo") or "Facturación",
            "email": top_candidate.get("email"),
            "phone": top_candidate.get("phone_e164"),
            "source": "datos_empleados.xlsx",
            "cargo": top_candidate.get("cargo"),
            "sede": top_candidate.get("sede"),
        }
    return get_facturador_routing_config().get(store_code)


def upload_bytes_to_dropbox(content_bytes: bytes, dropbox_path: str):
    dbx = get_dropbox_ventas_client()
    normalized_path = "/" + str(dropbox_path or "").lstrip("/")
    metadata = dbx.files_upload(content_bytes, normalized_path, mode=dropbox.files.WriteMode("overwrite"))
    return metadata.path_display or normalized_path


def build_icg_excel_rows_from_draft(commercial_draft: dict):
    rows = []
    for item in commercial_draft.get("items") or []:
        if item.get("status") != "matched":
            continue
        matched_product = item.get("matched_product") or {}
        product_request = item.get("product_request") or {}
        referencia = matched_product.get("referencia") or matched_product.get("codigo_articulo") or matched_product.get("producto_codigo")
        if not referencia:
            continue
        rows.append(
            {
                "REFERENCIA": referencia,
                "CANTIDAD": parse_numeric_value(product_request.get("requested_quantity")) or 1,
                "PRECIO": parse_numeric_value(matched_product.get("precio") or matched_product.get("precio_venta") or item.get("precio_unitario")) or 0,
                "DESCUENTO": parse_numeric_value(matched_product.get("descuento_pct") or item.get("discount_pct")) or 0,
                "DESCRIPCION": matched_product.get("descripcion") or matched_product.get("nombre_articulo") or item.get("original_text") or referencia,
            }
        )
    return rows


def generate_icg_order_excel_bytes(commercial_draft: dict):
    excel_rows = build_icg_excel_rows_from_draft(commercial_draft)
    if not excel_rows:
        raise RuntimeError("No hay líneas confirmadas para exportar a ICG.")

    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "PedidoICG"
    worksheet.append(["REFERENCIA", "CANTIDAD", "PRECIO", "DESCUENTO"])
    for row in excel_rows:
        worksheet.append([row["REFERENCIA"], row["CANTIDAD"], row["PRECIO"], row["DESCUENTO"]])

    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue(), excel_rows


def build_icg_order_filename(cliente_label: Optional[str], store_code: Optional[str], order_id: int):
    today_label = datetime.now().strftime("%Y-%m-%d")
    cliente_safe = sanitize_filename_segment(cliente_label, "SinCliente")
    tienda_safe = sanitize_filename_segment(get_store_short_label(store_code) or STORE_CODE_LABELS.get(store_code) or store_code or "SinTienda", "SinTienda")
    return f"pedido_{cliente_safe}_{today_label}_{tienda_safe}_{order_id}.xlsx"


def mark_agent_order_status(order_id: int, status: str, metadata_update: Optional[dict] = None, numero_externo: Optional[str] = None):
    if not order_id:
        return
    engine = get_db_engine()
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                UPDATE public.agent_order
                SET estado = :status,
                    numero_externo = COALESCE(:numero_externo, numero_externo),
                    submitted_at = COALESCE(submitted_at, now()),
                    metadata = COALESCE(metadata, '{}'::jsonb) || CAST(:metadata_update AS jsonb),
                    updated_at = now()
                WHERE id = :order_id
                """
            ),
            {
                "order_id": order_id,
                "status": status,
                "numero_externo": numero_externo,
                "metadata_update": safe_json_dumps(metadata_update or {}),
            },
        )


def upsert_order_dispatch_record(
    order_id: int,
    conversation_id: int,
    contact_id: Optional[int],
    cliente_id: Optional[int],
    destination_store_code: Optional[str],
    destination_store_name: Optional[str],
    export_filename: str,
    dropbox_folder: str,
    dropbox_path: str,
    facturador_route: Optional[dict],
    exported_by_user_id: Optional[int],
    observations: Optional[str],
    metadata: Optional[dict] = None,
    status: str = "pendiente",
    email_sent: bool = False,
    whatsapp_sent: bool = False,
):
    engine = get_db_engine()
    with engine.begin() as connection:
        dispatch_id = connection.execute(
            text(
                """
                INSERT INTO public.agent_order_dispatch (
                    order_id,
                    conversation_id,
                    contacto_id,
                    cliente_id,
                    destination_store_code,
                    destination_store_name,
                    exported_by_user_id,
                    facturador_name,
                    facturador_email,
                    facturador_phone,
                    export_filename,
                    dropbox_folder,
                    dropbox_path,
                    status,
                    observations,
                    metadata,
                    exported_at,
                    notified_email_at,
                    notified_whatsapp_at,
                    created_at,
                    updated_at
                )
                VALUES (
                    :order_id,
                    :conversation_id,
                    :contact_id,
                    :cliente_id,
                    :destination_store_code,
                    :destination_store_name,
                    :exported_by_user_id,
                    :facturador_name,
                    :facturador_email,
                    :facturador_phone,
                    :export_filename,
                    :dropbox_folder,
                    :dropbox_path,
                    :status,
                    :observations,
                    CAST(:metadata AS jsonb),
                    now(),
                    CASE WHEN :email_sent THEN now() ELSE NULL END,
                    CASE WHEN :whatsapp_sent THEN now() ELSE NULL END,
                    now(),
                    now()
                )
                ON CONFLICT (order_id)
                DO UPDATE SET
                    conversation_id = EXCLUDED.conversation_id,
                    contacto_id = EXCLUDED.contacto_id,
                    cliente_id = EXCLUDED.cliente_id,
                    destination_store_code = EXCLUDED.destination_store_code,
                    destination_store_name = EXCLUDED.destination_store_name,
                    exported_by_user_id = EXCLUDED.exported_by_user_id,
                    facturador_name = EXCLUDED.facturador_name,
                    facturador_email = EXCLUDED.facturador_email,
                    facturador_phone = EXCLUDED.facturador_phone,
                    export_filename = EXCLUDED.export_filename,
                    dropbox_folder = EXCLUDED.dropbox_folder,
                    dropbox_path = EXCLUDED.dropbox_path,
                    status = EXCLUDED.status,
                    observations = EXCLUDED.observations,
                    metadata = COALESCE(public.agent_order_dispatch.metadata, '{}'::jsonb) || EXCLUDED.metadata,
                    exported_at = now(),
                    notified_email_at = CASE WHEN :email_sent THEN now() ELSE public.agent_order_dispatch.notified_email_at END,
                    notified_whatsapp_at = CASE WHEN :whatsapp_sent THEN now() ELSE public.agent_order_dispatch.notified_whatsapp_at END,
                    updated_at = now()
                RETURNING id
                """
            ),
            {
                "order_id": order_id,
                "conversation_id": conversation_id,
                "contact_id": contact_id,
                "cliente_id": cliente_id,
                "destination_store_code": destination_store_code,
                "destination_store_name": destination_store_name,
                "exported_by_user_id": exported_by_user_id,
                "facturador_name": (facturador_route or {}).get("name"),
                "facturador_email": (facturador_route or {}).get("email"),
                "facturador_phone": (facturador_route or {}).get("phone"),
                "export_filename": export_filename,
                "dropbox_folder": dropbox_folder,
                "dropbox_path": dropbox_path,
                "status": status,
                "observations": observations,
                "metadata": safe_json_dumps(metadata or {}),
                "email_sent": email_sent,
                "whatsapp_sent": whatsapp_sent,
            },
        ).scalar_one()
    return dispatch_id


def notify_facturador_about_order(
    order_id: int,
    cliente_label: str,
    store_code: Optional[str],
    file_name: str,
    dropbox_path: str,
    facturador_route: Optional[dict],
    observations: Optional[str],
):
    route = facturador_route or {}
    store_label = get_store_short_label(store_code) or STORE_CODE_LABELS.get(store_code) or "sede sin definir"
    facturador_name = route.get("name") or "equipo de facturación"
    subject = f"Ferreinox | Pedido ICG listo {file_name}"
    text_content = (
        f"Hola {facturador_name}.\n\n"
        f"Ya quedó exportado un pedido para {store_label}.\n"
        f"Cliente: {cliente_label}\n"
        f"Pedido interno: {order_id}\n"
        f"Archivo: {file_name}\n"
        f"Ruta Dropbox: {dropbox_path}\n"
        f"Observación: {observations or 'Sin observación'}\n\n"
        "Por favor valida la carpeta compartida y continúa la facturación."
    )
    html_content = (
        "<div style='font-family:Segoe UI,Arial,sans-serif;background:#f4f6f8;padding:24px;color:#111827'>"
        "<div style='max-width:760px;margin:0 auto;background:#ffffff;border:1px solid #e5e7eb;border-radius:18px;padding:28px'>"
        f"<h1 style='margin-top:0'>Pedido listo para facturación</h1>"
        f"<p><strong>Facturador:</strong> {escape(facturador_name)}</p>"
        f"<p><strong>Tienda destino:</strong> {escape(store_label)}</p>"
        f"<p><strong>Cliente:</strong> {escape(cliente_label)}</p>"
        f"<p><strong>Pedido interno:</strong> {order_id}</p>"
        f"<p><strong>Archivo ICG:</strong> {escape(file_name)}</p>"
        f"<p><strong>Ruta Dropbox:</strong> {escape(dropbox_path)}</p>"
        f"<p><strong>Observación:</strong> {escape(observations or 'Sin observación')}</p>"
        "<p>Revisa la carpeta compartida y continúa el proceso en ICG.</p>"
        "</div></div>"
    )

    email_sent = False
    whatsapp_sent = False
    errors = []
    if route.get("email"):
        try:
            send_sendgrid_email(route["email"], subject, html_content, text_content)
            email_sent = True
        except Exception as exc:
            errors.append(f"email: {exc}")
    if route.get("phone"):
        whatsapp_body = (
            f"Hola {facturador_name}, ya quedó exportado el pedido {order_id} para {store_label}. "
            f"Cliente: {cliente_label}. Archivo: {file_name}. Ruta: {dropbox_path}."
        )
        try:
            send_whatsapp_text_message(route["phone"], whatsapp_body)
            whatsapp_sent = True
        except Exception as exc:
            errors.append(f"whatsapp: {exc}")
    return {
        "email_sent": email_sent,
        "whatsapp_sent": whatsapp_sent,
        "email": route.get("email"),
        "phone": route.get("phone"),
        "errors": errors,
    }


def export_confirmed_order_to_icg(
    order_id: int,
    context: dict,
    commercial_draft: dict,
    cliente_contexto: Optional[dict],
    internal_user: Optional[dict],
):
    store_filters = commercial_draft.get("store_filters") or []
    store_code = normalize_store_code(store_filters[0]) if store_filters else None
    if not store_code:
        raise RuntimeError("El pedido no tiene tienda o ciudad definida para exportar a ICG.")

    file_name = build_icg_order_filename(
        (cliente_contexto or {}).get("nombre_cliente") or context.get("nombre_visible"),
        store_code,
        order_id,
    )
    excel_bytes, excel_rows = generate_icg_order_excel_bytes(commercial_draft)
    dropbox_folder = get_dropbox_icg_orders_folder()
    dropbox_path = upload_bytes_to_dropbox(excel_bytes, f"{dropbox_folder}/{file_name}")
    facturador_route = get_facturador_route_for_store(store_code)
    observations = commercial_draft.get("facturador_notes") or commercial_draft.get("observaciones") or commercial_draft.get("nombre_despacho")
    notification_result = notify_facturador_about_order(
        order_id,
        (cliente_contexto or {}).get("nombre_cliente") or context.get("nombre_visible") or "Cliente Ferreinox",
        store_code,
        file_name,
        dropbox_path,
        facturador_route,
        observations,
    )
    dispatch_id = upsert_order_dispatch_record(
        order_id=order_id,
        conversation_id=context["conversation_id"],
        contact_id=context.get("contact_id"),
        cliente_id=context.get("cliente_id"),
        destination_store_code=store_code,
        destination_store_name=STORE_CODE_LABELS.get(store_code),
        export_filename=file_name,
        dropbox_folder=dropbox_folder,
        dropbox_path=dropbox_path,
        facturador_route=facturador_route,
        exported_by_user_id=(internal_user or {}).get("id"),
        observations=observations,
        metadata={"excel_rows": excel_rows, "notificacion": notification_result},
        status="pendiente",
        email_sent=notification_result.get("email_sent", False),
        whatsapp_sent=notification_result.get("whatsapp_sent", False),
    )
    mark_agent_order_status(
        order_id,
        "enviado_erp",
        metadata_update={
            "dispatch_id": dispatch_id,
            "dropbox_path": dropbox_path,
            "facturador": facturador_route,
            "icg_filename": file_name,
        },
        numero_externo=f"PED-{order_id}",
    )
    return {
        "dispatch_id": dispatch_id,
        "dropbox_path": dropbox_path,
        "dropbox_folder": dropbox_folder,
        "file_name": file_name,
        "facturador": facturador_route,
        "notification": notification_result,
    }


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


def translate_product_to_commercial(description: Optional[str], presentation: Optional[str] = None, brand: Optional[str] = None):
    """Convert raw DB descriptions like 'PQ VINILTEX ADV MAT BLANCO 1501 18.93L' to commercial language."""
    if not description:
        return "producto"
    raw = str(description).strip()
    # Remove common prefixes
    for prefix in ["PQ ", "IQ ", "EQ ", "SQ ", "MEG "]:
        if raw.upper().startswith(prefix):
            raw = raw[len(prefix):].strip()
    # Remove size suffixes like 18.93L, 3.79L, 0.95L, 0.22L
    cleaned = re.sub(r"\s+\d+\.\d+L$", "", raw, flags=re.IGNORECASE)
    # Remove trailing reference codes like " 1501", " 12286", but only at end
    cleaned = re.sub(r"\s+\d{3,6}$", "", cleaned)
    # Clean up double-quoted inches
    cleaned = cleaned.replace('""', '"').replace('"', '"')
    # Title case
    words = cleaned.split()
    titled_words = []
    skip_words = {"BR", "MAT", "ADV", "SAT", "SB", "CRE", "DEEP"}
    for w in words:
        if w.upper() in skip_words:
            continue
        titled_words.append(w.capitalize())
    commercial_name = " ".join(titled_words).strip()
    if not commercial_name:
        commercial_name = raw.title()
    # Add presentation label
    pres_label = ""
    if presentation:
        pres_map = {"cuñete": "en cuñete", "galon": "en galón", "cuarto": "en cuarto"}
        pres_label = pres_map.get(presentation, f"en {presentation}")
    if pres_label:
        commercial_name = f"{commercial_name} {pres_label}"
    return commercial_name


def get_exact_product_description(product_row: Optional[dict]):
    raw_description = (product_row or {}).get("descripcion") or (product_row or {}).get("nombre_articulo") or "producto"
    return re.sub(r"\s+", " ", str(raw_description).strip())


def build_product_audit_label(product_row: Optional[dict]):
    row = product_row or {}
    reference_value = row.get("referencia") or row.get("codigo_articulo") or row.get("codigo") or row.get("producto_codigo") or "sin referencia"
    return f"[{reference_value}] - {get_exact_product_description(row)}"


def has_meaningful_product_anchor(product_request: Optional[dict]):
    request = product_request or {}
    if request.get("product_codes") or request.get("brand_filters"):
        return True
    return bool(get_specific_product_terms(request))


def build_followup_inventory_request(text_value: Optional[str], product_request: Optional[dict], conversation_context: Optional[dict]):
    request = dict(product_request or {})
    previous_request = dict((conversation_context or {}).get("last_product_request") or {})
    if not previous_request or has_meaningful_product_anchor(request):
        return request

    has_followup_filter = any(
        request.get(field_name)
        for field_name in [
            "requested_unit",
            "store_filters",
            "direction_filters",
            "size_filters",
            "color_filters",
            "finish_filters",
        ]
    )
    if not has_followup_filter:
        return request

    # Short follow-ups like 'el de galon en ferrebox' should inherit the last confirmed product anchor.
    merged_request = dict(previous_request)
    for field_name in [
        "requested_quantity",
        "requested_unit",
        "quantity_expression",
        "store_filters",
        "direction_filters",
        "size_filters",
        "color_filters",
        "finish_filters",
        "brand_filters",
    ]:
        current_value = request.get(field_name)
        if current_value:
            if isinstance(current_value, list):
                merged_request[field_name] = merge_unique_terms(merged_request.get(field_name), current_value)
            else:
                merged_request[field_name] = current_value
    merged_request["original_query"] = text_value or request.get("original_query") or previous_request.get("original_query") or ""
    merged_request["followup_from_previous_product"] = True
    return merged_request


def is_technical_advisory_message(text_value: Optional[str]):
    """Detect if the client is asking for product application advice, not a product search."""
    normalized = normalize_text_value(text_value)
    if not normalized:
        return False
    return any(keyword in normalized for keyword in TECHNICAL_ADVISORY_KEYWORDS)


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
    if normalized in {"si", "sí", "esa", "ese", "la primera", "la segunda", "la tercera", "opcion 1", "opcion 2", "opcion 3"}:
        return False
    return len(normalized) >= 4


def contains_product_correction_signal(text_value: Optional[str]):
    normalized = normalize_text_value(text_value)
    if not normalized:
        return False
    return any(
        phrase in normalized
        for phrase in [
            "no era",
            "me corrijo",
            "corrijo",
            "quise decir",
            "mas bien",
            "más bien",
            "no ese",
            "no esa",
            "cambialo",
            "cámbialo",
            "cambio la referencia",
            "la referencia correcta",
        ]
    )


def should_merge_previous_learning_phrase(current_request: Optional[dict], previous_request: Optional[dict]):
    if not current_request or not previous_request:
        return False
    if contains_product_correction_signal(current_request.get("original_query")):
        return False
    current_codes = {normalize_reference_value(value) for value in (current_request.get("product_codes") or []) if value}
    previous_codes = {normalize_reference_value(value) for value in (previous_request.get("product_codes") or []) if value}
    if current_codes and previous_codes and current_codes != previous_codes:
        return False
    current_terms = set(get_specific_product_terms(current_request) or current_request.get("core_terms") or [])
    previous_terms = set(get_specific_product_terms(previous_request) or previous_request.get("core_terms") or [])
    if current_terms and previous_terms and not (current_terms & previous_terms):
        return False
    return True


def resolve_confirmed_learning_product_row(description_asociada: str, conversation_context: Optional[dict]):
    clarification_options = list((conversation_context or {}).get("clarification_options") or [])
    selected_option = resolve_product_clarification_choice(description_asociada, clarification_options)
    if selected_option:
        return {
            "referencia": selected_option.get("reference") or selected_option.get("referencia"),
            "descripcion": selected_option.get("name") or selected_option.get("descripcion"),
            "marca": selected_option.get("brand") or selected_option.get("marca"),
            "presentacion_canonica": selected_option.get("presentation") or selected_option.get("presentacion_canonica"),
        }

    learning_request = prepare_product_request_for_search(description_asociada)
    product_rows = lookup_product_context(description_asociada, learning_request)
    reliable_rows = select_reliable_learning_rows(learning_request, product_rows)
    if len(reliable_rows) == 1:
        return reliable_rows[0]

    explicit_codes = extract_product_codes(description_asociada)
    if explicit_codes and product_rows:
        normalized_codes = {normalize_reference_value(code) for code in explicit_codes}
        for row in product_rows:
            row_code = normalize_reference_value(row.get("referencia") or row.get("codigo_articulo"))
            if row_code and row_code in normalized_codes:
                return row
    return None


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


def ensure_product_companion_table():
    engine = get_db_engine()
    with engine.begin() as connection:
        connection.execute(
            text(
                """
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
                )
                """
            )
        )
        connection.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS idx_agent_product_companion_ref
                ON public.agent_product_companion(producto_referencia)
                """
            )
        )
        connection.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS idx_agent_product_companion_companion
                ON public.agent_product_companion(companion_referencia)
                """
            )
        )


def fetch_product_companions(referencia: str) -> list[dict]:
    """Fetch all active companion/complementary products for a given reference."""
    if not referencia:
        return []
    try:
        engine = get_db_engine()
        with engine.connect() as connection:
            rows = connection.execute(
                text(
                    """
                    SELECT c.companion_referencia, c.companion_descripcion, c.tipo_relacion,
                           c.proporcion, c.notas, c.confidence,
                           p.stock_total, p.descripcion AS descripcion_inventario
                    FROM public.agent_product_companion c
                    LEFT JOIN public.productos p ON p.referencia = c.companion_referencia
                    WHERE c.producto_referencia = :ref AND c.activo = true
                    ORDER BY c.tipo_relacion, c.confidence DESC
                    """
                ),
                {"ref": str(referencia)},
            ).mappings().all()
            return [dict(r) for r in rows]
    except Exception:
        return []


# ---------------------------------------------------------------------------
# RAG: búsqueda semántica en fichas técnicas vectorizadas
# ---------------------------------------------------------------------------

def _generate_query_embedding(query_text: str) -> list[float] | None:
    """Generate embedding vector for a search query using OpenAI."""
    try:
        client = get_openai_client()
        response = client.embeddings.create(
            model="text-embedding-3-small",
            input=query_text.strip(),
            dimensions=1536,
        )
        return response.data[0].embedding
    except Exception:
        return None


def search_technical_chunks(query: str, top_k: int = 5, marca_filter: str | None = None) -> list[dict]:
    """Semantic search over vectorized technical sheet chunks using pgvector cosine distance."""
    embedding = _generate_query_embedding(query)
    if not embedding:
        return []

    embedding_literal = "[" + ",".join(str(v) for v in embedding) + "]"

    marca_clause = ""
    params: list = [embedding_literal, embedding_literal, top_k]
    if marca_filter:
        marca_clause = "AND LOWER(marca) = LOWER(%s)"
        params = [embedding_literal, embedding_literal, marca_filter, top_k]

    try:
        engine = get_db_engine()
        raw_conn = engine.raw_connection()
        try:
            cur = raw_conn.cursor()
            cur.execute(
                f"""
                SELECT doc_filename, doc_path_lower, chunk_index, chunk_text,
                       marca, familia_producto, tipo_documento,
                       1 - (embedding <=> %s::vector) AS similarity
                FROM public.agent_technical_doc_chunk
                WHERE 1=1 {marca_clause}
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


def build_rag_context(chunks: list[dict], max_chunks: int = 4) -> str:
    """Build a textual context from RAG chunks for injection into the agent prompt."""
    if not chunks:
        return ""
    parts = []
    seen_files = set()
    for chunk in chunks[:max_chunks]:
        similarity = chunk.get("similarity", 0)
        if similarity < 0.25:
            continue
        filename = chunk.get("doc_filename", "desconocido")
        text_content = (chunk.get("chunk_text") or "").strip()
        if not text_content:
            continue
        header = f"[Fuente: {filename}]"
        parts.append(f"{header}\n{text_content}")
        seen_files.add(filename)
    if not parts:
        return ""
    return "\n\n---\n\n".join(parts)


def learn_product_resolution(conversation_id: Optional[int], product_request: Optional[dict], product_context: list[dict], conversation_context: Optional[dict] = None):
    if not product_request or not product_context:
        return

    reliable_rows = select_reliable_learning_rows(product_request, product_context)
    if not reliable_rows:
        return

    # --- Anti-tambor filter: never learn absurd presentations ---
    BANNED_LEARNING_TOKENS = ["tambor", "50 galones", "55 galones", "200 litros"]
    original_query_lower = (product_request.get("original_query") or "").lower()
    filtered_rows = []
    for row in reliable_rows:
        desc_lower = ((row.get("descripcion") or row.get("nombre_articulo")) or "").lower()
        if any(token in desc_lower for token in BANNED_LEARNING_TOKENS):
            if not any(token in original_query_lower for token in BANNED_LEARNING_TOKENS):
                continue
        filtered_rows.append(row)
    reliable_rows = filtered_rows
    if not reliable_rows:
        return

    phrases = []
    previous_product_request = (conversation_context or {}).get("last_product_request") or {}
    phrase_groups = [build_learning_phrase_candidates(product_request)]
    if should_merge_previous_learning_phrase(product_request, previous_product_request):
        phrase_groups.append(build_learning_phrase_candidates(previous_product_request))
    for candidate_phrase in [phrase for group in phrase_groups for phrase in group]:
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

    phrases = build_learning_phrase_candidates(product_request)

    # Also search learning table by product codes (P-53, 17174, etc.)
    for code in (product_request.get("product_codes") or []):
        normalized_code = normalize_text_value(str(code))
        if normalized_code and normalized_code not in phrases:
            phrases.insert(0, normalized_code)

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

    raw_candidates = re.findall(r"\b[a-z]?\d[a-z0-9-]{1,14}\b|\b\d{4,10}\b|\b[a-z0-9-]{4,16}\b", normalized)
    for prefix, suffix in re.findall(r"\b(sku|ref|referencia|cod|codigo)\s*[-/]?\s*(\d{3,10}[a-z0-9-]{0,8})\b", normalized):
        raw_candidates.append(f"{prefix}{suffix}")

    for raw_code in raw_candidates:
        cleaned_code = normalize_reference_value(raw_code)
        if len(cleaned_code) < 3 or cleaned_code in seen_codes or cleaned_code in excluded_codes:
            continue
        has_letters = bool(re.search(r"[a-z]", cleaned_code))
        has_digits = bool(re.search(r"\d", cleaned_code))
        if not re.fullmatch(r"\d{4,10}", cleaned_code) and not (has_letters and has_digits):
            continue
        if re.fullmatch(r"\d{1,3}mm", cleaned_code):
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
    explicit_presentation = canonicalize_presentation_value(product_row.get("presentacion_canonica"))
    if explicit_presentation:
        return explicit_presentation
    description_value = normalize_text_value(product_row.get("descripcion") or product_row.get("nombre_articulo"))
    for canonical_value, aliases in PRESENTATION_ALIASES.items():
        if any(normalize_text_value(alias) and normalize_text_value(alias) in description_value for alias in aliases):
            return canonical_value
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


def infer_product_color_from_row(product_row: dict):
    color_value = normalize_nullable_phrase(product_row.get("color_detectado") or product_row.get("color_raiz"))
    if color_value:
        return color_value
    description_value = normalize_text_value(product_row.get("descripcion") or product_row.get("nombre_articulo"))
    for compound_color in ["verde bronce", "blanco puro", "rojo fiesta", "verde esmeralda"]:
        if compound_color in description_value:
            return compound_color
    for candidate_color in ["blanco", "negro", "gris", "rojo", "verde", "azul", "amarillo", "naranja", "marfil", "crema", "bronce", "transparente"]:
        if re.search(rf"\b{re.escape(candidate_color)}\b", description_value):
            return candidate_color
    return None


def infer_product_finish_from_row(product_row: dict):
    finish_value = normalize_nullable_phrase(product_row.get("acabado_detectado"))
    if finish_value:
        return finish_value
    description_value = normalize_text_value(product_row.get("descripcion") or product_row.get("nombre_articulo"))
    for candidate_finish in ["mate", "brillante", "satinado", "semibrillante", "semimate", "texturizado"]:
        if re.search(rf"\b{re.escape(candidate_finish)}\b", description_value):
            return candidate_finish
    return None


def row_matches_requested_colors(product_row: dict, requested_colors: list[str]):
    if not requested_colors:
        return False

    inferred_color = infer_product_color_from_row(product_row)
    description_value = normalize_text_value(product_row.get("descripcion") or product_row.get("nombre_articulo"))
    description_tokens = tokenize_search_phrase(description_value)
    for color_value in requested_colors:
        normalized_color = normalize_text_value(color_value)
        if not normalized_color:
            continue
        if inferred_color == normalized_color or normalized_color in description_value:
            return True
        color_tokens = tokenize_search_phrase(normalized_color)
        if color_tokens and all(
            any(
                desc_token.startswith(color_token[:4]) or color_token.startswith(desc_token[:4])
                for desc_token in description_tokens
            )
            for color_token in color_tokens
        ):
            return True
    return False


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


def get_product_variant_signature(product_row: Optional[dict]):
    row = product_row or {}
    family_value = normalize_text_value(row.get("producto_padre_busqueda") or row.get("familia_consulta"))
    if family_value:
        return family_value

    raw_description = get_exact_product_description(row)
    cleaned_description = re.sub(r"^\s*(?:PQ|IQ|EQ|SQ|MEG)\s+", "", raw_description, flags=re.IGNORECASE)
    cleaned_description = re.sub(r"\s+\d+(?:\.\d+)?L\b", "", cleaned_description, flags=re.IGNORECASE)
    cleaned_description = re.sub(r"\s+", " ", cleaned_description).strip()
    return normalize_text_value(cleaned_description)


def get_product_variant_label(product_row: Optional[dict]):
    row = product_row or {}
    family_value = (row.get("producto_padre_busqueda") or row.get("familia_consulta") or "").strip()
    if family_value:
        return re.sub(r"\s+", " ", family_value)

    raw_description = get_exact_product_description(row)
    cleaned_description = re.sub(r"^\s*(?:PQ|IQ|EQ|SQ|MEG)\s+", "", raw_description, flags=re.IGNORECASE)
    cleaned_description = re.sub(r"\s+\d+(?:\.\d+)?L\b", "", cleaned_description, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", cleaned_description).strip()


def should_ask_product_clarification(product_request: Optional[dict], product_context: list[dict]):
    if not product_request or not product_context:
        return False

    top_candidates = product_context[:4]
    unique_references = {row.get("referencia") or row.get("codigo_articulo") for row in top_candidates if row.get("referencia") or row.get("codigo_articulo")}
    if len(unique_references) < 2:
        return False

    variant_signatures = {get_product_variant_signature(row) for row in top_candidates}
    variant_signatures.discard(None)
    variant_signatures.discard("")

    if product_request.get("product_codes") and len(variant_signatures) >= 2:
        return True

    presentation_values = {infer_product_presentation_from_row(row) for row in top_candidates}
    brand_values = {infer_product_brand_from_row(row) for row in top_candidates}
    direction_values = {infer_product_direction_from_row(row) for row in top_candidates}
    color_values = {infer_product_color_from_row(row) for row in top_candidates}
    finish_values = {infer_product_finish_from_row(row) for row in top_candidates}
    presentation_values.discard(None)
    brand_values.discard(None)
    direction_values.discard(None)
    color_values.discard(None)
    finish_values.discard(None)

    if not product_request.get("requested_unit") and len(presentation_values) >= 2:
        return True
    if len(brand_values) >= 2:
        return True
    if not (product_request.get("direction_filters") or []) and len(direction_values) >= 2:
        return True
    if not (product_request.get("color_filters") or []) and len(color_values) >= 2:
        return True
    if not (product_request.get("finish_filters") or []) and len(finish_values) >= 2:
        return True
    return False


def build_best_product_clarification_question(product_request: Optional[dict], product_context: list[dict]):
    top_candidates = product_context[:4]
    for row in top_candidates:
        question = (row.get("pregunta_desambiguacion") or "").strip()
        if question:
            return question

    variant_labels = []
    seen_variant_labels = set()
    for row in top_candidates:
        variant_label = get_product_variant_label(row)
        variant_signature = get_product_variant_signature(row)
        if not variant_label or not variant_signature or variant_signature in seen_variant_labels:
            continue
        seen_variant_labels.add(variant_signature)
        variant_labels.append(variant_label)

    presentation_values = {infer_product_presentation_from_row(row) for row in top_candidates}
    brand_values = {infer_product_brand_from_row(row) for row in top_candidates}
    color_values = {infer_product_color_from_row(row) for row in top_candidates}
    finish_values = {infer_product_finish_from_row(row) for row in top_candidates}
    presentation_values.discard(None)
    brand_values.discard(None)
    color_values.discard(None)
    finish_values.discard(None)

    if (product_request or {}).get("product_codes") and len(variant_labels) >= 2:
        options_text = ", ".join(variant_labels[:3])
        return f"Encontré ese código con varias descripciones exactas: {options_text}. ¿Cuál necesitas exactamente?"

    if not (product_request or {}).get("requested_unit") and len(presentation_values) >= 2:
        return "¿Lo necesitas en cuarto, galón o cuñete?"
    if not (product_request or {}).get("brand_filters") and len(brand_values) >= 2:
        brand_options = ", ".join(sorted(str(value).title() for value in brand_values))
        return f"Tengo opciones de {brand_options}. ¿Cuál marca buscas?"
    if not (product_request or {}).get("finish_filters") and len(finish_values) >= 2:
        finish_options = " y ".join(sorted(str(value) for value in finish_values))
        return f"Tengo esa línea en acabado {finish_options}. ¿Cuál necesitas?"
    if not (product_request or {}).get("color_filters") and len(color_values) >= 2:
        return "Tengo varias opciones de color en esa línea. ¿Cuál color necesitas exactamente?"
    return "Tengo varias opciones cercanas. ¿Cuál necesitas exactamente?"


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
        elif len(normalized_key) >= 4:
            best_ratio = 0.0
            best_aliases = None
            for alias_key, aliases in PORTFOLIO_ALIASES.items():
                if len(alias_key) < 4:
                    continue
                ratio = SequenceMatcher(None, normalized_key, alias_key).ratio()
                if ratio >= 0.75 and ratio > best_ratio:
                    best_ratio = ratio
                    best_aliases = aliases
            if best_aliases:
                for alias_term in best_aliases:
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
                SELECT id, cliente_id, resumen, contexto, last_message_at
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
        # Exact match first
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

        # Prefix match for NITs with verification digit (e.g. 1088266407 matches 10882664078)
        if row is None:
            row = connection.execute(
                text(
                    """
                    SELECT cod_cliente, nombre_cliente, nit
                    FROM public.vw_estado_cartera
                    WHERE regexp_replace(COALESCE(nit, ''), '[^0-9]', '', 'g') LIKE :document_prefix
                    ORDER BY fecha_documento DESC NULLS LAST
                    LIMIT 1
                    """
                ),
                {"document_prefix": f"{normalized_document}%"},
            ).mappings().one_or_none()

        if row is None:
            row = connection.execute(
                text(
                    """
                    SELECT codigo AS cod_cliente, nombre_legal AS nombre_cliente, numero_documento AS nit
                    FROM public.cliente
                    WHERE regexp_replace(COALESCE(numero_documento, ''), '[^0-9]', '', 'g') = :document_number
                       OR regexp_replace(COALESCE(numero_documento, ''), '[^0-9]', '', 'g') LIKE :document_prefix
                    LIMIT 1
                    """
                ),
                {"document_number": normalized_document, "document_prefix": f"{normalized_document}%"},
            ).mappings().one_or_none()

        # Also search in cod_cliente (some systems use cédula as client code)
        if row is None:
            row = connection.execute(
                text(
                    """
                    SELECT cod_cliente, nombre_cliente, nit
                    FROM public.vw_estado_cartera
                    WHERE regexp_replace(COALESCE(cod_cliente::text, ''), '[^0-9]', '', 'g') = :document_number
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


def fetch_pending_dispatches(destination_store_code: Optional[str] = None, limit: int = 8):
    where_sql = "WHERE d.status IN ('pendiente', 'en_transito')"
    params = {"limit": limit}
    if destination_store_code:
        where_sql += " AND d.destination_store_code = :destination_store_code"
        params["destination_store_code"] = normalize_store_code(destination_store_code)

    engine = get_db_engine()
    with engine.connect() as connection:
        rows = connection.execute(
            text(
                f"""
                SELECT
                    d.id,
                    d.order_id,
                    d.status,
                    d.destination_store_code,
                    d.destination_store_name,
                    d.facturador_name,
                    d.facturador_email,
                    d.export_filename,
                    d.dropbox_path,
                    d.exported_at,
                    o.numero_externo,
                    o.resumen,
                    wc.nombre_visible AS contacto_nombre
                FROM public.agent_order_dispatch d
                LEFT JOIN public.agent_order o ON o.id = d.order_id
                LEFT JOIN public.whatsapp_contacto wc ON wc.id = d.contacto_id
                {where_sql}
                ORDER BY d.exported_at DESC NULLS LAST, d.id DESC
                LIMIT :limit
                """
            ),
            params,
        ).mappings().all()
    return [dict(row) for row in rows]


def fetch_pending_dispatch_shortages(destination_store_code: Optional[str] = None, limit: int = 20):
    where_sql = "WHERE d.status IN ('pendiente', 'en_transito')"
    params = {"limit": limit}
    normalized_destination = normalize_store_code(destination_store_code)
    if normalized_destination:
        where_sql += " AND d.destination_store_code = :destination_store_code"
        params["destination_store_code"] = normalized_destination

    engine = get_db_engine()
    with engine.connect() as connection:
        rows = connection.execute(
            text(
                f"""
                WITH pending_lines AS (
                    SELECT
                        d.id AS dispatch_id,
                        d.order_id,
                        d.destination_store_code,
                        d.destination_store_name,
                        ol.referencia,
                        MAX(ol.descripcion) AS descripcion,
                        SUM(COALESCE(ol.cantidad, 0)) AS required_qty
                    FROM public.agent_order_dispatch d
                    JOIN public.agent_order_line ol ON ol.order_id = d.order_id
                    {where_sql}
                    GROUP BY 1, 2, 3, 4, 5
                ),
                destination_stock AS (
                    SELECT
                        referencia,
                        cod_almacen,
                        COALESCE(SUM(stock_disponible), 0) AS stock_destino
                    FROM public.vw_inventario_agente
                    GROUP BY 1, 2
                )
                SELECT
                    p.dispatch_id,
                    p.order_id,
                    p.destination_store_code,
                    p.destination_store_name,
                    p.referencia,
                    p.descripcion,
                    p.required_qty,
                    COALESCE(ds.stock_destino, 0) AS stock_destino,
                    GREATEST(p.required_qty - COALESCE(ds.stock_destino, 0), 0) AS shortage_qty
                FROM pending_lines p
                LEFT JOIN destination_stock ds
                    ON ds.referencia = p.referencia
                   AND ds.cod_almacen = p.destination_store_code
                WHERE GREATEST(p.required_qty - COALESCE(ds.stock_destino, 0), 0) > 0
                ORDER BY shortage_qty DESC, p.required_qty DESC, p.referencia ASC
                LIMIT :limit
                """
            ),
            params,
        ).mappings().all()
    return [dict(row) for row in rows]


def fetch_best_origin_stock_for_reference(referencia: str, destination_store_code: str, preferred_origin_store_code: Optional[str] = None):
    where_sql = "WHERE referencia = :referencia AND cod_almacen <> :destination_store_code AND COALESCE(stock_disponible, 0) > 0"
    params = {"referencia": referencia, "destination_store_code": normalize_store_code(destination_store_code)}
    origin_code = normalize_store_code(preferred_origin_store_code)
    if origin_code:
        where_sql += " AND cod_almacen = :origin_store_code"
        params["origin_store_code"] = origin_code

    engine = get_db_engine()
    with engine.connect() as connection:
        row = connection.execute(
            text(
                f"""
                SELECT
                    cod_almacen AS origin_store_code,
                    almacen_nombre AS origin_store_name,
                    referencia,
                    MAX(descripcion) AS descripcion,
                    COALESCE(SUM(stock_disponible), 0) AS stock_origen
                FROM public.vw_inventario_agente
                {where_sql}
                GROUP BY 1, 2, 3
                ORDER BY stock_origen DESC, origin_store_name ASC
                LIMIT 1
                """
            ),
            params,
        ).mappings().first()
    return dict(row) if row else None


def build_transfer_suggestions_for_pending_dispatches(destination_store_code: Optional[str], preferred_origin_store_code: Optional[str] = None, limit: int = 6):
    suggestions = []
    for shortage in fetch_pending_dispatch_shortages(destination_store_code, limit=limit * 2):
        origin_stock = fetch_best_origin_stock_for_reference(
            shortage.get("referencia"),
            shortage.get("destination_store_code"),
            preferred_origin_store_code,
        )
        if not origin_stock:
            continue
        available_qty = parse_numeric_value(origin_stock.get("stock_origen")) or 0
        shortage_qty = parse_numeric_value(shortage.get("shortage_qty")) or 0
        suggested_qty = min(available_qty, shortage_qty)
        if suggested_qty <= 0:
            continue
        suggestions.append(
            {
                "dispatch_id": shortage.get("dispatch_id"),
                "order_id": shortage.get("order_id"),
                "reference": shortage.get("referencia"),
                "description": shortage.get("descripcion"),
                "destination_store_code": shortage.get("destination_store_code"),
                "destination_store_name": shortage.get("destination_store_name"),
                "destination_stock": shortage.get("stock_destino"),
                "required_qty": shortage.get("required_qty"),
                "shortage_qty": shortage_qty,
                "origin_store_code": origin_stock.get("origin_store_code"),
                "origin_store_name": origin_stock.get("origin_store_name"),
                "origin_stock": available_qty,
                "suggested_qty": suggested_qty,
            }
        )
        if len(suggestions) >= limit:
            break
    return suggestions


def fetch_shortages_without_internal_origin(destination_store_code: Optional[str], preferred_origin_store_code: Optional[str] = None, limit: int = 6):
    unresolved = []
    for shortage in fetch_pending_dispatch_shortages(destination_store_code, limit=limit * 3):
        origin_stock = fetch_best_origin_stock_for_reference(
            shortage.get("referencia"),
            shortage.get("destination_store_code"),
            preferred_origin_store_code,
        )
        if origin_stock:
            continue
        unresolved.append(
            {
                "dispatch_id": shortage.get("dispatch_id"),
                "order_id": shortage.get("order_id"),
                "reference": shortage.get("referencia"),
                "description": shortage.get("descripcion"),
                "destination_store_code": shortage.get("destination_store_code"),
                "destination_store_name": shortage.get("destination_store_name"),
                "destination_stock": shortage.get("stock_destino"),
                "required_qty": shortage.get("required_qty"),
                "shortage_qty": shortage.get("shortage_qty"),
            }
        )
        if len(unresolved) >= limit:
            break
    return unresolved


def parse_internal_selection_indexes(content: Optional[str], max_items: int):
    digits = [int(value) for value in re.findall(r"\d+", content or "")]
    indexes = []
    for value in digits:
        if 1 <= value <= max_items and value not in indexes:
            indexes.append(value)
    return indexes


def summarize_transfer_candidates(items: list[dict], max_items: int = 5):
    lines = []
    for idx, item in enumerate(items[:max_items], start=1):
        origin_label = item.get("origin_store_name") or item.get("source_store_name") or "sin origen"
        destination_label = item.get("destination_store_name") or "sin destino"
        qty_value = item.get("suggested_qty") if item.get("suggested_qty") is not None else item.get("shortage_qty")
        lines.append(
            f"{idx}. Pedido {item.get('order_id')} | {item.get('reference')} | {origin_label} -> {destination_label} | {format_quantity(qty_value)} und"
        )
    return "\n".join(lines)


def build_internal_transfer_guidance_text(flow_payload: dict):
    destination_label = flow_payload.get("destination_store_name") or "la sede destino"
    suggestions = flow_payload.get("suggestions") or []
    unresolved = flow_payload.get("unresolved_shortages") or []
    sections = [f"Revisión operativa para {destination_label}:"]
    if suggestions:
        sections.append("Traslados sugeridos listos para crear:")
        sections.append(summarize_transfer_candidates(suggestions))
    if unresolved:
        sections.append("Faltantes sin origen interno útil:")
        sections.append(summarize_transfer_candidates(unresolved))
    sections.append(
        "Responde `confirmar traslado` para crear todos los traslados sugeridos, `1 y 3` para crear solo algunas opciones, `compras` para escalar faltantes sin origen, o `cancelar` para salir."
    )
    return "\n".join(section for section in sections if section)


def build_internal_transfer_flow_payload(destination_store_code: Optional[str], preferred_origin_store_code: Optional[str] = None):
    destination_store_code = normalize_store_code(destination_store_code)
    preferred_origin_store_code = normalize_store_code(preferred_origin_store_code)
    suggestions = build_transfer_suggestions_for_pending_dispatches(destination_store_code, preferred_origin_store_code)
    unresolved = fetch_shortages_without_internal_origin(destination_store_code, preferred_origin_store_code)
    return {
        "destination_store_code": destination_store_code,
        "destination_store_name": get_store_short_label(destination_store_code) or STORE_CODE_LABELS.get(destination_store_code) or destination_store_code,
        "origin_store_code": preferred_origin_store_code,
        "origin_store_name": get_store_short_label(preferred_origin_store_code) or STORE_CODE_LABELS.get(preferred_origin_store_code) or preferred_origin_store_code,
        "suggestions": suggestions,
        "unresolved_shortages": unresolved,
        "step": "awaiting_confirmation",
    }


def create_procurement_followup(context: dict, requested_by_user: dict, shortages: list[dict], notes: Optional[str] = None):
    if not shortages:
        return {"created": False, "task_type": None, "notification": None}
    destination_label = shortages[0].get("destination_store_name") or "sede destino"
    detail = {
        "requested_by": requested_by_user,
        "destination_store_code": shortages[0].get("destination_store_code"),
        "destination_store_name": destination_label,
        "shortages": shortages,
        "notes": notes,
    }
    upsert_agent_task(
        context["conversation_id"],
        context.get("cliente_id"),
        "abastecimiento_compras",
        f"Faltantes sin origen interno para {destination_label}",
        detail,
        "alta",
    )
    notification = notify_procurement_request_by_email(shortages, requested_by_user, notes=notes)
    return {"created": True, "task_type": "abastecimiento_compras", "notification": notification}


def fetch_inventory_gap_between_stores(source_store_code: str, destination_store_code: str, limit: int = 10):
    source_store_code = normalize_store_code(source_store_code)
    destination_store_code = normalize_store_code(destination_store_code)
    if not source_store_code or not destination_store_code:
        return []

    engine = get_db_engine()
    with engine.connect() as connection:
        rows = connection.execute(
            text(
                """
                SELECT
                    referencia,
                    MAX(descripcion) AS descripcion,
                    MAX(marca) AS marca,
                    COALESCE(SUM(CASE WHEN cod_almacen = :source_store_code THEN stock_disponible ELSE 0 END), 0) AS stock_origen,
                    COALESCE(SUM(CASE WHEN cod_almacen = :destination_store_code THEN stock_disponible ELSE 0 END), 0) AS stock_destino
                FROM public.vw_inventario_agente
                WHERE cod_almacen = :source_store_code OR cod_almacen = :destination_store_code
                GROUP BY referencia
                HAVING COALESCE(SUM(CASE WHEN cod_almacen = :source_store_code THEN stock_disponible ELSE 0 END), 0) > 0
                   AND COALESCE(SUM(CASE WHEN cod_almacen = :destination_store_code THEN stock_disponible ELSE 0 END), 0) <= 0
                ORDER BY stock_origen DESC, referencia ASC
                LIMIT :limit
                """
            ),
            {
                "source_store_code": source_store_code,
                "destination_store_code": destination_store_code,
                "limit": limit,
            },
        ).mappings().all()
    return [dict(row) for row in rows]


def create_transfer_request_records(suggestions: list[dict], requested_by_user: dict, notes: Optional[str] = None):
    if not suggestions:
        return []
    requester_metadata = dict((requested_by_user or {}).get("metadata") or {})
    requester_store_code = normalize_store_code(requester_metadata.get("store_code"))
    engine = get_db_engine()
    created_rows = []
    with engine.begin() as connection:
        for suggestion in suggestions:
            origin_store_code = normalize_store_code(suggestion.get("origin_store_code"))
            if requester_store_code and origin_store_code and requester_store_code != origin_store_code:
                continue
            transfer_id = connection.execute(
                text(
                    """
                    INSERT INTO public.agent_transfer_request (
                        order_dispatch_id,
                        order_id,
                        requested_by_user_id,
                        requested_via,
                        source_store_code,
                        source_store_name,
                        destination_store_code,
                        destination_store_name,
                        referencia,
                        descripcion,
                        quantity_requested,
                        status,
                        summary,
                        notes,
                        metadata,
                        created_at,
                        updated_at
                    )
                    VALUES (
                        :order_dispatch_id,
                        :order_id,
                        :requested_by_user_id,
                        'whatsapp_interno',
                        :source_store_code,
                        :source_store_name,
                        :destination_store_code,
                        :destination_store_name,
                        :referencia,
                        :descripcion,
                        :quantity_requested,
                        'pendiente',
                        :summary,
                        :notes,
                        CAST(:metadata AS jsonb),
                        now(),
                        now()
                    )
                    RETURNING id
                    """
                ),
                {
                    "order_dispatch_id": suggestion.get("dispatch_id"),
                    "order_id": suggestion.get("order_id"),
                    "requested_by_user_id": requested_by_user.get("id"),
                    "source_store_code": origin_store_code,
                    "source_store_name": suggestion.get("origin_store_name"),
                    "destination_store_code": suggestion.get("destination_store_code"),
                    "destination_store_name": suggestion.get("destination_store_name"),
                    "referencia": suggestion.get("reference"),
                    "descripcion": suggestion.get("description"),
                    "quantity_requested": suggestion.get("suggested_qty"),
                    "summary": f"Traslado {suggestion.get('reference')} {suggestion.get('origin_store_name')} -> {suggestion.get('destination_store_name')}",
                    "notes": notes,
                    "metadata": safe_json_dumps(suggestion),
                },
            ).scalar_one()
            created_rows.append({"id": transfer_id, **suggestion})
    return created_rows


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
    raw_description = matched_product.get("descripcion") or matched_product.get("nombre_articulo") or item.get("original_text") or "producto"
    presentation = infer_product_presentation_from_row(matched_product) if matched_product else None
    brand = infer_product_brand_from_row(matched_product) if matched_product else None
    commercial_name = translate_product_to_commercial(raw_description, presentation, brand)
    requested_quantity = parse_numeric_value(product_request.get("requested_quantity")) or 1
    requested_unit = product_request.get("requested_unit")
    if requested_unit:
        quantity_label = f"{format_quantity(requested_quantity)} {get_presentation_label(requested_unit, requested_quantity)} de "
    elif requested_quantity > 1:
        quantity_label = f"{format_quantity(requested_quantity)} unidades de "
    else:
        quantity_label = ""
    return f"{quantity_label}{commercial_name}".strip()


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

    # During verification, ignore messages that are clearly questions or commands, not names
    if any(character.isalpha() for character in text_value):
        # Skip common question patterns that aren't name lookups
        question_patterns = [
            r"\b(como|cómo|donde|dónde|cuando|cuándo|cual|cuál|que|qué|por que|por qué|puedo|pueden|hay|tiene)\b",
            r"\b(pagar|enviar|comprar|hacer|necesito|quiero|ayuda|informacion|información)\b",
        ]
        for qp in question_patterns:
            if re.search(qp, normalized_text):
                return None

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
            f"No me aparece {candidate_value} por acá, ¿de pronto está a nombre de otra persona o empresa? "
            "Envíame la cédula o NIT y con eso te busco."
        )
    return (
        f"No me aparece {candidate_value} en el sistema. "
        "¿De pronto es otro número? Prueba con tu cédula, NIT o código de cliente."
    )


def build_commercial_customer_snapshot(customer_context: Optional[dict]):
    if not customer_context:
        return None
    return {
        "cliente_codigo": customer_context.get("cliente_codigo") or customer_context.get("verified_cliente_codigo") or customer_context.get("cod_cliente"),
        "nombre_cliente": customer_context.get("nombre_cliente"),
        "nit": customer_context.get("nit") or customer_context.get("numero_documento") or customer_context.get("documento"),
        "email": customer_context.get("email"),
        "telefono1": customer_context.get("telefono1"),
        "telefono2": customer_context.get("telefono2"),
        "vendedor": customer_context.get("vendedor"),
        "vendedor_codigo": customer_context.get("vendedor_codigo"),
        "zona": customer_context.get("zona"),
    }


def resolve_commercial_customer_context(customer_input: Optional[str]):
    raw_value = (customer_input or "").strip()
    if not raw_value:
        return None, None

    identity_candidate = extract_identity_lookup_candidate(
        raw_value,
        {"awaiting_verification": True, "pending_intent": "consulta_cartera"},
        allow_unprompted=True,
    )
    if not identity_candidate:
        normalized = normalize_text_value(raw_value)
        tokens = [token for token in normalized.split() if len(token) >= 2]
        if 2 <= len(tokens) <= 8:
            identity_candidate = {"type": "name_lookup", "value": raw_value}

    verified_context, verified_by = resolve_identity_candidate(identity_candidate)
    if not verified_context:
        return None, verified_by
    return build_commercial_customer_snapshot(verified_context), verified_by


def trim_commercial_customer_candidate(raw_value: Optional[str]):
    text_value = (raw_value or "").strip()
    if not text_value:
        return ""
    quantity_words_pattern = "|".join(QUANTITY_WORD_MAP.keys())
    split_match = re.search(
        r"\s+(?=(?:\d+\s*/\s*(?:1|4|5)|\d+|" + quantity_words_pattern + r")\s+(?:cunetes?|cuñetes?|galones?|galon|cuartos?|canecas?|cubetas?|rodillos?|brochas?|bochas?|lijas?|cintas?|bultos?|kilos?|metros?|rollos?|tubos?|tarros?|cajas?|paquetes?|unidades?|cerraduras?|candados?|chapas?|selladores?|silicones?|llaves?|bisagras?|manijas?|laminas?|láminas?|tejas?|perfiles?|angulos?|ángulos?|baldes?|de)\b)",
        text_value,
        flags=re.IGNORECASE,
    )
    if split_match:
        text_value = text_value[:split_match.start()].strip(" ,.;:-")
    return text_value.strip()


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


def is_new_order_request(text_value: Optional[str]):
    """Detect phrases like 'otro pedido', 'nuevo pedido', 'necesito otro pedido', 'otra cotización'."""
    normalized = normalize_text_value(text_value)
    if not normalized:
        return False
    return bool(re.search(r"\b(otr[oa]s?|nuev[oa]s?)\s+(pedido|cotizaci[oó]n|orden|lista)\b", normalized))


def resolve_option_selections(text_value: Optional[str], existing_items: list[dict]):
    """Parse option selection patterns like '2a', '4b', 'la 1a y la 3b' from the message."""
    normalized = normalize_text_value(text_value)
    if not normalized or not existing_items:
        return {}
    selections = re.findall(r"(?:^|\s)(\d)\s*([a-c])\b", normalized)
    if not selections:
        selections = re.findall(r"(?:la|el)\s+(\d)\s*([a-c])\b", normalized)
    updates = {}
    for item_idx_str, letter in selections:
        item_idx = int(item_idx_str) - 1
        alt_idx = ord(letter) - 97
        if 0 <= item_idx < len(existing_items):
            item = existing_items[item_idx]
            alternatives = item.get("alternatives") or []
            if 0 <= alt_idx < len(alternatives):
                updates[item_idx] = alternatives[alt_idx]
    return updates


def is_affirmative_message(text_value: Optional[str]):
    lowered = normalize_text_value(text_value)
    if not lowered:
        return False
    return bool(re.match(
        r"^(si|sí|eso es|asi es|as[ií] esta|correcto|exacto|dale|listo|de una|h[aá]gale|ok|okay|perfecto|confirmado)[.!?,\s]*$",
        lowered,
    ))


def is_negative_message(text_value: Optional[str]):
    lowered = normalize_text_value(text_value)
    if not lowered:
        return False
    return bool(re.match(r"^(no|nop|negativo|ya no|ya no mas|ya no m[aá]s)[.!?,\s]*$", lowered))


def has_active_commercial_flow(conversation_context: Optional[dict]):
    context = conversation_context or {}
    draft = dict(context.get("commercial_draft") or {})
    active_intent = draft.get("intent") or context.get("last_direct_intent") or context.get("intent")
    if active_intent not in {"pedido", "cotizacion"}:
        return False
    if draft.get("items"):
        return True
    return bool(active_intent in {"pedido", "cotizacion"} and not draft.get("internal_notified"))


def build_conversation_closing_reply(profile_name: Optional[str]):
    return "¡Con gusto! Quedo por aquí para lo que necesites 👋"


def is_nudge_or_followup(text_value: Optional[str]):
    """Detects short follow-up nudges like '?', 'y?', 'entonces?', 'hola?'."""
    lowered = normalize_text_value(text_value)
    if not lowered:
        return False
    return bool(re.match(r"^[?!¿¡.\s]+$", lowered) or re.match(
        r"^(y|entonces|que paso|qué pasó|que pasa|que hay|hola|ey|oye|bueno|listo|y entonces|y que|y qué|dale|alo|aló|hey)[?!¿¡.\s]*$",
        lowered,
    ))


def build_nudge_reply(conversation_context: Optional[dict]):
    """Build a reply for nudge messages based on the active flow."""
    context = conversation_context or {}
    active_intent = context.get("last_direct_intent") or context.get("intent")
    claim_case = context.get("claim_case") or {}
    commercial_draft = context.get("commercial_draft") or {}

    if claim_case.get("active") and not claim_case.get("submitted"):
        step = claim_case.get("step")
        if step == "awaiting_product":
            return "Disculpa la demora. ¿Me cuentas qué producto es el del reclamo?"
        elif step == "awaiting_detail":
            return "Sigo acá. ¿Me cuentas qué pasó con el producto?"
        elif step == "awaiting_evidence":
            return "Estoy pendiente. ¿Tienes alguna foto o número de lote para el caso?"
        elif step == "awaiting_email":
            return "Solo me falta tu correo para enviarte la constancia del caso. ¿Me lo regalas?"
        return "Sigo acá pendiente, ¿en qué íbamos?"

    if active_intent in {"pedido", "cotizacion"} or commercial_draft.get("intent"):
        items = commercial_draft.get("items") or []
        if items:
            matched = sum(1 for i in items if i.get("status") == "matched")
            pending = len(items) - matched
            if pending > 0:
                return f"Ya tengo {matched} producto(s) listos y me faltan {pending} por precisar. ¿Me confirmas esos que quedaron pendientes?"
            if not commercial_draft.get("store_filters"):
                return "Ya tengo los productos listos. ¿En qué tienda o ciudad los necesitas?"
            return "Ya tengo todo listo. ¿Te confirmo el pedido por aquí o te lo mando al correo?"
        label = "cotización" if active_intent == "cotizacion" else "pedido"
        return f"Claro, seguimos con el {label}. ¿Qué productos necesitas?"

    if context.get("awaiting_verification"):
        return "Sigo esperando tu número de cédula o NIT para poder revisarte esa info 🔒"

    return None


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


QUANTITY_WORD_MAP = {
    "un": 1, "una": 1, "uno": 1,
    "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5,
    "seis": 6, "siete": 7, "ocho": 8, "nueve": 9, "diez": 10,
    "once": 11, "doce": 12, "quince": 15, "veinte": 20,
    "medio": 0.5, "media": 0.5,
}


def should_continue_commercial_flow(conversation_context: Optional[dict], detected_intent: Optional[str], text_value: Optional[str]):
    context = conversation_context or {}
    active_intent = context.get("last_direct_intent")
    if not active_intent and context.get("intent") in {"pedido", "cotizacion"}:
        active_intent = context.get("intent")
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
    if is_affirmative_message(text_value) or is_negative_message(text_value):
        return True
    if is_new_order_request(text_value):
        return True
    if re.search(r"\b\d\s*[a-c]\b", normalized):
        return True
    if re.search(r"\b(confirma|confirmame|conf[ií]rmame|conf[ií]rmalo|sep[aá]ralo|separalo|env[ií]ame|enviame|m[aá]ndame|mandame|eso ser[ií]a todo|eso es|as[ií] est[aá])\b", normalized):
        return True
    if re.search(r"\b(agregale|agregame|ponle|ponme|sumale|quitale|quitame)\b", normalized):
        return True
    if is_product_intent_message(text_value):
        return True
    if len(split_commercial_line_items(text_value)) >= 2:
        return True
    if bool(re.search(r"\b\d+\s*/\s*(1|4|5)\b", normalized)):
        return True

    quantity_words_pattern = "|".join(QUANTITY_WORD_MAP.keys())
    if re.search(r"(?:\d+|(?:" + quantity_words_pattern + r"))\s+\w+", normalized):
        extracted = extract_product_request(text_value)
        if extracted.get("core_terms") and (extracted.get("requested_quantity") or extracted.get("requested_unit")):
            return True

    # If there are ambiguous items in draft, any text with product terms could be a clarification
    if commercial_draft.get("items"):
        has_ambiguous = any(item.get("status") == "ambiguous" for item in commercial_draft["items"])
        if has_ambiguous:
            extracted = extract_product_request(text_value)
            if extracted.get("core_terms") or extracted.get("product_codes"):
                return True

    return False


def split_commercial_line_items(text_value: Optional[str]):
    if not text_value:
        return []

    filler_fragments = {
        "necesito",
        "tambien necesito",
        "también necesito",
        "tambien",
        "también",
        "ademas necesito",
        "además necesito",
        "ademas",
        "además",
        "y",
        "y tambien necesito",
        "y también necesito",
        "agregale",
        "agregame",
        "agregalo",
        "agrega",
        "ponle",
        "ponme",
        "ponlo",
        "sumale",
        "sumame",
        "quitale",
        "quitame",
    }

    def clean_split_candidates(candidates: list[str]):
        cleaned = []
        carry_prefix = ""
        for segment in candidates:
            stripped_segment = segment.strip()
            normalized_segment = normalize_text_value(stripped_segment)
            if not normalized_segment:
                continue
            if normalized_segment in filler_fragments:
                carry_prefix = f"{carry_prefix} {stripped_segment}".strip()
                continue
            if carry_prefix:
                stripped_segment = f"{carry_prefix} {stripped_segment}".strip()
                carry_prefix = ""
            stripped_segment = re.sub(
                r"\s+(?:y|tambien|también|ademas|además|tambien necesito|también necesito|ademas necesito|además necesito)\s*$",
                "",
                stripped_segment,
                flags=re.IGNORECASE,
            ).strip()
            cleaned.append(stripped_segment)
        return cleaned

    quantity_words_pattern = "|".join(QUANTITY_WORD_MAP.keys())
    quantity_start = re.search(
        r"(?:\b\d+\s*/\s*(?:1|4|5)\b|\b\d+\b|\b(?:" + quantity_words_pattern + r")\b)\s+(?:cunetes?|cuñetes?|galones?|galon|cuartos?|canecas?|cubetas?|rodillos?|brochas?|bochas?|lijas?|cintas?|bultos?|kilos?|metros?|rollos?|tubos?|tarros?|cajas?|paquetes?|unidades?|cerraduras?|candados?|chapas?|selladores?|silicones?|llaves?|bisagras?|manijas?|laminas?|láminas?|tejas?|perfiles?|angulos?|ángulos?|baldes?|de)\b",
        text_value,
        flags=re.IGNORECASE,
    )
    text_for_items = text_value[quantity_start.start():].strip() if quantity_start else text_value

    prepared_text = re.sub(r"[;|]+", "\n", text_for_items)
    raw_lines = [line.strip(" -*•\t") for line in prepared_text.splitlines()]
    lines = [line for line in raw_lines if line]
    if len(lines) >= 2:
        return lines

    normalized = normalize_text_value(text_for_items)
    if re.search(r"\b\d+\s*/\s*(1|4|5)\b", normalized):
        split_candidates = [segment.strip() for segment in re.split(r"\s{2,}|,(?=\s*\d)|(?<=\")\s+(?=\d)", text_for_items) if segment.strip()]
        if len(split_candidates) >= 2:
            return split_candidates

    qty_boundary = re.compile(
        r"(?<=\S)\s+(?=(?:\d+\s*/\s*(?:1|4|5)|\d+|" + quantity_words_pattern + r")\s+(?:cunetes?|cuñetes?|galones?|galon|cuartos?|canecas?|cubetas?|rodillos?|brochas?|bochas?|lijas?|cintas?|bultos?|kilos?|metros?|rollos?|tubos?|tarros?|cajas?|paquetes?|unidades?|cerraduras?|candados?|chapas?|selladores?|silicones?|llaves?|bisagras?|manijas?|laminas?|láminas?|tejas?|perfiles?|angulos?|ángulos?|baldes?|de)\b)",
        re.IGNORECASE,
    )
    split_candidates = [segment.strip() for segment in qty_boundary.split(text_for_items) if segment.strip()]
    if len(split_candidates) >= 2:
        cleaned_candidates = clean_split_candidates(split_candidates)
        return cleaned_candidates or split_candidates

    comma_split = [segment.strip() for segment in re.split(r",\s*", text_for_items) if segment.strip()]
    if len(comma_split) >= 2:
        product_like = sum(1 for seg in comma_split if re.search(r"\d|" + quantity_words_pattern, seg.lower()))
        if product_like >= 2:
            return comma_split

    y_split = [segment.strip() for segment in re.split(r"\by\b", text_for_items, flags=re.IGNORECASE) if segment.strip()]
    if len(y_split) >= 2:
        product_like = sum(1 for seg in y_split if re.search(r"\d|" + quantity_words_pattern, seg.lower()))
        if product_like >= 2:
            return y_split

    return lines if lines else [text_for_items.strip()]


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
    product_request = merge_store_filters(prepare_product_request_for_search(raw_line), inherited_store_filters)
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
        "alternatives": [],
    }

    if not product_rows:
        item_result["message"] = f"{describe_commercial_item_need(item_result)}: necesito la referencia exacta o la presentación para ubicarlo."
        return item_result

    # Build alternatives list from all returned product rows
    seen_refs = set()
    for row in product_rows[:5]:
        ref = row.get("referencia") or row.get("codigo_articulo") or ""
        if ref in seen_refs:
            continue
        seen_refs.add(ref)
        alt_commercial_name = translate_product_to_commercial(
            row.get("descripcion") or row.get("nombre_articulo"),
            infer_product_presentation_from_row(row),
            infer_product_brand_from_row(row),
        )
        alt_stock = parse_numeric_value(row.get("stock_total") if row.get("stock_total") is not None else row.get("stock")) or 0
        item_result["alternatives"].append({
            "commercial_name": alt_commercial_name,
            "referencia": ref,
            "stock_total": alt_stock,
            "row": dict(row),
        })

    if should_ask_product_clarification(product_request, product_rows):
        item_result["status"] = "ambiguous"
        options_text = "\n".join(
            f"   {chr(97 + idx)}) {alt['commercial_name']}"
            for idx, alt in enumerate(item_result["alternatives"][:4])
        )
        item_result["message"] = f"{describe_commercial_item_need(item_result)} — opciones:\n{options_text}"
        return item_result

    top_row = dict(product_rows[0])
    item_result["status"] = "matched"
    item_result["matched_product"] = top_row
    raw_description = top_row.get("descripcion") or top_row.get("nombre_articulo") or "producto"
    top_presentation = infer_product_presentation_from_row(top_row)
    top_brand = infer_product_brand_from_row(top_row)
    commercial_name = translate_product_to_commercial(raw_description, top_presentation, top_brand)
    stock_value = parse_numeric_value(top_row.get("stock_total") if top_row.get("stock_total") is not None else top_row.get("stock")) or 0
    requested_quantity = parse_numeric_value(product_request.get("requested_quantity"))

    if requested_store_label:
        if stock_value <= 0:
            item_result["message"] = f"{commercial_name}: no disponible en {requested_store_label} en este momento."
        else:
            item_result["message"] = f"{commercial_name}: ✅ disponible en {requested_store_label}"
            if requested_quantity:
                availability = ", te alcanza" if stock_value >= requested_quantity else ", pero no alcanza para toda la cantidad"
                item_result["message"] += availability
            item_result["message"] += "."
    else:
        if stock_value <= 0:
            item_result["message"] = f"{commercial_name}: agotado en este momento."
        else:
            item_result["message"] = f"{commercial_name}: ✅ disponible"
            if requested_quantity:
                availability = ", sí alcanza" if stock_value >= requested_quantity else ", pero no para toda la cantidad"
                item_result["message"] += availability
            item_result["message"] += "."

    return item_result


def format_draft_conversational(resolved_items: list[dict], store_label: Optional[str] = None):
    """Format the commercial draft as natural conversational text instead of numbered menus."""
    if not resolved_items:
        return "", False

    matched_labels = []
    ambiguous_parts = []
    missing_parts = []
    needs_input = False

    for item in resolved_items:
        pr = item.get("product_request") or {}
        qty = parse_numeric_value(pr.get("requested_quantity"))
        unit = pr.get("requested_unit")

        if item["status"] == "matched":
            mp = item.get("matched_product") or {}
            raw_desc = mp.get("descripcion") or mp.get("nombre_articulo") or "producto"
            pres = infer_product_presentation_from_row(mp) if mp else None
            brand = infer_product_brand_from_row(mp) if mp else None
            commercial_name = translate_product_to_commercial(raw_desc, pres, brand)
            if qty and unit:
                matched_labels.append(f"{format_quantity(qty)} {get_presentation_label(unit, qty)} de {commercial_name}")
            elif qty and qty > 1:
                matched_labels.append(f"{format_quantity(qty)} {commercial_name}")
            else:
                matched_labels.append(commercial_name)

        elif item["status"] == "ambiguous":
            needs_input = True
            orig = (item.get("original_text") or "").strip()
            alts = item.get("alternatives") or []
            alt_names = [a["commercial_name"] for a in alts[:4]]
            if len(alt_names) == 1:
                ambiguous_parts.append(f"Del *{orig}* tengo el {alt_names[0]}, ¿te sirve?")
            elif len(alt_names) == 2:
                ambiguous_parts.append(f"Del *{orig}* tengo el {alt_names[0]} y el {alt_names[1]}. ¿Cuál manejas?")
            else:
                options_text = ", ".join(alt_names[:-1]) + f" y {alt_names[-1]}"
                ambiguous_parts.append(f"Del *{orig}* tengo {options_text}. ¿Cuál necesitas?")

        elif item["status"] == "missing":
            needs_input = True
            orig = (item.get("original_text") or "").strip()
            missing_parts.append(orig)

    parts = []
    if matched_labels:
        if len(matched_labels) == 1:
            parts.append(f"✅ Te anoto {matched_labels[0]}.")
        elif len(matched_labels) == 2:
            parts.append(f"✅ Te anoto {matched_labels[0]} y {matched_labels[1]}.")
        else:
            items_text = ", ".join(matched_labels[:-1]) + f" y {matched_labels[-1]}"
            parts.append(f"✅ Te anoto {items_text}.")

    for amb in ambiguous_parts:
        parts.append(amb)

    if missing_parts:
        if len(missing_parts) == 1:
            parts.append(f"❌ No ubiqué *{missing_parts[0]}*, ¿me pasas la referencia o el código exacto?")
        else:
            items_text = " ni ".join(f"*{m}*" for m in missing_parts)
            parts.append(f"❌ No ubiqué {items_text}, ¿me pasas las referencias?")

    return "\n\n".join(parts), needs_input


def try_resolve_ambiguous_with_clarification(raw_line: str, existing_items: list[dict], inherited_store_filters: list[str], mode: str):
    """Try to match a clarification message to an existing ambiguous item and resolve it.

    Returns the index of the matched item, or None if no match found.
    """
    new_request = extract_product_request(raw_line)
    new_terms = set(new_request.get("core_terms") or [])
    new_codes = set(new_request.get("product_codes") or [])
    if not new_terms and not new_codes:
        return None

    best_idx = None
    best_score = 0

    for idx, item in enumerate(existing_items):
        if item.get("status") != "ambiguous":
            continue
        original_terms = set((item.get("product_request") or {}).get("core_terms") or [])
        # Check term overlap with original request
        overlap = len(new_terms & original_terms)
        # Also check if clarification matches any alternative's reference or name
        for alt in (item.get("alternatives") or []):
            alt_ref = normalize_text_value(alt.get("referencia") or "")
            alt_name = normalize_text_value(alt.get("commercial_name") or "")
            for term in new_terms:
                if term in alt_name:
                    overlap += 1
                    break
            for code in new_codes:
                if code == alt_ref or code in alt_ref:
                    overlap += 2
                    break
        if overlap > best_score:
            best_score = overlap
            best_idx = idx

    if best_idx is not None and best_score >= 1:
        return best_idx
    return None


def build_commercial_flow_reply(intent: str, profile_name: Optional[str], user_message: Optional[str], conversation_context: Optional[dict]):
    context = conversation_context or {}
    existing_draft = dict(context.get("commercial_draft") or {})
    last_intent = context.get("last_direct_intent")
    normalized_message = normalize_text_value(user_message)
    incoming_store_filters = extract_store_filters(user_message)
    incoming_email = extract_email_address(user_message)
    incoming_delivery_channel = extract_delivery_channel(user_message)
    inherited_store_filters = incoming_store_filters or existing_draft.get("store_filters") or []
    current_lines = split_commercial_line_items(user_message)
    has_existing_items = bool(existing_draft.get("items"))
    has_contextual_followup = bool(incoming_store_filters or incoming_email or incoming_delivery_channel)
    is_affirmative_followup = is_affirmative_message(user_message)
    is_negative_followup = is_negative_message(user_message)
    wants_order_confirmation = bool(re.search(r"\b(confirma|confirmame|conf[ií]rmame|conf[ií]rmalo|sep[aá]ralo|separalo|env[ií]ame|enviame|mandame|m[aá]ndame)\b", normalized_message))

    # ── Detect new order request ("otro pedido", "nuevo pedido") ──
    if is_new_order_request(user_message) and has_existing_items:
        summary_label = "cotización" if intent == "cotizacion" else "pedido"
        return {
            "tono": "consultivo",
            "intent": intent,
            "priority": "alta" if intent == "pedido" else "media",
            "summary": f"Nuevo {summary_label}",
            "response_text": (
                f"¡Dale! Arrancamos con un nuevo {summary_label}. "
                "Pásame los productos y la tienda o ciudad de entrega."
            ),
            "should_create_task": True,
            "task_type": intent,
            "task_summary": f"Nuevo {summary_label} iniciado por WhatsApp",
            "task_detail": {"mensaje": user_message, "mode": intent},
            "conversation_context_updates": {
                "commercial_draft": {
                    "intent": intent,
                    "store_filters": [],
                    "delivery_channel": None,
                    "contact_email": None,
                    "items": [],
                    "items_confirmed": False,
                }
            },
        }

    # ── Process option selections (e.g., "2a y 4b") ──
    option_updates = resolve_option_selections(user_message, existing_draft.get("items") or [])
    if option_updates and has_existing_items:
        draft_items_for_update = list(existing_draft.get("items") or [])
        for opt_idx, alt in option_updates.items():
            if 0 <= opt_idx < len(draft_items_for_update):
                old_item = draft_items_for_update[opt_idx]
                new_row = alt["row"]
                old_item["status"] = "matched"
                old_item["matched_product"] = new_row
                raw_desc = new_row.get("descripcion") or new_row.get("nombre_articulo") or "producto"
                pres = infer_product_presentation_from_row(new_row)
                brand = infer_product_brand_from_row(new_row)
                commercial_name = translate_product_to_commercial(raw_desc, pres, brand)
                old_item["message"] = f"{commercial_name}: ✅ seleccionado."
        existing_draft["items"] = draft_items_for_update
        has_existing_items = True
        current_lines = []

    items_confirmed = bool(existing_draft.get("items_confirmed"))

    has_explicit_items = any(
        extract_product_request(line).get("product_codes")
        or extract_product_request(line).get("core_terms")
        or extract_product_request(line).get("requested_unit")
        for line in current_lines
    )

    # Set items_confirmed when user explicitly confirms
    if is_affirmative_followup or wants_order_confirmation:
        items_confirmed = True

    if has_existing_items and (incoming_email or incoming_delivery_channel) and not incoming_store_filters:
        current_lines = []
        has_explicit_items = False

    if has_existing_items and (is_affirmative_followup or is_negative_followup or wants_order_confirmation) and not has_explicit_items and not has_contextual_followup and not option_updates:
        current_lines = []

    if not has_explicit_items and not has_existing_items and not has_contextual_followup and not option_updates:
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
                    "items_confirmed": False,
                }
            },
        }

    draft_items = []
    if existing_draft.get("intent") == intent:
        draft_items = list(existing_draft.get("items") or [])

    # When new explicit items are added, reset confirmation
    if has_explicit_items:
        items_confirmed = False

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
        raw_request = extract_product_request(raw_line)
        if not (
            raw_request.get("product_codes")
            or raw_request.get("core_terms")
            or raw_request.get("requested_unit")
            or is_product_intent_message(raw_line)
        ):
            continue
        # Try to resolve an existing ambiguous item with this clarification
        matched_idx = try_resolve_ambiguous_with_clarification(raw_line, resolved_items, inherited_store_filters, intent)
        if matched_idx is not None:
            original_text = resolved_items[matched_idx].get("original_text")
            resolved_items[matched_idx] = build_commercial_item_result(raw_line, inherited_store_filters, intent)
            resolved_items[matched_idx]["original_text"] = original_text or raw_line
        else:
            resolved_items.append(build_commercial_item_result(raw_line, inherited_store_filters, intent))

    matched_items = [item for item in resolved_items if item.get("status") == "matched"]
    ambiguous_items = [item for item in resolved_items if item.get("status") == "ambiguous"]
    missing_items = [item for item in resolved_items if item.get("status") == "missing"]
    store_label = STORE_CODE_LABELS.get(inherited_store_filters[0]) if len(inherited_store_filters) == 1 else None
    delivery_channel = incoming_delivery_channel or existing_draft.get("delivery_channel")
    contact_email = incoming_email or existing_draft.get("contact_email")
    internal_notified = bool(existing_draft.get("internal_notified"))
    customer_email_sent = bool(existing_draft.get("customer_email_sent"))
    destinatario = existing_draft.get("destinatario") or ""
    customer_identity_input = (existing_draft.get("customer_identity_input") or "").strip()
    customer_context = dict(existing_draft.get("customer_context") or {})
    customer_resolution_status = existing_draft.get("customer_resolution_status")

    # Extract destinatario from message like "a nombre de Juan Pérez"
    nombre_match = re.search(r"\ba\s+nombre\s+de\s+(.+?)(?:\s*[.,;]|$)", normalized_message)
    if nombre_match:
        customer_identity_input = trim_commercial_customer_candidate(nombre_match.group(1))
        resolved_customer_context, _ = resolve_commercial_customer_context(customer_identity_input)
        if resolved_customer_context:
            customer_context = resolved_customer_context
            customer_resolution_status = "resolved"
            destinatario = resolved_customer_context.get("nombre_cliente") or customer_identity_input.title()
        else:
            customer_context = {}
            customer_resolution_status = "unresolved"
            destinatario = customer_identity_input.title()
    elif customer_identity_input and not customer_context:
        resolved_customer_context, _ = resolve_commercial_customer_context(customer_identity_input)
        if resolved_customer_context:
            customer_context = resolved_customer_context
            customer_resolution_status = "resolved"
            destinatario = resolved_customer_context.get("nombre_cliente") or destinatario or customer_identity_input.title()
        elif customer_resolution_status != "resolved":
            customer_resolution_status = "unresolved"

    if customer_context and not destinatario:
        destinatario = customer_context.get("nombre_cliente") or ""

    compact_summary = summarize_commercial_items(matched_items)
    has_store = bool(inherited_store_filters)
    all_items_resolved = bool(matched_items) and not ambiguous_items and not missing_items
    requires_customer_resolution = bool(customer_identity_input) and customer_resolution_status != "resolved"
    ready_to_close = all_items_resolved and has_store and items_confirmed and not requires_customer_resolution

    if ready_to_close and not incoming_delivery_channel and wants_order_confirmation:
        delivery_channel = existing_draft.get("delivery_channel")

    if not ready_to_close:
        # ── Format response conversationally ──
        list_text, has_options = format_draft_conversational(resolved_items, store_label)

        closing_parts = []
        if not has_store:
            closing_parts.append("¿En qué tienda o ciudad lo necesitas?")
        if requires_customer_resolution:
            closing_parts.append("Antes de cerrarlo necesito validar a nombre de qué cliente va. Envíame NIT, código o nombre completo para no cruzar la facturación.")
        if all_items_resolved and has_store and not items_confirmed:
            request_label = "cotización" if intent == "cotizacion" else "pedido"
            closing_parts.append(f"¿Te confirmo el {request_label}? ¿A nombre de quién va el despacho?")
        elif all_items_resolved and not has_store:
            pass  # Already asked for store
        elif not has_options and not missing_items:
            closing_parts.append("Apenas me confirmes te armo el consolidado completo.")

        response_text = list_text
        if closing_parts:
            response_text += "\n\n" + " ".join(closing_parts)

        draft_state = {
            "intent": intent,
            "store_filters": inherited_store_filters,
            "delivery_channel": delivery_channel,
            "contact_email": contact_email,
            "internal_notified": internal_notified,
            "customer_email_sent": customer_email_sent,
            "items_confirmed": items_confirmed,
            "destinatario": destinatario,
            "customer_identity_input": customer_identity_input or None,
            "customer_context": customer_context or None,
            "customer_resolution_status": customer_resolution_status,
            "items": resolved_items,
        }

        return {
            "tono": "consultivo",
            "intent": intent,
            "priority": "alta" if intent == "pedido" else "media",
            "summary": "Consolidado comercial multiproducto",
            "response_text": response_text.strip(),
            "should_create_task": last_intent != intent,
            "task_type": intent,
            "task_summary": "Seguimiento a solicitud comercial por WhatsApp",
            "task_detail": {"items": resolved_items, "store_filters": inherited_store_filters, "mode": intent},
            "conversation_context_updates": {"commercial_draft": draft_state},
            "commercial_draft": draft_state,
        }

    # ── Ready to close ──
    request_label = "cotización" if intent == "cotizacion" else "pedido"
    destination_label = store_label or "la sede indicada"
    display_customer_label = (customer_context or {}).get("nombre_cliente") or destinatario
    destinatario_label = f" a nombre de {display_customer_label}" if display_customer_label else ""
    if not delivery_channel:
        response_text = (
            f"¡Listo! Ya te dejé montado el {request_label} para {destination_label}{destinatario_label} con {compact_summary}. "
            "¿Te lo confirmo por aquí o prefieres que te envíe un PDF al correo?"
        )
    elif delivery_channel == "email" and not contact_email:
        response_text = (
            f"¡Listo! Ya tengo el {request_label} para {destination_label}{destinatario_label} con {compact_summary}. "
            "Regálame tu correo y te mando el PDF con todo el detalle."
        )
    elif delivery_channel == "email":
        response_text = (
            f"¡Listo! Ya te dejé montado el {request_label} para {destination_label}{destinatario_label} con {compact_summary}. "
            f"Te va a llegar al correo {contact_email} un PDF con el detalle de las referencias y cantidades."
        )
    else:
        response_text = (
            f"¡Listo! Ya te dejé montado el {request_label} para {destination_label}{destinatario_label} con {compact_summary}. "
            "Te envío el PDF por aquí mismo para que lo tengas de referencia 📄"
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
        "items_confirmed": items_confirmed,
        "destinatario": destinatario,
        "customer_identity_input": customer_identity_input or None,
        "customer_context": customer_context or None,
        "customer_resolution_status": customer_resolution_status,
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
        "task_detail": {"items": resolved_items, "store_filters": inherited_store_filters, "mode": intent, "delivery_channel": delivery_channel, "contact_email": contact_email, "destinatario": destinatario, "customer_context": customer_context or None},
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
    if re.search(r"\b(necesito|quiero|quisiera|me gustaria|podria|puedo)\b.*\bpedido\b", lowered):
        return "pedido"
    if is_technical_advisory_message(text_value):
        return "asesoria_tecnica"
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
            "compro",
            "compró",
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


def clamp_purchase_end_date(end_date: date, today: Optional[date] = None):
    today = today or date.today()
    return min(end_date, today)


def format_purchase_period_label(month_numbers: list[int], year_value: int):
    unique_months = []
    for month_number in month_numbers:
        if month_number not in unique_months:
            unique_months.append(month_number)
    month_names = []
    for month_number in unique_months:
        month_name = next((name for name, value in MONTH_ALIASES.items() if value == month_number and len(name) > 3), None)
        if month_name:
            month_names.append(month_name)
    if not month_names:
        return f"{year_value}"
    if len(month_names) == 1:
        return f"{month_names[0]} de {year_value}"
    return f"{month_names[0]} a {month_names[-1]} de {year_value}"


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

    year_match = re.search(r"\b(?:en\s+el\s+)?(?:ano|año)\s+(\d{4}|este ano|este año)\b", normalized)
    explicit_year = None
    if year_match:
        year_token = year_match.group(1)
        explicit_year = today.year if year_token in {"este ano", "este año"} else int(year_token)

    month_mentions = []
    for month_name, month_value in MONTH_ALIASES.items():
        if month_name in normalized:
            month_mentions.append((normalized.find(month_name), month_value))

    if month_mentions:
        month_mentions.sort(key=lambda item: item[0])
        ordered_months = [item[1] for item in month_mentions]
        year_value = explicit_year or today.year
        start_month = min(ordered_months)
        end_month = max(ordered_months)
        start_date, _ = month_date_range(year_value, start_month)
        _, end_date = month_date_range(year_value, end_month)
        if year_value == today.year:
            end_date = clamp_purchase_end_date(end_date, today)
        result.update(
            {
                "start_date": start_date,
                "end_date": end_date,
                "label": format_purchase_period_label(ordered_months, year_value),
                "has_time_filter": True,
            }
        )
        return result

    if explicit_year is not None:
        start_date = date(explicit_year, 1, 1)
        end_date = date(explicit_year, 12, 31)
        if explicit_year == today.year:
            end_date = today
        result.update(
            {
                "start_date": start_date,
                "end_date": end_date,
                "label": f"{explicit_year}",
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
            if year_value == today.year:
                end_date = clamp_purchase_end_date(end_date, today)
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


PDF_STORAGE: dict[str, dict] = {}


def generate_commercial_pdf(
    conversation_id: int,
    request_type: str,
    profile_name: Optional[str],
    cliente_contexto: Optional[dict],
    detail: dict,
):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.units import mm, inch
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable, Image
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

    items = detail.get("items") or []
    matched_items = [item for item in items if item.get("status") == "matched"]
    compact_mode = request_type == "cotizacion" and 0 < len(matched_items) <= 8

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        topMargin=(12 if compact_mode else 20) * mm,
        bottomMargin=(12 if compact_mode else 20) * mm,
        leftMargin=(14 if compact_mode else 20) * mm,
        rightMargin=(14 if compact_mode else 20) * mm,
    )
    styles = getSampleStyleSheet()

    brand_dark = colors.HexColor(CORPORATE_BRAND["brand_dark"])
    brand_accent = colors.HexColor(CORPORATE_BRAND["brand_accent"])
    brand_light_bg = colors.HexColor(CORPORATE_BRAND["brand_light"])
    brand_border = colors.HexColor(CORPORATE_BRAND["brand_border"])
    white = colors.white

    title_style = ParagraphStyle("Title", parent=styles["Title"], fontSize=18 if compact_mode else 22, textColor=white, alignment=TA_LEFT, spaceAfter=3 if compact_mode else 4)
    subtitle_style = ParagraphStyle("Subtitle", parent=styles["Normal"], fontSize=8.5 if compact_mode else 10, textColor=colors.HexColor("#D1D5DB"), alignment=TA_LEFT, leading=10 if compact_mode else 12)
    heading_style = ParagraphStyle("Heading", parent=styles["Heading2"], fontSize=11 if compact_mode else 13, textColor=brand_dark, spaceBefore=8 if compact_mode else 14, spaceAfter=4 if compact_mode else 6)
    normal_style = ParagraphStyle("Body", parent=styles["Normal"], fontSize=8.6 if compact_mode else 10, textColor=brand_dark, leading=10.5 if compact_mode else 14)
    small_style = ParagraphStyle("Small", parent=styles["Normal"], fontSize=7 if compact_mode else 8, textColor=colors.HexColor("#6B7280"), leading=9 if compact_mode else 11)
    right_style = ParagraphStyle("Right", parent=styles["Normal"], fontSize=8.6 if compact_mode else 10, textColor=brand_dark, alignment=TA_RIGHT, leading=10.5 if compact_mode else 14)

    request_label = "Pedido" if request_type == "pedido" else "Cotización"
    document_version = "Formato CRM 2026.3"
    case_ref = f"CRM-{conversation_id}"
    now = datetime.now()
    date_str = now.strftime("%d/%m/%Y")
    time_str = now.strftime("%I:%M %p")
    commercial_customer_context = dict(detail.get("customer_context") or cliente_contexto or {})
    cliente_label = commercial_customer_context.get("nombre_cliente") or profile_name or "Cliente Ferreinox"
    cliente_codigo = commercial_customer_context.get("cliente_codigo") or ""
    cliente_nit = commercial_customer_context.get("nit") or commercial_customer_context.get("documento") or ""
    store_filters = detail.get("store_filters") or []
    store_name = STORE_CODE_LABELS.get(store_filters[0]) if len(store_filters) == 1 else (", ".join(STORE_CODE_LABELS.get(c, c) for c in store_filters) if store_filters else "Por definir")
    delivery_channel = detail.get("delivery_channel") or "chat"
    contact_email = detail.get("contact_email") or commercial_customer_context.get("email") or ""
    dispatch_name = detail.get("nombre_despacho") or cliente_label
    observations = detail.get("facturador_notes") or detail.get("observaciones") or ""

    elements = []

    logo_cell = ""
    if CORPORATE_LOGO_PATH.exists():
        logo = Image(str(CORPORATE_LOGO_PATH))
        logo.drawHeight = 18 * mm
        logo.drawWidth = 42 * mm
        logo_cell = logo

    header_data = [
        [
            logo_cell or Paragraph(f"<b>FERREINOX S.A.S. BIC</b>", title_style),
            Paragraph(f"<b>{request_label}</b><br/><font size='10'>{document_version}</font>", ParagraphStyle("RightTitle", parent=title_style, alignment=TA_RIGHT)),
        ],
        [
            Paragraph(f"NIT {CORPORATE_BRAND['nit']} | {CORPORATE_BRAND['address']}", subtitle_style),
            Paragraph(f"Ref: {case_ref} | {date_str}", ParagraphStyle("RightSub", parent=subtitle_style, alignment=TA_RIGHT)),
        ],
    ]
    header_table = Table(header_data, colWidths=[doc.width * 0.55, doc.width * 0.45])
    header_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), brand_dark),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, 0), 12 if compact_mode else 16),
        ("BOTTOMPADDING", (0, -1), (-1, -1), 10 if compact_mode else 14),
        ("LEFTPADDING", (0, 0), (-1, -1), 12 if compact_mode else 16),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12 if compact_mode else 16),
        ("ROUNDEDCORNERS", [8, 8, 0, 0]),
    ]))
    elements.append(header_table)
    elements.append(Spacer(1, (2 if compact_mode else 4) * mm))

    banner_table = Table(
        [[
            Paragraph(
                f"<b>Solicitud Comercial Digital</b><br/>{request_label} generado por el CRM Ferreinox para seguimiento operativo inmediato.",
                ParagraphStyle("BannerBody", parent=normal_style),
            ),
            Paragraph(
                f"<b>{document_version}</b><br/>Referencia {case_ref}",
                ParagraphStyle("BannerRight", parent=right_style),
            ),
        ]],
        colWidths=[doc.width * 0.64, doc.width * 0.36],
    )
    banner_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FEF3C7")),
        ("BOX", (0, 0), (-1, -1), 0.6, brand_accent),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 7 if compact_mode else 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7 if compact_mode else 10),
        ("LEFTPADDING", (0, 0), (-1, -1), 10 if compact_mode else 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10 if compact_mode else 12),
    ]))
    elements.append(banner_table)
    elements.append(Spacer(1, (3 if compact_mode else 5) * mm))

    if compact_mode:
        info_data = [
            [Paragraph("<b>Cliente</b>", normal_style), Paragraph(str(cliente_label), normal_style), Paragraph("<b>Cód. Cliente</b>", normal_style), Paragraph(str(cliente_codigo) if cliente_codigo else "—", normal_style)],
            [Paragraph("<b>Solicita</b>", normal_style), Paragraph(str(dispatch_name), normal_style), Paragraph("<b>NIT / Cédula</b>", normal_style), Paragraph(str(cliente_nit) if cliente_nit else "—", normal_style)],
            [Paragraph("<b>Tienda / Ciudad</b>", normal_style), Paragraph(str(store_name), normal_style), Paragraph("<b>Canal</b>", normal_style), Paragraph(str(delivery_channel).title(), normal_style)],
            [Paragraph("<b>Correo</b>", normal_style), Paragraph(str(contact_email) if contact_email else "—", normal_style), Paragraph("<b>Fecha</b>", normal_style), Paragraph(f"{date_str} - {time_str}", normal_style)],
        ]
        info_table = Table(info_data, colWidths=[doc.width * 0.14, doc.width * 0.36, doc.width * 0.16, doc.width * 0.34])
    else:
        info_data = [
            [Paragraph("<b>Cliente</b>", normal_style), Paragraph(str(cliente_label), normal_style)],
            [Paragraph("<b>Solicita</b>", normal_style), Paragraph(str(dispatch_name), normal_style)],
            [Paragraph("<b>Cód. Cliente</b>", normal_style), Paragraph(str(cliente_codigo) if cliente_codigo else "—", normal_style)],
            [Paragraph("<b>NIT / Cédula</b>", normal_style), Paragraph(str(cliente_nit) if cliente_nit else "—", normal_style)],
            [Paragraph("<b>Tienda / Ciudad</b>", normal_style), Paragraph(str(store_name), normal_style)],
            [Paragraph("<b>Canal</b>", normal_style), Paragraph(str(delivery_channel).title(), normal_style)],
            [Paragraph("<b>Correo</b>", normal_style), Paragraph(str(contact_email) if contact_email else "—", normal_style)],
            [Paragraph("<b>Fecha</b>", normal_style), Paragraph(f"{date_str} - {time_str}", normal_style)],
        ]
        info_table = Table(info_data, colWidths=[doc.width * 0.28, doc.width * 0.72])
    info_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), brand_light_bg),
        ("BOX", (0, 0), (-1, -1), 0.5, brand_border),
        ("INNERGRID", (0, 0), (-1, -1), 0.3, brand_border),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4 if compact_mode else 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4 if compact_mode else 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 7 if compact_mode else 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7 if compact_mode else 10),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, (3 if compact_mode else 6) * mm))

    elements.append(Paragraph(f"Detalle del {request_label}", heading_style))
    elements.append(HRFlowable(width="100%", thickness=1, color=brand_accent, spaceBefore=2, spaceAfter=4))

    table_header = [
        Paragraph("<b>#</b>", ParagraphStyle("TH", parent=normal_style, textColor=white, alignment=TA_CENTER)),
        Paragraph("<b>Producto</b>", ParagraphStyle("TH", parent=normal_style, textColor=white)),
        Paragraph("<b>Referencia</b>", ParagraphStyle("TH", parent=normal_style, textColor=white, alignment=TA_CENTER)),
        Paragraph("<b>Cantidad</b>", ParagraphStyle("TH", parent=normal_style, textColor=white, alignment=TA_CENTER)),
        Paragraph("<b>Disponibilidad</b>", ParagraphStyle("TH", parent=normal_style, textColor=white, alignment=TA_CENTER)),
    ]
    table_data = [table_header]

    for idx, item in enumerate(matched_items, start=1):
        matched_product = item.get("matched_product") or {}
        raw_desc = matched_product.get("descripcion") or matched_product.get("nombre_articulo") or item.get("original_text") or "Producto"
        presentation = infer_product_presentation_from_row(matched_product)
        brand = infer_product_brand_from_row(matched_product)
        commercial_name = translate_product_to_commercial(raw_desc, presentation, brand)
        ref_code = matched_product.get("referencia") or matched_product.get("codigo_articulo") or "—"
        req = item.get("product_request") or {}
        qty_val = req.get("requested_quantity")
        qty_unit = req.get("requested_unit")
        if qty_val and qty_unit:
            qty_label = f"{format_quantity(qty_val)} {qty_unit}"
        elif qty_val:
            qty_label = format_quantity(qty_val)
        else:
            qty_label = "Por confirmar"
        stock_val = parse_numeric_value(matched_product.get("stock_total") if matched_product.get("stock_total") is not None else matched_product.get("stock")) or 0
        availability = "✅ Disponible" if stock_val > 0 else "⚠️ Agotado"

        row_bg = white if idx % 2 == 1 else brand_light_bg
        table_data.append([
            Paragraph(str(idx), ParagraphStyle("Cell", parent=normal_style, alignment=TA_CENTER)),
            Paragraph(commercial_name, normal_style),
            Paragraph(str(ref_code), ParagraphStyle("Cell", parent=normal_style, alignment=TA_CENTER)),
            Paragraph(qty_label, ParagraphStyle("Cell", parent=normal_style, alignment=TA_CENTER)),
            Paragraph(availability, ParagraphStyle("Cell", parent=normal_style, alignment=TA_CENTER)),
        ])

    if not matched_items:
        table_data.append([Paragraph("—", normal_style)] * 5)

    col_widths = [doc.width * 0.05, doc.width * 0.41, doc.width * 0.16, doc.width * 0.16, doc.width * 0.22] if compact_mode else [doc.width * 0.06, doc.width * 0.38, doc.width * 0.18, doc.width * 0.18, doc.width * 0.20]
    items_table = Table(table_data, colWidths=col_widths, repeatRows=1)
    table_style_cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), brand_dark),
        ("TEXTCOLOR", (0, 0), (-1, 0), white),
        ("BOX", (0, 0), (-1, -1), 0.5, brand_border),
        ("INNERGRID", (0, 0), (-1, -1), 0.3, brand_border),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4 if compact_mode else 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4 if compact_mode else 7),
        ("LEFTPADDING", (0, 0), (-1, -1), 4 if compact_mode else 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4 if compact_mode else 6),
    ]
    for row_idx in range(1, len(table_data)):
        bg = white if row_idx % 2 == 1 else brand_light_bg
        table_style_cmds.append(("BACKGROUND", (0, row_idx), (-1, row_idx), bg))
    items_table.setStyle(TableStyle(table_style_cmds))
    elements.append(items_table)
    elements.append(Spacer(1, (3 if compact_mode else 6) * mm))

    total_items = len(matched_items)
    pending_items = len([i for i in items if i.get("status") != "matched"])
    metrics_table = Table(
        [[
            Paragraph(f"<b>Confirmados</b><br/>{total_items}", ParagraphStyle("Metric", parent=normal_style, alignment=TA_CENTER)),
            Paragraph(f"<b>Pendientes</b><br/>{pending_items}", ParagraphStyle("Metric", parent=normal_style, alignment=TA_CENTER)),
            Paragraph(f"<b>Sede</b><br/>{escape(str(store_name))}", ParagraphStyle("Metric", parent=normal_style, alignment=TA_CENTER)),
        ]],
        colWidths=[doc.width / 3.0, doc.width / 3.0, doc.width / 3.0],
    )
    metrics_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), brand_light_bg),
        ("BOX", (0, 0), (-1, -1), 0.5, brand_border),
        ("INNERGRID", (0, 0), (-1, -1), 0.3, brand_border),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5 if compact_mode else 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5 if compact_mode else 8),
    ]))
    elements.append(metrics_table)
    elements.append(Spacer(1, (2 if compact_mode else 5) * mm))
    summary_text = f"<b>Total productos confirmados:</b> {total_items}"
    if pending_items > 0:
        summary_text += f" — <i>{pending_items} pendiente(s) por precisar</i>"
    elements.append(Paragraph(summary_text, normal_style))
    if observations:
        elements.append(Spacer(1, (2 if compact_mode else 3) * mm))
        elements.append(Paragraph(f"<b>Observaciones operativas:</b> {escape(str(observations))}", normal_style))
    elements.append(Spacer(1, (3 if compact_mode else 8) * mm))

    elements.append(HRFlowable(width="100%", thickness=0.5, color=brand_border, spaceBefore=4, spaceAfter=4))
    elements.append(Paragraph(
        "Este documento resume una solicitud comercial generada desde el CRM Ferreinox. "
        "No constituye factura ni cotización valorada y está sujeto a validación de inventario, alistamiento y confirmación operativa por Ferreinox SAS BIC.",
        small_style,
    ))
    elements.append(Spacer(1, 3 * mm))
    elements.append(Paragraph(
        f"{CORPORATE_BRAND['company_name']} | {CORPORATE_BRAND['service_email']} | {CORPORATE_BRAND['phone_landline']} | {CORPORATE_BRAND['website']} | {document_version} | {date_str}",
        ParagraphStyle("Footer", parent=small_style, alignment=TA_CENTER),
    ))

    doc.build(elements)
    buffer.seek(0)
    return buffer


def store_commercial_pdf(conversation_id: int, request_type: str, profile_name: Optional[str], cliente_contexto: Optional[dict], detail: dict):
    pdf_buffer = generate_commercial_pdf(conversation_id, request_type, profile_name, cliente_contexto, detail)
    pdf_id = uuid.uuid4().hex[:12]
    request_label = "Pedido" if request_type == "pedido" else "Cotizacion"
    filename = f"Ferreinox_{request_label}_CRM-{conversation_id}_{pdf_id}.pdf"
    PDF_STORAGE[pdf_id] = {
        "buffer": pdf_buffer.getvalue(),
        "filename": filename,
        "created_at": datetime.now().isoformat(),
        "conversation_id": conversation_id,
    }
    return pdf_id, filename


def infer_confirmed_order_store_filters(commercial_draft: dict, context: dict, conversation_context: dict, internal_user: Optional[dict] = None):
    existing_filters = [normalize_store_code(value) for value in (commercial_draft.get("store_filters") or [])]
    existing_filters = [value for value in existing_filters if value]
    if existing_filters:
        return list(dict.fromkeys(existing_filters))

    candidate_texts = []
    for item in commercial_draft.get("items") or []:
        original_text = item.get("original_text")
        if original_text:
            candidate_texts.append(str(original_text))

    recent_messages = load_recent_conversation_messages(context["conversation_id"], limit=20)
    for message in reversed(recent_messages):
        if message.get("direction") != "inbound":
            continue
        content = message.get("contenido") or ""
        if content:
            candidate_texts.append(content)

    for text_value in candidate_texts:
        inferred = [normalize_store_code(value) for value in extract_store_filters(text_value)]
        inferred = [value for value in inferred if value]
        if inferred:
            return list(dict.fromkeys(inferred))

    metadata = dict((internal_user or {}).get("metadata") or {})
    fallback_store = normalize_store_code(metadata.get("store_code"))
    return [fallback_store] if fallback_store else []


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


def build_purchase_summary_response_text(cliente_label: str, purchase_query: dict, purchases: Optional[dict]):
    totals = (purchases or {}).get("totals") or {}
    product_rows = (purchases or {}).get("products") or []
    if not totals or not totals.get("ultima_compra"):
        if purchase_query.get("has_time_filter"):
            return f"No encontré compras registradas para {cliente_label} en {purchase_query.get('label')}."
        return f"No encontré compras registradas en los últimos 12 meses para {cliente_label}."

    top_summary = "; ".join(
        f"{row['nombre_articulo']} ({format_currency(row['valor'])}, {int(float(row['unidades'] or 0))} unidades)"
        for row in product_rows[:5]
    ) or "sin productos destacados"
    if purchase_query.get("has_time_filter"):
        return (
            f"{cliente_label}\n"
            f"En {purchase_query.get('label')} compró {format_currency(totals.get('valor_total'))}.\n"
            f"Fueron {int(totals.get('lineas') or 0)} líneas y {int(float(totals.get('unidades_totales') or 0))} unidades.\n"
            f"Primera compra del periodo: {totals.get('primera_compra') or 'sin fecha'} | última compra: {totals.get('ultima_compra') or 'sin fecha'}.\n"
            f"Productos principales: {top_summary}"
        )
    return (
        f"{cliente_label}\n"
        f"En los últimos 12 meses compró {format_currency(totals.get('valor_total'))}.\n"
        f"Acumula {int(totals.get('lineas') or 0)} líneas y {int(float(totals.get('unidades_totales') or 0))} unidades.\n"
        f"Última compra: {totals.get('ultima_compra') or 'sin fecha'}.\n"
        f"Productos principales: {top_summary}"
    )


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
    product_context_updates = {}
    if intent == "consulta_productos" and product_context:
        product_context_updates = {
            "last_product_request": product_request or {},
            "last_product_query": user_message or "",
            "last_product_context": [
                {
                    "referencia": row.get("referencia") or row.get("codigo_articulo"),
                    "descripcion": get_exact_product_description(row),
                    "presentacion": infer_product_presentation_from_row(row),
                    "stock_por_tienda": row.get("stock_por_tienda"),
                }
                for row in product_context[:5]
            ],
        }

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
            referencia_solicitada = ", ".join((product_request or {}).get("core_terms") or [])
            return {
                "tono": "informativo",
                "intent": intent,
                "priority": "media",
                "summary": "Consulta de productos sin coincidencia exacta",
                "response_text": (
                    f"No encontré algo claro con {referencia_solicitada or 'esa referencia'}. "
                    "Dame la referencia, el código, la marca o la presentación y te ubico lo que necesitas."
                ),
                "should_create_task": False,
                "task_type": "seguimiento_cliente",
                "task_summary": "Consulta de productos sin match exacto",
                "task_detail": {"product_request": product_request or {}},
            }

        if len(product_context) == 1:
            top_row = product_context[0]
            audit_label = build_product_audit_label(top_row)
            top_stock = top_row.get("stock_total") if top_row.get("stock_total") is not None else top_row.get("stock")
            requested_store_codes = (product_request or {}).get("store_filters") or []
            requested_store_label = STORE_CODE_LABELS.get(requested_store_codes[0]) if len(requested_store_codes) == 1 else None
            if top_stock is not None and parse_numeric_value(top_stock) and parse_numeric_value(top_stock) > 0:
                if requested_store_label:
                    direct_response = f"Sí tenemos {audit_label} en {requested_store_label}. ¿Te separo alguna cantidad?"
                else:
                    direct_response = f"Sí tenemos {audit_label} disponible. ¿En qué tienda lo necesitas?"
            else:
                direct_response = f"El producto {audit_label} lo veo agotado en este momento. ¿Quieres que te revise otra presentación o alternativa?"
            return {
                "tono": "informativo",
                "intent": intent,
                "priority": "media",
                "summary": "Consulta de producto con coincidencia directa",
                "response_text": direct_response,
                "context_updates": product_context_updates,
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
                commercial_label = build_product_audit_label(row)
                stock_val = parse_numeric_value(row.get("stock_total") if row.get("stock_total") is not None else row.get("stock"))
                stock_note = f" | stock {format_quantity(stock_val)}" if stock_val and stock_val > 0 else " | agotado"
                clarification_lines.append(f"{index}. {commercial_label}{stock_note}")

            return {
                "tono": "consultivo",
                "intent": intent,
                "priority": "media",
                "summary": "Consulta de productos con necesidad de aclaracion",
                "response_text": build_best_product_clarification_question(product_request, product_context)
                + "\n"
                + "\n".join(clarification_lines),
                "context_updates": product_context_updates,
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
            top_stock = top_row.get("stock_total") if top_row.get("stock_total") is not None else top_row.get("stock")
            audit_label = build_product_audit_label(top_row)
            stock_value = parse_numeric_value(top_stock) or 0
            if stock_value > 0:
                store_response = f"Sí, en {requested_store_label} tenemos {audit_label}."
                if product_request and product_request.get("requested_quantity"):
                    req_qty = float(product_request["requested_quantity"])
                    if stock_value >= req_qty:
                        store_response += " Te alcanza perfecto para lo que necesitas."
                    else:
                        store_response += " Pero no alcanza para toda la cantidad que pides."
                store_response += " ¿Te separo alguna cantidad o te reviso otra presentación?"
            else:
                store_response = f"El producto {audit_label} no lo veo disponible en {requested_store_label} en este momento. ¿Quieres que revise en otra sede?"
            return {
                "tono": "informativo",
                "intent": intent,
                "priority": "media",
                "summary": "Consulta de producto con tienda especifica",
                "response_text": store_response,
                "context_updates": product_context_updates,
                "should_create_task": False,
                "task_type": "seguimiento_cliente",
                "task_summary": "Consulta de producto por tienda",
                "task_detail": {"products": product_context, "product_request": product_request or {}},
            }

        for row in product_context[:3]:
            commercial_name = build_product_audit_label(row)
            stock = row.get("stock_total") if row.get("stock_total") is not None else row.get("stock")
            stock_value = parse_numeric_value(stock)
            if stock_value and stock_value > 0:
                line = f"{commercial_name} — disponible"
            else:
                line = f"{commercial_name} — agotado"
            product_lines.append(line)
        return {
            "tono": "informativo",
            "intent": intent,
            "priority": "media",
            "summary": "Consulta de productos",
            "context_updates": product_context_updates,
            "response_text": (
                f"{quantity_note + '. ' if quantity_note else ''}"
                f"Encontré estas opciones: {'; '.join(product_lines)}. "
                "¿Cuál es la que buscas o en qué tienda lo necesitas?"
            ),
            "should_create_task": False,
            "task_type": "seguimiento_cliente",
            "task_summary": "Consulta de productos",
            "task_detail": {"products": product_context, "product_request": product_request or {}},
        }

    return None


def build_verification_success_reply(profile_name: Optional[str], cliente_contexto: Optional[dict]):
    cliente_nombre = (cliente_contexto or {}).get("nombre_cliente")
    return (
        f"¡Listo, ya te ubiqué{', ' + str(cliente_nombre) if cliente_nombre else ''}! "
        "Ya puedo ayudarte con cartera, compras y todo tu historial comercial."
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
        is_numeric_code = bool(re.fullmatch(r"\d{4,10}", str(code or "")))
        params[f"code_like_{index}"] = f"%{code}%"
        params[f"code_exact_{index}"] = str(code)
        params[f"code_compact_{index}"] = f"%{normalize_reference_value(code)}%"
        code_filters.append(f"producto_codigo = :code_exact_{index}")
        code_filters.append(f"referencia = :code_exact_{index}")
        code_filters.append(f"producto_codigo LIKE :code_like_{index}")
        code_filters.append(f"search_blob ILIKE :code_like_{index}")
        if not is_numeric_code:
            code_filters.append(f"search_compact LIKE :code_compact_{index}")
            score_terms.append(
                f"CASE WHEN producto_codigo = :code_exact_{index} OR referencia = :code_exact_{index} THEN 100"
                f" WHEN producto_codigo LIKE :code_like_{index} OR search_blob ILIKE :code_like_{index} OR search_compact LIKE :code_compact_{index} THEN 1 ELSE 0 END"
            )
        else:
            score_terms.append(
                f"CASE WHEN producto_codigo = :code_exact_{index} OR referencia = :code_exact_{index} THEN 100"
                f" WHEN producto_codigo LIKE :code_like_{index} OR search_blob ILIKE :code_like_{index} THEN 1 ELSE 0 END"
            )

    if store_filters:
        store_code_filters = []
        store_score_terms = []
        for index, code in enumerate(product_codes[:3]):
            store_code_filters.append(f"referencia_normalizada = :code_exact_{index}")
            store_code_filters.append(f"referencia_normalizada LIKE :code_like_{index}")
            store_code_filters.append(f"search_blob ILIKE :code_like_{index}")
            store_score_terms.append(
                f"CASE WHEN referencia_normalizada = :code_exact_{index} THEN 100"
                f" WHEN referencia_normalizada LIKE :code_like_{index} OR search_blob ILIKE :code_like_{index} THEN 1 ELSE 0 END"
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


def build_curated_catalog_search_terms(text_value: Optional[str], product_request: Optional[dict]):
    request = product_request or {}
    search_terms = []

    def add_term(value: Optional[str]):
        normalized = normalize_text_value(value)
        if normalized and normalized not in search_terms:
            search_terms.append(normalized)

    add_term(request.get("canonical_product"))
    for term in get_specific_product_terms(request):
        add_term(term)
    for term in request.get("brand_filters") or []:
        add_term(term)
    for term in request.get("color_filters") or []:
        add_term(term)
    for term in request.get("finish_filters") or []:
        add_term(term)
    for code in request.get("product_codes") or []:
        add_term(code)
    if not search_terms:
        for term in request.get("core_terms") or []:
            add_term(term)
    add_term(text_value)
    return search_terms[:8]


def fetch_curated_catalog_product_rows(connection, text_value: Optional[str], product_request: Optional[dict], limit: int = 12):
    request = product_request or {}
    search_terms = build_curated_catalog_search_terms(text_value, request)
    if not search_terms:
        return []

    params = {}
    search_filters = []
    score_terms = []
    for index, term in enumerate(search_terms):
        params[f"catalog_term_{index}"] = f"%{term}%"
        search_filters.append(
            "(" 
            f"p.search_blob ILIKE :catalog_term_{index} OR "
            f"a.alias_normalizado ILIKE :catalog_term_{index} OR "
            f"public.fn_normalize_text(COALESCE(a.producto_padre_busqueda, '')) ILIKE :catalog_term_{index} OR "
            f"public.fn_normalize_text(COALESCE(a.familia_consulta, '')) ILIKE :catalog_term_{index} OR "
            f"public.fn_normalize_text(COALESCE(p.producto_padre_busqueda_sugerido, '')) ILIKE :catalog_term_{index} OR "
            f"public.fn_normalize_text(COALESCE(p.familia_consulta_sugerida, '')) ILIKE :catalog_term_{index})"
        )
        score_terms.append(
            f"MAX(CASE WHEN p.search_blob ILIKE :catalog_term_{index} OR a.alias_normalizado ILIKE :catalog_term_{index} THEN 1 ELSE 0 END)"
        )

    base_exact = normalize_text_value(
        request.get("canonical_product")
        or " ".join(get_specific_product_terms(request)[:4])
        or " ".join((request.get("core_terms") or [])[:2])
    )
    color_exact = normalize_text_value(" ".join(request.get("color_filters") or []))
    finish_exact = normalize_text_value(" ".join(request.get("finish_filters") or []))
    params.update(
        {
            "base_exact": base_exact,
            "color_exact": color_exact,
            "color_like": f"%{color_exact}%" if color_exact else "",
            "finish_exact": finish_exact,
            "finish_like": f"%{finish_exact}%" if finish_exact else "",
            "presentation_exact": normalize_text_value(request.get("requested_unit")),
        }
    )
    where_clause = " OR ".join(search_filters)
    brand_filters = request.get("brand_filters") or []
    if brand_filters:
        brand_clauses = []
        for index, brand_name in enumerate(brand_filters[:4]):
            params[f"brand_term_{index}"] = f"%{normalize_text_value(brand_name)}%"
            brand_clauses.append(
                f"p.search_blob ILIKE :brand_term_{index} OR "
                f"public.fn_normalize_text(COALESCE(p.marca, '')) ILIKE :brand_term_{index} OR "
                f"public.fn_normalize_text(COALESCE(p.producto_padre_busqueda_sugerido, '')) ILIKE :brand_term_{index} OR "
                f"public.fn_normalize_text(COALESCE(p.familia_consulta_sugerida, '')) ILIKE :brand_term_{index}"
            )
        where_clause = f"({where_clause}) AND ({' OR '.join(brand_clauses)})"
    requested_colors = request.get("color_filters") or []
    if requested_colors:
        color_groups = []
        for color_index, color_value in enumerate(requested_colors[:3]):
            token_clauses = []
            for token_index, token in enumerate(tokenize_search_phrase(color_value) or [color_value]):
                token_prefix = normalize_text_value(token)[:4]
                if not token_prefix:
                    continue
                param_name = f"color_term_{color_index}_{token_index}"
                params[param_name] = f"%{token_prefix}%"
                token_clauses.append(
                    f"p.search_blob ILIKE :{param_name} OR "
                    f"public.fn_normalize_text(COALESCE(p.color_detectado, '')) ILIKE :{param_name} OR "
                    f"public.fn_normalize_text(COALESCE(p.color_raiz, '')) ILIKE :{param_name}"
                )
            if token_clauses:
                color_groups.append("(" + " AND ".join(token_clauses) + ")")
        if color_groups:
            where_clause = f"({where_clause}) AND ({' OR '.join(color_groups)})"
    score_clause = " + ".join(score_terms) if score_terms else "0"

    return connection.execute(
        text(
            f"""
            SELECT
                p.producto_codigo,
                p.referencia,
                COALESCE(p.descripcion_inventario, p.descripcion_base) AS descripcion,
                p.marca,
                p.departamentos,
                p.stock_total,
                p.stock_por_tienda,
                p.costo_promedio_und,
                p.ventas_unidades_total,
                p.ventas_valor_total,
                p.ultima_venta,
                p.presentacion_canonica,
                p.color_detectado,
                p.color_raiz,
                p.acabado_detectado,
                COALESCE(MAX(NULLIF(a.familia_consulta, '')), p.familia_consulta_sugerida) AS familia_consulta,
                COALESCE(MAX(NULLIF(a.producto_padre_busqueda, '')), p.producto_padre_busqueda_sugerido) AS producto_padre_busqueda,
                MAX(a.pregunta_desambiguacion) AS pregunta_desambiguacion,
                MAX(a.terminos_excluir) AS terminos_excluir,
                ({score_clause}) AS match_score,
                CASE
                    WHEN :base_exact <> '' AND (
                        public.fn_normalize_text(COALESCE(p.producto_padre_busqueda_sugerido, '')) = :base_exact
                        OR MAX(CASE WHEN public.fn_normalize_text(COALESCE(a.producto_padre_busqueda, '')) = :base_exact THEN 1 ELSE 0 END) = 1
                        OR MAX(CASE WHEN a.alias_normalizado = :base_exact THEN 1 ELSE 0 END) = 1
                    ) THEN 2 ELSE 0
                END AS base_exact_score,
                CASE
                    WHEN :presentation_exact <> '' AND public.fn_normalize_text(COALESCE(p.presentacion_canonica, '')) = :presentation_exact THEN 1 ELSE 0
                END AS presentation_score,
                CASE
                    WHEN :color_exact <> '' AND (
                        public.fn_normalize_text(COALESCE(p.color_detectado, '')) = :color_exact
                        OR public.fn_normalize_text(COALESCE(p.color_raiz, '')) = :color_exact
                        OR MAX(CASE WHEN a.alias_type = 'color' AND a.alias_normalizado = :color_exact THEN 1 ELSE 0 END) = 1
                        OR MAX(CASE WHEN p.search_blob ILIKE :color_like THEN 1 ELSE 0 END) = 1
                    ) THEN 1 ELSE 0
                END AS color_score,
                CASE
                    WHEN :finish_exact <> '' AND (
                        public.fn_normalize_text(COALESCE(p.acabado_detectado, '')) = :finish_exact
                        OR MAX(CASE WHEN p.search_blob ILIKE :finish_like THEN 1 ELSE 0 END) = 1
                    ) THEN 1 ELSE 0
                END AS finish_score,
                CASE WHEN COALESCE(p.stock_total, 0) > 0 THEN 1 ELSE 0 END AS stock_score
            FROM public.vw_agent_catalog_product_search p
            LEFT JOIN public.vw_agent_catalog_alias_active a
                ON a.producto_codigo = p.producto_codigo
            WHERE {where_clause}
            GROUP BY
                p.producto_codigo,
                p.referencia,
                COALESCE(p.descripcion_inventario, p.descripcion_base),
                p.marca,
                p.departamentos,
                p.stock_total,
                p.stock_por_tienda,
                p.costo_promedio_und,
                p.ventas_unidades_total,
                p.ventas_valor_total,
                p.ultima_venta,
                p.presentacion_canonica,
                p.color_detectado,
                p.color_raiz,
                p.acabado_detectado,
                p.familia_consulta_sugerida,
                p.producto_padre_busqueda_sugerido
            ORDER BY
                base_exact_score DESC,
                presentation_score DESC,
                color_score DESC,
                finish_score DESC,
                stock_score DESC,
                COALESCE(p.ventas_unidades_total, 0) DESC,
                COALESCE(p.ultima_venta, DATE '1900-01-01') DESC,
                COALESCE(p.stock_total, 0) DESC,
                match_score DESC,
                descripcion ASC NULLS LAST
            LIMIT {int(limit)}
            """
        ),
        params,
    ).mappings().all()


def hydrate_curated_rows_with_store_inventory(connection, curated_rows: list[dict], store_filters: list[str]):
    if not curated_rows or not store_filters:
        return curated_rows

    reference_values = [str(row.get("referencia")) for row in curated_rows if row.get("referencia")]
    if not reference_values:
        return curated_rows

    inventory_rows = fetch_reference_product_rows(connection, reference_values, store_filters, 100)
    if not inventory_rows:
        return curated_rows

    inventory_map = {
        normalize_reference_value(row.get("referencia") or row.get("codigo_articulo")): dict(row)
        for row in inventory_rows
    }
    hydrated_rows = []
    for curated_row in curated_rows:
        reference_key = normalize_reference_value(curated_row.get("referencia") or curated_row.get("producto_codigo"))
        inventory_row = inventory_map.get(reference_key)
        if not inventory_row:
            continue
        merged_row = dict(inventory_row)
        for key, value in curated_row.items():
            if value is not None or key not in merged_row:
                merged_row[key] = value
        hydrated_rows.append(merged_row)
    return hydrated_rows or curated_rows


def rank_product_match_rows(product_rows: list[dict], product_request: Optional[dict], normalized_query: Optional[str]):
    if not product_rows:
        return []

    request = product_request or {}
    brand_filters = request.get("brand_filters") or []
    core_terms = request.get("core_terms") or []
    preferred_family_terms = expand_product_terms([normalize_reference_value(core_terms[0])]) if core_terms else []
    specific_terms = get_specific_product_terms(request)
    code_terms = []
    seen_code_terms = set()
    for raw_code in request.get("product_codes") or []:
        normalized_code = normalize_reference_value(raw_code)
        if normalized_code and normalized_code not in seen_code_terms:
            seen_code_terms.add(normalized_code)
            code_terms.append(normalized_code)

    ranked_rows = []
    for row in product_rows:
        candidate = dict(row)
        candidate_text = " ".join(
            str(value)
            for value in [
                candidate.get("descripcion") or candidate.get("nombre_articulo"),
                candidate.get("referencia") or candidate.get("codigo_articulo"),
                candidate.get("producto_codigo"),
                candidate.get("marca") or candidate.get("marca_producto"),
                candidate.get("familia_consulta"),
                candidate.get("producto_padre_busqueda"),
            ]
            if value
        )
        normalized_candidate_text = normalize_text_value(candidate_text)
        compact_candidate_text = normalize_reference_value(candidate_text)
        candidate_reference = normalize_reference_value(
            candidate.get("referencia") or candidate.get("producto_codigo") or candidate.get("codigo_articulo")
        )
        candidate_presentation = infer_product_presentation_from_row(candidate)
        candidate_brand = infer_product_brand_from_row(candidate)
        candidate_size = infer_product_size_from_row(candidate)
        candidate_direction = infer_product_direction_from_row(candidate)
        candidate_color = infer_product_color_from_row(candidate)
        candidate_finish = infer_product_finish_from_row(candidate)

        specific_matches = 0
        for term in specific_terms:
            normalized_term = normalize_text_value(term)
            compact_term = normalize_reference_value(term)
            if (
                normalized_term and normalized_term in normalized_candidate_text
            ) or (
                compact_term and len(compact_term) >= 4 and compact_term in compact_candidate_text
            ):
                specific_matches += 1

        exact_code_matches = 0
        for code_term in code_terms:
            if not code_term:
                continue
            if candidate_reference == code_term or code_term in compact_candidate_text:
                exact_code_matches += 1

        candidate["exact_code_score"] = exact_code_matches
        candidate["fuzzy_score"] = round(sequence_similarity(normalized_query, candidate_text), 4)
        candidate["family_score"] = 1 if any(term and term in normalized_candidate_text for term in preferred_family_terms[:5]) else 0
        candidate["specific_score"] = specific_matches
        candidate["presentation_score"] = 1 if request.get("requested_unit") and candidate_presentation == request.get("requested_unit") else 0
        candidate["brand_score"] = 1 if brand_filters and candidate_brand in brand_filters else 0
        candidate["size_score"] = 1 if (request.get("size_filters") or []) and candidate_size in (request.get("size_filters") or []) else 0
        candidate["direction_score"] = 1 if (request.get("direction_filters") or []) and candidate_direction in (request.get("direction_filters") or []) else 0
        candidate["color_score"] = 1 if (request.get("color_filters") or []) and candidate_color in (request.get("color_filters") or []) else 0
        candidate["finish_score"] = 1 if (request.get("finish_filters") or []) and candidate_finish in (request.get("finish_filters") or []) else 0
        ranked_rows.append(candidate)

    ranked_rows.sort(
        key=lambda item: (
            item.get("exact_code_score") or 0,
            item.get("direction_score") or 0,
            item.get("size_score") or 0,
            item.get("presentation_score") or 0,
            item.get("finish_score") or 0,
            item.get("color_score") or 0,
            item.get("brand_score") or 0,
            item.get("specific_score") or 0,
            item.get("base_exact_score") or 0,
            item.get("family_score") or 0,
            item.get("match_score") or 0,
            item.get("fuzzy_score") or 0,
            parse_numeric_value(item.get("stock_total")) or 0,
        ),
        reverse=True,
    )

    top_exact_code_score = ranked_rows[0].get("exact_code_score") or 0 if ranked_rows else 0
    if top_exact_code_score > 0:
        ranked_rows = [item for item in ranked_rows if (item.get("exact_code_score") or 0) == top_exact_code_score]

    top_specific_score = ranked_rows[0].get("specific_score") or 0 if ranked_rows else 0
    if top_specific_score >= 2:
        ranked_rows = [item for item in ranked_rows if (item.get("specific_score") or 0) == top_specific_score]
    elif top_specific_score > 0 and len(specific_terms) == 1:
        ranked_rows = [item for item in ranked_rows if (item.get("specific_score") or 0) > 0]

    top_match_score = ranked_rows[0].get("match_score") or 0 if ranked_rows else 0
    if top_match_score >= 2:
        ranked_rows = [
            item for item in ranked_rows
            if (item.get("match_score") or 0) >= max(2, top_match_score - 1)
            or (item.get("size_score") or 0) > 0
            or (item.get("brand_score") or 0) > 0
            or (item.get("family_score") or 0) > 0
            or (item.get("exact_code_score") or 0) > 0
        ]

    if request.get("requested_unit"):
        exact_presentation_rows = [
            item for item in ranked_rows
            if infer_product_presentation_from_row(item) == request.get("requested_unit")
        ]
        if exact_presentation_rows:
            ranked_rows = exact_presentation_rows
    if request.get("color_filters"):
        exact_color_rows = [
            item for item in ranked_rows
            if row_matches_requested_colors(item, request.get("color_filters") or [])
        ]
        if exact_color_rows:
            ranked_rows = exact_color_rows
    if request.get("finish_filters"):
        exact_finish_rows = [
            item for item in ranked_rows
            if infer_product_finish_from_row(item) in (request.get("finish_filters") or [])
        ]
        if exact_finish_rows:
            ranked_rows = exact_finish_rows
    if brand_filters:
        exact_brand_rows = [
            item for item in ranked_rows
            if infer_product_brand_from_row(item) in brand_filters
        ]
        if exact_brand_rows:
            ranked_rows = exact_brand_rows
    ranked_rows = filter_rows_by_requested_size(ranked_rows, request)
    if any((parse_numeric_value(item.get("stock_total")) or 0) > 0 for item in ranked_rows):
        ranked_rows = [item for item in ranked_rows if (parse_numeric_value(item.get("stock_total")) or 0) > 0]
    return ranked_rows


def lookup_product_context(text_value: Optional[str], product_request: Optional[dict] = None):
    product_request = prepare_product_request_for_search(text_value, product_request)
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
                    ranked_code_rows = rank_product_match_rows([dict(row) for row in code_rows], product_request, normalized_query)
                    ranked_code_rows = filter_rows_by_requested_presentation(ranked_code_rows, product_request)
                    return ranked_code_rows[:5]

            if not terms:
                return []

            curated_rows = fetch_curated_catalog_product_rows(connection, text_value, product_request, limit=100)
            if curated_rows:
                ranked_curated_rows = hydrate_curated_rows_with_store_inventory(
                    connection,
                    [dict(row) for row in curated_rows],
                    store_filters,
                )
                ranked_curated_rows = rank_product_match_rows(ranked_curated_rows, product_request, normalized_query)
                if ranked_curated_rows:
                    return ranked_curated_rows[:5]

            query_terms = []
            for term in list(core_terms) + list(terms):
                if term not in query_terms:
                    query_terms.append(term)
                if len(query_terms) == 5:
                    break
            rows = fetch_term_product_rows(connection, query_terms, store_filters)

            if rows:
                ranked_rows = rank_product_match_rows([dict(row) for row in rows], product_request, normalized_query)
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
        "Para darte esa info por tu seguridad, ¿me regalas tu número de cédula o NIT por favor? 🔒"
    )


def build_name_confirmation_challenge(cliente_nombre: str):
    return (
        f"Por seguridad, encontré una cuenta asociada. ¿Me confirmas si el titular es *{cliente_nombre}*? "
        "Respóndeme sí o no."
    )


def is_name_confirmation_response(text_value: Optional[str]):
    """Check if the message is a yes/no confirmation to the name challenge."""
    lowered = normalize_text_value(text_value)
    if not lowered:
        return None
    if re.match(r"^(si|sí|eso es|asi es|as[ií] es|correcto|exacto|dale|listo|de una|ok|okay|perfecto|confirmado|ese soy|soy yo|es[ae]? soy|es[ae]? es|ese soy yo|si se[ñn]or|si claro|claro que si|afirmativo|efectivamente)[.!?,\s]*.*$", lowered):
        return True
    if re.match(r"^(no|nop|negativo|no soy|no es|ese no|esa no|no es esa?|no soy yo|ese no es|esa no es|no ese no|para nada)[.!?,\s]*.*$", lowered):
        return False
    return None


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
                "Eres el Asesor Comercial y Técnico Senior de Ferreinox SAS BIC. Llevas más de 13 años atendiendo mostrador, diagnosticando problemas y vendiendo pinturas Pintuco, herramientas, cerraduras Yale, brochas Goya y todo el portafolio ferretero. Eres un solucionador de problemas, no un simple despachador. "
                "Tu tono es 100% conversacional, humano, cordial y comercial. Mensajes CORTOS: máximo 2-3 líneas por turno. NUNCA suenas como robot.\n\n"
                "REGLAS INQUEBRANTABLES:\n"
                "1. PROHIBIDO saludar en cada turno. Solo saluda si es el PRIMER mensaje de la conversación. Después conversa fluidamente.\n"
                "2. PROHIBIDO usar plantillas tipo 'Hola, [Nombre]', 'Resumen del caso:', 'Si necesitas algo más...', 'Encontré esta referencia para tu consulta'.\n"
                "3. PROHIBIDO vomitar la base de datos. Nunca enumeres stock de todas las tiendas. Si el cliente dijo Pereira, responde SOLO sobre Pereira en lenguaje humano.\n"
                "4. REFERENCIA AUDITABLE OBLIGATORIA: cuando confirmes inventario o muestres opciones con referencia, usa la descripción exacta que viene del ERP/backend. No la reescribas ni cambies base, tint, paste, color o modelo. Si el JSON trae `visibilidad_tienda_exacta=false`, no confirmes stock para esa sede: aclara que recuperaste la referencia correcta pero no tienes desglose exacto de esa tienda en la vista actual.\n"
                "5. PIENSA ANTES DE ACTUAR: clasifica mentalmente la intención del cliente antes de responder.\n"
                "   - Si el cliente plantea un PROBLEMA GENERAL (ej. humedad, pintar un techo, proteger un metal, tratar madera), primero activa un EMBUDO DE DIAGNÓSTICO. NO recomiendes nada todavía y NO uses RAG todavía.\n"
                "   - Si pregunta un dato técnico puntual sobre un producto ya identificado (ej. catalizador, tiempo de secado, dilución, rendimiento, preparación de superficie), ahí sí usa `consultar_conocimiento_tecnico` para buscar el dato exacto en las fichas técnicas vectorizadas ANTES de responder. NUNCA respondas preguntas técnicas de memoria.\n"
                "   - Si pide comprar o verificar disponibilidad de un producto → INVENTARIO, ahí sí consulta la base.\n"
                "   - Si dice reclamo, queja, garantía → RECLAMO, activa empatía y protocolo paso a paso. NO crees ticket hasta tener producto, problema y correo.\n"
                "   - Si pide cartera, saldos → CARTERA, valida identidad primero.\n"
                "6. NUNCA busques verbos o intenciones como parámetro de inventario. 'necesito hacer un pedido' es una INTENCIÓN, no un producto.\n"
                "7. EMBUDO DE DIAGNÓSTICO OBLIGATORIO: cuando el problema sea general, haz MÁXIMO 2 preguntas clave por mensaje para acotar la necesidad como humano de mostrador, no como formulario. Ejemplos: humedad → interior/exterior y muro pintado/obra negra; madera → intemperie/bajo techo y si tiene recubrimiento previo; metal → tipo de metal y agresividad del ambiente.\n"
                "8. TÚ GUÍAS AL CLIENTE. Haz preguntas progresivas y útiles. Nunca bombardees con más de 2 preguntas técnicas por turno.\n"
                "9. PREGUNTAS CASUALES O FUERA DE TEMA: Si el cliente pregunta algo que NO es del negocio (ej. 'cuánto es 10+10', un chiste, el clima), "
                "responde brevemente con naturalidad y luego redirige: 'Jaja, son 20 😄 Bueno, ¿seguimos con el pedido?' NO ignores la pregunta, pero tampoco te quedes en ella.\n"
                "10. FLUJO ACTIVO: Si hay un pedido, cotización o reclamo en curso (revisa el historial reciente), NO lo abandones. "
                "Si el cliente cambia de tema brevemente, contesta y retoma el flujo activo. Solo abandona el flujo si el cliente explícitamente dice que ya no lo quiere.\n"
                "11. NUNCA digas 'Un momento, por favor', 'Voy a verificar', 'Déjame revisar' como respuesta final. Tú ya tienes la info o no la tienes. Responde directamente.\n"
                "12. MURO DE LA VERDAD: cuando consultes fichas técnicas o FDS, responde ÚNICA Y EXCLUSIVAMENTE con lo recuperado. Si el dato exacto no aparece en el texto base, dilo así: 'Ese dato exacto no lo tengo en la ficha técnica base en este momento.' Nunca lo completes con intuición.\n\n"
                "PORTAFOLIO VÁLIDO: Pintuco (Viniltex, Doméstico, Pintulux 3en1, Koraza, Aerocolor), Abracol, Yale, Goya, Mega y las categorías reales del ERP. "
                "No inventes marcas fuera del portafolio.\n\n"
                "JERGA FERRETERA: 18.93L o 1/5 = cuñete, 3.79L o 1/1 = galón, 0.95L o 1/4 = cuarto, 2/5 = 2 cuñetes, 3/1 = 3 galones.\n\n"
                "SEGURIDAD: Nunca reveles cartera, saldos o datos privados si verification_state.verified es falso. Pide cédula o NIT primero.\n\n"
                "Si no tienes un dato seguro, dilo y ofrece el siguiente paso. Nunca inventes saldos, fechas o datos.\n\n"
                "Devuelve JSON válido con: tono, intent, priority, summary, response_text, should_create_task, task_type, task_summary, task_detail."
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
        "response_text": "Recibimos tu mensaje. Un asesor te contactará pronto.",
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


def send_whatsapp_document_bytes(to_phone: str, document_bytes: bytes, filename: str, caption: Optional[str] = None):
    upload_response = requests.post(
        f"https://graph.facebook.com/v22.0/{get_whatsapp_phone_number_id()}/media",
        headers={"Authorization": f"Bearer {get_whatsapp_access_token()}"},
        data={"messaging_product": "whatsapp", "type": "application/pdf"},
        files={"file": (filename, document_bytes, "application/pdf")},
        timeout=30,
    )
    if upload_response.status_code >= 400:
        try:
            error_payload = upload_response.json()
        except Exception:
            error_payload = {"raw": upload_response.text}
        raise RuntimeError(
            f"WhatsApp media upload devolvió {upload_response.status_code}: {safe_json_dumps(error_payload)}"
        )

    media_payload = upload_response.json()
    media_id = media_payload.get("id")
    if not media_id:
        raise RuntimeError(f"WhatsApp media upload no devolvió id: {safe_json_dumps(media_payload)}")

    payload = {
        "messaging_product": "whatsapp",
        "to": to_phone.lstrip("+"),
        "type": "document",
        "document": {
            "id": media_id,
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


# ── Agent v2: Function Calling Architecture ─────────────────────────

AGENT_SYSTEM_PROMPT_V2 = """Eres el Asesor Comercial y Técnico Senior de Ferreinox SAS BIC, una ferretería con más de 13 años de experiencia. \
Atiendes clientes por WhatsApp con tono conversacional, humano, cordial y comercial. Eres un solucionador de problemas y cierras ventas técnicas con criterio de experto.

REGLAS FUNDAMENTALES:
1. Mensajes CORTOS: máximo 3-4 líneas por turno. Nunca suenes como robot.
2. PROHIBIDO saludar repetidamente. Solo saluda si es el PRIMER mensaje de la conversación.
3. PROHIBIDO usar plantillas tipo "Hola, [Nombre]", "Resumen del caso:", "Si necesitas algo más...".
4. REFERENCIA AUDITABLE OBLIGATORIA:
    - Cuando `consultar_inventario` devuelva referencias, muestra la descripción exacta del ERP/backend. No la reescribas ni la resumas si eso cambia base, tint, paste, color o modelo.
    - 18.93L o 1/5 = cuñete, 3.79L o 1/1 = galón, 0.95L o 1/4 = cuarto.
    - Puedes explicar la presentación, pero no alteres el nombre real del producto.
    - Si el JSON trae `visibilidad_tienda_exacta=false`, no confirmes stock de esa sede. Di que recuperaste la referencia correcta, pero que esa tienda no tiene desglose exacto en la vista actual.
5. PIENSA antes de actuar: clasifica la intención del cliente.
   - Si el cliente plantea un PROBLEMA GENERAL (ej. humedad, goteras, techo, metal, madera, corrosión), activa primero un EMBUDO DE DIAGNÓSTICO. NO recomiendes todavía y NO llames `consultar_conocimiento_tecnico` todavía.
   - Si la pregunta ya es un dato técnico puntual sobre un producto o sistema identificado (aplicación, secado, rodillos, dilución, catalizador, mezcla, preparación, rendimiento), usa `consultar_conocimiento_tecnico` OBLIGATORIAMENTE antes de responder. NUNCA respondas de memoria.
   - Pide comprar, cotizar o verificar disponibilidad de un producto → usa consultar_inventario.
   - Dice reclamo, queja, garantía → empatía y protocolo paso a paso (producto, problema, correo).
   - Pide cartera, saldos, facturas → usa consultar_cartera (requiere verificación primero).
   - Pide historial de compras → usa consultar_compras (requiere verificación primero).
   - Problema técnico (humedad, goteras, moho, descascaramiento, ampollas) → ASESORÍA TÉCNICA: primero diagnostica y solo después usa `consultar_conocimiento_tecnico` con la necesidad exacta diagnosticada.
6. NUNCA busques verbos o intenciones como productos. "necesito hacer un pedido" es INTENCIÓN, no producto. Pregunta qué productos necesita.
7. EMBUDO DE DIAGNÓSTICO OBLIGATORIO: cuando el cliente exponga un problema general, haz MÁXIMO 2 preguntas clave por mensaje. Deben ser preguntas de diagnóstico, no relleno. Ejemplos: humedad → interior/exterior y si la pared está pintada o en obra negra; madera → intemperie o bajo techo y si tiene recubrimiento previo; metal → tipo de metal y ambiente (urbano, industrial o marino).
8. REGLA DE CONVERSACIÓN NATURAL: máximo 2 preguntas clave por turno. No abrumes al cliente ni suenes a formulario.
9. Preguntas fuera de tema: responde brevemente con naturalidad y redirige al negocio.
10. FLUJO ACTIVO: Si hay un pedido o reclamo en curso, no lo abandones a menos que el cliente lo pida explícitamente.
11. NUNCA digas "Voy a verificar", "Déjame revisar". Responde directamente con lo que sabes.
12. CIERRE: Si el cliente dice "gracias", "chao", "hasta luego", "no más por ahora", despídete cordialmente y brevemente.
13. "A nombre de..." durante un pedido = el cliente indica el destinatario/titular del pedido, NO es un producto.
14. Cuando el cliente confirma un pedido, resume TODOS los productos completos con cantidades. Nunca omitas items.
15. COHERENCIA CONVERSACIONAL ABSOLUTA:
    - Lee el historial reciente COMPLETO antes de responder. NUNCA repitas una pregunta que ya hiciste o que el cliente ya respondió.
    - Si el cliente ya te dijo qué necesita (ej. 'humedad en una pared'), NO vuelvas a preguntar '¿qué tipo de recomendación?'. Avanza con la solución.
    - PROHIBIDO mezclar temas de conversaciones diferentes. Si el cliente habla de humedad, tu respuesta debe ser sobre humedad. NUNCA le metas temas de traslados, sedes o faltantes si no los pidió.
    - Si el cliente te da contexto (ej. 'tiene humedad en la base de los muros'), usa ESE contexto como punto de partida. Haz preguntas de DIAGNÓSTICO progresivas, no genéricas.
    - NUNCA des respuestas genéricas como 'un agente de curado específico'. Si usas `consultar_conocimiento_tecnico`, lee 'respuesta_rag' y extrae el DATO CONCRETO (nombre del catalizador, código, proporción, tiempo exacto). Si el dato no está en el RAG, dilo honestamente.
16. ASESOR EXPERTO PROACTIVO: Cuando un cliente describe un problema (humedad, goteras, descascaramiento), actúa como un maestro pintor con 13 años de experiencia:
    - Haz preguntas inteligentes de diagnóstico: '¿La humedad viene de afuera o de una tubería interna?', '¿Se pela la pintura o sale verdosa/mohosa?'
    - Busca con `consultar_conocimiento_tecnico` productos específicos para ese problema (ej. impermeabilizantes, selladores antihumedad)
    - Recomienda un SISTEMA COMPLETO de solución: sellador + impermeabilizante + pintura final, con pasos claros
    - Siempre ofrece vender los productos recomendados al final
17. MURO DE LA VERDAD:
    - Cuando recibas fragmentos de fichas técnicas o FDS, responde ÚNICA Y EXCLUSIVAMENTE con lo que está en el texto recuperado.
    - Si el cliente pide un dato y NO ESTÁ en el texto recuperado, TIENES PROHIBIDO inventarlo usando conocimiento general.
    - Di: 'Ese dato exacto no lo tengo en la ficha técnica base en este momento. Déjame validarlo con logística o el fabricante.'

VERIFICACIÓN DE IDENTIDAD:
- Para cartera, saldos o datos sensibles: pide cédula o NIT y usa verificar_identidad.
- Si el cliente ya está verificado (ver estado abajo), NO pidas documento de nuevo.
- NUNCA reveles cartera, saldos o datos financieros sin verificación previa.
- REGLA DE BLOQUEO: Si el cliente pidió saber cuánto debe, su saldo o su cartera y AÚN NO está verificado, NO proceses pedidos ni des información de productos hasta que pase por `verificar_identidad` con éxito. La seguridad va primero.

PORTAFOLIO VÁLIDO: Pintuco (Viniltex, Pintulux 3en1, Koraza, Doméstico, Aerocolor), Abracol, Yale, Goya, Mega y categorías reales del ERP.
No inventes marcas ni productos fuera del portafolio.

TRADUCCIÓN DE JERGA FERRETERA (usar ANTES de buscar en inventario):
- "Blanca económica", "vinilo barato", "la económica" → buscar como "Domestico Blanco"
- "P-11", "p11" → buscar como "Domestico Blanco"
- "T-11", "t11" → buscar como "Pintulux Blanco"
- "Brochitas", "pinceles", "brochas pequeñas" → buscar como "Brocha"
- "Tarritos", "tarros pequeños" → buscar como "cuarto" (0.95L / 1/4)
- "Cuñetico", "tarro grande" → buscar como "cuñete" (18.93L / 1/5)
- Diminutivos en general: quita el sufijo (-itas, -itos, -ita, -ito) y busca la palabra base.
- Si la búsqueda de un término coloquial NO devuelve resultados, intenta automáticamente con el término técnico equivalente ANTES de decirle al cliente que no hay stock.
TRADUCCIÓN OBLIGATORIA ANTES DEL TOOL CALL: Cuando el cliente pida "blanca económica" o "vinilo barato", tú DEBES enviar "Domestico Blanco" al parámetro `producto` de `consultar_inventario`. No envíes la palabra "económica" porque fallará. Traduce la jerga del cliente a lenguaje de catálogo antes de ejecutar la herramienta.

SECRETO COMERCIAL DE STOCK: ESTRICTAMENTE PROHIBIDO decirle al cliente la cantidad exacta que hay en inventario (ej. 'hay 839 disponibles'). Tú ves el número para saber si alcanza para el pedido, pero al cliente SOLO le dices: 'Sí lo tengo disponible', 'Sí nos alcanza para lo que pides', o 'Lo tengo agotado en este momento'. Jamás des números de stock.

DESAMBIGUACIÓN DE PRODUCTOS: Si el cliente pide algo muy genérico (ej. 'Pintura blanca') y la herramienta de inventario te devuelve varias opciones de marcas o líneas diferentes, oblígalo a ser específico. Pregunta: '¿Buscas pintura para interior o exterior? ¿En qué marca y presentación (galón o cuñete)?'. Cuando el cliente aclare, el sistema aprenderá automáticamente su preferencia para la próxima vez.

ORDEN COMERCIAL IMPUESTO POR BACKEND: cuando `consultar_inventario` devuelva productos, ya vienen ordenados por PostgreSQL según coincidencia, familia comercial, stock y rotación. No los reordenes por intuición ni subas una opción peor por sonar más general.

COMPUERTA DE AMBIGÜEDAD OBLIGATORIA: si `consultar_inventario` devuelve `requiere_aclaracion=true`, usa la `pregunta_desambiguacion` como base de tu respuesta y pide esa aclaración antes de avanzar. No cierres el pedido ni des un producto por confirmado mientras la compuerta siga abierta.

PROHIBIDO RENDIRSE (VENDEDOR PERSISTENTE): Si la herramienta `consultar_inventario` devuelve vacío para un código corto (ej. P-53, T-40, 17174, 13755), NUNCA digas 'no lo encontré' ni 'no tenemos ese producto'. En su lugar, haz una pregunta de diagnóstico comercial: 'Ese código no lo tengo mapeado todavía, ¿me ayudas diciéndome qué producto es? ¿Es un color específico de Viniltex, una referencia de cerradura o un abrasivo?'. Tu objetivo es que el cliente te dé una pista (ej. 'es el verde esmeralda'). Con esa pista, vuelve a buscar usando el nombre comercial.

CUADERNO DE APRENDIZAJE: Cuando el cliente te aclare qué significa un código corto o referencia interna, solo guarda ese aprendizaje si el producto quedó realmente confirmado. Si el cliente está dudando, corrigiéndose o todavía no tienes la opción exacta con referencia válida, NO guardes memoria todavía. Cuando sí quede confirmado, ejecuta `guardar_aprendizaje_producto` y continúa atendiendo sin mencionarle al cliente que lo guardaste.

ACTITUD DE APRENDIZ (ANTI-BLOQUEO): Si el cliente pide un producto con una jerga o código que la herramienta `consultar_inventario` no encuentra con exactitud pero SÍ devuelve opciones parciales, TIENES ESTRICTAMENTE PROHIBIDO decir 'no lo tengo'. En su lugar, muestra hasta 3 opciones cercanas que devolvió la base de datos y pregunta: 'No tengo mapeado ese término exacto. ¿Es alguna de estas opciones?'. Si ninguna es, pídele al cliente que te dé la referencia correcta o una mejor descripción. Si el inventario devuelve vacío sin opciones, aplica la regla de PROHIBIDO RENDIRSE o EL ESCAPE COMERCIAL según corresponda.

GRABAR EN PIEDRA (MEMORIA OBLIGATORIA): Solo cuando el cliente confirme una opción exacta (ej. 'sí, la opción 2', 'exacto, ese', o ya tienes la referencia correcta validada), ejecuta `guardar_aprendizaje_producto` antes de continuar con el pedido. En `codigo_cliente` pon la jerga original del cliente. En `descripcion_asociada` pon la referencia y nombre real ya confirmados. Nunca aprendas desde una suposición, una corrección dudosa ni una referencia improvisada.

CONFIRMACIÓN AUDITABLE: Cada vez que confirmes un producto en el chat (ya sea porque lo encontraste directo o porque el cliente te lo enseñó), DEBES mostrarlo con este formato estricto: '✅ [REFERENCIA] - DESCRIPCIÓN EXACTA DEL ERP: Disponible/Agotado'. (Ej. '✅ [5891101] - PQ VINILTEX ADV MAT BLANCO 1501 18.93L: Disponible'). Esto le permite al equipo auditar que estás asociando las referencias correctas.

BÚSQUEDA POR FRAGMENTOS NUMÉRICOS: Si el cliente envía un código numérico puro (ej. 13755, 17174), manda el número limpio a `consultar_inventario`. Si no devuelve resultados, NO digas que no existe. Pregunta: '¿Me ayudas con el nombre del producto de ese código para grabármelo en la memoria?'. Cuando responda, guarda el aprendizaje y busca por nombre.

CERO SUGERENCIAS ABSURDAS: Si el cliente busca un producto específico (ej. 'pintura para canchas') y la herramienta de inventario devuelve vacío o productos de categorías completamente distintas (ej. aerosoles de 350ml cuando piden pintura de cancha), TIENES ESTRICTAMENTE PROHIBIDO ofrecer esos productos irrelevantes. Si no hay una coincidencia lógica en la misma categoría, asume que la búsqueda fue infructuosa.

EL ESCAPE COMERCIAL (PÁGINA WEB): Cuando la herramienta de inventario no encuentre el producto solicitado o solo devuelva resultados irrelevantes, NO inventes nombres ni ofrezcas cosas al azar para rellenar. Aplica esta respuesta adaptada a tu tono: 'No logro ubicar un producto con esa descripción exacta por acá. ¿De pronto tienes la referencia o un nombre más preciso? Si no tienes el dato a la mano, te invito a consultar nuestro catálogo en www.ferreinox.co. Allí seguro encuentras el producto exacto que buscas y me confirmas para armar el pedido.'.

CÓDIGOS FRACCIONARIOS: En esta ferretería, los clientes piden usando la estructura 'Cantidad/Presentación'.
- El sufijo '/1' significa GALÓN. (Ej. '4/1 p-11' = 4 galones de P-11).
- El sufijo '/4' significa CUARTO. (Ej. '6/4 pintulux naranja' = 6 cuartos de Pintulux Naranja).
- El sufijo '/5' significa CUÑETE o CANECA. (Ej. '3/5 de 27155' = 3 cuñetes de la referencia 27155).
Cuando veas esta nomenclatura, DEBES entender la cantidad y presentación solicitadas antes de usar la herramienta de inventario. Busca el producto por su nombre y luego filtra mentalmente la presentación correcta.

DESCARTAR BASURA DEL JSON (FILTRO DE PRESENTACIONES): Si el cliente pidió un 'cuarto' (ej. 6/4), y la herramienta de inventario te devuelve un JSON que incluye el cuarto, el galón y el tambor de 50 galones, TIENES ESTRICTAMENTE PROHIBIDO mencionar el galón y el tambor en tu respuesta. Filtra mentalmente el JSON y confírmale al cliente ÚNICAMENTE la presentación que solicitó. Si la presentación específica que pidió no aparece en el JSON, dile amablemente que esa presentación puntual no la tenemos disponible, y ofrécele las que sí hay en presentaciones lógicas (cuñete, galón o cuarto).

FILTRO FRACCIONARIO OBLIGATORIO: Si el cliente pide una presentación específica usando fracciones (ej. '/4' = cuarto, '/1' = galón, '/5' = cuñete) y la herramienta te devuelve múltiples tamaños del mismo producto, TIENES ESTRICTAMENTE PROHIBIDO mostrarle al cliente los tamaños que no pidió. Filtra mentalmente el JSON. Si pidió cuartos, confírmale SOLO los cuartos. Muestra otros tamaños SOLO si el solicitado está agotado.

PROCESAMIENTO LÍNEA POR LÍNEA (BULK ORDERS): Si el cliente te envía una lista de varios productos (ej. 5 líneas), debes confirmar exactamente esos productos con las cantidades y presentaciones solicitadas. NO agregues productos adicionales que la base de datos haya devuelto por coincidencia difusa, ni omitas los que el cliente pidió. Cada línea del pedido se procesa independientemente.

CANDADO DE CHECKOUT: Tienes ESTRICTAMENTE PROHIBIDO agregar un producto al resumen final del pedido si no lo has buscado antes con `consultar_inventario` y no tienes su [REFERENCIA] exacta. Si el cliente pide algo que no encuentras (ej. 'pintura para canchas'), no lo anotes en el pedido. Dile que no lo encuentras y pídele la referencia. NUNCA digas 'no puedo verificar el inventario directamente'.

PEDIDOS Y COTIZACIONES:
- Cuando el cliente pide productos, usa consultar_inventario para CADA producto mencionado.
- Presenta resultados en lenguaje natural: nombre comercial, presentación, disponibilidad y precio si hay.
- Si el cliente menciona múltiples productos separados por comas o "y", busca CADA UNO por separado.
- Siempre incluye TODOS los productos que el cliente pidió, nunca dejes ninguno por fuera.
- Si un producto no se encuentra, informa y sugiere alternativas.

DOCUMENTOS: Si te piden ficha técnica u hoja de seguridad, USA LA HERRAMIENTA `buscar_documento_tecnico` inmediatamente. No digas que no puedes hacerlo.
DOCUMENTOS MÚLTIPLES: Si la herramienta `buscar_documento_tecnico` te devuelve 'multiples_opciones', NO digas que no lo encontraste. Muéstrale al cliente una lista corta y amable con las opciones y pregúntale: 'Tengo estas versiones, ¿cuál de estas fichas necesitas exactamente?'.

ASESORÍA TÉCNICA INTELIGENTE (MODELO HÍBRIDO RAG):
- PASO 1 — DIAGNÓSTICO PRIMERO: Si el cliente trae un problema amplio (ej. 'tengo humedad', 'quiero proteger un metal', 'necesito pintar madera'), primero diagnostica con máximo 2 preguntas clave por turno hasta identificar la necesidad exacta. No busques en RAG todavía.
- PASO 2 — CONSULTA OBLIGATORIA: Solo cuando ya tengas la necesidad exacta diagnosticada o un producto/sistema identificado, usa `consultar_conocimiento_tecnico`. No busques términos genéricos; busca exactamente el problema diagnosticado o la referencia del producto correcto.
- PASO 3 — EXTRACCIÓN DE DATOS REALES: Lee 'respuesta_rag' y extrae los DATOS CONCRETOS: nombres de productos, códigos, proporciones exactas, tiempos exactos, temperaturas, rendimientos y pasos de aplicación. NUNCA digas frases vagas. Si el dato no está literal o claramente sustentado en el texto recuperado, no lo inventes.
- PASO 4 — RESPALDO PDF: Después del dato técnico, invoca `buscar_documento_tecnico` para enviar el PDF. Di: 'Te envío la ficha técnica oficial como respaldo.'
- EXCEPCIÓN: Si `consultar_conocimiento_tecnico` devuelve encontrado=false, usa `buscar_documento_tecnico` para enviar el PDF y dile al cliente que revise la ficha.
- REGLA DE ORO: Si el RAG te devuelve información, tu respuesta DEBE contener al menos un dato específico extraído de 'respuesta_rag' (un nombre, un número, una proporción, un tiempo). Si no encuentras el dato específico en el RAG, di honestamente: 'En la ficha que tengo no aparece ese dato exacto, pero te la envío para que la revises.'

PRODUCTOS COMPLEMENTARIOS (CATALIZADORES, DILUYENTES, BASES):
- Si `consultar_inventario` devuelve un campo `productos_complementarios` en algún producto, DEBES informar al cliente de forma proactiva. Ejemplo: 'Este producto necesita catalizador EGA247 y diluyente Ajustador 21209.'
- Si un experto o asesor interno (ej. Pablo Mafla) te enseña que un producto requiere un catalizador, diluyente, base, sellador o imprimante, guarda esa relación usando `guardar_producto_complementario`.
- NUNCA ignores los productos complementarios. Son críticos para que el cliente aplique el producto correctamente.
- Cuando cierres un pedido que incluya productos con complementarios, recuérdale al cliente si no los ha incluido en el pedido.

MEMORIA DE LISTAS: Si le mostraste al cliente una lista numerada de opciones (ya sean documentos, productos o cualquier cosa) y el cliente responde con un número (ej. '1', 'el 5', 'la segunda') o una afirmación ('sí', 'esa', 'la primera'), TIENES ESTRICTAMENTE PROHIBIDO pasarle ese número o 'sí' a las herramientas. DEBES buscar en tu memoria de conversación el nombre exacto de la opción que corresponde a ese número, y ejecutar la herramienta usando el NOMBRE COMPLETO EXACTO (ej. 'KORAZA ELASTOMÉRICA.pdf' o 'Domestico Blanco cuñete'). Nunca envíes '1', '2', 'sí' ni 'esa' como parámetro de búsqueda.

CIERRE DE PEDIDO: Una vez el cliente confirme el resumen de productos, pregúntale a nombre de quién va el despacho y si quiere el soporte por WhatsApp o al correo. Cuando tengas esos datos, ejecuta la herramienta `confirmar_pedido_y_generar_pdf`.

PROTOCOLO ESTRICTO PARA RECLAMOS Y GARANTÍAS:
Paso 1: Identidad. Si no tienes la cédula/NIT del cliente, usa `verificar_identidad`. Si ya está verificado, continúa.
Paso 2: Verificación de Compra. Usa `consultar_compras` para confirmar si el cliente realmente compró el producto reclamado recientemente. Si no aparece, díselo con tacto y ofrece alternativas.
Paso 3: Indagación y Asesoría Técnica (¡VITAL!). NO abras el reclamo inmediatamente. Si un cliente reporta que una pintura 'salió mala', 'parece agua' o 'no cubre', NO le pidas el correo inmediatamente para radicar. Actúa como el experto ferretero que eres: pregúntale de forma conversacional cómo preparó la pared (selló, lijó, aplicó fondo), con qué diluyó el producto y cuántas manos aplicó. Usa sus respuestas para intentar explicarle qué pudo pasar ANTES de radicar. Si definitivamente es garantía o defecto, ahí sí recopila la info.
- IMPORTANTE: Si el cliente dice que la pintura está aguada, no cubre o se descascara, NO le ofrezcas comprar más pintura. Primero cumple este Paso 3 completo: pregunta preparación de superficie, dilución y manos. Eres el experto, actúa como tal.
Paso 4: Radicación. Si el problema persiste o es un defecto de fábrica claro, pide una foto (o número de lote) y el correo electrónico del cliente. SOLO ENTONCES ejecuta la herramienta `radicar_reclamo`. Nunca cortes la conversación sin darle un cierre amable al cliente con su número de radicado.

ESTADO ACTUAL DE LA CONVERSACIÓN:
- Cliente verificado: {verificado}
- Código cliente: {cliente_codigo}
- Nombre cliente: {nombre_cliente}
- Borrador comercial activo: {borrador_activo}
- Reclamo activo: {reclamo_activo}

Si no tienes un dato seguro, dilo honestamente y ofrece el siguiente paso. Nunca inventes saldos, fechas o datos."""


AGENT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "consultar_inventario",
            "description": "Busca disponibilidad y precios de productos en el inventario de Ferreinox. "
            "Usa esta herramienta cuando el cliente pregunte por un producto específico, quiera hacer un pedido, "
            "cotización, o necesite verificar stock. NO la uses para intenciones genéricas como 'quiero hacer un pedido'. "
            "IMPORTANTE: Antes de llamar, limpia el término de búsqueda: quita diminutivos (brochitas→brocha, tarritos→tarro), "
            "traduce jerga (blanca económica→Domestico Blanco, P-11→Domestico Blanco, T-11→Pintulux Blanco, pinceles→brocha). "
            "Si la primera búsqueda no devuelve resultados, intenta con el sinónimo técnico.",
            "parameters": {
                "type": "object",
                "properties": {
                    "producto": {
                        "type": "string",
                        "description": "Nombre, descripción o código del producto a buscar. Ej: 'viniltex blanco cuñete', 'koraza rojo', 'cerradura yale'",
                    }
                },
                "required": ["producto"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "verificar_identidad",
            "description": "Verifica la identidad de un cliente por su número de cédula, NIT o nombre completo. "
            "Usa esta herramienta cuando el cliente proporcione voluntariamente un documento o diga su nombre para identificarse.",
            "parameters": {
                "type": "object",
                "properties": {
                    "criterio_busqueda": {
                        "type": "string",
                        "description": "Número de cédula/NIT (solo dígitos) o nombre completo del cliente.",
                    }
                },
                "required": ["criterio_busqueda"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "consultar_cartera",
            "description": "Consulta el estado de cartera (saldos pendientes, documentos vencidos) del cliente verificado. "
            "Solo funciona si el cliente ya está verificado.",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "consultar_compras",
            "description": "Consulta el historial de compras recientes del cliente verificado. "
            "Solo funciona si el cliente ya está verificado.",
            "parameters": {
                "type": "object",
                "properties": {
                    "periodo": {
                        "type": "string",
                        "description": "Periodo a consultar, ej: 'enero 2024', 'últimos 3 meses'. Por defecto últimos 12 meses.",
                    }
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "buscar_documento_tecnico",
            "description": "Busca y envía fichas técnicas u hojas de seguridad de productos. "
            "Úsala cuando el cliente pida ficha técnica, hoja de seguridad, FDS o información técnica de un producto. "
            "IMPORTANTE: Si el cliente seleccionó una opción de una lista previa (ej. respondió '1' o 'la segunda'), "
            "OBLIGATORIAMENTE debes enviar el nombre completo y exacto del archivo (incluyendo .pdf si lo tiene) "
            "en el parámetro `termino_busqueda`. NUNCA envíes un número o 'sí' como término de búsqueda.",
            "parameters": {
                "type": "object",
                "properties": {
                    "termino_busqueda": {
                        "type": "string",
                        "description": "Nombre del producto para buscar su ficha técnica. Ej: 'viniltex', 'koraza', 'pintulux'.",
                    },
                    "es_hoja_de_seguridad": {
                        "type": "boolean",
                        "description": "True si el cliente pide hoja de seguridad (FDS/MSDS), False si pide ficha técnica.",
                    },
                    "es_seleccion_final": {
                        "type": "boolean",
                        "description": "Envíalo en true ÚNICAMENTE cuando el cliente eligió una opción exacta de una lista previa "
                        "que tú le mostraste. En ese caso, termino_busqueda DEBE ser el nombre completo del archivo seleccionado.",
                    }
                },
                "required": ["termino_busqueda"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "consultar_conocimiento_tecnico",
            "description": "Busca información técnica detallada en las fichas técnicas vectorizadas (RAG). "
            "Úsala ANTES de responder preguntas técnicas como: tiempos de secado, relación de mezcla, "
            "preparación de superficie, rendimiento, temperatura de aplicación, número de manos, dilución, etc. "
            "Esta herramienta lee el contenido real de las fichas técnicas y te da la respuesta precisa. "
            "Después de usarla, SIEMPRE envía el PDF con `buscar_documento_tecnico` como respaldo oficial.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pregunta": {
                        "type": "string",
                        "description": "La pregunta técnica específica. Ej: '¿Cuál es el tiempo de secado del Viniltex?', "
                        "'¿Cómo se prepara la superficie para Koraza?', '¿Cuál es la relación de mezcla del Interseal 670?'",
                    },
                    "producto": {
                        "type": "string",
                        "description": "Nombre del producto sobre el que se pregunta. Ej: 'Viniltex', 'Koraza', 'Interseal 670'.",
                    },
                    "marca": {
                        "type": "string",
                        "description": "Filtro opcional de marca para acotar resultados. Ej: 'Pintuco', 'International'.",
                    },
                },
                "required": ["pregunta"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "radicar_reclamo",
            "description": "ESTRICTAMENTE PROHIBIDO llamar a esta herramienta de inmediato. "
            "Úsala ÚNICAMENTE DESPUÉS de haber actuado como asesor técnico: debes haberle hecho al menos 1 o 2 preguntas al cliente "
            "sobre cómo aplicó el producto (dilución, preparación de la superficie, herramientas usadas) Y el cliente debe haberte respondido. "
            "Solo cuando tengas ese diagnóstico técnico claro, además del producto, la falla y el correo, puedes ejecutar esta herramienta.",
            "parameters": {
                "type": "object",
                "properties": {
                    "producto_reclamado": {
                        "type": "string",
                        "description": "Nombre del producto con el que tiene el problema. Ej: 'Viniltex Blanco en galón'.",
                    },
                    "descripcion_problema": {
                        "type": "string",
                        "description": "Resumen claro del problema reportado por el cliente.",
                    },
                    "diagnostico_previo": {
                        "type": "string",
                        "description": "Resumen de la indagación técnica: qué le preguntaste al cliente sobre la aplicación y qué te respondió (preparación, dilución, manos, herramientas).",
                    },
                    "correo_cliente": {
                        "type": "string",
                        "description": "Correo electrónico del cliente para enviarle la constancia del radicado.",
                    },
                    "evidencia": {
                        "type": "string",
                        "description": "Descripción de la evidencia proporcionada: número de lote, foto enviada, etc. Si no hay, indicar 'Pendiente'.",
                    }
                },
                "required": ["producto_reclamado", "descripcion_problema", "diagnostico_previo", "correo_cliente"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "confirmar_pedido_y_generar_pdf",
            "description": "Úsala SOLO cuando el cliente apruebe el resumen final. "
            "DEBES pasarle el array exacto de productos. "
            "ESTRICTAMENTE PROHIBIDO incluir en el array un producto que no tenga una [REFERENCIA] confirmada previamente por la herramienta de inventario.",
            "parameters": {
                "type": "object",
                "properties": {
                    "nombre_despacho": {
                        "type": "string",
                        "description": "Nombre de la persona o empresa a cuyo nombre va el despacho.",
                    },
                    "canal_envio": {
                        "type": "string",
                        "enum": ["whatsapp", "email"],
                        "description": "Canal por el cual enviar el PDF: 'whatsapp' o 'email'.",
                    },
                    "correo_cliente": {
                        "type": "string",
                        "description": "Correo electrónico del cliente. Requerido solo si canal_envio es 'email'.",
                    },
                    "items_pedido": {
                        "type": "array",
                        "description": "Array con TODOS los productos del pedido. Cada producto DEBE tener la referencia exacta obtenida de consultar_inventario.",
                        "items": {
                            "type": "object",
                            "properties": {
                                "referencia": {
                                    "type": "string",
                                    "description": "Código de referencia EXACTO devuelto por la herramienta de inventario. PROHIBIDO inventar o aproximar.",
                                },
                                "descripcion_comercial": {
                                    "type": "string",
                                    "description": "Nombre comercial del producto tal como se lo confirmaste al cliente.",
                                },
                                "cantidad": {
                                    "type": "number",
                                    "description": "Cantidad solicitada por el cliente.",
                                }
                            },
                            "required": ["referencia", "descripcion_comercial", "cantidad"],
                        },
                    }
                },
                "required": ["nombre_despacho", "canal_envio", "items_pedido"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "guardar_aprendizaje_producto",
            "description": "Guarda en la memoria permanente del sistema la asociación entre una jerga o código corto del cliente "
            "y un producto real ya confirmado. Úsala solo cuando la conversación ya dejó clara la referencia y el producto exactos. "
            "Si el cliente sigue dudando, se está corrigiendo o la referencia no quedó validada, no la uses todavía.",
            "parameters": {
                "type": "object",
                "properties": {
                    "codigo_cliente": {
                        "type": "string",
                        "description": "El código corto o referencia interna que usa el cliente. Ej: 'P-53', 'T-40', '13755', '17174'.",
                    },
                    "descripcion_asociada": {
                        "type": "string",
                        "description": "La opción exacta ya confirmada por el cliente, idealmente con referencia y nombre comercial. Ej: '5891101 Viniltex Verde Esmeralda cuñete', '170123 Cerradura Yale 170'.",
                    }
                },
                "required": ["codigo_cliente", "descripcion_asociada"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "guardar_producto_complementario",
            "description": "Guarda la relación entre un producto principal y un producto complementario (catalizador, diluyente, base, sellador, imprimante, acabado, complemento). "
            "Úsala cuando un experto o asesor te enseñe que un producto necesita otro para funcionar correctamente. "
            "Ejemplo: Interseal 670 necesita catalizador EGA247 (ref 5891355) y diluyente Ajustador 21209.",
            "parameters": {
                "type": "object",
                "properties": {
                    "producto_referencia": {
                        "type": "string",
                        "description": "La referencia del producto principal. Ej: '5890737', 'INT670'.",
                    },
                    "producto_descripcion": {
                        "type": "string",
                        "description": "Nombre o descripción del producto principal. Ej: 'Interseal 670 Gris'.",
                    },
                    "companion_referencia": {
                        "type": "string",
                        "description": "La referencia del producto complementario. Ej: '5891355'.",
                    },
                    "companion_descripcion": {
                        "type": "string",
                        "description": "Nombre o descripción del producto complementario. Ej: 'Interseal 670 Hs EGA 247 Galón'.",
                    },
                    "tipo_relacion": {
                        "type": "string",
                        "enum": ["catalizador", "diluyente", "base", "complemento", "sellador", "imprimante", "acabado"],
                        "description": "Tipo de relación: catalizador, diluyente, base, complemento, sellador, imprimante o acabado.",
                    },
                    "proporcion": {
                        "type": "string",
                        "description": "Proporción de mezcla o uso. Ej: '10%', '1:1', '2 partes base + 1 catalizador'.",
                    },
                    "notas": {
                        "type": "string",
                        "description": "Notas adicionales sobre la relación. Ej: 'Para sistemas epóxicos marinos'.",
                    },
                },
                "required": ["producto_referencia", "companion_referencia", "tipo_relacion"],
            },
        },
    },
]


def _handle_tool_consultar_inventario(args, conversation_context):
    producto = args.get("producto", "")
    product_request = build_followup_inventory_request(
        producto,
        prepare_product_request_for_search(producto),
        conversation_context,
    )
    rows = lookup_product_context(producto, product_request)
    requested_store_codes = product_request.get("store_filters") or []
    requested_store_code = requested_store_codes[0] if len(requested_store_codes) == 1 else None
    if not rows and product_request.get("followup_from_previous_product"):
        rows = filter_previous_product_context(conversation_context, product_request)
    if not rows:
        return json.dumps(
            {
                "encontrados": 0,
                "mensaje": "No se encontraron productos con esa descripción.",
                "nlu_extraccion": product_request.get("nlu_extraction") or {},
                "estrategia_ranking": "catalogo_curado_postgresql",
                "requiere_aclaracion": False,
            },
            ensure_ascii=False,
        )
    results = []
    for row in rows[:5]:
        item = {
            "codigo": row.get("codigo_articulo") or row.get("referencia") or row.get("codigo"),
            "descripcion": get_exact_product_description(row),
            "descripcion_exacta": get_exact_product_description(row),
            "etiqueta_auditable": build_product_audit_label(row),
            "marca": row.get("marca") or row.get("marca_producto"),
            "presentacion": infer_product_presentation_from_row(row),
            "familia_consulta": row.get("familia_consulta"),
            "producto_padre_busqueda": row.get("producto_padre_busqueda"),
            "pregunta_desambiguacion": row.get("pregunta_desambiguacion"),
        }
        stock = parse_numeric_value(row.get("stock_total"))
        if stock is not None:
            item["stock_total"] = stock
        requested_store_stock = row.get("stock_en_tienda_solicitada")
        if requested_store_stock is None and requested_store_code:
            requested_store_stock = extract_store_stock_from_summary(row.get("stock_por_tienda"), requested_store_code)
        if requested_store_stock is not None:
            item["stock_tienda_solicitada"] = requested_store_stock
            item["disponible_tienda_solicitada"] = requested_store_stock > 0
        if requested_store_code:
            item["visibilidad_tienda_exacta"] = bool(row.get("visibilidad_tienda_exacta") or requested_store_stock is not None)
            item["tienda_solicitada"] = STORE_CODE_LABELS.get(requested_store_code) or requested_store_code
        stock_189 = parse_numeric_value(row.get("stock_189"))
        if stock_189 is not None:
            item["stock_pereira"] = stock_189
        precio = row.get("precio_venta")
        if precio is not None:
            item["precio"] = precio
        # --- Companion/complementary products ---
        ref_for_companion = item.get("codigo") or ""
        companions = fetch_product_companions(ref_for_companion)
        if companions:
            item["productos_complementarios"] = [
                {
                    "referencia": c.get("companion_referencia"),
                    "descripcion": c.get("companion_descripcion") or c.get("descripcion_inventario"),
                    "tipo": c.get("tipo_relacion"),
                    "proporcion": c.get("proporcion"),
                    "notas": c.get("notas"),
                    "stock_total": c.get("stock_total"),
                }
                for c in companions
            ]
        results.append(item)
    if rows:
        conversation_context["last_product_request"] = product_request
        conversation_context["last_product_query"] = producto
        conversation_context["last_product_context"] = results[:5]
    clarification_required = should_ask_product_clarification(product_request, rows)
    clarification_question = build_best_product_clarification_question(product_request, rows) if clarification_required else None
    return json.dumps(
        {
            "encontrados": len(results),
            "productos": results,
            "seguimiento_producto_previo": bool(product_request.get("followup_from_previous_product")),
            "nlu_extraccion": product_request.get("nlu_extraction") or {},
            "estrategia_ranking": "catalogo_curado_postgresql",
            "requiere_aclaracion": clarification_required,
            "pregunta_desambiguacion": clarification_question,
            "mensaje": (
                "Se recuperó el producto del mensaje anterior para resolver este seguimiento."
                if product_request.get("followup_from_previous_product") else None
            ),
        },
        ensure_ascii=False,
        default=str,
    )


def _handle_tool_verificar_identidad(args, context, conversation_context):
    criterio = args.get("criterio_busqueda", "").strip()
    if not criterio:
        return json.dumps({"verificado": False, "mensaje": "No se proporcionó criterio de búsqueda."}, ensure_ascii=False)

    is_numeric = bool(re.fullmatch(r"[\d\-\.]+", criterio.replace(" ", "")))

    verified_context = None
    verified_by = None

    if is_numeric:
        identity_candidate = {"type": "document", "value": criterio}
        try:
            verified_context, verified_by = resolve_identity_candidate(
                identity_candidate, context.get("telefono_e164", "")
            )
        except Exception:
            verified_context, verified_by = None, None
    else:
        try:
            name_result = find_cliente_contexto_by_name(criterio)
            if name_result:
                verified_context = name_result
                verified_by = "name"
        except Exception:
            verified_context, verified_by = None, None

    if verified_context:
        cliente_codigo = verified_context.get("cliente_codigo")
        try:
            cliente_id = update_contact_cliente(context["contact_id"], cliente_codigo)
            context["cliente_id"] = cliente_id
        except Exception:
            pass
        update_conversation_context(
            context["conversation_id"],
            {
                "verified": True,
                "verified_document": criterio if is_numeric else None,
                "verified_by": verified_by,
                "verified_cliente_codigo": cliente_codigo,
                "awaiting_verification": False,
                "awaiting_name_confirmation": False,
            },
        )
        conversation_context.update(
            {
                "verified": True,
                "verified_document": criterio if is_numeric else None,
                "verified_by": verified_by,
                "verified_cliente_codigo": cliente_codigo,
            }
        )
        return json.dumps(
            {
                "verificado": True,
                "nombre_cliente": verified_context.get("nombre_cliente"),
                "cliente_codigo": cliente_codigo,
                "ciudad": verified_context.get("ciudad"),
                "nit": verified_context.get("nit"),
            },
            ensure_ascii=False,
            default=str,
        )
    else:
        tipo = "documento" if is_numeric else "nombre"
        return json.dumps(
            {
                "verificado": False,
                "mensaje": f"No se encontró un cliente con ese {tipo}: {criterio}. "
                "Puede estar incorrecto o no estar registrado.",
            },
            ensure_ascii=False,
        )


def _handle_tool_consultar_cartera(conversation_context):
    cliente_codigo = conversation_context.get("verified_cliente_codigo")
    if not cliente_codigo:
        return json.dumps(
            {"error": "Cliente no verificado. Pide la cédula o NIT primero."},
            ensure_ascii=False,
        )

    result = {}
    try:
        contexto = get_cliente_contexto(cliente_codigo)
        result["nombre_cliente"] = contexto.get("nombre_cliente")
        result["saldo_cartera"] = contexto.get("saldo_cartera")
    except Exception:
        pass

    try:
        overdue = fetch_overdue_documents(cliente_codigo)
        if overdue:
            totals = overdue.get("totals", {})
            result["documentos_vencidos"] = totals.get("documentos_vencidos", 0)
            result["saldo_vencido"] = totals.get("saldo_vencido", 0)
            result["max_dias_vencido"] = totals.get("max_dias_vencido", 0)
            if overdue.get("documents"):
                result["detalle_documentos"] = overdue["documents"][:5]
    except Exception:
        pass

    if not result:
        return json.dumps({"error": "No se pudo consultar la cartera."}, ensure_ascii=False)
    return json.dumps(result, ensure_ascii=False, default=str)


def _handle_tool_consultar_compras(args, conversation_context):
    cliente_codigo = conversation_context.get("verified_cliente_codigo")
    if not cliente_codigo:
        return json.dumps(
            {"error": "Cliente no verificado. Pide la cédula o NIT primero."},
            ensure_ascii=False,
        )

    periodo = args.get("periodo", "")
    purchase_query = extract_purchase_query(periodo) if periodo else {}

    if purchase_query.get("wants_last_purchase"):
        summary = fetch_latest_purchase_detail(cliente_codigo)
    else:
        summary = fetch_purchase_summary(
            cliente_codigo,
            purchase_query.get("start_date"),
            purchase_query.get("end_date"),
        )

    if not summary:
        return json.dumps(
            {"encontrados": 0, "mensaje": "No se encontraron compras en ese periodo."},
            ensure_ascii=False,
        )
    return json.dumps(summary, ensure_ascii=False, default=str)


def _send_document_and_respond(doc, context):
    """Helper: send a single document via WhatsApp and return success JSON."""
    filename = doc.get("name") or "documento.pdf"
    path_lower = doc.get("path_lower")
    try:
        temporary_link = get_dropbox_temporary_link(path_lower)
        send_whatsapp_document_message(
            context["telefono_e164"],
            temporary_link,
            filename,
            caption=f"Aquí tienes: {filename}",
        )
        store_outbound_message(
            context["conversation_id"],
            None,
            "document",
            f"Documento técnico enviado: {filename}",
            {"filename": filename, "path": path_lower},
            intent_detectado="consulta_documentacion",
        )
        return json.dumps(
            {"status": "exito", "encontrado": True, "enviado": True, "archivo": filename,
             "mensaje": f"El archivo '{filename}' fue enviado exitosamente por WhatsApp."},
            ensure_ascii=False,
        )
    except Exception as exc:
        return json.dumps(
            {"encontrado": True, "enviado": False, "archivo": filename,
             "mensaje": f"Encontré el archivo '{filename}' pero no pude enviarlo: {exc}"},
            ensure_ascii=False,
        )


def _handle_tool_buscar_documento_tecnico(args, context, conversation_context):
    termino = args.get("termino_busqueda", "")
    es_hds = args.get("es_hoja_de_seguridad", False)
    es_seleccion_final = args.get("es_seleccion_final", False)
    if not termino:
        return json.dumps({"encontrado": False, "mensaje": "No se indicó qué producto buscar."}, ensure_ascii=False)

    product_request = extract_product_request(termino)
    document_request = extract_technical_document_request(
        termino, product_request, conversation_context
    )
    if es_hds:
        document_request["wants_safety_sheet"] = True
        document_request["wants_technical_sheet"] = False
    else:
        document_request["wants_technical_sheet"] = True

    documents = search_technical_documents(document_request)
    if not documents:
        return json.dumps(
            {"encontrado": False, "mensaje": f"No encontré documentos técnicos para '{termino}'."}, ensure_ascii=False
        )

    # --- Exact match: if termino matches a filename exactly, send it immediately ---
    termino_lower = termino.lower().strip()
    for doc in documents:
        doc_name = (doc.get("name") or "").lower().strip()
        if doc_name == termino_lower or doc_name == termino_lower + ".pdf":
            return _send_document_and_respond(doc, context)

    # --- Final selection mode: client already chose, force-send best match ---
    if es_seleccion_final:
        return _send_document_and_respond(documents[0], context)

    # --- Multiple results: ask client to choose ---
    if len(documents) > 1:
        opciones = [d.get("name", "documento.pdf") for d in documents]
        return json.dumps(
            {"status": "multiples_opciones", "opciones": opciones,
             "mensaje": f"Se encontraron {len(opciones)} documentos para '{termino}'. Pregúntale al cliente cuál necesita."},
            ensure_ascii=False,
        )

    # --- Single result: send directly ---
    return _send_document_and_respond(documents[0], context)


def _handle_tool_radicar_reclamo(args, context, conversation_context):
    producto_reclamado = args.get("producto_reclamado", "")
    descripcion_problema = args.get("descripcion_problema", "")
    diagnostico_previo = args.get("diagnostico_previo", "")
    correo_cliente = args.get("correo_cliente", "")
    evidencia = args.get("evidencia", "Pendiente")

    existing_claim = dict(conversation_context.get("claim_case") or {})
    existing_product = normalize_text_value(existing_claim.get("product_label"))
    incoming_product = normalize_text_value(producto_reclamado)
    if existing_claim.get("submitted") and existing_product and incoming_product and existing_product == incoming_product:
        return json.dumps(
            {
                "status": "ya_radicado",
                "numero_caso": existing_claim.get("case_reference") or f"CRM-{context['conversation_id']}",
                "producto": producto_reclamado,
                "mensaje": "Ese reclamo ya estaba radicado en esta conversación. No lo reenvié para evitar duplicados.",
            },
            ensure_ascii=False,
        )

    if not producto_reclamado or not descripcion_problema:
        return json.dumps(
            {"status": "error", "mensaje": "Faltan datos: producto y descripción del problema son requeridos."},
            ensure_ascii=False,
        )

    conversation_id = context["conversation_id"]
    numero_caso = f"CRM-{conversation_id}"

    verified_cliente = conversation_context.get("verified_cliente_codigo")
    cliente_contexto = None
    if verified_cliente:
        try:
            cliente_contexto = get_cliente_contexto(verified_cliente)
        except Exception:
            pass

    recent_messages = load_recent_conversation_messages(conversation_id)

    claim_detail = {
        "product_label": producto_reclamado,
        "issue_summary": descripcion_problema,
        "diagnostico_previo": diagnostico_previo,
        "evidence_note": evidencia,
        "contact_email": correo_cliente,
        "case_reference": numero_caso,
        "store_name": (cliente_contexto or {}).get("ciudad") or "Pendiente",
    }

    # Save claim case in conversation context
    update_conversation_context(
        conversation_id,
        {
            "claim_case": {
                "submitted": True,
                "case_reference": numero_caso,
                "product_label": producto_reclamado,
                "issue_summary": descripcion_problema,
                "contact_email": correo_cliente,
            },
        },
    )
    conversation_context["claim_case"] = claim_detail

    # Create agent task for tracking
    try:
        upsert_agent_task(
            conversation_id,
            context.get("cliente_id"),
            "reclamo_servicio",
            f"Reclamo radicado: {producto_reclamado}",
            claim_detail,
            "alta",
        )
    except Exception:
        pass

    correos_enviados = []

    # 1. Internal email to claims department
    try:
        internal_payload = build_operational_email_payload(
            "reclamos",
            context.get("nombre_visible"),
            cliente_contexto,
            claim_detail,
            recent_messages,
        )
        if internal_payload:
            send_sendgrid_email(
                internal_payload["to_email"],
                internal_payload["subject"],
                internal_payload["html_content"],
                internal_payload["text_content"],
                reply_to=correo_cliente,
            )
            correos_enviados.append(f"Área técnica ({internal_payload['to_email']})")
            store_outbound_message(
                conversation_id, None, "system",
                f"Correo reclamo interno enviado a {internal_payload['to_email']}",
                {"email_to": internal_payload["to_email"], "case": numero_caso},
                intent_detectado="correo_reclamo_interno",
            )
    except Exception as exc:
        store_outbound_message(
            conversation_id, None, "system",
            f"Error enviando correo interno de reclamo: {exc}",
            {"error": str(exc)},
            intent_detectado="correo_reclamo_interno_error",
        )

    # 2. Confirmation email to customer
    if correo_cliente:
        try:
            customer_payload = build_customer_claim_confirmation_email(
                conversation_id,
                context.get("nombre_visible"),
                cliente_contexto,
                claim_detail,
            )
            if customer_payload:
                send_sendgrid_email(
                    customer_payload["to_email"],
                    customer_payload["subject"],
                    customer_payload["html_content"],
                    customer_payload["text_content"],
                )
                correos_enviados.append(f"Cliente ({correo_cliente})")
                store_outbound_message(
                    conversation_id, None, "system",
                    f"Correo constancia reclamo enviado a {correo_cliente}",
                    {"email_to": correo_cliente, "case": numero_caso},
                    intent_detectado="correo_reclamo_cliente",
                )
        except Exception as exc:
            store_outbound_message(
                conversation_id, None, "system",
                f"Error enviando constancia al cliente: {exc}",
                {"error": str(exc)},
                intent_detectado="correo_reclamo_cliente_error",
            )

    return json.dumps(
        {
            "status": "exito",
            "numero_caso": numero_caso,
            "producto": producto_reclamado,
            "correos_enviados": correos_enviados,
            "mensaje": f"Reclamo radicado exitosamente con número {numero_caso}. "
            f"Correos enviados a: {', '.join(correos_enviados) if correos_enviados else 'ninguno (verificar configuración SendGrid)'}.",
        },
        ensure_ascii=False,
    )


def _handle_tool_confirmar_pedido(args, context, conversation_context):
    nombre_despacho = args.get("nombre_despacho", "")
    canal_envio = args.get("canal_envio", "whatsapp")
    correo_cliente = args.get("correo_cliente", "")
    items_pedido = args.get("items_pedido") or []
    internal_auth = dict(conversation_context.get("internal_auth") or {})
    internal_user = resolve_internal_session(internal_auth.get("token")) if internal_auth.get("token") else None

    # --- Validación: el LLM DEBE mandar items_pedido con referencias válidas ---
    if not items_pedido:
        return json.dumps(
            {"exito": False, "mensaje": "No enviaste el array de productos (items_pedido). Vuelve a llamar la herramienta incluyendo los productos."},
            ensure_ascii=False,
        )

    productos_sin_ref = [
        it.get("descripcion_comercial", "Producto desconocido")
        for it in items_pedido
        if not (it.get("referencia") or "").strip()
    ]
    if productos_sin_ref:
        nombres = ", ".join(productos_sin_ref)
        return json.dumps(
            {"exito": False, "mensaje": f"Error: No puedes facturar productos sin código. Los siguientes no tienen referencia: {nombres}. Pide al cliente que aclare el producto."},
            ensure_ascii=False,
        )

    # Construir el commercial_draft a partir de lo que manda el LLM
    commercial_draft = dict(conversation_context.get("commercial_draft") or {})
    store_filters = infer_confirmed_order_store_filters(commercial_draft, context, conversation_context, internal_user)
    customer_identity_input = (
        commercial_draft.get("customer_identity_input")
        or commercial_draft.get("destinatario")
        or nombre_despacho
        or ""
    ).strip()
    customer_context = dict(commercial_draft.get("customer_context") or {})
    customer_resolution_status = commercial_draft.get("customer_resolution_status")
    if customer_identity_input and not customer_context:
        resolved_customer_context, _ = resolve_commercial_customer_context(customer_identity_input)
        if resolved_customer_context:
            customer_context = resolved_customer_context
            customer_resolution_status = "resolved"
        else:
            return json.dumps(
                {
                    "exito": False,
                    "mensaje": f"Antes de confirmar necesito validar el cliente '{customer_identity_input}'. Envíame el NIT, código o nombre completo correcto para no cruzar el pedido.",
                },
                ensure_ascii=False,
            )

    if customer_context and customer_context.get("nombre_cliente"):
        nombre_despacho = customer_context.get("nombre_cliente")

    confirmed_items = []
    for it in items_pedido:
        reference_value = (it.get("referencia") or "").strip()
        lookup_request = {
            "product_codes": [reference_value] if reference_value else [],
            "store_filters": store_filters,
        }
        lookup_rows = lookup_product_context(reference_value, lookup_request) if reference_value else []
        matched_row = next(
            (
                row for row in lookup_rows
                if normalize_reference_value(row.get("referencia") or row.get("codigo_articulo") or row.get("producto_codigo"))
                == normalize_reference_value(reference_value)
            ),
            lookup_rows[0] if lookup_rows else {},
        )
        matched_product = dict(matched_row or {})
        matched_product.setdefault("referencia", reference_value)
        matched_product.setdefault("codigo_articulo", reference_value)
        matched_product.setdefault("descripcion", it.get("descripcion_comercial", ""))
        confirmed_items.append(
            {
                "status": "matched",
                "original_text": it.get("descripcion_comercial", ""),
                "matched_product": matched_product,
                "product_request": {
                    "requested_quantity": it.get("cantidad"),
                    "requested_unit": infer_product_presentation_from_row(matched_product) or "unidad",
                },
            }
        )

    commercial_draft["items"] = confirmed_items
    commercial_draft["store_filters"] = store_filters
    commercial_draft["delivery_channel"] = "email" if canal_envio == "email" else "chat"
    commercial_draft["contact_email"] = correo_cliente or commercial_draft.get("contact_email")
    commercial_draft["items_confirmed"] = True
    commercial_draft["claim_case"] = None
    commercial_draft["customer_identity_input"] = customer_identity_input or None
    commercial_draft["customer_context"] = customer_context or None
    commercial_draft["customer_resolution_status"] = customer_resolution_status
    conversation_context["commercial_draft"] = commercial_draft
    conversation_context["claim_case"] = None

    if not commercial_draft.get("items"):
        return json.dumps(
            {"exito": False, "mensaje": "No hay un pedido activo con productos para confirmar."},
            ensure_ascii=False,
        )

    commercial_draft["nombre_despacho"] = nombre_despacho
    commercial_draft["ready_to_close"] = True

    verified_cliente = conversation_context.get("verified_cliente_codigo")
    cliente_contexto = None
    if customer_context.get("cliente_codigo"):
        try:
            cliente_contexto = get_cliente_contexto(customer_context.get("cliente_codigo"))
        except Exception:
            cliente_contexto = customer_context
    elif verified_cliente:
        try:
            cliente_contexto = get_cliente_contexto(verified_cliente)
        except Exception:
            pass

    try:
        order_id = upsert_commercial_draft(
            "pedido",
            context["conversation_id"],
            context.get("contact_id"),
            context.get("cliente_id"),
            commercial_draft,
        )
        commercial_draft["draft_id"] = order_id
        mark_agent_order_status(order_id, "confirmado", metadata_update={"nombre_despacho": nombre_despacho})
        update_conversation_context(context["conversation_id"], {"commercial_draft": commercial_draft, "claim_case": None})
    except Exception as exc:
        return json.dumps(
            {"exito": False, "mensaje": f"No pude persistir el pedido en PostgreSQL: {exc}"},
            ensure_ascii=False,
        )

    try:
        pdf_id, pdf_filename = store_commercial_pdf(
            context["conversation_id"],
            "pedido",
            context.get("nombre_visible"),
            cliente_contexto,
            commercial_draft,
        )
    except Exception as exc:
        return json.dumps(
            {"exito": False, "mensaje": f"Error generando el PDF: {exc}"},
            ensure_ascii=False,
        )

    backend_base_url = os.environ.get("BACKEND_PUBLIC_URL", "").rstrip("/")
    pdf_url = f"{backend_base_url}/pdf/{pdf_id}" if backend_base_url else None
    export_summary = None
    export_error = None

    if internal_user:
        try:
            export_summary = export_confirmed_order_to_icg(
                order_id,
                context,
                commercial_draft,
                cliente_contexto,
                internal_user,
            )
            store_outbound_message(
                context["conversation_id"],
                None,
                "system",
                f"Pedido {order_id} exportado a ICG: {export_summary['file_name']}",
                export_summary,
                intent_detectado="pedido_icg_exportado",
            )
        except Exception as exc:
            export_error = str(exc)
            store_outbound_message(
                context["conversation_id"],
                None,
                "system",
                f"Error exportando pedido {order_id} a ICG: {exc}",
                {"error": str(exc), "order_id": order_id},
                intent_detectado="pedido_icg_error",
            )

    if canal_envio == "email" and correo_cliente:
        try:
            subject = f"Pedido Ferreinox CRM-{context['conversation_id']}"
            html_content = (
                f"<p>Estimado/a {nombre_despacho},</p>"
                f"<p>Adjuntamos el soporte de su pedido.</p>"
                f"<p>PDF: <a href='{pdf_url}'>{pdf_filename}</a></p>"
                f"<p>Gracias por su preferencia.<br>Ferreinox SAS BIC</p>"
            )
            send_sendgrid_email(
                correo_cliente, subject, html_content,
                f"Pedido Ferreinox: {pdf_url or pdf_filename}",
            )
            store_outbound_message(
                context["conversation_id"], None, "system",
                f"PDF pedido enviado por correo a {correo_cliente}",
                {"pdf_id": pdf_id, "email": correo_cliente},
                intent_detectado="pedido_pdf_email",
            )
            return json.dumps(
                {"exito": True, "canal": "email", "correo": correo_cliente,
                 "archivo": pdf_filename,
                 "order_id": order_id,
                 "export_icg": export_summary,
                 "export_error": export_error,
                 "mensaje": (
                     f"El PDF del pedido fue enviado al correo {correo_cliente} exitosamente."
                     + (f" Advertencia de exportación ICG: {export_error}" if export_error else "")
                 )},
                ensure_ascii=False,
            )
        except Exception as exc:
            return json.dumps(
                {"exito": False, "mensaje": f"No se pudo enviar el correo: {exc}"},
                ensure_ascii=False,
            )
    else:
        try:
            send_whatsapp_document_bytes(
                context["telefono_e164"],
                PDF_STORAGE[pdf_id]["buffer"],
                pdf_filename,
                caption=f"📄 Aquí tienes el soporte de tu pedido, {nombre_despacho}.",
            )
            store_outbound_message(
                context["conversation_id"], None, "system",
                f"PDF pedido enviado por WhatsApp: {pdf_filename}",
                {"pdf_id": pdf_id, "pdf_url": pdf_url},
                intent_detectado="pedido_pdf_whatsapp",
            )
            return json.dumps(
                {"exito": True, "canal": "whatsapp", "archivo": pdf_filename,
                 "order_id": order_id,
                 "export_icg": export_summary,
                 "export_error": export_error,
                 "mensaje": (
                     f"El PDF del pedido '{pdf_filename}' fue enviado por WhatsApp exitosamente."
                     + (f" Advertencia de exportación ICG: {export_error}" if export_error else "")
                 )},
                ensure_ascii=False,
            )
        except Exception as exc:
            if pdf_url:
                try:
                    send_whatsapp_document_message(
                        context["telefono_e164"],
                        pdf_url,
                        pdf_filename,
                        caption=f"📄 Aquí tienes el soporte de tu pedido, {nombre_despacho}.",
                    )
                    return json.dumps(
                        {"exito": True, "canal": "whatsapp", "archivo": pdf_filename,
                         "order_id": order_id,
                         "export_icg": export_summary,
                         "export_error": export_error,
                         "mensaje": (
                             f"El PDF del pedido '{pdf_filename}' fue enviado por WhatsApp exitosamente."
                             + (f" Advertencia de exportación ICG: {export_error}" if export_error else "")
                         )},
                        ensure_ascii=False,
                    )
                except Exception:
                    pass
            return json.dumps(
                {"exito": False,
                 "mensaje": f"PDF generado pero no se pudo enviar por WhatsApp: {exc}",
                 "archivo_pdf": pdf_filename,
                 "order_id": order_id,
                 "export_icg": export_summary,
                 "export_error": export_error},
                ensure_ascii=False,
            )


def _handle_tool_guardar_aprendizaje_producto(args, conversation_context):
    codigo_cliente = (args.get("codigo_cliente") or "").strip()
    descripcion_asociada = (args.get("descripcion_asociada") or "").strip()
    if not codigo_cliente or not descripcion_asociada:
        return json.dumps(
            {"guardado": False, "mensaje": "Se requiere código del cliente y descripción asociada."},
            ensure_ascii=False,
        )

    # --- Anti-tambor filter: block absurd associations ---
    BANNED_LEARNING_TOKENS = ["tambor", "50 galones", "55 galones", "200 litros"]
    desc_lower = descripcion_asociada.lower()
    code_lower = codigo_cliente.lower()
    if any(token in desc_lower for token in BANNED_LEARNING_TOKENS):
        if not any(token in code_lower for token in BANNED_LEARNING_TOKENS):
            return json.dumps(
                {"guardado": False, "mensaje": "No se guardó: presentación de tambor/industrial no se aprende automáticamente."},
                ensure_ascii=False,
            )

    normalized_code = normalize_text_value(codigo_cliente)
    if not should_store_learning_phrase(normalized_code):
        return json.dumps(
            {"guardado": False, "mensaje": "No se guardó: la jerga o frase del cliente es demasiado ambigua para memoria permanente."},
            ensure_ascii=False,
        )

    resolved_row = resolve_confirmed_learning_product_row(descripcion_asociada, conversation_context)
    if not resolved_row:
        return json.dumps(
            {
                "guardado": False,
                "mensaje": "No se guardó: todavía no tengo un producto confirmado con referencia exacta para esa descripción. Primero aclara o confirma la opción correcta.",
            },
            ensure_ascii=False,
        )

    canonical_reference = resolved_row.get("referencia") or resolved_row.get("codigo_articulo")
    canonical_description = resolved_row.get("descripcion") or resolved_row.get("nombre_articulo") or descripcion_asociada
    canonical_brand = resolved_row.get("marca") or resolved_row.get("marca_producto")
    canonical_presentation = infer_product_presentation_from_row(resolved_row) or normalize_text_value(resolved_row.get("presentacion_canonica")) or None
    if not canonical_reference:
        return json.dumps(
            {"guardado": False, "mensaje": "No se guardó: el producto confirmado todavía no tiene una referencia exacta usable."},
            ensure_ascii=False,
        )

    conversation_id = conversation_context.get("conversation_id")

    try:
        ensure_product_learning_table()
        engine = get_db_engine()
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO public.agent_product_learning (
                        normalized_phrase, raw_phrase, canonical_reference,
                        canonical_description, canonical_brand, canonical_presentation, source_conversation_id,
                        source_message, confidence, usage_count,
                        created_at, updated_at
                    ) VALUES (
                        :normalized_phrase, :raw_phrase, :canonical_reference,
                        :canonical_description, :canonical_brand, :canonical_presentation, :source_conversation_id,
                        :source_message, :confidence, 1, now(), now()
                    )
                    ON CONFLICT (normalized_phrase, canonical_reference)
                    DO UPDATE SET
                        canonical_description = EXCLUDED.canonical_description,
                        canonical_brand = COALESCE(EXCLUDED.canonical_brand, public.agent_product_learning.canonical_brand),
                        canonical_presentation = COALESCE(EXCLUDED.canonical_presentation, public.agent_product_learning.canonical_presentation),
                        source_conversation_id = COALESCE(EXCLUDED.source_conversation_id,
                            public.agent_product_learning.source_conversation_id),
                        confidence = GREATEST(public.agent_product_learning.confidence, EXCLUDED.confidence),
                        usage_count = public.agent_product_learning.usage_count + 1,
                        updated_at = now()
                    """
                ),
                {
                    "normalized_phrase": normalized_code,
                    "raw_phrase": codigo_cliente,
                    "canonical_reference": str(canonical_reference),
                    "canonical_description": canonical_description,
                    "canonical_brand": canonical_brand,
                    "canonical_presentation": canonical_presentation,
                    "source_conversation_id": conversation_id,
                    "source_message": f"{codigo_cliente} = {canonical_reference} | {canonical_description}",
                    "confidence": 0.95,
                },
            )
        return json.dumps(
            {"guardado": True, "mensaje": f"Aprendizaje guardado: '{codigo_cliente}' → '{canonical_reference} | {canonical_description}'. "
             "La próxima vez que alguien pida este código, el sistema lo reconocerá automáticamente."},
            ensure_ascii=False,
        )
    except Exception as exc:
        return json.dumps(
            {"guardado": False, "mensaje": f"No se pudo guardar el aprendizaje: {exc}"},
            ensure_ascii=False,
        )


def _handle_tool_consultar_conocimiento_tecnico(args, context, conversation_context):
    pregunta = (args.get("pregunta") or "").strip()
    producto = (args.get("producto") or "").strip()
    marca_filter = (args.get("marca") or "").strip() or None
    if not pregunta:
        return json.dumps(
            {"encontrado": False, "mensaje": "Se requiere una pregunta técnica."},
            ensure_ascii=False,
        )

    # Build search query combining question + product context
    search_query = pregunta
    if producto:
        search_query = f"{producto}: {pregunta}"

    chunks = search_technical_chunks(search_query, top_k=5, marca_filter=marca_filter)
    if not chunks:
        return json.dumps(
            {"encontrado": False, "respuesta_rag": None,
             "mensaje": "No encontré información técnica vectorizada para esa consulta. "
                        "Intenta con `buscar_documento_tecnico` para enviar el PDF completo."},
            ensure_ascii=False,
        )

    rag_context = build_rag_context(chunks, max_chunks=4)
    source_files = list(dict.fromkeys(c.get("doc_filename", "") for c in chunks if c.get("similarity", 0) >= 0.25))
    best_similarity = max(c.get("similarity", 0) for c in chunks)

    return json.dumps(
        {
            "encontrado": True,
            "respuesta_rag": rag_context,
            "archivos_fuente": source_files,
            "mejor_similitud": round(best_similarity, 4),
            "mensaje": (
                "INSTRUCCIONES OBLIGATORIAS: "
                "1) Lee 'respuesta_rag' y extrae DATOS CONCRETOS: nombres de catalizadores/componentes, "
                "proporciones exactas (ej. '4:1'), tiempos (ej. 'secado al tacto: 30 min'), rendimientos, temperaturas. "
                "2) Tu respuesta al cliente DEBE incluir al menos un dato específico numérico o un nombre de producto extraído de 'respuesta_rag'. "
                "3) PROHIBIDO decir frases genéricas como 'un agente de curado específico' o 'según las condiciones'. Cita el dato real. "
                "4) Luego usa `buscar_documento_tecnico` con el nombre del archivo fuente para enviar el PDF como respaldo."
            ),
        },
        ensure_ascii=False,
    )


def _handle_tool_guardar_producto_complementario(args, conversation_context):
    producto_ref = (args.get("producto_referencia") or "").strip()
    producto_desc = (args.get("producto_descripcion") or "").strip()
    companion_ref = (args.get("companion_referencia") or "").strip()
    companion_desc = (args.get("companion_descripcion") or "").strip()
    tipo = (args.get("tipo_relacion") or "").strip().lower()
    proporcion = (args.get("proporcion") or "").strip() or None
    notas = (args.get("notas") or "").strip() or None

    VALID_TIPOS = ["catalizador", "diluyente", "base", "complemento", "sellador", "imprimante", "acabado"]
    if not producto_ref or not companion_ref or not tipo:
        return json.dumps(
            {"guardado": False, "mensaje": "Se requiere producto_referencia, companion_referencia y tipo_relacion."},
            ensure_ascii=False,
        )
    if tipo not in VALID_TIPOS:
        return json.dumps(
            {"guardado": False, "mensaje": f"tipo_relacion debe ser uno de: {', '.join(VALID_TIPOS)}."},
            ensure_ascii=False,
        )

    conversation_id = conversation_context.get("conversation_id")

    try:
        ensure_product_companion_table()
        engine = get_db_engine()
        with engine.begin() as connection:
            connection.execute(
                text("""
                    INSERT INTO public.agent_product_companion (
                        producto_referencia, producto_descripcion,
                        companion_referencia, companion_descripcion,
                        tipo_relacion, proporcion, notas,
                        source_conversation_id, confidence,
                        created_at, updated_at
                    ) VALUES (
                        :producto_ref, :producto_desc,
                        :companion_ref, :companion_desc,
                        :tipo, :proporcion, :notas,
                        :conversation_id, 0.95, now(), now()
                    )
                    ON CONFLICT (producto_referencia, companion_referencia, tipo_relacion)
                    DO UPDATE SET
                        producto_descripcion = COALESCE(EXCLUDED.producto_descripcion, public.agent_product_companion.producto_descripcion),
                        companion_descripcion = COALESCE(EXCLUDED.companion_descripcion, public.agent_product_companion.companion_descripcion),
                        proporcion = COALESCE(EXCLUDED.proporcion, public.agent_product_companion.proporcion),
                        notas = COALESCE(EXCLUDED.notas, public.agent_product_companion.notas),
                        confidence = GREATEST(public.agent_product_companion.confidence, EXCLUDED.confidence),
                        updated_at = now()
                    """),
                {
                    "producto_ref": producto_ref,
                    "producto_desc": producto_desc or None,
                    "companion_ref": companion_ref,
                    "companion_desc": companion_desc or None,
                    "tipo": tipo,
                    "proporcion": proporcion,
                    "notas": notas,
                    "conversation_id": conversation_id,
                },
            )
        return json.dumps(
            {"guardado": True, "mensaje": f"Relación guardada: {producto_ref} → {tipo}: {companion_ref} ({companion_desc or 'sin descripción'})."},
            ensure_ascii=False,
        )
    except Exception as exc:
        return json.dumps(
            {"guardado": False, "mensaje": f"No se pudo guardar la relación: {exc}"},
            ensure_ascii=False,
        )


def _execute_agent_tool(tool_call, context, conversation_context):
    fn_name = tool_call.function.name
    try:
        fn_args = json.loads(tool_call.function.arguments)
    except json.JSONDecodeError:
        fn_args = {}

    if fn_name == "consultar_inventario":
        result = _handle_tool_consultar_inventario(fn_args, conversation_context)
    elif fn_name == "verificar_identidad":
        result = _handle_tool_verificar_identidad(fn_args, context, conversation_context)
    elif fn_name == "consultar_cartera":
        result = _handle_tool_consultar_cartera(conversation_context)
    elif fn_name == "consultar_compras":
        result = _handle_tool_consultar_compras(fn_args, conversation_context)
    elif fn_name == "buscar_documento_tecnico":
        result = _handle_tool_buscar_documento_tecnico(fn_args, context, conversation_context)
    elif fn_name == "consultar_conocimiento_tecnico":
        result = _handle_tool_consultar_conocimiento_tecnico(fn_args, context, conversation_context)
    elif fn_name == "radicar_reclamo":
        result = _handle_tool_radicar_reclamo(fn_args, context, conversation_context)
    elif fn_name == "confirmar_pedido_y_generar_pdf":
        result = _handle_tool_confirmar_pedido(fn_args, context, conversation_context)
    elif fn_name == "guardar_aprendizaje_producto":
        result = _handle_tool_guardar_aprendizaje_producto(fn_args, conversation_context)
    elif fn_name == "guardar_producto_complementario":
        result = _handle_tool_guardar_producto_complementario(fn_args, conversation_context)
    else:
        result = json.dumps({"error": f"Herramienta desconocida: {fn_name}"}, ensure_ascii=False)

    return fn_name, fn_args, result


def generate_agent_reply_v2(
    profile_name: Optional[str],
    conversation_context: dict,
    recent_messages: list[dict],
    user_message: str,
    context: dict,
):
    client = get_openai_client()
    nombre = profile_name or "cliente"

    verified = bool(conversation_context.get("verified"))
    verified_cliente = conversation_context.get("verified_cliente_codigo")
    nombre_cliente = ""
    if verified and verified_cliente:
        try:
            cli = get_cliente_contexto(verified_cliente)
            nombre_cliente = cli.get("nombre_cliente", "")
        except Exception:
            pass

    commercial_draft = conversation_context.get("commercial_draft")
    claim_case = conversation_context.get("claim_case")

    system_content = AGENT_SYSTEM_PROMPT_V2.format(
        verificado="SÍ" if verified else "NO",
        cliente_codigo=verified_cliente or "No identificado",
        nombre_cliente=nombre_cliente or "No identificado",
        borrador_activo=safe_json_dumps(commercial_draft) if commercial_draft else "Ninguno",
        reclamo_activo=safe_json_dumps(claim_case) if claim_case else "Ninguno",
    )

    messages = [{"role": "system", "content": system_content}]

    for msg in recent_messages[-20:]:
        role = "assistant" if msg.get("direction") == "outbound" else "user"
        content_text = msg.get("contenido") or ""
        if content_text and msg.get("message_type") in ("text", "button", "interactive", None):
            messages.append({"role": role, "content": content_text})

    messages.append({"role": "user", "content": user_message})

    response = client.chat.completions.create(
        model=get_openai_model(),
        messages=messages,
        tools=AGENT_TOOLS,
        tool_choice="auto",
        temperature=0.3,
    )

    assistant_message = response.choices[0].message
    tool_calls_made = []

    max_iterations = 5
    while assistant_message.tool_calls and max_iterations > 0:
        messages.append(assistant_message)
        for tc in assistant_message.tool_calls:
            fn_name, fn_args, result = _execute_agent_tool(tc, context, conversation_context)
            tool_calls_made.append({"name": fn_name, "args": fn_args, "result": result})
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result,
                }
            )

        response = client.chat.completions.create(
            model=get_openai_model(),
            messages=messages,
            tools=AGENT_TOOLS,
            tool_choice="auto",
            temperature=0.3,
        )
        assistant_message = response.choices[0].message
        max_iterations -= 1

    response_text = assistant_message.content or "Gracias por escribirnos. ¿En qué te puedo ayudar?"

    intent = "consulta_general"
    for tc in tool_calls_made:
        if tc["name"] == "verificar_identidad":
            intent = "verificacion_identidad"
        elif tc["name"] == "consultar_inventario":
            intent = "consulta_productos"
        elif tc["name"] == "consultar_cartera":
            intent = "consulta_cartera"
        elif tc["name"] == "consultar_compras":
            intent = "consulta_compras"
        elif tc["name"] == "buscar_documento_tecnico":
            intent = "consulta_documentacion"
        elif tc["name"] == "consultar_conocimiento_tecnico":
            intent = "asesoria_tecnica"
        elif tc["name"] == "radicar_reclamo":
            intent = "reclamo_servicio"
        elif tc["name"] == "confirmar_pedido_y_generar_pdf":
            intent = "pedido"

    return {
        "response_text": response_text,
        "intent": intent,
        "tool_calls": tool_calls_made,
        "context_updates": {
            "last_product_request": conversation_context.get("last_product_request"),
            "last_product_query": conversation_context.get("last_product_query"),
            "last_product_context": conversation_context.get("last_product_context"),
        } if conversation_context.get("last_product_request") else {},
        "should_create_task": False,
    }


def get_internal_bootstrap_token():
    return os.getenv("INTERNAL_AUTH_BOOTSTRAP_TOKEN")


@app.post("/agent/auth/bootstrap-user")
def bootstrap_internal_user(
    payload: InternalBootstrapUserRequest,
    x_bootstrap_token: Optional[str] = Header(default=None),
):
    configured_token = get_internal_bootstrap_token()
    if not configured_token:
        raise HTTPException(status_code=503, detail="No se configuró INTERNAL_AUTH_BOOTSTRAP_TOKEN en el backend.")
    if x_bootstrap_token != configured_token:
        raise HTTPException(status_code=403, detail="Bootstrap token inválido.")
    user_payload = upsert_internal_user(payload)
    return {
        "status": "ok",
        "user": {
            "id": user_payload.get("id"),
            "username": user_payload.get("username"),
            "full_name": user_payload.get("full_name"),
            "role": user_payload.get("role"),
            "phone_e164": user_payload.get("phone_e164"),
            "email": user_payload.get("email"),
            "scopes": user_payload.get("scopes") or [],
        },
    }


@app.post("/agent/auth/login-internal")
def login_internal_agent(payload: InternalLoginRequest):
    user_payload = authenticate_internal_user(payload.username, payload.password)
    if not user_payload:
        raise HTTPException(status_code=401, detail="Usuario o contraseña interna inválidos.")
    session_payload = create_internal_session(user_payload, channel="api")
    return {
        "status": "ok",
        "access_token": session_payload["token"],
        "token_type": "bearer",
        "expires_at": session_payload["expires_at"],
        "user": {
            "id": user_payload.get("id"),
            "username": user_payload.get("username"),
            "full_name": user_payload.get("full_name"),
            "role": user_payload.get("role"),
            "phone_e164": user_payload.get("phone_e164"),
            "email": user_payload.get("email"),
            "scopes": user_payload.get("scopes") or [],
        },
    }


@app.post("/agent/auth/logout")
def logout_internal_agent(authorization: Optional[str] = Header(default=None)):
    token = extract_bearer_token(authorization)
    if token:
        revoke_internal_session(token)
    return {"status": "ok"}


@app.get("/agent/auth/me")
def get_internal_agent_me(authorization: Optional[str] = Header(default=None)):
    internal_user = require_internal_user(authorization)
    return {
        "id": internal_user.get("id"),
        "username": internal_user.get("username"),
        "full_name": internal_user.get("full_name"),
        "role": internal_user.get("role"),
        "email": internal_user.get("email"),
        "phone_e164": internal_user.get("phone_e164"),
        "session_expires_at": internal_user.get("session_expires_at"),
        "scopes": internal_user.get("scopes") or [],
    }


@app.get("/agent/internal/clientes/buscar")
def search_internal_customers(q: str, authorization: Optional[str] = Header(default=None)):
    internal_user = require_internal_user(authorization)
    customer_rows = search_customer_lookup_rows(q, limit=10)
    visible_rows = [row for row in customer_rows if internal_user_can_access_customer(internal_user, row)]
    return {"items": visible_rows}


@app.get("/agent/internal/clientes/{cliente_codigo}/contexto")
def get_internal_customer_context(cliente_codigo: str, authorization: Optional[str] = Header(default=None)):
    internal_user = require_internal_user(authorization)
    customer_row = fetch_customer_lookup_row(cliente_codigo)
    if not customer_row:
        raise HTTPException(status_code=404, detail="Cliente no encontrado.")
    if not internal_user_can_access_customer(internal_user, customer_row):
        raise HTTPException(status_code=403, detail="No tienes permisos para consultar ese cliente.")
    contexto = get_cliente_contexto(cliente_codigo)
    return {"lookup": customer_row, "contexto": contexto}


@app.get("/agent/internal/clientes/{cliente_codigo}/cartera")
def get_internal_customer_portfolio(cliente_codigo: str, authorization: Optional[str] = Header(default=None)):
    internal_user = require_internal_user(authorization)
    customer_row = fetch_customer_lookup_row(cliente_codigo)
    if not customer_row:
        raise HTTPException(status_code=404, detail="Cliente no encontrado.")
    if not internal_user_can_access_customer(internal_user, customer_row):
        raise HTTPException(status_code=403, detail="No tienes permisos para consultar ese cliente.")
    contexto = get_cliente_contexto(cliente_codigo)
    overdue_info = fetch_overdue_documents(cliente_codigo)
    return {
        "lookup": customer_row,
        "contexto": contexto,
        "vencidos": overdue_info,
    }


@app.get("/agent/internal/clientes/{cliente_codigo}/compras")
def get_internal_customer_purchases(cliente_codigo: str, authorization: Optional[str] = Header(default=None)):
    internal_user = require_internal_user(authorization)
    customer_row = fetch_customer_lookup_row(cliente_codigo)
    if not customer_row:
        raise HTTPException(status_code=404, detail="Cliente no encontrado.")
    if not internal_user_can_access_customer(internal_user, customer_row):
        raise HTTPException(status_code=403, detail="No tienes permisos para consultar ese cliente.")
    latest_purchase = fetch_latest_purchase_detail(cliente_codigo)
    purchase_summary = fetch_purchase_summary(cliente_codigo)
    return {
        "lookup": customer_row,
        "ultima_compra": latest_purchase,
        "resumen": purchase_summary,
    }


@app.get("/agent/internal/productos/buscar")
def search_internal_products(q: str, store: Optional[str] = None, authorization: Optional[str] = Header(default=None)):
    require_internal_user(authorization)
    product_request = prepare_product_request_for_search(q)
    rows = lookup_product_context(q, product_request)
    response_rows = []
    for row in rows[:10]:
        if store and normalize_text_value(store) not in normalize_text_value(row.get("stock_by_store") or row.get("stock_por_tienda") or ""):
            continue
        response_rows.append(row)
    return {"items": response_rows, "nlu_extraccion": product_request.get("nlu_extraction") or {}}


@app.get("/")
def read_root():
    return {
        "estado": "Sistema CRM Ferreinox Activo",
        "version": "2026.3",
        "postgrest_url": get_postgrest_url(),
        "endpoints": [
            "/health",
            "/agent/clientes/{cliente_codigo}/contexto",
            "/agent/auth/login-internal",
            "/agent/auth/me",
            "/agent/internal/clientes/buscar",
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


@app.get("/pdf/{pdf_id}")
def serve_commercial_pdf(pdf_id: str):
    entry = PDF_STORAGE.get(pdf_id)
    if not entry:
        raise HTTPException(status_code=404, detail="PDF no encontrado o expirado")
    return StreamingResponse(
        io.BytesIO(entry["buffer"]),
        media_type="application/pdf",
        headers={"Content-Disposition": f"inline; filename=\"{entry['filename']}\""},
    )


@app.post("/conversations/{conversation_id}/reset")
def reset_conversation_context(conversation_id: int):
    """Clear all conversation context so the agent starts fresh."""
    engine = get_db_engine()
    with engine.begin() as connection:
        row = connection.execute(
            text(
                """
                SELECT id
                FROM public.agent_conversation
                WHERE id = :conversation_id
                """
            ),
            {"conversation_id": conversation_id},
        ).mappings().one_or_none()
        if not row:
            raise HTTPException(status_code=404, detail="Conversación no encontrada")
        connection.execute(
            text(
                """
                UPDATE public.agent_conversation
                SET contexto = '{}'::jsonb,
                    resumen = 'Contexto reiniciado manualmente',
                    estado = 'abierta',
                    updated_at = now(),
                    last_message_at = now()
                WHERE id = :conversation_id
                """
            ),
            {"conversation_id": conversation_id},
        )
    return {"status": "ok", "conversation_id": conversation_id, "message": "Contexto limpiado"}


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

                stored_content = content
                if content:
                    login_match = INTERNAL_LOGIN_PATTERN.match(content)
                    if login_match:
                        stored_content = f"login {login_match.group(1)} ******"
                    else:
                        employee_by_phone = find_employee_record_by_phone(context.get("telefono_e164"))
                        cedula_match = extract_internal_cedula_candidate(content)
                        if employee_by_phone and cedula_match:
                            stored_content = content.replace(cedula_match, f"{cedula_match[:2]}******{cedula_match[-2:]}")

                store_inbound_message(
                    context["conversation_id"],
                    message.get("id"),
                    message_type,
                    stored_content,
                    message,
                )

                recent_messages = load_recent_conversation_messages(context["conversation_id"])
                conversation_snapshot = get_conversation_snapshot(context["conversation_id"])
                conversation_context = dict(conversation_snapshot.get("contexto") or {})

                # ── Auto-reset conversation context after 3 hours of inactivity ──
                last_msg_at = conversation_snapshot.get("last_message_at")
                if last_msg_at:
                    if hasattr(last_msg_at, "tzinfo") and last_msg_at.tzinfo is not None:
                        from datetime import timezone
                        now_aware = datetime.now(timezone.utc)
                        elapsed = now_aware - last_msg_at
                    else:
                        elapsed = datetime.utcnow() - last_msg_at
                    if elapsed > timedelta(hours=3):
                        conversation_context = {}
                        update_conversation_context(
                            context["conversation_id"],
                            {
                                "verified": None,
                                "verified_document": None,
                                "verified_by": None,
                                "verified_cliente_codigo": None,
                                "awaiting_verification": None,
                                "awaiting_name_confirmation": None,
                                "pending_verified_context": None,
                                "pending_intent": None,
                                "commercial_draft": None,
                                "last_direct_intent": None,
                                "claim_case": None,
                                "pending_product_clarification": None,
                                "pending_document_options": None,
                                "last_product_request": None,
                                "internal_auth": None,
                                "internal_last_cliente_codigo": None,
                                "awaiting_internal_auth_cedula": None,
                                "internal_transfer_flow": None,
                            },
                            summary="Contexto reiniciado por inactividad (3h+)",
                        )

                # ── Function Calling routing (v2) ──
                # Load client context if already verified
                cliente_contexto = None
                verified_cliente_codigo = conversation_context.get("verified_cliente_codigo")
                if verified_cliente_codigo:
                    try:
                        cliente_contexto = get_cliente_contexto(verified_cliente_codigo)
                    except HTTPException:
                        cliente_contexto = None
                if cliente_contexto is None:
                    cliente_contexto = find_cliente_contexto_by_phone(context["telefono_e164"])
                    if cliente_contexto:
                        try:
                            cliente_id = update_contact_cliente(context["contact_id"], cliente_contexto.get("cliente_codigo"))
                            context["cliente_id"] = cliente_id
                        except Exception:
                            pass

                # Generate response using LLM with function calling
                ai_result = None
                outbound_payload = None
                if content and message_type in {"text", "button", "interactive"}:
                    try:
                        ai_result = handle_internal_whatsapp_message(content, context, conversation_context)
                        if ai_result is None:
                            ai_result = generate_agent_reply_v2(
                                context.get("nombre_visible"),
                                conversation_context,
                                recent_messages,
                                content,
                                context,
                            )
                    except Exception as exc:
                        ai_result = build_fallback_agent_result(content, str(exc))

                    response_text = ai_result.get("response_text") or "Gracias por escribirnos. ¿En qué te puedo ayudar?"

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
                            f"No fue posible enviar respuesta: {exc}",
                            {"error": str(exc), "response_text": response_text},
                            intent_detectado=ai_result.get("intent"),
                        )

                    # Update conversation context
                    context_updates = {
                        "intent": ai_result.get("intent"),
                        "last_direct_intent": ai_result.get("intent"),
                        "verified": conversation_context.get("verified", False),
                        "verified_document": conversation_context.get("verified_document"),
                        "verified_cliente_codigo": conversation_context.get("verified_cliente_codigo"),
                        "awaiting_verification": False,
                    }
                    extra_context_updates = ai_result.get("context_updates") or {}
                    if extra_context_updates:
                        context_updates.update(extra_context_updates)
                    update_conversation_context(
                        context["conversation_id"],
                        context_updates,
                        summary=content[:200] if content else "Mensaje procesado",
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