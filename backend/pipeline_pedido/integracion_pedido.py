"""
integracion_pedido.py — Puente entre Agent V3 y pipeline_pedido
================================================================

Estrategia de integración:
  - INTERCEPTA el flujo cuando se detecta intención de pedido directo
  - Solo para empleados internos (internal_auth=True) o clientes con tienda asignada
  - Inyecta las funciones reales (lookup, price, email, dropbox) del main.py

Uso desde agent_v3.py:
  from pipeline_pedido.integracion_pedido import interceptar_pedido_si_aplica

  intercepcion = interceptar_pedido_si_aplica(...)
  if intercepcion:
      return intercepcion
"""
from __future__ import annotations

import json
import logging
import re
import time
from typing import Optional

logger = logging.getLogger("pipeline_pedido.integracion")

# ============================================================================
# DETECCIÓN DE INTENCIÓN DE PEDIDO
# ============================================================================

# ── Keywords FUERTES: solo palabras que inequívocamente significan "hacer un pedido" ──
# Palabras genéricas como "necesito", "manda", "envía", "solicitar", "orden"
# NO están aquí porque se usan en asesoría/consultas normales.
# Ej: "necesito pintar mi fachada" ≠ pedido, "mándame info" ≠ pedido.
_KEYWORDS_PEDIDO_FUERTE = [
    "pedido", "pedir", "pideme", "pídeme",
    "despacho", "despacha", "despachar",
    "trasladar", "traslado", "transferencia",
]

# ── Anti-patterns: si el mensaje contiene estos, es consulta/asesoría, NO pedido ──
_ANTI_PEDIDO_PATTERNS = [
    r'\b(?:pintar|pintando|pinto)\b',
    r'\b(?:cómo|como)\s+(?:puedo|hago|aplico|uso|preparo)',
    r'\b(?:qué|que)\s+(?:me\s+)?(?:recomienda|sirve|necesito|uso|aplico)',
    r'\b(?:ayud(?:a|ame|en)|asesór(?:a|ame)|consejo|recomendaci[oó]n)',
    r'\b(?:problema|humedad|moho|fisura|grieta|ampolla|descascar)',
    r'\b(?:fachada|pared|muro|techo|piso|madera|metal)\b.*\b(?:pintar|proteger|sellar|impermeabilizar)',
    r'\b(?:cuál|cual)\s+(?:es|pintura|producto)',
    r'\b(?:sirve|funciona|aplica)\s+(?:para|en|sobre)',
    r'\b(?:diferencia|comparar|mejor)\s+entre',
    r'\b(?:ficha\s+t[eé]cnica|hoja\s+de\s+seguridad|rendimiento|cobertura)',
]

_KEYWORDS_TIENDA = [
    "pereira", "manizales", "dosquebradas", "armenia",
    "cerritos", "laureles", "ferrebox", "cedi",
    "tienda", "almacén", "almacen", "bodega",
]

# Códigos de tienda solo se buscan como palabra completa (evitar que "1559" matchee "155")
_TIENDA_CODES = {"189", "157", "158", "156", "463", "238", "439", "155"}


