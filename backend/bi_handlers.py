"""Handlers internos BI/ERP (Phase E1) — sólo accesibles por SessionContext.role=INTERNAL.

Cada handler:
  1. Valida la entrada con su Pydantic input schema.
  2. Ejecuta la consulta determinista contra la BD (sin LLM).
  3. Devuelve un Pydantic output schema serializable.
  4. NUNCA inventa columnas: si la consulta SQL no devolvió un campo,
     el campo en el output queda en su default seguro (0, None, []).
  5. Toda cifra monetaria se etiqueta y devuelve en COP.

Diseño: cada handler recibe explícitamente sus dependencias (engine SQL +
SessionContext) para que los tests puedan pasar mocks deterministas.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Optional

try:
    from schemas.internal_tools import (
        CheckInventoryBIInput,
        CheckInventoryBIOutput,
        GetCarteraStatusInput,
        GetCarteraStatusOutput,
        InventoryStockRow,
        OrderLineConfirmed,
        OrderLineRejected,
        SubmitOrderInput,
        SubmitOrderOutput,
    )
    from session_context import SessionContext, UserRole
except ImportError:
    from backend.schemas.internal_tools import (
        CheckInventoryBIInput,
        CheckInventoryBIOutput,
        GetCarteraStatusInput,
        GetCarteraStatusOutput,
        InventoryStockRow,
        OrderLineConfirmed,
        OrderLineRejected,
        SubmitOrderInput,
        SubmitOrderOutput,
    )
    from backend.session_context import SessionContext, UserRole

logger = logging.getLogger("bi_handlers")


class RBACDeniedError(PermissionError):
    """Se eleva cuando un handler interno es invocado por sesión EXTERNAL."""


def _require_internal(session: SessionContext, tool_name: str) -> None:
    """Aborta inmediatamente si la sesión NO es INTERNAL."""
    if not session.is_internal:
        logger.warning(
            "RBAC DENY: tool=%s role=%s phone=%s",
            tool_name,
            session.role.value,
            session.phone_e164,
        )
        raise RBACDeniedError(
            f"Tool '{tool_name}' requiere sesión INTERNA. "
            f"Sesión actual: role={session.role.value}."
        )


# ─────────────────────────────────────────────────────────────────────────
# check_inventory_bi
# ─────────────────────────────────────────────────────────────────────────


def handle_check_inventory_bi(
    raw_args: dict,
    session: SessionContext,
    *,
    inventory_lookup_fn,
) -> CheckInventoryBIOutput:
    """Lookup determinista de stock + precio para UN SKU exacto.

    Args:
        raw_args: dict crudo del LLM tool call. Validado por Pydantic.
        session: SessionContext (debe ser INTERNAL).
        inventory_lookup_fn: callable(sku, bodega) -> dict | None con keys:
            sku, descripcion, stock_total, stock_por_bodega (lista
            de {bodega, cantidad}), precio_lista (Optional[float]).

    Returns:
        CheckInventoryBIOutput. Si el SKU no existe: ``found=False`` y
        cifras en cero — NO se inventan datos.
    """
    _require_internal(session, "check_inventory_bi")
    args = CheckInventoryBIInput.model_validate(raw_args)
    row = inventory_lookup_fn(args.sku, args.bodega)
    if not row:
        return CheckInventoryBIOutput(
            sku=args.sku,
            descripcion="(no encontrado)",
            found=False,
            stock_total=0.0,
            stock_por_bodega=[],
            precio_lista=None,
        )
    stock_rows = [
        InventoryStockRow(
            bodega=str(r.get("bodega", "")),
            cantidad=float(r.get("cantidad", 0) or 0),
        )
        for r in (row.get("stock_por_bodega") or [])
    ]
    return CheckInventoryBIOutput(
        sku=row.get("sku", args.sku),
        descripcion=row.get("descripcion", ""),
        found=True,
        stock_total=float(row.get("stock_total", 0) or 0),
        stock_por_bodega=stock_rows,
        precio_lista=(
            float(row["precio_lista"])
            if row.get("precio_lista") is not None
            else None
        ),
    )


# ─────────────────────────────────────────────────────────────────────────
# get_cartera_status
# ─────────────────────────────────────────────────────────────────────────


def handle_get_cartera_status(
    raw_args: dict,
    session: SessionContext,
    *,
    cartera_lookup_fn,
) -> GetCarteraStatusOutput:
    """Saldo pendiente y mora para un NIT/cédula.

    Args:
        cartera_lookup_fn: callable(nit_o_cedula) -> dict | None con keys:
            cliente_codigo, cliente_nombre, saldo_pendiente,
            dias_mora_max, facturas_vencidas. Toda cifra en COP.
    """
    _require_internal(session, "get_cartera_status")
    args = GetCarteraStatusInput.model_validate(raw_args)
    row = cartera_lookup_fn(args.nit_o_cedula)
    if not row:
        return GetCarteraStatusOutput(
            nit_o_cedula=args.nit_o_cedula,
            cliente_codigo=None,
            cliente_nombre=None,
            found=False,
            saldo_pendiente=0.0,
            dias_mora_max=0,
            facturas_vencidas=0,
        )
    return GetCarteraStatusOutput(
        nit_o_cedula=args.nit_o_cedula,
        cliente_codigo=row.get("cliente_codigo"),
        cliente_nombre=row.get("cliente_nombre"),
        found=True,
        saldo_pendiente=float(row.get("saldo_pendiente", 0) or 0),
        dias_mora_max=int(row.get("dias_mora_max", 0) or 0),
        facturas_vencidas=int(row.get("facturas_vencidas", 0) or 0),
    )


# ─────────────────────────────────────────────────────────────────────────
# submit_order  (Move & Wire de la deuda C3)
# ─────────────────────────────────────────────────────────────────────────


def handle_submit_order(
    raw_args: dict,
    session: SessionContext,
    *,
    inventory_lookup_fn,
    persist_order_fn,
) -> SubmitOrderOutput:
    """Crea un pedido validando cada SKU contra inventario antes de confirmar.

    Args:
        inventory_lookup_fn: igual que en ``handle_check_inventory_bi``.
            Se invoca por cada línea para validar disponibilidad y precio.
        persist_order_fn: callable(payload) -> str con el ID del pedido
            persistido. Sólo se invoca si TODAS las líneas pasaron validación.

    Política: si AUNQUE SEA UNA línea es inválida (SKU inexistente, sin
    stock o sin precio), el pedido completo se rechaza —
    ``aceptado=False`` — y se devuelve la lista de motivos.
    Esto previene pedidos parciales no consentidos.
    """
    _require_internal(session, "submit_order")
    args = SubmitOrderInput.model_validate(raw_args)

    confirmed: list[OrderLineConfirmed] = []
    rejected: list[OrderLineRejected] = []
    total = 0.0

    for linea in args.lineas:
        row = inventory_lookup_fn(linea.sku, args.bodega)
        if not row:
            rejected.append(
                OrderLineRejected(
                    sku=linea.sku,
                    cantidad_solicitada=linea.cantidad,
                    motivo="sku_no_encontrado",
                    stock_disponible=0.0,
                )
            )
            continue
        stock_total = float(row.get("stock_total", 0) or 0)
        precio = row.get("precio_lista")
        if stock_total < linea.cantidad:
            rejected.append(
                OrderLineRejected(
                    sku=linea.sku,
                    cantidad_solicitada=linea.cantidad,
                    motivo="stock_insuficiente",
                    stock_disponible=stock_total,
                )
            )
            continue
        if precio is None:
            rejected.append(
                OrderLineRejected(
                    sku=linea.sku,
                    cantidad_solicitada=linea.cantidad,
                    motivo="precio_no_disponible",
                    stock_disponible=stock_total,
                )
            )
            continue
        precio_unit = float(precio)
        subtotal = round(precio_unit * linea.cantidad, 2)
        confirmed.append(
            OrderLineConfirmed(
                sku=linea.sku,
                descripcion=str(row.get("descripcion", "")),
                cantidad=linea.cantidad,
                precio_unitario=precio_unit,
                subtotal=subtotal,
            )
        )
        total += subtotal

    if rejected:
        logger.info(
            "submit_order rechazado: %d líneas inválidas (cliente=%s)",
            len(rejected),
            args.cliente_codigo,
        )
        return SubmitOrderOutput(
            aceptado=False,
            cliente_codigo=args.cliente_codigo,
            bodega=args.bodega,
            lineas_confirmadas=confirmed,
            lineas_rechazadas=rejected,
            total=round(total, 2),
            motivo_rechazo=(
                "Una o más líneas no pasaron validación de inventario/precio. "
                "Revisar 'lineas_rechazadas' antes de reintentar."
            ),
            pedido_id=None,
        )

    persist_payload = {
        "cliente_codigo": args.cliente_codigo,
        "bodega": args.bodega,
        "nota": args.nota,
        "internal_user_id": session.internal_user_id,
        "lineas": [c.model_dump() for c in confirmed],
        "total": round(total, 2),
        "moneda": "COP",
    }
    pedido_id = str(persist_order_fn(persist_payload) or uuid.uuid4())
    logger.info(
        "submit_order ok: pedido=%s cliente=%s total=%s COP",
        pedido_id,
        args.cliente_codigo,
        round(total, 2),
    )
    return SubmitOrderOutput(
        aceptado=True,
        cliente_codigo=args.cliente_codigo,
        bodega=args.bodega,
        lineas_confirmadas=confirmed,
        lineas_rechazadas=[],
        total=round(total, 2),
        motivo_rechazo=None,
        pedido_id=pedido_id,
    )


__all__ = [
    "RBACDeniedError",
    "handle_check_inventory_bi",
    "handle_get_cartera_status",
    "handle_submit_order",
]
