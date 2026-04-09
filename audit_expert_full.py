"""
Auditoría completa del conocimiento experto en agent_expert_knowledge.
NO usa API externa. Simula fetch_expert_knowledge localmente.
Detecta: duplicados exactos, registros supersedidos, contradicciones,
y prueba la recuperación con 20+ escenarios de cliente.
"""
import os, json, re
from collections import defaultdict
from sqlalchemy import create_engine, text

DB_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://postgres:o5S3X9VIYcbBWqd525hqT24UhYAc8AdjtevyHtlZHhGxJkfMQVZXReCTxkcjSOAX@192.81.216.49:3000/postgres",
)
engine = create_engine(DB_URL)


def load_all():
    with engine.connect() as c:
        rows = c.execute(text(
            "SELECT id, cedula_experto, nombre_experto, contexto_tags, "
            "producto_recomendado, producto_desestimado, nota_comercial, tipo, activo, created_at "
            "FROM public.agent_expert_knowledge ORDER BY id"
        )).mappings().all()
    return [dict(r) for r in rows]


def normalize(s):
    if not s:
        return ""
    s = s.lower().strip()
    for a, b in [("á","a"),("é","e"),("í","i"),("ó","o"),("ú","u"),("ñ","n"),("ü","u")]:
        s = s.replace(a, b)
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def sim_score(a, b):
    """Jaccard similarity on word sets."""
    wa = set(normalize(a).split())
    wb = set(normalize(b).split())
    if not wa or not wb:
        return 0
    return len(wa & wb) / len(wa | wb)


def fetch_local(rows, query, limit=8):
    """Simulate fetch_expert_knowledge without DB call."""
    terms = [t for t in normalize(query).split() if len(t) >= 2][:10]
    if not terms:
        return []
    scored = []
    for r in rows:
        if not r["activo"]:
            continue
        searchable = normalize(
            f"{r['contexto_tags']} {r['nota_comercial']} {r['producto_recomendado'] or ''} {r['producto_desestimado'] or ''}"
        )
        score = sum(1 for t in terms if t in searchable)
        if score > 0:
            scored.append((score, r))
    scored.sort(key=lambda x: (-x[0], -x[1]["id"]))
    return [r for _, r in scored[:limit]]


# ═══════════════════════════════════════════════
# 1. DETECCIÓN DE DUPLICADOS EXACTOS
# ═══════════════════════════════════════════════
def find_exact_duplicates(rows):
    """Find rows with identical nota_comercial (normalized)."""
    by_nota = defaultdict(list)
    for r in rows:
        key = normalize(r["nota_comercial"])[:200]
        by_nota[key].append(r["id"])
    return {k: v for k, v in by_nota.items() if len(v) > 1}


# ═══════════════════════════════════════════════
# 2. DETECCIÓN DE REGISTROS MUY SIMILARES
# ═══════════════════════════════════════════════
def find_high_similarity(rows, threshold=0.7):
    active = [r for r in rows if r["activo"]]
    pairs = []
    for i, a in enumerate(active):
        for b in active[i+1:]:
            s = sim_score(a["nota_comercial"], b["nota_comercial"])
            if s >= threshold:
                pairs.append((a["id"], b["id"], round(s, 2),
                              a["contexto_tags"][:60], b["contexto_tags"][:60]))
    return pairs


# ═══════════════════════════════════════════════
# 3. DETECCIÓN DE CONTRADICCIONES
# ═══════════════════════════════════════════════
def find_contradictions(rows):
    """Find records where the same product appears as both recommended and desestimado."""
    rec_map = defaultdict(list)  # product -> list of ids that recommend it
    des_map = defaultdict(list)  # product -> list of ids that desestimate it
    for r in rows:
        if not r["activo"]:
            continue
        for prod in (r.get("producto_recomendado") or "").split(","):
            p = normalize(prod).strip()
            if p and len(p) > 2:
                rec_map[p].append(r["id"])
        for prod in (r.get("producto_desestimado") or "").split(","):
            p = normalize(prod).strip()
            if p and len(p) > 2:
                des_map[p].append(r["id"])
    contradictions = []
    for prod in set(rec_map) & set(des_map):
        contradictions.append({
            "producto": prod,
            "recomendado_en": rec_map[prod],
            "desestimado_en": des_map[prod],
        })
    return contradictions


