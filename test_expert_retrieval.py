#!/usr/bin/env python3
"""
Test de Retrieval del Conocimiento Experto — CRM Ferreinox
============================================================
Simula las queries exactas que consultar_conocimiento_tecnico envía a
fetch_expert_knowledge() y verifica que las enseñanzas de Pablo y Diego se recuperan.

Ejecutar:  python test_expert_retrieval.py
"""
import os, sys, json

# ── Bootstrap: punto al backend para imports ──
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql://postgres:o5S3X9VIYcbBWqd525hqT24UhYAc8AdjtevyHtlZHhGxJkfMQVZXReCTxkcjSOAX@192.81.216.49:3000/postgres",
)

from main import fetch_expert_knowledge, normalize_text_value

# ── Escenarios de prueba ──
# Cada tupla: (query que armaría consultar_conocimiento_tecnico, notas esperadas parciales)
TEST_CASES = [
    # 1. Pisos industriales — debe traer Interseal 670HS, cuarzo, Intergard 2002, Pintucoat
    (
        "pintucoat piso industrial bodega montacargas",
        ["interseal", "cuarzo", "intergard", "pintucoat"],
    ),
    # 2. Sealer F100 en concreto liso
    (
        "sealer f100 imprimante concreto liso",
        ["sealer f100", "concreto"],
    ),
    # 3. Cuarzo + cálculo + broadcasting
    (
        "cuarzo broadcasting antideslizante piso",
        ["cuarzo", "broadcasting"],
    ),
    # 4. Intergard 2002 bloqueo comercial / sobre pedido
    (
        "intergard 2002 precio stock",
        ["intergard 2002", "sobre pedido"],
    ),
    # 5. Madera exterior — debe traer Barnex, NO sellador
    (
        "madera exterior pergola barniz",
        ["barnex", "sellador"],  # debe aparecer la contraindicación del sellador
    ),
    # 6. Fachadas — debe traer Koraza, m², jerarquía
    (
        "koraza fachada pintura metros cuadrados",
        ["koraza", "fachada"],
    ),
    # 7. Humedad interna (enseñanza de Pablo)
    (
        "humedad interna muro salitre ampollas",
        ["aquablock", "raspar", "humedad"],
    ),
    # 8. Tanque agua potable (enseñanza de Pablo)
    (
        "tanque agua potable epoxico",
        ["pintucoat", "epoxipoliamida", "agua potable"],
    ),
    # 9. Primer 50RS contraindicación pisos
    (
        "primer 50rs piso concreto imprimante",
        ["primer 50rs", "metal"],
    ),
    # 10. Lija sustitución
    (
        "lija abracol grano sustitucion",
        ["grano", "lija"],
    ),
]

PASS = 0
FAIL = 0
WARN = 0

print(f"\n{'='*80}")
print("  TEST DE RETRIEVAL — CONOCIMIENTO EXPERTO FERREINOX")
print(f"{'='*80}\n")

for i, (query, expected_keywords) in enumerate(TEST_CASES, 1):
    results = fetch_expert_knowledge(query, limit=5)
    
    # Flatten all text from results for keyword checking
    blob = " ".join(
        f"{r.get('contexto_tags','')} {r.get('nota_comercial','')} {r.get('producto_recomendado','')} {r.get('producto_desestimado','')}"
        for r in results
    ).lower()
    
    found = [kw for kw in expected_keywords if kw.lower() in blob]
    missing = [kw for kw in expected_keywords if kw.lower() not in blob]
    
    if not results:
        status = "❌ FAIL"
        FAIL += 1
        detail = "NO SE RECUPERÓ NINGÚN RESULTADO"
    elif missing:
        status = "⚠️ PARCIAL"
        WARN += 1
        detail = f"Encontrados: {found} | Faltan: {missing}"
    else:
        status = "✅ PASS"
        PASS += 1
        detail = f"Todos los keywords encontrados: {found}"
    
    print(f"Test {i:2d} | {status}")
    print(f"  Query:    \"{query}\"")
    print(f"  Results:  {len(results)} notas recuperadas")
    print(f"  Detail:   {detail}")
    if results:
        for r in results[:2]:  # show first 2
            print(f"    → [ID {r['id']}] {r.get('tipo','?')} | tags: {r.get('contexto_tags','')[:60]}...")
    print()

# ── Resumen ──
total = PASS + FAIL + WARN
print(f"{'─'*80}")
print(f"RESUMEN: {PASS}/{total} PASS | {WARN}/{total} PARCIAL | {FAIL}/{total} FAIL")
if FAIL > 0:
    print("🚨 HAY FALLOS — el conocimiento experto NO se está recuperando correctamente.")
elif WARN > 0:
    print("⚠️ Parciales — algunas enseñanzas se pierden por el método de búsqueda ILIKE.")
else:
    print("✅ TODAS las enseñanzas se recuperan correctamente.")

# ── Análisis de cuellos de botella ──
print(f"\n{'─'*80}")
print("ANÁLISIS DEL PIPELINE DE RETRIEVAL:")
print(f"{'─'*80}")

# Test: términos cortos que se pierden
short_terms_test = "m² UV F100 NSF pH"
normalized = normalize_text_value(short_terms_test)
terms = [t for t in normalized.split() if len(t) >= 4]
dropped = [t for t in normalized.split() if len(t) < 4]
print(f"\n  Filtro de términos cortos (≥4 chars):")
print(f"    Input:   \"{short_terms_test}\"")
print(f"    Pasan:   {terms}")
print(f"    PERDIDOS: {dropped}")
if dropped:
    print(f"    ⚠️ Estos términos NUNCA matchearán en la búsqueda experta.")

# Test: limit de 4 vs 38 registros
print(f"\n  Límite de resultados:")
print(f"    38 registros en DB, limit=4 por llamada")
all_results = fetch_expert_knowledge("piso industrial concreto pintucoat interseal intergard cuarzo", limit=20)
print(f"    Query amplia (7 keywords) devuelve: {len(all_results)} registros")
if len(all_results) > 4:
    print(f"    ⚠️ Con limit=4, se pierden {len(all_results) - 4} notas relevantes.")
    print(f"    IDs que se verían: {[r['id'] for r in all_results[:4]]}")
    print(f"    IDs PERDIDOS:      {[r['id'] for r in all_results[4:]]}")

print(f"\n{'='*80}\n")
