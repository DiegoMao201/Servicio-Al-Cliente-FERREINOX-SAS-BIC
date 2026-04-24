"""Tests de integración Fase D2 — Orquestación conversacional.

Estos tests validan el bucle TRIAGE → DIAGNOSIS_GATHERING →
TECHNICAL_RECOMMENDATION → ORDER_PREP del agente FERREAMIGO,
simulando al LLM como un router determinista sobre las herramientas
estructuradas de Fase D1.

El LLM real es no-determinista, por lo que no se invoca; en su lugar
se mockea con ``ScriptedLLMRouter`` que aplica EXACTAMENTE las reglas
del FERREAMIGO_SYSTEM_PROMPT (lee ``diagnostico_estructurado.ready``
para decidir si llama RAG o pregunta más).

Si el agente real (Gemini/Claude) violara la state machine, estos
tests no lo detectarían — lo que detectan es que las HERRAMIENTAS y
sus PAYLOADS proveen al LLM toda la información necesaria para
tomar la decisión correcta.
"""

from __future__ import annotations

import os
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if os.path.join(ROOT, "backend") not in sys.path:
    sys.path.insert(0, os.path.join(ROOT, "backend"))

from agent_prompt_ferreamigo import (  # noqa: E402
    FERREAMIGO_ALLOWED_TOOL_NAMES,
    FERREAMIGO_STATE_MARKERS,
    FERREAMIGO_SYSTEM_PROMPT,
)
from agent_profiles import get_agent_runtime_config  # noqa: E402
from rag_helpers import (  # noqa: E402
    _build_structured_diagnosis,
    _build_structured_technical_guide,
)


# ─────────────────────────────────────────────────────────────────────────
# Mock LLM router — aplica la state machine sin llamar a un modelo real.
# ─────────────────────────────────────────────────────────────────────────


class ScriptedLLMRouter:
    """Imita el comportamiento esperado del LLM siguiendo las reglas del
    ``FERREAMIGO_SYSTEM_PROMPT``.

    Estados emitidos: TRIAGE, DIAGNOSIS_GATHERING, TECHNICAL_RECOMMENDATION,
    ORDER_PREP. Cada llamada a ``step`` simula UN turno del LLM.
    """

    def __init__(self):
        self.tool_calls: list[dict] = []
        self.messages: list[dict] = []
        self.state: str = "TRIAGE"

    def step(
        self,
        user_message: str,
        *,
        rag_chunks=None,
        inventory_candidates=None,
    ) -> dict:
        # Paso 1: el agente SIEMPRE corre `_build_structured_diagnosis`
        # internamente (en producción lo hace tool_handlers; aquí lo hacemos
        # explícito para inspeccionar la decisión).
        diagnosis = _build_structured_diagnosis(user_message, "", best_similarity=0.0)

        # STATE 2 — DIAGNOSIS_GATHERING: faltan pilares → bloquear RAG.
        if not diagnosis["ready"]:
            self.state = "DIAGNOSIS_GATHERING"
            self.messages.append(
                {
                    "role": "assistant",
                    "content": (
                        "Para darte la solución correcta necesito 2 datos: "
                        + " | ".join(diagnosis["required_validations"][:2])
                    ),
                }
            )
            return {
                "state": self.state,
                "diagnosis": diagnosis,
                "tool_calls": list(self.tool_calls),
                "blocked_rag": True,
            }

        # STATE 3 — TECHNICAL_RECOMMENDATION: pilares completos → llamar RAG.
        self.state = "TECHNICAL_RECOMMENDATION"
        self.tool_calls.append(
            {
                "name": "consultar_conocimiento_tecnico",
                "arguments": {
                    "pregunta": user_message,
                    "producto": "",
                },
            }
        )
        guide = _build_structured_technical_guide(
            user_message,
            "",
            diagnosis,
            [],
            best_similarity=0.85,
            rag_chunks=rag_chunks or [],
            inventory_candidates=inventory_candidates or [],
        )

        # STATE 4 — ORDER_PREP: si la guía está lista para pricing.
        if guide.get("pricing_ready") and guide.get("approved_skus"):
            self.state = "ORDER_PREP"

        sku_names = [s["sku"] for s in guide.get("approved_skus", [])]
        prep = guide.get("preparation_steps", [])
        alerts = guide.get("alerts", [])
        self.messages.append(
            {
                "role": "assistant",
                "content": (
                    f"🩺 Diagnóstico: {diagnosis['surface_type']} / "
                    f"{diagnosis['condition']} / {diagnosis['interior_exterior']}\n"
                    f"🧱 Sistema: {', '.join(sku_names) if sku_names else '(pendiente)'}\n"
                    f"🔹 Preparación: {len(prep)} pasos\n"
                    f"⏰ Alertas: {len(alerts)}"
                ),
            }
        )
        return {
            "state": self.state,
            "diagnosis": diagnosis,
            "guide": guide,
            "tool_calls": list(self.tool_calls),
            "blocked_rag": False,
        }


