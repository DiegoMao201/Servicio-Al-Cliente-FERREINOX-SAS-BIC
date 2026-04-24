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
import unicodedata
from typing import Callable, Optional

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

_UNIT_PAT = (
    r'(?:gal(?:[oó]n(?:es?)?)?|gl|cuart(?:os?)?|cu(?:[ñn])etes?|'
    r'und(?:idades?)?|lt|litros?|kg|octav(?:os?)?|'
    r'medio\s+cu(?:[ñn])etes?|baldes?|1/[1245])'
)

_STOCK_CONFIRMATION_HINTS = [
    "esta bien",
    "está bien",
    "esta perfecto",
    "está perfecto",
    "dejalo asi",
    "déjalo así",
    "asi esta bien",
    "así está bien",
    "me sirve",
    "sirve",
    "dale asi",
    "dale así",
    "con eso esta bien",
    "con eso está bien",
]


def _normalize_text(text_value: str) -> str:
    normalized = unicodedata.normalize("NFKD", str(text_value or ""))
    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    normalized = re.sub(r'[^a-z0-9]+', ' ', normalized.lower()).strip()
    return normalized


def _canonicalize_unit(value: str) -> str:
    normalized = _normalize_text(value)
    if not normalized:
        return ""
    if "medio cunete" in normalized or "medio cunete" in normalized:
        return "balde"
    if "cunete" in normalized:
        return "cunete"
    if "gal" in normalized or normalized == "gl":
        return "galon"
    if "cuart" in normalized:
        return "cuarto"
    if "octav" in normalized:
        return "octavo"
    if "balde" in normalized:
        return "balde"
    if normalized.startswith("und"):
        return "und"
    return normalized.split()[0]


def _message_looks_like_stock_confirmation(user_message: str) -> bool:
    normalized = _normalize_text(user_message)
    if not normalized or not re.search(r'\b\d+(?:[.,]\d+)?\b', user_message or ""):
        return False
    return any(hint in normalized for hint in _STOCK_CONFIRMATION_HINTS)


def _extract_stock_confirmation_mentions(user_message: str) -> list[dict]:
    mentions = []
    pattern = re.compile(
        rf'(?:^|\b(?:y|,|;|\.))\s*(?:los?\s+)?(\d+(?:[.,]\d+)?)\s+({_UNIT_PAT})(.*?)(?=(?:\s+\b(?:y|,|;|\.)\b\s*(?:los?\s+)?\d+(?:[.,]\d+)?\s+{_UNIT_PAT})|$)',
        re.IGNORECASE,
    )
    for match in pattern.finditer(user_message or ""):
        qty = float(match.group(1).replace(",", "."))
        unit = _canonicalize_unit(match.group(2))
        tail_text = (match.group(3) or "").strip()
        mentions.append(
            {
                "qty": qty,
                "unit": unit,
                "tail_text": tail_text,
                "tail_tokens": set(_normalize_text(tail_text).split()),
            }
        )
    return mentions


def _build_stock_confirmation_candidates(match_result: dict) -> list[dict]:
    candidates = []
    for index, prod in enumerate((match_result or {}).get("productos_resueltos") or []):
        requested_qty = float(prod.get("cantidad") or 0)
        available_qty = float(prod.get("stock_disponible") or 0)
        if available_qty <= 0 or requested_qty <= available_qty:
            continue
        token_source = " ".join(
            str(value or "")
            for value in [
                prod.get("producto_solicitado"),
                prod.get("descripcion_real"),
                prod.get("original_text"),
                prod.get("codigo_encontrado"),
            ]
        )
        candidates.append(
            {
                "index": index,
                "requested_qty": requested_qty,
                "available_qty": available_qty,
                "unit": _canonicalize_unit(prod.get("unidad") or prod.get("presentacion_real") or ""),
                "tokens": {token for token in _normalize_text(token_source).split() if len(token) >= 2},
            }
        )
    return candidates


