import sys
import unittest
from unittest import mock

sys.path.insert(0, "backend")

from agent_context import build_turn_context, classify_intent
import main
from main import _draft_items_to_confirmation_payloads


def _build_ready_draft() -> dict:
    return {
        "intent": "cotizacion",
        "tipo_documento": "cotizacion",
        "items": [
            {
                "status": "matched",
                "original_text": "9 cuartos sd1",
                "descripcion_comercial": "Koraza transparente cuarto",
                "descripcion_exacta": "BARNIZ SD-1 INCOLORO CUARTO",
                "referencia": "SD1",
                "cantidad": 9,
                "unidad_medida": "cuarto",
                "audit_label": "[SD1] - BARNIZ SD-1 INCOLORO CUARTO",
                "matched_product": {
                    "referencia": "SD1",
                    "descripcion": "BARNIZ SD-1 INCOLORO CUARTO",
                },
                "product_request": {
                    "requested_quantity": 9,
                    "requested_unit": "cuarto",
                },
            }
        ],
    }


class CommercialCloseRegressionTests(unittest.TestCase):
    def test_multiline_short_codes_classify_as_direct_order(self):
        intent = classify_intent(
            "8 galones 1501\n9 cuartos sd1\n2 galones tu11\n2 galones teu95",
            {},
            [],
            {},
        )
        self.assertEqual(intent, "pedido_directo")

    def test_grouped_brocha_sizes_expand_into_independent_lines(self):
        lines = main.split_commercial_line_items(
            '12 brochas profesional goya de: 11/2", 21/2" 3"'
        )
        self.assertEqual(
            lines,
            [
                '12 brochas profesional goya de: 1 1/2"',
                '12 brochas profesional goya de: 2 1/2"',
                '12 brochas profesional goya de: 3"',
            ],
        )

    def test_discount_line_is_tracked_without_creating_fake_product(self):
        def fake_build_item(raw_line, _stores, _mode):
            return {
                "status": "matched",
                "original_text": raw_line,
                "matched_product": {"referencia": "F6514852", "descripcion": "BROCHA GOYA PROF. 2\"\"\""},
                "product_request": {"requested_quantity": 24, "requested_unit": "unidad", "brand_filters": ["goya"]},
                "audit_label": "[F6514852] - BROCHA GOYA PROF. 2\"\"\"",
                "descripcion_comercial": "BROCHA GOYA PROF. 2\"\"\"",
                "descripcion_exacta": "BROCHA GOYA PROF. 2\"\"\"",
                "referencia": "F6514852",
                "cantidad": 24,
                "unidad_medida": "unidad",
                "alternatives": [],
                "matches": [],
                "message": "ok",
            }

        with mock.patch.object(main, "build_commercial_item_result", side_effect=fake_build_item):
            result = main.build_commercial_flow_reply(
                "cotizacion",
                None,
                '24 brochas profesional goya de: 2"\nGoya descuento del 5',
                {},
            )

        draft = result["commercial_draft"]
        self.assertEqual(len(draft["items"]), 1)
        self.assertEqual(draft["items"][0]["original_text"], '24 brochas profesional goya de: 2"')
        self.assertEqual(draft["items"][0]["discount_pct"], 5)
        self.assertEqual(draft["discount_notes"][0]["brand"], "goya")
        self.assertEqual(draft["discount_notes"][0]["discount_pct"], 5)
        self.assertIn("descuento del 5% para Goya", result["response_text"])

    def test_confirmation_payload_uses_exact_inventory_description(self):
        payload = _draft_items_to_confirmation_payloads(_build_ready_draft())
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["referencia"], "SD1")
        self.assertEqual(payload[0]["descripcion_comercial"], "BARNIZ SD-1 INCOLORO CUARTO")
        self.assertEqual(payload[0]["etiqueta_auditable"], "[SD1] - BARNIZ SD-1 INCOLORO CUARTO")

    def test_ready_quote_treats_si_cotizame_as_confirmation(self):
        intent = classify_intent(
            "si cotizame",
            {"commercial_draft": _build_ready_draft()},
            [
                {
                    "direction": "outbound",
                    "contenido": "Subtotal: $100.000\nIVA 19%: $19.000\nTotal a Pagar: $119.000\n¿Deseas que te genere la cotización en PDF?",
                    "message_type": "text",
                }
            ],
            {},
        )
        self.assertEqual(intent, "confirmacion")

    def test_turn_context_shows_auditable_reference_and_description(self):
        context_text = build_turn_context(
            {"commercial_draft": _build_ready_draft()},
            [],
            "si en pdf la cotizacion",
            {},
        )
        self.assertIn("[SD1] - BARNIZ SD-1 INCOLORO CUARTO", context_text)


if __name__ == "__main__":
    unittest.main()