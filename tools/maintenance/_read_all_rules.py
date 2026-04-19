import json, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

rules = json.load(open("reglas_experto_ferreinox.json", "r", encoding="utf-8"))
# All rules not already printed
skip = {6, 7, 52, 53, 58, 59, 60, 61, 62, 63}
for r in rules:
    rid = r["id"]
    if rid in skip:
        continue
    print(f"=== REGLA #{rid} [{r['tipo']}] ===")
    print(f"Tags: {r['contexto_tags']}")
    print(f"Recomendar: {r.get('producto_recomendado', '-')}")
    print(f"Evitar: {r.get('producto_desestimado', '-')}")
    print(f"Nota: {r.get('nota_comercial', '')}")
    print()
