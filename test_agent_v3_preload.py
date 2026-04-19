from tests.internal.test_agent_v3_preload import *


if __name__ == "__main__":
    import unittest

    unittest.main()
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


if __name__ == "__main__":
    unittest.main()