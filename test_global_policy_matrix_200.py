import unittest

from backend import main as m


def _build_policy_snapshot(question: str, product: str = "") -> dict:
    diagnosis = m._build_structured_diagnosis(question, product, best_similarity=0.9)
    guide = m._build_structured_technical_guide(question, product, diagnosis, expert_notes=[], best_similarity=0.9)
    policies = m._build_hard_policies_for_context(question, product, diagnosis, guide, expert_notes=[])
    return {
        "diagnosis": diagnosis,
        "guide": guide,
        "policies": policies,
    }


def _variants(anchor: str) -> list[str]:
    return [
        anchor,
        f"Necesito {anchor}",
        f"Que sistema recomiendas para {anchor}",
        f"Cliente consulta: {anchor}",
        f"Tengo {anchor}, que va?",
        f"Quiero cotizar {anchor}",
        f"Me sirve algo para {anchor}",
        f"Asesoria tecnica: {anchor}",
    ]


def _scenario_specs() -> list[dict]:
    return [
        {
            "name": "humedad_capilaridad",
            "anchor": "muro interior con salitre y humedad que sube desde la base del muro",
            "problem_class": "humedad_interior_capilaridad",
            "policy": "humedad_interior_negativa",
            "required": ["Aquablock"],
            "forbidden": ["Koraza"],
        },
        {
            "name": "humedad_general",
            "anchor": "pared interior con humedad, moho y filtracion lateral",
            "problem_class": "humedad_interior_general",
            "policy": "humedad_interior_negativa",
            "required": ["Aquablock"],
            "forbidden": ["Pintuco Fill"],
        },
        {
            "name": "fachada_exterior",
            "anchor": "fachada exterior expuesta a lluvia y sol con pintura soplada",
            "problem_class": "fachada_exterior",
            "policy": "fachada_alta_exposicion",
            "required": ["Koraza"],
            "forbidden": ["Intervinil"],
        },
        {
            "name": "eternit_exterior",
            "anchor": "techo de eternit exterior repintado y envejecido",
            "problem_class": "eternit_fibrocemento",
            "policy": "eternit_fibrocemento_exterior",
            "required": ["Sellomax", "Koraza"],
            "forbidden": ["Intervinil"],
        },
        {
            "name": "ladrillo_vista",
            "anchor": "ladrillo a la vista exterior sin cambiar apariencia",
            "problem_class": "ladrillo_vista",
            "policy": "ladrillo_a_la_vista",
            "required": ["Construcleaner Limpiador Desengrasante", "Siliconite 7"],
            "forbidden": ["Koraza"],
        },
        {
            "name": "metal_alquidico_viejo",
            "anchor": "reja con esmalte sintetico viejo y anticorrosivo alquidico",
            "problem_class": "metal_pintado_alquidico",
            "policy": "metal_pintado_alquidico",
            "forbidden": ["Interseal", "Interthane 990"],
            "mandatory": "metal desnudo",
        },
        {
            "name": "metal_oxidado",
            "anchor": "reja metalica con oxido superficial y corrosion",
            "problem_class": "metal_oxidado",
            "policy": "metal_oxidado_mantenimiento",
            "required": ["Pintóxido", "Corrotec"],
            "forbidden": ["Viniltex"],
        },
        {
            "name": "metal_galvanizado",
            "anchor": "lamina zinc galvanizada nueva para pintar",
            "policy": "metal_nuevo_galvanizado",
            "required": ["Wash Primer"],
            "forbidden": ["Pintucoat"],
        },
        {
            "name": "piso_pesado",
            "anchor": "piso industrial de concreto para montacargas y estibadores",
            "problem_class": "piso_industrial",
            "policy": "piso_industrial_trafico_pesado",
            "required": ["Intergard 2002", "Arena de Cuarzo ref 5891610"],
            "forbidden": ["Pintucoat"],
        },
        {
            "name": "piso_medio",
            "anchor": "garaje de concreto interior con trafico medio",
            "problem_class": "piso_industrial",
            "policy": "piso_industrial_trafico_medio",
            "required": ["Interseal gris RAL 7038", "Pintucoat"],
            "forbidden": ["Primer 50RS"],
        },
        {
            "name": "piso_exterior_uv",
            "anchor": "piso industrial exterior al sol con sistema epoxico",
            "problem_class": "piso_industrial",
            "policy": "piso_exterior_uv",
            "required": ["Interthane 990 + Catalizador"],
            "mandatory": "poliuretano UV",
        },
        {
            "name": "concreto_sin_curado",
            "anchor": "piso de concreto nuevo recien fundido sin curar",
            "problem_class": "piso_industrial",
            "policy": "concreto_sin_curado",
            "mandatory": "28 dias",
        },
        {
            "name": "madera_exterior",
            "anchor": "deck de madera exterior expuesto a sol y lluvia",
            "problem_class": "madera",
            "policy": "madera_exterior",
            "required": ["Barnex", "Wood Stain"],
            "forbidden": ["Poliuretano Alto Trafico 1550/1551"],
        },
        {
            "name": "madera_interior_vitrificado",
            "anchor": "escalera interior de madera para vitrificar con alto trafico",
            "problem_class": "madera",
            "policy": "madera_interior_alto_trafico",
            "required": ["Poliuretano Alto Trafico 1550/1551"],
            "forbidden": ["Barnex"],
        },
        {
            "name": "techo_concreto_grietas",
            "anchor": "techo de concreto con grietas y fisuras en terraza",
            "policy": "techo_concreto_grietas",
            "required": ["Pintuco Fill"],
            "forbidden": ["Koraza"],
        },
        {
            "name": "bano_antihongos",
            "anchor": "baño con hongos por condensacion en muro interior",
            "policy": "bano_cocina_antihongos",
            "required": ["Viniltex Baños y Cocinas"],
            "forbidden": ["Koraza"],
        },
        {
            "name": "cancha_deportiva",
            "anchor": "cancha deportiva exterior y sendero peatonal",
            "policy": "cancha_sendero_peatonal",
            "required": ["Pintura Canchas"],
            "forbidden": ["Pintucoat"],
        },
        {
            "name": "inmersion_agua_potable",
            "anchor": "tanque de agua potable con sistema para inmersion",
            "policy": "inmersion_agua_potable_condicional",
            "forbidden": ["Pintucoat"],
            "mandatory": "NSF",
        },
        {
            "name": "proteccion_incendio",
            "anchor": "estructura metalica con proteccion pasiva contra incendio e intumescente",
            "policy": "proteccion_pasiva_incendio",
            "required": ["Interchar"],
            "mandatory": "espesor requerido",
        },
        {
            "name": "alta_estetica_industrial",
            "anchor": "acabado industrial de alta estetica con alta retencion de color",
            "policy": "acabado_industrial_alta_estetica",
            "required": ["Interfine"],
            "forbidden": ["Corrotec"],
        },
        {
            "name": "ambiente_quimico",
            "anchor": "planta industrial con ambiente quimico severo y corrosion industrial",
            "policy": "ambiente_quimico_industrial",
            "required": ["Intergard", "Interseal", "Interthane 990 + Catalizador"],
            "forbidden": ["Koraza"],
        },
        {
            "name": "espuma_poliuretano",
            "anchor": "espuma de poliuretano para sellar huecos y aislamiento termico",
            "policy": "espuma_poliuretano_sellado",
            "required": ["Espuma de Poliuretano"],
            "forbidden": ["Pintuco Fill"],
        },
        {
            "name": "esmalte_decorativo",
            "anchor": "esmalte top quality brillante para metal decorativo de mantenimiento liviano",
            "policy": "esmalte_decorativo_mantenimiento",
            "required": ["Esmaltes Top Quality"],
            "forbidden": ["Interseal"],
        },
        {
            "name": "arquitectonico_base_agua",
            "anchor": "muro de casa con pintura base agua y vinilo existente",
            "policy": "arquitectonico_sobre_base_agua",
            "forbidden": ["Interthane 990", "Pintucoat"],
            "mandatory": "agua con agua",
        },
        {
            "name": "interior_koraza_redirect",
            "anchor": "koraza para muro interior de sala y pasillo cerrado",
            "policy": "interior_koraza_redirect",
            "required": ["Viniltex Advanced"],
            "forbidden": ["Koraza"],
        },
    ]


