"""
Turn Context Builder — Inyección dinámica de estado por turno.

En vez de que el LLM gestione estado leyendo 900 líneas de reglas,
Python analiza la conversación y le inyecta un brief de ~15 líneas
que le dice EXACTAMENTE qué hacer en este turno.
"""

import json
import re
import logging
import time
import hashlib
from typing import Optional

logger = logging.getLogger("agent_context")

_EXPERT_DIRECTIVE_INTENTS = {"asesoria", "pedido_directo", "cotizacion", "confirmacion", "correccion", "reclamo"}

# ─── Cache de embeddings por turno (evita llamadas redundantes a OpenAI) ──────
# TTL de 120s: si el mismo semantic_query se repite en menos de 2 min, reutiliza el embedding.
_EMBEDDING_CACHE: dict[str, tuple[list[float], float]] = {}
_EMBEDDING_CACHE_TTL = 120  # seconds
_EMBEDDING_CACHE_MAX = 50   # max entries

def _get_cached_embedding(text: str) -> Optional[list[float]]:
    """Retorna embedding cacheado si existe y no expiró."""
    key = hashlib.md5(text.encode()).hexdigest()
    entry = _EMBEDDING_CACHE.get(key)
    if entry and (time.time() - entry[1]) < _EMBEDDING_CACHE_TTL:
        return entry[0]
    return None

def _set_cached_embedding(text: str, embedding: list[float]):
    """Guarda embedding en cache con timestamp."""
    # Evict oldest if cache is full
    if len(_EMBEDDING_CACHE) >= _EMBEDDING_CACHE_MAX:
        oldest_key = min(_EMBEDDING_CACHE, key=lambda k: _EMBEDDING_CACHE[k][1])
        del _EMBEDDING_CACHE[oldest_key]
    key = hashlib.md5(text.encode()).hexdigest()
    _EMBEDDING_CACHE[key] = (embedding, time.time())


# ─── Alertas críticas de superficie (Python-side, imposibles de ignorar) ─────
# Estas reglas son DURAS: si Python las detecta, el LLM las recibe como bloqueo.
# El RAG puede fallar en comunicarlas porque quedan enterradas en chunks de texto.
# Aquí se inyectan ANTES de la instrucción del turno → prioridad absoluta.

_SURFACE_CRITICAL_ALERTS: list[dict] = [
    {
        "surfaces": ["concreto", "piso", "piso industrial", "piso vehicular"],
        "conditions": ["superficie nueva", "sin pintar", None],
        "alert": (
            "🚨 ALERTA CRÍTICA DE SUPERFICIE: El concreto nuevo exige MÍNIMO 28 DÍAS de curado "
            "antes de aplicar cualquier recubrimiento. ANTES de recomendar productos, DEBES "
            "informar esto al cliente y preguntar: '¿Hace cuánto fue vaciado el concreto?' "
            "Si tiene menos de 28 días → NO recomiendes aplicar. La humedad residual del "
            "concreto causará FALLA por ampollamiento, descascaramiento y pérdida de adherencia."
        ),
    },
    {
        "surfaces": ["metal", "metal/inmersión", "reja"],
        "conditions": ["óxido", None],
        "alert": (
            "🚨 ALERTA CRÍTICA DE SUPERFICIE: Metal con óxido requiere preparación mecánica "
            "OBLIGATORIA antes de cualquier recubrimiento. DEBES preguntar el GRADO de oxidación "
            "(leve/moderado/severo) y recomendar lija, disco flap o grata según corresponda. "
            "Sin preparación correcta, CUALQUIER anticorrosivo fallará por falta de adherencia."
        ),
    },
    {
        "surfaces": ["interior húmedo", "muro", "interior"],
        "conditions": ["humedad", "salitre", "filtración", "goteras", "moho/hongos", "pintura descascarando", "pintura soplada"],
        "alert": (
            "🚨 ALERTA CRÍTICA DE SUPERFICIE: Problema de humedad detectado. ANTES de recomendar "
            "pintura, DEBES diagnosticar la CAUSA de la humedad (capilaridad, filtración, "
            "condensación). Si la fuente no se elimina, cualquier recubrimiento fallará. "
            "Pregunta: '¿La humedad viene de adentro del muro, de arriba, o aparece por temporada?' "
            "Si además hay salitre o pintura soplada/descascarada, debes indicar que la base dañada "
            "se remueve por completo antes del sistema nuevo."
        ),
    },
    {
        "surfaces": ["fachada", "exterior"],
        "conditions": ["pintura descascarando", "pintura soplada"],
        "alert": (
            "🚨 ALERTA CRÍTICA DE SUPERFICIE: Fachada con pintura en mal estado. ANTES de "
            "recomendar repintura, DEBES indicar que se necesita REMOVER la pintura suelta "
            "completamente (raspar, lijar, hidrolavado). Aplicar sobre pintura soplada causa "
            "falla inmediata. Pregunta al cliente cómo piensa preparar la superficie."
        ),
    },
    {
        "surfaces": ["madera", "madera exterior", "madera/metal"],
        "conditions": ["superficie nueva", "sin pintar", None],
        "alert": (
            "⚠️ ALERTA DE SUPERFICIE: Madera nueva requiere verificar contenido de humedad "
            "(máximo 18%) antes de aplicar recubrimiento. PREGUNTA al cliente si la madera es "
            "nueva/seca o si estuvo expuesta a lluvia. Madera húmeda → dejar secar primero."
        ),
    },
    {
        "surfaces": ["piso deportivo"],
        "conditions": [None],
        "alert": (
            "⚠️ ALERTA DE SUPERFICIE: Pisos deportivos (canchas) requieren productos "
            "específicos con resistencia a abrasión y tráfico. NUNCA recomendar Pintucoat, "
            "Interseal ni recubrimientos industriales. El producto correcto es Pintura para "
            "Canchas de Pintuco. Si es concreto nuevo → aplica regla de 28 días de curado."
        ),
    },
]


# ─── Protocolos técnicos por clase de problema ─────────────────────────────
# Esta capa evita depender de casos aislados o del wording exacto del cliente.
# Primero se infiere la CLASE DEL PROBLEMA, luego se inyecta un protocolo operativo.
_PROBLEM_PROTOCOLS: dict[str, dict] = {
    "humedad_interior_capilaridad": {
        "summary": "Muro interior con humedad/salitre por capilaridad o presión negativa.",
        "required_questions": [
            "Confirmar si la humedad viene de la base del muro, del piso o de una jardinera/exterior.",
            "Confirmar si el revoque/base está quemado, meteorizado o soplado.",
            "Pedir m² reales antes de cualquier cotización.",
        ],
        "required_system": [
            "Remover pintura suelta, salitre y base dañada hasta sustrato sano.",
            "Si el revoque está malo, reemplazarlo antes del sistema nuevo.",
            "Aplicar Aquablock Ultra en 2 manos.",
            "Aplicar Estuco Acrílico para Exterior/Humedad después del Aquablock (en ERP suele resolverse como estuco prof ext).",
            "Cerrar con vinilo interior compatible; si el cliente pide economía, solo cambia el vinilo final.",
        ],
        "forbidden_shortcuts": [
            "No usar Koraza como imprimante ni como acabado interior.",
            "No cotizar por galones propuestos por el cliente sin metraje.",
            "No saltar Aquablock + Estuco.",
        ],
        "pricing_gate": "m2_required",
    },
    "humedad_interior_general": {
        "summary": "Muro interior con humedad o salitre que requiere diagnóstico de causa antes de pintar.",
        "required_questions": [
            "Preguntar de dónde viene la humedad: piso, arriba, lateral o por temporada.",
            "Preguntar si la base está soplada, descascarada o meteorizada.",
            "Pedir m² reales antes de cotizar.",
        ],
        "required_system": [
            "Diagnosticar la causa.",
            "Definir si corresponde Aquablock/Sellamur como base técnica.",
            "Nivelar con Estuco Acrílico para Exterior/Humedad cuando aplique (en ERP suele resolverse como estuco prof ext).",
            "Cerrar con vinilo interior compatible.",
        ],
        "forbidden_shortcuts": [
            "No usar Koraza como sellador de humedad interior.",
            "No cotizar de una sin m².",
        ],
        "pricing_gate": "m2_required",
    },
    "fachada_exterior": {
        "summary": "Fachada o muro exterior expuesto a intemperie.",
        "required_questions": [
            "Preguntar si la base está pelada/soplada o si es obra nueva.",
            "Pedir m² antes de cotizar.",
        ],
        "required_system": [
            "Preparación completa de la base.",
            "Estuco/grietas si aplica.",
            "Acabado exterior tipo Koraza o vinilo exterior según desempeño.",
        ],
        "forbidden_shortcuts": [
            "No pintar sobre base soplada.",
        ],
        "pricing_gate": "m2_required",
    },
    "metal_oxidado": {
        "summary": "Metal con oxidación que requiere preparación mecánica y sistema anticorrosivo completo.",
        "required_questions": [
            "Preguntar el grado de oxidación.",
            "Preguntar si es interior o exterior.",
            "Pedir m² o dimensiones antes de cotizar sistema completo.",
        ],
        "required_system": [
            "Preparación mecánica.",
            "Convertidor/anticorrosivo según estado.",
            "Acabado compatible con la exposición.",
        ],
        "forbidden_shortcuts": [
            "No dejar solo anticorrosivo si el sistema exige acabado.",
        ],
        "pricing_gate": "m2_required",
    },
    "piso_industrial": {
        "summary": "Piso industrial o de concreto que requiere protocolo diagnóstico completo.",
        "required_questions": [
            "Estado del piso: nuevo, viejo o ya pintado.",
            "Curado de 28 días si es concreto nuevo.",
            "Tipo de tráfico y si es interior/exterior.",
            "m² reales antes de cotizar.",
        ],
        "required_system": [
            "Definir imprimante correcto.",
            "Definir acabado según tráfico.",
            "Agregar cuarzo/catalizadores si corresponde.",
        ],
        "forbidden_shortcuts": [
            "No cotizar sin m².",
            "No usar imprimantes incorrectos por analogía.",
        ],
        "pricing_gate": "m2_required",
    },
}


