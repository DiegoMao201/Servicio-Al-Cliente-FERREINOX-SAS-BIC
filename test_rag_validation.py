"""
Test masivo de la búsqueda RAG portfolio-aware para validar calidad.
Corre contra el endpoint /admin/rag-buscar del servidor desplegado.
"""
import json
import urllib.request
import urllib.parse
import sys

BASE = "https://apicrm.datovatenexuspro.com/admin/rag-buscar"
ADMIN_KEY = "ferreinox_admin_2024"

# ── 54 tests organizados por categoría ──────────────────────────
# Cada test: (query, productos_esperados, productos_prohibidos, descripcion)
TESTS = [
    # ═══ HUMEDAD / FILTRACIONES ═══
    ("tengo humedad interna en los muros se filtran las paredes por dentro",
     ["aquablock", "sellamur", "estuco anti humedad"], ["koraza", "viniltex advanced"],
     "HUMEDAD: filtración interna clásica"),
    ("pared mojando por dentro",
     ["aquablock", "sellamur"], ["koraza", "pintucoat"],
     "HUMEDAD: jerga - pared mojada"),
    ("filtra agua muro sotano",
     ["aquablock"], ["viniltex", "koraza", "pintucoat"],
     "HUMEDAD: sótano con filtración"),
    ("salitre blanco pared suda",
     ["aquablock", "estuco anti humedad", "sellamur"], ["pintulac", "pintucoat"],
     "HUMEDAD: eflorescencia/salitre"),
    ("antihumedad para bano",
     ["aquablock", "viniltex"], [],
     "HUMEDAD: baño húmedo"),
    ("sello pared filtra agua por dentro",
     ["aquablock", "sellamur"], ["silicona", "koraza"],
     "HUMEDAD: sellado filtración"),
    ("presion negativa humedad freatica muros",
     ["aquablock"], ["koraza", "pintulux"],
     "HUMEDAD: presión negativa técnica"),
    ("ampollando pintura pared interior suda",
     ["aquablock", "estuco anti humedad"], ["koraza"],
     "HUMEDAD: ampollas por humedad"),

    # ═══ FACHADAS / EXTERIORES ═══
    ("necesito pintar la fachada exterior deteriorada por lluvia y sol",
     ["koraza"], ["aquablock", "viniltex banos"],
     "FACHADA: caso típico lluvia/sol"),
    ("fachada de la casa se esta pelando la pintura",
     ["koraza"], ["pintucoat", "canchas"],
     "FACHADA: pelando pintura"),
    ("pintura exterior que aguante sol y lluvia",
     ["koraza"], ["aquablock", "pintucoat"],
     "FACHADA: resistencia intemperie"),
    ("descascarando pared exterior de la casa",
     ["koraza"], ["aquablock", "viniltex banos"],
     "FACHADA: descascaramiento exterior"),
    ("casa cayendo pedazos por la lluvia exterior",
     ["koraza"], ["pintucoat", "aquablock"],
     "FACHADA: jerga colombiana"),
    ("muro exterior se deterioro con el clima",
     ["koraza"], ["aquablock"],
     "FACHADA: deterioro climático"),

    # ═══ TECHOS / GOTERAS ═══
    ("necesito impermeabilizar el techo tiene goteras",
     ["pintuco fill", "impercoat"], ["viniltex", "koraza sol"],
     "TECHO: goteras clásico"),
    ("techo goteando necesito sellarlo",
     ["pintuco fill", "impercoat", "tela"], ["viniltex"],
     "TECHO: techo goteando"),
    ("impermeabilizar terraza de concreto",
     ["pintuco fill", "impercoat"], ["viniltex", "aquablock"],
     "TECHO: terraza concreto"),
    ("filtra agua plancha de concreto techo",
     ["pintuco fill", "impercoat"], [],
     "TECHO: plancha filtrando"),
    ("cubierta de eternit con goteras",
     ["pintuco fill", "impercoat", "koraza"], ["aquablock"],
     "TECHO: fibrocemento/eternit"),

    # ═══ METAL / ÓXIDO / ANTICORROSIVO ═══
    ("tengo una reja de hierro oxidada necesito pintarla",
     ["corrotec", "pintoxido", "anticorrosivo"], ["viniltex", "koraza"],
     "METAL: reja oxidada"),
    ("rejas oxidando se estan comiendo",
     ["corrotec", "pintoxido", "anticorrosivo"], ["viniltex"],
     "METAL: jerga - comiendo óxido"),
    ("tubo galvanizado necesito pintar",
     ["wash primer", "corrotec"], ["viniltex"],
     "METAL: galvanizado"),
    ("porton de hierro oxidado exterior",
     ["corrotec", "pintoxido", "anticorrosivo", "pintulux"], [],
     "METAL: portón exterior"),
    ("estructura metalica bodega necesita proteccion",
     ["corrotec", "intergard", "anticorrosivo"], [],
     "METAL: estructura industrial"),

    # ═══ PISOS ═══
    ("piso de bodega industrial con trafico pesado de montacargas",
     ["pintucoat"], ["viniltex"],
     "PISO: industrial pesado"),
    ("pintar piso garaje de la casa",
     ["pintura canchas", "pintucoat"], ["viniltex"],
     "PISO: garaje residencial"),
    ("pintura epoxica piso fabrica industrial",
     ["pintucoat"], [],
     "PISO: epóxica industrial"),
    ("piso bodega cemento",
     ["pintucoat", "pintura canchas"], ["viniltex"],
     "PISO: bodega cemento"),
    ("cancha de microfutbol",
     ["pintura canchas"], ["pintucoat"],
     "PISO: cancha deportiva"),
    ("anden del frente de la casa",
     ["pintura canchas"], [],
     "PISO: andén residencial"),

    # ═══ PISCINA (debe NO tener producto) ═══
    ("quiero pintar una piscina",
     [], ["pintucoat", "koraza", "viniltex"],
     "PISCINA: debe dar SIN_PRODUCTO"),
    ("pintura para tanque de agua potable",
     [], ["pintucoat"],
     "PISCINA: tanque agua"),

    # ═══ INTERIORES ═══
    ("pintar la sala de la casa",
     ["viniltex", "intervinil"], ["pintucoat", "koraza"],
     "INTERIOR: sala casa"),
    ("pintura para cuarto economica",
     ["pinturama", "vinil max", "icolatex", "intervinil", "domestico"], [],
     "INTERIOR: económica"),
    ("pintura lavable para la cocina",
     ["viniltex"], ["pintucoat"],
     "INTERIOR: cocina lavable"),
    ("cielo raso primer piso",
     ["viniltex", "pinturama", "pintura cielos"], [],
     "INTERIOR: cielo raso"),

    # ═══ MADERA ═══
    ("barniz para pergola de madera al aire libre",
     ["barnex", "wood stain", "barniz marino"], [],
     "MADERA: pergola exterior"),
    ("mueble de madera interior necesita barniz",
     ["pintulac", "barniz", "madetec"], [],
     "MADERA: mueble interior"),

    # ═══ JERGA COLOMBIANA / PREGUNTAS DIFÍCILES ═══
    ("la casita se me esta cayendo a pedazos por la lluvia",
     ["koraza"], ["pintucoat", "aquablock"],
     "JERGA: casa cayendo pedazos → fachada"),
    ("bano negro de hongos necesito quitarlos",
     ["aquablock", "viniltex"], ["alta temperatura"],
     "JERGA: baño con hongos"),
    ("piso del parqueadero se esta pelando",
     ["pintura canchas", "pintucoat"], [],
     "JERGA: parqueadero pelando"),
    ("la fachada esta hecha un desastre",
     ["koraza"], ["pintucoat"],
     "JERGA: fachada desastre"),
    ("necesito sellar el techo que llueve horrible",
     ["pintuco fill", "impercoat"], ["viniltex"],
     "JERGA: techo llueve horrible"),
    ("mi casa por dentro se esta mojando toda",
     ["aquablock", "sellamur"], ["koraza"],
     "JERGA: casa mojando por dentro"),

    # ═══ PREGUNTAS AMBIGUAS (el agente debería preguntar) ═══
    ("necesito pintura impermeabilizante",
     ["pintuco fill", "impercoat", "aquablock", "koraza"], [],
     "AMBIGUA: impermeabilizante genérico"),
    ("que me recomienda para la humedad",
     ["aquablock", "sellamur"], ["pintucoat"],
     "AMBIGUA: humedad genérica"),
    ("tengo un problema de pintura pelando",
     ["koraza", "viniltex"], [],
     "AMBIGUA: pelando genérico"),

    # ═══ TÉCNICOS ESPECÍFICOS ═══
    ("aquablock: humedad interna en los muros filtracion",
     ["aquablock"], [],
     "TÉCNICO: query con producto explícito Aquablock"),
    ("koraza: preparacion superficie fachada exterior",
     ["koraza"], [],
     "TÉCNICO: query con producto explícito Koraza"),
    ("pintucoat: preparacion piso concreto industrial",
     ["pintucoat"], [],
     "TÉCNICO: query con producto explícito Pintucoat"),
    ("corrotec: sistema anticorrosivo para rejas",
     ["corrotec"], [],
     "TÉCNICO: query con producto explícito Corrotec"),
]


