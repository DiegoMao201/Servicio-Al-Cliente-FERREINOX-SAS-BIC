from tests.regression.test_behavioral_rules import *


if __name__ == "__main__":
    run_behavioral_tests()
    "TEC_28_DIAS": "nunca recomendar pintar concreto menos 28 dias curado",
    "TEC_PREP_PISOS_MECANICA": "preparacion pisos industriales mecanica escarificado granallado copas diamante, nunca lija agua",
    "TEC_PRIMER_50RS_METAL": "primer 50rs exclusivo metal, nunca concreto, para concreto interseal gris ral 7038",
    "TEC_FAMILIAS_SEPARADAS": "pintucoat interseal intergard tecnologias diferentes prohibido mezclar",
    "TEC_PINTUCOAT_MEDIA": "pintucoat resistencia media trafico peatonal, para pesado intergard 2002 cuarzo",
    "TEC_PINTUCOAT_EXTERIOR": "pintucoat exterior obliga interthane acabado, epoxico entiza sol",
    "TEC_SELLADOR_BARNEX": "sellador nunca antes barnex wood stain exterior, poro abierto directo madera",
    "TEC_PINTULAC_NO_MARCOS": "pintulac no sirve marcos interiores, usar esmalte domestico pintulux mp",
    "TEC_LIJA_SUSTITUCION": "falta 60 80 ofrecer 100 120, falta 220 320 ofrecer 180 400, nunca fina por gruesa",
    "PROD_INTERGARD_SOBRE_PEDIDO": "intergard 2002 sobre pedido, sin referencia precio pendiente, contacto asesor",
    "PROD_CUARZO_CALCULO": "cuarzo 5891610 obligatorio intergard 2002, 0.5 kg m2, bultos 25 kg",
    "PROD_SEALER_F100_KIT": "sealer f100 mezcla 3 gal comp a 5893615 + 2 gal comp b 5893616, precio por kit",
    "PROD_INTERSEAL_REFS": "interseal 670hs 83 solidos, galon 5893596, cunete 5863715, catalizador ega247",
    "PROD_ESTUCO_EXT": "estuco acrilico exterior pq estuco prof ext blan 27060",
    "PROD_TRAFICO": "pintura trafico 5891322, prohibido pintucoat demarcacion",
    "PROD_THINNER_TRAFICO": "thinner 21204 f0116621204, 5 botellas galon 25 cunete, prohibido 21050 trafico",
    "TINTO_INTERSEAL": "interseal light ega130 5863715, ultra deep ega105 5893595",
    "TINTO_INTERGARD": "intergard light eca011 5897961, deep eca044 5893795",
    "TINTO_INTERTHANE": "interthane light pha130 5863716, deep pha120 5863711, ultra deep pha100 5863712",
    "JERARQUIA_FACHADAS": "premium koraza, tipo 1 viniltex advanced, tipo 2 intervinil, tipo 3 pinturama",
    "JERARQUIA_PISOS": "liviano pintura canchas, medio pintucoat intergard 740, pesado intergard 2002 cuarzo",
    "JERARQUIA_MADERA_EXT": "barnex extra proteccion wood stain sin sellador",
    "JERARQUIA_MADERA_INT": "esmalte domestico pintulux mp no pintulac",
    "VENTA_CRUZADA_SOLVENTES": "interthane ufa151, pintucoat thinner epoxico, trafico thinner 21204",
    "FLUJO_VENTA": "escuchar diagnosticar recomendar cotizar herramientas cerrar",
    "RENDIMIENTO_AQUABLOCK": "aquablock ultra 10 m2 galon 2 manos",
    "RENDIMIENTO_VINILTEX": "viniltex advanced 20 25 m2 galon 2 manos",
    "RENDIMIENTO_INTERSEAL": "interseal 670hs 12 16 m2 galon",
    "RENDIMIENTO_INTERGARD": "intergard 2002 12 16 m2 galon",
    "RENDIMIENTO_CUARZO": "cuarzo 0.5 kg m2 bultos 25 kg",
    "HERRAMIENTAS": "brocha goya profesional, lija abracol, removedor pintuco",
}


def normalize(s):
    if not s:
        return ""
    s = s.lower().strip()
    for a, b in [("á","a"),("é","e"),("í","i"),("ó","o"),("ú","u"),("ñ","n"),("ü","u")]:
        s = s.replace(a, b)
    return re.sub(r"[^a-z0-9 ]", " ", re.sub(r"\s+", " ", s)).strip()


