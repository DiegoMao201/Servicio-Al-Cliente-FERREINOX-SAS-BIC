"""
validador_pedido.py — Gates de validación para pedidos directos
===============================================================

Gates:
    1. validar_tienda               — Tienda especificada y válida
    2. validar_stock                — Stock suficiente para cantidades solicitadas
    3. validar_ral                  — Productos International con RAL completo
    4. validar_bicomponentes        — Catalizador/Ajustador incluidos
    5. validar_compatibilidad_tecnica — Mezclas químicas válidas y sistema completo
    6. validar_completitud          — No hay líneas fallidas sin resolver
"""
from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field, asdict
from functools import lru_cache
from pathlib import Path
from typing import Optional

from .matcher_inventario import ResultadoMatchPedido

from sqlalchemy import create_engine, text

logger = logging.getLogger("pipeline_pedido.validador")

# ============================================================================
# TIENDAS VÁLIDAS
# ============================================================================
TIENDAS_VALIDAS = {
    "155": "CEDI",
    "156": "San Francisco - Armenia",
    "157": "San Antonio - Manizales",
    "158": "Opalo - Dosquebradas",
    "189": "Parque Olaya - Pereira",
    "238": "Laureles",
    "439": "FerreBOX - Pereira",
    "463": "Cerritos",
}

TIENDA_ALIASES = {
    "cedi": "155", "centro de distribucion": "155",
    "armenia": "156", "san francisco": "156",
    "manizales": "157", "san antonio": "157",
    "opalo": "158", "dosquebradas": "158",
    "pereira": "189", "parque olaya": "189", "olaya": "189",
    "laureles": "238",
    "ferrebox": "439", "ferre box": "439",
    "cerritos": "463",
}


CHEMICAL_INCOMPATIBILITIES = [
    ("alquidica", "poliuretano", "Un sistema alquídico no puede rematarse con poliuretano porque compromete la adherencia y la reticulación."),
    ("alquidica", "epoxica", "Un epóxico o imprimante epóxico sobre base alquídica existente exige remoción total del sistema anterior antes de aplicar."),
]


def _read_streamlit_secret_value(*keys: str) -> str | None:
    secrets_path = Path(__file__).resolve().parents[2] / ".streamlit" / "secrets.toml"
    if not secrets_path.exists() or not keys:
        return None
    try:
        raw_text = secrets_path.read_text(encoding="utf-8")
    except Exception:
        return None
    for key in reversed(keys):
        match = re.search(rf'(?mi)^\s*{re.escape(key)}\s*=\s*"([^"]+)"\s*$', raw_text)
        if match:
            return match.group(1).strip()
    return None


def _get_database_url() -> str | None:
    return (
        os.getenv("DATABASE_URL")
        or os.getenv("POSTGRES_DB_URI")
        or _read_streamlit_secret_value("DATABASE_URL")
        or _read_streamlit_secret_value("postgres", "db_uri")
    )


@lru_cache(maxsize=1)
def _load_structured_product_profiles() -> list[dict]:
    database_url = _get_database_url()
    if not database_url:
        return []
    try:
        engine = create_engine(database_url)
        with engine.connect() as conn:
            rows = conn.execute(text("""
                SELECT canonical_family, profile_json
                FROM public.agent_technical_profile
                WHERE extraction_status = 'ready'
            """)).mappings().all()
        profiles = []
        for row in rows:
            profile_json = row.get("profile_json")
            if isinstance(profile_json, str):
                try:
                    profile_json = json.loads(profile_json)
                except Exception:
                    profile_json = {}
            profiles.append({
                "canonical_family": row.get("canonical_family") or "",
                "profile_json": profile_json or {},
            })
        return profiles
    except Exception:
        return []


