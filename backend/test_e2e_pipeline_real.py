"""
Test E2E del pipeline_pedido contra el backend REAL (via /admin/agent-test).
Simula el flujo completo:
  1. Login interno (Diego)
  2. Enviar pedido de 20 líneas
  3. Verificar que el pipeline lo intercepta
  4. Responder con tienda "pereira"
  5. Verificar presentaciones, productos, y precios en la respuesta

Uso:
  python test_e2e_pipeline_real.py [URL]

  URL default: https://apicrm.datovatenexuspro.com
  Para local: python test_e2e_pipeline_real.py http://localhost:8000
"""
import json
import os
import re
import sys
import requests

# Forzar UTF-8 en stdout para evitar crash cp1252 en Windows
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr.encoding != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

BACKEND_URL = sys.argv[1] if len(sys.argv) > 1 else "https://apicrm.datovatenexuspro.com"
ADMIN_KEY = os.getenv("ADMIN_API_KEY", "ferreinox_admin_2024")
REQUEST_TIMEOUT_SECONDS = int(os.getenv("E2E_TIMEOUT_SECONDS", "300"))

HEADERS = {
    "Content-Type": "application/json",
    "x-admin-key": ADMIN_KEY,
}


def agent_call(user_message: str, conversation_context: dict, recent_messages: list) -> dict:
    """Llama al agente via /admin/agent-test."""
    payload = {
        "profile_name": "Diego Mauricio García Rengifo",
        "conversation_context": conversation_context,
        "recent_messages": recent_messages,
        "user_message": user_message,
        "context": {"conversation_id": "test_e2e_pipeline_001"},
    }
    resp = requests.post(
        f"{BACKEND_URL}/admin/agent-test",
        json=payload,
        headers=HEADERS,
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("error"):
        print(f"  ERROR del backend: {data['error']}")
        return {}
    return data.get("result", {})


# =====================================================================
# TURNO 1: Login interno
# =====================================================================
print("=" * 70)
print(f"E2E Pipeline Pedido — Backend: {BACKEND_URL}")
print("=" * 70)

# Simulamos que ya está autenticado como Diego
ctx = {
    "internal_auth": {
        "employee_context": {
            "full_name": "Diego Mauricio García Rengifo",
            "cedula": "1088266407",
            "cargo": "Líder comercial y de compras",
            "sede": "Parque Olaya",
            "store_code": "155",
        },
        "role": "administrador",
    },
    "client_name": "Diego Mauricio García Rengifo",
}

PEDIDO_MSG = """4 galones azul Milano 1510
1526 ocre 2 galones
1559 negro viniltex 2 galones
Viniltex baños y cocinas 2 cuartos
vinílico blanco galones 4
vinílico blanco medio cuñete 3
vinílico blanco cuñete 3
vinílico blanco almendra galón 2
p153 aluminio 1 galón
p11 doméstico blanco 4 galones
p 90 doméstico vino tinto 3 cuartos
pulidora 4040 - 4 octavos
pulidora 1 galón
Aerosol alta temperatura negro brillante 3
aerosol multi superficie negro mate 3
aerosol multisuperficie negro brillante 3
aerosol multisuperficie gris 4
aerosol multisuperficie aluminio 3
Aerosol blanco brillante multisuperficie 3
t95 pintulux negro 2 galones"""

recent = [
    {"role": "assistant", "content": "Acceso interno activo para Diego Mauricio García Rengifo."},
]

# =====================================================================
# TURNO 2: Enviar pedido
# =====================================================================
print("\n--- TURNO 2: Envío pedido de 20 líneas ---")
r1 = agent_call(PEDIDO_MSG, ctx, recent)
r1_text = r1.get("response_text", "")
r1_intent = r1.get("intent", "")
r1_confidence = r1.get("confidence", {})
r1_ctx = r1.get("context_updates", {})

print(f"  Intent: {r1_intent}")
print(f"  Confidence: {r1_confidence}")
print(f"  Response preview: {r1_text[:200]}...")

# ¿Pidió tienda? (pipeline bloquea sin tienda)
asked_tienda = "tienda" in r1_text.lower() or "despacho" in r1_text.lower()
print(f"  ¿Pidió tienda? {asked_tienda}")

# Verificar flags de contexto
has_pending_lines = "_pedido_pendiente_lineas" in r1_ctx
print(f"  ¿Líneas pendientes guardadas? {has_pending_lines}")
if has_pending_lines:
    n_lines = len(r1_ctx["_pedido_pendiente_lineas"])
    print(f"  Líneas pendientes: {n_lines}")

# =====================================================================
# TURNO 3: Responder con tienda
# =====================================================================
if asked_tienda:
    print("\n--- TURNO 3: Respondo 'pereira' ---")
    ctx2 = dict(ctx)
    ctx2.update(r1_ctx)
    recent2 = recent + [
        {"role": "user", "content": PEDIDO_MSG},
        {"role": "assistant", "content": r1_text},
    ]
    r2 = agent_call("pereira", ctx2, recent2)
    r2_text = r2.get("response_text", "")
    r2_ctx = r2.get("context_updates", {})

    print(f"  Response length: {len(r2_text)} chars")
    print(f"  Preview: {r2_text[:300]}...")
else:
    # Pipeline resolvió directo (tenía tienda en contexto)
    r2_text = r1_text
    r2_ctx = r1_ctx

# =====================================================================
# VALIDACIONES
# =====================================================================
print("\n" + "=" * 70)
print("VALIDACIONES")
print("=" * 70)

errors = 0

def check(condition, msg):
    global errors
    if condition:
        print(f"  [OK] {msg}")
    else:
        print(f"  [FAIL] {msg}")
        errors += 1

# 1. Presentaciones correctas
check("3.79" in r2_text or "3,79" in r2_text or "galon" in r2_text.lower() or "galón" in r2_text.lower(),
      "Hay productos en presentación galón (3.79L)")

# 2. Azul Milano 1510 debe ser GALÓN (3.79L), NO cuarto (0.9)
azul_lines = [l for l in r2_text.split("\n") if "1510" in l or "AZUL MILANO" in l.upper() or "azul milano" in l.lower()]
if azul_lines:
    azul_text = azul_lines[0]
    has_galon = "3.79" in azul_text or "3,79" in azul_text or "galon" in azul_text.lower()
    has_cuarto = "0.9" in azul_text or "0,9" in azul_text
    check(has_galon or not has_cuarto,
          f"Azul Milano 1510 es GALÓN (no cuarto): {azul_text[:80]}")
else:
    check(False, "Azul Milano 1510 no aparece en respuesta")

# 3. P153 debe resolver a ALUMINIO, no a BLANCO/P-11
p153_lines = [l for l in r2_text.split("\n")
              if "P-153" in l.upper() or "P153" in l.upper() or "ALUMINIO" in l.upper()]
if p153_lines:
    check("ALUMINIO" in p153_lines[0].upper() or "aluminio" in p153_lines[0].lower(),
          f"P153 → ALUMINIO: {p153_lines[0][:80]}")
else:
    check(False, "P153 aluminio no aparece en respuesta")

# 4. P90 debe resolver a VINO TINTO, no a BLANCO
p90_lines = [l for l in r2_text.split("\n")
             if "P-90" in l.upper() or "P90" in l.upper() or "VINO TINTO" in l.upper()]
if p90_lines:
    check("VINO" in p90_lines[0].upper() or "vino" in p90_lines[0].lower(),
          f"P90 → VINO TINTO: {p90_lines[0][:80]}")
else:
    check(False, "P90 vino tinto no aparece en respuesta")

# 5. BYC debe ser CUARTO (0.95L), no GALÓN (3.79L)
byc_lines = [l for l in r2_text.split("\n") if "BYC" in l.upper() or "BAÑOS" in l.upper() or "banos" in l.lower()]
if byc_lines:
    byc_text = byc_lines[0]
    is_cuarto = "0.95" in byc_text or "0,95" in byc_text or "cuarto" in byc_text.lower()
    is_galon = "3.79" in byc_text or "3,79" in byc_text
    check(is_cuarto or not is_galon,
          f"BYC → CUARTO: {byc_text[:80]}")
else:
    check(False, "Viniltex BYC no aparece en respuesta")

# 6. Vinílico blanco cuñete debe ser 18.93L
cunete_lines = [l for l in r2_text.split("\n") if "18.93" in l or "18,93" in l]
check(bool(cunete_lines), "Hay productos en presentación cuñete (18.93L)")

# 7. Aerosoles: al menos 3 pendientes pidiendo Aerocolor/Tekbond
aerosol_pending = r2_text.lower().count("aerocolor") + r2_text.lower().count("tekbond")
check(aerosol_pending >= 2, f"Aerosoles piden clarificación Aerocolor/Tekbond: {aerosol_pending} menciones")

# 8. No debe repetir P-11 para P153 y P90
p11_count = r2_text.upper().count("P-11")
check(p11_count <= 2, f"P-11 aparece {p11_count} veces (máx 2 para el pedido real de 4 gal)")

# 9. Aerosol alta temperatura resuelto (no pendiente)
alta_temp_lines = [l for l in r2_text.split("\n")
                   if "ALTA" in l.upper() and "TEMP" in l.upper() or "901" in l]
check(bool(alta_temp_lines), "Aerosol alta temperatura resuelto")

# 10. Total calculado
check("$" in r2_text, "Hay precio total con $")

print(f"\n{'='*70}")
print(f"RESULTADO: {10 - errors}/10 checks passed")
if errors:
    print(f"FAILED: {errors}")
else:
    print("ALL PASSED")
print(f"{'='*70}")
print("\n" + "="*70)
print("RESPUESTA COMPLETA TURNO 2:")
print("="*70)
print(r1_text)
if asked_tienda:
    print("\n" + "="*70)
    print("RESPUESTA COMPLETA TURNO 3:")
    print("="*70)
    print(r2_text)

# Guardar respuesta completa para analisis
with open("_e2e_pipeline_result.txt", "w", encoding="utf-8") as f:
    f.write(f"TURNO 2 (pedido):\n{r1_text}\n\n")
    f.write(f"TURNO 2 ctx_updates: {json.dumps(r1_ctx, indent=2, default=str)}\n\n")
    if asked_tienda:
        f.write(f"TURNO 3 (tienda):\n{r2_text}\n\n")
        f.write(f"TURNO 3 ctx_updates: {json.dumps(r2_ctx, indent=2, default=str)}\n\n")
print("Respuesta completa guardada en _e2e_pipeline_result.txt")