def _infer_problem_class(diagnostic: dict, user_message: str) -> Optional[str]:
    """Clasifica el problema técnico en una familia reusable para activar protocolos."""
    surface = diagnostic.get("surface")
    condition = diagnostic.get("condition")
    location = diagnostic.get("interior_exterior")
    humidity_source = diagnostic.get("humidity_source")
    lowered = (user_message or "").lower()

    if surface == "interior húmedo":
        if humidity_source == "capilaridad/presión negativa" or any(token in lowered for token in ["jardinera", "viene del piso", "sube del piso", "capilaridad"]):
            return "humedad_interior_capilaridad"
        return "humedad_interior_general"

    if surface in ("fachada", "exterior") or location == "exterior":
        return "fachada_exterior"

    if surface in ("metal", "reja", "metal/inmersión") and condition == "óxido":
        return "metal_oxidado"

    if surface in ("piso", "piso industrial", "piso vehicular", "piso deportivo"):
        return "piso_industrial"

    return None


def _build_problem_protocol_lines(problem_class: Optional[str]) -> list[str]:
    if not problem_class:
        return []
    protocol = _PROBLEM_PROTOCOLS.get(problem_class)
    if not protocol:
        return []

    lines = []
    lines.append("")
    lines.append("═══ PROTOCOLO DEL CASO ═══")
    lines.append(f"Clase de problema: {problem_class}")
    lines.append(f"Resumen: {protocol['summary']}")
    if protocol.get("required_questions"):
        lines.append("Preguntas obligatorias:")
        for question in protocol["required_questions"]:
            lines.append(f"  • {question}")
    if protocol.get("required_system"):
        lines.append("Estructura mínima de solución:")
        for step in protocol["required_system"]:
            lines.append(f"  • {step}")
    if protocol.get("forbidden_shortcuts"):
        lines.append("Atajos prohibidos:")
        for shortcut in protocol["forbidden_shortcuts"]:
            lines.append(f"  • {shortcut}")
    if protocol.get("pricing_gate") == "m2_required":
        lines.append("No cotizar hasta tener m² reales del área.")
    lines.append("══════════════════════════")
    return lines


def _build_structured_diagnostic_summary(problem_class: Optional[str], diagnostic: dict, user_message: str) -> list[str]:
    if not problem_class:
        return []

    lowered = (user_message or "").lower()
    protocol = _PROBLEM_PROTOCOLS.get(problem_class, {})
    confidence = "baja"
    confidence_signals = 0

    signal_map = {
        "humedad_interior_capilaridad": ["humedad", "salitre", "jardinera", "capilaridad", "sube del piso", "base del muro"],
        "humedad_interior_general": ["humedad", "salitre", "interior", "pared", "muro"],
        "fachada_exterior": ["fachada", "exterior", "intemperie", "lluvia"],
        "metal_oxidado": ["metal", "reja", "óxido", "oxido"],
        "piso_industrial": ["piso", "concreto", "montacargas", "tráfico", "trafico"],
    }
    for token in signal_map.get(problem_class, []):
        if token in lowered:
            confidence_signals += 1

    if confidence_signals >= 4:
        confidence = "alta"
    elif confidence_signals >= 2:
        confidence = "media"

    validations = protocol.get("required_questions") or []
    lines = []
    lines.append("")
    lines.append("═══ DIAGNÓSTICO ESTRUCTURADO ═══")
    lines.append(f"problem_class={problem_class}")
    lines.append(f"confidence={confidence}")
    lines.append(f"surface={diagnostic.get('surface') or 'sin definir'}")
    lines.append(f"condition={diagnostic.get('condition') or 'sin definir'}")
    lines.append(f"interior_exterior={diagnostic.get('interior_exterior') or 'sin definir'}")
    lines.append(f"area_m2={diagnostic.get('area_m2') if diagnostic.get('area_m2') is not None else 'pendiente'}")
    lines.append(f"pricing_ready={'sí' if diagnostic.get('area_m2') else 'no'}")
    if validations:
        lines.append("Validaciones pendientes:")
        for validation in validations:
            lines.append(f"  • {validation}")
    lines.append("════════════════════════════════")
    return lines


def _get_surface_alerts(surface: Optional[str], condition: Optional[str]) -> list[str]:
    """Retorna alertas críticas que aplican a la combinación superficie+condición.
    Intenta cargar desde DB (extensible); fallback a hardcoded si DB no disponible."""
    if not surface:
        return []

    # Try loading from DB first (Rec 3: extensible via DB)
    db_alerts = _load_surface_alerts_from_db()
    rules = db_alerts if db_alerts else _SURFACE_CRITICAL_ALERTS

    alerts = []
    for rule in rules:
        if surface not in rule["surfaces"]:
            continue
        # Check condition match: None in conditions means "siempre aplica para esta superficie"
        rule_conditions = rule["conditions"]
        if None in rule_conditions:
            alerts.append(rule["alert"])
        elif condition and condition in rule_conditions:
            alerts.append(rule["alert"])
    return alerts


def _load_surface_alerts_from_db() -> list[dict]:
    """Load extensible surface alerts from DB via main.fetch_surface_alerts_from_db()."""
    try:
        try:
            from main import fetch_surface_alerts_from_db
        except ImportError:
            from backend.main import fetch_surface_alerts_from_db
        return fetch_surface_alerts_from_db()
    except Exception:
        return []


# ─── Búsqueda semántica de conocimiento experto para inyección en Turn Context ─

def _fetch_expert_directives_for_turn(
    user_message: str,
    diagnostic: dict,
    intent: str,
) -> list[dict]:
    """
    Busca conocimiento experto relevante para el turno actual usando embeddings.
    Se ejecuta ANTES del LLM para inyectar directrices como "Directriz de Gerencia".
    
    Estrategia híbrida:
    1. Búsqueda semántica con pgvector (embedding del mensaje + diagnóstico)
    2. Fallback a substring matching clásico si pgvector falla
    3. Solo retorna directrices con score alto (no ruido)
    """
    # Skip for intents that don't need expert knowledge
    if intent in ("saludo", "despedida", "identidad", "bi_interno", "documento"):
        return []

    # Build a semantic query from diagnostic context + user message
    query_parts = []
    if diagnostic.get("surface"):
        query_parts.append(diagnostic["surface"])
    if diagnostic.get("condition"):
        query_parts.append(diagnostic["condition"])
    if diagnostic.get("interior_exterior"):
        query_parts.append(diagnostic["interior_exterior"])
    if diagnostic.get("humidity_source"):
        query_parts.append(diagnostic["humidity_source"])
    problem_class = _infer_problem_class(diagnostic, user_message)
    if problem_class:
        query_parts.append(problem_class)
    if diagnostic.get("traffic"):
        query_parts.append(f"tráfico {diagnostic['traffic']}")
    # Add relevant terms from user message (not the whole thing to avoid noise)
    msg_lower = (user_message or "").lower()
    query_parts.append(msg_lower[:200])
    
    semantic_query = " ".join(query_parts).strip()
    if len(semantic_query) < 5:
        return []

    try:
        directives = _search_expert_knowledge_semantic(semantic_query, limit=3)
        if directives:
            return directives
        # Fallback: keyword-based search using main.py's function
        return _search_expert_knowledge_keyword_fallback(semantic_query, limit=3)
    except Exception as exc:
        logger.debug("_fetch_expert_directives_for_turn error: %s", exc)
        return []


