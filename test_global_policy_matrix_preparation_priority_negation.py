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


def _preparation_variants(anchor: str) -> list[str]:
    return [
        anchor,
        f"Antes de aplicar el producto haria esto: {anchor}",
        f"Cliente propone esta preparacion: {anchor}",
        f"Necesito validar si esta preparacion es correcta: {anchor}",
        f"Asesoria tecnica enfocada en metodo: {anchor}",
        f"El aplicador quiere trabajar asi: {anchor}",
        f"Caso de preparacion previa: {anchor}",
        f"Revisa si este metodo esta bien: {anchor}",
    ]


def _priority_variants(anchor: str) -> list[str]:
    return [
        anchor,
        f"Consulta mixta con posible ruta critica: {anchor}",
        f"Necesito priorizar la asesoria en este caso: {anchor}",
        f"Caso combinado donde no todo tiene el mismo riesgo: {anchor}",
        f"Proyecto con frente critico y frente decorativo: {anchor}",
        f"Quiero criterio de prioridad para: {anchor}",
        f"Asesoria con riesgo tecnico dominante: {anchor}",
        f"Revisa cual ruta debe mandar aqui: {anchor}",
    ]


def _negation_variants(anchor: str) -> list[str]:
    return [
        anchor,
        f"Aclaro desde ya que NO quiero esa opcion: {anchor}",
        f"El contexto historico del cliente es este: {anchor}",
        f"No es una solicitud del producto, es rechazo: {anchor}",
        f"Necesito evitar falso positivo con esta frase: {anchor}",
        f"El usuario menciona el producto solo para descartarlo: {anchor}",
        f"Caso de negacion explicita: {anchor}",
        f"Consulta con rechazo textual incluido: {anchor}",
    ]


def _double_contradiction_variants(anchor: str) -> list[str]:
    return [
        anchor,
        f"El cliente insiste en dos errores a la vez: {anchor}",
        f"Necesito que acumule ambas contradicciones: {anchor}",
        f"Caso con doble producto incorrecto: {anchor}",
        f"No se debe detener en la primera contradiccion: {anchor}",
        f"Asesoria con dos frentes mal planteados: {anchor}",
        f"Quieren cotizar dos rutas incompatibles en paralelo: {anchor}",
        f"Consulta doblemente conflictiva: {anchor}",
    ]


def _preparation_specs() -> list[dict]:
    return [
        {
            "name": "metal_oxidado_agua_jabon",
            "anchor": "voy a lavar el metal oxidado con agua y jabon y luego aplico Pintoxido",
            "policies": ["metal_oxidado_mantenimiento", "metal_oxidado_preparacion_incorrecta"],
            "required_products": ["Pintoxido", "Corrotec"],
            "required_tools": ["grata", "lija"],
            "forbidden_tools": ["agua y jabon"],
            "mandatory": ["metal seco"],
        },
        {
            "name": "metal_oxidado_lavar_con_agua",
            "anchor": "quiero lavar la reja oxidada con agua antes del anticorrosivo",
            "policies": ["metal_oxidado_mantenimiento", "metal_oxidado_preparacion_incorrecta"],
            "required_tools": ["grata", "lija"],
            "forbidden_tools": ["agua y jabon"],
        },
        {
            "name": "metal_oxidado_jabonoso",
            "anchor": "el aplicador piensa usar agua jabonosa en la reja oxidada y despues Corrotec",
            "policies": ["metal_oxidado_mantenimiento", "metal_oxidado_preparacion_incorrecta"],
            "required_products": ["Pintoxido", "Corrotec"],
            "required_tools": ["grata", "lija"],
        },
        {
            "name": "concreto_fresco_acido",
            "anchor": "quiero aplicar acido muriatico al piso de concreto recien fundido para curarlo rapido",
            "policies": ["concreto_sin_curado", "concreto_sin_curado_acido_incorrecto"],
            "forbidden_tools": ["acido muriatico"],
            "mandatory": ["28 dias", "curado"],
        },
        {
            "name": "concreto_nuevo_acido_antes_pintar",
            "anchor": "al concreto nuevo sin curar le voy a echar acido muriatico antes del sistema",
            "policies": ["concreto_sin_curado", "concreto_sin_curado_acido_incorrecto"],
            "forbidden_tools": ["acido muriatico"],
            "mandatory": ["28 dias"],
        },
        {
            "name": "obra_gris_acido",
            "anchor": "en obra gris recien vaciada quiero usar acido muriatico para acelerar la preparacion",
            "policies": ["concreto_sin_curado", "concreto_sin_curado_acido_incorrecto"],
            "forbidden_tools": ["acido muriatico"],
            "mandatory": ["curado"],
        },
    ]


