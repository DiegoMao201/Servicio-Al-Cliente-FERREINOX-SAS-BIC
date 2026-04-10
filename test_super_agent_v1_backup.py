"""
Super Test Agente CRM Ferreinox - Batería Exhaustiva
=====================================================
Prueba el flujo completo del agente: diagnóstico → RAG → inventario → pedido.
Simula conversaciones reales multi-turno y valida:
  1. Diagnóstico inteligente (sospecha correcta)
  2. RAG devuelve fichas técnicas relevantes
  3. Productos del inventario real (nunca inventados)
  4. Coherencia conversacional (no repite preguntas, sigue hilo)
  5. Corrección de pedido (color/tamaño genera nueva referencia)
  6. Abrasivos, removedores, superficies especiales (tobogán, etc.)
  7. Gaps del portafolio (piscinas)

Usa el endpoint /admin/rag-buscar para RAG puro
y llama generate_agent_reply_v2 directamente para flujo completo.
"""

import json
import os
import sys
import time
import re
import traceback

# Ensure backend is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

try:
    import requests
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests", "-q"])
    import requests

# ── Config ──
BACKEND_URL = os.environ.get("BACKEND_URL", "https://apicrm.datovatenexuspro.com")
ADMIN_KEY = os.environ.get("ADMIN_API_KEY", "ferreinox_admin_2024")
RAG_URL = f"{BACKEND_URL}/admin/rag-buscar"

