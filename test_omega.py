"""
TEST OMEGA — Stress Test Completo del Agente FERRO
====================================================
Prueba de flujo END-TO-END para escenarios complejos:
  1. Multi-intención (BI + CRM + B2B + RAG en un solo mensaje)
  2. Flujo de asesoría técnica completo (diagnóstico → sistema → cotización)
  3. Flujo B2B puro (lista de productos → cotización)
  4. Flujo CRM/BI puro (cartera, compras, ventas)
  5. Corrección transaccional (modificar cotización activa)
  6. Cambio de tema (cotización → nuevo proyecto)
  7. Guardias (pregunta técnica sin precios, asesoría sin cotización prematura)
  8. Finalización de flujo (despedida → cierre)
  9. Saludos y detección de intención
 10. Diagnóstico anti-repetición (no repetir preguntas ya respondidas)

Endpoint: POST /admin/agent-test
"""

import json
import os
import sys
import time
import re
import traceback
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

try:
    import requests
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests", "-q"])
    import requests

# ── Config ──
BACKEND_URL = os.environ.get("BACKEND_URL", "https://apicrm.datovatenexuspro.com")
ADMIN_KEY = os.environ.get("ADMIN_API_KEY", "ferreinox_admin_2024")
AGENT_URL = f"{BACKEND_URL.rstrip('/')}/admin/agent-test"
AGENT_TIMEOUT = 180  # higher for multi-tool scenarios
MAX_RETRIES = 2
PROMPT_VERSION = os.environ.get("PROMPT_VERSION", "")  # "v3" to force V3, "" for server default

# ── Colors for terminal ──
class C:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    END = "\033[0m"

# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _agent_request(payload, retries=MAX_RETRIES):
    """Send POST to /admin/agent-test with automatic retry."""
    last_error = None
    for attempt in range(1, retries + 1):
        try:
            t0 = time.time()
            resp = requests.post(
                AGENT_URL,
                headers={"x-admin-key": ADMIN_KEY, "Content-Type": "application/json"},
                json=payload,
                timeout=AGENT_TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()
            if data.get("error"):
                err_msg = str(data["error"])
                # 429 rate limit — retry after short wait
                if "rate_limit" in err_msg or "429" in err_msg:
                    last_error = RuntimeError(err_msg)
                    if attempt < retries:
                        wait = 8
                        print(f"  ⏳ Rate limit 429 (intento {attempt}/{retries}), reintentando en {wait}s...")
                        time.sleep(wait)
                    continue
                raise RuntimeError(err_msg)
            elapsed_ms = int((time.time() - t0) * 1000)
            return data.get("result") or {}, elapsed_ms
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            last_error = e
            if attempt < retries:
                wait = 5 * attempt
                print(f"  ⏳ Timeout (intento {attempt}/{retries}), reintentando en {wait}s...")
                time.sleep(wait)
            continue
        except requests.exceptions.HTTPError as e:
            # 524 = Cloudflare timeout, 502/503 = server restarting — retry
            if hasattr(e, 'response') and e.response is not None and e.response.status_code in (502, 503, 524):
                last_error = e
                if attempt < retries:
                    wait = 15 if e.response.status_code == 524 else 10
                    print(f"  ⏳ HTTP {e.response.status_code} (intento {attempt}/{retries}), reintentando en {wait}s...")
                    time.sleep(wait)
                continue
            raise e
        except Exception as e:
            raise e
    raise last_error


def build_payload(user_message, conversation_context=None, recent_messages=None,
                  profile_name="Test User", conv_id=88880, internal_employee=None):
    """Build the /admin/agent-test payload."""
    ctx = conversation_context or {}
    if internal_employee:
        ctx["internal_auth"] = {
            "role": internal_employee.get("role", "administrador"),
            "employee_context": {
                "cedula": internal_employee.get("cedula", "1088266407"),
                "full_name": internal_employee.get("name", "Diego Mauricio Garcia Rengifo"),
                "cargo": internal_employee.get("cargo", "Lider comercial y de compras"),
                "sede": internal_employee.get("sede", "Parque Olaya"),
                "store_code": internal_employee.get("store_code", "189"),
            },
        }
    payload = {
        "profile_name": profile_name,
        "conversation_context": ctx,
        "recent_messages": recent_messages or [],
        "user_message": user_message,
        "context": {
            "conversation_id": conv_id,
            "contact_id": conv_id,
            "cliente_id": None,
            "telefono_e164": "+573205046277",
            "nombre_visible": profile_name,
        },
    }
    if PROMPT_VERSION:
        payload["prompt_version"] = PROMPT_VERSION
    return payload


def extract_tool_names(result):
    """Get list of tool names called."""
    return [tc["name"] for tc in (result.get("tool_calls") or [])]


def extract_tool_results(result, tool_name):
    """Get all results from a specific tool."""
    return [tc["result"] for tc in (result.get("tool_calls") or []) if tc["name"] == tool_name]


def response_text(result):
    """Get the response text."""
    return (result.get("response_text") or "").strip()


def response_lower(result):
    """Get lowercase response text."""
    return response_text(result).lower()


# ══════════════════════════════════════════════════════════════════════════════
# ASSERTION HELPERS
# ══════════════════════════════════════════════════════════════════════════════

class TestResult:
    def __init__(self, name, category):
        self.name = name
        self.category = category
        self.status = "PASS"
        self.checks = []
        self.warnings = []
        self.failures = []
        self.elapsed_ms = 0
        self.tools_called = []
        self.response_preview = ""

    def check(self, condition, label, critical=True):
        """Assert a condition. critical=True → FAIL, critical=False → WARN."""
        if condition:
            self.checks.append(f"  ✅ {label}")
        elif critical:
            self.failures.append(f"  ❌ FAIL: {label}")
            self.status = "FAIL"
        else:
            self.warnings.append(f"  ⚠️ WARN: {label}")
            if self.status == "PASS":
                self.status = "WARN"

    def check_tool_called(self, tool_name, tools_list):
        """Assert a tool was called."""
        called = tool_name in tools_list
        self.check(called, f"Tool `{tool_name}` fue llamada", critical=True)
        return called

    def check_response_contains(self, text, keywords, label=None, critical=True):
        """Assert response contains at least one of the keywords."""
        txt = text.lower()
        found = [kw for kw in keywords if kw.lower() in txt]
        lbl = label or f"Respuesta contiene alguno de {keywords}"
        self.check(len(found) > 0, lbl, critical=critical)
        return found

    def check_response_not_contains(self, text, keywords, label=None, critical=True):
        """Assert response does NOT contain any of the keywords."""
        txt = text.lower()
        found = [kw for kw in keywords if kw.lower() in txt]
        lbl = label or f"Respuesta NO contiene {keywords}"
        self.check(len(found) == 0, lbl, critical=critical)
        return found

    def summary_line(self):
        status_color = {
            "PASS": C.GREEN,
            "WARN": C.YELLOW,
            "FAIL": C.RED,
        }
        c = status_color.get(self.status, "")
        return f"{c}{self.status:>4}{C.END} | {self.elapsed_ms:>6}ms | {self.name} [{self.category}]"


# ══════════════════════════════════════════════════════════════════════════════
# TEST DEFINITIONS
# ══════════════════════════════════════════════════════════════════════════════

def test_omega_multi_intent():
    """
    TEST OMEGA: Multi-intención pura.
    Un administrador/vendedor envía un solo mensaje con:
    1. BI: compras acumuladas este mes
    2. CRM: cartera de Constructora Bolívar
    3. B2B: pedido de 8 galones Viniltex 1501
    4. RAG: asesoría para piso industrial de bodega con montacargas, 120m²
    
    El agente DEBE llamar ≥4 herramientas diferentes y responder a TODAS.
    """
    tr = TestResult("OMEGA: Multi-intención (BI+CRM+B2B+RAG)", "multi-intent")

    payload = build_payload(
        user_message=(
            "Hola FERRO. Hermano, revíseme urgente cuánto llevamos en compras acumuladas este mes en la empresa. "
            "También necesito ver cómo está la cartera de la 'Constructora Bolívar'. "
            "Ah, y de una vez mónteme un pedido: mándeme 8 galones de Viniltex 1501, "
            "pero espere, necesito asesoría rápida: tengo un cliente con un piso de bodega donde "
            "entran montacargas pesados todo el día, está en cemento rústico pelado y "
            "necesita pintura de alto tráfico. ¿Qué sistema le aplico a eso y cuánto me "
            "valen los materiales para 120 metros cuadrados? Mándeme todo con IVA desglosado."
        ),
        internal_employee={
            "role": "administrador",
            "cedula": "1088266407",
            "name": "Diego Mauricio Garcia Rengifo",
            "cargo": "Lider comercial y de compras",
            "sede": "Parque Olaya",
            "store_code": "189",
        },
    )

    try:
        result, elapsed = _agent_request(payload)
        tr.elapsed_ms = elapsed
        tools = extract_tool_names(result)
        tr.tools_called = tools
        resp = response_text(result)
        tr.response_preview = resp[:300]
        resp_low = resp.lower()

        print(f"\n  🔧 Tools llamadas: {tools}")
        print(f"  ⏱️ Tiempo: {elapsed}ms")
        print(f"  📝 Respuesta ({len(resp)} chars): {resp[:200]}...")

        # ── ASSERTIONS ──
        # 1. BI: Debe llamar alguna herramienta de ventas/compras
        has_bi = "consultar_ventas_internas" in tools or "consultar_compras" in tools
        tr.check(has_bi, "BI: llamó consultar_ventas_internas o consultar_compras")

        # 2. CRM: Debe llamar verificar_identidad o consultar_cartera
        has_crm = "verificar_identidad" in tools or "consultar_cartera" in tools
        tr.check(has_crm, "CRM: llamó verificar_identidad o consultar_cartera")

        # 3. B2B: Debe llamar consultar_inventario o consultar_inventario_lote
        has_inv = "consultar_inventario" in tools or "consultar_inventario_lote" in tools
        tr.check(has_inv, "B2B: llamó consultar_inventario o consultar_inventario_lote")

        # 4. RAG: Debe llamar consultar_conocimiento_tecnico para piso industrial
        has_rag = "consultar_conocimiento_tecnico" in tools
        tr.check(has_rag, "RAG: llamó consultar_conocimiento_tecnico para piso industrial")

        # 5. Response covers ALL intents
        tr.check_response_contains(resp, ["compras", "ventas", "acumulad"], "Respuesta menciona compras/ventas", critical=False)
        tr.check_response_contains(resp, ["cartera", "bolívar", "bolivar", "constructora"], "Respuesta menciona cartera/Bolívar", critical=False)
        tr.check_response_contains(resp, ["viniltex", "1501"], "Respuesta menciona Viniltex 1501", critical=False)
        tr.check_response_contains(resp, ["piso", "bodega", "montacarga", "tráfico", "trafico", "industrial", "epóx", "epox", "interseal", "intergard", "pintucoat"], "Respuesta menciona sistema piso industrial")

        # 6. Should have ≥4 distinct tool types called
        distinct_tools = set(tools)
        tr.check(len(distinct_tools) >= 3, f"≥3 herramientas distintas llamadas (tiene {len(distinct_tools)})")
        tr.check(len(distinct_tools) >= 4, f"≥4 herramientas distintas llamadas (tiene {len(distinct_tools)})", critical=False)

        # 7. NOT: should not ONLY do B2B and skip everything else
        tr.check(len(tools) >= 3, f"≥3 llamadas totales a herramientas (tiene {len(tools)})")

    except Exception as e:
        tr.status = "FAIL"
        tr.failures.append(f"  ❌ EXCEPTION: {e}")
        traceback.print_exc()

    return tr


def test_asesoria_tecnica_flujo_completo():
    """
    Flujo completo de asesoría técnica:
    Turno 1: Cliente describe superficie → agente debe diagnosticar (NO cotizar)
    Turno 2: Cliente confirma → agente recomienda sistema con herramientas y diluyente
    Turno 3: Cliente pide precios → agente cotiza con IVA
    """
    tr = TestResult("Asesoría técnica: diagnóstico → sistema → cotización", "asesoria")

    ctx = {}
    messages = []

    # ── TURNO 1: Descripción de superficie ──
    try:
        payload = build_payload(
            "Necesito pintar un piso de bodega donde entran montacargas pesados todo el día, "
            "está en cemento pelado sin pintura. Son como 200 metros cuadrados.",
            conversation_context=ctx,
            recent_messages=messages,
        )
        result1, elapsed1 = _agent_request(payload)
        tools1 = extract_tool_names(result1)
        resp1 = response_text(result1)
        resp1_low = resp1.lower()
        tr.elapsed_ms += elapsed1

        print(f"\n  T1 Tools: {tools1} | {elapsed1}ms")
        print(f"  T1 Resp: {resp1[:200]}...")

        # Should either ask diagnostic questions OR go straight to system recommendation
        # (since user gave surface + condition + area already)
        has_rag = "consultar_conocimiento_tecnico" in tools1
        has_system = any(kw in resp1_low for kw in ["interseal", "intergard", "pintucoat", "epóx", "epox", "tráfico", "trafico"])
        has_questions = "?" in resp1

        tr.check(has_rag or has_system, "T1: llamó RAG o ya tiene sistema recomendado")
        # Should NOT have premature pricing (GUARDIA FLUJO-COMERCIAL should catch this)
        has_premature_price = "$" in resp1 and any(kw in resp1_low for kw in ["total", "subtotal", "iva"])
        tr.check(not has_premature_price, "T1: NO tiene precios prematuros (guardia flujo-comercial)", critical=False)

        # Accumulate context for next turns
        messages.append({"direction": "inbound", "contenido": payload["user_message"], "message_type": "text"})
        messages.append({"direction": "outbound", "contenido": resp1, "message_type": "text"})
        ctx.update(result1.get("context_updates") or {})

        # ── TURNO 2: Cliente confirma que quiere precios ──
        payload2 = build_payload(
            "Sí dale, revísame precios y disponibilidad de todo el sistema completo.",
            conversation_context=ctx,
            recent_messages=messages,
            conv_id=88881,
        )
        result2, elapsed2 = _agent_request(payload2)
        tools2 = extract_tool_names(result2)
        resp2 = response_text(result2)
        resp2_low = resp2.lower()
        tr.elapsed_ms += elapsed2

        print(f"\n  T2 Tools: {tools2} | {elapsed2}ms")
        print(f"  T2 Resp: {resp2[:200]}...")

        # Should now have inventory calls + prices
        has_inv2 = "consultar_inventario" in tools2 or "consultar_inventario_lote" in tools2
        tr.check(has_inv2, "T2: llamó inventario para precios")
        tr.check_response_contains(resp2, ["$", "precio", "total"], "T2: Respuesta contiene precios")

        # Should have IVA mention
        tr.check_response_contains(resp2, ["iva", "19%"], "T2: Menciona IVA", critical=False)

        # Should mention tools/diluyente as cross-sell
        tr.check_response_contains(
            resp2,
            ["diluyente", "thinner", "ufa151", "rodillo", "brocha", "herramienta", "lija"],
            "T2: Menciona herramientas o diluyente (venta cruzada)",
            critical=False,
        )

        messages.append({"direction": "inbound", "contenido": payload2["user_message"], "message_type": "text"})
        messages.append({"direction": "outbound", "contenido": resp2, "message_type": "text"})
        ctx.update(result2.get("context_updates") or {})

        # ── TURNO 3: Pregunta técnica puntual (rendimiento) ──
        payload3 = build_payload(
            "¿Cuánto rinde el Interseal por galón?",
            conversation_context=ctx,
            recent_messages=messages,
            conv_id=88881,
        )
        result3, elapsed3 = _agent_request(payload3)
        tools3 = extract_tool_names(result3)
        resp3 = response_text(result3)
        resp3_low = resp3.lower()
        tr.elapsed_ms += elapsed3

        print(f"\n  T3 Tools: {tools3} | {elapsed3}ms")
        print(f"  T3 Resp: {resp3[:200]}...")

        # Should be a SHORT technical answer about rendimiento, NOT a full quote
        has_rendimiento = any(kw in resp3_low for kw in [
            "rendimiento", "rinde", "m²", "m2", "metros cuadrados",
            "galón", "galon", "cuñete", "cobertura",
            "m2/gal", "por galón", "por galon",
        ])
        tr.check(has_rendimiento, "T3: Respuesta contiene dato de rendimiento")
        # Should NOT repeat the full quotation
        has_full_quote = "$" in resp3 and "total" in resp3_low and len(resp3) > 500
        tr.check(not has_full_quote, "T3: NO repite cotización completa (guardia pregunta-técnica)", critical=False)

    except Exception as e:
        tr.status = "FAIL"
        tr.failures.append(f"  ❌ EXCEPTION: {e}")
        traceback.print_exc()

    return tr


def test_b2b_puro():
    """B2B Fast-Track: empleado interno con lista de productos pura."""
    tr = TestResult("B2B Fast-Track: lista de productos pura", "b2b")

    payload = build_payload(
        "8 galones viniltex blanco 1501\n4 cuartos koraza rojo\n2 galones pintulux 3en1 blanco",
        internal_employee={"role": "vendedor", "cedula": "1088266407"},
    )

    try:
        result, elapsed = _agent_request(payload)
        tools = extract_tool_names(result)
        resp = response_text(result)
        tr.elapsed_ms = elapsed
        tr.tools_called = tools
        tr.response_preview = resp[:300]

        print(f"\n  🔧 Tools: {tools} | {elapsed}ms")
        print(f"  📝 Resp: {resp[:200]}...")

        # Should call inventory (lote or multiple singles)
        has_inv = "consultar_inventario_lote" in tools or "consultar_inventario" in tools
        tr.check(has_inv, "Llamó inventario para los productos")

        # Should NOT call RAG
        has_rag = "consultar_conocimiento_tecnico" in tools
        tr.check(not has_rag, "NO llamó RAG (B2B puro, sin diagnóstico)")

        # Should have prices
        tr.check_response_contains(resp, ["$", "precio"], "Respuesta contiene precios")

        # Should mention all 3 products
        tr.check_response_contains(resp, ["viniltex", "1501"], "Menciona Viniltex 1501")
        tr.check_response_contains(resp, ["koraza"], "Menciona Koraza", critical=False)
        tr.check_response_contains(resp, ["pintulux", "3en1"], "Menciona Pintulux 3en1", critical=False)

    except Exception as e:
        tr.status = "FAIL"
        tr.failures.append(f"  ❌ EXCEPTION: {e}")
        traceback.print_exc()

    return tr


def test_saludo_basico():
    """Saludo simple debe generar bienvenida sin herramientas."""
    tr = TestResult("Saludo básico: bienvenida sin herramientas", "flujo")

    payload = build_payload("Hola buenas tardes")

    try:
        result, elapsed = _agent_request(payload)
        tools = extract_tool_names(result)
        resp = response_text(result)
        tr.elapsed_ms = elapsed
        tr.tools_called = tools

        print(f"\n  🔧 Tools: {tools} | {elapsed}ms")
        print(f"  📝 Resp: {resp[:200]}...")

        tr.check(len(tools) == 0, f"NO llamó herramientas (llamó {len(tools)})", critical=False)
        tr.check_response_contains(resp, ["ferro", "ferreinox", "bienvenid", "asistente", "ayud"], "Respuesta de bienvenida")
        tr.check(len(resp) < 500, f"Respuesta corta (<500 chars, tiene {len(resp)})", critical=False)

    except Exception as e:
        tr.status = "FAIL"
        tr.failures.append(f"  ❌ EXCEPTION: {e}")
        traceback.print_exc()

    return tr


def test_despedida_cierre():
    """Despedida debe cerrar la conversación apropiadamente."""
    tr = TestResult("Despedida: cierre de conversación", "flujo")

    # Simulate previous interaction
    messages = [
        {"direction": "inbound", "contenido": "Hola", "message_type": "text"},
        {"direction": "outbound", "contenido": "¡Bienvenido a Ferreinox! Soy FERRO. ¿En qué te ayudo?", "message_type": "text"},
        {"direction": "inbound", "contenido": "Necesito koraza blanca galón", "message_type": "text"},
        {"direction": "outbound", "contenido": "Claro, el galón de Koraza Blanca está disponible a $89,900 + IVA. ¿Deseas pedirlo?", "message_type": "text"},
    ]

    payload = build_payload(
        "No gracias, eso era todo. Muchas gracias por la ayuda.",
        recent_messages=messages,
    )

    try:
        result, elapsed = _agent_request(payload)
        tools = extract_tool_names(result)
        resp = response_text(result)
        tr.elapsed_ms = elapsed

        print(f"\n  🔧 Tools: {tools} | {elapsed}ms")
        print(f"  📝 Resp: {resp[:200]}...")

        tr.check(len(tools) == 0, "NO llamó herramientas en despedida", critical=False)
        tr.check_response_contains(resp, ["gracias", "gusto", "cualquier", "orden", "servicio", "cuid", "nada", "ayud", "día", "dia", "excelente", "futuro", "suerte", "éxito", "vuelv"], "Respuesta de despedida cordial")
        # Should NOT repeat the Koraza quote
        tr.check_response_not_contains(resp, ["$89", "koraza", "pedido"], "NO repite cotización anterior", critical=False)

    except Exception as e:
        tr.status = "FAIL"
        tr.failures.append(f"  ❌ EXCEPTION: {e}")
        traceback.print_exc()

    return tr


def test_cambio_tema_post_cotizacion():
    """Después de cotización, cambio de tema debe resetear contexto."""
    tr = TestResult("Cambio de tema post-cotización", "flujo")

    messages = [
        {"direction": "inbound", "contenido": "Necesito 4 galones de Koraza blanca", "message_type": "text"},
        {"direction": "outbound", "contenido": "¡Claro! Koraza Blanca:\n- 4 galones x $89,900 = $359,600\n- IVA 19%: $68,324\n- **Total: $427,924**\n¿Deseas confirmar?", "message_type": "text"},
    ]

    payload = build_payload(
        "Oye, y tengo unas vigas de acero oxidadas en exterior, ¿qué les echo?",
        recent_messages=messages,
    )

    try:
        result, elapsed = _agent_request(payload)
        tools = extract_tool_names(result)
        resp = response_text(result)
        tr.elapsed_ms = elapsed

        print(f"\n  🔧 Tools: {tools} | {elapsed}ms")
        print(f"  📝 Resp: {resp[:200]}...")

        # Should NOT repeat the Koraza quote
        tr.check_response_not_contains(resp, ["koraza", "$427", "$359"], "NO arrastra cotización anterior")

        # Should address the new topic (metal/anticorrosivo)
        tr.check_response_contains(
            resp,
            ["acero", "metal", "oxid", "anticorrosiv", "corrotec", "interseal", "wash primer", "vigas", "estructura"],
            "Respuesta aborda vigas de acero/anticorrosivo",
        )

        # May call RAG for metal surface
        has_rag = "consultar_conocimiento_tecnico" in tools
        tr.check(has_rag, "Llamó RAG para asesoría de metal oxidado", critical=False)

    except Exception as e:
        tr.status = "FAIL"
        tr.failures.append(f"  ❌ EXCEPTION: {e}")
        traceback.print_exc()

    return tr


def test_correccion_transaccional():
    """Corrección de un ítem en cotización activa."""
    tr = TestResult("Corrección transaccional: cambiar ítem de cotización", "transaccional")

    messages = [
        {"direction": "inbound", "contenido": "Necesito 4 galones de Viniltex Blanco 1501 y 2 galones Koraza Blanca", "message_type": "text"},
        {"direction": "outbound", "contenido": (
            "¡Listo! Tu cotización:\n"
            "1. Viniltex Advanced Blanco 1501 - 4 gal x $85,000 = $340,000\n"
            "2. Koraza Blanca - 2 gal x $95,000 = $190,000\n"
            "- Subtotal: $530,000\n"
            "- IVA 19%: $100,700\n"
            "- **Total: $630,700**\n\n¿Deseas proceder?"
        ), "message_type": "text"},
    ]

    payload = build_payload(
        "Cambia el Viniltex blanco por Viniltex Almendra. Lo demás déjalo igual.",
        recent_messages=messages,
    )

    try:
        result, elapsed = _agent_request(payload)
        tools = extract_tool_names(result)
        resp = response_text(result)
        tr.elapsed_ms = elapsed

        print(f"\n  🔧 Tools: {tools} | {elapsed}ms")
        print(f"  📝 Resp: {resp[:200]}...")

        # Should call inventory for the corrected product
        has_inv = "consultar_inventario" in tools or "consultar_inventario_lote" in tools
        tr.check(has_inv, "Llamó inventario para Viniltex Almendra")

        # Should NOT call RAG (this is a correction, not advisory)
        has_rag = "consultar_conocimiento_tecnico" in tools
        tr.check(not has_rag, "NO llamó RAG (corrección transaccional)", critical=False)

        # Response should still have Koraza (unchanged item)
        tr.check_response_contains(resp, ["koraza"], "Mantiene Koraza (ítem no modificado)")

        # Response should have almendra (corrected item)
        tr.check_response_contains(resp, ["almendra", "viniltex"], "Incluye Viniltex Almendra (ítem corregido)")

        # Should have total
        tr.check_response_contains(resp, ["total", "$"], "Muestra total recalculado")

    except Exception as e:
        tr.status = "FAIL"
        tr.failures.append(f"  ❌ EXCEPTION: {e}")
        traceback.print_exc()

    return tr


def test_pregunta_tecnica_pura():
    """Pregunta técnica pura no debe generar precios."""
    tr = TestResult("Pregunta técnica pura: sin precios", "guardia")

    payload = build_payload(
        "¿Cómo se prepara la superficie antes de aplicar Interseal? ¿Se necesita sandblasting?"
    )

    try:
        result, elapsed = _agent_request(payload)
        tools = extract_tool_names(result)
        resp = response_text(result)
        tr.elapsed_ms = elapsed

        print(f"\n  🔧 Tools: {tools} | {elapsed}ms")
        print(f"  📝 Resp: {resp[:200]}...")

        # Should call RAG
        has_rag = "consultar_conocimiento_tecnico" in tools
        tr.check(has_rag, "Llamó RAG para información técnica")

        # Response should contain technical info
        tr.check_response_contains(
            resp,
            ["preparación", "preparacion", "superficie", "lij", "sandblast", "perfil", "granallad", "limpi"],
            "Respuesta contiene información de preparación",
        )

        # Should NOT have prices
        has_prices = "$" in resp and any(kw in resp.lower() for kw in ["total", "precio", "cotización", "cotizacion"])
        tr.check(not has_prices, "NO contiene precios (guardia pregunta-técnica)")

    except Exception as e:
        tr.status = "FAIL"
        tr.failures.append(f"  ❌ EXCEPTION: {e}")
        traceback.print_exc()

    return tr


def test_ventas_internas_admin():
    """Empleado admin consulta ventas internas."""
    tr = TestResult("BI Interno: consulta de ventas como admin", "bi")

    payload = build_payload(
        "¿Cómo van las ventas de Pereira este mes?",
        internal_employee={"role": "administrador", "cedula": "1088266407"},
    )

    try:
        result, elapsed = _agent_request(payload)
        tools = extract_tool_names(result)
        resp = response_text(result)
        tr.elapsed_ms = elapsed

        print(f"\n  🔧 Tools: {tools} | {elapsed}ms")
        print(f"  📝 Resp: {resp[:200]}...")

        has_ventas = "consultar_ventas_internas" in tools
        tr.check(has_ventas, "Llamó consultar_ventas_internas")

        # Response should have numbers
        has_numbers = bool(re.search(r'\$[\d.,]+', resp))
        tr.check(has_numbers, "Respuesta contiene cifras de ventas ($)")

        tr.check_response_contains(resp, ["pereira", "ventas", "neta", "abril", "mes"], "Menciona Pereira y periodo", critical=False)

    except Exception as e:
        tr.status = "FAIL"
        tr.failures.append(f"  ❌ EXCEPTION: {e}")
        traceback.print_exc()

    return tr


def test_cartera_sin_verificar():
    """Consulta de cartera sin estar verificado → debe pedir cédula/NIT."""
    tr = TestResult("CRM: cartera sin verificación previa", "crm")

    payload = build_payload("Quiero saber cuánto debo, soy de la Constructora Bolívar")

    try:
        result, elapsed = _agent_request(payload)
        tools = extract_tool_names(result)
        resp = response_text(result)
        tr.elapsed_ms = elapsed

        print(f"\n  🔧 Tools: {tools} | {elapsed}ms")
        print(f"  📝 Resp: {resp[:200]}...")

        # Should try to verify identity
        has_verify = "verificar_identidad" in tools
        # OR should ask for cédula/NIT
        asks_id = any(kw in resp.lower() for kw in ["cédula", "cedula", "nit", "identificar", "verificar", "documento"])

        tr.check(has_verify or asks_id, "Intentó verificar o pidió documento de identidad")

    except Exception as e:
        tr.status = "FAIL"
        tr.failures.append(f"  ❌ EXCEPTION: {e}")
        traceback.print_exc()

    return tr


def test_pedido_directo_sin_diagnostico():
    """Cliente nombra producto específico → directo a inventario, sin preguntas diagnósticas."""
    tr = TestResult("Pedido directo: producto específico sin diagnóstico", "flujo")

    payload = build_payload("Necesito 5 galones de Koraza Blanca para mi fachada")

    try:
        result, elapsed = _agent_request(payload)
        tools = extract_tool_names(result)
        resp = response_text(result)
        tr.elapsed_ms = elapsed

        print(f"\n  🔧 Tools: {tools} | {elapsed}ms")
        print(f"  📝 Resp: {resp[:200]}...")

        # Should call inventory
        has_inv = "consultar_inventario" in tools or "consultar_inventario_lote" in tools
        tr.check(has_inv, "Llamó inventario para Koraza")

        # Should mention Koraza
        tr.check_response_contains(resp, ["koraza"], "Respuesta menciona Koraza")

        # Should NOT ask "interior o exterior?" (client already said fachada)
        resp_low = resp.lower()
        asks_interior_exterior = "interior o exterior" in resp_low or "¿interior" in resp_low
        tr.check(not asks_interior_exterior, "NO pregunta interior/exterior (ya dijo fachada)", critical=False)

    except Exception as e:
        tr.status = "FAIL"
        tr.failures.append(f"  ❌ EXCEPTION: {e}")
        traceback.print_exc()

    return tr


def test_anti_repeticion_m2():
    """Si el cliente ya dio m², el agente no debe preguntar de nuevo."""
    tr = TestResult("Anti-repetición: no preguntar m² de nuevo", "guardia")

    messages = [
        {"direction": "inbound", "contenido": "Necesito pintar un piso de bodega de 150 metros cuadrados, tráfico pesado de montacargas", "message_type": "text"},
        {"direction": "outbound", "contenido": (
            "¡Entendido! Para un piso de bodega con tráfico pesado de montacargas, el sistema que te recomiendo es:\n"
            "1. Preparación: escarificado mecánico\n"
            "2. Imprimante: Interseal gris (epóxico)\n"
            "3. Acabado: Intergard 740 (epóxico de alto tráfico)\n"
            "4. Diluyente: UFA151\n\n"
            "¿Deseas que revise disponibilidad y precios del sistema completo?"
        ), "message_type": "text"},
    ]

    payload = build_payload(
        "Sí dale, revisa precios",
        recent_messages=messages,
    )

    try:
        result, elapsed = _agent_request(payload)
        tools = extract_tool_names(result)
        resp = response_text(result)
        tr.elapsed_ms = elapsed

        print(f"\n  🔧 Tools: {tools} | {elapsed}ms")
        print(f"  📝 Resp: {resp[:200]}...")

        # Should call inventory
        has_inv = "consultar_inventario" in tools or "consultar_inventario_lote" in tools
        tr.check(has_inv, "Llamó inventario para precios")

        # Should NOT ask for m² again
        resp_low = resp.lower()
        asks_m2_again = any(kw in resp_low for kw in ["cuántos metros", "cuantos metros", "metros cuadrados tiene"])
        tr.check(not asks_m2_again, "NO pregunta metros cuadrados de nuevo")

        # Should have prices or at least product details from inventory
        import re as _re_price
        has_price_sign = "$" in resp
        has_price_word = any(kw in resp.lower() for kw in ["precio", "total", "cotización", "cotizacion", "disponible", "stock"])
        has_numeric_price = bool(_re_price.search(r'\d{2,3}[.,]\d{3}', resp))  # e.g. 79,908 or 79.908
        tr.check(has_price_sign or has_price_word or has_numeric_price, "Respuesta contiene precios o datos de inventario")

    except Exception as e:
        tr.status = "FAIL"
        tr.failures.append(f"  ❌ EXCEPTION: {e}")
        traceback.print_exc()

    return tr


def test_reclamo_flujo():
    """Flujo básico de reclamo: empatía → diagnóstico → datos."""
    tr = TestResult("Reclamo: flujo de empatía y diagnóstico", "reclamo")

    payload = build_payload(
        "Compré Koraza hace 3 meses para la fachada y ya se está pelando toda. Estoy muy molesto."
    )

    try:
        result, elapsed = _agent_request(payload)
        tools = extract_tool_names(result)
        resp = response_text(result)
        tr.elapsed_ms = elapsed

        print(f"\n  🔧 Tools: {tools} | {elapsed}ms")
        print(f"  📝 Resp: {resp[:200]}...")

        # Should show empathy
        resp_low = resp.lower()
        has_empathy = any(kw in resp_low for kw in [
            "entiendo", "lamento", "tranquil", "solución", "solucion", "ayud",
            "preocup", "fastidio", "comprendo",
        ])
        tr.check(has_empathy, "Muestra empatía inicial")

        # Should ask diagnostic questions (preparation, tools used)
        has_questions = "?" in resp
        tr.check(has_questions, "Hace preguntas de diagnóstico")

        # Should NOT immediately ask for cédula
        tr.check_response_not_contains(resp, ["cédula", "cedula", "nit", "documento"], "NO pide cédula de inmediato", critical=False)

        # Should call RAG for Koraza technical info
        has_rag = "consultar_conocimiento_tecnico" in tools
        tr.check(has_rag, "Llamó RAG para diagnóstico técnico de Koraza", critical=False)

    except Exception as e:
        tr.status = "FAIL"
        tr.failures.append(f"  ❌ EXCEPTION: {e}")
        traceback.print_exc()

    return tr


def test_compatibilidad_quimica():
    """Cliente pide productos incompatibles → agente debe corregir."""
    tr = TestResult("Compatibilidad química: corrección de incompatibles", "guardia")

    payload = build_payload(
        "Quiero Corrotec como anticorrosivo y encima Interthane como acabado para mis rejas"
    )

    try:
        result, elapsed = _agent_request(payload)
        tools = extract_tool_names(result)
        resp = response_text(result)
        tr.elapsed_ms = elapsed

        print(f"\n  🔧 Tools: {tools} | {elapsed}ms")
        print(f"  📝 Resp: {resp[:200]}...")

        resp_low = resp.lower()
        # Should detect incompatibility (alquídico + PU)
        has_correction = any(kw in resp_low for kw in [
            "incompatible", "no es compatible", "no son compatibles",
            "alquídic", "alquidic", "remueve", "ataca",
            "sistema correcto", "la opción correcta", "la opcion correcta",
            "mejor opción", "mejor opcion",
            "en su lugar", "en vez de", "te recomiendo", "recomendado",
            "no utiliz", "no es adecuad", "no se debe", "no aplica sobre",
            "correcto sería", "correcto seria", "sistema recomendado",
            "no se recomienda", "no recomendamos", "te sugiero",
        ])
        tr.check(has_correction, "Detecta incompatibilidad o recomienda sistema correcto")

        # Should suggest alternatives
        has_alternative = any(kw in resp_low for kw in [
            "interseal", "pintulux", "3en1", "opción", "opcion", "alternativa",
        ])
        tr.check(has_alternative, "Sugiere alternativa compatible", critical=False)

    except Exception as e:
        tr.status = "FAIL"
        tr.failures.append(f"  ❌ EXCEPTION: {e}")
        traceback.print_exc()

    return tr


def test_documento_tecnico():
    """Solicitud de ficha técnica → buscar_documento_tecnico."""
    tr = TestResult("Ficha técnica: buscar documento", "flujo")

    payload = build_payload("Necesito la ficha técnica del Interseal 670")

    try:
        result, elapsed = _agent_request(payload)
        tools = extract_tool_names(result)
        resp = response_text(result)
        tr.elapsed_ms = elapsed

        print(f"\n  🔧 Tools: {tools} | {elapsed}ms")
        print(f"  📝 Resp: {resp[:200]}...")

        has_doc = "buscar_documento_tecnico" in tools
        tr.check(has_doc, "Llamó buscar_documento_tecnico")

        tr.check_response_contains(resp, ["interseal", "ficha", "técn", "tecn"], "Respuesta sobre ficha Interseal")

    except Exception as e:
        tr.status = "FAIL"
        tr.failures.append(f"  ❌ EXCEPTION: {e}")
        traceback.print_exc()

    return tr


def test_inventario_lote_multiple():
    """Lista de múltiples productos → usar consultar_inventario_lote."""
    tr = TestResult("Inventario lote: múltiples productos", "b2b")

    payload = build_payload(
        "¿Tienes disponible Viniltex Blanco, Koraza Roja, y Pintulux Negro? Todo en galones."
    )

    try:
        result, elapsed = _agent_request(payload)
        tools = extract_tool_names(result)
        resp = response_text(result)
        tr.elapsed_ms = elapsed

        print(f"\n  🔧 Tools: {tools} | {elapsed}ms")
        print(f"  📝 Resp: {resp[:200]}...")

        # Should use lote for 3 products OR multiple single calls
        has_lote = "consultar_inventario_lote" in tools
        inv_count = tools.count("consultar_inventario")
        tr.check(has_lote or inv_count >= 2, f"Usó inventario_lote o múltiples consultar_inventario ({inv_count})")

    except Exception as e:
        tr.status = "FAIL"
        tr.failures.append(f"  ❌ EXCEPTION: {e}")
        traceback.print_exc()

    return tr


def test_bicomponente_catalizador():
    """Bicomponente debe incluir catalizador obligatorio."""
    tr = TestResult("Bicomponente: catalizador obligatorio", "guardia")

    payload = build_payload(
        "Cotízame 4 galones de Interseal gris para un piso industrial"
    )

    try:
        result, elapsed = _agent_request(payload)
        tools = extract_tool_names(result)
        resp = response_text(result)
        tr.elapsed_ms = elapsed

        print(f"\n  🔧 Tools: {tools} | {elapsed}ms")
        print(f"  📝 Resp: {resp[:200]}...")

        resp_low = resp.lower()
        # Interseal is bicomponent - must mention catalizador
        has_catalyst = any(kw in resp_low for kw in ["catalizador", "componente b", "kit", "ega", "parte b"])
        tr.check(has_catalyst, "Menciona catalizador para Interseal (bicomponente)", critical=False)

        # Should have prices since user said "cotízame"
        has_inv = "consultar_inventario" in tools or "consultar_inventario_lote" in tools
        tr.check(has_inv, "Llamó inventario para cotizar")

    except Exception as e:
        tr.status = "FAIL"
        tr.failures.append(f"  ❌ EXCEPTION: {e}")
        traceback.print_exc()

    return tr


def test_mensaje_largo_incoherente():
    """Mensaje largo con errores de tipeo y jerga colombiana."""
    tr = TestResult("Robustez: mensaje con jerga y errores tipeo", "robustez")

    payload = build_payload(
        "oiga hermano necesito algo pa las carretas que pasan por el piso de la bodega "
        "esque se pela todito y queda feísimo las estibadoras pasan todo el santo dia "
        "y la pintura no aguanta nada que me recomienda?"
    )

    try:
        result, elapsed = _agent_request(payload)
        tools = extract_tool_names(result)
        resp = response_text(result)
        tr.elapsed_ms = elapsed

        print(f"\n  🔧 Tools: {tools} | {elapsed}ms")
        print(f"  📝 Resp: {resp[:200]}...")

        # Should understand this is industrial floor + heavy traffic
        resp_low = resp.lower()
        relevant_products = any(kw in resp_low for kw in [
            "piso", "bodega", "tráfico", "trafico", "epóx", "epox",
            "interseal", "intergard", "pintucoat", "industrial",
        ])
        tr.check(relevant_products, "Entiende que es piso industrial con tráfico pesado")

        # Should call RAG or ask diagnostic
        has_rag = "consultar_conocimiento_tecnico" in tools
        has_questions = "?" in resp
        tr.check(has_rag or has_questions, "Llamó RAG o hizo preguntas diagnósticas")

    except Exception as e:
        tr.status = "FAIL"
        tr.failures.append(f"  ❌ EXCEPTION: {e}")
        traceback.print_exc()

    return tr


# ══════════════════════════════════════════════════════════════════════════════
# EL LABERINTO COGNITIVO — Chaos Multi-Turn Stress Test
# ══════════════════════════════════════════════════════════════════════════════

def test_laberinto_cognitivo():
    """
    LABERINTO COGNITIVO: 4 turnos de caos cognitivo absoluto.
    T1: Carrito B2B (Koraza 10gal + brochas + candados) como empleado interno
    T2: Interrupción técnica (salitre/eflorescencia) → RAG diagnóstico, NO mezclar con T1
    T3: Salto a BI/CRM (cartera "ferretería la universal") → CRM, NO cotizar
    T4: Merge total — retomar T1 sin candados, Koraza 5gal no 10, agregar productos T2 para 40m², IVA desglosado
    """
    tr = TestResult("Laberinto Cognitivo: 4 turnos de caos", "laberinto")

    CONV_ID = 99990
    ctx = {}
    messages = []
    internal_emp = {
        "role": "administrador",
        "cedula": "1088266407",
        "name": "Diego Mauricio Garcia Rengifo",
        "cargo": "Lider comercial y de compras",
        "sede": "Parque Olaya",
        "store_code": "189",
    }

    # ── TURNO 1: Carrito B2B puro ──
    try:
        payload1 = build_payload(
            "Necesito armar un pedido para un cliente: 2 Koraza de 10 galones blanco, "
            "6 brochas de 4 pulgadas y una docena de candados de 40mm. "
            "Dame inventario y precios de los tres.",
            conversation_context=ctx,
            recent_messages=messages,
            conv_id=CONV_ID,
            internal_employee=internal_emp,
        )
        result1, elapsed1 = _agent_request(payload1)
        tools1 = extract_tool_names(result1)
        resp1 = response_text(result1)
        resp1_low = resp1.lower()
        tr.elapsed_ms += elapsed1

        print(f"\n  T1 Tools: {tools1} | {elapsed1}ms")
        print(f"  T1 Resp: {resp1[:300]}...")

        # ASSERT: Inventario llamado, NO RAG
        has_inv = any(t in tools1 for t in ["consultar_inventario", "consultar_inventario_lote"])
        tr.check(has_inv, "T1: Llamó inventario para el pedido B2B")
        has_rag = "consultar_conocimiento_tecnico" in tools1
        tr.check(not has_rag, "T1: NO llamó RAG (es pedido directo, no requiere diagnóstico)", critical=False)
        tr.check_response_contains(resp1, ["$", "precio", "koraza"], "T1: Respuesta tiene precios de Koraza")

        # Accumulate
        messages.append({"direction": "inbound", "contenido": payload1["user_message"], "message_type": "text"})
        messages.append({"direction": "outbound", "contenido": resp1, "message_type": "text"})
        ctx.update(result1.get("context_updates") or {})

    except Exception as e:
        tr.check(False, f"T1 EXCEPCIÓN: {e}")
        tr.response_preview = str(e)[:300]
        return tr

    # ── TURNO 2: Interrupción técnica (salitre) ──
    try:
        time.sleep(3)  # Rate limit buffer
        payload2 = build_payload(
            "Oye antes de seguir, un cliente me preguntó sobre un muro exterior que tiene "
            "salitre y eflorescencia. ¿Qué sistema le recomiendo para eso?",
            conversation_context=ctx,
            recent_messages=messages,
            conv_id=CONV_ID,
            internal_employee=internal_emp,
        )
        result2, elapsed2 = _agent_request(payload2)
        tools2 = extract_tool_names(result2)
        resp2 = response_text(result2)
        resp2_low = resp2.lower()
        tr.elapsed_ms += elapsed2

        print(f"\n  T2 Tools: {tools2} | {elapsed2}ms")
        print(f"  T2 Resp: {resp2[:300]}...")

        # ASSERT: RAG debe ser llamada para diagnóstico técnico
        has_rag2 = "consultar_conocimiento_tecnico" in tools2
        tr.check(has_rag2, "T2: Llamó RAG para diagnóstico de salitre/eflorescencia")

        # Debe tener diagnóstico técnico
        tr.check_response_contains(
            resp2,
            ["salitre", "eflorescencia", "humedad", "impermeab", "sellador", "koraza",
             "preparación", "superficie", "lavar", "limpiar", "anticorros"],
            "T2: Respuesta tiene diagnóstico técnico sobre salitre",
        )

        # NO debe mezclar con el carrito de T1 (items específicos del pedido)
        # "brocha" sola es legítima en instrucciones de aplicación de pintura.
        # Detectamos contamination del CARRITO: frases específicas del pedido B2B.
        cart_specific = ["brochas de 4", "6 brochas", "candado", "40mm", "docena de",
                         "pedido anterior", "pedido que", "el pedido"]
        mixed_t1 = any(kw in resp2_low for kw in cart_specific)
        tr.check(not mixed_t1, "T2: NO mezcla con el carrito B2B de T1 (separación de contextos)")

        messages.append({"direction": "inbound", "contenido": payload2["user_message"], "message_type": "text"})
        messages.append({"direction": "outbound", "contenido": resp2, "message_type": "text"})
        ctx.update(result2.get("context_updates") or {})

    except Exception as e:
        tr.check(False, f"T2 EXCEPCIÓN: {e}")
        tr.response_preview = str(e)[:300]
        return tr

    # ── TURNO 3: Salto a BI/CRM (cartera) ──
    try:
        time.sleep(3)
        payload3 = build_payload(
            "Ah y otra cosa, revísame la cartera de Ferretería La Universal, "
            "¿cuánto nos deben y hace cuánto no pagan?",
            conversation_context=ctx,
            recent_messages=messages,
            conv_id=CONV_ID,
            internal_employee=internal_emp,
        )
        result3, elapsed3 = _agent_request(payload3)
        tools3 = extract_tool_names(result3)
        resp3 = response_text(result3)
        resp3_low = resp3.lower()
        tr.elapsed_ms += elapsed3

        print(f"\n  T3 Tools: {tools3} | {elapsed3}ms")
        print(f"  T3 Resp: {resp3[:300]}...")

        # ASSERT: Debe llamar herramienta CRM/BI
        has_crm = any(t in tools3 for t in [
            "consultar_cartera", "consultar_compras",
            "verificar_identidad", "consultar_cupo_credito",
        ])
        tr.check(has_crm, "T3: Llamó herramienta CRM/BI para cartera")

        # Should call consultar_cartera (directly with nombre_o_nit for internal employees)
        has_cartera = "consultar_cartera" in tools3
        tr.check(
            has_cartera,
            "T3: Llamó consultar_cartera (directa o encadenada) para datos de cartera",
            critical=True,
        )

        # NO debe cotizar nada — es solo consulta de cartera
        has_quote = "$" in resp3 and any(kw in resp3_low for kw in ["subtotal", "total", "cotizac"])
        tr.check(not has_quote, "T3: NO genera cotización (es consulta de cartera pura)")

        # Debe mencionar datos de cartera
        tr.check_response_contains(
            resp3,
            ["universal", "cartera", "saldo", "deuda", "vencid", "factura", "pago",
             "crédito", "credito", "días", "dias", "no encontr"],
            "T3: Respuesta tiene datos de cartera o indicación de búsqueda",
        )

        messages.append({"direction": "inbound", "contenido": payload3["user_message"], "message_type": "text"})
        messages.append({"direction": "outbound", "contenido": resp3, "message_type": "text"})
        ctx.update(result3.get("context_updates") or {})

    except Exception as e:
        tr.check(False, f"T3 EXCEPCIÓN: {e}")
        tr.response_preview = str(e)[:300]
        return tr

    # ── TURNO 4: MERGE TOTAL — El turno del caos ──
    try:
        time.sleep(4)
        payload4 = build_payload(
            "Bueno volviendo al pedido del inicio: quita los candados, cambia la Koraza "
            "de 10 galones a 5 galones (mantenme las 2 unidades), y agrega lo que necesite "
            "el cliente del muro con salitre para cubrir 40 metros cuadrados. "
            "Hazme la cotización completa con IVA desglosado.",
            conversation_context=ctx,
            recent_messages=messages,
            conv_id=CONV_ID,
            internal_employee=internal_emp,
        )
        result4, elapsed4 = _agent_request(payload4)
        tools4 = extract_tool_names(result4)
        resp4 = response_text(result4)
        resp4_low = resp4.lower()
        tr.elapsed_ms += elapsed4

        print(f"\n  T4 Tools: {tools4} | {elapsed4}ms")
        print(f"  T4 Resp: {resp4[:500]}...")

        # ASSERT: Debe tener inventario (para precios) y posiblemente RAG (para productos salitre)
        has_inv4 = any(t in tools4 for t in ["consultar_inventario", "consultar_inventario_lote"])
        tr.check(has_inv4, "T4: Llamó inventario para cotización unificada")

        # Debe tener Koraza (producto principal)
        tr.check_response_contains(resp4, ["koraza", "5 gal"], "T4: Menciona Koraza 5 galones")

        # Debe tener brochas (mantenido de T1)
        tr.check_response_contains(
            resp4,
            ["brocha", "brochas"],
            "T4: Mantiene brochas del pedido original",
            critical=False,
        )

        # NO debe tener candados (eliminados)
        has_candados = "candado" in resp4_low
        tr.check(not has_candados, "T4: Candados eliminados del pedido", critical=False)

        # Debe tener productos para salitre/eflorescencia (del T2)
        tr.check_response_contains(
            resp4,
            ["salitre", "sellador", "impermeab", "koraza", "40 m", "40m",
             "metros", "muro", "efloresc", "preparación", "superficie"],
            "T4: Incluye productos para el muro con salitre (merge T2→T4)",
            critical=False,
        )

        # Debe tener IVA desglosado
        tr.check_response_contains(
            resp4,
            ["iva", "19%", "impuesto"],
            "T4: IVA desglosado en la cotización",
        )

        # Debe tener precio total
        tr.check_response_contains(
            resp4,
            ["total", "$"],
            "T4: Cotización tiene precio total",
        )

        # NO debe mezclar datos de cartera (T3)
        has_cartera_leak = any(kw in resp4_low for kw in ["universal", "cartera", "saldo", "deuda"])
        tr.check(not has_cartera_leak, "T4: NO filtra datos de cartera de T3 en la cotización", critical=False)

        tr.response_preview = resp4[:400]
        tr.tools_called = tools1 + tools2 + tools3 + tools4

    except Exception as e:
        tr.check(False, f"T4 EXCEPCIÓN: {e}")
        tr.response_preview = str(e)[:300]
        return tr

    return tr


# ══════════════════════════════════════════════════════════════════════════════
# TEST RUNNER
# ══════════════════════════════════════════════════════════════════════════════

ALL_TESTS = [
    test_saludo_basico,
    test_despedida_cierre,
    test_omega_multi_intent,
    test_asesoria_tecnica_flujo_completo,
    test_b2b_puro,
    test_pedido_directo_sin_diagnostico,
    test_correccion_transaccional,
    test_cambio_tema_post_cotizacion,
    test_pregunta_tecnica_pura,
    test_anti_repeticion_m2,
    test_ventas_internas_admin,
    test_cartera_sin_verificar,
    test_reclamo_flujo,
    test_compatibilidad_quimica,
    test_documento_tecnico,
    test_inventario_lote_multiple,
    test_bicomponente_catalizador,
    test_mensaje_largo_incoherente,
    test_laberinto_cognitivo,
]


def run_all_tests(filter_category=None, filter_name=None):
    """Run all tests and print summary."""
    tests = ALL_TESTS
    if filter_category:
        tests = [t for t in tests if filter_category.lower() in t.__doc__.lower() or True]
    if filter_name:
        tests = [t for t in tests if filter_name.lower() in t.__name__.lower()]

    print("\n" + "=" * 90)
    print(f"{C.BOLD}🧨 TEST OMEGA — Stress Test Completo del Agente FERRO{C.END}")
    print(f"  Backend: {BACKEND_URL}")
    print(f"  Prompt Version: {PROMPT_VERSION or 'server default'}")
    print(f"  Tests: {len(tests)} | Timeout: {AGENT_TIMEOUT}s | Retries: {MAX_RETRIES}")
    print(f"  Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 90)

    # Connectivity check
    try:
        r = requests.post(
            AGENT_URL,
            headers={"x-admin-key": ADMIN_KEY, "Content-Type": "application/json"},
            json=build_payload("test"),
            timeout=30,
        )
        if r.status_code >= 500:
            print(f"\n{C.RED}❌ Backend retornó {r.status_code}. ¿Está desplegado?{C.END}")
            return
        print(f"\n  ✅ Backend conectado ({r.status_code})")
    except Exception as e:
        print(f"\n{C.RED}❌ No se pudo conectar al backend: {e}{C.END}")
        return

    results = []
    total_time = 0

    for i, test_fn in enumerate(tests, 1):
        print(f"\n{'━' * 90}")
        print(f"{C.BOLD}TEST {i}/{len(tests)}: {test_fn.__name__}{C.END}")
        if test_fn.__doc__:
            print(f"  📋 {test_fn.__doc__.strip().split(chr(10))[0]}")
        print(f"{'━' * 90}")

        tr = test_fn()
        results.append(tr)
        total_time += tr.elapsed_ms

        # Print check results
        for check in tr.checks:
            print(check)
        for warn in tr.warnings:
            print(warn)
        for fail in tr.failures:
            print(fail)

    # ── SUMMARY ──
    passed = sum(1 for r in results if r.status == "PASS")
    warned = sum(1 for r in results if r.status == "WARN")
    failed = sum(1 for r in results if r.status == "FAIL")

    print("\n\n" + "=" * 90)
    print(f"{C.BOLD}📊 RESUMEN TEST OMEGA{C.END}")
    print("=" * 90)

    for r in results:
        print(f"  {r.summary_line()}")

    print(f"\n  {'─' * 60}")
    print(f"  {C.GREEN}PASS: {passed}{C.END} | {C.YELLOW}WARN: {warned}{C.END} | {C.RED}FAIL: {failed}{C.END} | Total: {len(results)}")
    print(f"  ⏱️ Tiempo total: {total_time / 1000:.1f}s")

    # Category breakdown
    cats = {}
    for r in results:
        if r.category not in cats:
            cats[r.category] = {"pass": 0, "warn": 0, "fail": 0}
        cats[r.category][r.status.lower()] += 1

    print(f"\n  {'Categoría':<20} {'PASS':>5} {'WARN':>5} {'FAIL':>5}")
    print(f"  {'─' * 40}")
    for cat, counts in sorted(cats.items()):
        print(f"  {cat:<20} {counts['pass']:>5} {counts['warn']:>5} {counts['fail']:>5}")

    # Save results
    results_data = {
        "timestamp": datetime.now().isoformat(),
        "backend_url": BACKEND_URL,
        "summary": {"pass": passed, "warn": warned, "fail": failed, "total": len(results)},
        "total_time_ms": total_time,
        "tests": [
            {
                "name": r.name,
                "category": r.category,
                "status": r.status,
                "elapsed_ms": r.elapsed_ms,
                "tools_called": r.tools_called,
                "checks": r.checks,
                "warnings": r.warnings,
                "failures": r.failures,
                "response_preview": r.response_preview,
            }
            for r in results
        ],
    }
    try:
        with open("test_omega_results.json", "w", encoding="utf-8") as f:
            json.dump(results_data, f, ensure_ascii=False, indent=2)
        print(f"\n  💾 Resultados guardados en test_omega_results.json")
    except Exception:
        pass

    print("=" * 90)
    return passed, warned, failed


if __name__ == "__main__":
    filter_name = None
    if len(sys.argv) > 1:
        filter_name = sys.argv[1]
        print(f"🎯 Filtro: {filter_name}")
        ALL_TESTS_FILTERED = [t for t in ALL_TESTS if filter_name.lower() in t.__name__.lower()]
        if ALL_TESTS_FILTERED:
            ALL_TESTS[:] = ALL_TESTS_FILTERED
        else:
            print(f"⚠️ No hay tests que coincidan con '{filter_name}'. Ejecutando todos.")

    run_all_tests()
