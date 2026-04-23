import sys
import unittest

sys.path.insert(0, "/Users/diegogarcia/Aplicaciones IA/Servicio-Al-Cliente-FERREINOX-SAS-BIC")

from backend.main import build_technical_search_query, extract_technical_advisory_case


class RealWorldSurfaceComboBatteryTests(unittest.TestCase):
    def test_real_world_surface_combinations(self):
        cases = [
            {
                "message": "Necesito sistema anticorrosivo para barandas metalicas de hotel frente al mar con mantenimiento premium.",
                "expect": {
                    "category": "metal",
                    "substrate_type": "metal",
                    "metal_type": "metal ferroso",
                    "environment": "marino",
                    "exposure_environment": "marino",
                },
            },
            {
                "message": "Necesito un recubrimiento para el piso de un taller de motos con derrame de gasolina y aceites livianos.",
                "expect": {
                    "category": "piso",
                    "floor_material": "cemento o concreto",
                    "traffic_level": "alto trafico",
                    "current_state": "con contaminacion superficial",
                },
            },
            {
                "message": "Quiero corregir un muro de sotano que da contra terreno y marca humedad permanente con acabado levantado.",
                "expect": {
                    "category": "humedad",
                    "source_context": "muro contra terreno o barranco",
                    "probable_pressure": "presion_negativa",
                    "wall_location": "interior",
                },
            },
            {
                "message": "Estoy revisando paneles lisos de fibrocemento en una fachada ventilada y necesito saber la ruta correcta de repinte.",
                "expect": {
                    "category": "fachada",
                    "substrate_type": "fibrocemento",
                    "exposure_environment": "exterior",
                },
                "query_must_include": ["fibrocemento", "sistema para fachada exterior"],
            },
            {
                "message": "Tengo una terraza transitable que cuando llueve moja el cuarto de abajo.",
                "expect": {
                    "category": "humedad",
                    "source_context": "posible filtracion desde terraza o cubierta",
                    "probable_pressure": "presion_negativa",
                },
                "query_must_include": ["terraza", "presion negativa"],
            },
            {
                "message": "Buenas, voy a pintar una estructura metalica interior de un local nuevo.",
                "expect": {
                    "category": "metal",
                    "substrate_type": "metal",
                    "previous_coating": "sin recubrimiento previo",
                    "exposure_environment": "interior",
                    "environment": "urbano",
                },
            },
        ]

        for case in cases:
            with self.subTest(message=case["message"]):
                technical_case = extract_technical_advisory_case(case["message"], {})
                search_query = build_technical_search_query(technical_case, case["message"])

                for key, expected_value in case["expect"].items():
                    self.assertEqual(technical_case.get(key), expected_value)

                for expected_snippet in case.get("query_must_include", []):
                    self.assertIn(expected_snippet, search_query)


if __name__ == "__main__":
    unittest.main()