# ─────────────────────────────────────────────────────────────────────────
# Sanity tests del prompt + runtime config
# ─────────────────────────────────────────────────────────────────────────


class FerreamigoPromptContractTests(unittest.TestCase):
    def test_prompt_contains_all_state_machine_markers(self):
        for marker in FERREAMIGO_STATE_MARKERS:
            self.assertIn(
                marker,
                FERREAMIGO_SYSTEM_PROMPT,
                f"El system prompt perdió el marcador de estado: {marker}",
            )

    def test_prompt_enforces_amnesia_and_routing(self):
        self.assertIn("AMNESIA TÉCNICA", FERREAMIGO_SYSTEM_PROMPT)
        self.assertIn("WHITELIST ESTRICTA DE SKUs", FERREAMIGO_SYSTEM_PROMPT)
        self.assertIn("ROUTING DETERMINISTA", FERREAMIGO_SYSTEM_PROMPT)
        self.assertIn("BICOMPONENT_MISSING_CATALYST", FERREAMIGO_SYSTEM_PROMPT)

    def test_runtime_config_exposes_ferreamigo_profile(self):
        os.environ["AGENT_PROFILE"] = "ferreamigo"
        try:
            cfg = get_agent_runtime_config()
        finally:
            os.environ.pop("AGENT_PROFILE", None)
        self.assertEqual(cfg["profile"], "ferreamigo")
        self.assertIs(cfg["system_prompt"], FERREAMIGO_SYSTEM_PROMPT)
        tool_names = {t["function"]["name"] for t in cfg["tools"]}
        # Debe tener el subset esperado y NO tener tools internas (BI, traslados…).
        self.assertTrue(FERREAMIGO_ALLOWED_TOOL_NAMES.issubset(tool_names))
        forbidden = {
            "consultar_bi_universal",
            "consultar_ventas_internas",
            "solicitar_traslado_interno",
            "confirmar_pedido_y_generar_pdf",
        }
        self.assertEqual(forbidden & tool_names, set())


# ─────────────────────────────────────────────────────────────────────────
# Tests de integración — bucle conversacional
# ─────────────────────────────────────────────────────────────────────────


class ConsultativePersistenceTest(unittest.TestCase):
    """STATE 2: el LLM NO puede invocar RAG si faltan pilares."""

    def test_user_says_only_pintar_un_tanque_blocks_rag(self):
        router = ScriptedLLMRouter()
        # Sólo nombra el sustrato implícito ("tanque") — sin estado ni exposición.
        result = router.step("Necesito pintar un tanque")

        self.assertEqual(
            router.state,
            "DIAGNOSIS_GATHERING",
            "Sin los 3 pilares el agente debe quedarse en DIAGNOSIS_GATHERING",
        )
        self.assertTrue(result["blocked_rag"], "RAG debe estar bloqueado en STATE 2")
        self.assertEqual(
            len(result["tool_calls"]),
            0,
            "Ninguna tool puede haberse llamado todavía (la state machine bloquea)",
        )

        diag = result["diagnosis"]
        self.assertFalse(diag["ready"])
        # El diagnóstico debe haber capturado al menos UN pilar pendiente
        # explícitamente listado para que el LLM sepa qué preguntar.
        self.assertGreaterEqual(len(diag["required_validations"]), 1)

        # La respuesta del agente debe ser una pregunta consultiva, no una
        # recomendación. Heurística: no debe contener nombres de productos
        # de Ferreinox ni precios.
        last_msg = router.messages[-1]["content"].lower()
        self.assertIn("necesito", last_msg)
        for forbidden in ("interseal", "viniltex", "koraza", "$", "precio", "cotización formal"):
            self.assertNotIn(
                forbidden,
                last_msg,
                f"STATE 2 no debe mencionar '{forbidden}'; debe limitarse a preguntar.",
            )