def _resolve_structured_product_metadata(product_text: str) -> dict:
    normalized_product = (product_text or "").lower()
    if not normalized_product:
        return {}

    for entry in _load_structured_product_profiles():
        profile_json = entry.get("profile_json") or {}
        identity = profile_json.get("product_identity") or {}
        aliases = identity.get("aliases") or []
        candidates = [
            entry.get("canonical_family") or "",
            identity.get("display_name") or "",
            *aliases,
        ]
        if any(candidate and candidate.lower() in normalized_product for candidate in candidates):
            return {
                "chemical_family": profile_json.get("chemical_family"),
                "requires_component_b": bool(profile_json.get("requires_component_b")),
                "component_b_name": profile_json.get("component_b_name"),
                "incompatible_previous_families": profile_json.get("incompatible_previous_families") or [],
            }
    return {}


def resolver_tienda(texto: str) -> tuple[str, str]:
    """Resuelve texto a (codigo_tienda, nombre_tienda)."""
    if not texto:
        return "", ""
    norm = texto.lower().strip()
    # Directo por código
    if norm in TIENDAS_VALIDAS:
        return norm, TIENDAS_VALIDAS[norm]
    # Por alias
    for alias, code in TIENDA_ALIASES.items():
        if alias in norm:
            return code, TIENDAS_VALIDAS.get(code, alias)
    return "", ""


# ============================================================================
# FEEDBACK ESTRUCTURADO
# ============================================================================

@dataclass
class FeedbackPedido:
    """Feedback estructurado para comunicación con el cliente."""
    status: str = "info"  # blocked / warning / info / action_required
    gate: str = ""
    reason: str = ""
    mensaje_usuario: str = ""
    productos_afectados: list[str] = field(default_factory=list)
    sugerencia: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ResultadoValidacion:
    """Resultado de la validación completa del pedido."""
    valido: bool = True
    puede_continuar: bool = True  # True si puede mostrar parcial
    errores: list[str] = field(default_factory=list)
    advertencias: list[str] = field(default_factory=list)
    feedbacks: list[FeedbackPedido] = field(default_factory=list)
    acciones_requeridas: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "valido": self.valido,
            "puede_continuar": self.puede_continuar,
            "errores": self.errores,
            "advertencias": self.advertencias,
            "feedbacks": [f.to_dict() for f in self.feedbacks],
            "acciones_requeridas": self.acciones_requeridas,
        }


# ============================================================================
# GATE 1: VALIDAR TIENDA
# ============================================================================

def validar_tienda(match_result: ResultadoMatchPedido) -> FeedbackPedido | None:
    if not match_result.tienda_codigo:
        return FeedbackPedido(
            status="action_required",
            gate="tienda",
            reason="missing_store",
            mensaje_usuario=(
                "Para verificar disponibilidad y despachar tu pedido necesito "
                "saber la tienda. Cual es la tienda de despacho?\n\n"
                + "\n".join(
                    f"  - *{nombre}*" for nombre in TIENDAS_VALIDAS.values()
                )
            ),
            sugerencia="Preguntar tienda de despacho",
        )
    if match_result.tienda_codigo not in TIENDAS_VALIDAS:
        return FeedbackPedido(
            status="action_required",
            gate="tienda",
            reason="invalid_store",
            mensaje_usuario=(
                f"No reconozco la tienda '{match_result.tienda_nombre}'. "
                "Las tiendas disponibles son:\n"
                + "\n".join(
                    f"  - *{nombre}*" for nombre in TIENDAS_VALIDAS.values()
                )
            ),
            sugerencia="Corregir tienda",
        )
    return None


# ============================================================================
# GATE 2: VALIDAR STOCK
# ============================================================================