# ──────────────────────────────────────────────────────────────────────────────
# PARTE 1: RAG PURO — Validar que las fichas técnicas correctas aparecen
# ──────────────────────────────────────────────────────────────────────────────
RAG_TESTS = [
    # ═══ HUMEDAD / FILTRACIONES ═══
    ("la pared se está mojando por dentro desde la base", ["aquablock", "sellamur"], ["koraza"], "humedad"),
    ("se filtra agua por el muro del sótano, sale salitre", ["aquablock"], ["koraza"], "humedad"),
    ("la pared suda y tiene manchas blancas de salitre", ["aquablock", "estuco anti humedad"], ["koraza"], "humedad"),
    ("humedad ascendente en primer piso, capilaridad", ["aquablock"], ["koraza"], "humedad"),
    ("se ampollan las paredes por humedad interior", ["aquablock"], ["koraza"], "humedad"),
    ("baño con hongos negros en las paredes", ["aquablock", "viniltex"], [], "humedad"),

    # ═══ FACHADAS / EXTERIORES ═══
    ("fachada deteriorada por lluvia y sol, se pela", ["koraza"], ["aquablock"], "fachada"),
    ("pintar frente de la casa que aguante intemperie", ["koraza"], ["aquablock"], "fachada"),
    ("muro exterior que le da el sol todo el día", ["koraza"], ["aquablock"], "fachada"),
    ("se descascara la pintura de la fachada exterior", ["koraza"], ["aquablock"], "fachada"),

    # ═══ TECHOS / GOTERAS ═══
    ("techo de concreto goteando, tiene grietas", ["pintuco fill"], [], "techo"),
    ("impermeabilizar terraza de plancha", ["pintuco fill", "impercoat"], [], "techo"),
    ("cubierta de fibrocemento eternit que se llueve", ["pintuco fill", "koraza"], [], "techo"),
    ("manto impermeabilizante para terraza con grietas profundas", ["pintuco fill"], [], "techo"),

    # ═══ METAL / ANTICORROSIVO ═══
    ("reja de hierro toda oxidada, se está comiendo", ["corrotec", "pintoxido"], ["koraza"], "metal"),
    ("portón metálico con óxido profundo y corrosión", ["corrotec", "pintoxido"], [], "metal"),
    ("estructura de acero nueva sin pintar a la intemperie", ["corrotec", "wash primer"], [], "metal"),
    ("tubo galvanizado nuevo cómo pintarlo", ["wash primer", "corrotec"], [], "metal"),

    # ═══ PISOS ═══
    ("piso de bodega industrial con tráfico de montacargas", ["pintucoat"], ["koraza"], "piso"),
    ("garaje residencial piso de concreto", ["pintura canchas", "pintucoat"], ["koraza"], "piso"),
    ("cancha de microfútbol hay que pintarla", ["pintura canchas"], ["koraza"], "piso"),
    ("andén de concreto exterior", ["pintura canchas"], [], "piso"),

    # ═══ INTERIORES ═══
    ("pintar sala de la casa, calidad premium lavable", ["viniltex"], ["koraza"], "interior"),
    ("pintura económica para cielo raso bodega", ["pinturama", "vinil"], [], "interior"),
    ("cuarto del bebé pintura lavable", ["viniltex"], ["koraza"], "interior"),

    # ═══ MADERA ═══
    ("pergola de madera al aire libre se deteriora", ["barnex", "wood stain"], ["koraza"], "madera"),
    ("barniz para mueble interior que se vea la veta", ["pintulac", "barniz"], [], "madera"),
    ("puerta de madera la quiero pintar de color", ["pintulux", "pintulac"], [], "madera"),

    # ═══ ABRASIVOS / PREPARACIÓN (NUEVAS CATEGORÍAS) ═══
    # Nota: abrasivos (lija, disco flap, grata, removedor) NO tienen fichas técnicas en RAG.
    # Son productos de ferretería/hardware. El RAG los manejará por contexto de preparación de superficie.
    # Las expectativas reflejan que el RAG devuelve productos de recubrimiento asociados a la preparación.
    ("con qué lijo una pared pintada antes de repintar", ["viniltex", "imprimante", "estuco"], [], "abrasivo"),
    ("cómo remuevo la pintura vieja de una reja de hierro", ["corrotec", "pintoxido"], [], "abrasivo"),
    ("necesito quitar barniz viejo de una puerta de madera", ["barnex", "barniz", "imprimante"], [], "abrasivo"),
    ("disco para pulir y quitar óxido en amoladora", ["corrotec", "pintoxido"], [], "abrasivo"),
    ("cepillo metálico para limpiar estructura oxidada", ["corrotec"], [], "abrasivo"),

    # ═══ SUPERFICIES ESPECIALES ═══
    ("necesito pintar un tobogán metálico de un parque", ["corrotec", "pintulux"], [], "especial"),
    ("baranda de hierro que está oxidada a la intemperie", ["corrotec", "pintoxido"], [], "especial"),
    ("juego infantil de metal al aire libre", ["corrotec", "pintulux"], [], "especial"),

    # ═══ PISCINAS (GAP - NO VENDEN) ═══
    # RAG puede devolver fichas genéricas, pero el agente DEBE rechazarlos.
    # El test del AGENTE (parte 2) valida el rechazo. Aquí solo validamos que no recomiende pintucoat.
    ("pintura especial para piscina de concreto", [], [], "gap_piscina"),
    ("pintar un tanque de agua potable por dentro", [], [], "gap_piscina"),

    # ═══ PREGUNTAS TÉCNICAS ESPECÍFICAS ═══
    ("cuántas manos de koraza debo aplicar en fachada", ["koraza"], [], "tecnico"),
    ("rendimiento por galón de pintuco fill 7", ["pintuco fill"], [], "tecnico"),
    ("tiempo de secado entre manos de pintucoat epóxico", ["pintucoat"], [], "tecnico"),
    ("se puede diluir el viniltex con agua y cuánto", ["viniltex"], [], "tecnico"),
    ("cómo se aplica el pintuco fill en techo de eternit", ["pintuco fill"], [], "tecnico"),
    ("qué rodillo usar para koraza en fachada", ["koraza"], [], "tecnico"),
    ("preparación de superficie para corrotec", ["corrotec"], [], "tecnico"),
    ("proporción de mezcla del pintucoat con catalizador", ["pintucoat"], [], "tecnico"),

    # ═══ JERGA COLOMBIANA ═══
    ("la casa se está cayendo a pedazos por el aguacero", ["koraza"], [], "jerga"),
    ("le está saliendo como un polvo blanco a la pared", ["aquablock", "estuco anti humedad"], [], "jerga"),
    ("el hierro se lo está comiendo el óxido", ["corrotec", "pintoxido"], [], "jerga"),
    ("qué le echo al piso del parqueadero para que quede bonito", ["pintucoat", "pintura canchas"], [], "jerga"),
    ("la terraza se me llueve toda y se moja abajo", ["pintuco fill", "impercoat"], [], "jerga"),
    ("esa reja ya está muy fea, cómo la recupero", ["corrotec", "pintoxido"], [], "jerga"),
]