def _search_expert_knowledge_semantic(query: str, limit: int = 3) -> list[dict]:
    """
    Búsqueda semántica de conocimiento experto usando pgvector.
    Embebe la consulta y busca contra embeddings pre-computados de las notas.
    Si la tabla no tiene columna embedding, cae al fallback de keywords.
    """
    try:
        # Import lazily to avoid circular dependency
        try:
            from main import get_openai_client, get_db_engine
        except ImportError:
            from backend.main import get_openai_client, get_db_engine

        # Generate embedding for the query (with cache)
        query_input = query.strip()[:500]
        query_embedding = _get_cached_embedding(query_input)
        if query_embedding is None:
            client = get_openai_client()
            resp = client.embeddings.create(
                model="text-embedding-3-small",
                input=query_input,
                dimensions=1536,
            )
            query_embedding = resp.data[0].embedding
            _set_cached_embedding(query_input, query_embedding)
        embedding_literal = "[" + ",".join(str(v) for v in query_embedding) + "]"

        engine = get_db_engine()
        raw_conn = engine.raw_connection()
        try:
            cur = raw_conn.cursor()
            # Check if embedding column exists in expert_knowledge
            cur.execute("""
                SELECT column_name FROM information_schema.columns 
                WHERE table_name = 'agent_expert_knowledge' 
                AND column_name = 'embedding'
            """)
            has_embedding = cur.fetchone() is not None

            if not has_embedding:
                return []  # Fall to keyword fallback

            cur.execute(
                """
                SELECT id, contexto_tags, producto_recomendado, producto_desestimado,
                       nota_comercial, tipo, nombre_experto,
                       1 - (embedding <=> %s::vector) AS similarity
                FROM public.agent_expert_knowledge
                WHERE activo = true
                  AND embedding IS NOT NULL
                ORDER BY embedding <=> %s::vector
                LIMIT %s
                """,
                [embedding_literal, embedding_literal, limit * 2],
            )
            columns = [desc[0] for desc in cur.description]
            rows = [dict(zip(columns, row)) for row in cur.fetchall()]
            
            # Only return rows with high semantic similarity (>= 0.45)
            # — lower than RAG threshold because expert notes are short texts
            strong = [r for r in rows if (r.get("similarity") or 0) >= 0.45]
            return strong[:limit]
        finally:
            raw_conn.close()
    except Exception as exc:
        logger.debug("_search_expert_knowledge_semantic error: %s", exc)
        return []


def _search_expert_knowledge_keyword_fallback(query: str, limit: int = 3) -> list[dict]:
    """
    Fallback: búsqueda keyword contra cache in-memory de main.py.
    Solo retorna resultados con score >= 2 (mínimo 2 terms match).
    """
    try:
        try:
            from main import fetch_expert_knowledge
        except ImportError:
            from backend.main import fetch_expert_knowledge
        
        results = fetch_expert_knowledge(query, limit=limit + 2)
        # fetch_expert_knowledge ya hace scoring por terms.
        # Solo retornamos si hay suficiente overlap (el score viene implícito en el orden)
        return results[:limit]
    except Exception:
        return []

# ─── Patrones de detección de intención ──────────────────────────────────────

_GREETING_PATTERNS = re.compile(
    r"^\s*(hola\s*,?\s*(?:buenas?\s*(?:tardes?|noches?|d[ií]as?))?|"
    r"buenas?\s*(?:tardes?|noches?|d[ií]as?)|hey|hi|buenos?\s*d[ií]as?|qu[eé]\s*tal)\s*[.!?]*\s*$",
    re.IGNORECASE,
)

_DIRECT_ORDER_PATTERNS = re.compile(
    r"\d+\s*(galones?|cuñetes?|cuartos?|unidades?|litros?|brochas?|rollos?|metros?|cajas?|"
    r"tarros?|cintas?|latas?|paquetes?|gal|und|uds?)\b",
    re.IGNORECASE,
)

_SHORT_REFERENCE_PATTERNS = re.compile(r"\b(?:[a-z]{1,4}\d{1,4}|\d{3,6})\b", re.IGNORECASE)

_SPECIFIC_PRODUCTS = [
    "koraza", "viniltex", "pintucoat", "intervinil", "pinturama",
    "interseal", "intergard", "interthane", "corrotec", "pintóxido", "pintoxido",
    "pintulux", "barnex", "barniz marino", "esmalte doméstico", "esmalte domestico",
    "aquablock", "sellamur", "wood stain", "pintura canchas", "wash primer",
    "primer 50rs", "pintuco fill", "pintutraf", "doméstico", "domestico",
    "1550", "1551", "poliuretano alto", "intergard 740", "intergard 2002",
    "sealer f100", "interchar", "sd1", "sd-1", "tu11", "teu11", "teu95",
    "tu95", "brocha goya", "brocha profesional goya", "goya profesional",
]

_COMMERCIAL_PRODUCT_SIGNALS = [
    "viniltex", "pintulux", "koraza", "barniz", "sd1", "sd-1", "tu11", "teu11",
    "teu95", "tu95", "brocha", "goya", "rodillo", "lija", "cinta", "estuco",
    "sellador", "pintucoat", "interseal", "intergard", "interthane", "corrotec",
]

_ADVISORY_SIGNALS = [
    "pintar", "impermeabilizar", "proteger", "recubrir", "barnizar", "lacar",
    "qué le aplico", "que le aplico", "qué sistema", "que sistema",
    "cómo pinto", "como pinto", "me recomiendas", "qué necesito",
    "que necesito", "asesoría", "asesoria", "asesorame",
    "qué se hace", "que se hace", "qué le echo", "que le echo",
    "se está descascarando", "se esta descascarando", "se pela",
    "se está pelando", "se esta pelando",
]

_SURFACE_SIGNALS = [
    "piso", "fachada", "techo", "muro", "pared", "reja", "estructura",
    "madera", "puerta", "mueble", "mesa", "bodega", "garaje", "terraza",
    "baño", "cocina", "cancha", "metal", "tanque", "cubierta", "cielo raso",
    "pergola", "pérgola", "sendero", "cicloruta", "nave", "planta",
    "tubería", "tuberia", "tubo", "galvanizado", "galvanizada",
]

_CONDITION_SIGNALS = [
    "humedad", "filtra", "gotea", "moho", "hongo", "salitre", "óxido", "oxido",
    "descascar", "pela", "sopla", "grieta", "entiza", "llueve", "ampolla",
    "nuevo", "viejo", "pintado", "sin pintar", "deterioro",
    "vapor", "condensación", "condensacion",
]

_CLAIM_SIGNALS = [
    "reclamo", "garantía", "garantia", "problema con", "se me dañó",
    "se me daño", "falló", "fallo", "defecto", "no sirvió", "no sirvio",
    "no me funcionó", "no me funciono", "se peló", "se pelo",
    "se descascaró", "se descascaro", "queja",
]

_BI_SIGNALS = [
    "ventas", "cuánto llevo", "cuanto llevo", "facturación", "facturacion",
    "cómo voy", "como voy", "vendí", "vendi", "cuánto vendí", "cuanto vendi",
    "cartera de", "compras de", "compras acumuladas",
]

_PRICE_SIGNALS = [
    "cotízame", "cotizame", "cotización", "cotizacion", "precio", "precios",
    "cuánto cuesta", "cuanto cuesta", "cuánto vale", "cuanto vale",
    "cuánto me sale", "cuanto me sale", "dame precios", "valor",
]

_INVENTORY_SIGNALS = [
    "inventario", "stock", "disponible", "disponibilidad", "tenemos", "hay",
]


def _looks_like_direct_commercial_batch(message: str) -> bool:
    lines = [line.strip() for line in re.split(r"[\r\n]+", message or "") if line.strip()]
    if len(lines) < 2:
        return False

    commercial_lines = 0
    for line in lines[:12]:
        lowered = line.lower()
        has_quantity = bool(_DIRECT_ORDER_PATTERNS.search(line) or re.match(r"^\s*\d+(?:[.,]\d+)?\b", line))
        has_reference = bool(_SHORT_REFERENCE_PATTERNS.search(lowered))
        has_product_signal = any(token in lowered for token in _COMMERCIAL_PRODUCT_SIGNALS)
        if has_quantity and (has_reference or has_product_signal):
            commercial_lines += 1

    return commercial_lines >= 2

_FAREWELL_PATTERNS = re.compile(
    r"^\s*(gracias|muchas gracias|listo|perfecto|ok|está bien|esta bien|"
    r"eso es todo|nos vemos|chao|adiós|adios|hasta luego|bye)\s*[.!?]*\s*$",
    re.IGNORECASE,
)

_CONFIRMATION_PATTERNS = re.compile(
    r"^\s*(s[ií]|dale|claro|por favor|listo|confirmo|sí por favor|si por favor|"
    r"perfecto|de una|vamos|hagale|procede|confirma)\s*[.!?]*\s*$",
    re.IGNORECASE,
)

