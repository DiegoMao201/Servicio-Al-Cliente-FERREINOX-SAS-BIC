import unittest

from backend import main as m
from backend.agent_context import build_turn_context


class TechnicalCommercialBridgeTests(unittest.TestCase):
    def test_enforce_guidance_blocks_forbidden_products_in_draft(self):
        technical_guidance = {
            "required_products": ["Sellomax", "Koraza"],
            "forbidden_products": ["Pintuco Fill"],
        }
        resolved_items = [
            {
                "status": "matched",
                "original_text": "sellador para techo",
                "descripcion_comercial": "PQ PINTUCO FILL 7 GRIS 2753 20K",
                "matched_product": {
                    "descripcion": "PQ PINTUCO FILL 7 GRIS 2753 20K",
                    "referencia": "5892274",
                },
            },
            {
                "status": "matched",
                "original_text": "pintura final",
                "descripcion_comercial": "PQ KORAZA MAT BLANCO 2650 3.79L",
                "matched_product": {
                    "descripcion": "PQ KORAZA MAT BLANCO 2650 3.79L",
                    "referencia": "5890706",
                },
            },
        ]

        filtered_items, blocked_products, missing_required = m._enforce_technical_guidance_on_resolved_items(
            resolved_items,
            technical_guidance,
        )

        self.assertEqual(filtered_items[0]["status"], "missing")
        self.assertEqual(filtered_items[1]["status"], "matched")
        self.assertIn("Pintuco Fill", blocked_products)
        self.assertIn("Sellomax", missing_required)

    def test_snapshot_extracts_required_and_forbidden_products(self):
        payload = {
            "diagnostico_estructurado": {"problem_class": "eternit_fibrocemento"},
            "guia_tecnica_estructurada": {"finish_options": [{"producto": "Koraza"}]},
            "politicas_duras_contexto": {
                "required_products": ["Sellomax", "Koraza"],
                "forbidden_products": ["Pintuco Fill"],
            },
            "productos_sistema_prioritarios": ["Sellomax", "Koraza"],
        }

        snapshot = m._build_latest_technical_guidance_snapshot(
            payload,
            {"pregunta": "techo de eternit exterior", "producto": "Koraza"},
        )

        self.assertEqual(snapshot["source_question"], "techo de eternit exterior")
        self.assertEqual(snapshot["source_product"], "Koraza")
        self.assertEqual(snapshot["required_products"], ["Sellomax", "Koraza"])
        self.assertEqual(snapshot["forbidden_products"], ["Pintuco Fill"])

    def test_case_registry_preserves_previous_case_when_new_surface_starts(self):
        conversation_context = {}

        humidity_case = m.extract_technical_advisory_case(
            "Las paredes del baño están negras de moho por el vapor de la ducha y están estucadas.",
            {},
        )
        updates_1 = m.sync_technical_case_registry(conversation_context, humidity_case)
        conversation_context.update(updates_1)

        metal_case = m.extract_technical_advisory_case(
            "Necesito saber cuál es la pintura recomendada para la teja metálica con recubrimiento de 25 micras.",
            {},
        )
        updates_2 = m.sync_technical_case_registry(
            conversation_context,
            metal_case,
            force_new_case=True,
        )

        self.assertEqual(updates_2["active_technical_case_id"], "caso_2")
        self.assertEqual(len(updates_2["technical_cases"]), 2)
        self.assertEqual(updates_2["technical_cases"][0]["category"], "humedad")
        self.assertEqual(updates_2["technical_cases"][0]["status"], "pendiente")
        self.assertEqual(updates_2["technical_cases"][1]["category"], "metal")
        self.assertEqual(updates_2["technical_cases"][1]["status"], "activo")

    def test_turn_context_exposes_active_and_pending_cases_without_mixing(self):
        context_text = build_turn_context(
            {
                "technical_cases": [
                    {"case_id": "caso_1", "summary": "Baño con moho/condensación", "category": "humedad", "status": "pendiente"},
                    {"case_id": "caso_2", "summary": "Teja o lámina metálica", "category": "metal", "status": "activo"},
                ],
                "active_technical_case_id": "caso_2",
                "technical_advisory_case": {"category": "metal"},
            },
            [],
            "Necesito el sistema para la teja metálica.",
            {},
        )

        self.assertIn("MEMORIA DE CASOS TÉCNICOS", context_text)
        self.assertIn("Caso activo: caso_2", context_text)
        self.assertIn("caso_1: Baño con moho/condensación", context_text)
        self.assertIn("NO se deben mezclar", context_text)

    def test_resolve_referenced_technical_case_by_product_label(self):
        conversation_context = {
            "active_technical_case_id": "caso_2",
            "technical_cases": [
                {
                    "case_id": "caso_1",
                    "summary": "Baño con moho/condensación",
                    "category": "humedad",
                    "status": "pendiente",
                    "commercial_draft": {"labels": ["PQ VINILTEX BYC SA BLANCO 2001 3.79L"]},
                    "commercial_draft_snapshot": {
                        "intent": "cotizacion",
                        "items": [{"status": "matched", "descripcion_comercial": "PQ VINILTEX BYC SA BLANCO 2001 3.79L"}],
                    },
                    "technical_case_snapshot": {"case_id": "caso_1", "category": "humedad"},
                },
                {
                    "case_id": "caso_2",
                    "summary": "Teja o lámina metálica",
                    "category": "metal",
                    "status": "activo",
                },
            ],
        }

        resolved = m.resolve_referenced_technical_case(
            "aaa y entonces como aplico el PQ VINILTEX BYC SA BLANCO 2001 3.79L",
            conversation_context,
        )

        self.assertEqual(resolved["status"], "matched")
        self.assertEqual(resolved["case_id"], "caso_1")

    def test_activate_technical_case_restores_saved_snapshots(self):
        conversation_context = {
            "technical_cases": [
                {
                    "case_id": "caso_1",
                    "summary": "Baño con moho/condensación",
                    "category": "humedad",
                    "status": "pendiente",
                    "technical_case_snapshot": {"case_id": "caso_1", "category": "humedad", "surface_state": "estucada"},
                    "technical_guidance_snapshot": {"required_products": ["Viniltex Baños y Cocinas"]},
                    "commercial_draft_snapshot": {"intent": "cotizacion", "items": [{"status": "matched", "descripcion_comercial": "PQ VINILTEX BYC SA BLANCO 2001 3.79L"}]},
                },
                {
                    "case_id": "caso_2",
                    "summary": "Teja o lámina metálica",
                    "category": "metal",
                    "status": "activo",
                },
            ],
            "active_technical_case_id": "caso_2",
        }

        activated = m.activate_technical_case("caso_1", conversation_context)

        self.assertEqual(activated["active_technical_case_id"], "caso_1")
        self.assertEqual(activated["technical_advisory_case"]["surface_state"], "estucada")
        self.assertEqual(activated["latest_technical_guidance"]["required_products"], ["Viniltex Baños y Cocinas"])
        self.assertEqual(activated["commercial_draft"]["intent"], "cotizacion")

    def test_resolve_referenced_technical_case_marks_ambiguity_when_two_cases_match(self):
        conversation_context = {
            "active_technical_case_id": "caso_3",
            "technical_cases": [
                {"case_id": "caso_1", "summary": "Baño con moho/condensación", "category": "humedad", "status": "pendiente"},
                {"case_id": "caso_2", "summary": "Muro con salitre/capilaridad", "category": "humedad", "status": "pendiente"},
                {"case_id": "caso_3", "summary": "Teja o lámina metálica", "category": "metal", "status": "activo"},
            ],
        }

        resolved = m.resolve_referenced_technical_case(
            "aparte el caso de humedad necesito que le agregues unas cosas",
            conversation_context,
        )

        self.assertEqual(resolved["status"], "ambiguous")
        self.assertEqual(len(resolved["candidates"]), 2)


if __name__ == "__main__":
    unittest.main()