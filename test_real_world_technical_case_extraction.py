import sys
import unittest

sys.path.insert(0, "/Users/diegogarcia/Aplicaciones IA/Servicio-Al-Cliente-FERREINOX-SAS-BIC")

from backend.main import build_technical_search_query, extract_technical_advisory_case


class RealWorldTechnicalCaseExtractionTests(unittest.TestCase):
    def test_metal_roof_case_is_not_left_generic(self):
        message = "Tengo una teja de zinc caliente y oxidada en la bodega y quiero protegerla."

        technical_case = extract_technical_advisory_case(message, {})

        self.assertEqual(technical_case["category"], "metal")
        self.assertEqual(technical_case["substrate_type"], "metal")
        self.assertEqual(technical_case["metal_type"], "galvanizado")
        self.assertEqual(technical_case["current_state"], "con oxido o corrosion")

    def test_fachada_case_infers_architectural_surface_and_state(self):
        message = "Quiero pintar la fachada de mi casa que ya esta descascarada por el sol y la lluvia."

        technical_case = extract_technical_advisory_case(message, {})

        self.assertEqual(technical_case["category"], "fachada")
        self.assertEqual(technical_case["substrate_type"], "concreto o mamposteria")
        self.assertEqual(technical_case["current_state"], "con recubrimiento deteriorado")
        self.assertEqual(technical_case["exposure_environment"], "exterior")

    def test_floor_cases_infer_concrete_context_from_everyday_language(self):
        message = "Quiero pintar el piso del garaje de mi casa donde entra el carro todos los dias."

        technical_case = extract_technical_advisory_case(message, {})

        self.assertEqual(technical_case["category"], "piso")
        self.assertEqual(technical_case["substrate_type"], "concreto o mamposteria")
        self.assertEqual(technical_case["floor_material"], "cemento o concreto")
        self.assertEqual(technical_case["traffic_level"], "alto trafico")

    def test_humidity_case_detects_capillarity_signal_from_base_of_wall(self):
        message = "Tengo una pared interior con salitre en la base del muro y se esta descascarando."

        technical_case = extract_technical_advisory_case(message, {})

        self.assertEqual(technical_case["category"], "humedad")
        self.assertEqual(technical_case["source_context"], "posible capilaridad desde la base del muro")
        self.assertEqual(technical_case["probable_pressure"], "presion_negativa")
        self.assertIn("salitre", technical_case["search_query"] if "search_query" in technical_case else build_technical_search_query(technical_case, message))

    def test_negated_humidity_follow_up_keeps_active_fachada_case(self):
        message = "Esta pintada y la pintada esta en mal estado algunas partes con desprendimiento no tenemos humedad y esta en estuco no tiene fisuras son 80 mts"

        technical_case = extract_technical_advisory_case(
            message,
            {"technical_advisory_case": {"category": "fachada", "stage": "diagnosing"}},
        )

        self.assertEqual(technical_case["category"], "fachada")
        self.assertEqual(technical_case["substrate_type"], "concreto o mamposteria")
        self.assertEqual(technical_case["surface_state"], "pintada")

    def test_metal_tank_query_carries_water_contact_signal_into_search(self):
        message = "Necesito pintar un tanque metalico de agua que esta oxidado por dentro y por fuera."

        technical_case = extract_technical_advisory_case(message, {})
        search_query = build_technical_search_query(technical_case, message)

        self.assertEqual(technical_case["category"], "metal")
        self.assertEqual(technical_case["environment"], "inmersion o contacto con agua")
        self.assertIn("inmersion o contacto con agua", search_query)
        self.assertIn("con oxido o corrosion", search_query)


if __name__ == "__main__":
    unittest.main()