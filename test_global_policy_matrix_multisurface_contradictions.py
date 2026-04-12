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


def _multi_surface_variants(anchor: str) -> list[str]:
    return [
        anchor,
        f"Cliente con varias superficies en el mismo proyecto: {anchor}",
        f"Necesito resolver esto en una sola asesoria: {anchor}",
        f"Caso mixto para cotizar: {anchor}",
        f"Tengo dos frentes tecnicos y quiero criterio correcto: {anchor}",
        f"Antes de cotizar revisa esta consulta larga: {anchor}",
        f"Asesoria tecnica para proyecto combinado: {anchor}",
        f"Consulta completa del cliente: {anchor}",
    ]


def _contradiction_variants(anchor: str) -> list[str]:
    return [
        anchor,
        f"Aunque el cliente insiste, quiere esto asi: {anchor}",
        f"El cliente lo pide textual aunque sospecho conflicto: {anchor}",
        f"Necesito que detectes la contradiccion tecnica en este pedido: {anchor}",
        f"Caso deliberadamente conflictivo: {anchor}",
        f"Quieren cotizar esto aunque parece incompatible: {anchor}",
        f"Asesoria tecnica con producto pedido por el cliente: {anchor}",
        f"Consulta larga con contradiccion incluida: {anchor}",
    ]