def _detectar_intencion_pedido(
    user_message: str,
    tool_calls_made: list[dict],
    conversation_context: dict,
) -> bool:
    """
    Detecta si el mensaje actual es un pedido directo de productos.

    PRINCIPIO CENTRAL: El LLM es el cerebro conversacional. Solo
    interceptamos cuando hay EVIDENCIA CONCRETA de un pedido comercial
    (líneas con productos+cantidades). Nunca por keywords genéricas
    que podrían ser consultas de asesoría.

    "Necesito pintar mi fachada"  →  NO es pedido (asesoría)
    "Necesito 4 galones vinílico" →  SÍ es pedido (producto+cantidad)
    "Pedido para Pereira"         →  SÍ es pedido (keyword fuerte)
    """
    user_lower = (user_message or "").lower()

    # ── ANTI-PATTERNS: Si el mensaje parece consulta/asesoría, NO interceptar ──
    # Esto protege frases como "necesito pintar mi fachada", "qué me recomiendas
    # para humedad", etc., incluso si tienen keywords de pedido.
    for anti_pat in _ANTI_PEDIDO_PATTERNS:
        if re.search(anti_pat, user_lower):
            logger.debug("Detección pedido: anti-pattern '%s' detectado, NO interceptar", anti_pat)
            return False

    # ── 1. Pedido en progreso (continuación explícita) ──
    # Solo si ya estamos en flujo de pedido activo y el user envía más líneas
    pedido_en_progreso = conversation_context.get("_pedido_en_progreso", False)
    if pedido_en_progreso:
        # Pero si es una sola línea sin productos, podría estar cambiando de tema
        lineas_producto = _contar_lineas_producto(user_message)
        if lineas_producto >= 1:
            return True
        # Si es frase corta tipo "listo", "ya", "eso es todo" → no nuevas líneas
        # pero el pedido está en progreso → dejar al LLM manejar cierre
        return False

    # ── 2. Keywords FUERTES de pedido (inequívocas) ──
    tiene_keyword_fuerte = any(kw in user_lower for kw in _KEYWORDS_PEDIDO_FUERTE)

    # ── 3. Contar líneas que parecen producto+cantidad ──
    lineas_producto = _contar_lineas_producto(user_message)

    # ── 4. Herramientas de inventario usadas en este turno ──
    inventory_tools = {"consultar_inventario", "consultar_inventario_lote"}
    tools_used = {tc.get("name", "") for tc in tool_calls_made}
    uso_inventario = bool(tools_used & inventory_tools)

    # ══════════════════════════════════════════════════════════════
    # REGLAS DE INTERCEPCIÓN (de más fuerte a más débil)
    # ══════════════════════════════════════════════════════════════

    # R1: 3+ líneas con producto+cantidad → pedido claro, no necesita keyword
    if lineas_producto >= 3:
        return True

    # R2: Keyword fuerte ("pedido", "despacho") + al menos 1 línea de producto
    if tiene_keyword_fuerte and lineas_producto >= 1:
        return True

    # R3: Keyword fuerte sola → intención de pedido sin productos aún
    #     (el interceptor preguntará "¿qué productos necesitas?")
    if tiene_keyword_fuerte:
        return True

    # R4: Herramientas de inventario ya usadas + líneas de producto
    if uso_inventario and lineas_producto >= 1:
        return True

    # TODO ELSE: dejar que el LLM maneje la conversación
    return False


def _contar_lineas_producto(user_message: str) -> int:
    """
    Cuenta cuántas líneas del mensaje parecen tener productos + cantidades.

    Una línea se considera "producto" si tiene:
    - Al menos un número (cantidad o código)
    - Algún texto alfabético (nombre de producto)
    - NO es pura prosa conversacional

    "4 galones vinílico blanco"  →  SÍ (número + texto + unidad)
    "necesito pintar mi fachada" →  NO (sin números)
    "hola buen día"              →  NO (sin números + es saludo)
    """
    count = 0
    for raw_line in re.split(r'[\n\r]+', user_message or ""):
        line = raw_line.strip()
        if not line or len(line) < 4:
            continue
        # Debe tener al menos un dígito Y texto alfabético
        if not re.search(r'\d', line):
            continue
        if not re.search(r'[a-záéíóú]{3,}', line, re.IGNORECASE):
            continue
        # Filtrar líneas que son claramente contexto/prosa
        if _es_linea_contexto(line.lower()):
            continue
        count += 1
    return count


def _extraer_tienda_de_mensaje(user_message: str) -> str:
    """Extrae texto de tienda del mensaje libre."""
    user_lower = (user_message or "").lower()
    # Primero: buscar nombres de tienda (substring OK)
    for kw in _KEYWORDS_TIENDA:
        if kw in user_lower:
            return kw
    # Segundo: buscar códigos numéricos como palabra COMPLETA
    # (evitar que "1559" matchee código de tienda "155")
    for code in _TIENDA_CODES:
        if re.search(rf'\b{code}\b', user_lower):
            return code
    return ""


