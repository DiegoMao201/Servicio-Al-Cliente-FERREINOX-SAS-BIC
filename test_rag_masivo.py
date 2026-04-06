"""
Batería masiva de tests RAG para afinar el agente CRM Ferreinox.
Ejecuta 50+ consultas contra /admin/rag-buscar y clasifica resultados.
"""
import json, sys, time
try:
    import requests
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests", "-q"])
    import requests

BASE = "https://apicrm.datovatenexuspro.com/admin/rag-buscar"
ADMIN_KEY = "ferreinox_admin_2024"

# ── TESTS: (query, productos_esperados, productos_NO_deben_aparecer, categoria) ──
TESTS = [
    # ═══ HUMEDAD / FILTRACIONES ═══
    ("la pared se está mojando por dentro", ["aquablock", "sellamur", "estuco anti humedad"], ["koraza"], "humedad"),
    ("se me filtra el agua por el muro del sótano", ["aquablock"], ["koraza", "viniltex"], "humedad"),
    ("hay manchas de humedad en la base del muro", ["aquablock", "estuco anti humedad", "sellamur"], ["koraza"], "humedad"),
    ("la pared suda mucho y sale como salitre blanco", ["aquablock", "estuco anti humedad"], ["koraza"], "humedad"),
    ("tengo humedad ascendente en un primer piso", ["aquablock", "sellamur"], ["koraza"], "humedad"),
    ("se me están ampollando las paredes por humedad", ["aquablock", "estuco anti humedad"], ["koraza"], "humedad"),
    ("necesito pintura antihumedad para baño", ["aquablock", "viniltex"], ["koraza"], "humedad"),
    ("cómo sello una pared que filtra agua", ["aquablock", "sellamur"], ["koraza"], "humedad"),

    # ═══ FACHADAS / EXTERIORES ═══
    ("necesito para la fachada de la casa", ["koraza"], ["aquablock", "viniltex"], "fachada"),
    ("la casa por fuera se está pelando la pintura", ["koraza"], ["aquablock"], "fachada"),
    ("quiero pintar el frente de la casa", ["koraza"], ["aquablock", "pintucoat"], "fachada"),
    ("pintura para exterior que aguante el sol", ["koraza"], ["aquablock", "viniltex"], "fachada"),
    ("se me está descascarando la fachada", ["koraza"], ["aquablock"], "fachada"),
    ("pintura exterior para clima de tierra caliente", ["koraza"], ["aquablock"], "fachada"),

    # ═══ TECHOS / GOTERAS ═══
    ("el techo me está goteando", ["impercoat", "pintuco fill", "impermeabilizante"], ["koraza", "aquablock"], "techo"),
    ("necesito impermeabilizar una terraza", ["koraza", "impercoat", "pintuco fill"], [], "techo"),
    ("se filtra el agua por la plancha de concreto", ["impercoat", "pintuco fill"], ["aquablock"], "techo"),
    ("manto para terraza que se llueve", ["impercoat", "pintuco fill", "tela de refuerzo"], [], "techo"),

    # ═══ METAL / ANTICORROSIVO ═══
    ("tengo unas rejas que se están oxidando", ["corrotec", "pintoxido", "anticorrosivo"], ["koraza", "viniltex"], "metal"),
    ("una puerta de hierro vieja toda oxidada", ["corrotec", "pintoxido", "anticorrosivo"], ["koraza"], "metal"),
    ("para pintar un portón metálico con óxido", ["corrotec", "pintoxido", "anticorrosivo"], [], "metal"),
    ("anticorrosivo para estructura metálica", ["corrotec", "anticorrosivo"], [], "metal"),
    ("pintura para tubo galvanizado", ["wash primer", "anticorrosivo", "corrotec"], [], "metal"),

    # ═══ PISOS ═══
    ("pintura para el piso del garaje", ["pintucoat", "pintura canchas", "pintura pisos"], ["koraza"], "piso"),
    ("necesito pintar el piso de una bodega", ["pintucoat"], ["koraza", "viniltex"], "piso"),
    ("pintura epóxica para piso de fábrica", ["pintucoat"], ["koraza"], "piso"),
    ("necesito para piso de un parqueadero", ["pintucoat", "pintura canchas"], [], "piso"),
    ("quiero pintar una cancha de microfútbol", ["pintura canchas", "pintura para canchas"], ["koraza"], "piso"),
    ("pintura para un andén", ["pintura canchas"], ["koraza"], "piso"),

    # ═══ INTERIORES ═══
    ("quiero pintar el cuarto del bebé", ["viniltex"], ["koraza", "pintucoat"], "interior"),
    ("qué me recomienda para la sala", ["viniltex"], ["koraza"], "interior"),
    ("pintura lavable para la cocina", ["viniltex"], ["koraza"], "interior"),
    ("pintura para cielo raso", ["viniltex"], ["koraza", "pintucoat"], "interior"),

    # ═══ MADERA ═══
    ("quiero proteger una puerta de madera exterior", ["barnex", "wood stain", "barniz"], ["koraza", "viniltex"], "madera"),
    ("necesito barniz para un mueble", ["barniz", "barnex", "wood stain", "madetec"], ["koraza"], "madera"),
    ("la terraza tiene una pérgola de madera", ["barnex", "wood stain"], ["koraza"], "madera"),

    # ═══ CASOS AMBIGUOS / DIFÍCILES ═══
    ("se me está dañando la pared", [], ["piscina"], "ambiguo"),  # Debería preguntar: ¿interior o exterior?
    ("necesito pintura", [], [], "ambiguo"),  # Debería preguntar: ¿para qué superficie?
    ("necesito impermeabilizar", [], [], "ambiguo"),  # ¿Techo? ¿Muro? ¿Sótano?
    ("se me está pelando", [], [], "ambiguo"),  # ¿Pared interior? ¿Fachada? ¿Metal?
    ("me recomiendan algo bueno para pintar", [], [], "ambiguo"),  # Muy genérico

    # ═══ PISCINAS (NO VENDEN) ═══
    ("quiero pintar la piscina", ["cementos impermeable", "piscina"], [], "piscina_no"),
    ("pintura para tanque de agua", ["cementos impermeable"], [], "piscina_no"),

    # ═══ JERGA COLOMBIANA / COLOQUIAL ═══
    ("la casa se me está cayendo a pedazos por la lluvia", ["koraza"], [], "jerga"),
    ("el baño está todo negro de hongos", ["aquablock", "viniltex", "anti humedad"], [], "jerga"),
    ("la pared está sudando horrible", ["aquablock", "estuco anti humedad", "sellamur"], ["koraza"], "jerga"),
    ("se está comiendo el óxido la reja", ["corrotec", "pintoxido", "anticorrosivo"], [], "jerga"),
    ("qué le echo al piso del parqueadero que no se dañe", ["pintucoat", "pintura canchas"], [], "jerga"),
    ("la terraza se me llueve toda", ["impercoat", "pintuco fill", "koraza"], [], "jerga"),

    # ═══ PREGUNTAS TÉCNICAS ESPECÍFICAS ═══
    ("cuántas manos de koraza debo dar", ["koraza"], [], "tecnico"),
    ("se puede mezclar aquablock con agua", ["aquablock"], [], "tecnico"),
    ("rendimiento por galón de viniltex", ["viniltex"], [], "tecnico"),
    ("cuánto demora en secar el pintucoat", ["pintucoat"], [], "tecnico"),
    ("qué rodillo uso para koraza", ["koraza"], [], "tecnico"),
]

