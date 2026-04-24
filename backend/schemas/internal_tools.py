"""Pydantic schemas para herramientas internas (Phase E1).

Contratos estrictos de I/O para las tools BI/ERP que SOLO pueden ser
invocadas por usuarios INTERNAL. Estos schemas:

  * Forzan COP como única moneda válida (``Literal["COP"]``).
  * Rechazan campos extras (``model_config = ConfigDict(extra="forbid")``)
    para evitar que el LLM intente inyectar columnas inventadas.
  * Tienen ``model_dump()`` listo para serializar al LLM.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

Currency = Literal["COP"]


# ─────────────────────────────────────────────────────────────────────────
# check_inventory_bi
# ─────────────────────────────────────────────────────────────────────────


class CheckInventoryBIInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sku: str = Field(..., min_length=1, description="Código exacto del producto.")
    bodega: Optional[str] = Field(
        None, description="Código de bodega/tienda (opcional)."
    )


class InventoryStockRow(BaseModel):
    model_config = ConfigDict(extra="forbid")
    bodega: str
    cantidad: float = Field(ge=0)


class CheckInventoryBIOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sku: str
    descripcion: str
    found: bool
    stock_total: float = Field(ge=0)
    stock_por_bodega: list[InventoryStockRow] = Field(default_factory=list)
    precio_lista: Optional[float] = Field(default=None, ge=0)
    moneda: Currency = "COP"


# ─────────────────────────────────────────────────────────────────────────
# get_cartera_status
# ─────────────────────────────────────────────────────────────────────────


class GetCarteraStatusInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    nit_o_cedula: str = Field(..., min_length=4, description="Identificación del cliente.")


class GetCarteraStatusOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    nit_o_cedula: str
    cliente_codigo: Optional[str] = None
    cliente_nombre: Optional[str] = None
    found: bool
    saldo_pendiente: float = Field(ge=0)
    moneda: Currency = "COP"
    dias_mora_max: int = Field(ge=0, default=0)
    facturas_vencidas: int = Field(ge=0, default=0)


# ─────────────────────────────────────────────────────────────────────────
# submit_order
# ─────────────────────────────────────────────────────────────────────────


class OrderLineInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sku: str = Field(..., min_length=1)
    cantidad: float = Field(..., gt=0)


class SubmitOrderInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    cliente_codigo: str = Field(..., min_length=1)
    lineas: list[OrderLineInput] = Field(..., min_length=1, max_length=50)
    bodega: Optional[str] = None
    nota: Optional[str] = Field(default=None, max_length=500)


class OrderLineConfirmed(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sku: str
    descripcion: str
    cantidad: float = Field(gt=0)
    precio_unitario: float = Field(ge=0)
    subtotal: float = Field(ge=0)


class OrderLineRejected(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sku: str
    cantidad_solicitada: float
    motivo: str  # 'sku_no_encontrado' | 'stock_insuficiente' | 'precio_no_disponible'
    stock_disponible: float = Field(ge=0, default=0)


class SubmitOrderOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    aceptado: bool
    cliente_codigo: str
    bodega: Optional[str] = None
    lineas_confirmadas: list[OrderLineConfirmed] = Field(default_factory=list)
    lineas_rechazadas: list[OrderLineRejected] = Field(default_factory=list)
    total: float = Field(ge=0)
    moneda: Currency = "COP"
    motivo_rechazo: Optional[str] = None  # populated when aceptado=False
    pedido_id: Optional[str] = None  # populated when aceptado=True


__all__ = [
    "Currency",
    "CheckInventoryBIInput",
    "CheckInventoryBIOutput",
    "InventoryStockRow",
    "GetCarteraStatusInput",
    "GetCarteraStatusOutput",
    "SubmitOrderInput",
    "SubmitOrderOutput",
    "OrderLineInput",
    "OrderLineConfirmed",
    "OrderLineRejected",
]
