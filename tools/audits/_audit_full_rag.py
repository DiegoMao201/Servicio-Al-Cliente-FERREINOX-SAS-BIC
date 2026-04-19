"""
AUDITORÍA COMPLETA: Verificación de recomendaciones de producto vs RAG real.
Genera ~50 escenarios realistas (superficie + contexto) y verifica que el RAG
devuelve productos coherentes con lo que el prompt/mappings recomendarían.
"""
import requests, json, time, re, sys

ADMIN_KEY = "ferreinox_admin_2024"
RAG_URL = "https://apicrm.datovatenexuspro.com/admin/rag-buscar"

# ── 50 escenarios realistas con superficie + contexto ──
# Cada escenario tiene: query, productos_correctos_esperados, productos_prohibidos, notas
SCENARIOS = [
    # ═══ PISOS: contexto determina producto ═══
    {"q": "pintar piso garaje residencial carros livianos", "ok": ["pintucoat"], "bad": ["pintura canchas", "koraza"], "cat": "piso"},
    {"q": "piso cancha de baloncesto escenario deportivo", "ok": ["pintura canchas"], "bad": ["pintucoat", "koraza"], "cat": "piso"},
    {"q": "sendero peatonal concreto parque", "ok": ["pintura canchas"], "bad": ["pintucoat", "intergard"], "cat": "piso"},
    {"q": "cicloruta asfalto exterior", "ok": ["pintura canchas"], "bad": ["pintucoat"], "cat": "piso"},
    {"q": "piso bodega con montacargas pesados", "ok": ["intergard 2002", "intergard"], "bad": ["pintura canchas"], "cat": "piso"},
    {"q": "piso fábrica tráfico pesado estibadores", "ok": ["intergard 2002", "intergard"], "bad": ["pintura canchas", "pintucoat"], "cat": "piso"},
    {"q": "piso parqueadero centro comercial vehículos", "ok": ["pintucoat"], "bad": ["pintura canchas"], "cat": "piso"},
    {"q": "rampa vehicular edificio estacionamiento", "ok": ["pintucoat"], "bad": ["pintura canchas"], "cat": "piso"},
    {"q": "andén entrada casa concreto", "ok": ["pintucoat"], "bad": ["koraza", "viniltex"], "cat": "piso"},
    {"q": "piso industrial planta alimentos químicos", "ok": ["pintucoat", "intergard"], "bad": ["pintura canchas", "viniltex"], "cat": "piso"},

    # ═══ MADERA: interior vs exterior, veta vs color sólido ═══
    {"q": "mesa de madera interior acabado transparente", "ok": ["pintulac", "barniz"], "bad": ["barnex", "koraza", "viniltex"], "cat": "madera"},
    {"q": "pérgola madera exterior intemperie proteger veta", "ok": ["barnex", "wood stain"], "bad": ["pintulac", "koraza", "viniltex"], "cat": "madera"},
    {"q": "puerta madera interior color blanco", "ok": ["pintulux", "esmalte"], "bad": ["barnex", "koraza"], "cat": "madera"},
    {"q": "deck madera exterior piscina sol lluvia", "ok": ["barnex", "wood stain"], "bad": ["pintulac", "viniltex"], "cat": "madera"},
    {"q": "closet madera interior acabado natural", "ok": ["pintulac", "barniz"], "bad": ["barnex", "koraza"], "cat": "madera"},
    {"q": "cerca madera finca exterior intemperie", "ok": ["barnex", "wood stain"], "bad": ["pintulac"], "cat": "madera"},
    {"q": "mueble cocina madera laca brillante", "ok": ["pintulac", "barniz", "laca"], "bad": ["barnex", "koraza"], "cat": "madera"},

    # ═══ METAL: nuevo vs oxidado, galvanizado, interior vs exterior ═══
    {"q": "reja hierro nueva sin pintar exterior", "ok": ["corrotec", "anticorrosivo", "pintulux"], "bad": ["viniltex", "koraza", "pintucoat"], "cat": "metal"},
    {"q": "reja vieja muy oxidada óxido profundo", "ok": ["corrotec", "pintoxido", "anticorrosivo"], "bad": ["viniltex", "koraza"], "cat": "metal"},
    {"q": "estructura acero galvanizado nueva", "ok": ["wash primer", "corrotec"], "bad": ["viniltex", "pintucoat", "koraza"], "cat": "metal"},
    {"q": "tubería metálica industrial exterior", "ok": ["corrotec", "intergard", "anticorrosivo"], "bad": ["viniltex", "koraza"], "cat": "metal"},
    {"q": "portón metálico casa exterior", "ok": ["corrotec", "pintulux", "anticorrosivo"], "bad": ["viniltex", "koraza"], "cat": "metal"},
    {"q": "silla metálica exterior jardín oxidada", "ok": ["corrotec", "pintoxido", "pintulux"], "bad": ["viniltex", "koraza", "pintucoat"], "cat": "metal"},
    {"q": "tanque metálico almacenamiento industrial", "ok": ["corrotec", "intergard", "anticorrosivo"], "bad": ["viniltex"], "cat": "metal"},
    {"q": "barandal escalera hierro interior", "ok": ["corrotec", "pintulux", "anticorrosivo"], "bad": ["koraza", "viniltex"], "cat": "metal"},

    # ═══ MUROS: interior vs exterior, humedad vs decorativo ═══
    {"q": "pintar sala casa interior calidad premium", "ok": ["viniltex"], "bad": ["koraza", "pintucoat"], "cat": "interior"},
    {"q": "pintar habitación interior económico", "ok": ["pinturama", "intervinil", "vinil"], "bad": ["koraza", "pintucoat"], "cat": "interior"},
    {"q": "pintar fachada casa exterior lluvia sol", "ok": ["koraza"], "bad": ["viniltex", "pintucoat", "aquablock"], "cat": "exterior"},
    {"q": "muro interior con humedad salitre blanco filtrando", "ok": ["aquablock"], "bad": ["koraza", "viniltex", "pintucoat"], "cat": "humedad"},
    {"q": "baño con hongos negros humedad paredes", "ok": ["aquablock", "viniltex"], "bad": ["koraza", "pintucoat"], "cat": "humedad"},
    {"q": "pared exterior descascarando lluvia directa", "ok": ["koraza"], "bad": ["aquablock", "viniltex", "pintucoat"], "cat": "exterior"},
    {"q": "cielo raso bodega económico", "ok": ["pinturama", "intervinil", "vinil", "viniltex"], "bad": ["koraza", "pintucoat"], "cat": "interior"},
    {"q": "acabado satinado pared interior elegante", "ok": ["viniltex", "acriltex"], "bad": ["koraza", "pintucoat", "pinturama"], "cat": "interior"},

    # ═══ TECHOS / IMPERMEABILIZACIÓN ═══
    {"q": "terraza con goteras filtra agua lluvia", "ok": ["pintuco fill", "impercoat"], "bad": ["koraza", "viniltex", "pintucoat"], "cat": "techo"},
    {"q": "techo eternit fibrocemento cubierta", "ok": ["pintuco fill", "koraza"], "bad": ["viniltex", "pintucoat", "aquablock"], "cat": "techo"},
    {"q": "losa concreto terraza impermeabilizar", "ok": ["pintuco fill", "impercoat"], "bad": ["viniltex", "pintucoat"], "cat": "techo"},
    {"q": "cubierta plana edificio goteras grietas", "ok": ["pintuco fill", "impercoat"], "bad": ["koraza solo", "viniltex"], "cat": "techo"},

    # ═══ CASOS AMBIGUOS: contexto define todo ═══
    {"q": "pintar mesa metálica jardín exterior oxidada", "ok": ["corrotec", "pintoxido", "pintulux"], "bad": ["barnex", "pintulac", "viniltex"], "cat": "ambiguo"},
    {"q": "pintar mesa madera comedor interior", "ok": ["pintulac", "barniz", "pintulux"], "bad": ["barnex", "koraza", "corrotec"], "cat": "ambiguo"},
    {"q": "pintar silla plástica jardín", "ok": ["aerocolor"], "bad": ["viniltex", "koraza", "corrotec"], "cat": "ambiguo"},
    {"q": "proteger piso concreto taller mecánico aceite grasa", "ok": ["pintucoat", "intergard"], "bad": ["pintura canchas", "viniltex"], "cat": "ambiguo"},
    {"q": "señalización líneas amarillas parqueadero piso", "ok": ["pintutraf", "pintura trafico"], "bad": ["viniltex", "koraza"], "cat": "ambiguo"},
    {"q": "demarcación vial carretera pavimento", "ok": ["pintutraf", "pintura trafico"], "bad": ["pintura canchas", "viniltex"], "cat": "ambiguo"},

    # ═══ INDUSTRIAL / INTERNATIONAL ═══
    {"q": "estructura metálica nave industrial protección fuego", "ok": ["interchar"], "bad": ["viniltex", "koraza", "pintucoat"], "cat": "industrial"},
    {"q": "acabado poliuretano sobre epóxica maquinaria", "ok": ["interthane", "interfine"], "bad": ["pintulux", "viniltex"], "cat": "industrial"},
    {"q": "piso industrial alto desempeño brillante", "ok": ["intergard 740", "intergard"], "bad": ["pintura canchas", "viniltex"], "cat": "industrial"},
    {"q": "ambiente marino salino estructura costera acero", "ok": ["intergard", "interseal", "corrotec"], "bad": ["viniltex", "pintura canchas"], "cat": "industrial"},
    {"q": "pared planta procesadora alimentos limpieza constante", "ok": ["pintucoat", "intergard", "epoxica"], "bad": ["viniltex", "koraza", "pintura canchas"], "cat": "industrial"},

    # ═══ GAPS / PRODUCTOS QUE NO VENDEMOS ═══
    {"q": "pintura especial para piscina de concreto", "ok": ["__gap__"], "bad": ["pintucoat", "aquablock", "pintuco fill"], "cat": "gap"},
    {"q": "pintura para tanque de agua potable inmersión", "ok": ["__gap__"], "bad": ["pintucoat", "aquablock"], "cat": "gap"},
]