def validar_stock(match_result: ResultadoMatchPedido) -> list[FeedbackPedido]:
    feedbacks = []
    for prod in match_result.productos_resueltos:
        if not prod.disponible:
            feedbacks.append(FeedbackPedido(
                status="warning",
                gate="stock",
                reason="out_of_stock",
                mensaje_usuario=(
                    f"*{prod.descripcion_real}* [{prod.codigo_encontrado}]: "
                    f"sin stock disponible en este momento."
                ),
                productos_afectados=[prod.codigo_encontrado],
                sugerencia="Verificar alternativas o esperar reabastecimiento",
            ))
        elif prod.cantidad > prod.stock_disponible:
            feedbacks.append(FeedbackPedido(
                status="warning",
                gate="stock",
                reason="insufficient_stock",
                mensaje_usuario=(
                    f"*{prod.descripcion_real}* [{prod.codigo_encontrado}]: "
                    f"pides {int(prod.cantidad)} pero solo hay "
                    f"{int(prod.stock_disponible)} disponibles."
                ),
                productos_afectados=[prod.codigo_encontrado],
                sugerencia="Ajustar cantidad o verificar en otra tienda",
            ))
    return feedbacks


# ============================================================================
# GATE 3: VALIDAR RAL (Productos International)
# ============================================================================

def validar_ral(match_result: ResultadoMatchPedido) -> list[FeedbackPedido]:
    feedbacks = []
    for pend in match_result.productos_pendientes:
        if pend.razon == "missing_ral":
            feedbacks.append(FeedbackPedido(
                status="action_required",
                gate="ral",
                reason="missing_ral",
                mensaje_usuario=pend.mensaje_usuario,
                productos_afectados=[pend.producto_solicitado],
                sugerencia="Solicitar codigo RAL al cliente",
            ))
        elif pend.razon == "ral_not_found":
            feedbacks.append(FeedbackPedido(
                status="action_required",
                gate="ral",
                reason="ral_not_found",
                mensaje_usuario=pend.mensaje_usuario,
                productos_afectados=[pend.producto_solicitado],
                sugerencia="Verificar RAL con el cliente",
            ))
    return feedbacks


# ============================================================================
# GATE 4: VALIDAR BICOMPONENTES
# ============================================================================

def validar_bicomponentes(match_result: ResultadoMatchPedido) -> list[FeedbackPedido]:
    feedbacks = []
    for bico in match_result.bicomponentes_inyectados:
        if bico.disponible:
            feedbacks.append(FeedbackPedido(
                status="info",
                gate="bicomponentes",
                reason="auto_injected",
                mensaje_usuario=(
                    f"El producto *{bico.para_producto}* requiere "
                    f"*{bico.tipo}: {bico.nombre}*. "
                    f"Lo incluyo automaticamente en tu pedido."
                ),
                productos_afectados=[bico.codigo_encontrado],
                sugerencia=f"Agregar {bico.tipo} {bico.nombre}",
            ))
        else:
            feedbacks.append(FeedbackPedido(
                status="action_required",
                gate="bicomponentes",
                reason="companion_not_found",
                mensaje_usuario=(
                    f"El producto *{bico.para_producto}* necesita "
                    f"*{bico.tipo}: {bico.nombre}* y no lo encontre "
                    f"en inventario. No debo cerrar el pedido incompleto porque el sistema quedaria mal armado."
                ),
                productos_afectados=[bico.nombre],
                sugerencia=f"Resolver {bico.tipo} obligatorio antes de confirmar",
            ))
    return feedbacks


def validar_compatibilidad_tecnica(match_result: ResultadoMatchPedido) -> list[FeedbackPedido]:
    feedbacks: list[FeedbackPedido] = []
    family_to_products: dict[str, list[str]] = {}

    for prod in match_result.productos_resueltos:
        text_blob = " ".join(
            value for value in [prod.descripcion_real, prod.producto_solicitado, prod.linea_international] if value
        )
        profile_metadata = _resolve_structured_product_metadata(text_blob)
        family = profile_metadata.get("chemical_family")
        if not family:
            continue
        family_to_products.setdefault(family, []).append(prod.descripcion_real or prod.producto_solicitado)

    present_families = set(family_to_products)
    for family_a, family_b, reason in CHEMICAL_INCOMPATIBILITIES:
        if family_a in present_families and family_b in present_families:
            affected = family_to_products[family_a] + family_to_products[family_b]
            feedbacks.append(FeedbackPedido(
                status="action_required",
                gate="compatibilidad_tecnica",
                reason="chemical_incompatibility",
                mensaje_usuario=(
                    "Detecté un sistema químicamente incompatible en el pedido. "
                    f"{reason} Necesito corregir la combinación antes de confirmarlo."
                ),
                productos_afectados=affected,
                sugerencia="Reemplazar el sistema por una ruta técnicamente compatible",
            ))

    return feedbacks


