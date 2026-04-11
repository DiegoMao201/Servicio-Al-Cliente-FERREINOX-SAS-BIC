"""
Turn Context Builder — Inyección dinámica de estado por turno.

En vez de que el LLM gestione estado leyendo 900 líneas de reglas,
Python analiza la conversación y le inyecta un brief de ~15 líneas
que le dice EXACTAMENTE qué hacer en este turno.
"""

import json
import re
import logging
from typing import Optional

logger = logging.getLogger("agent_context")

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

_SPECIFIC_PRODUCTS = [
    "koraza", "viniltex", "pintucoat", "intervinil", "pinturama",
    "interseal", "intergard", "interthane", "corrotec", "pintóxido", "pintoxido",
    "pintulux", "barnex", "barniz marino", "esmalte doméstico", "esmalte domestico",
    "aquablock", "sellamur", "wood stain", "pintura canchas", "wash primer",
    "primer 50rs", "pintuco fill", "pintutraf", "doméstico", "domestico",
    "1550", "1551", "poliuretano alto", "intergard 740", "intergard 2002",
    "sealer f100", "interchar",
]

_ADVISORY_SIGNALS = [
    "pintar", "impermeabilizar", "proteger", "recubrir", "barnizar", "lacar",
    "qué le aplico", "que le aplico", "qué sistema", "que sistema",
    "cómo pinto", "como pinto", "me recomiendas", "qué necesito",
    "que necesito", "asesoría", "asesoria", "asesorame",
]

_SURFACE_SIGNALS = [
    "piso", "fachada", "techo", "muro", "pared", "reja", "estructura",
    "madera", "puerta", "mueble", "mesa", "bodega", "garaje", "terraza",
    "baño", "cocina", "cancha", "metal", "tanque", "cubierta", "cielo raso",
    "pergola", "pérgola", "sendero", "cicloruta", "nave", "planta",
]

_CONDITION_SIGNALS = [
    "humedad", "filtra", "gotea", "moho", "hongo", "salitre", "óxido", "oxido",
    "descascar", "pela", "sopla", "grieta", "entiza", "llueve", "ampolla",
    "nuevo", "viejo", "pintado", "sin pintar", "deterioro",
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

    # 6. Identity (pure numeric 6-15 digits)
    if re.match(r"^\d{6,15}$", msg.strip()):
        pending = conversation_context.get("pending_intent")
        if pending:
            return "identidad"

    # 7. Correction (if last bot msg was a quotation)
    last_bot = _get_last_bot_message(recent_messages)
    if last_bot and "$" in last_bot and _CORRECTION_PATTERNS.search(msg_lower):
        return "correccion"

    # 8. Confirmation (short affirmative after quotation)
    if last_bot and "$" in last_bot and _CONFIRMATION_PATTERNS.match(msg):
        return "confirmacion"

    # 9. Direct order (names specific products + quantities)
    has_specific = any(p in msg_lower for p in _SPECIFIC_PRODUCTS)
    has_quantity = bool(_DIRECT_ORDER_PATTERNS.search(msg))
    has_price_request = any(s in msg_lower for s in _PRICE_SIGNALS)
    if has_specific and has_quantity:
        return "pedido_directo"
    if has_specific and has_price_request:
        return "pedido_directo"

    # 10. Advisory (describes surface/need without naming specific product)
    has_advisory = any(s in msg_lower for s in _ADVISORY_SIGNALS)
    has_surface = any(s in msg_lower for s in _SURFACE_SIGNALS)
    if (has_advisory or has_surface) and not has_specific:
        return "asesoria"

    # 11. Quotation request (asks for prices on prior topic)
    if has_price_request:
        return "cotizacion"

    # 12. If names a specific product without quantity (info request)
    if has_specific:
        return "pedido_directo"

    return "general"


# ─── Extracción de datos diagnósticos ────────────────────────────────────────

def extract_diagnostic_data(user_message: str, recent_messages: list) -> dict:
    """
    Extrae datos diagnósticos de la conversación combinada.
    Retorna dict con claves: surface, condition, interior_exterior, area_m2, traffic
    Valores None si no detectado.
    """
    # Combine last ~5 inbound messages + current
    texts = []
    for msg in recent_messages[-10:]:
        if msg.get("direction") == "inbound":
            texts.append((msg.get("contenido") or "").lower())
    texts.append((user_message or "").lower())
    combined = " ".join(texts)

    data = {
        "surface": None,
        "condition": None,
        "interior_exterior": None,
        "area_m2": None,
        "traffic": None,
    }

    # Surface
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
    for kw, surf in surface_map.items():
        if kw in combined:
            data["surface"] = surf
            break

    # Interior/Exterior
    if any(w in combined for w in ["fachada", "terraza", "exterior", "intemperie", "azotea"]):
        data["interior_exterior"] = "exterior"
    elif any(w in combined for w in ["interior", "apartamento", "casa", "oficina", "habitación",
                                      "habitacion", "sala", "cuarto", "dormitorio"]):
        data["interior_exterior"] = "interior"
    elif any(w in combined for w in ["bodega", "fábrica", "fabrica", "planta", "nave"]):
        data["interior_exterior"] = "industrial"

    # Condition
    cond_signals = {
        "humedad": "humedad", "filtra": "filtración", "gotea": "goteras",
        "moho": "moho/hongos", "óxido": "óxido", "oxido": "óxido",
        "descascar": "pintura descascarando", "sopla": "pintura soplada",
        "grieta": "grietas", "nuevo": "superficie nueva",
        "sin pintar": "sin pintar", "pintado": "repintura",
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
                f"{it.get('cantidad', '?')}x {it.get('descripcion_comercial', it.get('descripcion', '?'))}"
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
            missing.append("condición (¿nuevo, pintado, con humedad, óxido?)")

        if diagnostic["surface"]:
            lines.append(f"Superficie detectada: {diagnostic['surface']}")
        if diagnostic["interior_exterior"]:
            lines.append(f"Ubicación: {diagnostic['interior_exterior']}")
        if diagnostic["condition"]:
            lines.append(f"Condición: {diagnostic['condition']}")
        if diagnostic["area_m2"]:
            lines.append(f"Área: {diagnostic['area_m2']} m²")
        if diagnostic["traffic"]:
            lines.append(f"Tráfico: {diagnostic['traffic']}")

        if missing:
            lines.append(f"Datos faltantes: {', '.join(missing)}")
            lines.append("Acción: Haz 1-2 preguntas conversacionales breves para completar el diagnóstico.")
            lines.append("Todavía NO recomiendes productos ni llames herramientas de inventario.")
        else:
            lines.append("Datos suficientes para recomendar.")
            lines.append("Acción: Llama consultar_conocimiento_tecnico con la superficie y condición.")
            lines.append("Presenta el sistema completo (preparación → imprimante → acabado + diluyente + herramientas).")
            if not diagnostic["area_m2"]:
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

    elif intent == "confirmacion":
        lines.append("El cliente aceptó la cotización.")
        lines.append("Acción: Recopila datos faltantes (nombre, cédula si es pedido). Llama confirmar_pedido_y_generar_pdf.")
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