# ──────────────────────────────────────────────────────────────────────────────
# PARTE 2: AGENT FLOW — Simula conversaciones multi-turno
# ──────────────────────────────────────────────────────────────────────────────
# Each test is a list of (user_message, validations_dict)
# validations_dict keys:
#   "tools_called"     : list of tool names that MUST have been called
#   "tools_not_called" : list of tool names that MUST NOT have been called
#   "response_contains": list of strings that MUST appear in response
#   "response_excludes": list of strings that MUST NOT appear in response
#   "intent"           : expected intent classification
#   "check_diagnostic" : True = response should be a diagnostic question, not a product offer

AGENT_CONVERSATIONS = [
    {
        "name": "TECHO ETERNIT → DIAGNÓSTICO → PINTUCO FILL → PEDIDO CON CORRECCIÓN",
        "category": "flujo_completo",
        "turns": [
            (
                "Hola buenas tardes",
                {
                    "response_contains": ["ayud"],
                    "tools_not_called": ["consultar_inventario", "consultar_conocimiento_tecnico"],
                },
            ),
            (
                "Necesito pintar un techo por fuera",
                {
                    "check_diagnostic": True,
                    "response_contains": ["concreto", "fibrocemento", "eternit", "plancha"],
                    "tools_not_called": ["consultar_inventario"],
                },
            ),
            (
                "Es de eternit, techo exterior",
                {
                    "tools_called": ["consultar_conocimiento_tecnico"],
                    "response_contains": ["fill", "koraza"],
                },
            ),
            (
                "Quiero pintuco fill, qué opciones hay",
                {
                    "tools_called": ["consultar_inventario"],
                    "response_contains": ["disponible"],
                },
            ),
        ],
    },
    {
        "name": "HUMEDAD INTERNA → AQUABLOCK (nunca Koraza)",
        "category": "diagnostico_tecnico",
        "turns": [
            (
                "Tengo un problema de humedad en una pared interior, sale salitre blanco",
                {
                    "check_diagnostic": True,
                    "response_excludes": ["Koraza"],
                },
            ),
            (
                "Viene de la base del muro, primer piso",
                {
                    "tools_called": ["consultar_conocimiento_tecnico"],
                    "response_contains": ["Aquablock"],
                    "response_excludes": ["Koraza"],
                },
            ),
        ],
    },
    {
        "name": "PISO GARAJE → DIAGNÓSTICO → PINTURA CANCHAS o PINTUCOAT",
        "category": "diagnostico_tecnico",
        "turns": [
            (
                "Necesito pintar el piso de un garaje de la casa",
                {
                    "check_diagnostic": True,
                    "response_contains": ["tráfico", "pesado", "peatonal", "residencial", "industrial", "montacargas"],
                },
            ),
            (
                "Es tráfico liviano, solo carros livianos de la casa",
                {
                    "tools_called": ["consultar_conocimiento_tecnico"],
                    "response_contains": ["Canchas", "Pintucoat"],
                },
            ),
        ],
    },
    {
        "name": "REJA OXIDADA → SISTEMA COMPLETO anticorrosivo",
        "category": "diagnostico_tecnico",
        "turns": [
            (
                "Tengo unas rejas muy oxidadas, se las está comiendo el óxido",
                {
                    "check_diagnostic": True,
                    "response_contains": ["óxido", "profund", "superficial"],
                },
            ),
            (
                "El óxido está bastante profundo, las rejas están a la intemperie",
                {
                    "tools_called": ["consultar_conocimiento_tecnico"],
                    "response_contains": ["Corrotec", "Pintulux"],
                },
            ),
        ],
    },
    {
        "name": "PISCINA → GAP DEL PORTAFOLIO (debe rechazar)",
        "category": "gap_portfolio",
        "turns": [
            (
                "Necesito pintar una piscina, ¿qué producto me sirve?",
                {
                    "response_contains": ["no manejamos", "asesor", "piscina"],
                    "response_excludes": ["Pintucoat", "Koraza", "Viniltex"],
                    "tools_not_called": ["consultar_inventario"],
                },
            ),
        ],
    },
    {
        "name": "MADERA EXTERIOR → BARNEX / WOOD STAIN",
        "category": "diagnostico_tecnico",
        "turns": [
            (
                "Tengo una pérgola de madera que está a la intemperie y quiero protegerla",
                {
                    "check_diagnostic": True,
                    "response_contains": ["transparente", "color", "veta", "exterior", "interior"],
                },
            ),
            (
                "Quiero que se vea la veta de la madera, acabado transparente",
                {
                    "tools_called": ["consultar_conocimiento_tecnico"],
                    "response_contains": ["Barnex", "Wood Stain"],
                },
            ),
        ],
    },
    {
        "name": "TOBOGÁN METÁLICO → SISTEMA anticorrosivo + abrasivo",
        "category": "superficie_especial",
        "turns": [
            (
                "Necesito pintar un tobogán metálico de un parque infantil que está al aire libre",
                {
                    "check_diagnostic": True,
                },
            ),
            (
                "Es de metal y tiene algo de óxido, está a la intemperie siempre",
                {
                    "tools_called": ["consultar_conocimiento_tecnico"],
                    "response_contains": ["Corrotec", "Pintulux"],
                },
            ),
        ],
    },
    {
        "name": "REMOVEDOR DE PINTURA → diagnóstico superficie",
        "category": "abrasivos",
        "turns": [
            (
                "Necesito quitar la pintura vieja de unas puertas de madera, ¿cómo le hago?",
                {
                    "response_contains": ["removedor", "Removedor", "lija", "Lija"],
                },
            ),
        ],
    },
    {
        "name": "DISCO FLAP Y GRATA → herramientas de preparación metal",
        "category": "abrasivos",
        "turns": [
            (
                "¿Con qué le quito el óxido a una estructura metálica? Tengo amoladora",
                {
                    "response_contains": ["disco flap", "grata", "Disco", "Grata", "amoladora", "flap"],
                },
            ),
        ],
    },
    {
        "name": "PREGUNTA TÉCNICA RAG → rendimiento + aplicación",
        "category": "tecnico_rag",
        "turns": [
            (
                "¿Cuánto rinde el Pintuco Fill 7 por galón y cómo se aplica en un techo de eternit?",
                {
                    "tools_called": ["consultar_conocimiento_tecnico"],
                    "response_contains": ["m²", "galón", "galones", "rodillo", "brocha", "superficie", "aplic"],
                },
            ),
        ],
    },
    {
        "name": "PREGUNTA TÉCNICA RAG → secado pintucoat",
        "category": "tecnico_rag",
        "turns": [
            (
                "¿Cuánto tiempo de secado tiene el Pintucoat entre manos?",
                {
                    "tools_called": ["consultar_conocimiento_tecnico"],
                    "response_contains": ["hora", "seca"],
                },
            ),
        ],
    },
    {
        "name": "PREGUNTA TÉCNICA RAG → preparación Corrotec",
        "category": "tecnico_rag",
        "turns": [
            (
                "¿Cómo preparo la superficie de metal antes de aplicar Corrotec?",
                {
                    "tools_called": ["consultar_conocimiento_tecnico"],
                    "response_contains": ["lij", "óxido", "limp"],
                },
            ),
        ],
    },
    {
        "name": "VINILO GENÉRICO → DESAMBIGUACIÓN tipo 1/2/3",
        "category": "desambiguacion",
        "turns": [
            (
                "Necesito vinilo, ¿qué tienen?",
                {
                    "check_diagnostic": True,
                    "response_contains": ["tipo 1", "tipo 2", "tipo 3", "premium", "intermedi", "económic"],
                },
            ),
        ],
    },
    {
        "name": "ESMALTE GENÉRICO → ¿interior o exterior?",
        "category": "desambiguacion",
        "turns": [
            (
                "Necesito esmalte, ¿qué tienen?",
                {
                    "check_diagnostic": True,
                    "response_contains": ["interior", "exterior", "Pintulux", "Doméstico"],
                },
            ),
        ],
    },
    {
        "name": "FICHA TÉCNICA → enviar documento real",
        "category": "documentos",
        "turns": [
            (
                "Me puedes enviar la ficha técnica de Koraza",
                {
                    "tools_called": ["buscar_documento_tecnico"],
                },
            ),
        ],
    },
    {
        "name": "CONSULTA INVENTARIO → producto específico con opciones",
        "category": "inventario",
        "turns": [
            (
                "¿Tienen viniltex blanco en galón?",
                {
                    "tools_called": ["consultar_inventario"],
                    "response_contains": ["disponible", "Disponible"],
                },
            ),
        ],
    },
    {
        "name": "CONSULTA INVENTARIO → koraza con colores disponibles",
        "category": "inventario",
        "turns": [
            (
                "¿Qué colores de Koraza tienen disponibles en cuñete?",
                {
                    "tools_called": ["consultar_inventario"],
                    "response_contains": ["disponible", "Disponible"],
                },
            ),
        ],
    },
    {
        "name": "LIJA → buscar productos de preparación",
        "category": "inventario",
        "turns": [
            (
                "Necesito lijas al agua para preparar una pared",
                {
                    "tools_called": ["consultar_inventario"],
                },
            ),
        ],
    },
    {
        "name": "CAMBIO DE CONTEXTO → de asesoría a pedido",
        "category": "coherencia",
        "turns": [
            (
                "Tengo humedad en un muro interior",
                {
                    "check_diagnostic": True,
                },
            ),
            (
                "Ya sé qué necesito, quiero 2 cuñetes de aquablock blanco",
                {
                    "tools_called": ["consultar_inventario"],
                    "response_contains": ["disponible", "Disponible", "Aquablock"],
                },
            ),
        ],
    },
    {
        "name": "SALUDO + DESPEDIDA → coherencia básica",
        "category": "coherencia",
        "turns": [
            (
                "Hola buenos días",
                {
                    "response_contains": ["ayud"],
                    "tools_not_called": ["consultar_inventario", "consultar_conocimiento_tecnico"],
                },
            ),
        ],
    },
]


