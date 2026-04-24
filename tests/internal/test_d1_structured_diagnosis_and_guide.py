"""Tests TDD para los motores estructurados Fase D1.

Cubre las 3 reglas inquebrantables del prompt de la fase:

  1. Diagnóstico consultivo: si falta cualquiera de los 3 pilares
     (sustrato, estado, exposición), el output exige información en
     lugar de adivinar. NO se marca ``ready=True``.

  2. Validación bicomponente: si el RAG sugiere un sistema epóxico
     pero el inventario no incluye el catalizador,
     ``bicomponent_verified=False`` + alerta crítica + pricing bloqueado.

  3. Cero alucinación comercial: un SKU inventado pasado como ``product``
     argument NO entra a ``approved_skus`` salvo que provenga de una
     fuente verificada (inventory o rag_chunk con metadata.sku).
"""

from __future__ import annotations

import os
import sys
import unittest
from unittest import mock

# Asegurar que el backend está en sys.path para imports directos.
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if os.path.join(ROOT, "backend") not in sys.path:
    sys.path.insert(0, os.path.join(ROOT, "backend"))

from rag_helpers import _build_structured_diagnosis, _build_structured_technical_guide  # noqa: E402
from schemas.diagnosis import DiagnosisPayload  # noqa: E402
from schemas.technical_guide import TechnicalGuidePayload  # noqa: E402


class DiagnosisPillarValidationTests(unittest.TestCase):
    """Pilar #1 + #2 presentes pero el #3 (exposición) faltante.

    El diagnóstico debe NO marcarse ready y debe pedir explícitamente
    el nivel de exposición.
    """

    def test_missing_exposure_forces_request_for_more_info(self):
        # "concreto" (sustrato) + "humedad" (estado) — falta exposición
        question = "Tengo paredes de concreto con humedad y manchas de salitre."
        product = ""
        result = _build_structured_diagnosis(question, product, best_similarity=0.0)

        self.assertTrue(result["has_substrate"], "Debe detectar sustrato 'concreto'")
        self.assertTrue(result["has_state"], "Debe detectar estado 'humedo/salitre'")
        self.assertFalse(
            result["has_exposure"],
            "NO hay keyword de exposición (interior/exterior/sumergido/...)",
        )
        self.assertFalse(result["ready"], "Sin los 3 pilares no puede estar ready")

        joined = " ".join(result["required_validations"]).upper()
        self.assertIn(
            "EXPOSICI",
            joined,
            "El missing_info_requests debe mencionar EXPOSICIÓN",
        )

        # Reconstruir desde el dict para validar el contrato Pydantic
        payload = DiagnosisPayload(
            has_substrate=result["has_substrate"],
            has_state=result["has_state"],
            has_exposure=result["has_exposure"],
            missing_info_requests=result["required_validations"],
            detected_substrate=result["surface_type"] or None,
            detected_state=result["condition"] or None,
            detected_exposure=result["interior_exterior"] or None,
            category=result["category"],
        )
        self.assertFalse(payload.is_complete)