def _multi_surface_specs() -> list[dict]:
    return [
        {
            "name": "fachada_y_bano",
            "anchor": "fachada exterior con pintura soplada y ademas baño interior con hongos por condensacion",
            "policies": ["fachada_alta_exposicion", "bano_cocina_antihongos"],
            "required": ["Koraza", "Viniltex Baños y Cocinas"],
        },
        {
            "name": "ladrillo_y_bano",
            "anchor": "ladrillo a la vista exterior sin cambiar apariencia y además baño interior con hongos",
            "policies": ["ladrillo_a_la_vista", "bano_cocina_antihongos"],
            "required": ["Construcleaner", "Siliconite", "Viniltex Baños y Cocinas"],
        },
        {
            "name": "eternit_y_grietas",
            "anchor": "techo de eternit exterior envejecido y tambien techo de concreto con grietas en terraza",
            "policies": ["eternit_fibrocemento_exterior", "techo_concreto_grietas"],
            "required": ["Sellomax", "Koraza", "Pintuco Fill"],
        },
        {
            "name": "tanque_e_incendio",
            "anchor": "tanque de agua potable con zona sumergida y estructura con proteccion pasiva contra incendio e intumescente",
            "policies": ["inmersion_agua_potable_condicional", "proteccion_pasiva_incendio"],
            "required": ["Interchar"],
            "mandatory": ["NSF", "espesor requerido"],
        },
        {
            "name": "techo_y_galvanizado",
            "anchor": "techo de concreto con grietas en terraza y tambien lamina galvanizada nueva para pintar",
            "policies": ["techo_concreto_grietas", "metal_nuevo_galvanizado"],
            "required": ["Pintuco Fill", "Wash Primer"],
        },
        {
            "name": "madera_exterior_e_interior",
            "anchor": "deck exterior de madera expuesto al sol y lluvia y ademas escalera interior de madera para vitrificar",
            "policies": ["madera_exterior", "madera_interior_alto_trafico"],
            "required": ["Barnex", "Wood Stain", "Poliuretano Alto Trafico 1550/1551"],
        },
        {
            "name": "sendero_y_galvanizado",
            "anchor": "sendero peatonal exterior y porton galvanizado nuevo para pintar en el mismo proyecto",
            "policies": ["cancha_sendero_peatonal", "metal_nuevo_galvanizado"],
            "required": ["Pintura Canchas", "Wash Primer"],
        },
        {
            "name": "espuma_y_bano",
            "anchor": "espuma de poliuretano para sellar huecos en un punto y además baño interior con hongos",
            "policies": ["espuma_poliuretano_sellado", "bano_cocina_antihongos"],
            "required": ["Espuma de Poliuretano", "Viniltex Baños y Cocinas"],
        },
        {
            "name": "agua_potable_y_galvanizado",
            "anchor": "tanque de agua potable y lamina zinc galvanizada nueva para pintar en otra zona",
            "policies": ["inmersion_agua_potable_condicional", "metal_nuevo_galvanizado"],
            "required": ["Wash Primer"],
            "mandatory": ["NSF"],
        },
        {
            "name": "incendio_y_alta_estetica",
            "anchor": "estructura con proteccion contra incendio intumescente y acabado industrial de alta estetica con retencion de color",
            "policies": ["proteccion_pasiva_incendio", "acabado_industrial_alta_estetica"],
            "required": ["Interchar", "Interfine"],
        },
        {
            "name": "ambiente_quimico_e_incendio",
            "anchor": "planta industrial con ambiente quimico severo y ademas proteccion pasiva contra incendio en estructura metalica",
            "policies": ["ambiente_quimico_industrial", "proteccion_pasiva_incendio"],
            "required": ["Intergard", "Interseal", "Interthane 990 + Catalizador", "Interchar"],
        },
        {
            "name": "eternit_y_ladrillo",
            "anchor": "cubierta de eternit exterior envejecida y muro de ladrillo a la vista que se quiere conservar",
            "policies": ["eternit_fibrocemento_exterior", "ladrillo_a_la_vista"],
            "required": ["Sellomax", "Construcleaner", "Siliconite"],
        },
        {
            "name": "cancha_y_bano",
            "anchor": "cancha deportiva exterior y ademas baño interior con hongos en el mismo complejo",
            "policies": ["cancha_sendero_peatonal", "bano_cocina_antihongos"],
            "required": ["Pintura Canchas", "Viniltex Baños y Cocinas"],
        },
        {
            "name": "espuma_y_terraza",
            "anchor": "espuma expansiva para sellar paso de tuberia y tambien techo de concreto con grietas en terraza",
            "policies": ["espuma_poliuretano_sellado", "techo_concreto_grietas"],
            "required": ["Espuma de Poliuretano", "Pintuco Fill"],
        },
        {
            "name": "bano_y_koraza_interior",
            "anchor": "baño interior con hongos y adicionalmente muro interior de sala donde el cliente menciona Koraza",
            "policies": ["bano_cocina_antihongos", "interior_koraza_redirect"],
            "required": ["Viniltex Baños y Cocinas", "Viniltex Advanced"],
            "forbidden": ["Koraza"],
        },
        {
            "name": "agua_potable_y_espuma",
            "anchor": "tanque de agua potable y sellado de pasos con espuma de poliuretano en otra zona del proyecto",
            "policies": ["inmersion_agua_potable_condicional", "espuma_poliuretano_sellado"],
            "required": ["Espuma de Poliuretano"],
            "mandatory": ["NSF"],
        },
    ]


