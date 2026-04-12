import unittest

from backend.ingest_technical_sheets import build_heuristic_technical_profile


class TechnicalProfileExtractionTests(unittest.TestCase):
    def test_extracts_surface_targets_alerts_and_diagnostic_questions(self):
        clean_text = """
        DESCRIPCION
        Recubrimiento protector para ladrillo poroso y mampostería exterior.
        Ideal para fachadas absorbentes expuestas a intemperie.

        PREPARACION DE SUPERFICIE
        La superficie debe estar seca, libre de polvo, sales y humedad ascendente.
        Verifique la porosidad antes de aplicar el producto.

        APLICACION
        Aplique con brocha o rodillo en dos manos uniformes.

        LIMITACIONES
        No aplicar sobre fachaleta sellada, superficies vitrificadas o sustratos con baja absorción.
        Evite aplicar si existe humedad activa o filtración permanente.
        """
        profile, _ = build_heuristic_technical_profile(
            filename="Siliconite 7.pdf",
            path_lower="/data/fichas/siliconite7.pdf",
            marca="Pintuco",
            canonical_family="PINTUCO SILICONITE 7",
            clean_text=clean_text,
            pdf_entry={"content_hash": "abc123", "duplicate_count": 0, "duplicate_members": []},
            doc_kind="ficha_tecnica",
            portfolio_segment="recubrimientos_pinturas",
            portfolio_subsegment="impermeabilizacion_humedad",
        )

        self.assertIn("ladrillo", profile["commercial_context"]["compatible_surfaces"])
        self.assertIn("mamposteria", profile["commercial_context"]["compatible_surfaces"])
        self.assertIn("ladrillo", profile["commercial_context"]["incompatible_surfaces"])
        self.assertIn("brocha", profile["application"]["application_methods"])
        self.assertTrue(profile["alerts"])
        self.assertTrue(profile["alerts_detail"]["critical"])
        self.assertTrue(profile["solution_guidance"]["diagnostic_questions"])
        self.assertTrue(any("porosa" in question.lower() or "sellada" in question.lower() for question in profile["solution_guidance"]["diagnostic_questions"]))

    def test_source_excerpts_are_persisted_for_audit(self):
        clean_text = """
        DESCRIPCION
        Imprimante acrílico para concreto y estuco.

        PREPARACION DE SUPERFICIE
        La superficie debe estar curada y libre de polvo.

        APLICACION
        Aplicar con rodillo o brocha.
        """
        profile, _ = build_heuristic_technical_profile(
            filename="Imprimax.pdf",
            path_lower="/data/fichas/imprimax.pdf",
            marca="Pintuco",
            canonical_family="PINTUCO IMPRIMAX",
            clean_text=clean_text,
            pdf_entry={"content_hash": "def456", "duplicate_count": 0, "duplicate_members": []},
            doc_kind="ficha_tecnica",
            portfolio_segment="recubrimientos_pinturas",
            portfolio_subsegment="arquitectonico_decorativo",
        )

        self.assertTrue(profile["source_excerpts"])
        self.assertTrue(all("section" in item and "text" in item for item in profile["source_excerpts"]))


if __name__ == "__main__":
    unittest.main()
