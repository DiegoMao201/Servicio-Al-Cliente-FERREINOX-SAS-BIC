"""Tests E2E Phase E1 — RBAC + Dynamic Tool Binding + Internal Tools.

Cobertura:

  * **RBAC classifier**: teléfono interno → INTERNAL, otro → EXTERNAL.
  * **Dynamic tool binding**: build_tools_for_session filtra por whitelist.
  * **Data leak prevention (EXTERNAL)**: el LLM mockeado intenta llamar
    tools internas (check_inventory_bi / get_cartera_status) y la app
    NO ejecuta el handler — RBACDeniedError o whitelist deny.
  * **Flujo INTERNAL completo**: get_cartera_status (COP) → submit_order
    contra inventario mockeado → pedido aceptado con total en COP.
  * **submit_order rechazo parcial**: si una sola línea es inválida,
    todo el pedido se rechaza atómicamente.
"""

from __future__ import annotations

import os
import sys
import unittest
from unittest import mock

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if os.path.join(ROOT, "backend") not in sys.path:
    sys.path.insert(0, os.path.join(ROOT, "backend"))

from agent_prompt_ferreamigo import (  # noqa: E402
    FERREAMIGO_INTERNAL_ADDENDUM,
    build_ferreamigo_system_prompt,
)
from bi_handlers import (  # noqa: E402
    RBACDeniedError,
    handle_check_inventory_bi,
    handle_get_cartera_status,
    handle_submit_order,
)
from llm_client import build_llm_runtime_kwargs  # noqa: E402
from rbac import (  # noqa: E402
    _EXTERNAL_TOOL_WHITELIST,
    _INTERNAL_TOOL_WHITELIST,
    build_tools_for_session,
    is_tool_allowed_for_session,
)
from session_context import (  # noqa: E402
    SessionContext,
    UserRole,
    classify_session_from_phone,
)


# ─────────────────────────────────────────────────────────────────────────
# Helpers — mocks deterministas
# ─────────────────────────────────────────────────────────────────────────


def _normalize_phone(phone):
    """Mock minimalista: deja números E.164 intactos, devuelve None si vacío."""
    if not phone:
        return None
    return phone.strip()


def _internal_lookup_factory(internal_phones: dict[str, dict]):
    """Factoría: dado un dict {phone_e164: user_row} devuelve el lookup_fn."""
    def _lookup(phone_e164):
        return internal_phones.get(phone_e164)
    return _lookup


_FAKE_INVENTORY = {
    "VINILTEX-G-BLANCO": {
        "sku": "VINILTEX-G-BLANCO",
        "descripcion": "Viniltex Galón Blanco 1501",
        "stock_total": 24.0,
        "stock_por_bodega": [
            {"bodega": "PRINCIPAL", "cantidad": 18.0},
            {"bodega": "OPALO", "cantidad": 6.0},
        ],
        "precio_lista": 95000.0,
    },
    "INTERSEAL-670HS-A": {
        "sku": "INTERSEAL-670HS-A",
        "descripcion": "Interseal 670HS Parte A",
        "stock_total": 4.0,
        "stock_por_bodega": [{"bodega": "PRINCIPAL", "cantidad": 4.0}],
        "precio_lista": 320000.0,
    },
    "OUT-OF-STOCK-SKU": {
        "sku": "OUT-OF-STOCK-SKU",
        "descripcion": "Producto Sin Stock",
        "stock_total": 0.0,
        "stock_por_bodega": [],
        "precio_lista": 50000.0,
    },
}


def _inventory_lookup_fn(sku, bodega=None):
    return _FAKE_INVENTORY.get(sku)


_FAKE_CARTERA = {
    "900123456": {
        "cliente_codigo": "C-001",
        "cliente_nombre": "Constructora Andina SAS",
        "saldo_pendiente": 1_580_000.0,
        "dias_mora_max": 12,
        "facturas_vencidas": 2,
    }
}


def _cartera_lookup_fn(nit_o_cedula):
    return _FAKE_CARTERA.get(nit_o_cedula)


def _persist_order_fn(payload):
    return f"PED-{payload['cliente_codigo']}-001"


# ─────────────────────────────────────────────────────────────────────────
# Sesiones reutilizables
# ─────────────────────────────────────────────────────────────────────────


_INTERNAL_SESSION = SessionContext(
    role=UserRole.INTERNAL,
    phone_e164="+573001112233",
    internal_user_id=42,
    internal_username="dgarcia",
    internal_full_name="Diego García",
    internal_scopes=("bi.read", "orders.create"),
)
_EXTERNAL_SESSION = SessionContext(
    role=UserRole.EXTERNAL,
    phone_e164="+573009998877",
)