_CORRECTION_PATTERNS = re.compile(
    r"cambia\w*\s+.+\s+por\s+|no\s+es\s+.+\s+(?:es|sino)\s+|"
    r"(?:quita|elimina|saca)\s+|(?:agrega|añade|pon)\s+|en\s+vez\s+de\s+|"
    r"son\s+\d+\s+no\s+\d+|deja\s+as[ií]",
    re.IGNORECASE,
)

_COMMERCIAL_CLOSE_SIGNALS = [
    "pdf", "cotizacion", "cotización", "genera", "generar", "envia", "enví", "manda",
    "procede", "confirma", "cerrar", "cotiza", "cotizar", "cotizame", "cotízame",
]


def _draft_item_display_label(item: dict) -> str:
    if item.get("audit_label"):
        return str(item["audit_label"])
    reference_value = item.get("referencia") or item.get("codigo_articulo") or item.get("codigo") or "sin referencia"
    description = (
        item.get("descripcion_exacta")
        or item.get("descripcion_comercial")
        or item.get("descripcion")
        or item.get("original_text")
        or "Producto"
    )
    description = re.sub(r"\s+", " ", str(description).strip())
    return f"[{reference_value}] - {description}"


def _extract_commercial_customer_identity_like_text(message: str) -> str:
    raw_value = (message or "").strip()
    if not raw_value:
        return ""
    compact_value = " ".join(raw_value.split()).strip(" ,.;:-")
    if re.fullmatch(r"\d{6,15}", compact_value):
        return compact_value

    patterns = [
        r"^(?:para|va\s+para|seria\s+para|sería\s+para|a\s+nombre\s+de)\s+(.+)$",
        r"^(?:cc|c\.c\.|cedula|cédula|nit|nif)\s*[:#-]?\s*(.+)$",
    ]
    for pattern in patterns:
        match = re.match(pattern, compact_value, flags=re.IGNORECASE)
        if not match:
            continue
        candidate = match.group(1).strip(" ,.;:-")
        if candidate:
            return candidate
    return ""


def _has_ready_commercial_draft(conversation_context: dict) -> bool:
    commercial_draft = conversation_context.get("commercial_draft") or {}
    draft_intent = commercial_draft.get("tipo_documento") or commercial_draft.get("intent")
    items = commercial_draft.get("items") or []
    if draft_intent not in {"pedido", "cotizacion"} or not items:
        return False
    return all(item.get("status") == "matched" for item in items)


# ─── Clasificación de intención ─────────────────────────────────────────────

def classify_intent(user_message: str, conversation_context: dict, recent_messages: list, internal_auth: dict) -> str:
    """
    Clasifica la intención del usuario en una de estas categorías:
    - saludo
    - pedido_directo (nombra productos + cantidades)
    - asesoria (describe superficie/necesidad genérica)
    - cotizacion (pide precios de algo ya discutido)
    - confirmacion (acepta cotización/pedido)
    - correccion (modifica un ítem de cotización activa)
    - reclamo
    - bi_interno (consultas de ventas/cartera para empleados)
    - documento (pide ficha técnica)
    - identidad (da cédula/NIT)
    - despedida
    - general (todo lo demás)
    """
    msg = (user_message or "").strip()
    msg_lower = msg.lower()
    diagnostic = extract_diagnostic_data(user_message, recent_messages)
    diagnostic_surface = diagnostic.get("surface")
    diagnostic_condition = diagnostic.get("condition")
    diagnostic_location = diagnostic.get("interior_exterior")
    diagnostic_surface_without_location = {
            "fachada", "exterior", "madera exterior", "piso deportivo"
    }
    has_structured_diagnostic = bool(
        diagnostic_surface
        and diagnostic_condition
        and (diagnostic_location or diagnostic_surface in diagnostic_surface_without_location)
    )

    # 1. Greeting
    if _GREETING_PATTERNS.match(msg):
        return "saludo"

    # 2. Farewell
    if _FAREWELL_PATTERNS.match(msg):
        return "despedida"

    # 3. Claims
    if any(s in msg_lower for s in _CLAIM_SIGNALS):
        return "reclamo"

    # 4. BI internal (employee only)
    if internal_auth and any(s in msg_lower for s in _BI_SIGNALS):
        return "bi_interno"

    # 5. Document request
    if any(kw in msg_lower for kw in ["ficha técnica", "ficha tecnica", "hoja de seguridad", "fds", "msds"]):
        return "documento"

    # 6. Commercial close follow-up (identity/PDF after a resolved draft)
    if _has_ready_commercial_draft(conversation_context):
        customer_candidate = _extract_commercial_customer_identity_like_text(msg)
        if customer_candidate:
            return "confirmacion"
        if any(signal in msg_lower for signal in _COMMERCIAL_CLOSE_SIGNALS):
            return "confirmacion"

    # 7. Identity (pure numeric 6-15 digits)
    if re.match(r"^\d{6,15}$", msg.strip()):
        pending = conversation_context.get("pending_intent")
        if pending:
            return "identidad"

    # 8. Correction (if last bot msg was a quotation)
    last_bot = _get_last_bot_message(recent_messages)
    if last_bot and "$" in last_bot and _CORRECTION_PATTERNS.search(msg_lower):
        return "correccion"

    # 9. Confirmation (short affirmative after quotation)
    if last_bot and "$" in last_bot and _CONFIRMATION_PATTERNS.match(msg):
        return "confirmacion"

    # 10. Direct order (names specific products + quantities)
    has_specific = any(p in msg_lower for p in _SPECIFIC_PRODUCTS)
    has_quantity = bool(_DIRECT_ORDER_PATTERNS.search(msg))
    has_price_request = any(s in msg_lower for s in _PRICE_SIGNALS)
    has_condition = any(s in msg_lower for s in _CONDITION_SIGNALS)
    has_surface = any(s in msg_lower for s in _SURFACE_SIGNALS)
    has_inventory_request = any(s in msg_lower for s in _INVENTORY_SIGNALS)
    has_reference_like = has_specific or bool(_SHORT_REFERENCE_PATTERNS.search(msg_lower))

    if _looks_like_direct_commercial_batch(msg):
        return "pedido_directo"

    # Si el cliente describe una condición problemática CON una superficie,
    # SIEMPRE es asesoría técnica — incluso si nombra un producto específico.
    # Ejemplo: "le aplicaron esmalte a la tubería galvanizada y se descascara" = ASESORÍA
    if has_condition and has_surface:
        return "asesoria"

    if has_inventory_request and has_reference_like and not has_price_request and not has_condition:
        return "consulta_productos"

    # Si el cliente nombra un producto PERO describe una condición problemática
    # (humedad, salitre, óxido, descascarada, etc.), la intención es ASESORÍA.
    # El cliente necesita un sistema completo, no solo el producto que pidió.
    if has_specific and has_condition:
        return "asesoria"

    if has_specific and has_quantity:
        return "pedido_directo"
    if has_specific and has_price_request:
        return "pedido_directo"

    # 10.5 Structured follow-up diagnosis
    # If Python can already infer a usable technical case from the current turn + history,
    # force advisory intent even when the wording is brief or follow-up style.
    if has_structured_diagnostic:
        return "asesoria"

    # 11. Advisory (describes surface/need without naming specific product)
    has_advisory = any(s in msg_lower for s in _ADVISORY_SIGNALS)
    if (has_advisory or has_surface) and not has_specific:
        return "asesoria"

    # 12. Quotation request (asks for prices on prior topic)
    if has_price_request:
        return "cotizacion"

    # 13. If names a specific product without quantity → product inquiry unless active draft
    if has_specific:
        if (conversation_context.get("commercial_draft") or {}).get("items"):
            return "pedido_directo"
        return "consulta_productos"

    return "general"


# ─── Extracción de datos diagnósticos ────────────────────────────────────────