# ============================================================================
# GATE 6: VALIDAR COMPLETITUD
# ============================================================================

def validar_completitud(match_result: ResultadoMatchPedido) -> list[FeedbackPedido]:
    feedbacks = []
    for fallido in match_result.productos_fallidos:
        feedbacks.append(FeedbackPedido(
            status="warning",
            gate="completitud",
            reason="product_not_found",
            mensaje_usuario=(
                f"No encontre *{fallido.producto_solicitado}* en el inventario. "
                f"Necesito la referencia exacta o la presentacion para ubicarlo."
            ),
            productos_afectados=[fallido.producto_solicitado],
            sugerencia="Solicitar referencia o aclaración",
        ))
    return feedbacks


# ============================================================================
# VALIDACIÓN COMPLETA
# ============================================================================

def ejecutar_validacion_pedido(
    match_result: ResultadoMatchPedido,
) -> ResultadoValidacion:
    """Ejecuta todos los gates de validación sobre el resultado del matching."""
    resultado = ResultadoValidacion()

    # Gate 1: Tienda
    fb_tienda = validar_tienda(match_result)
    if fb_tienda:
        resultado.feedbacks.append(fb_tienda)
        if fb_tienda.status == "action_required":
            resultado.valido = False
            resultado.puede_continuar = False
            resultado.acciones_requeridas.append(fb_tienda.reason)
            resultado.errores.append(f"[tienda] {fb_tienda.mensaje_usuario}")
            # Si no hay tienda, retornar inmediatamente
            return resultado

    # Gate 2: Stock
    for fb in validar_stock(match_result):
        resultado.feedbacks.append(fb)
        resultado.advertencias.append(f"[stock] {fb.mensaje_usuario}")

    # Gate 3: RAL
    for fb in validar_ral(match_result):
        resultado.feedbacks.append(fb)
        if fb.status == "action_required":
            resultado.acciones_requeridas.append(fb.reason)
            # No bloquea completamente, puede mostrar parcial

    # Gate 4: Bicomponentes
    for fb in validar_bicomponentes(match_result):
        resultado.feedbacks.append(fb)
        if fb.status == "action_required":
            resultado.valido = False
            resultado.puede_continuar = False
            resultado.acciones_requeridas.append(fb.reason)
            resultado.errores.append(f"[bicomponentes] {fb.mensaje_usuario}")
        elif fb.status == "warning":
            resultado.advertencias.append(f"[bicomponentes] {fb.mensaje_usuario}")

    # Gate 5: Compatibilidad tecnica
    for fb in validar_compatibilidad_tecnica(match_result):
        resultado.feedbacks.append(fb)
        if fb.status == "action_required":
            resultado.valido = False
            resultado.puede_continuar = False
            resultado.acciones_requeridas.append(fb.reason)
            resultado.errores.append(f"[compatibilidad_tecnica] {fb.mensaje_usuario}")

    # Gate 6: Completitud
    for fb in validar_completitud(match_result):
        resultado.feedbacks.append(fb)
        resultado.advertencias.append(f"[completitud] {fb.mensaje_usuario}")

    # Si hay acciones requeridas pero el flujo nunca fue bloqueado por gates
    # duros, puede continuar de forma parcial (ej. falta RAL).
    if resultado.acciones_requeridas:
        resultado.valido = False
        if resultado.puede_continuar:
            resultado.puede_continuar = True  # Puede mostrar lo que ya resolvió

    return resultado
