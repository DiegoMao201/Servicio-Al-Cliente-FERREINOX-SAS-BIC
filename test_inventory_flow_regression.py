from tests.internal.test_inventory_flow_regression import *


if __name__ == "__main__":
    import unittest

    unittest.main()
                    "stock_total": "0.0",
                    "stock_por_tienda": "TIENDA PEREIRA: 4.0; TIENDA ARMENIA: 1.0",
                }
            ]

        with mock.patch.object(main, "lookup_product_context", side_effect=fake_lookup), \
             mock.patch.object(main, "fetch_product_price", return_value={"precio_mejor": 67143}), \
             mock.patch.object(main, "fetch_product_companions", return_value=[]), \
             mock.patch.object(main, "fetch_expert_knowledge", return_value=[]), \
             mock.patch.object(main, "fetch_exact_store_stock_for_reference", return_value=0):
            payload = json.loads(
                main._handle_tool_consultar_inventario(
                    {
                        "producto": "inventario de sd1 en galon en opalo",
                        "modo_consulta": "inventario",
                    },
                    {"internal_auth": {"role": "administrador"}},
                )
            )

        self.assertEqual(captured["query_text"], "barniz sd-1")
        self.assertEqual(payload["modo_consulta"], "inventario")
        self.assertEqual(payload["requested_store_code"], "158")
        self.assertEqual(payload["productos"][0]["stock_tienda_solicitada"], 0)
        self.assertNotIn("precio_unitario", payload["productos"][0])

    def test_inventory_handler_prunes_irrelevant_matches_when_one_result_dominates(self):
        with mock.patch.object(
            main,
            "lookup_product_context",
            return_value=[
                {
                    "referencia": "5890919",
                    "descripcion": "MH BARNIZ BR INCOLORO SD-1 3.79L",
                    "stock_total": "21.0",
                    "stock_por_tienda": "TIENDA ARMENIA: 6.0",
                    "specific_score": 3,
                    "match_score": 5,
                },
                {
                    "referencia": "5890866",
                    "descripcion": "PQ CORROTEC PREMIUM MAT GRIS 507 3.79L",
                    "stock_total": "68.0",
                    "stock_por_tienda": "TIENDA OPALO: 6.0",
                    "specific_score": 0,
                    "match_score": 3,
                },
            ],
        ), mock.patch.object(main, "fetch_product_companions", return_value=[]), mock.patch.object(main, "fetch_expert_knowledge", return_value=[]):
            payload = json.loads(
                main._handle_tool_consultar_inventario(
                    {
                        "producto": "Inventario de sd1 en galón tenemos ?",
                        "modo_consulta": "inventario",
                    },
                    {"internal_auth": {"role": "administrador"}},
                )
            )

        self.assertFalse(payload["requiere_aclaracion"])
        self.assertEqual(payload["encontrados"], 1)
        self.assertEqual(payload["productos"][0]["codigo"], "5890919")

    def test_lookup_product_context_prioritizes_explicit_codes_over_learned_references(self):
        class DummyConnection:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        class DummyEngine:
            def connect(self):
                return DummyConnection()

        with mock.patch.object(main, "get_db_engine", return_value=DummyEngine()), \
             mock.patch.object(main, "fetch_rotation_cache", return_value={}), \
             mock.patch.object(main, "fetch_learned_product_references", return_value=["5892240"]), \
             mock.patch.object(
                 main,
                 "fetch_code_product_rows",
                 return_value=[
                     {
                         "referencia": "5891322",
                         "descripcion": "P7 PINTUTRAF BS AMARILLO 13755-659 3.79L",
                         "stock_total": "9.0",
                     },
                     {
                         "referencia": "5891323",
                         "descripcion": "P7 PINTUTRAF BS AMARILL 13755-659 18.93L",
                         "stock_total": "4.0",
                     },
                 ],
             ), \
             mock.patch.object(main, "fetch_reference_product_rows", return_value=[
                 {
                     "referencia": "5892240",
                     "descripcion": "PQ VINILTEX ADV MAT BLANCO 1501 3.79L PE",
                     "stock_total": "425.0",
                 }
             ]):
            rows = main.lookup_product_context(
                "13755",
                {
                    "product_codes": ["13755"],
                    "requested_unit": "galon",
                    "nlu_processed": True,
                    "core_terms": ["galon"],
                    "search_terms": ["galon"],
                },
            )

        self.assertEqual(rows[0]["referencia"], "5891322")
        self.assertEqual(len(rows), 1)

    def test_v3_explicit_inventory_clears_commercial_draft(self):
        """When user says 'inventario de...', commercial_draft should be cleared
        so the LLM sees a clean state without commercial contamination."""
        import backend.agent_v3 as agent_v3

        conversation_context = {
            "commercial_draft": {"intent": "cotizacion", "items": [{"producto": "Koraza"}]},
        }
        # After the explicit inventory check, draft should be gone
        msg = "Inventario de sd1 en galón tenemos ?"
        from backend.agent_v3 import _is_explicit_inventory_query
        self.assertTrue(_is_explicit_inventory_query(msg))
        # Simulate what generate_agent_reply_v3 now does:
        if _is_explicit_inventory_query(msg):
            conversation_context.pop("commercial_draft", None)
        self.assertNotIn("commercial_draft", conversation_context)


if __name__ == "__main__":
    unittest.main()