def extract_diagnostic_data(user_message: str, recent_messages: list) -> dict:
    """
    Extrae datos diagnósticos de la conversación combinada.
    Retorna dict con claves: surface, condition, interior_exterior, area_m2, traffic, humidity_source
    Valores None si no detectado.
    """
    # Combine last ~5 inbound messages + current
    texts = []
    for msg in recent_messages[-10:]:
        if msg.get("direction") == "inbound":
            texts.append((msg.get("contenido") or "").lower())
    texts.append((user_message or "").lower())
    combined = " ".join(texts)
    combined_surface = combined
    combined_without_negated_exterior = re.sub(
        r"\bno\s+(?:es|era|viene|venia|venía|parece|pareciera)\b[^.\n]{0,80}\b(?:fachada|exterior|lluvia)\b",
        " ",
        combined,
        flags=re.IGNORECASE,
    )
    for level_phrase in [
        "primer piso", "segundo piso", "tercer piso", "cuarto piso", "quinto piso",
        "sexto piso", "septimo piso", "séptimo piso", "octavo piso", "noveno piso",
        "decimo piso", "décimo piso",
    ]:
        combined_surface = combined_surface.replace(level_phrase, " ")

    data = {
        "surface": None,
        "condition": None,
        "interior_exterior": None,
        "area_m2": None,
        "traffic": None,
        "humidity_source": None,
        "substrate_type": None,
    }

    # Surface
    # ── PRIORITY surface signals: metal/galvanizado beats "techo" when both appear ──
    # ("hicimos un techo con tubería galvanizada" = metal, not techo)
    _metal_priority_signals = [
        "galvanizado", "galvanizada", "galvanizad", "tubería", "tuberia", "tubo ",
        "reja", "porton", "portón", "baranda", "estructura metálica", "estructura metalica",
        "lámina", "lamina", "perfil", "angulo", "ángulo",
    ]
    _forced_metal = any(kw in combined for kw in _metal_priority_signals)

    surface_map = {
        "piso": "piso", "fachada": "fachada", "techo": "techo",
        "muro": "muro", "pared": "muro", "reja": "metal",
        "estructura": "metal", "madera": "madera", "puerta": "madera/metal",
        "mueble": "madera", "mesa": "madera", "bodega": "piso industrial",
        "garaje": "piso vehicular", "terraza": "exterior",
        "baño": "interior húmedo", "cocina": "interior", "cancha": "piso deportivo",
        "metal": "metal", "tanque": "metal/inmersión", "cubierta": "techo",
        "cielo raso": "interior", "pergola": "madera exterior",
        "pérgola": "madera exterior",
    }
    _has_wall_context = any(kw in combined for kw in ["pared", "muro", "cielo raso"])
    _has_humidity_context = any(kw in combined for kw in ["humedad", "salitre", "moho", "hongo", "filtra", "gotea", "descascar", "sopla", "vapor", "condensación", "condensacion"])
    _has_exterior_wall_context = any(kw in combined for kw in ["fachada", "exterior", "intemperie", "culata"])

    if _forced_metal:
        data["surface"] = "metal"
    elif _has_wall_context and _has_humidity_context and not _has_exterior_wall_context:
        data["surface"] = "interior húmedo"
    else:
        for kw, surf in surface_map.items():
            if kw in combined_surface:
                data["surface"] = surf
                break

    # Interior/Exterior
    _has_explicit_interior = any(w in combined for w in ["interior", "apartamento", "casa", "oficina", "habitación",
                                      "habitacion", "sala", "cuarto", "dormitorio", "laboratorio",
                                      "consultorio", "clínica", "clinica", "hospital", "restaurante",
                                      "local", "almacén", "almacen", "aula", "colegio",
                                      "baño", "ducha", "cocina"])
    _has_explicit_exterior = any(w in combined_without_negated_exterior for w in ["fachada", "terraza", "exterior", "intemperie", "azotea"])

    if _has_explicit_interior and not _has_explicit_exterior:
        data["interior_exterior"] = "interior"
    elif _has_explicit_exterior:
        data["interior_exterior"] = "exterior"
    elif _has_explicit_interior:
        data["interior_exterior"] = "interior"
    elif any(w in combined for w in ["bodega", "fábrica", "fabrica", "planta", "nave", "taller"]):
        data["interior_exterior"] = "industrial"

    # Condition
    cond_signals = {
        "humedad": "humedad", "salitre": "salitre", "filtra": "filtración", "gotea": "goteras",
        "gotera": "goteras",
        "moho": "moho/hongos", "hongo": "moho/hongos",
        "óxido": "óxido", "oxido": "óxido", "oxidado": "óxido", "oxidada": "óxido",
        "corrosión": "óxido", "corrosion": "óxido", "corrosi": "óxido",
        "descascar": "pintura descascarando", "despega": "pintura descascarando",
        "pelando": "pintura descascarando", "ampollado": "pintura descascarando",
        "ampollada": "pintura descascarando", "levantando": "pintura descascarando",
        "sopla": "pintura soplada", "soplado": "pintura soplada", "soplada": "pintura soplada",
        "grieta": "grietas", "fisura": "grietas",
        "nuevo": "superficie nueva", "nueva": "superficie nueva", "virgen": "superficie nueva",
        "sin pintar": "sin pintar", "pintado": "repintura", "pintada": "repintura",
        "repintar": "repintura", "repintura": "repintura",
        "impermeabilizar": "impermeabilización", "impermea": "impermeabilización",
        "podrido": "madera deteriorada", "podrida": "madera deteriorada",
        "deteriorad": "deteriorada", "dañad": "deteriorada",
    }
    for kw, cond in cond_signals.items():
        if kw in combined:
            data["condition"] = cond
            break

    # Area
    area_match = re.search(r"(\d+)\s*(?:m2|m²|metros?\s*cuadrados?)", combined)
    if area_match:
        data["area_m2"] = int(area_match.group(1))

    # Traffic
    if any(w in combined for w in ["montacarga", "estibador", "carreta", "zorra", "tráfico pesado", "trafico pesado"]):
        data["traffic"] = "pesado"
    elif any(w in combined for w in ["peatonal", "liviano", "residencial", "oficina"]):
        data["traffic"] = "liviano"
    elif any(w in combined for w in ["vehicular", "parqueadero", "garaje"]):
        data["traffic"] = "vehicular"

    if any(w in combined for w in ["viene del piso", "sube del piso", "base del muro", "capilaridad", "jardinera", "jardiner", "presion negativa", "presión negativa", "permanente", "pegado al piso", "desde abajo", "arranca pegado al piso"]):
        data["humidity_source"] = "capilaridad/presión negativa"
    elif any(w in combined_without_negated_exterior for w in ["de arriba", "techo", "cubierta", "canal", "lluvia", "filtracion exterior", "filtración exterior"]):
        data["humidity_source"] = "filtración superior/exterior"
    elif any(w in combined for w in ["temporada", "cuando llueve", "invierno", "solo en lluvia"]):
        data["humidity_source"] = "humedad por temporada"
    elif any(w in combined for w in ["vapor", "ducha", "condensación", "condensacion", "baño", "ventilación", "ventilacion"]):
        data["humidity_source"] = "condensación/vapor (baño o cocina)"

    if (
        any(kw in combined for kw in ["pared", "muro", "cielo raso"])
        and data.get("interior_exterior") == "interior"
        and data.get("condition") in {"humedad", "salitre", "filtración", "goteras", "moho/hongos", "pintura descascarando", "pintura soplada"}
    ):
        data["surface"] = "interior húmedo"

    # Muro interior con humedad/salitre se trata como "interior húmedo" para activar alertas duras.
    if (
        data["surface"] == "muro"
        and data["interior_exterior"] == "interior"
        and data["condition"] in {"humedad", "salitre", "filtración", "goteras", "moho/hongos", "pintura descascarando", "pintura soplada"}
    ):
        data["surface"] = "interior húmedo"

    # ── Substrate type (tipo de sustrato / material) ──
    # Muros / Fachadas
    if any(w in combined for w in ["estuco", "estucado", "estucada", "pañete", "pañetado", "pañetada"]):
        data["substrate_type"] = "estuco/pañete"
    elif any(w in combined for w in ["ladrillo", "bloque", "mampostería", "mamposteria"]):
        data["substrate_type"] = "ladrillo/bloque"
    elif any(w in combined for w in ["drywall", "superboard"]):
        data["substrate_type"] = "drywall/fibrocemento"
    elif any(w in combined for w in ["revoque", "repello", "friso"]):
        data["substrate_type"] = "revoque"
    # Techos / Cubiertas
    elif any(w in combined for w in ["eternit", "fibrocemento", "asbesto cemento"]):
        data["substrate_type"] = "fibrocemento/eternit"
    elif any(w in combined for w in ["teja", "tejas", "barro cocido"]):
        data["substrate_type"] = "teja"
    elif data.get("surface") == "techo" and any(w in combined for w in ["concreto", "placa", "plancha", "losa"]):
        data["substrate_type"] = "concreto"
    elif data.get("surface") == "techo" and any(w in combined for w in ["lámina", "lamina", "zinc", "metal"]):
        data["substrate_type"] = "lámina metálica"
    # Pisos
    elif data.get("surface") in ("piso", "piso industrial", "piso vehicular", "piso deportivo") and any(w in combined for w in ["concreto", "cemento", "hormigón", "hormigon"]):
        data["substrate_type"] = "concreto"
    elif data.get("surface") in ("piso", "piso industrial", "piso vehicular") and any(w in combined for w in ["baldosa", "cerámica", "ceramica", "porcelanato"]):
        data["substrate_type"] = "baldosa/cerámica"
    # Metal
    elif any(w in combined for w in ["galvanizado", "galvanizada", "galvanizad"]):
        data["substrate_type"] = "galvanizado"
    elif any(w in combined for w in ["hierro negro", "acero al carbono", "hierro", "acero"]):
        data["substrate_type"] = "hierro/acero"
    elif any(w in combined for w in ["aluminio"]):
        data["substrate_type"] = "aluminio"
    elif any(w in combined for w in ["inoxidable", "inox"]):
        data["substrate_type"] = "acero inoxidable"
    # Madera
    elif any(w in combined for w in ["mdf", "triplex", "aglomerado", "tablex"]):
        data["substrate_type"] = "MDF/aglomerado"
    elif any(w in combined for w in ["cedro", "pino", "roble", "teca", "guayacán", "guayacan"]):
        data["substrate_type"] = "madera natural"
    # Genérico: concreto/cemento sin contexto de piso
    elif any(w in combined for w in ["concreto", "cemento", "hormigón", "hormigon", "placa"]):
        data["substrate_type"] = "concreto"

    return data


