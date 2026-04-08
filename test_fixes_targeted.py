"""
Quick targeted test for the 4 conversations with WARN/FAIL issues.
Runs only relevant turns to validate the prompt fixes without exhausting OpenAI quota.
"""
import json, os, sys, time, re
import requests

BACKEND_URL = os.environ.get("BACKEND_URL", "https://apicrm.datovatenexuspro.com")
ADMIN_KEY = os.environ.get("ADMIN_API_KEY", "ferreinox_admin_2024")
AGENT_URL = f"{BACKEND_URL.rstrip('/')}/admin/agent-test"

def normalize(s):
    return (s.lower()
            .replace("á","a").replace("é","e").replace("í","i")
            .replace("ó","o").replace("ú","u").replace("ñ","n"))

def call_agent(conv_id, recent_msgs, user_msg):
    resp = requests.post(
        AGENT_URL,
        headers={"x-admin-key": ADMIN_KEY, "Content-Type": "application/json"},
        json={
            "profile_name": "Test User",
            "conversation_context": {},
            "recent_messages": recent_msgs,
            "user_message": user_msg,
            "context": {"conversation_id": conv_id, "contact_id": conv_id,
                        "cliente_id": None, "telefono_e164": "+573001234567",
                        "nombre_visible": "Test User"},
        },
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("error"):
        raise RuntimeError(data["error"])
    return data.get("result", {})

def check(result, required_words=None, required_tools=None, forbidden_tools=None):
    text = result.get("response_text", "")
    tools = [tc["name"] for tc in result.get("tool_calls", [])]
    txt_norm = normalize(text)
    
    ok = True
    issues = []
    preview = text[:250].replace("\n", " ↵ ")
    print(f"  Response: \"{preview}\"")
    print(f"  Tools: {tools or '—'}")
    
    if required_words:
        for w in required_words:
            if normalize(w) not in txt_norm:
                issues.append(f"MISSING: '{w}'")
                ok = False
    
    if required_tools:
        for t in required_tools:
            if t not in tools:
                issues.append(f"TOOL_NOT_CALLED: '{t}'")
                ok = False
    
    if forbidden_tools:
        for t in forbidden_tools:
            if t in tools:
                issues.append(f"FORBIDDEN_TOOL: '{t}'")
                ok = False
    
    for issue in issues:
        print(f"  ❌ {issue}")
    
    if ok:
        print(f"  ✅ PASS")
    return ok

TESTS = [
    # Conv 1 Turn 2: Techo → debe preguntar sobre material con palabras exactas
    {
        "id": "Conv1-T2 Techo diagnosis",
        "conv_id": 9001,
        "prior": [
            {"direction":"inbound","contenido":"Hola buenas tardes","message_type":"text"},
            {"direction":"outbound","contenido":"¡Buenas tardes! ¿En qué te puedo ayudar?","message_type":"text"},
        ],
        "message": "Necesito pintar un techo por fuera",
        "required_words": ["concreto", "fibrocemento", "eternit", "plancha"],
        "req_tools": None,
        "forb_tools": ["consultar_inventario"],
    },
    # Conv 3 Turn 1: Garaje → debe preguntar con 6 palabras clave
    {
        "id": "Conv3-T1 Piso garaje diagnosis",
        "conv_id": 9003,
        "prior": [],
        "message": "Necesito pintar el piso de un garaje de la casa",
        "required_words": ["tráfico", "pesado", "peatonal", "residencial", "industrial", "montacargas"],
        "req_tools": None,
        "forb_tools": ["consultar_inventario"],
    },
    # Conv 3 Turn 2: Respuesta sobre piso liviano → mencionar AMBOS Canchas y Pintucoat
    {
        "id": "Conv3-T2 Piso respuesta con Canchas+Pintucoat",
        "conv_id": 9003,
        "prior": [
            {"direction":"inbound","contenido":"Necesito pintar el piso de un garaje de la casa","message_type":"text"},
            {"direction":"outbound","contenido":"¿El piso tiene tráfico industrial pesado (montacargas, camiones) o es uso residencial/peatonal?","message_type":"text"},
        ],
        "message": "Es tráfico liviano, solo carros livianos de la casa",
        "required_words": ["Canchas", "Pintucoat"],
        "req_tools": ["consultar_conocimiento_tecnico"],
        "forb_tools": None,
    },
    # Conv 4 Turn 1: Rejas oxidadas → debe preguntar sobre profundidad con palabras exactas
    {
        "id": "Conv4-T1 Metal óxido diagnosis",
        "conv_id": 9004,
        "prior": [],
        "message": "Tengo unas rejas muy oxidadas, se las está comiendo el óxido",
        "required_words": ["óxido", "profund", "superficial"],
        "req_tools": None,
        "forb_tools": ["consultar_inventario"],
    },
    # Conv 6 Turn 1: Pérgola → debe preguntar sobre veta/transparente/color
    {
        "id": "Conv6-T1 Madera diagnosis",
        "conv_id": 9006,
        "prior": [],
        "message": "Tengo una pérgola de madera que está a la intemperie y quiero protegerla",
        "required_words": ["transparente", "color", "veta", "exterior", "interior"],
        "req_tools": None,
        "forb_tools": ["consultar_inventario"],
    },
    # Conv 6 Turn 2: Veta transparente → DEBE llamar consultar_conocimiento_tecnico, NO inventario primero
    {
        "id": "Conv6-T2 Madera veta → conocimiento_tecnico + Barnex+Wood Stain",
        "conv_id": 9006,
        "prior": [
            {"direction":"inbound","contenido":"Tengo una pérgola de madera que está a la intemperie y quiero protegerla","message_type":"text"},
            {"direction":"outbound","contenido":"¿La madera es exterior (al aire libre) o interior? ¿Quieres que se vea la veta natural (acabado transparente) o prefieres un color sólido?","message_type":"text"},
        ],
        "message": "Quiero que se vea la veta de la madera, acabado transparente",
        "required_words": ["Barnex", "Wood Stain"],
        "req_tools": ["consultar_conocimiento_tecnico"],
        "forb_tools": None,
    },
]

def main():
    print("=" * 70)
    print("TEST DE FIXES DIRIGIDOS — Verificando 6 casos WARNed/FAILed")
    print("=" * 70)
    
    passed = 0
    failed = 0
    
    for t in TESTS:
        print(f"\n{'─' * 70}")
        print(f"🔍 {t['id']}")
        print(f"   Mensaje: \"{t['message']}\"")
        try:
            t0 = time.time()
            result = call_agent(t["conv_id"], t["prior"], t["message"])
            elapsed = int((time.time() - t0) * 1000)
            print(f"  [{elapsed}ms]")
            ok = check(result,
                       required_words=t.get("required_words"),
                       required_tools=t.get("req_tools"),
                       forbidden_tools=t.get("forb_tools"))
            if ok:
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"  💥 ERROR: {e}")
            failed += 1
        time.sleep(2)  # rate limit guard
    
    print(f"\n{'=' * 70}")
    print(f"RESULTADO: ✅ {passed}/{passed+failed} PASS  ❌ {failed}/{passed+failed} FAIL")
    print("=" * 70)

if __name__ == "__main__":
    main()