def query_rag(q, top_k=5, retries=2):
    for attempt in range(retries + 1):
        try:
            resp = requests.get(RAG_URL, params={"q": q, "top_k": top_k},
                              headers={"x-admin-key": ADMIN_KEY}, timeout=120)
            return resp.json()
        except Exception as e:
            if attempt < retries:
                time.sleep(5)
            else:
                return {"error": str(e), "productos_candidatos": [], "resultados": []}

def normalize(text):
    return re.sub(r'[^a-záéíóúñü0-9\s]', '', text.lower().strip())

def check_scenario(sc):
    """Returns (status, details)"""
    data = query_rag(sc["q"])
    if "error" in data:
        return "ERROR", f"RAG error: {data['error']}"

    candidatos_raw = data.get("productos_candidatos", [])
    candidatos = [normalize(c) for c in candidatos_raw]
    resultados = data.get("resultados", [])

    # Extract product families from results
    familias = [normalize(r.get("familia", "")) for r in resultados[:5]]
    textos = [r.get("texto", "")[:400] for r in resultados[:3]]

    # Check if any "ok" product appears in candidates or families
    ok_found = []
    ok_missing = []
    for prod in sc["ok"]:
        if prod == "__gap__":
            ok_found.append("__gap__")
            continue
        p = normalize(prod)
        found = any(p in c for c in candidatos) or any(p in f for f in familias)
        if found:
            ok_found.append(prod)
        else:
            ok_missing.append(prod)

    # Check if any "bad" product appears in top candidates
    bad_found = []
    for prod in sc["bad"]:
        p = normalize(prod)
        # Only flag if it's in the TOP 2 candidates (most likely to be recommended)
        top2 = candidatos[:2] + familias[:2]
        if any(p in c for c in top2):
            bad_found.append(prod)

    # Determine status
    if sc["ok"] == ["__gap__"]:
        # For gap products, we expect NO good products in results
        relevant_products = any(
            any(kw in c for kw in ["pintucoat", "aquablock", "pintuco fill", "epoxica"])
            for c in candidatos[:3]
        )
        if relevant_products:
            return "WARN", f"GAP product: RAG returns products that might mislead. Candidatos: {candidatos_raw[:4]}"
        return "PASS", f"GAP handled. Candidatos: {candidatos_raw[:3]}"

    issues = []
    if ok_missing:
        issues.append(f"FALTA producto correcto: {ok_missing}")
    if bad_found:
        issues.append(f"PRODUCTO INCORRECTO en top: {bad_found}")

    if bad_found:
        status = "FAIL"
    elif ok_missing and not ok_found:
        status = "FAIL"
    elif ok_missing:
        status = "WARN"
    else:
        status = "PASS"

    details = f"Candidatos: {candidatos_raw[:5]}"
    if issues:
        details += " | " + " | ".join(issues)

    # Add text snippet for context on failures
    if status in ("FAIL", "WARN") and textos:
        details += f"\n    RAG texto[0]: {textos[0][:200]}"

    return status, details


