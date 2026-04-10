import requests, json

ADMIN_KEY = "ferreinox_admin_2024"
RAG_URL = "https://apicrm.datovatenexuspro.com/admin/rag-buscar"

queries = [
    ("pintura para canchas usos aplicacion donde se usa", 3),
    ("pintucoat uso recomendado aplicacion", 3),
    ("pintura trafico piso concreto garaje", 3),
    ("piso garaje residencial pintura recomendada", 3),
]

for q, top in queries:
    print(f"\n{'='*80}")
    print(f"QUERY: {q}")
    print("="*80)
    resp = requests.get(RAG_URL, params={"q": q, "top_k": top}, headers={"x-admin-key": ADMIN_KEY}, timeout=120)
    data = resp.json()
    print(f"Candidatos: {data.get('productos_candidatos', [])}")
    for i, r in enumerate(data.get("resultados", [])):
        print(f"\n  [{r['familia']}] sim={r['similitud']:.3f}")
        print(f"  {r['texto'][:500]}")
    print()