class BicomponentVerificationTests(unittest.TestCase):
    """RAG sugiere sistema epóxico pero el inventario omite el catalizador."""

    def test_epoxy_without_catalyst_marks_bicomponent_unverified(self):
        # Mock determinista de normalize_text_value para evitar tocar main
        rag_chunks = [
            {
                "metadata": {
                    "sku": "INTERSEAL-670HS-A",
                    "chemical_family": "epoxico",
                    "nombre_comercial": "Interseal 670HS Parte A",
                },
                "doc_filename": "Interseal 670HS",
                "familia_producto": "epoxico",
                "similarity": 0.85,
            }
        ]
        # Sólo Parte A en inventario — falta el catalizador (Parte B / hardener)
        inventory_candidates = [
            {
                "codigo": "INTERSEAL-670HS-A",
                "descripcion": "Interseal 670HS Parte A — base epóxica",
                "etiqueta_auditable": "Interseal 670HS Parte A",
                "marca": "International",
            }
        ]
        diagnosis = {
            "ready": True,
            "surface_type": "metal",
            "condition": "oxidado",
            "interior_exterior": "exterior",
        }

        result = _build_structured_technical_guide(
            question="Necesito proteger un tanque metálico oxidado a la intemperie",
            product="Interseal 670HS",
            diagnosis=diagnosis,
            expert_notes=[],
            best_similarity=0.85,
            rag_chunks=rag_chunks,
            inventory_candidates=inventory_candidates,
        )

        self.assertTrue(
            result["bicomponent_required"],
            "Debe detectar bicomponente desde 'epoxico' en metadata RAG + nombre del producto",
        )
        self.assertFalse(
            result["bicomponent_verified"],
            "No hay SKU con role='catalizador' en inventario → unverified",
        )
        self.assertFalse(
            result["pricing_ready"],
            "Bicomponente sin verificar debe bloquear pricing",
        )
        self.assertEqual(
            result["pricing_gate"],
            "bicomponent_missing_catalyst",
            "Pricing gate debe identificar la causa exacta",
        )

        alert_codes = [a.get("code") for a in result.get("alerts", [])]
        self.assertIn(
            "BICOMPONENT_MISSING_CATALYST",
            alert_codes,
            "Debe emitir alerta crítica con el code esperado",
        )

        # Reconstruir desde el dict para validar el contrato Pydantic estricto
        payload = TechnicalGuidePayload.model_validate(
            {
                "surface_preparation_steps": result["preparation_steps"],
                "approved_skus": result["approved_skus"],
                "bicomponent_required": result["bicomponent_required"],
                "bicomponent_verified": result["bicomponent_verified"],
                "alerts": result["alerts"],
            }
        )
        self.assertTrue(payload.bicomponent_required and not payload.bicomponent_verified)


class SkuWhitelistEnforcementTests(unittest.TestCase):
    """Un SKU inyectado manualmente como ``product`` arg debe ser rechazado."""

    def test_manually_injected_fake_sku_is_rejected_in_favor_of_strict_schema(self):
        rag_chunks: list[dict] = []
        # Único SKU "real": viene de inventario verificado.
        inventory_candidates = [
            {
                "codigo": "REAL-VINILTEX-G",
                "descripcion": "Viniltex Galón Blanco — vinílico látex",
                "etiqueta_auditable": "Viniltex G Blanco",
                "marca": "Pintuco",
            }
        ]
        diagnosis = {
            "ready": True,
            "surface_type": "concreto",
            "condition": "intacto",
            "interior_exterior": "interior",
        }

        # El usuario / LLM intenta inyectar un SKU inventado vía 'product' arg.
        result = _build_structured_technical_guide(
            question="Pinta paredes interiores nuevas con FAKE-INVENTED-SKU",
            product="FAKE-INVENTED-SKU",
            diagnosis=diagnosis,
            expert_notes=[
                {"producto_recomendado": "GHOST-SKU-FROM-EXPERT-NOTE"},
            ],
            best_similarity=0.4,
            rag_chunks=rag_chunks,
            inventory_candidates=inventory_candidates,
        )

        approved_skus = result["approved_skus"]
        sku_values = {item["sku"] for item in approved_skus}

        self.assertNotIn(
            "FAKE-INVENTED-SKU",
            sku_values,
            "Un SKU inyectado como argumento NUNCA debe entrar a approved_skus",
        )
        self.assertNotIn(
            "GHOST-SKU-FROM-EXPERT-NOTE",
            sku_values,
            "Productos en expert_notes NO son fuente verificada para approved_skus",
        )
        self.assertEqual(
            sku_values,
            {"REAL-VINILTEX-G"},
            "Sólo SKUs venidos de inventory/rag_chunk deben aparecer",
        )
        for item in approved_skus:
            self.assertIn(
                item["source"],
                ("inventory", "rag_chunk"),
                f"Source inválida: {item.get('source')}",
            )


if __name__ == "__main__":
    unittest.main()
