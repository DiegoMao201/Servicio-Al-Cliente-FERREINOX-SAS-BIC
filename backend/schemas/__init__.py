"""Schemas Pydantic — Fase D1.

Contratos estrictos para los outputs del motor de diagnóstico estructurado
y la guía técnica destilada. Reglas inquebrantables:

  - Cero alucinación comercial: ningún SKU puede entrar al schema sin
    venir de una fuente verificada (inventory o rag_chunk).
  - Flujo consultivo estricto: el diagnóstico no puede marcarse como
    completo sin los 3 pilares (sustrato + estado + exposición).
  - Validación química: si el sistema es bicomponente y falta el
    catalizador en el inventario, el schema lo bloquea y emite alerta.
"""

from __future__ import annotations

from .diagnosis import DiagnosisPayload
from .technical_guide import (
    ApprovedSku,
    SkuRole,
    SourceKind,
    TechnicalAlert,
    TechnicalGuidePayload,
)

__all__ = [
    "DiagnosisPayload",
    "ApprovedSku",
    "SkuRole",
    "SourceKind",
    "TechnicalAlert",
    "TechnicalGuidePayload",
]
