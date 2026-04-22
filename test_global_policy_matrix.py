import unittest
from unittest import mock

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


class GlobalPolicyMatrixTests(unittest.TestCase):
    def assertContains(self, values, expected):
        self.assertIn(expected, values, f"Expected '{expected}' in {values}")

    def assertAnyContains(self, values, expected_fragment):
        self.assertTrue(
            any(expected_fragment.lower() in str(value).lower() for value in values),
            f"Expected fragment '{expected_fragment}' in {values}",
        )

    def test_question_category_does_not_inject_commercial_names_without_evidence(self):
        candidates = m.extract_candidate_products_from_rag_context(
            "",
            None,
            original_question="Tengo un techo de eternit exterior repintado y envejecido",
        )
        self.assertEqual(candidates, [])

    def test_technical_inventory_lookup_does_not_expand_portfolio_when_disabled(self):
        with mock.patch.object(m, "lookup_product_context", return_value=[]), mock.patch.object(
            m,
            "_expand_terms_with_portfolio_knowledge",
            return_value=["Sellomax", "Koraza"],
        ) as expand_mock:
            candidates = m.lookup_inventory_candidates_from_terms(
                ["impermeabilizante techo"],
                {},
                allow_portfolio_expansion=False,
            )

        self.assertEqual(candidates, [])
        expand_mock.assert_not_called()

    def test_humedad_capilaridad_blocks_fachada_products(self):
        snapshot = _build_policy_snapshot("Muro interior con salitre y humedad que sube desde la base del muro")
        self.assertEqual(snapshot["diagnosis"]["problem_class"], "humedad_interior_capilaridad")
        self.assertContains(snapshot["policies"]["required_products"], "Aquablock")
        self.assertContains(snapshot["policies"]["forbidden_products"], "Koraza")
        self.assertContains(snapshot["policies"]["policy_names"], "humedad_interior_negativa")

    def test_eternit_requires_humid_prep_and_sellomax(self):
        snapshot = _build_policy_snapshot("Techo de eternit exterior repintado y envejecido")
        self.assertEqual(snapshot["diagnosis"]["problem_class"], "eternit_fibrocemento")
        self.assertContains(snapshot["policies"]["required_products"], "Sellomax")
        self.assertContains(snapshot["policies"]["required_products"], "Koraza")
        self.assertContains(snapshot["policies"]["forbidden_tools"], "lijas")
        self.assertContains(snapshot["policies"]["policy_names"], "eternit_fibrocemento_exterior")

    def test_eternit_policy_candidates_prioritize_required_system(self):
        snapshot = _build_policy_snapshot("Techo de eternit exterior repintado y envejecido")
        candidate_terms = m._derive_policy_inventory_candidate_terms(
            snapshot["guide"],
            snapshot["policies"],
            expert_notes=[],
            explicit_product="",
        )
        self.assertGreaterEqual(len(candidate_terms), 2)
        self.assertEqual(candidate_terms[:2], ["Sellomax", "Koraza"])

    def test_inventory_candidate_filter_removes_noise_against_required_products(self):
        snapshot = _build_policy_snapshot("Techo de eternit exterior repintado y envejecido")
        raw_candidates = [
            {
                "codigo": "5892274",
                "descripcion": "PQ PINTUCO FILL 7 GRIS 2753 20K",
                "etiqueta_auditable": "[5892274] - PQ PINTUCO FILL 7 GRIS 2753 20K",
                "marca": "Pintuco",
            },
            {
                "codigo": "5890001",
                "descripcion": "PQ SELLOMAX ULTRA WHITE 3.79L",
                "etiqueta_auditable": "[5890001] - PQ SELLOMAX ULTRA WHITE 3.79L",
                "marca": "Pintuco",
            },
            {
                "codigo": "5890706",
                "descripcion": "PQ KORAZA MAT BLANCO 2650 3.79L",
                "etiqueta_auditable": "[5890706] - PQ KORAZA MAT BLANCO 2650 3.79L",
                "marca": "Pintuco",
            },
        ]
        filtered = m._filter_inventory_candidates_by_policy(raw_candidates, snapshot["policies"])
        filtered_codes = [item["codigo"] for item in filtered]
        self.assertEqual(filtered_codes, ["5890001", "5890706"])

    def test_ladrillo_vista_prefers_cleaner_and_waterproofer(self):
        snapshot = _build_policy_snapshot("Ladrillo a la vista exterior sin cambiar apariencia")
        self.assertEqual(snapshot["diagnosis"]["problem_class"], "ladrillo_vista")
        self.assertContains(snapshot["policies"]["required_products"], "Construcleaner Limpiador Desengrasante")
        self.assertContains(snapshot["policies"]["required_products"], "Siliconite 7")
        self.assertContains(snapshot["policies"]["forbidden_products"], "Koraza")

    def test_metal_old_alkyd_requires_full_removal(self):
        snapshot = _build_policy_snapshot("Reja con esmalte sintetico viejo y anticorrosivo alquidico")
        self.assertEqual(snapshot["diagnosis"]["problem_class"], "metal_pintado_alquidico")
        self.assertContains(snapshot["policies"]["forbidden_products"], "Interseal")
        self.assertAnyContains(snapshot["policies"]["mandatory_steps"], "metal desnudo")
        self.assertContains(snapshot["policies"]["policy_names"], "metal_pintado_alquidico")

    def test_heavy_traffic_floor_requires_quartz_system(self):
        snapshot = _build_policy_snapshot("Piso industrial de concreto para montacargas y estibadores")
        self.assertEqual(snapshot["diagnosis"]["problem_class"], "piso_industrial")
        self.assertContains(snapshot["policies"]["required_products"], "Intergard 2002")
        self.assertContains(snapshot["policies"]["required_products"], "Arena de Cuarzo ref 5891610")
        self.assertContains(snapshot["policies"]["forbidden_products"], "Pintucoat")
        self.assertContains(snapshot["policies"]["policy_names"], "piso_industrial_trafico_pesado")

    def test_medium_floor_blocks_metal_primer(self):
        snapshot = _build_policy_snapshot("Garaje de concreto interior con trafico medio")
        self.assertContains(snapshot["policies"]["required_products"], "Interseal gris RAL 7038")
        self.assertContains(snapshot["policies"]["required_products"], "Pintucoat")
        self.assertContains(snapshot["policies"]["forbidden_products"], "Primer 50RS")

    def test_uncured_concrete_requires_waiting(self):
        snapshot = _build_policy_snapshot("Piso de concreto nuevo recien fundido sin curar")
        self.assertContains(snapshot["policies"]["policy_names"], "concreto_sin_curado")
        self.assertAnyContains(snapshot["policies"]["mandatory_steps"], "28 dias")

    def test_exterior_wood_forbids_interior_polyurethane(self):
        snapshot = _build_policy_snapshot("Deck de madera exterior expuesto a sol y lluvia")
        self.assertEqual(snapshot["diagnosis"]["problem_class"], "madera")
        self.assertContains(snapshot["policies"]["required_products"], "Barnex")
        self.assertContains(snapshot["policies"]["forbidden_products"], "Poliuretano Alto Trafico 1550/1551")

    def test_interior_wood_high_traffic_requires_1550_system(self):
        snapshot = _build_policy_snapshot("Escalera interior de madera para vitrificar con alto trafico")
        self.assertContains(snapshot["policies"]["required_products"], "Poliuretano Alto Trafico 1550/1551")
        self.assertContains(snapshot["policies"]["policy_names"], "madera_interior_alto_trafico")

    def test_roof_concrete_cracks_uses_fill_not_koraza(self):
        snapshot = _build_policy_snapshot("Techo de concreto con grietas y fisuras en terraza")
        self.assertContains(snapshot["policies"]["required_products"], "Pintuco Fill")
        self.assertContains(snapshot["policies"]["forbidden_products"], "Koraza")
        self.assertContains(snapshot["policies"]["policy_names"], "techo_concreto_grietas")

    def test_bathroom_mold_prefers_antifungal_finish(self):
        snapshot = _build_policy_snapshot("Baño con hongos por condensacion en muro interior")
        self.assertContains(snapshot["policies"]["required_products"], "Viniltex Baños y Cocinas")
        self.assertContains(snapshot["policies"]["forbidden_products"], "Koraza")
        self.assertContains(snapshot["policies"]["policy_names"], "bano_cocina_antihongos")

    def test_sports_court_blocks_industrial_floor_systems(self):
        snapshot = _build_policy_snapshot("Cancha deportiva exterior y sendero peatonal")
        self.assertContains(snapshot["policies"]["required_products"], "Pintura Canchas")
        self.assertContains(snapshot["policies"]["forbidden_products"], "Pintucoat")
        self.assertContains(snapshot["policies"]["policy_names"], "cancha_sendero_peatonal")

    def test_galvanized_metal_requires_wash_primer(self):
        snapshot = _build_policy_snapshot("Lamina zinc galvanizada nueva para pintar")
        self.assertContains(snapshot["policies"]["required_products"], "Wash Primer")
        self.assertContains(snapshot["policies"]["policy_names"], "metal_nuevo_galvanizado")

    def test_immersion_water_potable_activates_conditional_route(self):
        snapshot = _build_policy_snapshot("Tanque de agua potable con sistema para inmersion")
        self.assertContains(snapshot["policies"]["policy_names"], "inmersion_agua_potable_condicional")
        self.assertContains(snapshot["policies"]["forbidden_products"], "Pintucoat")
        self.assertAnyContains(snapshot["policies"]["mandatory_steps"], "NSF")

    def test_fire_protection_requires_interchar(self):
        snapshot = _build_policy_snapshot("Estructura metalica con proteccion pasiva contra incendio e intumescente")
        self.assertContains(snapshot["policies"]["required_products"], "Interchar")
        self.assertContains(snapshot["policies"]["policy_names"], "proteccion_pasiva_incendio")

    def test_high_aesthetic_industrial_finish_prefers_interfine(self):
        snapshot = _build_policy_snapshot("Acabado industrial de alta estetica con alta retencion de color")
        self.assertContains(snapshot["policies"]["required_products"], "Interfine")
        self.assertContains(snapshot["policies"]["policy_names"], "acabado_industrial_alta_estetica")

    def test_aggressive_chemical_environment_requires_full_industrial_system(self):
        snapshot = _build_policy_snapshot("Planta industrial con ambiente quimico severo y corrosion industrial")
        self.assertContains(snapshot["policies"]["required_products"], "Intergard")
        self.assertContains(snapshot["policies"]["required_products"], "Interseal")
        self.assertContains(snapshot["policies"]["required_products"], "Interthane 990 + Catalizador")
        self.assertContains(snapshot["policies"]["policy_names"], "ambiente_quimico_industrial")


if __name__ == "__main__":
    unittest.main()