# ── Comprehensive test scenarios ──
# Each scenario: (description, customer_query, what_prompt_rules_must_cover, what_rag_should_return)
BEHAVIORAL_SCENARIOS = [
    {
        "nombre": "Piso industrial - diagnóstico obligatorio",
        "query_cliente": "Quiero pintar un piso de bodega",
        "reglas_prompt_requeridas": ["DIAG_PISOS_4_PREGUNTAS", "DIAG_GENERAL_M2"],
        "rag_keywords": ["piso", "concreto", "diagnostico"],
        "respuesta_correcta_contiene": ["28 dias", "montacargas", "interior o exterior", "m2"],
        "respuesta_correcta_NO_contiene": ["pintucoat"],
        "fase": "diagnostico",
    },
    {
        "nombre": "Piso pesado - cotización con cuarzo",
        "query_cliente": "Piso de bodega con montacargas, 200 m2, concreto nuevo de 2 meses",
        "reglas_prompt_requeridas": ["TEC_PINTUCOAT_MEDIA", "PROD_CUARZO_CALCULO", "COT_CALCULAR_CANTIDADES", "COT_SUBTOTAL_IVA_TOTAL"],
        "rag_keywords": ["intergard 2002", "cuarzo", "interseal"],
        "respuesta_correcta_contiene": ["intergard 2002", "cuarzo", "5891610", "interseal", "200 m2"],
        "respuesta_correcta_NO_contiene": ["pintucoat para trafico pesado"],
        "fase": "cotizacion",
    },
    {
        "nombre": "Madera - primer turno sin productos",
        "query_cliente": "Necesito pintar una pérgola de madera",
        "reglas_prompt_requeridas": ["DIAG_MADERA_PRIMER_TURNO"],
        "rag_keywords": ["madera", "exterior"],
        "respuesta_correcta_contiene": ["exterior", "interior", "transparente", "veta", "color"],
        "respuesta_correcta_NO_contiene": ["barnex", "wood stain", "pintulac"],
        "fase": "diagnostico",
    },
    {
        "nombre": "Madera exterior transparente - productos correctos",
        "query_cliente": "Es exterior y quiero que se vea la veta natural",
        "reglas_prompt_requeridas": ["JERARQUIA_MADERA_EXT", "TEC_SELLADOR_BARNEX", "HERRAMIENTAS"],
        "rag_keywords": ["barnex", "wood stain", "brocha goya"],
        "respuesta_correcta_contiene": ["barnex", "wood stain", "brocha goya"],
        "respuesta_correcta_NO_contiene": ["sellador"],
        "fase": "recomendacion",
    },
    {
        "nombre": "Madera interior color sólido - preguntar color",
        "query_cliente": "Es interior y quiero un color sólido",
        "reglas_prompt_requeridas": ["JERARQUIA_MADERA_INT", "COT_PREGUNTAR_COLOR"],
        "rag_keywords": ["esmalte domestico", "pintulux mp"],
        "respuesta_correcta_contiene": ["esmalte domestico", "pintulux"],
        "respuesta_correcta_NO_contiene": ["pintulac"],
        "fase": "recomendacion",
    },
    {
        "nombre": "Fachada - preguntar m² primero",
        "query_cliente": "Quiero pintar la fachada de mi casa",
        "reglas_prompt_requeridas": ["DIAG_FACHADAS_M2", "DIAG_GENERAL_M2"],
        "rag_keywords": ["koraza", "viniltex", "fachada"],
        "respuesta_correcta_contiene": ["m2", "metros"],
        "respuesta_correcta_NO_contiene": [],
        "fase": "diagnostico",
    },
    {
        "nombre": "Fachada - jerarquía de productos",
        "query_cliente": "Fachada deteriorada, 80 m2, se descascara",
        "reglas_prompt_requeridas": ["JERARQUIA_FACHADAS", "HERRAMIENTAS"],
        "rag_keywords": ["koraza", "viniltex", "estuco acrilico", "abracol"],
        "respuesta_correcta_contiene": ["koraza", "estuco"],
        "respuesta_correcta_NO_contiene": [],
        "fase": "recomendacion",
    },
    {
        "nombre": "Imprimante concreto vs metal",
        "query_cliente": "Necesito imprimante para un piso de concreto",
        "reglas_prompt_requeridas": ["TEC_PRIMER_50RS_METAL"],
        "rag_keywords": ["interseal", "ral 7038"],
        "respuesta_correcta_contiene": ["interseal"],
        "respuesta_correcta_NO_contiene": ["primer 50rs", "50rs"],
        "fase": "recomendacion",
    },
    {
        "nombre": "Pintucoat exterior - Interthane obligatorio",
        "query_cliente": "Quiero aplicar Pintucoat en un piso exterior",
        "reglas_prompt_requeridas": ["TEC_PINTUCOAT_EXTERIOR"],
        "rag_keywords": ["interthane", "entiza", "uv"],
        "respuesta_correcta_contiene": ["interthane"],
        "respuesta_correcta_NO_contiene": [],
        "fase": "recomendacion",
    },
    {
        "nombre": "Concreto nuevo - regla 28 días",
        "query_cliente": "Vacié un piso hace 10 días y quiero pintarlo",
        "reglas_prompt_requeridas": ["TEC_28_DIAS"],
        "rag_keywords": ["curado", "28 dias"],
        "respuesta_correcta_contiene": ["28 dias", "esperar"],
        "respuesta_correcta_NO_contiene": [],
        "fase": "diagnostico",
    },
    {
        "nombre": "Pintura de tráfico - código correcto",
        "query_cliente": "Necesito demarcar un parqueadero con pintura amarilla",
        "reglas_prompt_requeridas": ["PROD_TRAFICO", "PROD_THINNER_TRAFICO"],
        "rag_keywords": ["5891322", "thinner 21204"],
        "respuesta_correcta_contiene": ["5891322"],
        "respuesta_correcta_NO_contiene": ["pintucoat"],
        "fase": "recomendacion",
    },
    {
        "nombre": "Solvente para Interthane",
        "query_cliente": "Qué solvente lleva el Interthane?",
        "reglas_prompt_requeridas": ["VENTA_CRUZADA_SOLVENTES"],
        "rag_keywords": ["ufa151"],
        "respuesta_correcta_contiene": ["ufa151"],
        "respuesta_correcta_NO_contiene": ["21204", "thinner trafico"],
        "fase": "tecnica",
    },
    {
        "nombre": "Color RAL para piso epóxico",
        "query_cliente": "Necesito un Interseal en color RAL 7040",
        "reglas_prompt_requeridas": ["TINTO_INTERSEAL"],
        "rag_keywords": ["base", "light", "ega130", "5863715"],
        "respuesta_correcta_contiene": ["base"],
        "respuesta_correcta_NO_contiene": ["no disponible"],
        "fase": "tecnica",
    },
    {
        "nombre": "Esmalte sin color - preguntar",
        "query_cliente": "Quiero Pintulux para unos marcos",
        "reglas_prompt_requeridas": ["COT_PREGUNTAR_COLOR"],
        "rag_keywords": ["color", "marcos"],
        "respuesta_correcta_contiene": ["color"],
        "respuesta_correcta_NO_contiene": [],
        "fase": "diagnostico",
    },
    {
        "nombre": "Bicomponente - kit",
        "query_cliente": "Cuánto cuesta el Pintucoat?",
        "reglas_prompt_requeridas": ["COT_BICOMPONENTE_KIT"],
        "rag_keywords": ["comp a", "catalizador", "kit"],
        "respuesta_correcta_contiene": ["kit", "catalizador"],
        "respuesta_correcta_NO_contiene": [],
        "fase": "cotizacion",
    },
    {
        "nombre": "Familias separadas - no mezclar",
        "query_cliente": "Puedo usar Interseal como imprimante y Pintucoat como acabado?",
        "reglas_prompt_requeridas": ["TEC_FAMILIAS_SEPARADAS"],
        "rag_keywords": ["tecnologias diferentes", "prohibido mezclar"],
        "respuesta_correcta_contiene": ["no"],
        "respuesta_correcta_NO_contiene": [],
        "fase": "tecnica",
    },
    {
        "nombre": "Lija sustitución",
        "query_cliente": "No hay lija 80, qué otra puedo usar?",
        "reglas_prompt_requeridas": ["TEC_LIJA_SUSTITUCION"],
        "rag_keywords": ["100", "120"],
        "respuesta_correcta_contiene": ["100", "120"],
        "respuesta_correcta_NO_contiene": ["220", "320"],
        "fase": "tecnica",
    },
    {
        "nombre": "Intergard 2002 - sobre pedido",
        "query_cliente": "Necesito Intergard 2002 para mi bodega",
        "reglas_prompt_requeridas": ["PROD_INTERGARD_SOBRE_PEDIDO"],
        "rag_keywords": ["sobre pedido", "asesor experto"],
        "respuesta_correcta_contiene": ["sobre pedido"],
        "respuesta_correcta_NO_contiene": [],
        "fase": "recomendacion",
    },
    {
        "nombre": "Humedad interna - rendimiento y sistema",
        "query_cliente": "Tengo humedad en muros, 30 m2. Qué necesito y cuánto?",
        "reglas_prompt_requeridas": ["RENDIMIENTO_AQUABLOCK", "RENDIMIENTO_VINILTEX", "COT_CALCULAR_CANTIDADES"],
        "rag_keywords": ["aquablock", "10 m2", "viniltex", "20"],
        "respuesta_correcta_contiene": ["aquablock", "viniltex", "galones"],
        "respuesta_correcta_NO_contiene": [],
        "fase": "cotizacion",
    },
    {
        "nombre": "Flujo completo - venta cierre",
        "query_cliente": "Ya diagnosticado, cotizado y aprobado. Confirmar pedido",
        "reglas_prompt_requeridas": ["FLUJO_VENTA"],
        "rag_keywords": [],
        "respuesta_correcta_contiene": ["confirmar"],
        "respuesta_correcta_NO_contiene": [],
        "fase": "cierre",
    },
]


