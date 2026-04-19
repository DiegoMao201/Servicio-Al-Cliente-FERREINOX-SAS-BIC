import json

for section in [1]:
    fname = f"guias_solucion_seccion_{section}_humedad.json"
    data = json.load(open(fname, "r", encoding="utf-8"))
    print(f"OK {fname}: {len(data)} guias")
    for g in data:
        print(f"  {g['id']}: {g['titulo']}")
        kw = g.get("palabras_clave_cliente", [])
        print(f"    Keywords: {len(kw)}")