# ─────────────────────────────────────────────────────────────────────────
# 1. RBAC classifier
# ─────────────────────────────────────────────────────────────────────────


class RBACClassifierTests(unittest.TestCase):
    def test_known_internal_phone_classifies_as_internal(self):
        ctx = classify_session_from_phone(
            "+573001112233",
            normalize_phone=_normalize_phone,
            fetch_internal_user_by_phone=_internal_lookup_factory(
                {
                    "+573001112233": {
                        "id": 42,
                        "username": "dgarcia",
                        "full_name": "Diego García",
                        "is_active": True,
                        "scopes": ["bi.read", "orders.create"],
                    }
                }
            ),
        )
        self.assertEqual(ctx.role, UserRole.INTERNAL)
        self.assertTrue(ctx.is_internal)
        self.assertEqual(ctx.internal_user_id, 42)
        self.assertEqual(ctx.internal_scopes, ("bi.read", "orders.create"))

    def test_unknown_phone_defaults_to_external(self):
        ctx = classify_session_from_phone(
            "+573009998877",
            normalize_phone=_normalize_phone,
            fetch_internal_user_by_phone=_internal_lookup_factory({}),
        )
        self.assertEqual(ctx.role, UserRole.EXTERNAL)
        self.assertFalse(ctx.is_internal)
        self.assertIsNone(ctx.internal_user_id)

    def test_inactive_internal_user_treated_as_external(self):
        ctx = classify_session_from_phone(
            "+573001112233",
            normalize_phone=_normalize_phone,
            fetch_internal_user_by_phone=_internal_lookup_factory(
                {
                    "+573001112233": {
                        "id": 42,
                        "username": "dgarcia",
                        "is_active": False,
                        "scopes": [],
                    }
                }
            ),
        )
        self.assertEqual(ctx.role, UserRole.EXTERNAL)


# ─────────────────────────────────────────────────────────────────────────
# 2. Dynamic Tool Binding
# ─────────────────────────────────────────────────────────────────────────


class DynamicToolBindingTests(unittest.TestCase):
    def test_external_session_does_not_see_internal_tools(self):
        tools = build_tools_for_session(_EXTERNAL_SESSION)
        names = {t["function"]["name"] for t in tools}
        # Las internas NO deben aparecer en el array enviado al LLM.
        forbidden = {
            "check_inventory_bi",
            "get_cartera_status",
            "submit_order",
            "consultar_inventario",
            "consultar_inventario_lote",
            "consultar_bi_universal",
            "consultar_ventas_internas",
            "consultar_indicadores_internos",
            "solicitar_traslado_interno",
            "confirmar_pedido_y_generar_pdf",
        }
        self.assertEqual(
            forbidden & names,
            set(),
            f"Tools internas filtradas a sesión EXTERNAL: {forbidden & names}",
        )
        # Las whitelisted SÍ deben estar.
        self.assertTrue(_EXTERNAL_TOOL_WHITELIST.issubset(names))

    def test_internal_session_sees_internal_tools(self):
        tools = build_tools_for_session(_INTERNAL_SESSION)
        names = {t["function"]["name"] for t in tools}
        for required in ("check_inventory_bi", "get_cartera_status", "submit_order"):
            self.assertIn(required, names)

    def test_is_tool_allowed_double_defense_guard(self):
        self.assertTrue(is_tool_allowed_for_session("check_inventory_bi", _INTERNAL_SESSION))
        self.assertFalse(is_tool_allowed_for_session("check_inventory_bi", _EXTERNAL_SESSION))
        self.assertTrue(is_tool_allowed_for_session("consultar_conocimiento_tecnico", _EXTERNAL_SESSION))
        self.assertFalse(is_tool_allowed_for_session("submit_order", _EXTERNAL_SESSION))

    def test_runtime_kwargs_inject_internal_addendum_only_for_internal(self):
        ext_kwargs = build_llm_runtime_kwargs(
            _EXTERNAL_SESSION,
            base_messages=[{"role": "user", "content": "hola"}],
        )
        int_kwargs = build_llm_runtime_kwargs(
            _INTERNAL_SESSION,
            base_messages=[{"role": "user", "content": "hola"}],
        )
        # System prompt EXTERNO no debe mencionar las tools internas.
        ext_system = ext_kwargs["messages"][0]["content"]
        self.assertNotIn("check_inventory_bi", ext_system)
        self.assertNotIn("submit_order", ext_system)
        self.assertNotIn("EXTENSIÓN MODO INTERNO", ext_system)
        # System prompt INTERNO sí.
        int_system = int_kwargs["messages"][0]["content"]
        self.assertIn("check_inventory_bi", int_system)
        self.assertIn("submit_order", int_system)
        self.assertIn("get_cartera_status", int_system)
        self.assertIn(FERREAMIGO_INTERNAL_ADDENDUM.strip()[:60], int_system)
        # Y los arrays de tools también divergen.
        ext_tool_names = {t["function"]["name"] for t in ext_kwargs.get("tools", [])}
        int_tool_names = {t["function"]["name"] for t in int_kwargs.get("tools", [])}
        self.assertNotIn("submit_order", ext_tool_names)
        self.assertIn("submit_order", int_tool_names)