# ═══════════════════════════════════════════════
# 4. TEST DE RECUPERACIÓN (20+ escenarios)
# ═══════════════════════════════════════════════
TEST_SCENARIOS = [
    # (query_simulada, tema, expected_topics)
    ("quiero pintar un piso de bodega con montacargas", "piso industrial pesado",
     ["intergard 2002", "cuarzo", "interseal"]),
    ("necesito pintar un piso de concreto nuevo", "piso concreto nuevo",
     ["28 dias", "curado"]),
    ("piso exterior epoxico sol UV", "piso exterior",
     ["interthane", "entiza"]),
    ("pintar tanque de agua potable", "tanque agua potable",
     ["epoxipoliamida", "pintucoat"]),
    ("pared con humedad y salitre interior", "humedad interna",
     ["aquablock", "estuco acrilico"]),
    ("revoque dañado meteorizado", "revoque dañado",
     ["revofast"]),
    ("pintar reja de metal oxidada exterior", "metal oxidado",
     ["pintoxido", "corrotec", "pintulux"]),
    ("madera exterior pergola deck", "madera exterior",
     ["barnex", "wood stain"]),
    ("madera interior marcos color solido", "madera interior sólido",
     ["esmalte domestico", "pintulux"]),
    ("que lija uso para madera barniz viejo", "preparación madera",
     ["removedor", "abracol"]),
    ("pintar fachada descascarada exterior", "fachada",
     ["koraza", "viniltex", "estuco"]),
    ("que imprimante para piso concreto", "imprimante concreto",
     ["interseal"]),
    ("que imprimante para estructura metalica", "imprimante metal",
     ["primer 50rs"]),
    ("cuarzo para piso intergard 2002", "cuarzo cálculo",
     ["5891610", "broadcasting"]),
    ("pintura de tráfico para parqueadero", "tráfico",
     ["5891322", "thinner 21204"]),
    ("solvente para interthane poliuretano", "solvente Interthane",
     ["ufa151"]),
    ("pintucoat para piso interior de oficina", "Pintucoat uso correcto",
     ["pintucoat", "media"]),
    ("color RAL para piso epoxico", "colores RAL",
     ["base", "tintometria"]),
    ("cotizar sistema para 60 m2 de piso", "cotización m²",
     ["metros", "m2"]),
    ("estuco para fachada exterior", "estuco exterior",
     ["estuco acrilico", "exterior"]),
    ("brocha para barniz madera", "herramientas madera",
     ["goya profesional"]),
    ("pintucoat vs intergard para bodega pesada", "comparación pisos",
     ["intergard 2002", "pintucoat"]),
    ("sealer f100 para que sirve", "Sealer F100",
     ["sealer f100", "concreto liso"]),
    ("pintar piso exterior con montacargas", "piso exterior pesado",
     ["intergard 2002", "interthane"]),
]


def run_tests(rows):
    active = [r for r in rows if r["activo"]]
    results = []
    for query, tema, expected in TEST_SCENARIOS:
        hits = fetch_local(active, query, limit=8)
        hit_ids = [h["id"] for h in hits]
        hit_text = " ".join(
            normalize(f"{h['contexto_tags']} {h['nota_comercial']} {h['producto_recomendado'] or ''}")
            for h in hits
        )
        found = [kw for kw in expected if kw in hit_text]
        missed = [kw for kw in expected if kw not in hit_text]
        status = "PASS" if not missed else "PARTIAL" if found else "FAIL"
        results.append({
            "query": query,
            "tema": tema,
            "status": status,
            "hit_ids": hit_ids,
            "found": found,
            "missed": missed,
        })
    return results