def _priority_specs() -> list[dict]:
    return [
        {
            "name": "agua_potable_y_fachada",
            "anchor": "necesito pintar un tanque de agua potable y la fachada de la casa",
            "policies": ["inmersion_agua_potable_condicional", "fachada_alta_exposicion"],
            "critical": ["inmersion_agua_potable_condicional"],
            "dominant": ["inmersion_agua_potable_condicional"],
            "highest": "critical",
        },
        {
            "name": "agua_potable_y_bano",
            "anchor": "tengo un tanque de agua potable y además un baño interior con hongos",
            "policies": ["inmersion_agua_potable_condicional", "bano_cocina_antihongos"],
            "critical": ["inmersion_agua_potable_condicional"],
            "dominant": ["inmersion_agua_potable_condicional"],
            "highest": "critical",
        },
        {
            "name": "incendio_y_esmalte_decorativo",
            "anchor": "hay una estructura con proteccion pasiva contra incendio y aparte un metal decorativo con esmalte brillante",
            "policies": ["proteccion_pasiva_incendio", "esmalte_decorativo_mantenimiento"],
            "critical": ["proteccion_pasiva_incendio"],
            "dominant": ["proteccion_pasiva_incendio"],
            "highest": "critical",
        },
        {
            "name": "incendio_y_fachada",
            "anchor": "estructura metalica con proteccion contra incendio y también fachada exterior de la casa",
            "policies": ["proteccion_pasiva_incendio", "fachada_alta_exposicion"],
            "critical": ["proteccion_pasiva_incendio"],
            "dominant": ["proteccion_pasiva_incendio"],
            "highest": "critical",
        },
        {
            "name": "agua_potable_y_cancha",
            "anchor": "tanque de agua potable por un lado y cancha deportiva exterior por otro",
            "policies": ["inmersion_agua_potable_condicional", "cancha_sendero_peatonal"],
            "critical": ["inmersion_agua_potable_condicional"],
            "dominant": ["inmersion_agua_potable_condicional"],
            "highest": "critical",
        },
        {
            "name": "agua_potable_e_incendio",
            "anchor": "tengo un tanque de agua potable y una estructura con proteccion pasiva contra incendio",
            "policies": ["inmersion_agua_potable_condicional", "proteccion_pasiva_incendio"],
            "critical": ["inmersion_agua_potable_condicional", "proteccion_pasiva_incendio"],
            "dominant": ["inmersion_agua_potable_condicional", "proteccion_pasiva_incendio"],
            "highest": "critical",
        },
    ]


def _negation_specs() -> list[dict]:
    return [
        {
            "name": "humedad_no_quiere_koraza",
            "anchor": "tengo humedad en un muro interior y no quiero usar Koraza porque ya vi que se sopla",
            "policies": ["humedad_interior_negativa"],
            "absent_policies": ["interior_koraza_redirect"],
            "forbidden_products": ["Koraza"],
        },
        {
            "name": "bano_no_quiere_koraza",
            "anchor": "es un baño interior con hongos y no quiero usar Koraza porque no me convence",
            "policies": ["bano_cocina_antihongos"],
            "absent_policies": ["interior_koraza_redirect"],
            "forbidden_products": ["Koraza"],
        },
        {
            "name": "interior_descarta_koraza",
            "anchor": "muro interior de sala, no quiero usar Koraza, que vinilo recomiendan",
            "absent_policies": ["interior_koraza_redirect"],
        },
        {
            "name": "metal_no_lavar_con_agua",
            "anchor": "la reja oxidada no la voy a lavar con agua y jabon, la preparare con grata y lija",
            "policies": ["metal_oxidado_mantenimiento"],
            "absent_policies": ["metal_oxidado_preparacion_incorrecta"],
        },
        {
            "name": "concreto_no_usar_acido",
            "anchor": "el piso de concreto recien fundido no quiero tratarlo con acido muriatico, prefiero esperar el curado",
            "policies": ["concreto_sin_curado"],
            "absent_policies": ["concreto_sin_curado_acido_incorrecto"],
        },
        {
            "name": "humedad_descarta_koraza_y_pide_opcion",
            "anchor": "muro interior con humedad y salitre, no usaré Koraza, busco una ruta correcta",
            "policies": ["humedad_interior_negativa"],
            "absent_policies": ["interior_koraza_redirect"],
        },
    ]


