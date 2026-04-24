"""Schema estricto de la guía técnica destilada (Fase D1).

Reglas inquebrantables:
  - ``approved_skus`` SÓLO acepta SKUs verificados desde una de dos fuentes:
    ``inventory`` (la fuente más fuerte: efectivamente comprable) o
    ``rag_chunk`` (extraído de un chunk RAG con metadata.sku poblada).
    Cualquier nombre comercial inventado por el LLM NUNCA debe entrar aquí.
  - Si el sistema químico es bicomponente (epóxico, poliuretano, polyurea)
    y el catalizador NO está presente en el inventario, la guía emite una
    alerta crítica y bloquea el flujo de pricing downstream
    (``pricing_ready=False``, ``pricing_gate="bicomponent_missing_catalyst"``).
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

# Roles permitidos para un SKU en la guía técnica.
SkuRole = Literal["base", "imprimante", "acabado", "solvente", "catalizador"]

# Origen verificable del SKU. NUNCA "llm" ni "guess".
SourceKind = Literal["inventory", "rag_chunk"]


class ApprovedSku(BaseModel):
    """Un SKU comercial verificado, con su rol en el sistema técnico.

    El campo ``source`` exige trazabilidad: el SKU debe poder reconstruirse
    desde una consulta a la BD de inventario o desde un chunk RAG concreto.
    Cualquier instancia con ``source`` fuera del ``Literal`` declarado es
    rechazada por Pydantic.
    """

    model_config = ConfigDict(extra="forbid")

    sku: str
    descripcion: str
    role: SkuRole
    chemical_family: Optional[str] = None
    source: SourceKind


class TechnicalAlert(BaseModel):
    """Alerta técnica emitida por la guía. Severidad ``critical`` bloquea pricing."""

    model_config = ConfigDict(extra="forbid")

    severity: Literal["info", "warning", "critical"]
    code: str
    message: str


class TechnicalGuidePayload(BaseModel):
    """Guía técnica destilada con verificación de bicomponentes."""

    model_config = ConfigDict(extra="forbid")

    surface_preparation_steps: list[str] = Field(default_factory=list)
    approved_skus: list[ApprovedSku] = Field(default_factory=list)
    bicomponent_required: bool = False
    bicomponent_verified: bool = False
    alerts: list[TechnicalAlert] = Field(default_factory=list)

    def to_legacy_dict(self, *, best_similarity: float = 0.0) -> dict:
        """Serializa preservando el contrato legacy + exponiendo campos D1."""
        base_or_primer = [
            {
                "producto": s.descripcion,
                "sku": s.sku,
                "chemical_family": s.chemical_family,
            }
            for s in self.approved_skus
            if s.role in ("base", "imprimante")
        ]
        finish_options = [
            {
                "producto": s.descripcion,
                "sku": s.sku,
                "chemical_family": s.chemical_family,
            }
            for s in self.approved_skus
            if s.role == "acabado"
        ]

        critical_msgs = [a.message for a in self.alerts if a.severity == "critical"]
        pricing_ready = (not self.bicomponent_required) or self.bicomponent_verified
        pricing_gate = (
            "bicomponent_missing_catalyst"
            if (self.bicomponent_required and not self.bicomponent_verified)
            else None
        )

        return {
            # Legacy contract (Phase C2)
            "preparation_steps": list(self.surface_preparation_steps),
            "base_or_primer": base_or_primer,
            "finish_options": finish_options,
            "commercial_alternatives": [],
            "restrictions": critical_msgs,
            "pricing_ready": pricing_ready,
            "pricing_gate": pricing_gate,
            "best_similarity": float(best_similarity or 0.0),
            # Phase D1 strict fields
            "approved_skus": [s.model_dump() for s in self.approved_skus],
            "bicomponent_required": self.bicomponent_required,
            "bicomponent_verified": self.bicomponent_verified,
            "alerts": [a.model_dump() for a in self.alerts],
            "_schema_version": "D1",
        }


__all__ = [
    "ApprovedSku",
    "SkuRole",
    "SourceKind",
    "TechnicalAlert",
    "TechnicalGuidePayload",
]
