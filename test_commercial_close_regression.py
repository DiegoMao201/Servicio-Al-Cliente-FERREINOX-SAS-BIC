import sys
import unittest

sys.path.insert(0, "backend")

from agent_context import build_turn_context, classify_intent
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