def _double_contradiction_specs() -> list[dict]:
    return [
        {
            "name": "pintucoat_y_viniltex",
            "anchor": "quiero Pintucoat para la cancha y Viniltex para la reja oxidada",
            "policies": ["cancha_sendero_peatonal", "metal_oxidado_mantenimiento"],
            "required_products": ["Pintura Canchas", "Pintoxido", "Corrotec"],
            "forbidden_products": ["Pintucoat", "Viniltex"],
        },
        {
            "name": "koraza_y_pintucoat",
            "anchor": "quiero Koraza para baño interior con hongos y Pintucoat para la cancha",
            "policies": ["bano_cocina_antihongos", "interior_koraza_redirect", "cancha_sendero_peatonal"],
            "required_products": ["Viniltex Baños y Cocinas", "Viniltex Advanced", "Pintura Canchas"],
            "forbidden_products": ["Koraza", "Pintucoat"],
        },
        {
            "name": "intervinil_y_koraza_ladrillo",
            "anchor": "quiero Intervinil para techo de eternit exterior y Koraza para ladrillo a la vista",
            "policies": ["eternit_fibrocemento_exterior", "ladrillo_a_la_vista"],
            "required_products": ["Sellomax", "Koraza", "Construcleaner", "Siliconite"],
            "forbidden_products": ["Intervinil", "Koraza"],
        },
        {
            "name": "barnex_y_poliuretano_exterior_interior",
            "anchor": "quiero Barnex para escalera interior de madera y poliuretano 1550 para deck exterior",
            "policies": ["madera_interior_alto_trafico", "madera_exterior"],
            "required_products": ["Poliuretano Alto Trafico 1550/1551", "Barnex", "Wood Stain"],
            "forbidden_products": ["Barnex", "Poliuretano Alto Trafico 1550/1551"],
        },
        {
            "name": "pintucoat_y_pintulux_criticos",
            "anchor": "quiero Pintucoat para tanque de agua potable y Pintulux 3 en 1 para proteccion contra incendio",
            "policies": ["inmersion_agua_potable_condicional", "proteccion_pasiva_incendio"],
            "required_products": ["Interchar"],
            "forbidden_products": ["Pintucoat", "Pintulux 3 en 1"],
            "critical": ["inmersion_agua_potable_condicional", "proteccion_pasiva_incendio"],
        },
        {
            "name": "corrotec_y_viniltex",
            "anchor": "quiero Corrotec para acabado industrial de alta estetica y Viniltex para la reja oxidada",
            "policies": ["acabado_industrial_alta_estetica", "metal_oxidado_mantenimiento"],
            "required_products": ["Interfine", "Pintoxido", "Corrotec"],
            "forbidden_products": ["Corrotec", "Viniltex"],
        },
        {
            "name": "interseal_y_koraza",
            "anchor": "quiero Interseal para baño interior con hongos y Koraza para planta con ambiente quimico severo",
            "policies": ["bano_cocina_antihongos", "ambiente_quimico_industrial"],
            "required_products": ["Viniltex Baños y Cocinas", "Intergard", "Interseal", "Interthane 990 + Catalizador"],
            "forbidden_products": ["Interseal", "Koraza"],
        },
        {
            "name": "pintuco_fill_y_pintucoat",
            "anchor": "quiero Pintuco Fill para sellar huecos con espuma expansiva y Pintucoat para la cancha deportiva",
            "policies": ["espuma_poliuretano_sellado", "cancha_sendero_peatonal"],
            "required_products": ["Espuma de Poliuretano", "Pintura Canchas"],
            "forbidden_products": ["Pintuco Fill", "Pintucoat"],
        },
    ]