def _match_stock_confirmation_adjustments(match_result: dict, user_message: str) -> dict[int, float]:
    if not _message_looks_like_stock_confirmation(user_message):
        return {}
    mentions = _extract_stock_confirmation_mentions(user_message)
    if not mentions:
        return {}

    candidates = _build_stock_confirmation_candidates(match_result)
    if not candidates:
        return {}

    adjustments: dict[int, float] = {}
    available_by_signature = {}
    for candidate in candidates:
        signature = (candidate["available_qty"], candidate["unit"])
        available_by_signature.setdefault(signature, []).append(candidate)

    for mention in mentions:
        signature = (mention["qty"], mention["unit"])
        same_signature = [c for c in available_by_signature.get(signature, []) if c["index"] not in adjustments]
        if not same_signature:
            continue
        if len(same_signature) == 1:
            adjustments[same_signature[0]["index"]] = same_signature[0]["available_qty"]
            continue

        if mention["tail_tokens"]:
            overlapped = [
                candidate
                for candidate in same_signature
                if candidate["tokens"] & mention["tail_tokens"]
            ]
            if len(overlapped) == 1:
                adjustments[overlapped[0]["index"]] = overlapped[0]["available_qty"]

    return adjustments


def _rebuild_lines_from_previous_match(match_result: dict, adjustments: dict[int, float]) -> list[dict]:
    rebuilt_lines = []

    for index, prod in enumerate((match_result or {}).get("productos_resueltos") or []):
        quantity = adjustments.get(index, float(prod.get("cantidad") or 0) or 1)
        unit = prod.get("unidad") or prod.get("presentacion_real") or "UND"
        product_name = prod.get("producto_solicitado") or prod.get("descripcion_real") or prod.get("original_text") or ""
        rebuilt_lines.append(
            {
                "texto": f"{int(quantity) if float(quantity).is_integer() else quantity} {unit} {product_name}".strip(),
                "producto": product_name,
                "cantidad": quantity,
                "unidad": unit,
                "codigos": [],
            }
        )

    for pending in (match_result or {}).get("productos_pendientes") or []:
        rebuilt_lines.append(
            {
                "texto": pending.get("original_text") or pending.get("producto_solicitado") or "",
                "producto": pending.get("producto_solicitado") or "",
                "cantidad": float(pending.get("cantidad") or 0) or 1,
                "unidad": pending.get("unidad") or "UND",
                "codigos": [],
            }
        )

    for failed in (match_result or {}).get("productos_fallidos") or []:
        rebuilt_lines.append(
            {
                "texto": failed.get("original_text") or failed.get("producto_solicitado") or "",
                "producto": failed.get("producto_solicitado") or "",
                "cantidad": float(failed.get("cantidad") or 0) or 1,
                "unidad": failed.get("unidad") or "UND",
                "codigos": [],
            }
        )

    return [line for line in rebuilt_lines if line.get("producto")]


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


def _normalize_brush_size_token(raw_size: str) -> str:
    cleaned = re.sub(r'["“”″]', '', str(raw_size or '')).strip().replace(' ', '')
    if re.fullmatch(r'\d1/2', cleaned):
        return f"{cleaned[0]} 1/2"
    if re.fullmatch(r'\d+', cleaned):
        return cleaned
    return cleaned