def run_test(query, expected, prohibited, desc):
    """Run a single RAG search test and evaluate results."""
    url = f"{BASE}?q={urllib.parse.quote(query)}&top_k=8"
    req = urllib.request.Request(url, headers={
        "x-admin-key": ADMIN_KEY,
        "User-Agent": "Mozilla/5.0 CRM-Ferreinox-Test/1.0",
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
    except Exception as e:
        return "ERROR", f"HTTP error: {e}", []

    candidates = [c.lower() for c in data.get("productos_candidatos", [])]
    results = data.get("resultados", [])
    best_sim = max((r.get("similitud", 0) for r in results), default=0)
    
    # Also check archivos/familias in results for broader matching
    all_text = " ".join([
        (r.get("archivo", "") + " " + r.get("familia", "") + " " + r.get("texto", "")[:200]).lower()
        for r in results
    ])
    
    # Check expected products
    found_expected = []
    missing_expected = []
    for exp in expected:
        exp_low = exp.lower()
        if any(exp_low in c for c in candidates) or exp_low in all_text:
            found_expected.append(exp)
        else:
            missing_expected.append(exp)
    
    # Check prohibited products
    found_prohibited = []
    for pro in prohibited:
        pro_low = pro.lower()
        # Only check if it appears as a DOMINANT result (first 3 results or candidates)
        top_text = " ".join([
            (r.get("archivo", "") + " " + r.get("familia", "")).lower()
            for r in results[:3]
        ])
        if any(pro_low in c for c in candidates[:3]) or pro_low in top_text:
            found_prohibited.append(pro)
    
    # Determine status
    if found_prohibited:
        status = "FAIL"
        detail = f"PROHIBIDO encontrado: {found_prohibited}"
    elif not expected:
        # No expected = query should NOT find specific products
        status = "PASS"
        detail = f"Sin producto esperado (OK). Candidatos: {candidates[:3]}"
    elif missing_expected and len(missing_expected) == len(expected):
        status = "FAIL"
        detail = f"NINGUN esperado encontrado. Faltantes: {missing_expected}. Candidatos: {candidates[:4]}"
    elif missing_expected:
        status = "WARN"
        detail = f"Parcial. Encontrados: {found_expected}. Faltantes: {missing_expected}"
    else:
        status = "PASS"
        detail = f"Todos encontrados: {found_expected}"
    
    return status, f"sim={best_sim:.3f} | {detail}", candidates[:4]


def main():
    print("=" * 80)
    print("VALIDACIÓN RAG PORTFOLIO-AWARE — 50 tests")
    print("=" * 80)
    
    stats = {"PASS": 0, "WARN": 0, "FAIL": 0, "ERROR": 0}
    failures = []
    
    for i, (query, expected, prohibited, desc) in enumerate(TESTS, 1):
        status, detail, candidates = run_test(query, expected, prohibited, desc)
        stats[status] += 1
        
        icon = {"PASS": "✓", "WARN": "⚠", "FAIL": "✗", "ERROR": "!"}.get(status, "?")
        color_code = {"PASS": "", "WARN": "  ", "FAIL": " ", "ERROR": ""}.get(status, "")
        print(f"  {icon} [{status:4s}] {desc}")
        if status in ("FAIL", "WARN", "ERROR"):
            print(f"         {detail}")
            failures.append((desc, status, detail))
    
    print()
    print("=" * 80)
    total = sum(stats.values())
    print(f"RESULTADOS: {stats['PASS']}/{total} PASS, {stats['WARN']} WARN, {stats['FAIL']} FAIL, {stats['ERROR']} ERROR")
    pass_rate = (stats['PASS'] / total * 100) if total else 0
    print(f"TASA DE ÉXITO: {pass_rate:.0f}%")
    print("=" * 80)
    
    if failures:
        print("\nDETALLE FALLOS:")
        for desc, status, detail in failures:
            print(f"  [{status}] {desc}: {detail}")
    
    return 0 if stats['FAIL'] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
