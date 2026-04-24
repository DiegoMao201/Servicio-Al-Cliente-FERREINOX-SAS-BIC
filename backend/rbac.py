"""Dynamic Tool Binding por rol RBAC (Phase E1).

Construye el array de ``tools`` que se envía al LLM según el
``SessionContext.role``. Política de mínimo privilegio:

  EXTERNAL → conjunto reducido (asesoría técnica + cartera/compras
             del PROPIO cliente verificado + reclamos).
  INTERNAL → conjunto reducido + inventario en vivo + cartera de
             cualquier cliente + creación de pedidos + BI universal.

Las definiciones JSON-schema vienen de ``agent_prompt_v3.AGENT_TOOLS_V3``;
este módulo añade las 3 definiciones nuevas de Fase E1
(``check_inventory_bi``, ``get_cartera_status``, ``submit_order``)
y hace el filtro determinista. Si el LLM intenta llamar una tool
fuera de su whitelist, el orquestador lo trata como violación crítica.
"""

from __future__ import annotations

from typing import Any

try:
    from agent_prompt_v3 import AGENT_TOOLS_V3
    from session_context import SessionContext, UserRole
except ImportError:
    from backend.agent_prompt_v3 import AGENT_TOOLS_V3
    from backend.session_context import SessionContext, UserRole


# ─────────────────────────────────────────────────────────────────────────
# Whitelists — fuente única de verdad. Cualquier tool fuera de estos sets
# es invisible para el LLM en el rol correspondiente.
# ─────────────────────────────────────────────────────────────────────────

_EXTERNAL_TOOL_WHITELIST: frozenset[str] = frozenset(
    {
        "consultar_conocimiento_tecnico",
        "buscar_documento_tecnico",
        "verificar_identidad",
        "consultar_cartera",     # del PROPIO cliente verificado
        "consultar_compras",     # del PROPIO cliente verificado
        "radicar_reclamo",
    }
)

_INTERNAL_TOOL_WHITELIST: frozenset[str] = frozenset(
    {
        # Asesoría técnica (compartida con EXTERNAL)
        "consultar_conocimiento_tecnico",
        "buscar_documento_tecnico",
        # ERP / BI — exclusivo INTERNAL
        "check_inventory_bi",
        "get_cartera_status",
        "submit_order",
        # Tools legacy ERP (conviven con las nuevas Phase E1)
        "consultar_inventario",
        "consultar_inventario_lote",
        "consultar_cartera",
        "consultar_compras",
        "consultar_bi_universal",
        "consultar_ventas_internas",
        "consultar_indicadores_internos",
        "enviar_reporte_interno_correo",
        "sugerir_reposicion_bodega",
        "solicitar_traslado_interno",
        # Operación
        "verificar_identidad",
        "radicar_reclamo",
        "confirmar_pedido_y_generar_pdf",
        "registrar_cliente_nuevo",
        "guardar_aprendizaje_producto",
        "guardar_producto_complementario",
        "registrar_conocimiento_experto",
    }
)


# ─────────────────────────────────────────────────────────────────────────
# Definiciones JSON-schema de las tools nuevas Phase E1
# (formato OpenAI / function-calling — compatible con Gemini & Anthropic).
# ─────────────────────────────────────────────────────────────────────────