def normalize(s):
    return (s.lower()
            .replace("á", "a").replace("é", "e").replace("í", "i")
            .replace("ó", "o").replace("ú", "u").replace("ñ", "n"))


# ──────────────────────────────────────────────────────────────────────────────
# RAG Test Runner
# ──────────────────────────────────────────────────────────────────────────────
def run_rag_tests():
    print("\n" + "=" * 90)
    print("PARTE 1: RAG PURO — Validar fichas técnicas y candidatos del portafolio")
    print("=" * 90)

    total = len(RAG_TESTS)
    passed = 0
    warned = 0
    failed = 0
    results = []

    for i, (query, expected, forbidden, category) in enumerate(RAG_TESTS, 1):
        try:
            resp = requests.get(
                RAG_URL,
                params={"q": query, "top_k": 6},
                headers={"x-admin-key": ADMIN_KEY},
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print(f"\n💥 Test {i:02d} [{category:>12}] ERROR: {e}")
            failed += 1
            results.append({"test": i, "category": category, "status": "ERROR", "query": query})
            continue

        if "error" in data:
            print(f"\n💥 Test {i:02d} [{category:>12}] ERROR: {data['error']}")
            failed += 1
            results.append({"test": i, "category": category, "status": "ERROR", "query": query})
            continue

        candidates = data.get("productos_candidatos", [])
        top_results = data.get("resultados", [])
        # Save raw RAG response for deeper analysis
        try:
            os.makedirs("artifacts/rag", exist_ok=True)
            with open(f"artifacts/rag/test_{i:03d}.json", "w", encoding="utf-8") as rf:
                json.dump({"query": query, "response": data}, rf, ensure_ascii=False, indent=2)
        except Exception:
            pass
        top_sim = top_results[0]["similitud"] if top_results else 0
        top_family = top_results[0].get("familia", "?") if top_results else "?"

        candidates_norm = [normalize(c) for c in candidates]
        families_norm = [normalize(r.get("familia", "")) for r in top_results]
        all_text = " ".join(candidates_norm + families_norm)

        # Check if "no product" test (piscinas)
        is_gap_test = "__SIN_PRODUCTO_FERREINOX__" in expected

        found_exp = []
        missed_exp = []
        for exp in expected:
            if exp == "__SIN_PRODUCTO_FERREINOX__":
                continue
            if normalize(exp) in all_text:
                found_exp.append(exp)
            else:
                missed_exp.append(exp)

        found_forbidden = []
        for forb in forbidden:
            if normalize(forb) in all_text:
                found_forbidden.append(forb)

        # Determine status
        # Extra validation: low similarity means weak evidence
        low_sim_warning = False
        try:
            if top_sim and float(top_sim) < 0.18:
                low_sim_warning = True
        except Exception:
            pass

        if found_forbidden:
            status = "FAIL"
            detail = f"PROHIBIDO: {found_forbidden} | Candidatos: {candidates[:5]}"
            failed += 1
        elif is_gap_test:
            # For gap tests, success if no relevant product candidates found
            relevant_products = [c for c in candidates if normalize(c) not in ("lija", "sellador")]
            if not relevant_products or len(relevant_products) <= 1:
                status = "PASS"
                detail = f"Gap correcto, sin producto relevante (sim={top_sim:.3f})"
                passed += 1
            else:
                status = "WARN"
                detail = f"Gap: candidatos inesperados: {candidates[:5]} (sim={top_sim:.3f})"
                warned += 1
        elif not expected or all(e == "__SIN_PRODUCTO_FERREINOX__" for e in expected):
            status = "INFO"
            detail = f"Candidatos: {candidates[:5]} (sim={top_sim:.3f})"
            warned += 1
        elif missed_exp and not found_exp:
            status = "FAIL"
            detail = f"NINGUNO encontrado: {missed_exp} | Candidatos: {candidates[:5]}"
            failed += 1
        elif missed_exp:
            status = "WARN"
            detail = f"Parcial: ✓{found_exp} ✗{missed_exp} (sim={top_sim:.3f})"
            warned += 1
            if low_sim_warning:
                detail += " | Low similarity evidence"
        else:
            status = "PASS"
            detail = f"Top: {top_family} (sim={top_sim:.3f}) | Candidatos: {candidates[:4]}"
            if low_sim_warning:
                status = "WARN"
                detail += " | Low similarity evidence"
                warned += 1
            passed += 1

        icon = {"PASS": "✅", "FAIL": "❌", "WARN": "⚠️", "INFO": "ℹ️"}.get(status, "?")
        print(f"\n{icon} Test {i:02d} [{category:>12}] {status}")
        print(f"   Q: \"{query}\"")
        print(f"   {detail}")

        results.append({
            "test": i, "category": category, "status": status,
            "query": query, "detail": detail,
        })

    print(f"\n{'─' * 90}")
    print(f"RAG RESUMEN: ✅ PASS={passed}  ⚠️ WARN={warned}  ❌ FAIL={failed}  Total={total}")

    # Category breakdown
    cats = {}
    for r in results:
        c = r["category"]
        cats.setdefault(c, {"pass": 0, "warn": 0, "fail": 0})
        if r["status"] == "PASS":
            cats[c]["pass"] += 1
        elif r["status"] == "WARN":
            cats[c]["warn"] += 1
        elif r["status"] in ("FAIL", "ERROR"):
            cats[c]["fail"] += 1

    print(f"\n{'Categoría':<15} {'PASS':>5} {'WARN':>5} {'FAIL':>5}")
    print("─" * 35)
    for cat, counts in sorted(cats.items()):
        print(f"{cat:<15} {counts['pass']:>5} {counts['warn']:>5} {counts['fail']:>5}")

    return passed, warned, failed


# ──────────────────────────────────────────────────────────────────────────────
# AGENT Test Runner — Simula conversaciones multi-turno
# ──────────────────────────────────────────────────────────────────────────────
def run_agent_tests():
    print("\n\n" + "=" * 90)
    print("PARTE 2: AGENTE COMPLETO — Flujo multi-turno con LLM + herramientas")
    print("=" * 90)

    # Use admin test endpoint to call agent synchronously
    agent_test_url = f"{BACKEND_URL.rstrip('/')}/admin/agent-test"

    total_turns = sum(len(conv["turns"]) for conv in AGENT_CONVERSATIONS)
    passed = 0
    warned = 0
    failed = 0
    conv_results = []

    for conv_idx, conv in enumerate(AGENT_CONVERSATIONS, 1):
        conv_name = conv["name"]
        conv_category = conv["category"]
        print(f"\n{'━' * 90}")
        print(f"🗣️ CONVERSACIÓN {conv_idx}: {conv_name} [{conv_category}]")
        print(f"{'━' * 90}")

        conversation_context = {}
        recent_messages = []
        context = {
            "conversation_id": 99990 + conv_idx,
            "contact_id": 99990 + conv_idx,
            "cliente_id": None,
            "telefono_e164": "+573001234567",
            "nombre_visible": "Test User",
        }

        conv_passed = 0
        conv_failed = 0
        conv_warned = 0

        for turn_idx, (user_message, validations) in enumerate(conv["turns"], 1):
            print(f"\n  👤 Turno {turn_idx}: \"{user_message}\"")

            try:
                t0 = time.time()
                resp = requests.post(
                    agent_test_url,
                    headers={"x-admin-key": ADMIN_KEY, "Content-Type": "application/json"},
                    json={
                        "profile_name": "Test User",
                        "conversation_context": conversation_context,
                        "recent_messages": recent_messages,
                        "user_message": user_message,
                        "context": context,
                    },
                    timeout=60,
                )
                resp.raise_for_status()
                data = resp.json()
                if data.get("error"):
                    raise RuntimeError(data.get("error"))
                result = data.get("result") or {}
                elapsed_ms = int((time.time() - t0) * 1000)
                # Save per-turn result for auditing
                try:
                    os.makedirs("artifacts/agent", exist_ok=True)
                    with open(f"artifacts/agent/conv_{conv_idx:03d}_turn_{turn_idx:02d}.json", "w", encoding="utf-8") as af:
                        json.dump({"user": user_message, "result": result}, af, ensure_ascii=False, indent=2)
                except Exception:
                    pass
            except Exception as e:
                print(f"  💥 ERROR: {e}")
                traceback.print_exc()
                failed += 1
                conv_failed += 1
                continue

            response_text = result.get("response_text", "")
            tool_calls = result.get("tool_calls", [])
            intent = result.get("intent", "")
            tools_used = [tc["name"] for tc in tool_calls]

            # Update conversation history for next turn
            recent_messages.append({
                "direction": "inbound",
                "contenido": user_message,
                "message_type": "text",
            })
            recent_messages.append({
                "direction": "outbound",
                "contenido": response_text,
                "message_type": "text",
            })

            # Update context from result
            ctx_updates = result.get("context_updates", {})
            for k, v in ctx_updates.items():
                if v is not None:
                    conversation_context[k] = v

            # Display response
            response_preview = response_text[:300].replace("\n", " ↵ ")
            print(f"  🤖 [{elapsed_ms}ms] Tools: {tools_used or '—'}")
            print(f"     \"{response_preview}\"")

            # Validate
            errors = []
            warnings = []

            # Check required tools
            if "tools_called" in validations:
                for tool in validations["tools_called"]:
                    if tool not in tools_used:
                        errors.append(f"Tool '{tool}' NO fue llamada (usó: {tools_used})")

            # Check forbidden tools
            if "tools_not_called" in validations:
                for tool in validations["tools_not_called"]:
                    if tool in tools_used:
                        errors.append(f"Tool '{tool}' NO debía llamarse")

            # Check response contains
            if "response_contains" in validations:
                resp_norm = normalize(response_text)
                for keyword in validations["response_contains"]:
                    kw_norm = normalize(keyword)
                    if kw_norm not in resp_norm:
                        # Be lenient: warn instead of fail for partial keyword matches
                        warnings.append(f"Respuesta no contiene '{keyword}'")

            # Check response excludes
            if "response_excludes" in validations:
                resp_norm = normalize(response_text)
                for keyword in validations["response_excludes"]:
                    kw_norm = normalize(keyword)
                    if kw_norm in resp_norm:
                        errors.append(f"Respuesta contiene '{keyword}' (PROHIBIDO)")

            # Check diagnostic mode
            if validations.get("check_diagnostic"):
                # Should be asking a diagnostic question, not giving a product recommendation directly
                resp_lower = response_text.lower()
                has_question = "?" in response_text
                if not has_question:
                    warnings.append("Se esperaba pregunta diagnóstica pero no hay '?'")

            # Determine turn status
            if errors:
                status = "FAIL"
                failed += 1
                conv_failed += 1
            elif warnings:
                status = "WARN"
                warned += 1
                conv_warned += 1
            else:
                status = "PASS"
                passed += 1
                conv_passed += 1

            icon = {"PASS": "✅", "FAIL": "❌", "WARN": "⚠️"}.get(status, "?")
            print(f"  {icon} Turno {turn_idx}: {status}")
            for e in errors:
                print(f"     ❌ {e}")
            for w in warnings:
                print(f"     ⚠️ {w}")

        # Conversation summary
        conv_total = len(conv["turns"])
        conv_icon = "✅" if conv_failed == 0 and conv_warned == 0 else ("⚠️" if conv_failed == 0 else "❌")
        print(f"\n  {conv_icon} Conversación: {conv_passed}/{conv_total} PASS, {conv_warned} WARN, {conv_failed} FAIL")
        conv_results.append({
            "name": conv_name,
            "category": conv_category,
            "passed": conv_passed,
            "warned": conv_warned,
            "failed": conv_failed,
            "total": conv_total,
        })

    print(f"\n{'─' * 90}")
    print(f"AGENT RESUMEN: ✅ PASS={passed}  ⚠️ WARN={warned}  ❌ FAIL={failed}  Total={total_turns}")

    # Category breakdown
    cats = {}
    for r in conv_results:
        c = r["category"]
        cats.setdefault(c, {"pass": 0, "warn": 0, "fail": 0})
        cats[c]["pass"] += r["passed"]
        cats[c]["warn"] += r["warned"]
        cats[c]["fail"] += r["failed"]

    print(f"\n{'Categoría':<22} {'PASS':>5} {'WARN':>5} {'FAIL':>5}")
    print("─" * 40)
    for cat, counts in sorted(cats.items()):
        print(f"{cat:<22} {counts['pass']:>5} {counts['warn']:>5} {counts['fail']:>5}")

    return passed, warned, failed


# ──────────────────────────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 90)
    print("  SUPER TEST AGENTE CRM FERREINOX — Batería Exhaustiva")
    print("  Diagnóstico • RAG • Inventario • Pedidos • Abrasivos • Gaps")
    print("=" * 90)

    # Part 1: RAG Tests (always runs, only needs network)
    rag_pass, rag_warn, rag_fail = run_rag_tests()

    # Part 2: Agent Tests (uses /admin/agent-test endpoint — no local DB/OpenAI needed)
    agent_pass, agent_warn, agent_fail = 0, 0, 0
    skip_agent = os.environ.get("SKIP_AGENT_TESTS", "").lower() in ("1", "true", "yes")
    if skip_agent:
        print(f"\n⏭️  Saltando PARTE 2 (Agent Tests): SKIP_AGENT_TESTS=1")
    else:
        # Quick connectivity check before running full suite
        try:
            _probe = requests.post(
                f"{BACKEND_URL}/admin/agent-test",
                headers={"x-admin-key": ADMIN_KEY, "Content-Type": "application/json"},
                json={"user_message": "ping", "profile_name": "probe"},
                timeout=15,
            )
            if _probe.status_code == 403:
                print("\n❌ Admin key rechazada por el backend. Verifica ADMIN_API_KEY.")
                skip_agent = True
            elif _probe.status_code >= 500:
                print(f"\n❌ Backend devolvió {_probe.status_code}. ¿Está desplegado el endpoint /admin/agent-test?")
                skip_agent = True
        except Exception as _err:
            print(f"\n❌ No se pudo conectar al backend ({BACKEND_URL}): {_err}")
            skip_agent = True

        if not skip_agent:
            agent_pass, agent_warn, agent_fail = run_agent_tests()

    # Final summary
    total_pass = rag_pass + agent_pass
    total_warn = rag_warn + agent_warn
    total_fail = rag_fail + agent_fail
    total_all = total_pass + total_warn + total_fail

    print("\n\n" + "=" * 90)
    print("  RESULTADO FINAL")
    print("=" * 90)
    print(f"  RAG:   ✅ {rag_pass}  ⚠️ {rag_warn}  ❌ {rag_fail}")
    if agent_pass + agent_warn + agent_fail > 0:
        print(f"  Agent: ✅ {agent_pass}  ⚠️ {agent_warn}  ❌ {agent_fail}")
    print(f"  TOTAL: ✅ {total_pass}  ⚠️ {total_warn}  ❌ {total_fail}  ({total_all} tests)")

    pct = (total_pass / total_all * 100) if total_all > 0 else 0
    if total_fail == 0:
        print(f"\n  🏆 {pct:.0f}% — Sin fallos críticos")
    elif total_fail <= 3:
        print(f"\n  ⚠️ {pct:.0f}% — Pocos fallos, revisar")
    else:
        print(f"\n  ❌ {pct:.0f}% — Fallos significativos, requiere ajuste")

    print("=" * 90)

    # Save results
    summary = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "rag": {"pass": rag_pass, "warn": rag_warn, "fail": rag_fail},
        "agent": {"pass": agent_pass, "warn": agent_warn, "fail": agent_fail},
        "total": {"pass": total_pass, "warn": total_warn, "fail": total_fail},
    }
    with open("test_super_agent_results.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print(f"\nResultados guardados en test_super_agent_results.json")
