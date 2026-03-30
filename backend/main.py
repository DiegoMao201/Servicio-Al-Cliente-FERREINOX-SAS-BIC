import os
import json
import re
import unicodedata
from difflib import SequenceMatcher
from datetime import date, timedelta
from typing import Optional

import requests
from fastapi import FastAPI, HTTPException, Query, Request
from openai import OpenAI
from sqlalchemy import create_engine, text


app = FastAPI(title="CRM Ferreinox Backend", version="2026.2")


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
    "domestico": ["domestico", "doméstico", "vinilico", "viniltex", "economico", "económico"],
    "pintuco": ["pintuco", "viniltex", "p11", "p-11", "p 11"],
    "p11": ["p11", "p-11", "p 11", "pintuco 11"],
    "abracol": ["abracol"],
    "yale": ["yale"],
    "goya": ["goya"],
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

    phrases = []
    previous_product_request = (conversation_context or {}).get("last_product_request") or {}
    for candidate_phrase in [
        product_request.get("original_query"),
        " ".join(product_request.get("core_terms") or []),
        previous_product_request.get("original_query"),
        " ".join(previous_product_request.get("core_terms") or []),
    ]:
        if should_store_learning_phrase(candidate_phrase):
            normalized_phrase = normalize_text_value(candidate_phrase)
            if normalized_phrase not in phrases:
                phrases.append(normalized_phrase)

    if not phrases:
        return

    ensure_product_learning_table()
    engine = get_db_engine()
    with engine.begin() as connection:
        for phrase in phrases[:6]:
            for row in product_context[:3]:
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

    phrases = []
    for candidate_phrase in [
        product_request.get("original_query"),
        " ".join(product_request.get("core_terms") or []),
    ]:
        normalized_phrase = normalize_text_value(candidate_phrase)
        if normalized_phrase and normalized_phrase not in phrases:
            phrases.append(normalized_phrase)

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
                    SELECT canonical_reference, MAX(confidence) AS confidence, SUM(usage_count) AS total_hits
                    FROM public.agent_product_learning
                    WHERE normalized_phrase = :normalized_phrase
                    GROUP BY canonical_reference
                    ORDER BY MAX(confidence) DESC, SUM(usage_count) DESC
                    LIMIT 5
                    """
                ),
                {"normalized_phrase": phrase},
            ).mappings().all()
            learned_rows.extend(row_set)

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

    codes = []
    seen_codes = set()
    for raw_code in re.findall(r"\b[a-z]?\d[a-z0-9-]{1,14}\b|\b\d{4,10}\b", normalized):
        cleaned_code = normalize_reference_value(raw_code)
        if len(cleaned_code) < 3 or cleaned_code in seen_codes:
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


def infer_product_presentation_from_row(product_row: dict):
    description_value = normalize_text_value(product_row.get("descripcion") or product_row.get("nombre_articulo"))
    for size_token, unit_name in PRESENTATION_SIZE_MAP.items():
        if size_token in description_value:
            return unit_name
    return None


def infer_product_brand_from_row(product_row: dict):
    brand_text = normalize_text_value(product_row.get("marca") or product_row.get("marca_producto") or "")
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
    if department_value:
        summary_parts.append(str(department_value))
    if stock_value is not None:
        summary_parts.append(f"stock {stock_value}")
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
    presentation_values.discard(None)
    brand_values.discard(None)

    if not product_request.get("requested_unit") and len(presentation_values) >= 2:
        return True
    if len(brand_values) >= 2:
        return True
    return False


def filter_rows_by_requested_presentation(product_rows: list[dict], product_request: Optional[dict]):
    if not product_request or not product_request.get("requested_unit"):
        return product_rows
    exact_rows = [row for row in product_rows if infer_product_presentation_from_row(row) == product_request.get("requested_unit")]
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


def is_sensitive_intent_message(text_value: Optional[str]):
    if not text_value:
        return False
    lowered = text_value.lower()
    sensitive_keywords = [
        "cartera",
        "saldo",
        "debo",
        "deuda",
        "cupo",
        "credito",
        "vencido",
        "factura",
        "facturas",
        "pago",
        "pagos",
        "estado de cuenta",
        "ventas",
        "compras",
        "recaudo",
    ]
    return any(keyword in lowered for keyword in sensitive_keywords)


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
    ]
    has_keyword = any(keyword in lowered for keyword in product_keywords)
    quantity_format = bool(re.search(r"\b\d+(?:[.,]\d+)?\s*(galones?|galon|cuartos?|cunetes?|cuñetes?|canecas?|cubetas?)\b", lowered))
    shorthand_format = bool(re.search(r"\b\d+\s*/\s*\d+\b", lowered))
    code_with_stock = bool(re.search(r"\b\d{4,10}\b", lowered)) and any(kw in lowered for kw in ["stock", "inventario", "hay", "precio", "cuanto", "producto"])
    return has_keyword or quantity_format or shorthand_format or code_with_stock


def is_greeting_message(text_value: Optional[str]):
    lowered = normalize_text_value(text_value)
    if not lowered:
        return False
    exact_greetings = {"hola", "buen dia", "buenos dias", "buenas tardes", "buenas noches", "hello", "hi", "hey"}
    if lowered in exact_greetings:
        return True
    return bool(re.match(
        r"^(hola|hey|buenas?|buenos?\s+dias?|buenas?\s+tardes?|buenas?\s+noches?)"
        r"(\s+(como estas|como esta|que tal|buen dia|buenos dias|buenas tardes|buenas noches))?"
        r"[.!?,\s]*$",
        lowered,
    ))


def detect_business_intent(text_value: Optional[str]):
    if not text_value:
        return "consulta_general"

    lowered = normalize_text_value(text_value)
    if any(keyword in lowered for keyword in ["cartera", "saldo", "deuda", "debo", "vencido", "estado de cuenta", "cupo", "credito", "cuanto debo", "cuánto debo"]):
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
            "store_filters": [],
            "original_query": "",
        }

    requested_quantity = None
    requested_unit = None
    quantity_expression = None

    quantity_match = re.search(r"\b(\d+(?:[.,]\d+)?)\s*(galones?|galon|cuartos?|cunetes?|cuñetes?|canecas?|cubetas?)\b", normalized)
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
        "wants_overdue_only": "vencid" in normalized,
        "wants_invoice_list": any(keyword in normalized for keyword in ["factura", "facturas", "cuales", "cuáles", "que facturas", "qué facturas", "documentos"]),
    }


def has_temporal_reference(text_value: Optional[str]):
    purchase_query = extract_purchase_query(text_value)
    return bool(purchase_query.get("has_time_filter"))


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
                """
                SELECT MAX(fecha_venta) AS fecha_venta
                FROM public.vw_ventas_netas
                WHERE cliente_id = :cliente_codigo
                """
            ),
            {"cliente_codigo": cliente_codigo},
        ).mappings().one()

        latest_date = latest_row.get("fecha_venta")
        if not latest_date:
            return None

        totals = connection.execute(
            text(
                """
                SELECT
                    COUNT(*) AS lineas,
                    COALESCE(SUM(valor_venta_neto), 0) AS valor_total,
                    COALESCE(SUM(unidades_vendidas_netas), 0) AS unidades_totales
                FROM public.vw_ventas_netas
                WHERE cliente_id = :cliente_codigo
                  AND fecha_venta = :latest_date
                """
            ),
            {"cliente_codigo": cliente_codigo, "latest_date": latest_date},
        ).mappings().one()

        products = connection.execute(
            text(
                """
                SELECT codigo_articulo, nombre_articulo,
                       COALESCE(SUM(unidades_vendidas_netas), 0) AS unidades,
                       COALESCE(SUM(valor_venta_neto), 0) AS valor
                FROM public.vw_ventas_netas
                WHERE cliente_id = :cliente_codigo
                  AND fecha_venta = :latest_date
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
):
    nombre = profile_name or "cliente"

    if intent == "consulta_cartera":
        if not cliente_contexto:
            return None
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
                    f"factura {row['numero_documento']} por {format_currency(row['importe_normalizado'])}, vencida {row['dias_vencido']} días"
                    for row in documents[:5]
                )
                response_text = (
                    f"Hola, {nombre}. Tu cartera vencida suma {overdue_total} en {int(overdue_info['totals'].get('documentos_vencidos') or 0)} facturas. "
                    f"Las principales son: {doc_lines}."
                )
            else:
                response_text = (
                    f"Hola, {nombre}. Tu cartera vencida actual es {overdue_total}. "
                    f"Tienes {int(overdue_info['totals'].get('documentos_vencidos') or 0)} documentos vencidos y el máximo atraso es de {int(overdue_info['totals'].get('max_dias_vencido') or 0)} días."
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
                f"Documentos vencidos: {vencidos}. Máximo de días vencidos: {dias}. "
                f"Tu asesor asociado es {vendedor}. Si quieres, también puedo resumirte tus compras del último año."
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
                    f"Hola, {nombre}. Tu última compra fue el {latest_purchase.get('fecha_venta')} por {format_currency(totals.get('valor_total'))}, "
                    f"con {int(totals.get('lineas') or 0)} líneas y {int(float(totals.get('unidades_totales') or 0))} unidades. "
                    f"Los productos fueron: {product_summary}."
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
                    f"Hola, {nombre}. En {purchase_query.get('label')} compraste {format_currency(totals.get('valor_total'))} "
                    f"en {int(totals.get('lineas') or 0)} líneas, con {int(float(totals.get('unidades_totales') or 0))} unidades. "
                    f"Los productos registrados fueron: {top_summary}."
                )
            else:
                response_text = (
                    f"Hola, {nombre}. En los últimos 12 meses registras compras por {format_currency(totals.get('valor_total'))} "
                    f"en {int(totals.get('lineas') or 0)} líneas de venta, con {int(float(totals.get('unidades_totales') or 0))} unidades. "
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
                    f"Hola, {nombre}. Busqué *{referencia_solicitada or 'esa referencia'}* pero no encontré una coincidencia en el inventario. "
                    "¿Podrías darme más detalles? Por ejemplo:\n"
                    "• La referencia o código del producto\n"
                    "• La marca o línea del portafolio Ferreinox: Pintuco, Abracol, Yale o Goya\n"
                    "• La presentación (galón, cuñete, cuarto, 1/1, 1/5, 1/4)\n"
                    "• La tienda que te interesa (CEDI, Armenia, Manizales, Opalo, Pereira, Laures, Cerritos o Ferrebox)\n"
                    "Así puedo buscarlo con más precisión."
                ),
                "should_create_task": False,
                "task_type": "seguimiento_cliente",
                "task_summary": "Consulta de productos sin match exacto",
                "task_detail": {"product_request": product_request or {}},
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
                    f"Hola, {nombre}. Encontré varias opciones que podrían ser la que buscas. Responde con el número o la referencia:\n"
                    + "\n".join(clarification_lines)
                    + "\nAsí te doy el stock exacto de la opción correcta."
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
        if product_request:
            requested_quantity = product_request.get("requested_quantity")
            requested_unit = product_request.get("requested_unit")
            quantity_expression = product_request.get("quantity_expression")
            if requested_quantity and requested_unit:
                quantity_note = f"Entendí una solicitud de {requested_quantity:g} {get_presentation_label(requested_unit, requested_quantity)}"
            elif quantity_expression:
                quantity_note = f"Tomé la referencia de cantidad {quantity_expression} para orientarte mejor"

        for row in product_context[:3]:
            descripcion = row.get("descripcion") or row.get("nombre_articulo") or row.get("referencia") or row.get("codigo_articulo")
            referencia = row.get("referencia") or row.get("codigo_articulo") or "sin referencia"
            stock = row.get("stock_total") if row.get("stock_total") is not None else row.get("stock")
            stock_value = parse_numeric_value(stock)
            costo_promedio = row.get("costo_promedio_und")
            line = f"{descripcion} ({referencia})"
            if stock is not None:
                line += f", stock total aproximado {stock}"
            if costo_promedio is not None:
                line += f", costo promedio {format_currency(costo_promedio)}"
            category_value = row.get("departamentos") or row.get("categoria_producto")
            if category_value and str(category_value).strip().upper() != "NULL":
                line += f", categoria {category_value}"
            if row.get("stock_por_tienda"):
                line += f", disponible en {row.get('stock_por_tienda')}"
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
                f"Encontré estas referencias relacionadas: {'; '.join(product_lines)}. "
                "Si quieres, en el siguiente paso puedo ayudarte a convertir esto en una pre-solicitud de pedido."
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
        f"Gracias, {nombre}. Tu identidad quedó validada"
        f"{' para el cliente ' + str(cliente_nombre or cliente_codigo) if (cliente_nombre or cliente_codigo) else ''}"
        f"{' (' + str(cliente_codigo) + ')' if cliente_nombre and cliente_codigo else ''}. "
        "Ahora ya puedo ayudarte con cartera, compras del último año y consultas relacionadas con tu historial comercial."
    )


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
                learned_params = {}
                learned_filters = []
                for index, reference_value in enumerate(learned_references[:5]):
                    learned_params[f"learned_ref_{index}"] = normalize_reference_value(reference_value)
                    learned_filters.append(f"referencia_normalizada = :learned_ref_{index}")
                learned_store_clause = ""
                if store_filters:
                    learned_store_predicates = []
                    for store_index, store_code in enumerate(store_filters):
                        learned_params[f"learned_store_{store_index}"] = store_code
                        learned_store_predicates.append(f"cod_almacen = :learned_store_{store_index}")
                    learned_store_clause = f" AND ({' OR '.join(learned_store_predicates)})"
                learned_rows = connection.execute(
                    text(
                        f"""
                        SELECT referencia, descripcion, marca,
                               STRING_AGG(DISTINCT departamento, ', ' ORDER BY departamento) AS departamentos,
                               COALESCE(SUM(stock_disponible), 0) AS stock_total,
                               AVG(costo_promedio_und) AS costo_promedio_und,
                               STRING_AGG(
                                   almacen_nombre || ': ' || COALESCE(stock_disponible::text, '0'),
                                   '; '
                                   ORDER BY almacen_nombre
                               ) FILTER (WHERE COALESCE(stock_disponible, 0) > 0) AS stock_por_tienda,
                               90 AS match_score
                        FROM public.vw_inventario_agente
                        WHERE ({' OR '.join(learned_filters)}){learned_store_clause}
                        GROUP BY referencia, descripcion, marca
                        ORDER BY COALESCE(SUM(stock_disponible), 0) DESC NULLS LAST
                        LIMIT 5
                        """
                    ),
                    learned_params,
                ).mappings().all()
                if learned_rows:
                    return filter_rows_by_requested_presentation([dict(row) for row in learned_rows], product_request)

            if product_codes:
                code_params = {}
                code_filters = []
                for i, code in enumerate(product_codes[:3]):
                    code_params[f"code_{i}"] = f"%{code}%"
                    code_filters.append(f"referencia_normalizada LIKE :code_{i}")
                    code_filters.append(f"search_blob ILIKE :code_{i}")
                store_clause = ""
                if store_filters:
                    store_predicates = []
                    for store_index, store_code in enumerate(store_filters):
                        code_params[f"store_{store_index}"] = store_code
                        store_predicates.append(f"cod_almacen = :store_{store_index}")
                    store_clause = f" AND ({' OR '.join(store_predicates)})"
                code_rows = connection.execute(
                    text(
                        f"""
                           SELECT referencia, descripcion, marca,
                               STRING_AGG(DISTINCT departamento, ', ' ORDER BY departamento) AS departamentos,
                               COALESCE(SUM(stock_disponible), 0) AS stock_total,
                               AVG(costo_promedio_und) AS costo_promedio_und,
                               STRING_AGG(
                                   almacen_nombre || ': ' || COALESCE(stock_disponible::text, '0'),
                                   '; '
                                   ORDER BY almacen_nombre
                               ) FILTER (WHERE COALESCE(stock_disponible, 0) > 0) AS stock_por_tienda,
                               100 AS match_score
                        FROM public.vw_inventario_agente
                        WHERE ({' OR '.join(code_filters)}){store_clause}
                        GROUP BY referencia, descripcion, marca
                        ORDER BY COALESCE(SUM(stock_disponible), 0) DESC NULLS LAST
                        LIMIT 5
                        """
                    ),
                    code_params,
                ).mappings().all()
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
            params = {}
            inventory_filters = []
            inventory_scores = []
            for index, term in enumerate(query_terms):
                params[f"pattern_{index}"] = f"%{term}%"
                inventory_filters.append(f"search_blob ILIKE :pattern_{index}")
                inventory_scores.append(f"CASE WHEN search_blob ILIKE :pattern_{index} THEN 1 ELSE 0 END")
            base_store_clause = ""
            if store_filters:
                store_predicates = []
                for store_index, store_code in enumerate(store_filters):
                    params[f"store_{store_index}"] = store_code
                    store_predicates.append(f"cod_almacen = :store_{store_index}")
                base_store_clause = f"WHERE {' OR '.join(store_predicates)}"

            rows = connection.execute(
                text(
                    f"""
                          SELECT referencia, descripcion, marca, departamentos, stock_total, costo_promedio_und, stock_por_tienda,
                           ({' + '.join(inventory_scores)}) AS match_score
                    FROM (
                        SELECT
                            referencia,
                            descripcion,
                            marca,
                            COALESCE(SUM(stock_disponible), 0) AS stock_total,
                            AVG(costo_promedio_und) AS costo_promedio_und,
                            STRING_AGG(
                                almacen_nombre || ': ' || COALESCE(stock_disponible::text, '0'),
                                '; '
                                ORDER BY almacen_nombre
                            ) FILTER (WHERE COALESCE(stock_disponible, 0) > 0) AS stock_por_tienda,
                            MAX(search_blob) AS search_blob
                        FROM public.vw_inventario_agente
                        {base_store_clause}
                        GROUP BY referencia, descripcion, marca
                    ) inventory
                    WHERE ({' OR '.join(inventory_filters)})
                    ORDER BY match_score DESC, stock_total DESC NULLS LAST, descripcion ASC NULLS LAST
                    LIMIT 25
                    """
                ),
                params,
            ).mappings().all()

            if rows:
                ranked_rows = []
                primary_term = normalize_reference_value(core_terms[0]) if core_terms else ""
                preferred_family_terms = expand_product_terms([primary_term]) if primary_term else []
                for row in rows:
                    candidate = dict(row)
                    candidate_text = " ".join(
                        value
                        for value in [candidate.get("descripcion"), candidate.get("referencia"), candidate.get("marca")]
                        if value
                    )
                    candidate_presentation = infer_product_presentation_from_row(candidate)
                    candidate_brand = infer_product_brand_from_row(candidate)
                    candidate["fuzzy_score"] = round(sequence_similarity(normalized_query, candidate_text), 4)
                    candidate["family_score"] = 1 if any(term and term in normalize_text_value(candidate_text) for term in preferred_family_terms[:5]) else 0
                    candidate["presentation_score"] = 1 if product_request.get("requested_unit") and candidate_presentation == product_request.get("requested_unit") else 0
                    candidate["brand_score"] = 1 if brand_filters and candidate_brand in brand_filters else 0
                    ranked_rows.append(candidate)
                ranked_rows.sort(
                    key=lambda item: (
                        item.get("presentation_score") or 0,
                        item.get("brand_score") or 0,
                        item.get("family_score") or 0,
                        item.get("match_score") or 0,
                        item.get("fuzzy_score") or 0,
                        parse_numeric_value(item.get("stock_total")) or 0,
                    ),
                    reverse=True,
                )
                if product_request.get("requested_unit"):
                    exact_presentation_rows = [
                        item for item in ranked_rows
                        if infer_product_presentation_from_row(item) == product_request.get("requested_unit")
                    ]
                    if exact_presentation_rows:
                        ranked_rows = exact_presentation_rows
                if any((parse_numeric_value(item.get("stock_total")) or 0) > 0 for item in ranked_rows):
                    ranked_rows = [item for item in ranked_rows if (parse_numeric_value(item.get("stock_total")) or 0) > 0]
                return ranked_rows[:5]

            sales_filters = []
            sales_scores = []
            for index, term in enumerate(query_terms):
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
                params,
            ).mappings().all()

            return [dict(row) for row in sales_rows]
    except Exception:
        return []