_E1_TOOL_DEFINITIONS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "check_inventory_bi",
            "description": (
                "[INTERNAL ONLY] Lookup determinista de stock + precio (COP) "
                "para UN SKU exacto. Devuelve schema CheckInventoryBIOutput "
                "con stock_total, stock_por_bodega y precio_lista. "
                "Si el SKU no existe: found=False y cifras en 0. "
                "NO inventes columnas; el output viene de SQL real."
            ),
            "parameters": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "sku": {
                        "type": "string",
                        "description": "Código exacto del producto (case-insensitive).",
                    },
                    "bodega": {
                        "type": "string",
                        "description": "Código de bodega/tienda. Omitir para consolidado.",
                    },
                },
                "required": ["sku"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_cartera_status",
            "description": (
                "[INTERNAL ONLY] Saldo pendiente y mora de un cliente por NIT/cédula. "
                "Cifras SIEMPRE en COP. Si el cliente no existe: found=False, "
                "saldo 0. Útil para el flujo: cliente cita NIT → asesor "
                "valida cartera → decide si autoriza pedido a crédito."
            ),
            "parameters": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "nit_o_cedula": {
                        "type": "string",
                        "description": "NIT (sin DV) o cédula del cliente.",
                    }
                },
                "required": ["nit_o_cedula"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "submit_order",
            "description": (
                "[INTERNAL ONLY] Crea un pedido en firme. Por cada línea valida "
                "SKU + stock + precio antes de aceptar. Si CUALQUIER línea es "
                "inválida, el pedido completo es rechazado (aceptado=False) y "
                "se devuelve la lista de motivos por línea. Cuando aceptado=True "
                "devuelve pedido_id. Total siempre en COP."
            ),
            "parameters": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "cliente_codigo": {
                        "type": "string",
                        "description": "Código interno del cliente (no NIT).",
                    },
                    "bodega": {
                        "type": "string",
                        "description": "Bodega de despacho. Omitir para default.",
                    },
                    "nota": {
                        "type": "string",
                        "description": "Comentario libre opcional para el pedido.",
                    },
                    "lineas": {
                        "type": "array",
                        "minItems": 1,
                        "maxItems": 50,
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "sku": {"type": "string"},
                                "cantidad": {"type": "number", "exclusiveMinimum": 0},
                            },
                            "required": ["sku", "cantidad"],
                        },
                    },
                },
                "required": ["cliente_codigo", "lineas"],
            },
        },
    },
]


# ─────────────────────────────────────────────────────────────────────────
# Builder — única función que el orquestador debe llamar.
# ─────────────────────────────────────────────────────────────────────────


def _index_tools_by_name(tools: list[dict]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for tool in tools:
        name = ((tool or {}).get("function") or {}).get("name")
        if name:
            out[name] = tool
    return out


def _whitelist_for(role: UserRole) -> frozenset[str]:
    if role == UserRole.INTERNAL:
        return _INTERNAL_TOOL_WHITELIST
    return _EXTERNAL_TOOL_WHITELIST


def build_tools_for_session(
    session: SessionContext,
    *,
    extra_tool_definitions: list[dict] | None = None,
) -> list[dict]:
    """Devuelve el array de tools que se debe pasar al LLM.

    Args:
        session: SessionContext inmutable con el rol del usuario.
        extra_tool_definitions: tools adicionales (típicamente vacío;
            permite tests inyectar fakes).

    Política:
      * Roles desconocidos → tratado como EXTERNAL.
      * Tools cuyo nombre no está en la whitelist del rol → eliminadas.
      * Cero salida vacía: si la whitelist se vacía, devuelve [] y el
        LLM responde sin function calling.
    """
    catalog: dict[str, dict] = {}
    catalog.update(_index_tools_by_name(AGENT_TOOLS_V3))
    catalog.update(_index_tools_by_name(_E1_TOOL_DEFINITIONS))
    if extra_tool_definitions:
        catalog.update(_index_tools_by_name(extra_tool_definitions))

    allowed = _whitelist_for(session.role)
    return [catalog[name] for name in catalog if name in allowed]


def is_tool_allowed_for_session(tool_name: str, session: SessionContext) -> bool:
    """Guard explícito antes de ejecutar el handler de la tool.

    Defensa en profundidad: aunque el array de tools enviado al LLM
    ya esté filtrado, NUNCA confiar — el dispatcher debe re-verificar
    contra esta función antes de invocar el handler real.
    """
    return tool_name in _whitelist_for(session.role)


__all__ = [
    "build_tools_for_session",
    "is_tool_allowed_for_session",
    "_EXTERNAL_TOOL_WHITELIST",
    "_INTERNAL_TOOL_WHITELIST",
]