def _contradiction_specs() -> list[dict]:
    return [
        {
            "name": "koraza_en_bano_interior",
            "anchor": "quiero Koraza para baño interior con hongos y condensacion",
            "policies": ["bano_cocina_antihongos", "interior_koraza_redirect"],
            "required": ["Viniltex Baños y Cocinas", "Viniltex Advanced"],
            "forbidden": ["Koraza"],
        },
        {
            "name": "koraza_en_humedad_interior",
            "anchor": "quiero Koraza para muro interior con humedad, moho y salitre",
            "policies": ["humedad_interior_negativa", "interior_koraza_redirect"],
            "required": ["Aquablock", "Viniltex Advanced"],
            "forbidden": ["Koraza", "Pintuco Fill"],
        },
        {
            "name": "pintucoat_en_cancha",
            "anchor": "quiero Pintucoat para cancha deportiva exterior",
            "policies": ["cancha_sendero_peatonal"],
            "required": ["Pintura Canchas"],
            "forbidden": ["Pintucoat"],
        },
        {
            "name": "pintucoat_en_galvanizado",
            "anchor": "quiero Pintucoat para lamina galvanizada nueva",
            "policies": ["metal_nuevo_galvanizado"],
            "required": ["Wash Primer"],
            "forbidden": ["Pintucoat"],
        },
        {
            "name": "viniltex_en_reja_oxidada",
            "anchor": "quiero Viniltex para reja oxidada con corrosion superficial",
            "policies": ["metal_oxidado_mantenimiento"],
            "required": ["Pintoxido", "Corrotec"],
            "forbidden": ["Viniltex"],
        },
        {
            "name": "barnex_en_escalera_interior",
            "anchor": "quiero Barnex para escalera interior de madera con alto trafico",
            "policies": ["madera_interior_alto_trafico"],
            "required": ["Poliuretano Alto Trafico 1550/1551"],
            "forbidden": ["Barnex"],
        },
        {
            "name": "poliuretano_1550_en_deck",
            "anchor": "quiero poliuretano 1550 para deck exterior de madera",
            "policies": ["madera_exterior"],
            "required": ["Barnex", "Wood Stain"],
            "forbidden": ["Poliuretano Alto Trafico 1550/1551"],
        },
        {
            "name": "koraza_en_terraza_grietas",
            "anchor": "quiero Koraza para techo de concreto con grietas en terraza",
            "policies": ["techo_concreto_grietas"],
            "required": ["Pintuco Fill"],
            "forbidden": ["Koraza"],
        },
        {
            "name": "intervinil_en_eternit",
            "anchor": "quiero Intervinil para techo de eternit exterior envejecido",
            "policies": ["eternit_fibrocemento_exterior"],
            "required": ["Sellomax", "Koraza"],
            "forbidden": ["Intervinil"],
        },
        {
            "name": "acido_en_ladrillo_vista",
            "anchor": "quiero acido muriatico para limpiar ladrillo a la vista exterior",
            "policies": ["ladrillo_a_la_vista"],
            "required": ["Construcleaner", "Siliconite"],
            "forbidden": ["acido muriatico"],
        },
        {
            "name": "pintucoat_en_agua_potable",
            "anchor": "quiero Pintucoat para tanque de agua potable en inmersion",
            "policies": ["inmersion_agua_potable_condicional"],
            "forbidden": ["Pintucoat"],
            "mandatory": ["NSF"],
        },
        {
            "name": "koraza_en_agua_potable",
            "anchor": "quiero Koraza para tanque de agua potable sumergido",
            "policies": ["inmersion_agua_potable_condicional"],
            "forbidden": ["Koraza"],
            "mandatory": ["NSF"],
        },
        {
            "name": "pintulux_en_incendio",
            "anchor": "quiero Pintulux 3 en 1 para proteccion pasiva contra incendio",
            "policies": ["proteccion_pasiva_incendio"],
            "required": ["Interchar"],
            "forbidden": ["Pintulux 3 en 1"],
        },
        {
            "name": "corrotec_en_alta_estetica",
            "anchor": "quiero Corrotec para acabado industrial de alta estetica y retencion de color",
            "policies": ["acabado_industrial_alta_estetica"],
            "required": ["Interfine"],
            "forbidden": ["Corrotec"],
        },
        {
            "name": "koraza_en_ambiente_quimico",
            "anchor": "quiero Koraza para planta industrial con ambiente quimico severo",
            "policies": ["ambiente_quimico_industrial"],
            "required": ["Intergard", "Interseal", "Interthane 990 + Catalizador"],
            "forbidden": ["Koraza"],
        },
        {
            "name": "interseal_en_bano",
            "anchor": "quiero Interseal para baño interior con hongos",
            "policies": ["bano_cocina_antihongos"],
            "required": ["Viniltex Baños y Cocinas"],
            "forbidden": ["Interseal"],
        },
        {
            "name": "interthane_en_base_agua",
            "anchor": "quiero Interthane 990 para muro de casa con pintura base agua existente",
            "policies": ["arquitectonico_sobre_base_agua"],
            "forbidden": ["Interthane 990", "Pintucoat"],
            "mandatory": ["agua con agua"],
        },
        {
            "name": "primer50_en_piso_medio",
            "anchor": "quiero Primer 50RS para garaje de concreto interior con trafico medio",
            "policies": ["piso_industrial_trafico_medio"],
            "required": ["Interseal gris RAL 7038", "Pintucoat"],
            "forbidden": ["Primer 50RS"],
        },
        {
            "name": "pintucoat_en_piso_pesado",
            "anchor": "quiero Pintucoat para piso industrial de montacargas y estibadores",
            "policies": ["piso_industrial_trafico_pesado"],
            "required": ["Intergard 2002", "Arena de Cuarzo"],
            "forbidden": ["Pintucoat"],
        },
        {
            "name": "viniltex_en_terraza_grietas",
            "anchor": "quiero Viniltex para techo de concreto con grietas en terraza",
            "policies": ["techo_concreto_grietas"],
            "required": ["Pintuco Fill"],
            "forbidden": ["Viniltex"],
        },
        {
            "name": "koraza_en_ladrillo_vista",
            "anchor": "quiero Koraza para ladrillo a la vista exterior sin cambiar apariencia",
            "policies": ["ladrillo_a_la_vista"],
            "required": ["Construcleaner", "Siliconite"],
            "forbidden": ["Koraza"],
        },
        {
            "name": "pintucoat_en_bano",
            "anchor": "quiero Pintucoat para baño interior con hongos",
            "policies": ["bano_cocina_antihongos"],
            "required": ["Viniltex Baños y Cocinas"],
            "forbidden": ["Pintucoat"],
        },
        {
            "name": "viniltex_en_incendio",
            "anchor": "quiero Viniltex para estructura con proteccion pasiva contra incendio",
            "policies": ["proteccion_pasiva_incendio"],
            "required": ["Interchar"],
            "forbidden": ["Viniltex"],
        },
        {
            "name": "pintuco_fill_en_espuma",
            "anchor": "quiero Pintuco Fill para sellar huecos con espuma expansiva",
            "policies": ["espuma_poliuretano_sellado"],
            "required": ["Espuma de Poliuretano"],
            "forbidden": ["Pintuco Fill"],
        },
    ]