def _expand_brush_size_line(raw_line: str) -> list[dict]:
    line = (raw_line or '').strip()
    match = re.match(r'^\s*(\d+(?:[.,]\d+)?)\s+brochas?\s+(.+?)\s+de:\s*(.+)$', line, re.IGNORECASE)
    if not match:
        return []

    quantity = _parse_num(match.group(1))
    base_product = match.group(2).strip()
    sizes_blob = match.group(3).strip()
    size_tokens = re.findall(r'\d1/2|\d+(?=\s*["“”″]|\s|,|$)', sizes_blob)
    normalized_sizes = []
    for token in size_tokens:
        normalized = _normalize_brush_size_token(token)
        if normalized and normalized not in normalized_sizes:
            normalized_sizes.append(normalized)

    return [
        {
            "texto": raw_line.strip(),
            "producto": f"brocha {base_product} {size}".strip(),
            "cantidad": quantity,
            "unidad": "UND",
            "codigos": [],
        }
        for size in normalized_sizes
    ]


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

    for raw_line in re.split(r'[\n\r]+', user_msg):
        line = raw_line.strip()
        if not line:
            continue
        # Ignorar líneas que son puro contexto conversacional (sin productos)
        line_lower = line.lower()
        if _es_linea_contexto(line_lower):
            continue

        expanded_brush_lines = _expand_brush_size_line(raw_line)
        if expanded_brush_lines:
            lineas.extend(expanded_brush_lines)
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
        r'^\s*(?:necesito\s+)?(?:este\s+)?pedido\s*:??\s*$',
        r'^\s*(?:puedo|podemos|quiero|quisiera|necesito)\s+(?:montar|armar|hacer|crear|generar|pasar)\s+(?:un\s+)?pedido\b.*$',
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
    lookup_fn: Optional[Callable] = None,
    price_fn: Optional[Callable] = None,
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
                lookup_fn=lookup_fn, price_fn=price_fn,
            )
        # El usuario dijo algo pero no es tienda — quizá es un producto más o contexto
        # Dejar que caiga al flujo normal

    # ── CASO 2: Confirmación de cantidades disponibles por advertencias de stock ──
    stock_pending = conversation_context.get("_pedido_stock_por_confirmar") or []
    previous_match = conversation_context.get("_pedido_match_result") or {}
    if stock_pending and previous_match:
        adjustments = _match_stock_confirmation_adjustments(previous_match, user_message)
        if adjustments:
            logger.info(
                "INTERCEPCIÓN PEDIDO: confirmación de stock detectada, ajustando %d líneas | conv=%s",
                len(adjustments), context.get("conversation_id", "?"),
            )
            rebuilt_lines = _rebuild_lines_from_previous_match(previous_match, adjustments)
            conversation_context.pop("_pedido_stock_por_confirmar", None)
            tienda_texto = conversation_context.get("_pedido_tienda") or previous_match.get("tienda_nombre") or previous_match.get("tienda_codigo") or ""
            return _ejecutar_pipeline(
                main_module,
                conversation_context,
                rebuilt_lines,
                tienda_texto,
                tool_calls_made,
                context,
                lookup_fn=lookup_fn,
                price_fn=price_fn,
            )

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
        lookup_fn=lookup_fn, price_fn=price_fn,
    )


def _ejecutar_pipeline(
    main_module,
    conversation_context: dict,
    lineas: list[dict],
    tienda_texto: str,
    tool_calls_made: list[dict],
    context: dict,
    lookup_fn: Optional[Callable] = None,
    price_fn: Optional[Callable] = None,
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

    # ── Inyectar funciones reales ──
    # Prioridad: funciones pasadas explícitamente > getattr > sys.modules > import directo
    import sys as _sys

    if not lookup_fn or not price_fn:
        _candidates = [main_module]
        for _mod_name in ("main", "__main__", "backend.main"):
            _m = _sys.modules.get(_mod_name)
            if _m and _m is not main_module:
                _candidates.append(_m)

        def _resolve(fn_name):
            for _mod in _candidates:
                fn = getattr(_mod, fn_name, None)
                if fn is not None:
                    return fn
            return None

        lookup_fn = lookup_fn or _resolve("lookup_product_context")
        price_fn = price_fn or _resolve("fetch_product_price")
        send_email_fn = _resolve("send_sendgrid_email")
        upload_dropbox_fn = _resolve("upload_bytes_to_dropbox")

        # Último recurso: import directo
        if lookup_fn is None:
            try:
                import main as _direct_main
                lookup_fn = getattr(_direct_main, "lookup_product_context", None)
                price_fn = price_fn or getattr(_direct_main, "fetch_product_price", None)
                logger.warning("_ejecutar_pipeline: lookup_fn recuperado via import directo")
            except Exception as exc:
                logger.error("_ejecutar_pipeline: NO se pudo importar main: %s", exc)
    else:
        send_email_fn = getattr(main_module, "send_sendgrid_email", None)
        upload_dropbox_fn = getattr(main_module, "upload_bytes_to_dropbox", None)

    logger.info(
        "_ejecutar_pipeline: lookup_fn=%s, price_fn=%s",
        type(lookup_fn).__name__ if lookup_fn else "NONE",
        type(price_fn).__name__ if price_fn else "NONE",
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
            shortage_candidates = _build_stock_confirmation_candidates(resultado["match_result"])
            if shortage_candidates:
                conversation_context["_pedido_stock_por_confirmar"] = [
                    {
                        "index": candidate["index"],
                        "requested_qty": candidate["requested_qty"],
                        "available_qty": candidate["available_qty"],
                        "unit": candidate["unit"],
                    }
                    for candidate in shortage_candidates
                ]
            else:
                conversation_context.pop("_pedido_stock_por_confirmar", None)

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
        "_pedido_stock_por_confirmar",
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
