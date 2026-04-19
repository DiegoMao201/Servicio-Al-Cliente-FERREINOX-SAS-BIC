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
                "consultar_ventas_internas",
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


if __name__ == "__main__":
    unittest.main()