# ─── Detección de cotización activa ──────────────────────────────────────────

def _get_last_bot_message(recent_messages: list) -> Optional[str]:
    for msg in reversed(recent_messages):
        if msg.get("direction") == "outbound":
            return (msg.get("contenido") or "")
    return None


def has_active_quotation(recent_messages: list) -> bool:
    """Detecta si el último mensaje del bot fue una cotización."""
    last_bot = _get_last_bot_message(recent_messages)
    if not last_bot:
        return False
    lower = last_bot.lower()
    return "$" in last_bot and any(kw in lower for kw in ["total", "cotización", "cotizacion", "subtotal", "precio", "pedido"])


def detect_topic_change(user_message: str, recent_messages: list) -> bool:
    """Detecta si el usuario cambió de tema respecto a la cotización anterior."""
    if not has_active_quotation(recent_messages):
        return False
    msg_lower = (user_message or "").lower()
    topic_signals = [
        "necesito pintar", "quiero pintar", "tengo que pintar",
        "sistema completo", "me recomiendas", "otro proyecto",
        "también necesito", "tambien necesito", "aparte de eso",
    ]
    return any(s in msg_lower for s in topic_signals)


def is_diagnostic_incomplete(intent: str, diagnostic: dict) -> bool:
    """Return True when intent is 'asesoria' and essential diagnostic data is missing.

    Used by agent_v3 to enforce the BLOQUEO at the Python level —
    stripping advisory tools so the LLM physically cannot skip the diagnostic.

    Checks 3 universal fields (surface, interior_exterior, condition) PLUS
    surface-specific critical fields:
      - pisos → traffic is mandatory (defines the entire product line)
      - interior húmedo → humidity_source is mandatory (defines the system)
      - madera → condition is mandatory (new vs old changes system completely)
      - metal → condition is mandatory (virgin vs rusted vs already primed)
    """
    if intent != "asesoria":
        return False
    missing = []
    surface = diagnostic.get("surface") or ""
    if not surface:
        missing.append("surface")
    if not diagnostic.get("interior_exterior"):
        if surface not in ("fachada", "exterior", "madera exterior", "piso deportivo", "techo"):
            missing.append("interior_exterior")
    if not diagnostic.get("condition"):
        missing.append("condition")

    # ── Surface-specific critical fields (Python-level enforcement) ──
    # ONLY broad, reliable checks. The LLM (IA) handles nuanced questions
    # like substrate type, m², specific material — Python only enforces PROCESS.
    #
    # Pisos: sin tipo de tráfico es imposible elegir el sistema correcto
    if surface in ("piso", "piso industrial", "piso vehicular", "piso deportivo"):
        if not diagnostic.get("traffic"):
            missing.append("traffic")
    # Humedad interior: sin origen de la humedad no podemos definir el sistema base
    if surface == "interior húmedo":
        if not diagnostic.get("humidity_source"):
            missing.append("humidity_source")

    return bool(missing)


# ─── Builder principal ───────────────────────────────────────────────────────