class GlobalPolicyMatrixMultiSurfaceContradictionsTests(unittest.TestCase):
    def _contains_fragment(self, values: list[str], fragment: str) -> bool:
        normalized_fragment = m.normalize_text_value(fragment)
        return any(normalized_fragment in m.normalize_text_value(str(value)) for value in values)

    def _assert_fragment(self, values: list[str], fragment: str):
        self.assertTrue(
            self._contains_fragment(values, fragment),
            f"Expected fragment '{fragment}' in {values}",
        )

    def _assert_policy_set(self, policies: dict, spec: dict):
        for policy in spec.get("policies", []):
            self.assertIn(policy, policies["policy_names"], f"Expected policy '{policy}' in {policies['policy_names']}")
        for required in spec.get("required", []):
            self._assert_fragment(policies["required_products"], required)
        for forbidden in spec.get("forbidden", []):
            self._assert_fragment(policies["forbidden_products"], forbidden)
        for mandatory in spec.get("mandatory", []):
            self._assert_fragment(policies["mandatory_steps"], mandatory)

    def test_multisurface_policy_matrix(self):
        cases_run = 0
        for spec in _multi_surface_specs():
            for question in _multi_surface_variants(spec["anchor"]):
                with self.subTest(case=spec["name"], question=question):
                    snapshot = _build_policy_snapshot(question)
                    self._assert_policy_set(snapshot["policies"], spec)
                    cases_run += 1

        self.assertEqual(cases_run, len(_multi_surface_specs()) * 8)

    def test_contradiction_policy_matrix(self):
        cases_run = 0
        for spec in _contradiction_specs():
            for question in _contradiction_variants(spec["anchor"]):
                with self.subTest(case=spec["name"], question=question):
                    snapshot = _build_policy_snapshot(question)
                    self._assert_policy_set(snapshot["policies"], spec)
                    cases_run += 1

        self.assertEqual(cases_run, len(_contradiction_specs()) * 8)


if __name__ == "__main__":
    unittest.main()