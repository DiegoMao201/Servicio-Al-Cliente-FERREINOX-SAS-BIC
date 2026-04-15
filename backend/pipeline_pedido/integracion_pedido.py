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

_KEYWORDS_PEDIDO = [
    "pedido", "pedir", "pideme", "pídeme", "pide", "necesito",
    "despacho", "despacha", "despachar", "envía", "envia",
    "enviar", "manda", "mandar", "mándame",
    "trasladar", "traslado", "transferencia",
    "solicitame", "solicítame", "solicitar",
    "orden", "ordenar",
]

_KEYWORDS_TIENDA = [
    "pereira", "manizales", "dosquebradas", "armenia",
    "cerritos", "laureles", "ferrebox", "cedi",
    "tienda", "almacén", "almacen", "bodega",
    "189", "157", "158", "156", "463", "238", "439", "155",
]


def _detectar_intencion_pedido(
    user_message: str,
    tool_calls_made: list[dict],
    conversation_context: dict,
) -> bool:
    """Detecta si el mensaje actual es un pedido directo."""
    user_lower = (user_message or "").lower()

    # 1. Keywords explícitas de pedido
    tiene_keyword = any(kw in user_lower for kw in _KEYWORDS_PEDIDO)

    # 2. Herramientas de inventario usadas en este turno
    inventory_tools = {"consultar_inventario", "consultar_inventario_lote"}
    tools_used = {tc["name"] for tc in tool_calls_made}
    uso_inventario = bool(tools_used & inventory_tools)

    # 3. Contexto: hay pedido en progreso
    pedido_en_progreso = conversation_context.get("_pedido_en_progreso", False)

    # 4. Contexto: empleado interno (los empleados suelen hacer pedidos directos)
    es_interno = conversation_context.get("internal_auth", False)

    # Regla compuesta
    if tiene_keyword and (uso_inventario or es_interno):
        return True
    if pedido_en_progreso:
        return True

    return False


def _extraer_tienda_de_mensaje(user_message: str) -> str:
    """Extrae texto de tienda del mensaje libre."""
    user_lower = (user_message or "").lower()
    for kw in _KEYWORDS_TIENDA:
        if kw in user_lower:
            return kw
    return ""


def _parsear_lineas_pedido(
    user_message: str,
    tool_calls_made: list[dict],
) -> list[dict]:
    """
    Extrae líneas de pedido del mensaje y/o resultados de herramientas.

    Cada linea: {producto: str, cantidad: int, unidad: str, codigo: str}
    """
    lineas = []

    # 1. Extraer de tool results (consultar_inventario devuelve productos)
    for tc in tool_calls_made:
        if tc["name"] in ("consultar_inventario", "consultar_inventario_lote"):
            try:
                result = json.loads(tc.get("result", "{}"))
                if isinstance(result, dict):
                    items = result.get("items") or result.get("resultados") or []
                    for item in items:
                        if isinstance(item, dict) and item.get("referencia"):
                            lineas.append({
                                "producto": item.get("descripcion", ""),
                                "cantidad": item.get("cantidad_solicitada", 1),
                                "unidad": item.get("unidad", "UND"),
                                "codigo": item.get("referencia", ""),
                            })
            except (json.JSONDecodeError, TypeError):
                pass

    # 2. Parsear del mensaje libre (patrón: cantidad + producto)
    patrones = [
        # "10 galones de viniltex blanco"
        r'(\d+)\s*(gal(?:ones?)?|cun(?:etes?)?|und|unidades?|lt|litros?|kg)\s+(?:de\s+)?(.+?)(?:\n|,|$)',
        # "viniltex blanco x 10"
        r'(.+?)\s+x\s*(\d+)',
        # "5 koraza rojo"
        r'(\d+)\s+([a-záéíóú][a-záéíóú\s]+)',
    ]
    user_msg = user_message or ""
    for pat in patrones:
        for m in re.finditer(pat, user_msg, re.IGNORECASE):
            groups = m.groups()
            if len(groups) == 3:
                cant, unidad, prod = groups
                lineas.append({
                    "producto": prod.strip(),
                    "cantidad": int(cant),
                    "unidad": unidad.strip(),
                    "codigo": "",
                })
            elif len(groups) == 2:
                prod, cant = groups
                try:
                    cant_int = int(cant)
                    lineas.append({
                        "producto": prod.strip(),
                        "cantidad": cant_int,
                        "unidad": "UND",
                        "codigo": "",
                    })
                except ValueError:
                    pass

    return lineas


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
    # ── Guard: detectar intención ──
    if not _detectar_intencion_pedido(
        user_message, tool_calls_made, conversation_context,
    ):
        return None

    # ── Parsear líneas de pedido ──
    lineas = _parsear_lineas_pedido(user_message, tool_calls_made)
    if not lineas:
        return None

    logger.info(
        "INTERCEPCIÓN PEDIDO: %d líneas detectadas | conv=%s",
        len(lineas), context.get("conversation_id", "?"),
    )

    # ── Extraer contexto ──
    tienda_texto = (
        conversation_context.get("_pedido_tienda")
        or _extraer_tienda_de_mensaje(user_message)
    )
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

    return {
        "response_text": response_text,
        "intent": "pedido",
        "tool_calls": tool_calls_made,
        "context_updates": {
            key: value
            for key, value in {
                "_pedido_en_progreso": conversation_context.get("_pedido_en_progreso"),
                "_pedido_match_result": conversation_context.get("_pedido_match_result"),
                "_ultimo_pipeline_pedido_trace": trace,
            }.items()
            if value is not None
        },
        "should_create_task": False,
        "confidence": 0.95,
        "is_farewell": False,
    }
