"""
Tests: Diagnostic-first flow — el agente NO debe mencionar productos antes de diagnosticar.
Valida que build_turn_context bloquee herramientas y productos cuando faltan datos.
"""
import sys, os, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

from agent_context import build_turn_context, extract_diagnostic_data, _infer_problem_class


class DiagnosticFirstTests(unittest.TestCase):
    """Verifica que el bloqueo de diagnóstico incompleto funcione correctamente."""

    def _build_ctx(self, user_msg, recent=None, conv_ctx=None):
        return build_turn_context(
            conversation_context=conv_ctx or {},
            recent_messages=recent or [],
            user_message=user_msg,
            internal_auth={},
            profile_name="Cliente Test",
        )

    # ── Test 1: "pintar un piso" sin más datos → BLOQUEO ──
    def test_piso_sin_diagnostico_bloquea_herramientas(self):
        ctx = self._build_ctx("necesito asesoría para pintar un piso")
        self.assertIn("BLOQUEO DE DIAGNÓSTICO INCOMPLETO", ctx)
        self.assertIn("consultar_conocimiento_tecnico", ctx)
        self.assertIn("PROHIBIDO", ctx)

    # ── Test 2: "pintar un piso" debe pedir tráfico ──
    def test_piso_pide_tipo_trafico(self):
        ctx = self._build_ctx("necesito asesoría para pintar un piso")
        self.assertIn("tráfico", ctx.lower())

    # ── Test 3: "pintar un piso" debe pedir interior/exterior ──
    def test_piso_pide_ubicacion(self):
        ctx = self._build_ctx("necesito asesoría para pintar un piso")
        self.assertIn("ubicación", ctx)

    # ── Test 4: piso + interior + tráfico liviano + condición → NO bloqueo ──
    def test_piso_con_diagnostico_completo_no_bloquea(self):
        recent = [
            {"direction": "inbound", "contenido": "quiero pintar un piso interior de concreto nuevo, tráfico peatonal"},
        ]
        ctx = self._build_ctx(
            "es para una oficina",
            recent=recent,
        )
        self.assertNotIn("BLOQUEO DE DIAGNÓSTICO INCOMPLETO", ctx)

    # ── Test 5: "pintar una fachada" sin condición → BLOQUEO ──
    def test_fachada_sin_condicion_bloquea(self):
        ctx = self._build_ctx("quiero pintar la fachada de mi casa")
        # fachada implies exterior, so only condition is missing
        self.assertIn("BLOQUEO DE DIAGNÓSTICO INCOMPLETO", ctx)

    # ── Test 6: extract_diagnostic_data para "piso" extrae surface=piso ──
    def test_extract_diagnostic_piso(self):
        data = extract_diagnostic_data("necesito pintar un piso", [])
        self.assertEqual(data["surface"], "piso")

    # ── Test 7: _infer_problem_class para piso → piso_industrial ──
    def test_infer_problem_class_piso(self):
        diag = {"surface": "piso", "condition": None, "interior_exterior": None}
        pc = _infer_problem_class(diag, "quiero pintar un piso")
        self.assertEqual(pc, "piso_industrial")

    # ── Test 8: piso con solo interior pero sin tráfico ni condición → BLOQUEO ──
    def test_piso_interior_sin_trafico_bloquea(self):
        recent = [
            {"direction": "inbound", "contenido": "quiero pintar un piso"},
        ]
        ctx = self._build_ctx("es un piso interior, necesito asesoría", recent=recent)
        self.assertIn("BLOQUEO DE DIAGNÓSTICO INCOMPLETO", ctx)

    # ── Test 9: muro con humedad → BLOQUEO (condición problemática sin m²) ──
    def test_muro_humedad_bloquea_sin_m2(self):
        ctx = self._build_ctx("tengo humedad en una pared interior")
        # Should trigger either diagnostic incomplete or the humidity block
        has_block = ("BLOQUEO" in ctx)
        self.assertTrue(has_block, "Muro con humedad debe tener algún tipo de bloqueo")

    # ── Test 10: metal oxidado sin ubicación → BLOQUEO ──
    def test_metal_oxidado_sin_ubicacion_bloquea(self):
        ctx = self._build_ctx("necesito pintar una reja oxidada")
        self.assertIn("BLOQUEO DE DIAGNÓSTICO INCOMPLETO", ctx)

    # ── Test 11: madera sin condición → BLOQUEO ──
    def test_madera_sin_condicion_bloquea(self):
        ctx = self._build_ctx("quiero pintar unas puertas de madera")
        self.assertIn("BLOQUEO DE DIAGNÓSTICO INCOMPLETO", ctx)

    # ── Test 12: techo sin condición → BLOQUEO ──
    def test_techo_sin_condicion_bloquea(self):
        ctx = self._build_ctx("necesito asesoría para el techo")
        self.assertIn("BLOQUEO DE DIAGNÓSTICO INCOMPLETO", ctx)

    # ── Test 13: fachada con condición completa → NO bloqueo ──
    def test_fachada_con_condicion_no_bloquea(self):
        recent = [
            {"direction": "inbound", "contenido": "quiero pintar la fachada de mi casa, está descascarando"},
        ]
        ctx = self._build_ctx("sí está pelando la pintura vieja", recent=recent)
        # fachada implies exterior, descascarando is condition → should not block
        self.assertNotIn("BLOQUEO DE DIAGNÓSTICO INCOMPLETO", ctx)

    # ── Test 14: "laboratorio" detecta interior ──
    def test_laboratorio_detected_as_interior(self):
        diag = extract_diagnostic_data("necesito pintar las paredes de un laboratorio", [])
        self.assertEqual(diag["surface"], "muro")
        self.assertEqual(diag["interior_exterior"], "interior")

    # ── Test 15: is_diagnostic_incomplete helper ──
    def test_is_diagnostic_incomplete(self):
        from agent_context import is_diagnostic_incomplete
        diag_empty = {"surface": "muro", "interior_exterior": None, "condition": None}
        self.assertTrue(is_diagnostic_incomplete("asesoria", diag_empty))
        diag_full = {"surface": "muro", "interior_exterior": "interior", "condition": "superficie nueva"}
        self.assertFalse(is_diagnostic_incomplete("asesoria", diag_full))
        # Non-asesoria intent should never block
        self.assertFalse(is_diagnostic_incomplete("pedido_directo", diag_empty))

    # ── Test 16: laboratorio → BLOQUEO because condition is missing ──
    def test_laboratorio_blocks_without_condition(self):
        ctx = self._build_ctx("necesito pintar las paredes de un laboratorio")
        # interior detected from "laboratorio", surface from "paredes", but NO condition
        self.assertIn("BLOQUEO DE DIAGNÓSTICO INCOMPLETO", ctx)
        self.assertIn("condición", ctx)
        # Should NOT ask for ubicación since laboratorio → interior is detected
        self.assertNotIn("ubicación", ctx)


if __name__ == "__main__":
    unittest.main()