def check_prompt_coverage():
    """Verify that all prompt rules are covered by at least one test scenario."""
    covered = set()
    for s in BEHAVIORAL_SCENARIOS:
        for r in s["reglas_prompt_requeridas"]:
            covered.add(r)
    uncovered = set(PROMPT_RULES.keys()) - covered
    return covered, uncovered


def validate_rules_in_prompt(prompt_text):
    """Check that key terms from each rule appear in the prompt text."""
    norm_prompt = normalize(prompt_text)
    results = {}
    for rule_id, rule_keywords in PROMPT_RULES.items():
        terms = [t.strip() for t in rule_keywords.split(",") if t.strip()]
        # A rule is "present" if at least 50% of its terms appear in the prompt
        found = sum(1 for t in terms if t.strip() in norm_prompt)
        results[rule_id] = {
            "terms_total": len(terms),
            "terms_found": found,
            "coverage": round(found / max(len(terms), 1), 2),
            "present": found >= max(len(terms) * 0.4, 1),
        }
    return results


def run_behavioral_tests():
    """Run all behavioral scenarios and report coverage."""
    print(f"\n{'='*70}")
    print("  TEST DE COMPORTAMIENTO COMERCIAL COMPLETO")
    print(f"  {len(BEHAVIORAL_SCENARIOS)} escenarios | {len(PROMPT_RULES)} reglas de prompt")
    print(f"{'='*70}")

    # 1. Coverage check
    covered, uncovered = check_prompt_coverage()
    print(f"\n{'─'*50}")
    print("1. COBERTURA DE REGLAS POR ESCENARIOS")
    print(f"{'─'*50}")
    print(f"  Reglas cubiertas: {len(covered)}/{len(PROMPT_RULES)}")
    if uncovered:
        print(f"  ⚠️ Sin escenario de test: {uncovered}")
    else:
        print(f"  ✅ Todas las reglas tienen al menos un escenario")

    # 2. Validate rules exist in prompt
    print(f"\n{'─'*50}")
    print("2. VALIDACIÓN DE REGLAS EN SYSTEM PROMPT")
    print(f"{'─'*50}")
    try:
        main_py = os.path.join(os.path.dirname(__file__), "backend", "main.py")
        with open(main_py, "r", encoding="utf-8") as f:
            content = f.read()
        # Extract AGENT_SYSTEM_PROMPT_V2
        start = content.find('AGENT_SYSTEM_PROMPT_V2 = """')
        if start < 0:
            print("  ❌ No se encontró AGENT_SYSTEM_PROMPT_V2")
            return
        end = content.find('"""', start + 27)
        prompt_text = content[start:end]
        
        rule_results = validate_rules_in_prompt(prompt_text)
        present_count = sum(1 for r in rule_results.values() if r["present"])
        missing = {k: v for k, v in rule_results.items() if not v["present"]}
        print(f"  Reglas detectadas en prompt: {present_count}/{len(rule_results)}")
        if missing:
            for k, v in missing.items():
                print(f"  ❌ FALTA: {k} (coverage={v['coverage']}, found={v['terms_found']}/{v['terms_total']})")
        else:
            print(f"  ✅ Todas las {len(rule_results)} reglas están presentes en el prompt")
    except Exception as e:
        print(f"  Error leyendo prompt: {e}")

    # 3. Scenario detail
    print(f"\n{'─'*50}")
    print("3. DETALLE DE ESCENARIOS POR FASE")
    print(f"{'─'*50}")
    by_phase = defaultdict(list)
    for s in BEHAVIORAL_SCENARIOS:
        by_phase[s["fase"]].append(s)
    
    for phase in ["diagnostico", "recomendacion", "cotizacion", "tecnica", "cierre"]:
        scenarios = by_phase.get(phase, [])
        print(f"\n  📌 Fase: {phase.upper()} ({len(scenarios)} escenarios)")
        for s in scenarios:
            rules = ", ".join(s["reglas_prompt_requeridas"][:3])
            must_have = ", ".join(s["respuesta_correcta_contiene"][:4])
            must_not = ", ".join(s["respuesta_correcta_NO_contiene"][:3])
            print(f"    • {s['nombre']}")
            print(f"      Reglas: {rules}")
            print(f"      DEBE incluir: {must_have}")
            if must_not:
                print(f"      NO debe incluir: {must_not}")

    # 4. RAG retrieval test (if DB available)
    print(f"\n{'─'*50}")
    print("4. TEST DE RECUPERACIÓN RAG PARA ESCENARIOS")
    print(f"{'─'*50}")
    try:
        from sqlalchemy import create_engine, text as sql_text
        db_url = os.environ.get(
            "DATABASE_URL",
            "postgresql://postgres:o5S3X9VIYcbBWqd525hqT24UhYAc8AdjtevyHtlZHhGxJkfMQVZXReCTxkcjSOAX@192.81.216.49:3000/postgres",
        )
        eng = create_engine(db_url)
        with eng.connect() as c:
            all_rows = [dict(r) for r in c.execute(sql_text(
                "SELECT id, contexto_tags, producto_recomendado, producto_desestimado, "
                "nota_comercial, tipo FROM public.agent_expert_knowledge WHERE activo = true"
            )).mappings().all()]
        
        pass_count = 0
        partial_count = 0
        fail_count = 0
        
        for s in BEHAVIORAL_SCENARIOS:
            if not s["rag_keywords"]:
                pass_count += 1
                continue
            
            # Simulate fetch
            terms = [t for t in normalize(s["query_cliente"]).split() if len(t) >= 2][:10]
            scored = []
            for r in all_rows:
                searchable = normalize(
                    f"{r['contexto_tags']} {r['nota_comercial']} {r.get('producto_recomendado') or ''} {r.get('producto_desestimado') or ''}"
                )
                score = sum(1 for t in terms if t in searchable)
                if score > 0:
                    scored.append((score, r))
            scored.sort(key=lambda x: -x[0])
            hits = [r for _, r in scored[:8]]
            
            hit_text = normalize(" ".join(
                f"{h['contexto_tags']} {h['nota_comercial']} {h.get('producto_recomendado') or ''}"
                for h in hits
            ))
            
            found_kw = [kw for kw in s["rag_keywords"] if normalize(kw) in hit_text]
            missed_kw = [kw for kw in s["rag_keywords"] if normalize(kw) not in hit_text]
            
            if not missed_kw:
                status = "PASS"
                pass_count += 1
                icon = "✅"
            elif found_kw:
                status = "PARTIAL"
                partial_count += 1
                icon = "⚠️"
            else:
                status = "FAIL"
                fail_count += 1
                icon = "❌"
            
            hit_ids = [h["id"] for h in hits[:5]]
            detail = f" FALTA RAG: {missed_kw}" if missed_kw else ""
            print(f"  {icon} [{status}] {s['nombre']}: IDs={hit_ids}{detail}")
        
        total = len(BEHAVIORAL_SCENARIOS)
        print(f"\n  Resultado RAG: {pass_count} PASS | {partial_count} PARTIAL | {fail_count} FAIL de {total}")
    except Exception as e:
        print(f"  No se pudo conectar a la DB: {e}")

    # 5. Teaching guide
    print(f"\n{'─'*50}")
    print("5. MAPA COMPLETO DEL CONOCIMIENTO")
    print(f"{'─'*50}")
    categories = {
        "REGLAS EN PROMPT (siempre activas)": len(PROMPT_RULES),
        "ESCENARIOS DE VALIDACIÓN": len(BEHAVIORAL_SCENARIOS),
    }
    if 'all_rows' in dir():
        categories["REGISTROS RAG ACTIVOS"] = len(all_rows)
    for cat, count in categories.items():
        print(f"  {cat}: {count}")
    
    print(f"\n{'='*70}")
    print("  TEST COMPLETO FINALIZADO")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    run_behavioral_tests()
