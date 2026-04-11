"""Check raw inventory output for a specific product."""
import requests, json

URL = "https://apicrm.datovatenexuspro.com/admin/agent-test"
HEADERS = {"x-admin-key": "ferreinox_admin_2024", "Content-Type": "application/json"}

payload = {
    "profile_name": "Test Precio",
    "conversation_context": {},
    "recent_messages": [],
    "user_message": "precio de Intergard 2002 galon",
    "context": {
        "conversation_id": 99995,
        "contact_id": 99995,
        "cliente_id": None,
        "telefono_e164": "+573000000002",
        "nombre_visible": "Test Precio",
    },
}
resp = requests.post(URL, headers=HEADERS, json=payload, timeout=120)
data = resp.json().get("result", {})

for tc in (data.get("tool_calls") or []):
    name = tc["name"]
    args = json.dumps(tc.get("args", {}), ensure_ascii=False)
    print(f"TOOL: {name}")
    print(f"  args: {args}")
    raw = tc.get("result", "")
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except Exception:
            print(f"  raw: {raw[:200]}")
            continue
        if name in ("consultar_inventario", "consultar_inventario_lote"):
            prods = parsed.get("resultados") or parsed.get("productos") or []
            print(f"  encontrados: {parsed.get('encontrados', len(prods))}")
            for p in prods[:3]:
                print(f"  ---PRODUCT---")
                print(json.dumps(p, ensure_ascii=False, indent=2)[:1000])
        elif name == "consultar_conocimiento_tecnico":
            print(f"  encontrado: {parsed.get('encontrado')}")
            print(f"  similitud: {parsed.get('mejor_similitud')}")

print()
print("RESPONSE (400ch):", (data.get("response_text", ""))[:400])
