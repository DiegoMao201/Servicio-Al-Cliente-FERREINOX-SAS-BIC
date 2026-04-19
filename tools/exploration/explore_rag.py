"""
Explorar CAT_PRODUCTO via admin API y construir mapa completo del portafolio.
"""
import requests, json, collections

BACKEND_URL = "https://apicrm.datovatenexuspro.com"
ADMIN_KEY = "ferreinox_admin_2024"
headers = {"x-admin-key": ADMIN_KEY, "Content-Type": "application/json"}

# Use admin SQL endpoint or rag search to probe categories
# First try: call rag-buscar with broad queries to discover products
queries = [
    "portafolio completo ferreinox",
    "anticorrosivo metal reja",
    "vinilo muro interior",
    "esmalte alquidico exterior",
    "impermeabilizante techo",
    "piso concreto industrial",
    "barniz madera exterior",
    "poliuretano industrial",
    "epoxica piso",
    "disolvente thinner varsol",
    "lija abrasivo",
    "removedor pintura",
    "imprimante sellador",
    "tráfico demarcación",
    "pintura madera color",
    "humedad filtración estuco",
    "Sika sikaflex",
    "Yale Abracol",
    "Goya Mega ferretería",
    "silicona sellante",
]

print("=== RAG QUERY PROBE ===\n")
for q in queries:
    r = requests.post(
        f"{BACKEND_URL}/admin/rag-buscar",
        headers=headers,
        json={"query": q, "top_k": 5},
        timeout=15
    )
    if r.status_code == 200:
        data = r.json()
        resultados = data.get("resultados", [])
        categories = [x.get("categoria","?") for x in resultados]
        productos = [x.get("producto","?") for x in resultados]
        print(f"Q: {q!r}")
        print(f"   productos: {productos[:5]}")
        print()
    else:
        print(f"Q: {q!r} -> ERROR {r.status_code}")
