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


if __name__ == "__main__":
    unittest.main()