def _parsear_lineas_pedido(
    user_message: str,
    tool_calls_made: list[dict],
) -> list[dict]:
    """
    Extrae líneas de pedido del mensaje y/o resultados de herramientas.

    Soporta formatos reales de WhatsApp:
      - "4 galones azul Milano 1510"
      - "1526 ocre 2 galones"
      - "vinílico blanco galones 4"
      - "p153 aluminio 1 galón"
      - "pulidora 4040 - 4 octavos"
      - "pulidora 1 galón"
      - "aerosol multi superficie negro mate 3"
      - "t95 pintulux negro 2 galones"
      - "Viniltex baños y cocinas 2 cuartos"
      - "vinilico blanco medio cuñete 3"
      - "vinilico blanco cuñete 3"

    Cada linea: {texto: str, producto: str, cantidad: int|float, unidad: str}
    """
    lineas = []

    # 1. Extraer de tool results (consultar_inventario devuelve productos)
    for tc in tool_calls_made:
        if tc.get("name") in ("consultar_inventario", "consultar_inventario_lote"):
            try:
                result = json.loads(tc.get("result", "{}"))
                if isinstance(result, dict):
                    items = result.get("items") or result.get("resultados") or []
                    for item in items:
                        if isinstance(item, dict) and item.get("referencia"):
                            lineas.append({
                                "texto": item.get("descripcion", ""),
                                "producto": item.get("descripcion", ""),
                                "cantidad": item.get("cantidad_solicitada", 1),
                                "unidad": item.get("unidad", "UND"),
                                "codigo": item.get("referencia", ""),
                                "codigos": [item.get("referencia", "")],
                            })
            except (json.JSONDecodeError, TypeError):
                pass

    # 2. Parsear del mensaje libre — dividir por líneas y analizar cada una
    user_msg = user_message or ""

    # Unidades reconocidas (para extraer cantidad + unidad)
    _UNIT_PAT = (
        r'(?:gal(?:on(?:es?)?)?|gl|cuart(?:os?)?|cu(?:ñ|n)etes?|'
        r'und(?:idades?)?|lt|litros?|kg|octav(?:os?)?|'
        r'medio\s+cu(?:ñ|n)etes?|baldes?|1/[1245])'
    )

    for raw_line in re.split(r'[\n\r]+', user_msg):
        line = raw_line.strip()
        if not line:
            continue
        # Ignorar líneas que son puro contexto conversacional (sin productos)
        line_lower = line.lower()
        if _es_linea_contexto(line_lower):
            continue

        # ── Intentar extraer cantidad y unidad del texto libre ──
        cantidad = 0
        unidad = ""
        producto_text = line

        # Patrón A: "4 galones azul Milano 1510" (cantidad + unidad al inicio)
        m_a = re.match(
            rf'^\s*(\d+(?:[.,]\d+)?)\s+({_UNIT_PAT})\s+(?:de\s+)?(.+)$',
            line, re.IGNORECASE,
        )
        # Patrón B: "1526 ocre 2 galones" (código/nombre + cantidad + unidad al final)
        m_b = re.search(
            rf'(\d+(?:[.,]\d+)?)\s+({_UNIT_PAT})\s*$',
            line, re.IGNORECASE,
        )
        # Patrón C: "vinílico blanco galones 4" (nombre + unidad + cantidad al final)
        m_c = re.search(
            rf'({_UNIT_PAT})\s+(\d+(?:[.,]\d+)?)\s*$',
            line, re.IGNORECASE,
        )
        # Patrón D: "aerosol multi superficie negro mate 3" (nombre + número suelto al final)
        m_d = re.search(
            r'(\d+(?:[.,]\d+)?)\s*$',
            line,
        )
        # Patrón E: "pulidora 4040 - 4 octavos" (nombre + ref - cantidad unidad)
        m_e = re.search(
            rf'[-–]\s*(\d+(?:[.,]\d+)?)\s+({_UNIT_PAT})\s*$',
            line, re.IGNORECASE,
        )

        if m_e:
            # Patrón E: "pulidora 4040 - 4 octavos"
            cantidad = _parse_num(m_e.group(1))
            unidad = m_e.group(2)
            producto_text = line[:m_e.start()].strip().rstrip('-–').strip()
        elif m_a:
            # Patrón A: "4 galones azul Milano 1510"
            cantidad = _parse_num(m_a.group(1))
            unidad = m_a.group(2)
            producto_text = m_a.group(3).strip()
        elif m_b and not m_a:
            # Patrón B: "1526 ocre 2 galones"
            cantidad = _parse_num(m_b.group(1))
            unidad = m_b.group(2)
            producto_text = line[:m_b.start()].strip()
        elif m_c:
            # Patrón C: "vinílico blanco galones 4"
            unidad = m_c.group(1)
            cantidad = _parse_num(m_c.group(2))
            producto_text = line[:m_c.start()].strip()
        elif m_d:
            # Patrón D: "aerosol multi superficie negro mate 3"
            cantidad = _parse_num(m_d.group(1))
            unidad = "UND"
            producto_text = line[:m_d.start()].strip()
        else:
            # Sin cantidad detectada → tratar toda la línea como producto
            producto_text = line
            cantidad = 1
            unidad = "UND"

        if not producto_text.strip():
            continue

        # Evitar que líneas de contexto pasen como producto
        if cantidad <= 0:
            cantidad = 1

        lineas.append({
            "texto": raw_line.strip(),
            "producto": producto_text.strip(),
            "cantidad": cantidad,
            "unidad": unidad.strip(),
            "codigos": [],
        })

    return lineas