# ═══════════════════════════════════════════════
# 5. ANÁLISIS DE SUPERSEDIDOS
# ═══════════════════════════════════════════════
def find_superseded(rows):
    """Manually identified superseded records based on chronological analysis."""
    superseded = []
    active = {r["id"]: r for r in rows if r["activo"]}

    # Pablo #2 superseded by Pablo #6 (humedad interna - order corrected)
    if 2 in active and 6 in active:
        superseded.append((2, 6, "Humedad interna: #6 corrige el orden Aquablock→Estuco (antes estaba al revés en #2)"))

    # Pablo #3: Pintucoat para tráfico pesado — CONTRADICHO por Diego #11,#13
    if 3 in active and 11 in active:
        superseded.append((3, 11, "Piso industrial: #3 dice Pintucoat para montacargas, #11 dice Pintucoat es MEDIA resistencia. Correcto: Intergard 2002"))

    # Pablo #5: Sellador + Barnex — CONTRADICHO por Diego #25
    if 5 in active and 25 in active:
        superseded.append((5, 25, "Madera exterior: #5 recomienda sellador, #25 dice NUNCA sellador antes de Barnex"))

    # #34 exact duplicate of #35
    if 34 in active and 35 in active:
        superseded.append((35, 34, "Duplicado exacto de madera exterior/interior"))

    # #37 exact duplicate of #38
    if 37 in active and 38 in active:
        superseded.append((38, 37, "Duplicado exacto de fachadas"))

    # #46 exact duplicate of #47
    if 46 in active and 47 in active:
        superseded.append((47, 46, "Duplicado exacto de metales"))

    # #29 redundant with #26 (brocha Goya)
    if 29 in active and 26 in active:
        superseded.append((29, 26, "Brocha Goya: #29 repite lo mismo que #26"))

    # #32 consolidated into #34 (madera consolidación)
    if 32 in active and 34 in active:
        superseded.append((32, 34, "Madera sistemas: #32 fue consolidado en #34"))

    # #33 consolidated into #34 (herramientas madera)
    if 33 in active and 34 in active:
        superseded.append((33, 34, "Madera herramientas: #33 fue consolidado en #34"))

    # #36 superseded by #37 (fachadas expanded)
    if 36 in active and 37 in active:
        superseded.append((36, 37, "Fachadas: #36 fue expandido y mejorado en #37"))

    # #55 overlaps with #17 (control diagnóstico / preguntar m²)
    if 55 in active and 17 in active:
        superseded.append((55, 17, "Control diagnóstico: #55 repite concepto de #17 (preguntar m²)"))

    return superseded


