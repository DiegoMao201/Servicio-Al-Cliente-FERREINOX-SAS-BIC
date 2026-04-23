import sys
from types import SimpleNamespace
import unittest

sys.path.insert(0, "backend")

from agent_context import classify_intent, extract_diagnostic_data, is_diagnostic_incomplete
from agent_v3 import _enforce_verified_technical_guidance, _guardia_universal_producto


class AdvisoryEnforcementTests(unittest.TestCase):
    def test_first_turn_humidity_without_location_stays_blocked(self):
        user_message = "Buenas, detras del closet del primer piso la pared se esta soplando y sale polvillo blanco desde abajo."

        diagnostic = extract_diagnostic_data(user_message, [])
        intent = classify_intent(user_message, {}, [], {})

        self.assertEqual(intent, "asesoria")
        self.assertEqual(diagnostic["surface"], "interior húmedo")
        self.assertEqual(diagnostic["condition"], "pintura soplada")
        self.assertIsNone(diagnostic["interior_exterior"])
        self.assertTrue(is_diagnostic_incomplete(intent, diagnostic))

    def test_followup_diagnostic_turn_stays_advisory(self):
        recent_messages = [
            {
                "direction": "inbound",
                "contenido": "Buenas, detras del closet del primer piso la pared se esta soplando y sale polvillo blanco desde abajo.",
                "message_type": "text",
            }
        ]
        user_message = "Es interior, el dano arranca pegado al piso y ya saco salitre. No es lluvia por fachada. Son 24 metros cuadrados."

        diagnostic = extract_diagnostic_data(user_message, recent_messages)
        intent = classify_intent(user_message, {}, recent_messages, {})

        self.assertEqual(intent, "asesoria")
        self.assertEqual(diagnostic["surface"], "interior húmedo")
        self.assertEqual(diagnostic["condition"], "salitre")
        self.assertEqual(diagnostic["interior_exterior"], "interior")
        self.assertFalse(is_diagnostic_incomplete(intent, diagnostic))

    def test_universal_guard_accepts_chatcompletion_like_messages(self):
        assistant_message = SimpleNamespace(content="Recomiendo Aquablock Ultra como base.", tool_calls=None)
        messages = [
            {"role": "system", "content": "Usa solo productos respaldados por herramientas."},
            SimpleNamespace(role="user", content="Tengo una pared interior con salitre."),
        ]
        tool_calls_made = [
            {
                "name": "consultar_conocimiento_tecnico",
                "args": {"pregunta": "muro interior con salitre"},
                "result": '{"respuesta_rag":"Aquablock Ultra como base tecnica para humedad interior"}',
            }
        ]

        guarded = _guardia_universal_producto(
            assistant_message,
            messages,
            tool_calls_made,
            context={},
            conversation_context={},
            m=None,
        )

        self.assertIs(guarded, assistant_message)
        self.assertIn("Aquablock", guarded.content)

    def test_blocks_unverified_recommendation_without_rag_guidance(self):
        class _M:
            @staticmethod
            def normalize_text_value(text):
                return (text or "").lower()

        response = _enforce_verified_technical_guidance(
            "**Sistema Recomendado:** Usa Koraza y Sellomax con dos manos.",
            effective_advisory_flow=True,
            recommendation_ready=True,
            best_effort_ready=True,
            conversation_context={},
            technical_case={"category": "fachada"},
            m=_M(),
        )

        self.assertIn("no te voy a cerrar un sistema", response.lower())
        self.assertIn("sin respaldo técnico verificable del rag", response.lower())

    def test_keeps_recommendation_when_verified_guidance_exists(self):
        class _M:
            @staticmethod
            def normalize_text_value(text):
                return (text or "").lower()

        original = "**Sistema Recomendado:** Usa Koraza y Sellomax con dos manos."
        response = _enforce_verified_technical_guidance(
            original,
            effective_advisory_flow=True,
            recommendation_ready=True,
            best_effort_ready=True,
            conversation_context={"latest_technical_guidance": {"problem_class": "fachada_exterior"}},
            technical_case={"category": "fachada"},
            m=_M(),
        )

        self.assertEqual(original, response)


if __name__ == "__main__":
    unittest.main()