import os
import sys
import unittest
from unittest import mock


ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
BACKEND_DIR = os.path.join(ROOT_DIR, "backend")

sys.path.insert(0, BACKEND_DIR)

os.environ.setdefault("DATABASE_URL", "postgresql://postgres:x@localhost:5432/test")
os.environ.setdefault("OPENAI_API_KEY", "sk-test")

import agent_profiles
import agent_context
import agent_v3
import internal_agent_ops
import main


class InternalAgentProfileTests(unittest.TestCase):
    def test_internal_profile_filters_tools_and_disables_transactional_flows(self):
        with mock.patch.dict(os.environ, {"AGENT_PROFILE": "internal"}, clear=False):
            runtime_config = agent_profiles.get_agent_runtime_config()

        tool_names = [tool["function"]["name"] for tool in runtime_config["tools"]]

        self.assertEqual(runtime_config["profile"], "internal")
        self.assertFalse(runtime_config["enable_order_pipeline"])
        self.assertFalse(runtime_config["enable_quote_pipeline"])
        self.assertFalse(runtime_config["enable_iva_guard"])
        self.assertFalse(runtime_config["force_first_advisory_depth_turn"])
        self.assertEqual(
            tool_names,
            [
                "consultar_inventario",
                "consultar_conocimiento_tecnico",
                "consultar_bi_universal",
                "consultar_ventas_internas",
                "consultar_indicadores_internos",
                "enviar_reporte_interno_correo",
                "buscar_documento_tecnico",
            ],
        )

    def test_internal_profile_blocks_transfer_and_logistics_scope(self):
        with mock.patch.dict(os.environ, {"AGENT_PROFILE": "internal"}, clear=False):
            with mock.patch.object(main, "resolve_internal_session", return_value={"id": 7, "role": "operador", "session_expires_at": "2099-01-01T00:00:00Z"}):
                with mock.patch.object(main, "build_internal_auth_context", return_value={"token": "abc", "role": "operador"}):
                    with mock.patch.object(main, "find_employee_record_by_phone", return_value=None):
                        response = main.handle_internal_whatsapp_message(
                            "crear traslado de viniltex a manizales",
                            {"telefono_e164": "+573001112233"},
                            {"internal_auth": {"token": "abc"}},
                        )

        self.assertIsNotNone(response)
        self.assertEqual(response["intent"], "internal_scope_blocked")
        self.assertIn("No gestiona despachos, reclamos internos ni traslados", response["response_text"])

    def test_internal_advisory_context_does_not_force_square_meters_by_default(self):
        context_text = agent_context.build_turn_context(
            conversation_context={},
            recent_messages=[
                {"direction": "inbound", "contenido": "como pinto una fachada"},
            ],
            user_message="tengo humedad y pintura vieja desgastada",
            internal_auth={"role": "administrador"},
            profile_name="Diego",
        )

        self.assertIn("PROFUNDIZACIÓN DIAGNÓSTICA", context_text)
        self.assertNotIn("¿Cuántos m² tiene el área?", context_text)
        self.assertNotIn("Al final pregunta m² y color para calcular cantidades.", context_text)

    def test_internal_prompt_closes_with_technical_handoff_not_quote_push(self):
        with mock.patch.dict(os.environ, {"AGENT_PROFILE": "internal"}, clear=False):
            runtime_config = agent_profiles.get_agent_runtime_config()

        system_prompt = runtime_config["system_prompt"]

        self.assertIn("No crear cotizaciones.", system_prompt)
        self.assertIn("No preguntes m² por defecto en este canal.", system_prompt)
        self.assertIn("Consultar indicadores internos de ventas, proyeccion, cartera e inventario.", system_prompt)
        self.assertIn("Exportar reportes internos por correo con Excel adjunto", system_prompt)
        self.assertIn("interpreta que pide el consolidado de toda la empresa", system_prompt)
        self.assertIn("consultar_bi_universal", system_prompt)
        self.assertIn("clientes con decrecimiento", system_prompt)
        self.assertIn("clientes para reactivar", system_prompt)
        self.assertIn("productos para impulsar", system_prompt)
        self.assertIn("Si quieres, te conecto con un asesor comercial para cotizar los productos.", system_prompt)

    def test_universal_bi_plan_detects_open_analytics_intent(self):
        plan = internal_agent_ops._infer_universal_bi_plan(
            "Cuales son los 10 productos que debo impulsar este mes y en que clientes",
            None,
            None,
        )

        self.assertEqual(plan["kind"], "indicator")
        self.assertEqual(plan["tipo_consulta"], "productos_a_impulsar")
        self.assertEqual(plan["limite"], 10)

    def test_universal_bi_plan_detects_semantic_growth_analysis(self):
        plan = internal_agent_ops._infer_universal_bi_plan(
            "Dime el crecimiento por linea este mes vs año anterior",
            None,
            None,
        )

        self.assertEqual(plan["kind"], "semantic")
        self.assertEqual(plan["analysis"], "crecimiento")
        self.assertEqual(plan["dimension"], "marca")

    def test_universal_bi_plan_detects_cartera_concentration(self):
        plan = internal_agent_ops._infer_universal_bi_plan(
            "Cual es la concentracion de cartera por cliente",
            None,
            None,
        )

        self.assertEqual(plan["kind"], "semantic")
        self.assertEqual(plan["analysis"], "concentracion_cartera")
        self.assertEqual(plan["dimension"], "cliente")

    # ── Regresiones exactas de preguntas fallidas en WhatsApp 2026-04-19 ──

    def test_whatsapp_mix_por_producto_pereira(self):
        plan = internal_agent_ops._infer_universal_bi_plan(
            "Muéstrame el mix por producto en Pereira",
            None,
            None,
        )
        self.assertEqual(plan["kind"], "semantic")
        self.assertEqual(plan["analysis"], "participacion")
        self.assertEqual(plan["dimension"], "producto")

    def test_whatsapp_crecimiento_por_linea_vs_anio(self):
        plan = internal_agent_ops._infer_universal_bi_plan(
            "Dime el crecimiento por línea este mes vs año anterior",
            None,
            None,
        )
        self.assertEqual(plan["kind"], "semantic")
        self.assertEqual(plan["analysis"], "crecimiento")
        self.assertEqual(plan["dimension"], "marca")

    def test_whatsapp_caida_frecuencia_vendedores(self):
        plan = internal_agent_ops._infer_universal_bi_plan(
            "Qué vendedores muestran mayor caída de frecuencia",
            None,
            None,
        )
        self.assertEqual(plan["kind"], "semantic")
        self.assertEqual(plan["analysis"], "caida_frecuencia")

    def test_whatsapp_concentracion_cartera_por_cliente(self):
        plan = internal_agent_ops._infer_universal_bi_plan(
            "Cuál es la concentración de cartera por cliente",
            None,
            None,
        )
        self.assertEqual(plan["kind"], "semantic")
        self.assertEqual(plan["analysis"], "concentracion_cartera")
        self.assertEqual(plan["dimension"], "cliente")

    def test_whatsapp_oportunidades_por_sede(self):
        plan = internal_agent_ops._infer_universal_bi_plan(
            "Dónde están las mayores oportunidades por sede",
            None,
            None,
        )
        self.assertEqual(plan["kind"], "semantic")
        self.assertEqual(plan["analysis"], "oportunidades_dimension")
        self.assertEqual(plan["dimension"], "tienda")

    def test_whatsapp_lineas_creciendo_cayendo(self):
        plan = internal_agent_ops._infer_universal_bi_plan(
            "Qué líneas vienen creciendo y cuáles cayendo",
            None,
            None,
        )
        self.assertEqual(plan["kind"], "semantic")
        self.assertEqual(plan["analysis"], "crecimiento")
        self.assertEqual(plan["dimension"], "marca")

    def test_whatsapp_participacion_por_linea(self):
        plan = internal_agent_ops._infer_universal_bi_plan(
            "Cuál es la participación por línea este mes",
            None,
            None,
        )
        self.assertEqual(plan["kind"], "semantic")
        self.assertEqual(plan["analysis"], "participacion")
        self.assertEqual(plan["dimension"], "marca")

    def test_whatsapp_mostradores_creciendo_decreciendo(self):
        plan = internal_agent_ops._infer_universal_bi_plan(
            "los mostradores vienen creciendo o decreciendo",
            None,
            None,
        )
        self.assertEqual(plan["kind"], "semantic")
        self.assertEqual(plan["analysis"], "crecimiento")
        self.assertEqual(plan["dimension"], "vendedor")
        self.assertEqual(plan["channel"], "mostrador")

    def test_whatsapp_mostradores_ventas(self):
        plan = internal_agent_ops._infer_universal_bi_plan(
            "cómo van las ventas de mostrador este mes",
            None,
            None,
        )
        self.assertEqual(plan["kind"], "sales")
        self.assertEqual(plan["dimension"], "vendedor")
        self.assertEqual(plan["channel"], "mostrador")

    def test_whatsapp_vendedores_no_channel(self):
        plan = internal_agent_ops._infer_universal_bi_plan(
            "top 5 vendedores este mes",
            None,
            None,
        )
        self.assertEqual(plan["kind"], "sales")
        self.assertEqual(plan["dimension"], "vendedor")
        self.assertIsNone(plan.get("channel"))

    def test_detect_internal_query_intent_flags_sales_and_projection_questions(self):
        self.assertEqual(
            main.detect_internal_query_intent("Las ventas de Pereira cuáles son y qué proyección tiene para cierre de abril"),
            "consulta_bi",
        )
        self.assertEqual(
            main.detect_internal_query_intent("Cuánto lleva en ventas OLAYA"),
            "consulta_bi",
        )
        self.assertEqual(
            main.detect_internal_query_intent("La empresa cuanto lleva en ventas en abril"),
            "consulta_bi",
        )

    def test_detect_internal_query_intent_does_not_hijack_customer_price_question(self):
        self.assertIsNone(main.detect_internal_query_intent("Cuánto vale el viniltex en Pereira"))

    def test_handle_internal_whatsapp_message_requests_internal_login_for_sales_bi_without_session(self):
        with mock.patch.dict(os.environ, {"AGENT_PROFILE": "internal"}, clear=False):
            with mock.patch.object(main, "find_employee_record_by_phone", return_value=None):
                response = main.handle_internal_whatsapp_message(
                    "La empresa cuanto lleva en ventas en abril",
                    {"telefono_e164": "+573001112233"},
                    {},
                )

        self.assertIsNotNone(response)
        self.assertEqual(response["intent"], "internal_auth_required")
        self.assertIn("Para consultas internas primero debes iniciar sesión", response["response_text"])

    def test_handle_internal_whatsapp_message_keeps_bi_queries_for_internal_llm_after_auth(self):
        with mock.patch.dict(os.environ, {"AGENT_PROFILE": "internal"}, clear=False):
            with mock.patch.object(
                main,
                "resolve_internal_session",
                return_value={"id": 7, "role": "administrador", "session_expires_at": "2099-01-01T00:00:00Z"},
            ):
                with mock.patch.object(main, "build_internal_auth_context", return_value={"token": "abc", "role": "administrador"}):
                    with mock.patch.object(main, "find_employee_record_by_phone", return_value=None):
                        response = main.handle_internal_whatsapp_message(
                            "Cuánto lleva en ventas Pereira",
                            {"telefono_e164": "+573001112233"},
                            {"internal_auth": {"token": "abc"}},
                        )

        self.assertIsNone(response)

    def test_bicomponent_guard_skips_internal_indicator_turns(self):
        assistant_message = mock.Mock()
        assistant_message.content = (
            "Baja rotación: 20 referencias. - INTERGARD 740 stock 2 en Manizales."
        )
        tool_calls_made = [
            {
                "name": "consultar_indicadores_internos",
                "args": {"tipo_consulta": "inventario_baja_rotacion", "almacen": "157", "limite": 20},
                "result": "Baja rotación: 20 referencias y $49,676,072 comprometidos en inventario.",
            }
        ]

        guarded = agent_v3._guardia_bicomponente(
            assistant_message,
            messages=[],
            tool_calls_made=tool_calls_made,
            context={"conversation_id": 148},
            conversation_context={"internal_auth": {"role": "administrador"}},
            m=mock.Mock(),
        )

        self.assertIs(guarded, assistant_message)


if __name__ == "__main__":
    unittest.main()