def search_rag(query, top_k=6):
    try:
        resp = requests.get(BASE, params={"q": query, "top_k": top_k},
                           headers={"x-admin-key": ADMIN_KEY}, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        return {"error": str(e), "resultados": [], "productos_candidatos": []}

def normalize(s):
    return s.lower().replace("á","a").replace("é","e").replace("í","i").replace("ó","o").replace("ú","u").replace("ñ","n")

def check_match(candidates_raw, expected, forbidden):
    candidates = [normalize(c) for c in candidates_raw]
    results_text = " ".join(candidates)
    
    found_expected = []
    missed_expected = []
    for exp in expected:
        exp_n = normalize(exp)
        if any(exp_n in c for c in candidates):
            found_expected.append(exp)
        else:
            missed_expected.append(exp)
    
    found_forbidden = []
    for forb in forbidden:
        forb_n = normalize(forb)
        if any(forb_n in c for c in candidates):
            found_forbidden.append(forb)
    
    return found_expected, missed_expected, found_forbidden

# ── MAIN ──
print("=" * 80)
print("BATERÍA MASIVA DE TESTS RAG - CRM FERREINOX")
print("=" * 80)

results_by_category = {}
total_pass = 0
total_fail = 0
total_warn = 0
all_results = []

for i, (query, expected, forbidden, category) in enumerate(TESTS, 1):
    data = search_rag(query)
    
    if "error" in data:
        status = "ERROR"
        detail = data["error"]
        total_fail += 1
    else:
        candidates = data.get("productos_candidatos", [])
        top_results = data.get("resultados", [])
        top_sim = top_results[0]["similitud"] if top_results else 0
        top_product = top_results[0].get("familia", "?") if top_results else "?"
        
        found_exp, missed_exp, found_forb = check_match(candidates, expected, forbidden)
        
        if found_forb:
            status = "FAIL"
            detail = f"PROHIBIDO encontrado: {found_forb}"
            total_fail += 1
        elif not expected:  # Caso ambiguo - no hay expectativa específica
            status = "INFO"
            detail = f"Candidatos: {candidates[:4]} (sim={top_sim:.3f})"
            total_warn += 1
        elif missed_exp and not found_exp:
            status = "FAIL"
            detail = f"NINGUNO esperado encontrado. Candidatos: {candidates[:4]}"
            total_fail += 1
        elif missed_exp:
            status = "WARN"
            detail = f"Parcial: encontró {found_exp}, faltó {missed_exp} (sim={top_sim:.3f})"
            total_warn += 1
        else:
            status = "PASS"
            detail = f"Top: {top_product} (sim={top_sim:.3f})"
            total_pass += 1
    
    icon = {"PASS": "✅", "FAIL": "❌", "WARN": "⚠️", "INFO": "ℹ️", "ERROR": "💥"}.get(status, "?")
    print(f"\n{icon} Test {i:02d} [{category:>10}] {status}")
    print(f"   Q: \"{query}\"")
    print(f"   {detail}")
    
    all_results.append({
        "test": i, "query": query, "category": category, "status": status,
        "detail": detail, "candidates": data.get("productos_candidatos", []),
        "top_sim": top_results[0]["similitud"] if data.get("resultados") else 0,
        "top_family": top_results[0].get("familia", "") if data.get("resultados") else ""
    })

print("\n" + "=" * 80)
print(f"RESUMEN: ✅ PASS={total_pass}  ⚠️ WARN={total_warn}  ❌ FAIL={total_fail}")
print(f"TOTAL: {len(TESTS)} tests")
print("=" * 80)

# Resumen por categoría
cats = {}
for r in all_results:
    c = r["category"]
    if c not in cats:
        cats[c] = {"pass": 0, "warn": 0, "fail": 0, "info": 0}
    if r["status"] == "PASS": cats[c]["pass"] += 1
    elif r["status"] == "WARN": cats[c]["warn"] += 1
    elif r["status"] == "FAIL": cats[c]["fail"] += 1
    else: cats[c]["info"] += 1

print("\nPOR CATEGORÍA:")
for cat, counts in sorted(cats.items()):
    print(f"  {cat:>12}: ✅{counts['pass']} ⚠️{counts['warn']} ❌{counts['fail']} ℹ️{counts['info']}")

# Guardar JSON para análisis
with open("test_rag_results.json", "w", encoding="utf-8") as f:
    json.dump(all_results, f, ensure_ascii=False, indent=2)
print("\nResultados guardados en test_rag_results.json")
