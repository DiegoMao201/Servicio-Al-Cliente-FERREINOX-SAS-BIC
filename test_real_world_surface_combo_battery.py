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
            {
                "message": "Buenas, se me esta pelando la pintura de una puerta de madera de baño por el vapor de la ducha.",
                "expect": {
                    "category": "madera",
                    "substrate_type": "madera",
                    "previous_coating": "con recubrimiento previo",
                    "exposure_environment": "interior",
                    "exposure": "bajo techo",
                },
            },
            {
                "message": "Tengo un deck de madera alrededor de la piscina que quedo reseco del sol y el agua.",
                "expect": {
                    "category": "madera",
                    "substrate_type": "madera",
                    "exposure_environment": "exterior",
                    "exposure": "intemperie",
                },
                "query_must_include": ["sistema para madera", "intemperie"],
            },
            {
                "message": "Quiero repintar un porton galvanizado de bodega que esta opaco pero casi no tiene oxido.",
                "expect": {
                    "category": "metal",
                    "substrate_type": "metal",
                    "metal_type": "galvanizado",
                    "previous_coating": "con recubrimiento previo",
                    "exposure_environment": "interior",
                },
            },
            {
                "message": "Necesito arreglar una pared del baño que se pone negra arriba del enchape por condensacion.",
                "expect": {
                    "category": "humedad",
                    "substrate_type": "concreto o mamposteria",
                    "source_context": "condensacion o vapor en baño/cocina",
                    "wall_location": "interior",
                },
            },
            {
                "message": "La culata de la casa ya esta pintada pero se soplo por varios lados con el sol y la lluvia.",
                "expect": {
                    "category": "fachada",
                    "substrate_type": "concreto o mamposteria",
                    "current_state": "con recubrimiento deteriorado",
                    "exposure_environment": "exterior",
                },
                "query_must_include": ["sistema para fachada exterior", "con recubrimiento deteriorado"],
            },
            {
                "message": "Me preguntan por una placa de concreto en azotea que filtra por microfisuras cuando cae un aguacero duro.",
                "expect": {
                    "category": "humedad",
                    "substrate_type": "concreto o mamposteria",
                    "source_context": "posible filtracion desde terraza o cubierta",
                    "probable_pressure": "presion_negativa",
                },
                "query_must_include": ["humedad en muro", "presion negativa"],
            },
            {
                "message": "Tengo un anden exterior de concreto en la entrada del local y quiero algo que aguante peatones y lluvia.",
                "expect": {
                    "category": "piso",
                    "substrate_type": "concreto o mamposteria",
                    "floor_location": "exterior",
                    "floor_material": "cemento o concreto",
                    "traffic_level": "trafico peatonal o residencial",
                    "exposure_environment": "exterior",
                },
            },
            {
                "message": "Voy a pintar una puerta metalica de apartamento bajo techo que ya tiene esmalte viejo pero no esta oxidada.",
                "expect": {
                    "category": "metal",
                    "substrate_type": "metal",
                    "metal_type": "metal ferroso",
                    "previous_coating": "con recubrimiento previo",
                    "exposure_environment": "interior",
                },
            },
            {
                "message": "El muro exterior del patio pega contra el jardin y por dentro me esta blanqueando la pintura en la parte baja.",
                "expect": {
                    "category": "humedad",
                    "substrate_type": "concreto o mamposteria",
                    "source_context": "posible filtracion desde fachada o exterior",
                    "wall_location": "interior",
                },
            },
            {
                "message": "Necesito algo para un meson de madera en cafeteria interior, ya tiene laca vieja y lo quieren volver a dejar bonito.",
                "expect": {
                    "category": "madera",
                    "substrate_type": "madera",
                    "previous_coating": "con recubrimiento previo",
                    "exposure": "bajo techo",
                },
            },
            {
                "message": "Una teja de zinc en taller caliente se esta oxidando por encima y recibe sol todo el dia.",
                "expect": {
                    "category": "metal",
                    "substrate_type": "metal",
                    "metal_type": "galvanizado",
                    "current_state": "con oxido o corrosion",
                    "exposure_environment": "exterior",
                },
                "query_must_include": ["sistema anticorrosivo", "galvanizado"],
            },
            {
                "message": "Tengo un cuarto util con muro en obra negra que huele humedo porque da al talud del conjunto.",
                "expect": {
                    "category": "humedad",
                    "substrate_type": "concreto o mamposteria",
                    "source_context": "muro contra terreno o barranco",
                    "surface_state": "obra negra",
                    "probable_pressure": "presion_negativa",
                },
            },
            {
                "message": "Quiero repintar un piso de parqueadero residencial que ya tiene pintura vieja y le caen llantas todos los dias.",
                "expect": {
                    "category": "piso",
                    "substrate_type": "concreto o mamposteria",
                    "floor_location": "exterior",
                    "traffic_level": "alto trafico",
                    "previous_coating": "con recubrimiento previo",
                },
                "query_must_include": ["sistema pintura para piso", "alto trafico"],
            },
            {
                "message": "Me escribieron por una fachada en panel cementicio nueva para local comercial, sin pintar todavia, full intemperie.",
                "expect": {
                    "category": "fachada",
                    "current_state": "sin recubrimiento previo",
                    "exposure_environment": "exterior",
                },
            },
            {
                "message": "Necesito proteger una escalera metalica exterior de finca que ya tiene base vieja y le cae lluvia lateral.",
                "expect": {
                    "category": "metal",
                    "substrate_type": "metal",
                    "metal_type": "metal ferroso",
                    "previous_coating": "con recubrimiento previo",
                    "exposure_environment": "exterior",
                },
            },
            {
                "message": "Hay una pared de cocina que se pone grasosa y con vapor, la quieren lavar seguido y volver a pintar.",
                "expect": {
                    "category": "humedad",
                    "substrate_type": "concreto o mamposteria",
                    "source_context": "condensacion o vapor en baño/cocina",
                    "wall_location": "interior",
                    "exposure_environment": "interior",
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