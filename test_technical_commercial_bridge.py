import unittest

from backend import main as m


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


if __name__ == "__main__":
    unittest.main()