class GlobalPolicyPreparationPriorityNegationTests(unittest.TestCase):
    def _contains_fragment(self, values: list[str], fragment: str) -> bool:
        target = m.normalize_text_value(fragment)
        return any(target in m.normalize_text_value(str(value)) for value in values)

    def _assert_fragment(self, values: list[str], fragment: str):
        self.assertTrue(self._contains_fragment(values, fragment), f"Expected fragment '{fragment}' in {values}")

    def _assert_absent_policy(self, policies: dict, policy_name: str):
        self.assertNotIn(policy_name, policies.get("policy_names") or [], f"Did not expect policy '{policy_name}' in {policies.get('policy_names')}")

    def _assert_common(self, policies: dict, spec: dict):
        for policy in spec.get("policies", []):
            self.assertIn(policy, policies["policy_names"], f"Expected policy '{policy}' in {policies['policy_names']}")
        for policy in spec.get("absent_policies", []):
            self._assert_absent_policy(policies, policy)
        for required in spec.get("required_products", []):
            self._assert_fragment(policies["required_products"], required)
        for required_tool in spec.get("required_tools", []):
            self._assert_fragment(policies["required_tools"], required_tool)
        for forbidden in spec.get("forbidden_products", []):
            self._assert_fragment(policies["forbidden_products"], forbidden)
        for forbidden_tool in spec.get("forbidden_tools", []):
            self._assert_fragment(policies["forbidden_tools"], forbidden_tool)
        for mandatory in spec.get("mandatory", []):
            self._assert_fragment(policies["mandatory_steps"], mandatory)
        for critical in spec.get("critical", []):
            self.assertIn(critical, policies.get("critical_policy_names") or [], f"Expected critical policy '{critical}' in {policies.get('critical_policy_names')}")
        for dominant in spec.get("dominant", []):
            self.assertIn(dominant, policies.get("dominant_policy_names") or [], f"Expected dominant policy '{dominant}' in {policies.get('dominant_policy_names')}")
        if spec.get("highest"):
            self.assertEqual(policies.get("highest_priority_level"), spec["highest"])

    def test_preparation_hardening_matrix(self):
        cases_run = 0
        for spec in _preparation_specs():
            for question in _preparation_variants(spec["anchor"]):
                with self.subTest(case=spec["name"], question=question):
                    snapshot = _build_policy_snapshot(question)
                    self._assert_common(snapshot["policies"], spec)
                    cases_run += 1
        self.assertEqual(cases_run, len(_preparation_specs()) * 8)

    def test_priority_dominance_matrix(self):
        cases_run = 0
        for spec in _priority_specs():
            for question in _priority_variants(spec["anchor"]):
                with self.subTest(case=spec["name"], question=question):
                    snapshot = _build_policy_snapshot(question)
                    self._assert_common(snapshot["policies"], spec)
                    cases_run += 1
        self.assertEqual(cases_run, len(_priority_specs()) * 8)

    def test_negation_false_positive_matrix(self):
        cases_run = 0
        for spec in _negation_specs():
            for question in _negation_variants(spec["anchor"]):
                with self.subTest(case=spec["name"], question=question):
                    snapshot = _build_policy_snapshot(question)
                    self._assert_common(snapshot["policies"], spec)
                    cases_run += 1
        self.assertEqual(cases_run, len(_negation_specs()) * 8)

    def test_double_contradiction_matrix(self):
        cases_run = 0
        for spec in _double_contradiction_specs():
            for question in _double_contradiction_variants(spec["anchor"]):
                with self.subTest(case=spec["name"], question=question):
                    snapshot = _build_policy_snapshot(question)
                    self._assert_common(snapshot["policies"], spec)
                    cases_run += 1
        self.assertEqual(cases_run, len(_double_contradiction_specs()) * 8)


if __name__ == "__main__":
    unittest.main()