class FullPassWithBicomponentVerificationTest(unittest.TestCase):
    """STATE 3 + STATE 4: contexto completo → RAG → guía bicomponente verificada."""

    def test_full_context_routes_to_recommendation_with_verified_bicomponent(self):
        router = ScriptedLLMRouter()
        rag_chunks = [
            {
                "metadata": {
                    "sku": "INTERSEAL-670HS-A",
                    "chemical_family": "epoxico",
                    "nombre_comercial": "Interseal 670HS Parte A",
                },
                "doc_filename": "Interseal 670HS",
                "similarity": 0.88,
            },
            {
                "metadata": {
                    "sku": "INTERSEAL-670HS-B",
                    "chemical_family": "epoxico",
                    "nombre_comercial": "Interseal 670HS Componente B (catalizador)",
                },
                "doc_filename": "Interseal 670HS catalizador",
                "similarity": 0.86,
            },
        ]
        # Inventario completo: A + B (catalizador) → bicomponente verificable.
        inventory_candidates = [
            {
                "codigo": "INTERSEAL-670HS-A",
                "descripcion": "Interseal 670HS Parte A epóxico",
            },
            {
                "codigo": "INTERSEAL-670HS-B",
                "descripcion": "Interseal 670HS Componente B catalizador endurecedor",
            },
        ]

        result = router.step(
            "Tanque de acero oxidado, va sumergido en agua",
            rag_chunks=rag_chunks,
            inventory_candidates=inventory_candidates,
        )

        # Diagnóstico debe estar completo (3 pilares).
        diag = result["diagnosis"]
        self.assertTrue(diag["has_substrate"], "Detecta sustrato 'metal' (acero)")
        self.assertTrue(diag["has_state"], "Detecta estado 'oxidado'")
        self.assertTrue(diag["has_exposure"], "Detecta exposición 'sumergido'")
        self.assertTrue(diag["ready"], "Diagnóstico completo")

        # El router debe haber invocado el RAG.
        self.assertEqual(
            [tc["name"] for tc in result["tool_calls"]],
            ["consultar_conocimiento_tecnico"],
            "Con los 3 pilares completos, el agente DEBE llamar a RAG",
        )

        guide = result["guide"]
        self.assertTrue(guide["bicomponent_required"], "Sistema epóxico → bicomponente")
        self.assertTrue(
            guide["bicomponent_verified"],
            "Catalizador presente en inventario → debe quedar verificado",
        )
        self.assertEqual(
            guide["alerts"],
            [],
            "Sin alertas críticas porque el catalizador SÍ está en inventario",
        )
        self.assertTrue(guide["pricing_ready"])

        sku_set = {s["sku"] for s in guide["approved_skus"]}
        self.assertIn("INTERSEAL-670HS-A", sku_set)
        self.assertIn("INTERSEAL-670HS-B", sku_set)

        # Estado final esperado.
        self.assertEqual(router.state, "ORDER_PREP")

        # La respuesta del agente debe contener los SKUs reales del payload.
        last_msg = router.messages[-1]["content"]
        self.assertIn("INTERSEAL-670HS-A", last_msg)
        self.assertIn("INTERSEAL-670HS-B", last_msg)


if __name__ == "__main__":
    unittest.main()