def main():
    print("=" * 90)
    print("  AUDITORÍA COMPLETA: Producto vs RAG — 50 escenarios")
    print("=" * 90)

    results = {"PASS": 0, "WARN": 0, "FAIL": 0, "ERROR": 0}
    details_list = []

    for i, sc in enumerate(SCENARIOS):
        status, details = check_scenario(sc)
        results[status] += 1
        icon = {"PASS": "✅", "WARN": "⚠️", "FAIL": "❌", "ERROR": "💥"}.get(status, "?")
        line = f"  {icon} [{sc['cat']:10}] {sc['q'][:60]}"
        if status != "PASS":
            line += f"\n     → {details}"
        print(line)
        details_list.append({"scenario": sc, "status": status, "details": details})
        time.sleep(0.5)  # Rate limit

    print("\n" + "=" * 90)
    print(f"  RESUMEN: ✅ {results['PASS']} PASS | ⚠️ {results['WARN']} WARN | ❌ {results['FAIL']} FAIL | 💥 {results['ERROR']} ERROR")
    print(f"  Total: {len(SCENARIOS)}")
    print("=" * 90)

    # Save detailed results
    output_path = "reports/audits/_audit_results.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(details_list, f, ensure_ascii=False, indent=2)
    print(f"Resultados guardados en {output_path}")

    # Print failure/warn summary
    problems = [d for d in details_list if d["status"] in ("FAIL", "WARN")]
    if problems:
        print(f"\n{'─' * 90}")
        print(f"  PROBLEMAS DETECTADOS ({len(problems)}):")
        print(f"{'─' * 90}")
        for d in problems:
            sc = d["scenario"]
            print(f"\n  {'❌' if d['status']=='FAIL' else '⚠️'} {sc['q']}")
            print(f"     Esperado: {sc['ok']}")
            print(f"     Prohibido: {sc['bad']}")
            print(f"     {d['details']}")


if __name__ == "__main__":
    main()
