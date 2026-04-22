import unittest
from unittest.mock import patch

from backend.ingest_technical_sheets import build_heuristic_technical_profile
from backend.pipeline_pedido.matcher_inventario import (
    BicomponenteInyectado,
    LineaResuelta,
    ResultadoMatchPedido,
)
from backend.pipeline_pedido.validador_pedido import ejecutar_validacion_pedido


class PedidoTechnicalValidationTests(unittest.TestCase):
    def test_missing_bicomponent_blocks_order(self):
        match_result = ResultadoMatchPedido(
            productos_resueltos=[
                LineaResuelta(
                    producto_solicitado="Pintucoat Epoxico",
                    cantidad=2,
                    unidad="galon",
                    codigo_encontrado="6001",
                    descripcion_real="PINTUCOAT EPOXICO SA GRIS 6001 3.79L",
                    disponible=True,
                )
            ],
            bicomponentes_inyectados=[
                BicomponenteInyectado(
                    tipo="catalizador",
                    para_producto="Pintucoat Epoxico",
                    nombre="Catalizador Epoxico Parte B",
                    disponible=False,
                )
            ],
            tienda_codigo="189",
            tienda_nombre="Parque Olaya - Pereira",
        )

        result = ejecutar_validacion_pedido(match_result)

        self.assertFalse(result.valido)
        self.assertFalse(result.puede_continuar)
        self.assertIn("companion_not_found", result.acciones_requeridas)

    def test_chemical_incompatibility_blocks_order(self):
        match_result = ResultadoMatchPedido(
            productos_resueltos=[
                LineaResuelta(
                    producto_solicitado="Corrotec",
                    cantidad=1,
                    unidad="galon",
                    codigo_encontrado="5001",
                    descripcion_real="CORROTEC ANTICORROSIVO GRIS GALON",
                    disponible=True,
                ),
                LineaResuelta(
                    producto_solicitado="Interthane 990",
                    cantidad=1,
                    unidad="galon",
                    codigo_encontrado="8001",
                    descripcion_real="INTERTHANE 990 SA GRIS 3.79L",
                    disponible=True,
                ),
            ],
            bicomponentes_inyectados=[
                BicomponenteInyectado(
                    tipo="catalizador",
                    para_producto="Interthane 990",
                    nombre="PHA046 catalizador",
                    codigo_encontrado="8010",
                    descripcion_real="PHA046 CATALIZADOR INTERTHANE 3.79L",
                    disponible=True,
                )
            ],
            tienda_codigo="189",
            tienda_nombre="Parque Olaya - Pereira",
        )

        def _metadata_lookup(text: str):
            normalized = text.upper()
            if "CORROTEC" in normalized:
                return {"chemical_family": "alquidica"}
            if "INTERTHANE 990" in normalized:
                return {"chemical_family": "poliuretano"}
            return {}

        with patch(
            "backend.pipeline_pedido.validador_pedido._resolve_structured_product_metadata",
            side_effect=_metadata_lookup,
        ):
            result = ejecutar_validacion_pedido(match_result)

        self.assertFalse(result.valido)
        self.assertFalse(result.puede_continuar)
        self.assertIn("chemical_incompatibility", result.acciones_requeridas)

    def test_heuristic_profile_extracts_compatibility_metadata(self):
        profile, _ = build_heuristic_technical_profile(
            filename="Interthane 990 FT.pdf",
            path_lower="/fichas/interthane-990-ft.pdf",
            marca="International",
            canonical_family="INTERTHANE 990",
            clean_text=(
                "Interthane 990 es un acabado poliuretano de dos componentes. "
                "Catalizador PHA046. Relacion de mezcla 4:1. "
                "No aplicar sobre sistemas alquidicos sin remocion completa."
            ),
            pdf_entry={},
            doc_kind="ficha_tecnica",
            portfolio_segment="recubrimientos_pinturas",
            portfolio_subsegment="industrial_proteccion",
        )

        self.assertEqual(profile["chemical_family"], "poliuretano")
        self.assertEqual(profile["component_count"], 2)
        self.assertTrue(profile["requires_component_b"])
        self.assertIn("PHA046", profile["component_b_name"])
        self.assertEqual(profile["mix_ratio_text"], "Relacion de mezcla 4:1")
        self.assertIn("alquidica", profile["incompatible_previous_families"])


if __name__ == "__main__":
    unittest.main()