# ─────────────────────────────────────────────────────────────────────────
# 3. Test del Ácido — fuga de datos
# ─────────────────────────────────────────────────────────────────────────


class _MockLLMRouter:
    """Simula al LLM intentando llamar tools (legítimas o filtradas).

    Comportamiento: dado un dict `desired_tool_call`, simula que el LLM
    devolvió esa intención. El dispatcher debe verificar RBAC ANTES de
    invocar el handler.
    """

    def __init__(self, session: SessionContext):
        self.session = session
        self.executed_tools: list[str] = []
        self.denied_tools: list[str] = []

    def dispatch(self, tool_name: str, args: dict, *, handler_fn, **handler_kwargs):
        # Defense in depth #1: RBAC whitelist.
        if not is_tool_allowed_for_session(tool_name, self.session):
            self.denied_tools.append(tool_name)
            return {"error": "tool_not_available_for_role"}
        # Defense in depth #2: handler interno re-valida con _require_internal.
        try:
            result = handler_fn(args, self.session, **handler_kwargs)
        except RBACDeniedError as exc:
            self.denied_tools.append(tool_name)
            return {"error": str(exc)}
        self.executed_tools.append(tool_name)
        return result


class DataLeakPreventionTests(unittest.TestCase):
    """EXTERNAL intenta acceder a tools internas: deny en 2 capas."""

    def test_external_attempt_to_call_get_cartera_is_blocked_at_whitelist(self):
        router = _MockLLMRouter(_EXTERNAL_SESSION)
        result = router.dispatch(
            "get_cartera_status",
            {"nit_o_cedula": "900123456"},
            handler_fn=handle_get_cartera_status,
            cartera_lookup_fn=_cartera_lookup_fn,
        )
        self.assertEqual(result, {"error": "tool_not_available_for_role"})
        self.assertEqual(router.executed_tools, [])
        self.assertIn("get_cartera_status", router.denied_tools)

    def test_external_attempt_to_call_check_inventory_bi_is_blocked(self):
        router = _MockLLMRouter(_EXTERNAL_SESSION)
        result = router.dispatch(
            "check_inventory_bi",
            {"sku": "VINILTEX-G-BLANCO"},
            handler_fn=handle_check_inventory_bi,
            inventory_lookup_fn=_inventory_lookup_fn,
        )
        self.assertEqual(result, {"error": "tool_not_available_for_role"})
        self.assertNotIn("check_inventory_bi", router.executed_tools)

    def test_handler_called_directly_with_external_session_raises_rbac(self):
        """Defensa #2: incluso si alguien bypassa el dispatcher, el
        handler interno re-valida y eleva RBACDeniedError."""
        with self.assertRaises(RBACDeniedError):
            handle_get_cartera_status(
                {"nit_o_cedula": "900123456"},
                _EXTERNAL_SESSION,
                cartera_lookup_fn=_cartera_lookup_fn,
            )
        with self.assertRaises(RBACDeniedError):
            handle_submit_order(
                {
                    "cliente_codigo": "C-001",
                    "lineas": [{"sku": "VINILTEX-G-BLANCO", "cantidad": 1}],
                },
                _EXTERNAL_SESSION,
                inventory_lookup_fn=_inventory_lookup_fn,
                persist_order_fn=_persist_order_fn,
            )

    def test_external_session_tools_array_is_safe_payload(self):
        """Auditoría: el JSON de tools enviado al LLM para EXTERNAL no
        contiene strings sensibles (BI, cartera de terceros, pedido)."""
        import json as _json
        tools = build_tools_for_session(_EXTERNAL_SESSION)
        payload = _json.dumps(tools, ensure_ascii=False).lower()
        for forbidden_token in (
            "check_inventory_bi",
            "get_cartera_status",
            "submit_order",
            "consultar_bi_universal",
            "[internal only]",
        ):
            self.assertNotIn(
                forbidden_token,
                payload,
                f"Token sensible '{forbidden_token}' filtrado al payload EXTERNAL",
            )


# ─────────────────────────────────────────────────────────────────────────
# 4. Flujo INTERNAL completo
# ─────────────────────────────────────────────────────────────────────────