class GlobalPolicyMatrix200Tests(unittest.TestCase):
    def _assert_contains(self, values, expected):
        self.assertIn(expected, values, f"Expected '{expected}' in {values}")

    def _assert_fragment(self, values, fragment):
        self.assertTrue(
            any(fragment.lower() in str(value).lower() for value in values),
            f"Expected fragment '{fragment}' in {values}",
        )

    def test_global_policy_matrix_200_cases(self):
        cases_run = 0
        for spec in _scenario_specs():
            for question in _variants(spec["anchor"]):
                with self.subTest(case=spec["name"], question=question):
                    snapshot = _build_policy_snapshot(question)
                    diagnosis = snapshot["diagnosis"]
                    policies = snapshot["policies"]

                    if spec.get("problem_class"):
                        self.assertEqual(diagnosis["problem_class"], spec["problem_class"])
                    self._assert_contains(policies["policy_names"], spec["policy"])
                    for required in spec.get("required", []):
                        self._assert_contains(policies["required_products"], required)
                    for forbidden in spec.get("forbidden", []):
                        self._assert_contains(policies["forbidden_products"], forbidden)
                    if spec.get("mandatory"):
                        self._assert_fragment(policies["mandatory_steps"], spec["mandatory"])
                    cases_run += 1

        self.assertEqual(cases_run, 200)


if __name__ == "__main__":
    unittest.main()