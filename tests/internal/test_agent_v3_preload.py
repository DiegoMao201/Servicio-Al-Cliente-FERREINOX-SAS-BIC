import os
import sys
import unittest

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, os.path.join(ROOT_DIR, "backend"))
os.environ.setdefault("DATABASE_URL", "postgresql://postgres:x@localhost:5432/test")
os.environ.setdefault("OPENAI_API_KEY", "sk-test")

import agent_v3
import agent_context
import main


class AgentV3PreloadTests(unittest.TestCase):
    def test_metadata_prefilter_for_facade_maps_to_koraza(self):
        filters = main._infer_technical_metadata_prefilters(
            "Necesito pintar una fachada exterior muy castigada por lluvia y sol.",
            "",
            {"problem_class": "fachada_exterior", "confidence": "alta"},
        )

        self.assertIn("%koraza%", filters["canonical_family_patterns"])

    def test_metadata_prefilter_for_galvanized_roof_prioritizes_wash_primer(self):
        filters = main._infer_technical_metadata_prefilters(
            "Quiero pintar una teja de zinc galvanizada nueva.",
            "",
            {"problem_class": "metal_oxidado", "confidence": "alta"},
        )

        self.assertIn("%wash primer%", filters["canonical_family_patterns"])

    def test_commercial_batch_detected_by_intent_classifier(self):
        """Multi-product batch messages should still classify as direct order intent,
        even though the old helper no longer exists."""
        conversation_context = {}
        user_message = "8 galones 1501\n9 cuartos sd1\n2 galones tu11\n2 galones teu95"
        result = agent_context.classify_intent(
            user_message,
            conversation_context,
            [],
            {},
        )
        self.assertEqual(result, "pedido_directo")

    def test_preload_triggers_on_second_advisory_turn_with_complete_diagnostic(self):
        recent_messages = [
            {"direction": "inbound", "contenido": "Tengo una fachada de ladrillo a la vista y se puso negra por humo y agua."},
        ]
        diagnostic = {
            "surface": "fachada",
            "condition": "manchas/negreado",
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

    def test_preload_triggers_for_potable_water_immersion_case_when_diagnostic_is_complete(self):
        diagnostic = {
            "surface": "metal/inmersión",
            "condition": "contacto permanente con agua",
            "interior_exterior": "interior",
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

    def test_humidity_case_captures_bath_condensation_context_for_search(self):
        technical_case = main.extract_technical_advisory_case(
            "Las paredes del baño están negras de moho por el vapor de la ducha y están estucadas.",
            {},
        )

        self.assertEqual(technical_case.get("category"), "humedad")
        self.assertEqual(technical_case.get("source_context"), "condensacion o vapor en baño/cocina")
        self.assertEqual(technical_case.get("wall_location"), "interior")

        query = main.normalize_text_value(main.build_technical_search_query(technical_case))
        self.assertIn("condensacion", query)
        self.assertIn("bano", query)

    def test_detect_new_technical_topic_switch_clears_humidity_context_for_metal_case(self):
        conversation_context = {
            "commercial_draft": {
                "intent": "cotizacion",
                "items": [{"status": "matched", "descripcion_comercial": "Viniltex Banos y Cocinas"}],
                "technical_guidance": {
                    "source_question": "humedad en muro condensacion o vapor en bano interior estucada",
                    "diagnostico_estructurado": {"problem_class": "humedad_interior_general"},
                },
            },
            "latest_technical_guidance": {
                "source_question": "humedad en muro condensacion o vapor en bano interior estucada",
                "diagnostico_estructurado": {"problem_class": "humedad_interior_general"},
            },
        }

        topic_switch = agent_v3._detect_new_technical_topic_switch(
            "Y necesito saber cuál es la pintura recomendada para la teja metálica con recubrimiento de 25 micras.",
            conversation_context,
            main,
        )

        self.assertIsNotNone(topic_switch)
        self.assertEqual(topic_switch["active_category"], "humedad")
        self.assertEqual(topic_switch["new_category"], "metal")

    def test_detect_new_technical_topic_switch_does_not_reset_same_humidity_case(self):
        conversation_context = {
            "latest_technical_guidance": {
                "source_question": "humedad en muro condensacion o vapor en bano interior estucada",
                "diagnostico_estructurado": {"problem_class": "humedad_interior_general"},
            },
            "technical_advisory_case": {"category": "humedad"},
        }

        topic_switch = agent_v3._detect_new_technical_topic_switch(
            "Y la humedad es por la ducha y además necesito estucar porque el estuco está muy feo.",
            conversation_context,
            main,
        )

        self.assertIsNone(topic_switch)

    def test_consultive_block_message_for_galvanized_roof_forces_disambiguation(self):
        technical_case = {
            "category": "metal",
            "last_user_message": "Necesito pintar una teja de zinc galvanizada.",
            "conversation_history": ["La cubierta es metálica y está a la intemperie."],
        }

        message = agent_v3._build_consultive_block_message(technical_case, main)

        self.assertIn("¿La teja es nueva (galvanizada) o ya presenta oxidación?", message)

    def test_classifier_system_directive_blocks_architectural_water_based_metal_shortcut(self):
        technical_case = {
            "category": "metal",
            "last_user_message": "Voy a pintar una teja galvanizada y quiero saber qué sistema usar.",
        }

        directive = agent_v3._build_classifier_system_directives(technical_case, main)

        self.assertIsNotNone(directive)
        self.assertIn("PROHIBIDO recomendar sistemas base agua arquitectónicos sin anticorrosivo", directive)


if __name__ == "__main__":
    unittest.main()