def build_turn_context(
    conversation_context: dict,
    recent_messages: list,
    user_message: str,
    internal_auth: dict,
    profile_name: Optional[str] = None,
) -> str:
    """
    Construye el bloque de contexto dinámico para inyectar antes del mensaje del usuario.
    Reemplaza 900 líneas de reglas estáticas con ~15 líneas enfocadas en este turno.
    """
    intent = classify_intent(user_message, conversation_context, recent_messages, internal_auth)
    diagnostic = extract_diagnostic_data(user_message, recent_messages)
    problem_class = _infer_problem_class(diagnostic, user_message)
    is_internal = bool(internal_auth)
    verified = bool(conversation_context.get("verified"))
    commercial_draft = conversation_context.get("commercial_draft")
    claim_case = conversation_context.get("claim_case")
    topic_changed = detect_topic_change(user_message, recent_messages)

    lines = []
    lines.append(f"═══ CONTEXTO DEL TURNO ═══")
    lines.append(f"Intención detectada: {intent}")

    # Client state
    if verified:
        nombre = conversation_context.get("verified_cliente_nombre") or profile_name or "Cliente"
        codigo = conversation_context.get("verified_cliente_codigo") or "?"
        lines.append(f"Cliente: {nombre} (código {codigo}) — verificado ✅")
    else:
        lines.append(f"Cliente: {profile_name or 'No identificado'} — no verificado")

    if is_internal:
        emp = internal_auth.get("employee_context") or {}
        rol = internal_auth.get("role", "empleado")
        lines.append(f"Empleado interno: {emp.get('full_name', '?')} ({rol}, sede {emp.get('sede', '?')})")

    # Active cart
    if commercial_draft and not topic_changed:
        items = commercial_draft.get("items") or []
        if items:
            items_text = ", ".join(
                f"{it.get('cantidad', '?')}x {_draft_item_display_label(it)}"
                for it in items[:8]
            )
            lines.append(f"Carrito activo: [{items_text}]")

    # Active claim
    if claim_case:
        producto = claim_case.get("producto_reclamado", "?")
        lines.append(f"Reclamo activo: producto={producto}")

    # Topic change
    if topic_changed:
        lines.append("⚡ CAMBIO DE TEMA: El cliente pregunta algo NUEVO. Ignora el pedido/cotización anterior.")

    # ─── Alertas críticas de superficie (prioridad absoluta, antes de instrucciones) ──
    surface_alerts = _get_surface_alerts(diagnostic.get("surface"), diagnostic.get("condition"))
    if surface_alerts:
        lines.append("")
        for alert in surface_alerts:
            lines.append(alert)

    structured_diagnostic_lines = _build_structured_diagnostic_summary(problem_class, diagnostic, user_message)
    if structured_diagnostic_lines:
        lines.extend(structured_diagnostic_lines)

    problem_protocol_lines = _build_problem_protocol_lines(problem_class)
    if problem_protocol_lines:
        lines.extend(problem_protocol_lines)

    # ─── Directrices de Gerencia (conocimiento experto elevado) ──────────
    expert_directives = []
    if intent in _EXPERT_DIRECTIVE_INTENTS:
        expert_directives = _fetch_expert_directives_for_turn(
            user_message, diagnostic, intent,
        )
    if expert_directives:
        lines.append("")
        lines.append("═══ DIRECTRIZ DE GERENCIA (PRIORIDAD MÁXIMA) ═══")
        for directive in expert_directives:
            experto = directive.get("nombre_experto", "Experto Ferreinox")
            tipo = directive.get("tipo", "")
            nota = directive.get("nota_comercial", "")
            rec = directive.get("producto_recomendado")
            des = directive.get("producto_desestimado")
            line = f"• [{tipo.upper()}] {experto}: \"{nota}\""
            if rec:
                line += f" → RECOMENDAR: {rec}"
            if des:
                line += f" | ⛔ EVITAR: {des}"
            lines.append(line)
        lines.append("Las directrices de Gerencia PREVALECEN sobre el RAG si hay contradicción.")
        lines.append("═══════════════════════════════════════════════")

    # ─── BLOQUEO DE TRANSACCIÓN: Si hay directrices críticas activas,
    # degradar intent transaccional a asesoría para forzar diagnóstico ──────
    if expert_directives and intent in ("pedido_directo", "cotizacion"):
        # Revisar si alguna directriz contiene señales de bloqueo
        _directives_text = " ".join(
            (d.get("nota_comercial") or "") + " " + (d.get("producto_desestimado") or "")
            for d in expert_directives
        ).lower()
        _blocking_signals = [
            "nunca", "prohibido", "no usar", "no recomendar",
            "incompatible", "contraindicacion", "no aplicar",
            "no se puede", "no apto", "evitar",
        ]
        _has_critical_block = any(sig in _directives_text for sig in _blocking_signals)
        if _has_critical_block:
            intent = "asesoria"  # Degradar intención transaccional
            lines.append("")
            lines.append("🚨 BLOQUEO DE TRANSACCIÓN: Hay directrices técnicas CRÍTICAS activas para este caso.")
            lines.append("TIENES ESTRICTAMENTE PROHIBIDO llamar a herramientas de inventario o dar precios en este turno.")
            lines.append("Tu ÚNICA tarea es:")
            lines.append("  1. Advertir al cliente sobre la regla técnica que impide su solicitud.")
            lines.append("  2. Explicar POR QUÉ su solicitud es técnicamente inviable.")
            lines.append("  3. Ofrecer la alternativa correcta según la directriz.")
            lines.append("  4. Hacer las preguntas de diagnóstico necesarias (m², estado, preparación).")
            lines.append("NO COTICES. NO BUSQUES PRECIOS. PRIMERO EDUCA, LUEGO VENDES.")

    # ─── BLOQUEO DE DIAGNÓSTICO Y METRAJE: patologías de superficie no se cotizan de una ───
    _problematic_conditions = {
        "humedad", "salitre", "filtración", "goteras", "moho/hongos",
        "pintura descascarando", "pintura soplada", "óxido", "grietas",
    }
    if diagnostic.get("condition") in _problematic_conditions and not diagnostic.get("area_m2"):
        intent = "asesoria"
        lines.append("")
        lines.append("🚨 BLOQUEO DE DIAGNÓSTICO Y METRAJE: Hay una patología real de superficie y todavía NO tienes m².")
        lines.append("TIENES ESTRICTAMENTE PROHIBIDO cotizar, calcular cantidades o llamar inventario en este turno.")
        lines.append("Reglas obligatorias para este caso:")
        lines.append("  1. Diagnostica primero la causa y la preparación necesaria.")
        lines.append("  2. Presenta el sistema ideal completo como SOLUCIÓN, no como lista de precios.")
        lines.append("  3. Pide los m² reales del área.")
        lines.append("  4. Solo después pregunta: '¿Quieres que te cotice el sistema ideal con cantidades exactas?'")
        lines.append("  5. La cantidad que el cliente cree necesitar (ej. '5 galones') NO reemplaza el metraje real.")
        lines.append("  6. NO inventes imprimantes: un acabado pedido por el cliente NO se convierte en imprimante por deducción.")

    technical_cases = [entry for entry in (conversation_context.get("technical_cases") or []) if isinstance(entry, dict)]
    active_case_id = conversation_context.get("active_technical_case_id")
    if technical_cases:
        active_case = next((entry for entry in technical_cases if entry.get("case_id") == active_case_id), None)
        pending_cases = [entry for entry in technical_cases if entry.get("case_id") != active_case_id]
        lines.append("")
        lines.append("═══ MEMORIA DE CASOS TÉCNICOS ═══")
        if active_case:
            lines.append(
                f"Caso activo: {active_case.get('case_id')} | {active_case.get('summary') or active_case.get('category') or 'caso técnico'}"
            )
        if pending_cases:
            lines.append("Casos en memoria que SIGUEN ABIERTOS pero NO se deben mezclar con el activo:")
            for case in pending_cases[:3]:
                lines.append(
                    f"  - {case.get('case_id')}: {case.get('summary') or case.get('category') or 'caso técnico'}"
                )
        lines.append("Regla obligatoria: cada diagnóstico, sistema, cotización y PDF pertenece SOLO al caso activo del turno.")

    # ─── Phase-specific instructions ────────────────────────────────────
    lines.append("")
    lines.append("═══ INSTRUCCIÓN PARA ESTE TURNO ═══")

    if intent == "saludo":
        nombre_saludo = profile_name or ""
        if nombre_saludo:
            lines.append(f"Saluda a {nombre_saludo} de forma cálida y breve. Pregunta en qué puedes ayudar.")
        else:
            lines.append("Saluda de forma cálida y breve. Pregunta en qué puedes ayudar.")

    elif intent == "despedida":
        lines.append("Despídete amablemente. Cierra la conversación.")

    elif intent == "asesoria":
        # Check what diagnostic data we already have
        missing = []
        if not diagnostic["surface"]:
            missing.append("superficie (¿qué va a pintar/proteger?)")
        if not diagnostic["interior_exterior"]:
            # Skip if surface already implies it
            if diagnostic["surface"] not in ("fachada", "exterior", "madera exterior", "piso deportivo"):
                missing.append("ubicación (¿interior o exterior?)")
        if not diagnostic["condition"]:
            missing.append("condición (¿nuevo, pintado, con humedad, óxido, descascarado?)")

        # ── Preguntas específicas por tipo de superficie ──
        # SOLO checks AMPLIOS. La IA decide qué preguntas de profundidad hacer.
        # Para pisos: tráfico es CRÍTICO (define la línea de producto)
        if problem_class == "piso_industrial" and not diagnostic.get("traffic"):
            missing.append("tipo de tráfico (¿peatonal/liviano, vehicular, montacargas/pesado?)")
        # Para humedad: la fuente es crítica para la solución
        if diagnostic.get("surface") == "interior húmedo" and not diagnostic.get("humidity_source"):
            missing.append("origen de la humedad (¿viene del piso/base, de arriba, por temporada, o por vapor de ducha/cocina?)")

        if diagnostic["surface"]:
            lines.append(f"Superficie detectada: {diagnostic['surface']}")
        if diagnostic["interior_exterior"]:
            lines.append(f"Ubicación: {diagnostic['interior_exterior']}")
        if diagnostic["condition"]:
            lines.append(f"Condición: {diagnostic['condition']}")
        if diagnostic.get("humidity_source"):
            lines.append(f"Causa probable: {diagnostic['humidity_source']}")
        if diagnostic.get("substrate_type"):
            lines.append(f"Sustrato: {diagnostic['substrate_type']}")
        if diagnostic["area_m2"]:
            lines.append(f"Área: {diagnostic['area_m2']} m²")
        if diagnostic["traffic"]:
            lines.append(f"Tráfico: {diagnostic['traffic']}")

        _interior_humidity_conditions = {"humedad", "salitre", "filtración", "goteras", "moho/hongos", "pintura descascarando", "pintura soplada"}
        if diagnostic.get("surface") == "interior húmedo" and diagnostic.get("condition") in _interior_humidity_conditions:
            lines.append("")
            _humidity_src = diagnostic.get("humidity_source") or ""
            if "condensación" in _humidity_src or "vapor" in _humidity_src or diagnostic.get("condition") == "moho/hongos":
                lines.append("🚨 CASO: HUMEDAD POR CONDENSACIÓN (BAÑO/COCINA)")
                lines.append("La humedad por vapor de ducha/cocción es DIFERENTE de la infiltración de agua líquida.")
                lines.append("Consultá al RAG especificando: superficie='interior húmedo', condición='moho por condensación en baño'.")
                lines.append("El RAG diferencia entre condensación (moho por vapor) e infiltración (agua que filtra).")
                lines.append("La solución es distinta — no asumas que aplica el mismo sistema ni metas Aquablock por inercia si no hay filtración/capilaridad.")
            else:
                lines.append("🚨 CASO: HUMEDAD INTERIOR POR INFILTRACIÓN")
                lines.append("Este tipo de humedad requiere un sistema de impermeabilización + nivelación + acabado.")
                lines.append("Consultá al RAG especificando: superficie='interior húmedo', condición='" + (diagnostic.get("condition") or "humedad") + "'.")
                lines.append("El RAG te dará la secuencia correcta de impermeabilización, estuco y acabado.")
            lines.append("IMPORTANTE: NO prescribas productos hasta consultar al RAG. Cada caso de humedad tiene un sistema específico.")
            if is_internal:
                lines.append("Acción: Consulta al RAG con el diagnóstico completo y entrega una ruta técnica clara. No abras cotización ni pidas m² salvo que el colaborador los necesite explícitamente para cálculo interno.")
            else:
                lines.append("Acción: Consulta al RAG con el diagnóstico completo y luego pide m² para cotizar.")

        # ── Galvanizado: guía diagnóstica (sin prescribir productos) ──
        _conv_text_lower = (user_message or "").lower() + " " + " ".join(
            (msg.get("contenido") or "").lower()
            for msg in (recent_messages or [])[-10:]
            if msg.get("direction") == "inbound"
        )
        if diagnostic.get("surface") == "metal" and any(w in _conv_text_lower for w in ["galvanizado", "galvanizada", "galvanizad"]):
            lines.append("")
            lines.append("🚨 METAL GALVANIZADO DETECTADO")
            lines.append("El galvanizado tiene una capa de zinc que rechaza la pintura convencional.")
            lines.append("Si el cliente aplicó esmalte directo, se descascara como un plástico.")
            lines.append("Consultá al RAG especificando: superficie='metal galvanizado', condición='" + (diagnostic.get("condition") or "descascarado") + "'.")
            lines.append("El RAG te dará el sistema correcto (promotor de adherencia + anticorrosivo + acabado).")
            lines.append("IMPORTANTE: NO prescribas productos hasta consultar al RAG. El galvanizado necesita un sistema específico.")

        if missing:
            lines.append(f"Datos faltantes: {', '.join(missing)}")
            lines.append("")
            lines.append("🚫 BLOQUEO DE DIAGNÓSTICO INCOMPLETO 🚫")
            lines.append("TIENES ESTRICTAMENTE PROHIBIDO en este turno:")
            lines.append("  1. Llamar consultar_conocimiento_tecnico.")
            lines.append("  2. Llamar consultar_inventario o consultar_inventario_lote.")
            lines.append("  3. Sugerir sistemas completos, cotizar precios o calcular cantidades.")
            lines.append("")
            lines.append("✅ LO QUE SÍ PUEDES HACER:")
            lines.append("  1. Dar una SOSPECHA PRELIMINAR breve (categoría general, SIN nombres de productos)")
            lines.append("  2. Hacer 1-3 preguntas diagnósticas CONVERSACIONALES")
            lines.append("  3. Mostrar empatía con el problema del cliente")
            lines.append("")
            lines.append("FORMATO IDEAL:")
            lines.append("  1. Empatía + sospecha: 'Uy, qué fastidio con eso. Por lo que me cuentas parece un caso de [categoría]...'")
            lines.append("  2. Preguntas: 'pero para darte la solución exacta necesito saber: [preguntas faltantes]'")
            lines.append("Tú eres la IA — entiendes lo que el cliente necesita y sabes qué preguntar. Hazlo natural.")

        elif not conversation_context.get("_advisory_diagnostic_turn_done") and not conversation_context.get("latest_technical_guidance"):
            # ─── PROFUNDIZACIÓN DIAGNÓSTICA (first advisory turn) ───
            # Broad checks passed but this is the FIRST advisory turn.
            # The LLM (IA) must ask depth questions before consulting RAG.
            lines.append("")
            lines.append("📋 PROFUNDIZACIÓN DIAGNÓSTICA — PRIMER TURNO DE ASESORÍA")
            lines.append("Tienes la información BÁSICA del caso. Pero como asesor experto,")
            lines.append("SIEMPRE verificas los detalles antes de recomendar.")
            lines.append("")
            lines.append("Tú eres INTELIGENCIA ARTIFICIAL — entiendes lo que el cliente escribió")
            lines.append("y sabes exactamente qué preguntas hacer para cada tipo de superficie.")
            lines.append("NO dependes de palabras clave. Entiende el CONTEXTO del cliente.")
            lines.append("")
            lines.append("DEBES confirmar con el cliente ANTES de consultar herramientas:")
            lines.append("  • ¿De qué MATERIAL es la superficie? (cada material cambia el sistema)")
            if not is_internal:
                lines.append("  • ¿Cuántos m² tiene el área?")
            lines.append("  • Cualquier otro detalle que como asesor experto necesites para dar una recomendación precisa")
            lines.append("")
            lines.append("FORMATO:")
            lines.append("  1. Empatía + sospecha preliminar (categoría general, SIN productos específicos)")
            lines.append("  2. 2-3 preguntas naturales que un asesor experto haría para este caso")
            lines.append("  3. En el PRÓXIMO turno, con la respuesta del cliente, SÍ podrás consultar el RAG")

        else:
            lines.append("Datos suficientes para recomendar.")
            lines.append("Acción: Llama consultar_conocimiento_tecnico con la superficie y condición EN ESTE MISMO TURNO.")
            lines.append("NO respondas 'voy a consultar' o 'un momento' sin haber usado realmente la herramienta.")
            lines.append("Presenta la recomendación basada en el RAG: preparación de superficie (SIEMPRE) → producto principal → imprimante/sellador SOLO si el RAG lo confirma → diluyente + herramientas.")
            lines.append("NO agregues imprimante ni sellador que el RAG no indique para este caso. Los productos son claros en su uso y sustratos.")
            if is_internal:
                lines.append("CIERRE INTERNO OBLIGATORIO: entrega recomendación técnica directa, rendimientos consultados y advertencias de aplicación. No ofrezcas cotización, pedido ni PDF.")
                lines.append("Si el colaborador quiere cierre comercial, cierra así: 'Si quieres, te conecto con un asesor comercial para cotizar los productos.'")
            elif not diagnostic["area_m2"]:
                lines.append("Al final pregunta m² y color para calcular cantidades.")

    elif intent == "pedido_directo":
        if is_internal:
            lines.append("Empleado interno con producto específico. Directo a inventario, sin diagnóstico.")
            lines.append("Acción: Llama consultar_inventario o consultar_inventario_lote con los productos.")
            lines.append("Presenta cotización: producto + cant + precio unitario + subtotal. Al final: Subtotal + IVA 19% + Total.")
        else:
            lines.append("Cliente nombra producto específico.")
            lines.append("Acción: Llama consultar_conocimiento_tecnico para validar que el producto es adecuado.")
            lines.append("Luego consultar_inventario para disponibilidad y precios.")
            lines.append("Si el producto es bicomponente, incluye obligatoriamente el catalizador.")

    elif intent == "cotizacion":
        lines.append("El cliente quiere precios de algo ya discutido.")
        lines.append("Acción: Llama consultar_inventario_lote para todos los productos del sistema recomendado.")
        lines.append("Presenta: sistema + cantidades + precios. Subtotal + IVA 19% + Total a Pagar.")

    elif intent == "consulta_productos":
        if is_internal:
            lines.append("Consulta operativa de inventario para colaborador interno.")
            lines.append("Acción: Llama consultar_inventario con modo_consulta='inventario'.")
            lines.append("Si preguntan una tienda específica, responde con el stock exacto de esa tienda.")
            lines.append("Si no piden tienda específica, muestra el desglose por tienda con cantidades exactas.")
            lines.append("NO cotices. NO des IVA. NO mezcles esta consulta con pedido o cotización.")
            lines.append("Cierra en tono interno y util: ofrece revisar otra referencia o tienda, pero NO ofrezcas pedidos, cotizaciones ni PDF.")
        else:
            lines.append("Consulta puntual de disponibilidad de producto.")
            lines.append("Acción: Llama consultar_inventario para validar referencia, presentación y disponibilidad.")
            lines.append("Responde solo disponibilidad o pide aclaración si hay varias coincidencias.")

    elif intent == "confirmacion":
        lines.append("El cliente aceptó la cotización.")
        lines.append("Si el cliente solo envía cédula/NIT, nombre o dice que la quiere en PDF, NO vuelvas a cotizar ni a consultar inventario.")
        draft_tipo = (commercial_draft or {}).get("tipo_documento")
        if draft_tipo == "cotizacion":
            lines.append("Acción: Si el cliente no está validado, para cotización pide nombre + cédula/NIT y usa registrar_cliente_nuevo en modo cotizacion.")
            lines.append("NO bloquees la cotización por falta de dirección o ciudad.")
        elif draft_tipo == "pedido":
            lines.append("Acción: Para pedido reúne nombre + cédula/NIT + dirección + ciudad antes de cerrar.")
            lines.append("Si no existe en base, usa registrar_cliente_nuevo en modo pedido y luego confirmar_pedido_y_generar_pdf.")
        else:
            lines.append("Acción: Recopila datos faltantes según el tipo de cierre: cotización = nombre + cédula/NIT; pedido = nombre + cédula/NIT + dirección + ciudad.")
        lines.append("Luego llama confirmar_pedido_y_generar_pdf.")
        lines.append("NO repitas la cotización. Solo recoge lo que falta y cierra.")

    elif intent == "correccion":
        lines.append("El cliente corrige un ítem de la cotización activa.")
        lines.append("Acción: Llama consultar_inventario SOLO con el producto corregido.")
        lines.append("Mantén todos los demás ítems intactos. Recalcula solo la línea y el total.")
        lines.append("Muestra la cotización completa actualizada.")

    elif intent == "reclamo":
        if claim_case:
            lines.append(f"Reclamo en curso: {claim_case.get('producto_reclamado', '?')}")
            lines.append("Acción: Continúa el flujo de reclamo. Recoge datos faltantes y radica cuando estén completos.")
        else:
            lines.append("Nuevo reclamo.")
            lines.append("Acción: Escucha con empatía. Pregunta qué producto y qué problema tiene.")
            lines.append("Llama consultar_conocimiento_tecnico para cruzar con la ficha técnica.")
            lines.append("Sigue el flujo: empatía → diagnóstico → resolución → escalar si necesario → radicar.")

    elif intent == "bi_interno":
        lines.append("Consulta de inteligencia de negocios (empleado interno).")
        lines.append("Acción: Llama consultar_ventas_internas con los parámetros apropiados.")

    elif intent == "documento":
        lines.append("Solicitud de ficha técnica o documento.")
        lines.append("Acción: Llama buscar_documento_tecnico con el producto mencionado.")

    elif intent == "identidad":
        lines.append("El cliente proporcionó un número de identificación.")
        lines.append("Acción: Llama verificar_identidad con el número.")

    else:
        lines.append("Responde de forma útil y conversacional. Si necesitas info técnica, consulta tus herramientas.")

    lines.append("═══════════════════════════")

    return "\n".join(lines)
