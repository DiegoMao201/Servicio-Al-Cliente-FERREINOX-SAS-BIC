import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))
os.environ.setdefault("DATABASE_URL", "postgresql://postgres:x@localhost:5432/test")
os.environ.setdefault("OPENAI_API_KEY", "sk-test")

import agent_v3
import main


class AgentV3PreloadTests(unittest.TestCase):
    def test_commercial_batch_detected_by_routing_function(self):
        """_should_route_to_commercial_flow still detects multi-product batch messages,
        even though we no longer short-circuit on it (the LLM handles it via tools)."""
        conversation_context = {}
        user_message = "8 galones 1501\n9 cuartos sd1\n2 galones tu11\n2 galones teu95"
        result = agent_v3._should_route_to_commercial_flow(
            "pedido_directo", conversation_context, user_message, main,
        )
        self.assertTrue(result)

    def test_preload_triggers_on_second_advisory_turn_with_known_surface(self):
        recent_messages = [
            {"direction": "inbound", "contenido": "Tengo una fachada de ladrillo a la vista y se puso negra por humo y agua."},
        ]
        diagnostic = {
            "surface": "fachada",
            "condition": None,
            "interior_exterior": "exterior",
            "area_m2": None,
            "traffic": None,
            "humidity_source": None,
        }
        technical_case = {"category": "general", "ready": False}

        should_preload = agent_v3._should_preload_technical_guidance(
            "asesoria",
            diagnostic,
            "La idea NO es pintarla, sino limpiarla y dejarla protegida conservando el ladrillo natural.",
            recent_messages,
            {},
            technical_case,
            main,
        )

        self.assertTrue(should_preload)

    def test_preload_triggers_for_potable_water_immersion_case(self):
        diagnostic = {
            "surface": "metal/inmersión",
            "condition": None,
            "interior_exterior": None,
            "area_m2": None,
            "traffic": None,
            "humidity_source": None,
        }

        should_preload = agent_v3._should_preload_technical_guidance(
            "asesoria",
            diagnostic,
            "Necesito un sistema para pintar por dentro un tanque de agua potable metálico y va sumergido.",
            [],
            {},
            {"category": "metal", "ready": False},
            main,
        )

        self.assertTrue(should_preload)

    def test_preload_does_not_trigger_for_direct_order_intent(self):
        diagnostic = {
            "surface": "muro",
            "condition": None,
            "interior_exterior": "interior",
            "area_m2": None,
            "traffic": None,
            "humidity_source": None,
        }

        should_preload = agent_v3._should_preload_technical_guidance(
            "pedido_directo",
            diagnostic,
            "Necesito 2 galones de viniltex blanco 1501.",
            [],
            {},
            {"category": "general", "ready": False},
            main,
        )

        self.assertFalse(should_preload)

    def test_preemptive_lookup_uses_structured_search_query_when_available(self):
        recent_messages = [
            {"direction": "inbound", "contenido": "Tengo una pérgola de madera a la intemperie."},
        ]
        technical_case = main.extract_technical_advisory_case(
            "Quiero protegerla pero que se siga viendo la veta natural.",
            {},
        )

        args = agent_v3._build_preemptive_technical_lookup_args(
            "Quiero protegerla pero que se siga viendo la veta natural.",
            recent_messages,
            {},
            technical_case,
            main,
        )

        self.assertIn("sistema para madera", main.normalize_text_value(args.get("pregunta") or ""))


if __name__ == "__main__":
    unittest.main()