def build_verification_challenge():
    return (
        "Para revisar cartera, ventas u otra informacion sensible necesito validar tu identidad. "
        "Por favor enviame tu cedula o NIT sin puntos ni comas para continuar."
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
                "Nunca reveles cartera, saldos, ventas historicas o datos privados si verification_state.verified es falso. En ese caso pide cedula o NIT. "
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
                if detected_intent == "consulta_general" and is_product_code_message(content):
                    previous_product_request = conversation_context.get("last_product_request") or {}
                    if conversation_context.get("last_direct_intent") == "consulta_productos" or previous_product_request.get("search_terms"):
                        detected_intent = "consulta_productos"
                if detected_intent == "consulta_general" and has_temporal_reference(content):
                    previous_intent = conversation_context.get("last_direct_intent") or conversation_context.get("intent")
                    if previous_intent in {"consulta_compras", "consulta_cartera"}:
                        detected_intent = previous_intent
                product_request = extract_product_request(content)
                pending_product_clarification = conversation_context.get("pending_product_clarification") or []
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

                document_candidate = None
                if detected_intent != "consulta_productos":
                    document_candidate = extract_document_candidate(content)
                if document_candidate:
                    try:
                        verified_context = find_cliente_contexto_by_document(document_candidate)
                    except Exception:
                        verified_context = None
                    if verified_context:
                        cliente_id = update_contact_cliente(context["contact_id"], verified_context.get("cliente_codigo"))
                        context["cliente_id"] = cliente_id
                        update_conversation_context(
                            context["conversation_id"],
                            {
                                "verified": True,
                                "verified_document": document_candidate,
                                "verified_cliente_codigo": verified_context.get("cliente_codigo"),
                            },
                        )
                        conversation_context.update(
                            {
                                "verified": True,
                                "verified_document": document_candidate,
                                "verified_cliente_codigo": verified_context.get("cliente_codigo"),
                                "awaiting_verification": False,
                            }
                        )
                    else:
                        phone_fallback = find_cliente_contexto_by_phone(context["telefono_e164"])
                        if phone_fallback:
                            verified_context = phone_fallback
                            cliente_id = update_contact_cliente(context["contact_id"], phone_fallback.get("cliente_codigo"))
                            context["cliente_id"] = cliente_id
                            update_conversation_context(
                                context["conversation_id"],
                                {
                                    "verified": True,
                                    "verified_by": "phone",
                                    "verified_cliente_codigo": phone_fallback.get("cliente_codigo"),
                                },
                            )
                            conversation_context.update(
                                {
                                    "verified": True,
                                    "verified_cliente_codigo": phone_fallback.get("cliente_codigo"),
                                    "awaiting_verification": False,
                                }
                            )
                        else:
                            invalid_doc_text = (
                                f"No encontré el documento {document_candidate} en nuestro sistema. "
                                "Verifica que sea tu cédula o NIT registrado, sin puntos ni comas. "
                                "Si no estás seguro, dime tu nombre y te ayudo a buscarlo. "
                                "Mientras tanto, puedo ayudarte con consultas de inventario y productos."
                            )
                            outbound_payload = None
                            try:
                                outbound_payload = send_whatsapp_text_message(context["telefono_e164"], invalid_doc_text)
                                provider_message_id = None
                                if outbound_payload.get("messages"):
                                    provider_message_id = outbound_payload["messages"][0].get("id")
                                store_outbound_message(
                                    context["conversation_id"],
                                    provider_message_id,
                                    "text",
                                    invalid_doc_text,
                                    outbound_payload,
                                    intent_detectado="documento_no_validado",
                                )
                            except Exception as exc:
                                store_outbound_message(
                                    context["conversation_id"],
                                    None,
                                    "system",
                                    f"No fue posible enviar respuesta de documento no validado: {exc}",
                                    {"error": str(exc), "response_text": invalid_doc_text},
                                    intent_detectado="documento_no_validado",
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
                    )
                    response_text = build_verification_success_reply(context.get("nombre_visible"), cliente_contexto)
                    if direct_result:
                        response_text = f"{response_text} {direct_result['response_text']}"
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
                            "verified_document": conversation_context.get("verified_document") or document_candidate,
                            "verified_cliente_codigo": cliente_contexto.get("cliente_codigo") if cliente_contexto else None,
                            "awaiting_verification": False,
                            "pending_intent": None,
                            "pending_question": None,
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

                product_context = lookup_product_context(content, product_request) if is_product_intent_message(content) else []

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