class InternalFullFlowTests(unittest.TestCase):
    def test_internal_advisor_consults_cartera_in_cop(self):
        router = _MockLLMRouter(_INTERNAL_SESSION)
        result = router.dispatch(
            "get_cartera_status",
            {"nit_o_cedula": "900123456"},
            handler_fn=handle_get_cartera_status,
            cartera_lookup_fn=_cartera_lookup_fn,
        )
        # Debe ser el output Pydantic del handler interno.
        self.assertTrue(result.found)
        self.assertEqual(result.moneda, "COP")
        self.assertEqual(result.saldo_pendiente, 1_580_000.0)
        self.assertEqual(result.dias_mora_max, 12)
        self.assertEqual(result.facturas_vencidas, 2)
        self.assertEqual(router.executed_tools, ["get_cartera_status"])

    def test_internal_advisor_submits_valid_order(self):
        router = _MockLLMRouter(_INTERNAL_SESSION)
        result = router.dispatch(
            "submit_order",
            {
                "cliente_codigo": "C-001",
                "bodega": "PRINCIPAL",
                "lineas": [
                    {"sku": "VINILTEX-G-BLANCO", "cantidad": 5},
                    {"sku": "INTERSEAL-670HS-A", "cantidad": 2},
                ],
            },
            handler_fn=handle_submit_order,
            inventory_lookup_fn=_inventory_lookup_fn,
            persist_order_fn=_persist_order_fn,
        )
        self.assertTrue(result.aceptado)
        self.assertEqual(result.moneda, "COP")
        self.assertEqual(len(result.lineas_confirmadas), 2)
        self.assertEqual(result.lineas_rechazadas, [])
        # Total esperado: 5*95000 + 2*320000 = 475000 + 640000 = 1_115_000 COP
        self.assertEqual(result.total, 1_115_000.0)
        self.assertEqual(result.pedido_id, "PED-C-001-001")
        self.assertEqual(router.executed_tools, ["submit_order"])

    def test_submit_order_rejects_atomically_on_partial_failure(self):
        """Si UNA línea es inválida, TODO el pedido se rechaza —
        no se aceptan pedidos parciales."""
        router = _MockLLMRouter(_INTERNAL_SESSION)
        result = router.dispatch(
            "submit_order",
            {
                "cliente_codigo": "C-001",
                "lineas": [
                    {"sku": "VINILTEX-G-BLANCO", "cantidad": 5},   # ok
                    {"sku": "OUT-OF-STOCK-SKU", "cantidad": 1},     # falla stock
                    {"sku": "FAKE-SKU-INVENTED", "cantidad": 1},    # falla SKU
                ],
            },
            handler_fn=handle_submit_order,
            inventory_lookup_fn=_inventory_lookup_fn,
            persist_order_fn=_persist_order_fn,
        )
        self.assertFalse(result.aceptado)
        self.assertIsNone(result.pedido_id)
        self.assertEqual(len(result.lineas_rechazadas), 2)
        motivos = {r.motivo for r in result.lineas_rechazadas}
        self.assertIn("stock_insuficiente", motivos)
        self.assertIn("sku_no_encontrado", motivos)

    def test_check_inventory_bi_returns_cop_and_real_columns_only(self):
        result = handle_check_inventory_bi(
            {"sku": "VINILTEX-G-BLANCO"},
            _INTERNAL_SESSION,
            inventory_lookup_fn=_inventory_lookup_fn,
        )
        self.assertTrue(result.found)
        self.assertEqual(result.moneda, "COP")
        self.assertEqual(result.stock_total, 24.0)
        self.assertEqual(len(result.stock_por_bodega), 2)
        self.assertEqual(result.precio_lista, 95000.0)
        # Pydantic strict: no hay extras inventados.
        dumped = result.model_dump()
        self.assertEqual(
            set(dumped.keys()),
            {
                "sku", "descripcion", "found", "stock_total",
                "stock_por_bodega", "precio_lista", "moneda",
            },
        )

    def test_check_inventory_bi_not_found_returns_zeros_no_invention(self):
        result = handle_check_inventory_bi(
            {"sku": "TOTALLY-MADE-UP-XYZ"},
            _INTERNAL_SESSION,
            inventory_lookup_fn=_inventory_lookup_fn,
        )
        self.assertFalse(result.found)
        self.assertEqual(result.stock_total, 0.0)
        self.assertEqual(result.stock_por_bodega, [])
        self.assertIsNone(result.precio_lista)
        self.assertEqual(result.descripcion, "(no encontrado)")


if __name__ == "__main__":
    unittest.main()