def _parse_num(s: str) -> float:
    """Parsea número con posible coma decimal."""
    return float(s.replace(",", "."))


def _es_linea_contexto(line_lower: str) -> bool:
    """Detecta líneas que son contexto conversacional, no productos.
    
    IMPORTANTE: Solo filtra líneas que CLARAMENTE no son productos.
    En caso de duda, NO filtrar (dejar pasar al matcher que es más robusto).
    """
    # Líneas muy cortas que no parecen producto
    if len(line_lower) < 3:
        return True
    # Líneas largas (>80 chars) con pocas cifras son prosa, no productos
    if len(line_lower) > 80:
        digits = sum(1 for c in line_lower if c.isdigit())
        if digits <= 2:
            return True
    # Saludos puros y frases genéricas (SIN productos)
    _CONTEXT_PATTERNS = [
        r'^(?:buen\s*d[ií]a|buenos?\s+d[ií]as?)\b',
        r'^hola\s*[,.]?\s*$',
        r'^\s*(?:muchas\s+)?gracias\s*[,.]?\s*$',
        r'^(?:por\s+favor)\s*[,.]?\s*$',
        r'^\s*muchas\s+gracias\s*[,.]?\s*gracias\s*[,.]?\s*$',
    ]
    for pat in _CONTEXT_PATTERNS:
        if re.search(pat, line_lower):
            return True
    return False


# ============================================================================
# INTERCEPTOR PRINCIPAL
# ============================================================================

