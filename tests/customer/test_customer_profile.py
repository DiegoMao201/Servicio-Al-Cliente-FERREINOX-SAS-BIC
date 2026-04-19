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


class CustomerAgentProfileTests(unittest.TestCase):
    def test_customer_profile_filters_tools_and_disables_transactional_flows(self):
        with mock.patch.dict(os.environ, {"AGENT_PROFILE": "customer"}, clear=False):
            runtime_config = agent_profiles.get_agent_runtime_config()

        tool_names = [tool["function"]["name"] for tool in runtime_config["tools"]]

        self.assertEqual(runtime_config["profile"], "customer")
        self.assertFalse(runtime_config["enable_order_pipeline"])
        self.assertFalse(runtime_config["enable_quote_pipeline"])
        self.assertFalse(runtime_config["enable_iva_guard"])
        self.assertEqual(
            tool_names,
            [
                "consultar_conocimiento_tecnico",
                "verificar_identidad",
                "consultar_cartera",
                "consultar_compras",
                "buscar_documento_tecnico",
                "radicar_reclamo",
            ],
        )

    def test_customer_profile_bypasses_internal_auth_flow(self):
        with mock.patch.dict(os.environ, {"AGENT_PROFILE": "customer"}, clear=False):
            response = main.handle_internal_whatsapp_message(
                "necesito revisar mi cartera",
                {"telefono_e164": "+573001112233"},
                {"internal_auth": {"token": "abc"}},
            )

        self.assertIsNone(response)


if __name__ == "__main__":
    unittest.main()