# ═══════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════
if __name__ == "__main__":
    rows = load_all()
    total = len(rows)
    active = [r for r in rows if r["activo"]]
    print(f"\n{'='*70}")
    print(f"  AUDITORÍA COMPLETA DE CONOCIMIENTO EXPERTO")
    print(f"  Total registros: {total} | Activos: {len(active)}")
    print(f"  Pablo: {sum(1 for r in active if r['cedula_experto']=='1053774777')}")
    print(f"  Diego: {sum(1 for r in active if r['cedula_experto']=='1088266407')}")
    print(f"{'='*70}")

    # 1. Duplicados exactos
    print(f"\n{'─'*50}")
    print("1. DUPLICADOS EXACTOS (nota_comercial idéntica)")
    print(f"{'─'*50}")
    dupes = find_exact_duplicates(active)
    if dupes:
        for nota, ids in dupes.items():
            print(f"  IDs {ids} → '{nota[:80]}...'")
    else:
        print("  Ninguno encontrado.")

    # 2. Alta similaridad
    print(f"\n{'─'*50}")
    print("2. REGISTROS MUY SIMILARES (Jaccard ≥ 0.70)")
    print(f"{'─'*50}")
    sims = find_high_similarity(active, 0.70)
    for a, b, score, tag_a, tag_b in sims:
        print(f"  #{a} ↔ #{b} (sim={score}) | {tag_a} | {tag_b}")

    # 3. Contradicciones producto
    print(f"\n{'─'*50}")
    print("3. CONTRADICCIONES (producto recomendado Y desestimado)")
    print(f"{'─'*50}")
    contras = find_contradictions(active)
    for c in contras:
        print(f"  '{c['producto']}': recomendado en {c['recomendado_en']}, desestimado en {c['desestimado_en']}")

    # 4. Supersedidos
    print(f"\n{'─'*50}")
    print("4. REGISTROS SUPERSEDIDOS / REDUNDANTES")
    print(f"{'─'*50}")
    superseded = find_superseded(active)
    deactivate_ids = []
    for old_id, new_id, reason in superseded:
        print(f"  DESACTIVAR #{old_id} (reemplazado por #{new_id}): {reason}")
        deactivate_ids.append(old_id)

    # 5. Tests de recuperación
    print(f"\n{'─'*50}")
    print("5. TEST DE RECUPERACIÓN (24 escenarios de cliente)")
    print(f"{'─'*50}")
    test_results = run_tests(active)
    pass_count = sum(1 for r in test_results if r["status"] == "PASS")
    partial_count = sum(1 for r in test_results if r["status"] == "PARTIAL")
    fail_count = sum(1 for r in test_results if r["status"] == "FAIL")
    for r in test_results:
        icon = "✅" if r["status"] == "PASS" else "⚠️" if r["status"] == "PARTIAL" else "❌"
        ids_str = ",".join(str(i) for i in r["hit_ids"][:5])
        missed_str = f" FALTA: {r['missed']}" if r["missed"] else ""
        print(f"  {icon} [{r['status']}] {r['tema']}: IDs=[{ids_str}]{missed_str}")

    print(f"\n  Resultado: {pass_count} PASS | {partial_count} PARTIAL | {fail_count} FAIL de {len(test_results)}")

    # 6. Simulación post-limpieza
    print(f"\n{'─'*50}")
    print("6. SIMULACIÓN POST-LIMPIEZA")
    print(f"{'─'*50}")
    cleaned = [r for r in active if r["id"] not in deactivate_ids]
    print(f"  Registros activos actuales: {len(active)}")
    print(f"  Registros tras limpieza: {len(cleaned)}")
    print(f"  Se desactivarían: {len(deactivate_ids)} → IDs: {deactivate_ids}")

    test_results_clean = run_tests(cleaned)
    pass_clean = sum(1 for r in test_results_clean if r["status"] == "PASS")
    partial_clean = sum(1 for r in test_results_clean if r["status"] == "PARTIAL")
    fail_clean = sum(1 for r in test_results_clean if r["status"] == "FAIL")
    print(f"  Resultado post-limpieza: {pass_clean} PASS | {partial_clean} PARTIAL | {fail_clean} FAIL")

    # Detectar regresiones
    regressed = []
    for before, after in zip(test_results, test_results_clean):
        if before["status"] == "PASS" and after["status"] != "PASS":
            regressed.append(after["tema"])
    if regressed:
        print(f"  ⚠️ REGRESIONES: {regressed}")
    else:
        print(f"  ✅ Sin regresiones tras limpieza")

    # 7. SQL de consolidación
    if deactivate_ids:
        print(f"\n{'─'*50}")
        print("7. SQL DE CONSOLIDACIÓN (ejecutar solo tras revisar)")
        print(f"{'─'*50}")
        ids_sql = ",".join(str(i) for i in deactivate_ids)
        print(f"  UPDATE public.agent_expert_knowledge SET activo = false WHERE id IN ({ids_sql});")

    # 8. Resumen por tema
    print(f"\n{'─'*50}")
    print("8. MAPA DE CONOCIMIENTO POR TEMA (post-limpieza)")
    print(f"{'─'*50}")
    topics = {
        "PISOS": [8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,56,57],
        "HUMEDAD": [6,7,52,53],
        "METAL": [4,46],
        "MADERA": [23,24,25,26,27,28,30,34],
        "FACHADAS": [37,39,40,54],
        "TRÁFICO": [48,49,50,51],
        "TANQUE AGUA": [1],
        "COLORES/BASES": [42,43,44,45],
        "REGLAS COMERCIALES": [17,31,41,54,57],
    }
    for topic, expected_ids in topics.items():
        alive = [i for i in expected_ids if i not in deactivate_ids and i in {r["id"] for r in active}]
        print(f"  {topic}: {len(alive)} registros → IDs {alive}")

    print(f"\n{'='*70}")
    print("  AUDITORÍA COMPLETA FINALIZADA")
    print(f"{'='*70}\n")
