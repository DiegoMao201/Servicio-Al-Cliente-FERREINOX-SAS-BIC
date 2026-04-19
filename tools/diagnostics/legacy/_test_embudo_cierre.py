"""Test del embudo de cierre comercial completo."""
import requests, json, time

URL = "https://apicrm.datovatenexuspro.com/admin/agent-test"
HEADERS = {"x-admin-key": "ferreinox_admin_2024", "Content-Type": "application/json"}
CONV_ID = 88880
PHONE = "+573000088880"

shared_ctx = {}
shared_msgs = []

def send(msg, label=""):
    global shared_ctx, shared_msgs
    payload = {
        "profile_name": "Angela Test",
        "conversation_context": shared_ctx,
        "recent_messages": shared_msgs,
        "user_message": msg,
        "context": {
            "conversation_id": CONV_ID,
            "contact_id": CONV_ID,
            "cliente_id": None,
            "telefono_e164": PHONE,
            "nombre_visible": "Angela Test",
        },
    }
    print(f"\n{'='*60}")
    print(f"[CLIENTE] {msg}")
    if label:
        print(f"--- TEST: {label} ---")
    print(f"{'='*60}")
    
    t0 = time.time()
    resp = requests.post(URL, headers=HEADERS, json=payload, timeout=180)
    elapsed = time.time() - t0
    data = resp.json().get("result", {})
    
    tools = [tc["name"] for tc in (data.get("tool_calls") or [])]
    resp_text = data.get("response_text", "")
    
    print(f"[FERRO] ({elapsed:.1f}s) Tools: {tools}")
    print(f"[FERRO] {resp_text[:500]}")
    
    # Update shared context
    shared_ctx = data.get("conversation_context") or shared_ctx
    shared_msgs.append({"direction": "inbound", "contenido": msg})
    shared_msgs.append({"direction": "outbound", "contenido": resp_text[:300]})
    
    return data

# ── TEST 1: Diagnostic guard for generic question ──
r1 = send("hola, necesito saber como pintar un piso", "GUARDIA DIAGNOSTICA")
t1_lower = (r1.get("response_text", "") or "").lower()
t1_asked = "?" in t1_lower
t1_system = sum(1 for kw in ["imprimante", "acabado", "interseal", "intergard", "sistema completo", "pintucoat"] if kw in t1_lower) >= 2
print(f"\n>>> T1: {'✅ PREGUNTÓ' if t1_asked and not t1_system else '❌ DIO SISTEMA' if t1_system else '⚠️ INDETERMINADO'}")

# ── TEST 2: Client gives details → should recommend ──
r2 = send("es de tráfico pesado en una bodega interior, unos 200 metros cuadrados", "RECOMENDAR CON DATOS")
t2_lower = (r2.get("response_text", "") or "").lower()
t2_has_product = any(kw in t2_lower for kw in ["interseal", "intergard", "pintucoat", "koraza"])
t2_has_link = "ferreinox.co" in t2_lower
print(f"\n>>> T2: Producto={'✅' if t2_has_product else '❌'} | Link={'✅' if t2_has_link else '❌'}")

# ── TEST 3: Client says "cotizame" → prices ──
r3 = send("puedes cotizarme todo?", "COTIZACIÓN")
t3_lower = (r3.get("response_text", "") or "").lower()
t3_has_prices = "$" in (r3.get("response_text", "") or "")
print(f"\n>>> T3: Precios={'✅' if t3_has_prices else '❌'}")

# ── TEST 4: Client confirms → should NOT repeat quote ──
r4 = send("si por favor, quiero hacer el pedido", "CONFIRMACIÓN SIN REPETIR")
t4_lower = (r4.get("response_text", "") or "").lower()
t4_repeated_quote = "$" in (r4.get("response_text", "") or "") and "total" in t4_lower
t4_asks_data = any(kw in t4_lower for kw in ["nombre", "cédula", "nit", "cedula", "dirección", "direccion"])
t4_tools = [tc["name"] for tc in (r4.get("tool_calls") or [])]
print(f"\n>>> T4: Repitió cotización={'❌ SÍ' if t4_repeated_quote else '✅ NO'} | Pide datos={'✅' if t4_asks_data else '❌'}")

# ── TEST 5: Client gives identity → should try verification then register ──
r5 = send("Angela Maria Contreras, cédula 41961744, enviar a Cra 15 #23-45 Pereira", "REGISTRO CLIENTE NUEVO")
t5_tools = [tc["name"] for tc in (r5.get("tool_calls") or [])]
t5_lower = (r5.get("response_text", "") or "").lower()
t5_registered = "registrar_cliente_nuevo" in t5_tools
t5_verified = "verificar_identidad" in t5_tools
print(f"\n>>> T5: verificar={'✅' if t5_verified else '❌'} | registrar={'✅' if t5_registered else '❌'} | Tools={t5_tools}")

print("\n" + "="*60)
print("RESUMEN EMBUDO DE CIERRE")
print("="*60)
print(f"T1 Guardia diagnóstica: {'✅' if t1_asked and not t1_system else '❌'}")
print(f"T2 Recomendación con datos: {'✅' if t2_has_product else '❌'}")
print(f"T3 Cotización con precios: {'✅' if t3_has_prices else '❌'}")
print(f"T4 No repitió + pidió datos: {'✅' if not t4_repeated_quote and t4_asks_data else '❌'}")
print(f"T5 Registro cliente nuevo: {'✅' if t5_registered else '❌'}")
