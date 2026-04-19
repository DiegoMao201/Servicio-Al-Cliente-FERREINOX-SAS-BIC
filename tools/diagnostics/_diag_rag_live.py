"""Diagnóstico LIVE del RAG, Expert Knowledge y Complementarios."""
import requests, json, sys

URL = "https://apicrm.datovatenexuspro.com/admin/agent-test"
HEADERS = {"x-admin-key": "ferreinox_admin_2024", "Content-Type": "application/json"}

def test_query(label, msg, conv_id):
    print(f"\n{'='*60}")
    print(f"TEST: {label}")
    print(f"QUERY: {msg}")
    print(f"{'='*60}")
    payload = {
        "profile_name": "Test RAG",
        "conversation_context": {},
        "recent_messages": [],
        "user_message": msg,
        "context": {
            "conversation_id": conv_id,
            "contact_id": conv_id,
            "cliente_id": None,
            "telefono_e164": "+573000000001",
            "nombre_visible": "Test RAG",
        },
    }
    resp = requests.post(URL, headers=HEADERS, json=payload, timeout=120)
    data = resp.json().get("result", {})

    # Tools
    tools = data.get("tool_calls") or []
    print(f"\nTOOLS CALLED ({len(tools)}):")
    for tc in tools:
        name = tc["name"]
        args = json.dumps(tc.get("args", {}), ensure_ascii=False)
        print(f"  -> {name}: {args[:200]}")
        raw = tc.get("result", "")
        if isinstance(raw, str):
            try:
                parsed = json.loads(raw)
            except Exception:
                print(f"     raw result: {raw[:200]}")
                continue

            if name == "consultar_conocimiento_tecnico":
                print(f"     encontrado: {parsed.get('encontrado')}")
                print(f"     mejor_similitud: {parsed.get('mejor_similitud')}")
                fuentes = parsed.get("archivos_fuente", [])
                print(f"     archivos_fuente: {fuentes}")
                rag = parsed.get("respuesta_rag", "")
                print(f"     respuesta_rag (500ch): {rag[:500]}")
                exp = parsed.get("conocimiento_comercial_ferreinox", "")
                if exp:
                    print(f"     EXPERT KNOWLEDGE: {str(exp)[:500]}")
                else:
                    print(f"     EXPERT KNOWLEDGE: (vacío/no encontrado)")

            elif name in ("consultar_inventario", "consultar_inventario_lote"):
                prods = parsed.get("resultados") or parsed.get("productos") or []
                if isinstance(prods, list):
                    print(f"     productos encontrados: {len(prods)}")
                    for p in prods[:5]:
                        desc = p.get("descripcion", "?")
                        ref = p.get("referencia", "")
                        precio = p.get("precio", "N/A")
                        stock = p.get("stock_total", "?")
                        comps = p.get("productos_complementarios", [])
                        print(f"     -> {desc} | ref={ref} | ${precio} | stock={stock} | complementarios={len(comps)}")
                        for c in comps[:5]:
                            print(f"        COMP: tipo={c.get('tipo','')} | {c.get('descripcion','')} | ref={c.get('referencia','')} | ${c.get('precio','?')} | stock={c.get('stock_total','?')}")
                else:
                    print(f"     result: {str(prods)[:300]}")
            else:
                print(f"     result keys: {list(parsed.keys()) if isinstance(parsed, dict) else type(parsed).__name__}")

    print(f"\nRESPONSE (500ch):")
    print((data.get("response_text", ""))[:500])
    print(f"\nTHINKING (300ch):")
    print((data.get("thinking", "") or "")[:300])
    return data


if __name__ == "__main__":
    # Test 1: Piso tráfico pesado — should ask diagnostic questions, NOT recommend
    r1 = test_query(
        "PISO TRAFICO PESADO - debe preguntar diagnóstico",
        "necesito pintar un piso de tráfico pesado",
        99991
    )

    # Test 2: Query about dilution — should find RAG dilution rules
    r2 = test_query(
        "DILUCION EPOXICOS - debe traer reglas de dilución",
        "cómo se diluye una pintura epóxica?",
        99992
    )

    # Test 3: Specific product with complementarios — should show prices
    r3 = test_query(
        "INTERGARD 2002 CON COMPLEMENTARIOS",
        "quiero Intergard 2002, necesito todo lo que lleva",
        99993
    )

    # Test 4: Expert knowledge check — should retrieve seeded knowledge
    r4 = test_query(
        "CONOCIMIENTO EXPERTO - pisos industriales",
        "qué sistema recomiendan para pisos de bodegas?",
        99994
    )

    print("\n" + "="*60)
    print("RESUMEN DIAGNÓSTICO")
    print("="*60)

    # Check T1: Did it ask questions or just give a recommendation?
    t1_resp = (r1.get("response_text", "") or "").lower()
    t1_tools = [tc["name"] for tc in (r1.get("tool_calls") or [])]
    asked_questions = any(w in t1_resp for w in ["metros cuadrados", "m²", "interior", "exterior", "superficie", "área", "qué tipo", "cuántos"])
    print(f"\nT1 PISO: {'✅ PREGUNTÓ diagnóstico' if asked_questions else '❌ NO preguntó — recomendó directo'}")
    print(f"   Tools: {t1_tools}")

    # Check T2: Did RAG return dilution rules?
    t2_tools = r2.get("tool_calls") or []
    rag_called = False
    rag_found = False
    for tc in t2_tools:
        if tc["name"] == "consultar_conocimiento_tecnico":
            rag_called = True
            try:
                p = json.loads(tc.get("result", ""))
                if p.get("encontrado"):
                    rag_found = True
            except:
                pass
    print(f"\nT2 DILUCIÓN: RAG llamado={'✅' if rag_called else '❌'} | Encontró datos={'✅' if rag_found else '❌'}")

    # Check T3: Complementarios with prices
    t3_tools = r3.get("tool_calls") or []
    inv_called = False
    comps_with_price = 0
    comps_total = 0
    for tc in t3_tools:
        if tc["name"] in ("consultar_inventario", "consultar_inventario_lote"):
            inv_called = True
            try:
                p = json.loads(tc.get("result", ""))
                prods = p.get("resultados") or p.get("productos") or []
                for prod in prods:
                    for c in prod.get("productos_complementarios", []):
                        comps_total += 1
                        if c.get("precio") and c.get("precio") != "N/A":
                            comps_with_price += 1
            except:
                pass
    print(f"\nT3 COMPLEMENTARIOS: Inventario={'✅' if inv_called else '❌'} | Complementarios={comps_total} | Con precio={comps_with_price}")

    # Check T4: Expert knowledge used?
    t4_tools = r4.get("tool_calls") or []
    expert_found = False
    for tc in t4_tools:
        if tc["name"] == "consultar_conocimiento_tecnico":
            try:
                p = json.loads(tc.get("result", ""))
                exp = p.get("conocimiento_comercial_ferreinox", "")
                if exp:
                    expert_found = True
            except:
                pass
    print(f"\nT4 EXPERT KNOWLEDGE: {'✅ Se encontró' if expert_found else '❌ No se encontró/vacío'}")