def interceptar_pedido_si_aplica(
    main_module,
    conversation_context: dict,
    user_message: str,
    tool_calls_made: list[dict],
    context: dict,
) -> Optional[dict]:
    """
    Evalúa si el mensaje actual es un pedido directo y, de ser así,
    lo redirige al pipeline determinístico de pedidos.

    Returns:
        dict compatible con generate_agent_reply_v3() si interceptó,
        None si no aplica.
    """
    # ── CASO 1: Respuesta a pregunta de tienda pendiente ──
    lineas_pendientes = conversation_context.get("_pedido_pendiente_lineas")
    if lineas_pendientes:
        tienda_texto = _extraer_tienda_de_mensaje(user_message)
        if tienda_texto:
            logger.info(
                "INTERCEPCIÓN PEDIDO: Tienda recibida '%s', re-ejecutando con %d líneas guardadas | conv=%s",
                tienda_texto, len(lineas_pendientes), context.get("conversation_id", "?"),
            )
            conversation_context["_pedido_tienda"] = tienda_texto
            # Limpiar líneas pendientes para no re-ejecutar
            conversation_context.pop("_pedido_pendiente_lineas", None)
            return _ejecutar_pipeline(
                main_module, conversation_context, lineas_pendientes,
                tienda_texto, tool_calls_made, context,
            )
        # El usuario dijo algo pero no es tienda — quizá es un producto más o contexto
        # Dejar que caiga al flujo normal

    # ── Guard: detectar intención ──
    if not _detectar_intencion_pedido(
        user_message, tool_calls_made, conversation_context,
    ):
        return None

    # ── Parsear líneas de pedido ──
    lineas = _parsear_lineas_pedido(user_message, tool_calls_made)
    if not lineas:
        # Tiene intención de pedido pero sin líneas de producto aún.
        # Marcar en contexto para que el siguiente mensaje con productos
        # sea interceptado aunque no diga "pedido".
        conversation_context["_pedido_en_progreso"] = True
        logger.info(
            "INTERCEPCIÓN PEDIDO: intención detectada sin líneas, marcando _pedido_en_progreso | conv=%s",
            context.get("conversation_id", "?"),
        )
        return _construir_return_agente(
            "Listo, ¿qué productos necesitas? Envíame la lista con cantidades y presentaciones.",
            tool_calls_made,
            conversation_context,
        )

    logger.info(
        "INTERCEPCIÓN PEDIDO: %d líneas detectadas | conv=%s",
        len(lineas), context.get("conversation_id", "?"),
    )

    # ── Extraer tienda del mensaje o del contexto ──
    tienda_texto = (
        conversation_context.get("_pedido_tienda")
        or _extraer_tienda_de_mensaje(user_message)
    )

    return _ejecutar_pipeline(
        main_module, conversation_context, lineas,
        tienda_texto, tool_calls_made, context,
    )


