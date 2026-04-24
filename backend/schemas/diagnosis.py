"""Schema estricto del diagnóstico consultivo (Fase D1).

Tres pilares OBLIGATORIOS para que un diagnóstico sea válido:
  1. Sustrato (qué material es la superficie)
  2. Estado actual (oxidado, descascarado, húmedo, intacto, etc.)
  3. Nivel de exposición (interior, exterior, sumergido, alta temperatura, ...)

Si falta cualquier pilar, ``is_complete`` retorna False y el agente debe
solicitar la información faltante en lugar de adivinar un sistema.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class DiagnosisPayload(BaseModel):
    """Diagnóstico estructurado con validación de los 3 pilares."""

    model_config = ConfigDict(extra="forbid")

    has_substrate: bool = False
    has_state: bool = False
    has_exposure: bool = False

    missing_info_requests: list[str] = Field(default_factory=list)
    technical_summary: Optional[str] = None

    detected_substrate: Optional[str] = None
    detected_state: Optional[str] = None
    detected_exposure: Optional[str] = None

    category: str = "general"

    @property
    def is_complete(self) -> bool:
        """True sólo si los 3 pilares están presentes."""
        return self.has_substrate and self.has_state and self.has_exposure

    def to_legacy_dict(
        self,
        *,
        question: str = "",
        product: str = "",
        best_similarity: float = 0.0,
    ) -> dict:
        """Serializa al contrato dict que esperan los consumidores legacy.

        Mantiene retro-compatibilidad con ``_build_hard_policies_for_context``,
        ``tool_handlers`` y los matrices de tests existentes, mientras
        expone los nuevos campos ``has_*``, ``missing_info_requests`` y
        ``_schema_version`` para los consumidores nuevos.
        """
        return {
            # Legacy contract (Phase C2)
            "category": self.category,
            "ready": self.is_complete,
            "system": "",
            "surface_type": self.detected_substrate or "",
            "condition": self.detected_state or "",
            "interior_exterior": self.detected_exposure or "",
            "area_m2": None,
            "humidity_source": None,
            "traffic": None,
            "required_validations": list(self.missing_info_requests),
            "best_similarity": float(best_similarity or 0.0),
            "question": question or "",
            "product": product or "",
            # Phase D1 strict fields
            "has_substrate": self.has_substrate,
            "has_state": self.has_state,
            "has_exposure": self.has_exposure,
            "technical_summary": self.technical_summary,
            "_schema_version": "D1",
        }


__all__ = ["DiagnosisPayload"]
