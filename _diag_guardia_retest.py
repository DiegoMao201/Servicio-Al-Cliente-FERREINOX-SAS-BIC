"""Quick retest: does the guardia diagnostica now fire for 'piso trafico pesado'?"""
import requests, json

URL = "https://apicrm.datovatenexuspro.com/admin/agent-test"
HEADERS = {"x-admin-key": "ferreinox_admin_2024", "Content-Type": "application/json"}

payload = {
    "profile_name": "Test Guardia",
    "conversation_context": {},
    "recent_messages": [],
    "user_message": "necesito pintar un piso de tráfico pesado",
    "context": {
        "conversation_id": 99996,
        "contact_id": 99996,
        "cliente_id": None,
        "telefono_e164": "+573000000003",
        "nombre_visible": "Test Guardia",
    },
}
resp = requests.post(URL, headers=HEADERS, json=payload, timeout=120)
data = resp.json().get("result", {})

tools = [tc["name"] for tc in (data.get("tool_calls") or [])]
print(f"Tools: {tools}")
print()

resp_text = data.get("response_text", "")
print(f"RESPONSE:\n{resp_text[:600]}")
print()

# Check
lower = resp_text.lower()
asked = any(w in lower for w in ["metros cuadrados", "m²", "interior", "exterior", "superficie", "área", "cuántos", "cuantos", "?"])
gave_system = sum(1 for kw in ["imprimante", "acabado", "interseal", "intergard", "sistema"] if kw in lower) >= 2

if asked and not gave_system:
    print("RESULTADO: ✅ GUARDIA FUNCIONÓ — preguntó sin recomendar")
elif asked and gave_system:
    print("RESULTADO: ⚠️ Preguntó pero TAMBIÉN recomendó")
else:
    print("RESULTADO: ❌ NO PREGUNTÓ — recomendó directo (guardia falló)")