def _ejecutar_pipeline(
    main_module,
    conversation_context: dict,
    lineas: list[dict],
    tienda_texto: str,
    tool_calls_made: list[dict],
    context: dict,
) -> Optional[dict]:
    """Ejecuta el pipeline de pedido con las líneas y tienda dadas."""
    cliente_nombre = (
        conversation_context.get("client_name")
        or conversation_context.get("nombre_cliente")
        or "Cliente"
    )
    notas = conversation_context.get("_pedido_notas", "")
    descuentos = conversation_context.get("_pedido_descuentos")
    pedido_id = conversation_context.get("_pedido_id", 0)

    # ── Inyectar funciones reales desde main_module ──
    lookup_fn = getattr(main_module, "lookup_product_context", None)
    price_fn = getattr(main_module, "fetch_product_price", None)
    send_email_fn = getattr(main_module, "send_sendgrid_email", None)
    upload_dropbox_fn = getattr(main_module, "upload_bytes_to_dropbox", None)
    logger.info(
        "_ejecutar_pipeline: lookup_fn=%s, price_fn=%s, main_module=%s",
        type(lookup_fn).__name__ if lookup_fn else "NONE",
        type(price_fn).__name__ if price_fn else "NONE",
        type(main_module).__name__ if main_module else "NONE",
    )

    # ── Ejecutar pipeline ──
    try:
        from .orquestador_pedido import ejecutar_pipeline_pedido

        t0 = time.time()
        resultado = ejecutar_pipeline_pedido(
            lineas_parseadas=lineas,
            tienda_texto=tienda_texto,
            cliente_nombre=cliente_nombre,
            notas=notas,
            descuentos=descuentos,
            lookup_fn=lookup_fn,
            price_fn=price_fn,
            send_email_fn=send_email_fn,
            upload_dropbox_fn=upload_dropbox_fn,
            conversation_id=context.get("conversation_id", ""),
            pedido_id=pedido_id,
        )
        duracion = int((time.time() - t0) * 1000)

        logger.info(
            "INTERCEPCIÓN PEDIDO: Pipeline completado en %dms | exito=%s",
            duracion, resultado.get("exito"),
        )

        # ── Persistir estado en contexto ──
        conversation_context["_pedido_en_progreso"] = not resultado.get("exito")
        if resultado.get("match_result"):
            conversation_context["_pedido_match_result"] = resultado["match_result"]

        # Si el pipeline necesita tienda, guardar estado para siguiente turno
        if resultado.get("bloqueado"):
            conversation_context["_pedido_pendiente_lineas"] = [
                l for l in lineas
            ]
            return _construir_return_agente(
                resultado["respuesta_whatsapp"],
                tool_calls_made,
                conversation_context,
                trace=resultado.get("trace"),
            )

        # ── Pipeline exitoso → retornar respuesta determinística ──
        if resultado.get("exito"):
            conversation_context["_pedido_en_progreso"] = False
            conversation_context.pop("_pedido_pendiente_lineas", None)
            # Guardar excel por si necesita reenviarse
            if resultado.get("excel_bytes"):
                conversation_context["_ultimo_pedido_excel"] = resultado["excel_bytes"]
                conversation_context["_ultimo_pedido_filename"] = resultado.get("excel_filename", "")

        return _construir_return_agente(
            resultado["respuesta_whatsapp"],
            tool_calls_made,
            conversation_context,
            trace=resultado.get("trace"),
        )

    except Exception as e:
        logger.error("INTERCEPCIÓN PEDIDO: Error — %s", e, exc_info=True)
        return None


# ============================================================================
# INTERCEPTOR PARA RESPUESTA RAL PENDIENTE
# ============================================================================

def interceptar_respuesta_ral_pedido(
    conversation_context: dict,
    user_message: str,
) -> Optional[str]:
    """
    Detecta si el usuario está respondiendo con un código RAL
    a una pregunta pendiente del pipeline.

    Returns: código RAL si detectado, None si no.
    """
    if not conversation_context.get("_pedido_pendiente_ral"):
        return None

    user_upper = (user_message or "").upper().strip()
    ral_match = re.search(r'\b(?:RAL\s*)?(\d{4})\b', user_upper)
    if ral_match:
        return ral_match.group(1)
    return None


# ============================================================================
# CONSTRUCTOR DE RESPUESTA AGENTE
# ============================================================================

def _construir_return_agente(
    response_text: str,
    tool_calls_made: list,
    conversation_context: dict,
    trace: dict = None,
) -> dict:
    """Construye dict compatible con generate_agent_reply_v3()."""
    if trace:
        conversation_context["_ultimo_pipeline_pedido_trace"] = trace

    # Recopilar todas las keys de pedido del contexto para persistir
    ctx_updates = {}
    _PERSIST_KEYS = [
        "_pedido_en_progreso",
        "_pedido_match_result",
        "_pedido_pendiente_lineas",
        "_pedido_tienda",
        "_pedido_notas",
        "_pedido_descuentos",
        "_pedido_pendiente_ral",
        "_ultimo_pipeline_pedido_trace",
    ]
    for key in _PERSIST_KEYS:
        val = conversation_context.get(key)
        if val is not None:
            ctx_updates[key] = val
    if trace:
        ctx_updates["_ultimo_pipeline_pedido_trace"] = trace

    return {
        "response_text": response_text,
        "intent": "pedido",
        "tool_calls": tool_calls_made,
        "context_updates": ctx_updates,
        "should_create_task": False,
        "confidence": {"level": "alta", "score": 0.95},
        "is_farewell": False,
    }
