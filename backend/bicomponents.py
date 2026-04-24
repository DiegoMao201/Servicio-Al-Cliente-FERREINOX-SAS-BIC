"""Catálogo verificado de productos bicomponentes.

Fuente de verdad interna: los catalizadores y proporciones aquí registrados
PREVALECEN sobre cualquier respuesta del RAG o memoria del LLM.
Si el RAG no confirma la relación, el agente DEBE citar este catálogo.

Módulo extraído de `backend/main.py` durante la Fase C2 (modularización).
La lógica interna NO fue modificada; solo movida y aislada.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Optional


def _normalize_for_match(text_value: Optional[str]) -> str:
    """Versión local mínima de `normalize_text_value` para evitar dependencia
    circular con `backend.main`. Equivalente funcional al normalizador global."""
    if not text_value:
        return ""
    normalized = unicodedata.normalize("NFKD", text_value)
    normalized = "".join(character for character in normalized if not unicodedata.combining(character))
    normalized = normalized.lower()
    normalized = re.sub(r"[^a-z0-9./+-]+", " ", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


BICOMPONENT_CATALOG: dict[str, dict] = {
    # ─ Pintucoat (Pintuco) ─────────────────────────────────────────────────
    # galón COMP A (3.44L, ref 516 o 517) → catalizador 13227 COMP B 0.37L (1/8)
    # cuñete COMP A (15.14L) → catalizador 13227 COMP B 1.89L
    "pintucoat": {
        "tipo_sistema": "epoxica_dos_componentes",
        "componente_a_descripcion": "Pintucoat 516 o 517 COMP A (base de color)",
        "componente_b_codigo": "13227",
        "componente_b_descripcion": "Pintucoat COMP B catalizador",
        "proporcion_galon": "COMP A 3.44L + catalizador 13227 COMP B 0.37L (1/8 de galón)",
        "proporcion_cunete": "COMP A 15.14L + catalizador 13227 COMP B 1.89L",
        "pot_life_horas": 6,
        "restriccion_exterior": (
            "Pintucoat es epóxico y ENTIZA (se decolora) en exteriores expuestos al sol. "
            "En exterior REQUIERE capa de acabado con poliuretano (Interthane). "
            "NUNCA ofrecer Pintulux 3en1 como acabado sobre Pintucoat: Pintulux es esmalte alquídico, "
            "no es poliuretano y no da la resistencia UV requerida."
        ),
        "acabado_exterior_obligatorio": "interthane",
        "resistencia": "media",
        "acabado": "mate",
        "uso_piso": True,
        "nota_resistencia": (
            "Pintucoat es de resistencia MEDIA. NO resiste tráfico pesado de montacargas/estibadores. "
            "Para tráfico pesado recomendar Intergard 2002 + cuarzo (ref 5891610). "
            "Alternativa brillante de resistencia media: Intergard 740."
        ),
    },
    # ─ Interthane (International / AkzoNobel) ─────────────────────────────
    # galón (3.7L, PHA120 o PHA130) → catalizador PHA046 0.5L
    # cuñete (20L) → catalizador PHA046 3.7L
    "interthane": {
        "tipo_sistema": "poliuretano_dos_componentes",
        "componente_a_descripcion": "Interthane 990 COMP A (color, ej. PHA120 o PHA130)",
        "componente_b_codigo": "PHA046",
        "componente_b_descripcion": "Interthane 990 PHA046 catalizador (hardener)",
        "proporcion_galon": "COMP A 3.7L + catalizador PHA046 0.5L",
        "proporcion_cunete": "COMP A 20L + catalizador PHA046 3.7L",
        "nota": "Verificar relación exacta en ficha técnica según número de lote y temperatura.",
    },
    # ─ Interseal (International / AkzoNobel) ──────────────────────────────
    "interseal": {
        "tipo_sistema": "epoxica_dos_componentes",
        "componente_a_descripcion": "Interseal COMP A",
        "componente_b_descripcion": "Interseal COMP B catalizador — consultar ficha técnica Internacional",
        "nota": "Relación de mezcla y código de catalizador deben extraerse de la ficha técnica International o la Guía de Sistemas.",
        "aplicacion_condicional_agua_potable": (
            "Interseal 670HS tiene certificación NSF/ANSI 61 para agua potable en tanques > 100 gal (378.5L). "
            "Condiciones obligatorias: (1) preparación Sa 2.5 / SSPC-SP10, (2) colores específicos certificados "
            "(verificar lote con distribuidor), (3) respetar tiempo de curado completo antes de servicio. "
            "Alternativa de mayor desempeño en inmersión permanente: línea Interline (100% sólidos, sin solventes)."
        ),
    },
    # ─ Intergard (International / AkzoNobel) ── GENÉRICO ────────────────────
    "intergard": {
        "tipo_sistema": "epoxica_dos_componentes",
        "componente_a_descripcion": "Intergard COMP A (primer epóxico)",
        "componente_b_descripcion": "Intergard COMP B catalizador — consultar ficha técnica International",
        "nota": "Relación de mezcla y código de catalizador deben extraerse de la ficha técnica International o la Guía de Sistemas.",
    },
    # ─ Intergard 740 (International / AkzoNobel) ── PISOS TRÁFICO MEDIO ACABADO BRILLANTE ──
    "intergard 740": {
        "tipo_sistema": "epoxica_dos_componentes",
        "componente_a_descripcion": "Intergard 740 COMP A (acabado brillante)",
        "componente_b_descripcion": "Intergard 740 COMP B catalizador — consultar ficha técnica International",
        "nota": "Epóxico para pisos de tráfico MEDIO con acabado BRILLANTE. Alternativa al Pintucoat cuando el cliente quiere más brillo.",
        "resistencia": "media",
        "acabado": "brillante",
        "uso_piso": True,
    },
    # ─ Intergard 2002 (International / AkzoNobel) ── SOBRE PEDIDO — ESCALAR A ASESOR ──
    "intergard 2002": {
        "tipo_sistema": "epoxica_dos_componentes",
        "componente_a_descripcion": "Intergard 2002 COMP A (alto volumen de sólidos)",
        "componente_b_descripcion": "Intergard 2002 COMP B catalizador — consultar ficha técnica International",
        "sobre_pedido": True,
        "nota": (
            "⚠️ PRODUCTO SOBRE PEDIDO — NO cotizar precio, NO buscar inventario. "
            "Intergard 2002 es un sistema especializado para pisos de tráfico PESADO (montacargas, estibadores) "
            "que requiere asesoría técnica personalizada. ESCALAR al Asesor Técnico Comercial. "
            "Sistema referencial: Interseal gris RAL 7038 (imprimante) → Intergard 2002 + cuarzo ref 5891610 → sello opcional."
        ),
        "resistencia": "alta (con cuarzo)",
        "acabado": "mate/satinado",
        "uso_piso": True,
        "cuarzo_ref": "5891610",
    },
    # ─ Interfine (International / AkzoNobel) ──────────────────────────────
    "interfine": {
        "tipo_sistema": "poliuretano_dos_componentes",
        "componente_a_descripcion": "Interfine 979 COMP A",
        "componente_b_descripcion": "Interfine COMP B catalizador — consultar ficha técnica International",
        "nota": "Relación de mezcla y código de catalizador deben extraerse de la ficha técnica International.",
    },
}

# Alias rápidos para buscar si un producto cae en BICOMPONENT_CATALOG
_BICOMPONENT_KEYWORDS: frozenset[str] = frozenset(BICOMPONENT_CATALOG.keys()) | frozenset([
    "pintucoat 516", "pintucoat 517", "pintucoat plus",
    "interthane 990", "interseal 670", "intergard 475",
    "dos componentes", "bicomponente", "comp a", "comp b",
    "pha046", "pha120", "pha130",
    "catalizador 13227",
    "1550", "1551", "poliuretano alto trafico", "pisos trafic alt",
    "vitrificar", "vitrificar piso",
])


def get_bicomponent_info(product_name_or_query: str) -> dict | None:
    """Return bicomponent catalog entry if the query matches a known 2-component product."""
    q = _normalize_for_match(product_name_or_query)
    for key, info in BICOMPONENT_CATALOG.items():
        if key in q:
            return {"producto_base": key, **info}
    return None


__all__ = ["BICOMPONENT_CATALOG", "_BICOMPONENT_KEYWORDS", "get_bicomponent_info"]
