import os
import sys
import unittest
from unittest import mock


ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
BACKEND_DIR = os.path.join(ROOT_DIR, "backend")

sys.path.insert(0, BACKEND_DIR)

os.environ.setdefault("DATABASE_URL", "postgresql://postgres:x@localhost:5432/test")
os.environ.setdefault("OPENAI_API_KEY", "sk-test")

import main


class InternalLatencyConfigTests(unittest.TestCase):
    def test_internal_uses_faster_default_debounce(self):
        with mock.patch.dict(os.environ, {"AGENT_PROFILE": "internal"}, clear=False):
            with mock.patch.object(main, "get_agent_profile_name", return_value="internal"):
                debounce = main.get_effective_whatsapp_debounce_seconds()

        self.assertEqual(debounce, 0.8)

    def test_global_override_still_applies_for_internal(self):
        with mock.patch.dict(os.environ, {"AGENT_PROFILE": "internal", "WA_DEBOUNCE_SECONDS": "1.5"}, clear=False):
            with mock.patch.object(main, "get_agent_profile_name", return_value="internal"):
                debounce = main.get_effective_whatsapp_debounce_seconds()

        self.assertEqual(debounce, 1.5)

    def test_internal_specific_override_wins(self):
        with mock.patch.dict(os.environ, {"AGENT_PROFILE": "internal", "WA_DEBOUNCE_SECONDS": "1.5", "WA_DEBOUNCE_SECONDS_INTERNAL": "0.4"}, clear=False):
            with mock.patch.object(main, "get_agent_profile_name", return_value="internal"):
                debounce = main.get_effective_whatsapp_debounce_seconds()

        self.assertEqual(debounce, 0.4)


if __name__ == "__main__":
    unittest.main()