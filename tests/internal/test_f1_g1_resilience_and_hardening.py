"""Tests Phase F1 (Observability/Resilience) + G1 (Hardening Output).

Cobertura:

  * **F1.1 Webhook async**: el endpoint responde 200 con `status="received"`
    inmediatamente y delega procesamiento a BackgroundTasks.
  * **F1.2 Idempotencia**: mismo `message_id` enviado 2 veces → segundo
    request retorna `status="duplicate_ignored"` y el procesamiento NO
    corre dos veces.
  * **F1.3 Telemetría**: `AuditLogger.record_agent_turn` invoca el INSERT
    con los campos correctos (mockeando engine).
  * **F1.4 Graceful degradation**: si `_process_whatsapp_payload` lanza
    excepción, `send_whatsapp_text_message` recibe el mensaje fallback.
  * **G1 Sanitizer**: bloques JSON / tags <tool_call> / pure JSON →
    eliminados o reemplazados por mensaje seguro.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import unittest
from unittest import mock

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if os.path.join(ROOT, "backend") not in sys.path:
    sys.path.insert(0, os.path.join(ROOT, "backend"))

from agent_response_sanitizer import (  # noqa: E402
    GRACEFUL_DEGRADATION_MESSAGE,
    SAFE_FALLBACK_AFTER_LEAK,
    SAFE_FALLBACK_EMPTY,
    sanitize_agent_response,
)
from idempotency import (  # noqa: E402
    WebhookIdempotencyCache,
    extract_inbound_message_ids,
    webhook_idempotency_cache,
)
from telemetry import (  # noqa: E402
    AGENT_AUDIT_LOGS_DDL,
    AgentAuditEntry,
    AuditLogger,
    build_entry_from_ai_result,
)


# ─────────────────────────────────────────────────────────────────────────
# 1. F1.2 — Idempotencia ligera
# ─────────────────────────────────────────────────────────────────────────


class IdempotencyCacheTests(unittest.TestCase):
    def test_first_call_not_processed(self):
        c = WebhookIdempotencyCache(ttl_seconds=60)
        self.assertFalse(c.is_processed("wamid.AAA"))

    def test_mark_then_processed(self):
        c = WebhookIdempotencyCache(ttl_seconds=60)
        c.mark_processing("wamid.AAA")
        self.assertTrue(c.is_processed("wamid.AAA"))
        # Otro id distinto sigue libre.
        self.assertFalse(c.is_processed("wamid.BBB"))

    def test_filter_new_drops_already_seen(self):
        c = WebhookIdempotencyCache(ttl_seconds=60)
        c.mark_processing("wamid.AAA")
        new_ids = c.filter_new(["wamid.AAA", "wamid.BBB", None, ""])
        self.assertEqual(new_ids, ["wamid.BBB"])

    def test_ttl_expiration(self):
        c = WebhookIdempotencyCache(ttl_seconds=1)
        c.mark_processing("wamid.AAA")
        # Forzar expiración manipulando el timestamp interno.
        c._store["wamid.AAA"] = c._store["wamid.AAA"] - 5
        self.assertFalse(c.is_processed("wamid.AAA"))

    def test_extract_message_ids_from_meta_payload(self):
        payload = {
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "messages": [
                                    {"id": "wamid.111", "from": "573001112233"},
                                    {"id": "wamid.222", "from": "573001112233"},
                                ]
                            }
                        }
                    ]
                }
            ]
        }
        self.assertEqual(extract_inbound_message_ids(payload), ["wamid.111", "wamid.222"])

    def test_extract_handles_empty_payload(self):
        self.assertEqual(extract_inbound_message_ids({}), [])
        self.assertEqual(extract_inbound_message_ids({"entry": []}), [])

    def test_global_singleton_instance_exists(self):
        self.assertIsInstance(webhook_idempotency_cache, WebhookIdempotencyCache)


# ─────────────────────────────────────────────────────────────────────────
# 2. G1 — Sanitizer del output del agente
# ─────────────────────────────────────────────────────────────────────────


class AgentResponseSanitizerTests(unittest.TestCase):
    def test_plain_text_unchanged(self):
        text = "Hola Diego, te recomiendo aplicar Viniltex blanco galón."
        self.assertEqual(sanitize_agent_response(text), text)

    def test_pure_json_replaced_by_safe_fallback(self):
        text = '{"tool": "consultar_inventario", "args": {"sku": "VINILTEX"}}'
        result = sanitize_agent_response(text)
        self.assertEqual(result, SAFE_FALLBACK_AFTER_LEAK)
        # CRÍTICO: ningún caracter del JSON original sobrevive.
        self.assertNotIn("tool", result)
        self.assertNotIn("VINILTEX", result)

    def test_pure_json_array_replaced(self):
        text = '[{"name":"x"},{"name":"y"}]'
        result = sanitize_agent_response(text)
        self.assertEqual(result, SAFE_FALLBACK_AFTER_LEAK)

    def test_fenced_json_block_stripped(self):
        text = (
            "Aquí está el resultado:\n"
            "```json\n"
            '{"sku":"VINILTEX","stock":24}\n'
            "```\n"
            "El producto está disponible."
        )
        result = sanitize_agent_response(text)
        self.assertNotIn("```", result)
        self.assertNotIn("VINILTEX", result)
        self.assertIn("disponible", result)

    def test_analisis_block_stripped(self):
        text = (
            "<analisis>El usuario pide pintura para humedad.</analisis>\n"
            "Te recomiendo Sikatop antihumedad para esa pared."
        )
        result = sanitize_agent_response(text)
        self.assertNotIn("<analisis>", result)
        self.assertNotIn("usuario pide", result)
        self.assertIn("Sikatop", result)

    def test_tool_call_tag_stripped(self):
        text = (
            "<tool_call>{\"name\":\"x\"}</tool_call>\n"
            "Procesando tu solicitud..."
        )
        result = sanitize_agent_response(text)
        self.assertNotIn("<tool_call>", result)
        self.assertNotIn('"name"', result)

    def test_empty_text_returns_safe_fallback(self):
        self.assertEqual(sanitize_agent_response(None), SAFE_FALLBACK_EMPTY)
        self.assertEqual(sanitize_agent_response(""), SAFE_FALLBACK_EMPTY)
        self.assertEqual(sanitize_agent_response("   \n\n"), SAFE_FALLBACK_EMPTY)

    def test_text_after_stripping_only_blocks_returns_fallback(self):
        text = "<analisis>solo análisis</analisis>"
        result = sanitize_agent_response(text)
        self.assertEqual(result, SAFE_FALLBACK_EMPTY)

    def test_mixed_content_keeps_natural_prose(self):
        text = (
            "Para tu humedad te recomiendo Pintucoat Acrílico.\n"
            "```json\n{\"interno\":true}\n```\n"
            "Rinde 30 m² por galón según ficha técnica."
        )
        result = sanitize_agent_response(text)
        self.assertIn("Pintucoat", result)
        self.assertIn("30 m²", result)
        self.assertNotIn("```", result)
        self.assertNotIn("interno", result)


# ─────────────────────────────────────────────────────────────────────────
# 3. F1.3 — AuditLogger / Telemetry
# ─────────────────────────────────────────────────────────────────────────


class AuditLoggerTests(unittest.TestCase):
    def _build_mock_engine(self):
        """Crea un engine mock con .begin() context manager y .execute()."""
        captured: dict = {"sql": [], "params": []}

        class _MockResult:
            def fetchone(self_inner):
                return (101,)

        class _MockConn:
            def execute(self_inner, sql, params=None):
                captured["sql"].append(str(sql))
                captured["params"].append(params or {})
                return _MockResult()

        class _MockBegin:
            def __enter__(self_inner):
                return _MockConn()
            def __exit__(self_inner, *args):
                return False

        engine = mock.MagicMock()
        engine.begin = mock.MagicMock(return_value=_MockBegin())
        return engine, captured

    def test_audit_entry_pydantic_strict(self):
        entry = AgentAuditEntry(
            session_id="conv-42",
            conversation_id=42,
            role="external",
            phone_e164="+573001112233",
            user_message="¿Cuánto cuesta el viniltex blanco?",
            response_text="El Viniltex Galón Blanco está disponible.",
            intent="consulta_inventario",
            tools_invoked=[{"name": "consultar_inventario"}],
            tokens_total=420,
            duration_ms=1850,
        )
        params = entry.to_db_params()
        # JSONB se serializa como string.
        self.assertIsInstance(params["tools_invoked"], str)
        loaded = json.loads(params["tools_invoked"])
        self.assertEqual(loaded[0]["name"], "consultar_inventario")
        self.assertEqual(params["role"], "external")

    def test_audit_logger_writes_insert_and_returns_id(self):
        engine, captured = self._build_mock_engine()
        log = AuditLogger(engine_provider=lambda: engine)
        entry = AgentAuditEntry(
            role="internal",
            conversation_id=99,
            response_text="ok",
            tools_invoked=[{"name": "check_inventory_bi"}],
        )
        new_id = log.record_agent_turn(entry)
        self.assertEqual(new_id, 101)
        # Se ejecutó al menos el DDL + el INSERT.
        joined_sql = "\n".join(captured["sql"])
        self.assertIn("agent_audit_logs", joined_sql)
        self.assertIn("INSERT INTO public.agent_audit_logs", joined_sql)
        # El INSERT recibió los params correctos.
        insert_params = captured["params"][-1]
        self.assertEqual(insert_params["role"], "internal")
        self.assertEqual(insert_params["conversation_id"], 99)
        self.assertIn("check_inventory_bi", insert_params["tools_invoked"])

    def test_audit_logger_silences_db_errors(self):
        def _broken_engine():
            raise RuntimeError("DB caída")

        log = AuditLogger(engine_provider=_broken_engine)
        # No debe lanzar — la auditoría NUNCA bloquea la conversación.
        result = log.record_agent_turn(
            AgentAuditEntry(role="external", response_text="hola")
        )
        self.assertIsNone(result)

    def test_build_entry_from_ai_result_extracts_safety_score(self):
        ai_result = {
            "response_text": "Te recomiendo Pintucoat.",
            "intent": "asesoria_tecnica",
            "tool_calls": [
                {
                    "name": "consultar_conocimiento_tecnico",
                    "args": {"pregunta": "humedad"},
                    "result": json.dumps({"safety_score": 0.87, "found": True}),
                }
            ],
            "confidence": {"level": "alta"},
        }
        entry = build_entry_from_ai_result(
            ai_result=ai_result,
            role="external",
            phone_e164="+573001112233",
            conversation_id=42,
            user_message="tengo humedad",
            duration_ms=1500,
        )
        self.assertEqual(entry.role, "external")
        self.assertEqual(entry.intent, "asesoria_tecnica")
        self.assertEqual(entry.safety_score, 0.87)
        self.assertEqual(entry.confidence_level, "alta")
        self.assertEqual(entry.duration_ms, 1500)
        self.assertEqual(len(entry.tools_invoked), 1)
        self.assertEqual(entry.tools_invoked[0]["name"], "consultar_conocimiento_tecnico")


# ─────────────────────────────────────────────────────────────────────────
# 4. F1.1 + F1.4 — Webhook async + graceful degradation
#
#   Estos tests usan FastAPI TestClient con `main.app`. Mockeamos las
#   funciones DB y de envío a WhatsApp para que no toquen recursos reales.
# ─────────────────────────────────────────────────────────────────────────


class WebhookAsyncEndpointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Limpiar la cache global para aislar tests entre corridas.
        webhook_idempotency_cache.clear()

    def setUp(self):
        webhook_idempotency_cache.clear()

    def _build_meta_payload(self, message_id: str = "wamid.TEST_E1_001",
                            from_number: str = "573001112233",
                            text: str = "hola"):
        return {
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "contacts": [
                                    {"profile": {"name": "Diego Test"}, "wa_id": from_number}
                                ],
                                "messages": [
                                    {
                                        "id": message_id,
                                        "from": from_number,
                                        "type": "text",
                                        "text": {"body": text},
                                    }
                                ],
                            }
                        }
                    ]
                }
            ]
        }

    def test_webhook_returns_200_with_received_status_immediately(self):
        # Importar perezosamente para evitar startup con DB real.
        from fastapi.testclient import TestClient
        import main as main_module

        # Mock de _process_whatsapp_payload para no tocar DB/LLM/WhatsApp.
        async def _noop(payload):
            await asyncio.sleep(0)
            return None

        with mock.patch.object(main_module, "_process_whatsapp_payload", side_effect=_noop):
            client = TestClient(main_module.app)
            payload = self._build_meta_payload(message_id="wamid.RECEIVED_001")
            resp = client.post("/webhooks/whatsapp", json=payload)

        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["status"], "received")
        self.assertIn("wamid.RECEIVED_001", body["queued_message_ids"])

    def test_webhook_idempotency_drops_duplicate(self):
        from fastapi.testclient import TestClient
        import main as main_module

        async def _noop(payload):
            await asyncio.sleep(0)
            return None

        with mock.patch.object(main_module, "_process_whatsapp_payload", side_effect=_noop) as mocked:
            client = TestClient(main_module.app)
            payload = self._build_meta_payload(message_id="wamid.DUPE_001")
            r1 = client.post("/webhooks/whatsapp", json=payload)
            r2 = client.post("/webhooks/whatsapp", json=payload)

        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r1.json()["status"], "received")
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(r2.json()["status"], "duplicate_ignored")
        self.assertEqual(r2.json()["message_ids"], ["wamid.DUPE_001"])
        # El procesador asíncrono se invocó SOLO 1 vez (no dos).
        self.assertEqual(mocked.call_count, 1)

    def test_webhook_invalid_json_returns_ignored(self):
        from fastapi.testclient import TestClient
        import main as main_module

        client = TestClient(main_module.app)
        resp = client.post(
            "/webhooks/whatsapp",
            data="esto no es json",
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["status"], "ignored")

    def test_graceful_degradation_sends_fallback_on_processing_failure(self):
        """F1.4 — Si el procesador async lanza excepción, el cliente recibe
        el mensaje GRACEFUL_DEGRADATION_MESSAGE vía send_whatsapp_text_message."""
        import main as main_module

        async def _failing(payload):
            raise RuntimeError("LLM API timeout")

        sent_messages = []

        def _capture_send(phone, body):
            sent_messages.append((phone, body))
            return {"messages": [{"id": "fallback-001"}]}

        with mock.patch.object(main_module, "_process_whatsapp_payload", side_effect=_failing), \
             mock.patch.object(main_module, "send_whatsapp_text_message", side_effect=_capture_send):
            payload = self._build_meta_payload(message_id="wamid.FAIL_001",
                                               from_number="573009998877")
            asyncio.run(main_module._process_whatsapp_payload_with_resilience(payload))

        # Se envió el mensaje fallback al número del cliente.
        self.assertEqual(len(sent_messages), 1)
        phone, body = sent_messages[0]
        self.assertEqual(phone, "573009998877")
        self.assertEqual(body, GRACEFUL_DEGRADATION_MESSAGE)


if __name__ == "__main__":
    unittest.main()
