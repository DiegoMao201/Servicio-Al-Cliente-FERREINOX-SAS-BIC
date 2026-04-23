import sys
import unittest

sys.path.insert(0, "/Users/diegogarcia/Aplicaciones IA/Servicio-Al-Cliente-FERREINOX-SAS-BIC")

from backend.main import build_technical_search_query, extract_technical_advisory_case


class AggressiveWhatsAppRealWorldBatteryTests(unittest.TestCase):
    def test_aggressive_whatsapp_cases(self):
        cases = [
            {
                "message": "hola bro tengo una pared del baño q se pone negra arriba y suda cuando se bañan",
                "expect": {
                    "category": "humedad",
                    "source_context": "condensacion o vapor en baño/cocina",
                    "wall_location": "interior",
                },
            },
            {
                "message": "me dejaron una reja nueva sin nada en una casa en la costa, quiero algo bueno no barato",
                "expect": {
                    "category": "metal",
                    "substrate_type": "metal",
                    "environment": "marino",
                    "previous_coating": "sin recubrimiento previo",
                },
            },
            {
                "message": "el techo de zinc de la panaderia se pone feo por calor y oxido en unas partes",
                "expect": {
                    "category": "metal",
                    "metal_type": "galvanizado",
                    "current_state": "con oxido o corrosion",
                    "exposure_environment": "exterior",
                },
            },
            {
                "message": "una terraza encima del cuarto no se ve inundada siempre pero cuando llueve duro amanece el cielo raso marcado",
                "expect": {
                    "category": "humedad",
                    "source_context": "posible filtracion desde terraza o cubierta",
                    "probable_pressure": "presion_negativa",
                },
            },
            {
                "message": "voy a arreglar un locker metalico escolar por dentro, esta aporreado pero no oxidado mal",
                "expect": {
                    "category": "metal",
                    "substrate_type": "metal",
                    "exposure_environment": "interior",
                },
            },
            {
                "message": "que le mando a un cliente para un deck de cabaña pegado al lago, quiere ver veta no taparla",
                "expect": {
                    "category": "madera",
                    "substrate_type": "madera",
                    "exposure": "intemperie",
                    "exposure_environment": "exterior",
                },
                "query_must_include": ["sistema para madera", "intemperie"],
            },
            {
                "message": "tengo un piso de taller pequeño donde cae aceite, gasolina y le pasan motos todos los dias",
                "expect": {
                    "category": "piso",
                    "floor_material": "cemento o concreto",
                    "traffic_level": "alto trafico",
                    "current_state": "con contaminacion superficial",
                },
            },
            {
                "message": "una culata ya pintada esta como soplada y tostada del verano, es para repinte exterior",
                "expect": {
                    "category": "fachada",
                    "current_state": "con recubrimiento deteriorado",
                    "exposure_environment": "exterior",
                },
            },
            {
                "message": "puerta de madera del baño, ya pintada, se pela por vapor, la quieren otra vez blanca",
                "expect": {
                    "category": "madera",
                    "previous_coating": "con recubrimiento previo",
                    "exposure": "bajo techo",
                    "exposure_environment": "interior",
                },
            },
            {
                "message": "muro de cuarto util contra talud, pintura inflada y polvillo blanco abajo",
                "expect": {
                    "category": "humedad",
                    "source_context": "muro contra terreno o barranco",
                    "probable_pressure": "presion_negativa",
                },
            },
            {
                "message": "andan preguntando por un porton galvanizado q ya tuvo pintura pero ahora esta opaco en bodega",
                "expect": {
                    "category": "metal",
                    "metal_type": "galvanizado",
                    "previous_coating": "con recubrimiento previo",
                    "exposure_environment": "interior",
                },
            },
            {
                "message": "anden de local comercial a la intemperie, puro peaton y lluvia, concreto normal",
                "expect": {
                    "category": "piso",
                    "floor_location": "exterior",
                    "traffic_level": "trafico peatonal o residencial",
                    "exposure_environment": "exterior",
                },
            },
            {
                "message": "cocina de restaurante, pared con vapor y grasa, quieren algo que soporte limpieza seguida",
                "expect": {
                    "category": "humedad",
                    "source_context": "condensacion o vapor en baño/cocina",
                    "wall_location": "interior",
                    "exposure_environment": "interior",
                },
            },
            {
                "message": "cliente con fachada de panel cementicio nueva nueva, cero pintura, le da agua y sol todo el dia",
                "expect": {
                    "category": "fachada",
                    "current_state": "sin recubrimiento previo",
                    "exposure_environment": "exterior",
                },
            },
            {
                "message": "es una escalera metalica de finca, ya tenia base vieja, lluvia lateral y sol, algo rendidor",
                "expect": {
                    "category": "metal",
                    "metal_type": "metal ferroso",
                    "previous_coating": "con recubrimiento previo",
                    "exposure_environment": "exterior",
                },
            },
            {
                "message": "me sale humedad abajo en un muro del patio, por fuera pega jardin y por dentro blanquea",
                "expect": {
                    "category": "humedad",
                    "source_context": "posible filtracion desde fachada o exterior",
                    "wall_location": "interior",
                },
            },
            {
                "message": "parqueadero residencial ya pintado, llanta encima todo el tiempo, quiero repinte que dure",
                "expect": {
                    "category": "piso",
                    "previous_coating": "con recubrimiento previo",
                    "traffic_level": "alto trafico",
                },
                "query_must_include": ["sistema pintura para piso", "alto trafico"],
            },
            {
                "message": "nota de voz transcrita feo: barraanda metalica apto playa ya pintada pero cascariando",
                "expect": {
                    "category": "metal",
                    "environment": "marino",
                    "current_state": "con recubrimiento deteriorado",
                },
            },
            {
                "message": "un meson de cafeteria en madera con laca vieja, interior, no quieren perder tiempo lijando tanto",
                "expect": {
                    "category": "madera",
                    "previous_coating": "con recubrimiento previo",
                    "exposure": "bajo techo",
                },
            },
            {
                "message": "placa en azotea con microfisura, abajo no siempre gotea pero si marca cuando cae aguacero",
                "expect": {
                    "category": "humedad",
                    "source_context": "posible filtracion desde terraza o cubierta",
                    "probable_pressure": "presion_negativa",
                },
            },
            {
                "message": "quiero pintar una estructura metalica interior pero tambien me hablaron de humedad en una pared del local",
                "expect": {
                    "category": "metal",
                    "substrate_type": "metal",
                    "exposure_environment": "interior",
                },
                "query_must_include": ["sistema anticorrosivo"],
            },
            {
                "message": "me piden algo para un techo de eternit viejito, tizoso, sin meterle inventos raros",
                "expect": {
                    "category": "fachada",
                    "substrate_type": "fibrocemento",
                    "exposure_environment": "exterior",
                },
            },
            {
                "message": "pared de bodega en obra negra que suda porque da al terreno, aun sin pintura",
                "expect": {
                    "category": "humedad",
                    "surface_state": "obra negra",
                    "source_context": "muro contra terreno o barranco",
                },
            },
            {
                "message": "puerta metalica bajo techo en apto, esmalte viejo, nada de oxido por ahora",
                "expect": {
                    "category": "metal",
                    "previous_coating": "con recubrimiento previo",
                    "exposure_environment": "interior",
                },
            },
            {
                "message": "madera exterior en pergola de rooftop, solazo y agua, quieren algo elegante no pintura cubriente",
                "expect": {
                    "category": "madera",
                    "exposure": "intemperie",
                    "exposure_environment": "exterior",
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