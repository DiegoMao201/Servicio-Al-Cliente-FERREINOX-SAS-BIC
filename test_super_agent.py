"""
Super Test Agente CRM Ferreinox - Batería Exhaustiva V2
========================================================
Prueba el flujo completo del agente: diagnóstico → RAG → inventario → pedido.
Simula conversaciones reales multi-turno y valida:
  1. Diagnóstico inteligente (sospecha correcta)
  2. RAG devuelve fichas técnicas relevantes
  3. Productos del inventario real (nunca inventados)
  4. Coherencia conversacional (no repite preguntas, sigue hilo)
  5. Corrección de pedido (color/tamaño genera nueva referencia)
  6. Abrasivos, removedores, superficies especiales
  7. Gaps del portafolio (piscinas)
  8. Query Expansion (jerga → RAG técnico)
  9. Bicomponentes con catalizador obligatorio
 10. Anti-rendición comercial (cotizar en vez de derivar)
 11. Pedido directo sin diagnóstico
 12. Multi-producto en un solo pedido
 13. Validación de precios (sin IVA doble)

Usa el endpoint /admin/rag-buscar para RAG puro
y /admin/agent-test para flujo completo del agente.
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
AGENT_TIMEOUT = 120  # seconds per agent turn (increased from 60)
MAX_RETRIES = 2      # retry on timeout

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
    ("muro de contención enterrado filtra agua", ["aquablock"], ["koraza"], "humedad"),
    ("la pintura se sopla y sale agua detrás", ["aquablock"], ["koraza"], "humedad"),

    # ═══ FACHADAS / EXTERIORES ═══
    ("fachada deteriorada por lluvia y sol, se pela", ["koraza"], ["aquablock"], "fachada"),
    ("pintar frente de la casa que aguante intemperie", ["koraza"], ["aquablock"], "fachada"),
    ("muro exterior que le da el sol todo el día", ["koraza"], ["aquablock"], "fachada"),
    ("se descascara la pintura de la fachada exterior", ["koraza"], ["aquablock"], "fachada"),
    ("edificio de 5 pisos fachada con chalk y decoloración", ["koraza"], [], "fachada"),
    ("muro medianero exterior que comparto con el vecino", ["koraza"], [], "fachada"),

    # ═══ TECHOS / GOTERAS ═══
    ("techo de concreto goteando, tiene grietas", ["pintuco fill"], [], "techo"),
    ("impermeabilizar terraza de plancha", ["pintuco fill", "impercoat"], [], "techo"),
    ("cubierta de fibrocemento eternit que se llueve", ["pintuco fill", "koraza"], [], "techo"),
    ("manto impermeabilizante para terraza con grietas profundas", ["pintuco fill"], [], "techo"),
    ("terraza transitable con fisuras que se llueve abajo", ["pintuco fill", "impercoat"], [], "techo"),

    # ═══ METAL / ANTICORROSIVO ═══
    ("reja de hierro toda oxidada, se está comiendo", ["corrotec", "pintoxido"], ["koraza"], "metal"),
    ("portón metálico con óxido profundo y corrosión", ["corrotec", "pintoxido"], [], "metal"),
    ("estructura de acero nueva sin pintar a la intemperie", ["corrotec", "wash primer"], [], "metal"),
    ("tubo galvanizado nuevo cómo pintarlo", ["wash primer", "corrotec"], [], "metal"),
    ("tanque metálico industrial expuesto a químicos", ["interseal", "interthane"], [], "metal"),
    ("estructura metálica de nave industrial nueva", ["corrotec", "interseal"], [], "metal"),

    # ═══ PISOS ═══
    ("piso de bodega industrial con tráfico de montacargas", ["pintucoat"], ["koraza"], "piso"),
    ("garaje residencial piso de concreto", ["pintura canchas", "pintucoat"], ["koraza"], "piso"),
    ("cancha de microfútbol hay que pintarla", ["pintura canchas"], ["koraza"], "piso"),
    ("andén de concreto exterior", ["pintura canchas"], [], "piso"),
    ("piso de planta de producción con estibadoras pesadas", ["pintucoat"], ["koraza"], "piso"),
    ("rampa de parqueadero con tráfico vehicular", ["pintura canchas", "pintucoat"], [], "piso"),

    # ═══ INTERIORES ═══
    ("pintar sala de la casa, calidad premium lavable", ["viniltex"], ["koraza"], "interior"),
    ("pintura económica para cielo raso bodega", ["pinturama", "vinil"], [], "interior"),
    ("cuarto del bebé pintura lavable", ["viniltex"], ["koraza"], "interior"),
    ("oficina corporativa paredes interiores acabado mate", ["viniltex"], [], "interior"),
    ("cocina y baño con mucha humedad y grasa", ["viniltex"], [], "interior"),

    # ═══ MADERA ═══
    ("pergola de madera al aire libre se deteriora", ["barnex", "wood stain"], ["koraza"], "madera"),
    ("barniz para mueble interior que se vea la veta", ["pintulac", "barniz"], [], "madera"),
    ("puerta de madera la quiero pintar de color", ["pintulux", "pintulac"], [], "madera"),
    ("deck de madera exterior expuesto a lluvia", ["barnex", "wood stain"], [], "madera"),

    # ═══ ABRASIVOS / PREPARACIÓN ═══
    ("con qué lijo una pared pintada antes de repintar", ["viniltex", "imprimante", "estuco"], [], "abrasivo"),
    ("cómo remuevo la pintura vieja de una reja de hierro", ["corrotec", "pintoxido"], [], "abrasivo"),
    ("necesito quitar barniz viejo de una puerta de madera", ["barnex", "barniz", "imprimante"], [], "abrasivo"),
    ("disco para pulir y quitar óxido en amoladora", ["corrotec", "pintoxido"], [], "abrasivo"),
    ("cepillo metálico para limpiar estructura oxidada", ["corrotec"], [], "abrasivo"),

    # ═══ SUPERFICIES ESPECIALES ═══
    ("necesito pintar un tobogán metálico de un parque", ["corrotec", "pintulux"], [], "especial"),
    ("baranda de hierro que está oxidada a la intemperie", ["corrotec", "pintoxido"], [], "especial"),
    ("juego infantil de metal al aire libre", ["corrotec", "pintulux"], [], "especial"),
    ("señalización vial en pavimento de parqueadero", ["pintura canchas", "pintura trafico"], [], "especial"),

    # ═══ PISCINAS (GAP - NO VENDEN) ═══
    ("pintura especial para piscina de concreto", [], [], "gap_piscina"),
    ("pintar un tanque de agua potable por dentro", [], [], "gap_piscina"),

    # ═══ BICOMPONENTES / INDUSTRIALES ═══
    ("recubrimiento epóxico para piso de planta química", ["pintucoat", "interseal"], [], "bicomponente"),
    ("pintura de poliuretano para estructura metálica exterior", ["interthane"], [], "bicomponente"),
    ("imprimante epóxico para metal industrial", ["interseal", "intergard"], [], "bicomponente"),
    ("acabado poliuretano alto brillo para tanque", ["interthane", "interfine"], [], "bicomponente"),

    # ═══ PREGUNTAS TÉCNICAS ESPECÍFICAS ═══
    ("cuántas manos de koraza debo aplicar en fachada", ["koraza"], [], "tecnico"),
    ("rendimiento por galón de pintuco fill 7", ["pintuco fill"], [], "tecnico"),
    ("tiempo de secado entre manos de pintucoat epóxico", ["pintucoat"], [], "tecnico"),
    ("se puede diluir el viniltex con agua y cuánto", ["viniltex"], [], "tecnico"),
    ("cómo se aplica el pintuco fill en techo de eternit", ["pintuco fill"], [], "tecnico"),
    ("qué rodillo usar para koraza en fachada", ["koraza"], [], "tecnico"),
    ("preparación de superficie para corrotec", ["corrotec"], [], "tecnico"),
    ("proporción de mezcla del pintucoat con catalizador", ["pintucoat"], [], "tecnico"),
    ("cuánto dura la vida útil de koraza en fachada", ["koraza"], [], "tecnico"),
    ("temperatura mínima de aplicación para epóxicos", ["pintucoat", "interseal"], [], "tecnico"),

    # ═══ JERGA COLOMBIANA / QUERY EXPANSION ═══
    ("la casa se está cayendo a pedazos por el aguacero", ["koraza"], [], "jerga"),
    ("le está saliendo como un polvo blanco a la pared", ["aquablock", "estuco anti humedad"], [], "jerga"),
    ("el hierro se lo está comiendo el óxido", ["corrotec", "pintoxido"], [], "jerga"),
    ("qué le echo al piso del parqueadero para que quede bonito", ["pintucoat", "pintura canchas"], [], "jerga"),
    ("la terraza se me llueve toda y se moja abajo", ["pintuco fill", "impercoat"], [], "jerga"),
    ("esa reja ya está muy fea, cómo la recupero", ["corrotec", "pintoxido"], [], "jerga"),
    ("las carretas pesadas me están dañando el piso", ["pintucoat"], [], "jerga"),
    ("la bodega huele a guardado y las paredes tienen manchas negras", ["aquablock", "viniltex"], [], "jerga"),
    ("la pintura se puso como amarillenta y polvosa", ["koraza"], [], "jerga"),
    ("necesito algo pa que no se oxide más el portón", ["corrotec", "pintoxido"], [], "jerga"),
    ("el techo de eternit se me está pelando todo", ["pintuco fill", "koraza"], [], "jerga"),
    ("zorras del almacén me rayaron todo el piso", ["pintucoat"], [], "jerga"),
]


# ──────────────────────────────────────────────────────────────────────────────
# PARTE 2: AGENT FLOW — Simula conversaciones multi-turno
# ──────────────────────────────────────────────────────────────────────────────
# validations_dict keys:
#   "tools_called"        : list of tool names that MUST have been called
#   "tools_not_called"    : list of tool names that MUST NOT have been called
#   "response_contains"   : list of strings — ANY match = pass for this check
#   "response_excludes"   : list of strings — ANY match = FAIL
#   "check_diagnostic"    : True = must have '?' in response
#   "check_has_price"     : True = must have '$' or 'precio' in response
#   "check_no_iva_double" : True = must NOT show subtotal + IVA separately

AGENT_CONVERSATIONS = [
    # ══════════════════════════════════════════════════════════════════════
    # FLUJOS COMPLETOS (diagnóstico → RAG → inventario → cotización)
    # ══════════════════════════════════════════════════════════════════════
    {
        "name": "TECHO ETERNIT → DIAGNÓSTICO → PINTUCO FILL → PEDIDO",
        "category": "flujo_completo",
        "turns": [
            (
                "Hola buenas tardes",
                {
                    "tools_not_called": ["consultar_inventario", "consultar_conocimiento_tecnico"],
                },
            ),
            (
                "Necesito pintar un techo por fuera",
                {
                    "check_diagnostic": True,
                    "tools_not_called": ["consultar_inventario"],
                },
            ),
            (
                "Es de eternit, techo exterior",
                {
                    "tools_called": ["consultar_conocimiento_tecnico"],
                    "response_contains": ["fill", "koraza", "Fill", "Koraza"],
                },
            ),
            (
                "Quiero pintuco fill, qué opciones hay",
                {
                    "tools_called": ["consultar_inventario"],
                },
            ),
        ],
    },
    {
        "name": "FACHADA COMPLETO → KORAZA → m² → COTIZACIÓN CON PRECIO",
        "category": "flujo_completo",
        "turns": [
            (
                "Necesito pintar la fachada de mi casa, se está pelando toda",
                {
                    "check_diagnostic": True,
                },
            ),
            (
                "Es un muro exterior de concreto, le da sol y lluvia todo el día, unos 80 metros cuadrados",
                {
                    "tools_called": ["consultar_conocimiento_tecnico"],
                    "response_contains": ["Koraza", "koraza"],
                },
            ),
            (
                "Quiero Koraza blanco, me das la cotización",
                {
                    "tools_called": ["consultar_inventario"],
                    "check_has_price": True,
                    "check_no_iva_double": True,
                },
            ),
        ],
    },
    {
        "name": "PISO INDUSTRIAL → PINTUCOAT → CATALIZADOR OBLIGATORIO",
        "category": "flujo_completo",
        "turns": [
            (
                "Necesito pintar el piso de una bodega, pasan montacargas todo el día",
                {
                    "tools_called": ["consultar_conocimiento_tecnico"],
                    "response_contains": ["Pintucoat", "pintucoat", "epóx", "epox"],
                },
            ),
            (
                "Quiero el Pintucoat, necesito para unos 200 m²",
                {
                    "tools_called": ["consultar_inventario"],
                    "response_contains": ["catalizador", "Catalizador", "kit", "Kit", "comp", "Comp"],
                    "check_has_price": True,
                },
            ),
        ],
    },
    {
        "name": "METAL INDUSTRIAL → INTERSEAL + INTERTHANE (sistema International)",
        "category": "flujo_completo",
        "turns": [
            (
                "Tengo una estructura metálica de una nave industrial, necesito un sistema de protección de alto desempeño",
                {
                    "tools_called": ["consultar_conocimiento_tecnico"],
                    "response_contains": ["Interseal", "interseal", "Interthane", "interthane", "epóx", "epox", "poliuretano"],
                },
            ),
        ],
    },

    # ══════════════════════════════════════════════════════════════════════
    # DIAGNÓSTICO TÉCNICO (el agente debe preguntar antes de recomendar)
    # ══════════════════════════════════════════════════════════════════════
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
                    "response_contains": ["Aquablock", "aquablock"],
                    "response_excludes": ["Koraza"],
                },
            ),
        ],
    },
    {
        "name": "PISO GARAJE → DIAGNÓSTICO TRÁFICO → CANCHAS o PINTUCOAT",
        "category": "diagnostico_tecnico",
        "turns": [
            (
                "Necesito pintar el piso de un garaje de la casa",
                {
                    "check_diagnostic": True,
                },
            ),
            (
                "Es tráfico liviano, solo carros livianos de la casa",
                {
                    "tools_called": ["consultar_conocimiento_tecnico"],
                    "response_contains": ["Canchas", "canchas", "Pintucoat", "pintucoat"],
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
                },
            ),
            (
                "El óxido está bastante profundo, las rejas están a la intemperie",
                {
                    "tools_called": ["consultar_conocimiento_tecnico"],
                    "response_contains": ["Corrotec", "corrotec"],
                },
            ),
        ],
    },
    {
        "name": "MADERA EXTERIOR → diagnóstico veta/color → BARNEX/WOOD STAIN",
        "category": "diagnostico_tecnico",
        "turns": [
            (
                "Tengo una pérgola de madera que está a la intemperie y quiero protegerla",
                {
                    "check_diagnostic": True,
                },
            ),
            (
                "Quiero que se vea la veta de la madera, acabado transparente",
                {
                    "tools_called": ["consultar_conocimiento_tecnico"],
                    "response_contains": ["Barnex", "barnex", "Wood Stain", "wood stain"],
                },
            ),
        ],
    },
    {
        "name": "METAL NUEVO GALVANIZADO → WASH PRIMER obligatorio",
        "category": "diagnostico_tecnico",
        "turns": [
            (
                "Tengo una estructura de acero galvanizado nueva, quiero pintarla",
                {
                    "tools_called": ["consultar_conocimiento_tecnico"],
                    "response_contains": ["Wash Primer", "wash primer", "galvanizado"],
                },
            ),
        ],
    },
    {
        "name": "BAÑO CON HONGOS → VINILTEX BAÑOS Y COCINAS",
        "category": "diagnostico_tecnico",
        "turns": [
            (
                "El baño de mi casa tiene hongos negros en las paredes y mucha humedad",
                {
                    "tools_called": ["consultar_conocimiento_tecnico"],
                    "response_contains": ["Viniltex", "viniltex", "baño", "Baño", "antibacterial"],
                },
            ),
        ],
    },
    {
        "name": "CIELO RASO ECONÓMICO → PINTURAMA / PINTURA CIELOS",
        "category": "diagnostico_tecnico",
        "turns": [
            (
                "Necesito pintar el cielo raso de una bodega grande, lo más económico que tengan",
                {
                    "tools_called": ["consultar_conocimiento_tecnico"],
                    "response_contains": ["Pinturama", "pinturama", "cielos", "Cielos", "económic"],
                },
            ),
        ],
    },

    # ══════════════════════════════════════════════════════════════════════
    # GAP DEL PORTAFOLIO (debe rechazar honestamente)
    # ══════════════════════════════════════════════════════════════════════
    {
        "name": "PISCINA → GAP DEL PORTAFOLIO (debe rechazar)",
        "category": "gap_portfolio",
        "turns": [
            (
                "Necesito pintar una piscina, ¿qué producto me sirve?",
                {
                    "response_excludes": ["Pintucoat", "Koraza", "Viniltex"],
                    "tools_not_called": ["consultar_inventario"],
                },
            ),
        ],
    },
    {
        "name": "PINTURA EPÓXICA ALIMENTARIA → GAP",
        "category": "gap_portfolio",
        "turns": [
            (
                "Necesito pintura epóxica grado alimentario para un tanque de leche",
                {
                    "response_excludes": ["Pintucoat"],
                },
            ),
        ],
    },

    # ══════════════════════════════════════════════════════════════════════
    # SUPERFICIES ESPECIALES
    # ══════════════════════════════════════════════════════════════════════
    {
        "name": "TOBOGÁN METÁLICO → SISTEMA anticorrosivo",
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
                    "response_contains": ["Corrotec", "corrotec", "Pintulux", "pintulux"],
                },
            ),
        ],
    },
    {
        "name": "SEÑALIZACIÓN PARQUEADERO → PINTURA TRÁFICO",
        "category": "superficie_especial",
        "turns": [
            (
                "Necesito pintar la señalización de un parqueadero, líneas amarillas y blancas en el piso",
                {
                    "tools_called": ["consultar_conocimiento_tecnico"],
                    "response_contains": ["tráfico", "trafico", "canchas", "Canchas", "señalización", "demarcación"],
                },
            ),
        ],
    },

    # ══════════════════════════════════════════════════════════════════════
    # ABRASIVOS Y HERRAMIENTAS DE PREPARACIÓN
    # ══════════════════════════════════════════════════════════════════════
    {
        "name": "REMOVEDOR pintura madera → asesoría preparación",
        "category": "abrasivos",
        "turns": [
            (
                "Necesito quitar la pintura vieja de unas puertas de madera, ¿cómo le hago?",
                {
                    "response_contains": ["removedor", "Removedor", "lija", "Lija", "lijar"],
                },
            ),
        ],
    },
    {
        "name": "DISCO FLAP → herramientas de preparación metal",
        "category": "abrasivos",
        "turns": [
            (
                "¿Con qué le quito el óxido a una estructura metálica? Tengo amoladora",
                {
                    "response_contains": ["disco", "Disco", "flap", "amoladora", "grata", "Grata", "cepillo"],
                },
            ),
        ],
    },

    # ══════════════════════════════════════════════════════════════════════
    # PREGUNTAS TÉCNICAS RAG (DEBE llamar consultar_conocimiento_tecnico)
    # ══════════════════════════════════════════════════════════════════════
    {
        "name": "TÉCNICA → rendimiento Pintuco Fill 7 + aplicación",
        "category": "tecnico_rag",
        "turns": [
            (
                "¿Cuánto rinde el Pintuco Fill 7 por galón y cómo se aplica en un techo de eternit?",
                {
                    "tools_called": ["consultar_conocimiento_tecnico"],
                    "response_contains": ["m²", "m2", "galón", "galon"],
                },
            ),
        ],
    },
    {
        "name": "TÉCNICA → secado Pintucoat entre manos",
        "category": "tecnico_rag",
        "turns": [
            (
                "¿Cuánto tiempo de secado tiene el Pintucoat entre manos?",
                {
                    "tools_called": ["consultar_conocimiento_tecnico"],
                    "response_contains": ["hora", "seca", "sec"],
                },
            ),
        ],
    },
    {
        "name": "TÉCNICA → preparación superficie Corrotec",
        "category": "tecnico_rag",
        "turns": [
            (
                "¿Cómo preparo la superficie de metal antes de aplicar Corrotec?",
                {
                    "tools_called": ["consultar_conocimiento_tecnico"],
                    "response_contains": ["lij", "óxido", "oxido", "limp", "prepar"],
                },
            ),
        ],
    },
    {
        "name": "TÉCNICA → dilución Viniltex con agua",
        "category": "tecnico_rag",
        "turns": [
            (
                "¿Se puede diluir el Viniltex con agua y en qué proporción?",
                {
                    "tools_called": ["consultar_conocimiento_tecnico"],
                    "response_contains": ["agua", "%", "proporci", "diluir", "diluc"],
                },
            ),
        ],
    },
    {
        "name": "TÉCNICA → mezcla Pintucoat con catalizador",
        "category": "tecnico_rag",
        "turns": [
            (
                "¿Cuál es la proporción de mezcla del Pintucoat con su catalizador?",
                {
                    "tools_called": ["consultar_conocimiento_tecnico"],
                    "response_contains": ["proporci", "mezcl", "catalizador", "parte"],
                },
            ),
        ],
    },
    {
        "name": "TÉCNICA → vida útil Koraza en fachada",
        "category": "tecnico_rag",
        "turns": [
            (
                "¿Cuánto dura la Koraza en una fachada? ¿Cuántos años de garantía?",
                {
                    "tools_called": ["consultar_conocimiento_tecnico"],
                    "response_contains": ["año", "garantí", "durabilidad", "vida"],
                },
            ),
        ],
    },

    # ══════════════════════════════════════════════════════════════════════
    # DESAMBIGUACIÓN (el agente debe aclarar antes de recomendar)
    # ══════════════════════════════════════════════════════════════════════
    {
        "name": "VINILO GENÉRICO → desambiguación tipo/calidad",
        "category": "desambiguacion",
        "turns": [
            (
                "Necesito vinilo, ¿qué tienen?",
                {
                    "check_diagnostic": True,
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
                },
            ),
        ],
    },
    {
        "name": "PINTURA GENÉRICA → qué superficie / uso",
        "category": "desambiguacion",
        "turns": [
            (
                "Necesito pintura, ¿qué me recomiendan?",
                {
                    "check_diagnostic": True,
                },
            ),
        ],
    },
    {
        "name": "ANTICORROSIVO GENÉRICO → qué tipo de metal/uso",
        "category": "desambiguacion",
        "turns": [
            (
                "Necesito anticorrosivo",
                {
                    "check_diagnostic": True,
                },
            ),
        ],
    },

    # ══════════════════════════════════════════════════════════════════════
    # DOCUMENTOS TÉCNICOS
    # ══════════════════════════════════════════════════════════════════════
    {
        "name": "FICHA TÉCNICA Koraza → enviar documento real",
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
        "name": "FICHA TÉCNICA Pintucoat → documento",
        "category": "documentos",
        "turns": [
            (
                "Necesito la ficha técnica del Pintucoat por favor",
                {
                    "tools_called": ["buscar_documento_tecnico"],
                },
            ),
        ],
    },

    # ══════════════════════════════════════════════════════════════════════
    # INVENTARIO DIRECTO (buscar inventario INMEDIATAMENTE)
    # ══════════════════════════════════════════════════════════════════════
    {
        "name": "VINILTEX BLANCO GALÓN → inventario directo",
        "category": "inventario",
        "turns": [
            (
                "¿Tienen viniltex blanco en galón?",
                {
                    "tools_called": ["consultar_inventario"],
                },
            ),
        ],
    },
    {
        "name": "KORAZA CUÑETE COLORES → inventario directo",
        "category": "inventario",
        "turns": [
            (
                "¿Qué colores de Koraza tienen disponibles en cuñete?",
                {
                    "tools_called": ["consultar_inventario"],
                },
            ),
        ],
    },
    {
        "name": "LIJA AL AGUA → inventario directo (accesorio)",
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
        "name": "THINNER → inventario directo (insumo)",
        "category": "inventario",
        "turns": [
            (
                "¿Tienen thinner en galón?",
                {
                    "tools_called": ["consultar_inventario"],
                },
            ),
        ],
    },
    {
        "name": "RODILLOS → inventario directo (herramienta)",
        "category": "inventario",
        "turns": [
            (
                "Necesito rodillos para pintar, ¿qué tienen?",
                {
                    "tools_called": ["consultar_inventario"],
                },
            ),
        ],
    },
    {
        "name": "CORROTEC GALÓN → inventario + precio",
        "category": "inventario",
        "turns": [
            (
                "Quiero 2 galones de Corrotec rojo",
                {
                    "tools_called": ["consultar_inventario"],
                    "check_has_price": True,
                },
            ),
        ],
    },
    {
        "name": "MASILLA → inventario directo (accesorio)",
        "category": "inventario",
        "turns": [
            (
                "Necesito masilla para resanar una pared",
                {
                    "tools_called": ["consultar_inventario"],
                },
            ),
        ],
    },

    # ══════════════════════════════════════════════════════════════════════
    # PEDIDO DIRECTO (cliente sabe lo que quiere)
    # ══════════════════════════════════════════════════════════════════════
    {
        "name": "PEDIDO DIRECTO → 3 cuñetes Koraza blanco",
        "category": "pedido_directo",
        "turns": [
            (
                "Necesito 3 cuñetes de Koraza blanco",
                {
                    "tools_called": ["consultar_inventario"],
                    "check_has_price": True,
                },
            ),
        ],
    },
    {
        "name": "PEDIDO DIRECTO → 8 galones Viniltex blanco",
        "category": "pedido_directo",
        "turns": [
            (
                "Quiero 8 galones de Viniltex blanco",
                {
                    "tools_called": ["consultar_inventario"],
                    "check_has_price": True,
                },
            ),
        ],
    },
    {
        "name": "PEDIDO MULTI-PRODUCTO → varios ítems",
        "category": "pedido_directo",
        "turns": [
            (
                "Necesito 2 galones de Corrotec rojo, 2 galones de Pintulux blanco y 5 lijas 120",
                {
                    "tools_called": ["consultar_inventario"],
                },
            ),
        ],
    },
    {
        "name": "PEDIDO DIRECTO → presentación calculada sin preguntar",
        "category": "pedido_directo",
        "turns": [
            (
                "Quiero Koraza blanco para 50 metros cuadrados",
                {
                    "tools_called": ["consultar_inventario"],
                    "check_has_price": True,
                },
            ),
        ],
    },

    # ══════════════════════════════════════════════════════════════════════
    # COHERENCIA CONVERSACIONAL
    # ══════════════════════════════════════════════════════════════════════
    {
        "name": "CAMBIO DE CONTEXTO → de asesoría a pedido directo",
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
                    "response_contains": ["Aquablock", "aquablock"],
                },
            ),
        ],
    },
    {
        "name": "SALUDO → no llamar herramientas",
        "category": "coherencia",
        "turns": [
            (
                "Hola buenos días",
                {
                    "tools_not_called": ["consultar_inventario", "consultar_conocimiento_tecnico"],
                },
            ),
        ],
    },
    {
        "name": "DESPEDIDA → respuesta cordial sin herramientas",
        "category": "coherencia",
        "turns": [
            (
                "Muchas gracias por todo, eso es todo por hoy",
                {
                    "tools_not_called": ["consultar_inventario", "consultar_conocimiento_tecnico"],
                },
            ),
        ],
    },
    {
        "name": "PREGUNTA FUERA DE CONTEXTO → no inventar",
        "category": "coherencia",
        "turns": [
            (
                "¿Ustedes venden cemento o arena?",
                {
                    "tools_not_called": ["consultar_inventario"],
                },
            ),
        ],
    },
    {
        "name": "CORRECCIÓN DE PEDIDO → cambio de color tras consulta",
        "category": "coherencia",
        "turns": [
            (
                "Quiero 2 galones de Viniltex blanco",
                {
                    "tools_called": ["consultar_inventario"],
                },
            ),
            (
                "Mejor no, cámbialo a Viniltex almendra",
                {
                    "tools_called": ["consultar_inventario"],
                },
            ),
        ],
    },

    # ══════════════════════════════════════════════════════════════════════
    # QUERY EXPANSION (jerga → traducción técnica → RAG)
    # ══════════════════════════════════════════════════════════════════════
    {
        "name": "JERGA → carretas pesadas dañan piso → Pintucoat",
        "category": "query_expansion",
        "turns": [
            (
                "Las carretas pesadas del almacén me están dañando el piso de la bodega",
                {
                    "tools_called": ["consultar_conocimiento_tecnico"],
                    "response_contains": ["Pintucoat", "pintucoat", "epóx", "epox", "piso"],
                },
            ),
        ],
    },
    {
        "name": "JERGA → pintura se sopla/ampolla → Aquablock",
        "category": "query_expansion",
        "turns": [
            (
                "La pintura de la pared se sopla y se ampolla, sale como un polvo blanco",
                {
                    "tools_called": ["consultar_conocimiento_tecnico"],
                    "response_contains": ["Aquablock", "aquablock", "humedad"],
                },
            ),
        ],
    },
    {
        "name": "JERGA → agua sube pared desde piso → humedad capilar",
        "category": "query_expansion",
        "turns": [
            (
                "Me sale agua por la pared de abajo, desde el piso sube la humedad",
                {
                    "tools_called": ["consultar_conocimiento_tecnico"],
                    "response_contains": ["Aquablock", "aquablock", "capilar", "humedad"],
                },
            ),
        ],
    },
    {
        "name": "JERGA → zorras almacén rayan piso → epóxico",
        "category": "query_expansion",
        "turns": [
            (
                "Las zorras del almacén me rayaron todo el piso de la bodega",
                {
                    "tools_called": ["consultar_conocimiento_tecnico"],
                    "response_contains": ["Pintucoat", "pintucoat", "piso", "epóx", "epox", "industrial"],
                },
            ),
        ],
    },
    {
        "name": "JERGA → fachada se moja y pela → Koraza",
        "category": "query_expansion",
        "turns": [
            (
                "Cada que llueve la fachada de la casa se moja toda y se pela la pintura",
                {
                    "tools_called": ["consultar_conocimiento_tecnico"],
                    "response_contains": ["Koraza", "koraza", "fachada", "impermeab"],
                },
            ),
        ],
    },
    {
        "name": "JERGA → mucho humo y químicos en planta → recubrimiento industrial",
        "category": "query_expansion",
        "turns": [
            (
                "Tenemos una planta industrial con mucho humo químico y necesitamos proteger las paredes y pisos",
                {
                    "tools_called": ["consultar_conocimiento_tecnico"],
                    "response_contains": ["epóx", "epox", "Pintucoat", "pintucoat", "Interseal", "interseal", "químic"],
                },
            ),
        ],
    },

    # ══════════════════════════════════════════════════════════════════════
    # ANTI-RENDICIÓN COMERCIAL (debe cotizar, NO derivar a asesor)
    # ══════════════════════════════════════════════════════════════════════
    {
        "name": "ANTI-RENDICIÓN → tiene producto+precio, debe cotizar",
        "category": "anti_rendicion",
        "turns": [
            (
                "Quiero comprar Koraza blanco en cuñete, ¿cuánto cuesta?",
                {
                    "tools_called": ["consultar_inventario"],
                    "check_has_price": True,
                    "response_excludes": ["consulte con", "comuníquese con", "contacte a"],
                },
            ),
        ],
    },
    {
        "name": "ANTI-RENDICIÓN → precio + disponibilidad directa",
        "category": "anti_rendicion",
        "turns": [
            (
                "¿Cuánto vale el galón de Viniltex blanco y lo tienen en stock?",
                {
                    "tools_called": ["consultar_inventario"],
                    "check_has_price": True,
                },
            ),
        ],
    },

    # ══════════════════════════════════════════════════════════════════════
    # VALIDACIÓN DE PRECIOS Y FORMATO
    # ══════════════════════════════════════════════════════════════════════
    {
        "name": "PRECIO → Koraza cuñete sin IVA doble",
        "category": "precio_validacion",
        "turns": [
            (
                "Dame el precio de Koraza blanco en cuñete",
                {
                    "tools_called": ["consultar_inventario"],
                    "check_has_price": True,
                    "check_no_iva_double": True,
                },
            ),
        ],
    },
    {
        "name": "PRECIO → Pintuco Fill galón sin IVA doble",
        "category": "precio_validacion",
        "turns": [
            (
                "¿Cuánto cuesta el galón de Pintuco Fill?",
                {
                    "tools_called": ["consultar_inventario"],
                    "check_has_price": True,
                    "check_no_iva_double": True,
                },
            ),
        ],
    },
    {
        "name": "PRECIO → Viniltex cuarto sin IVA doble",
        "category": "precio_validacion",
        "turns": [
            (
                "¿Cuánto vale un cuarto de Viniltex blanco?",
                {
                    "tools_called": ["consultar_inventario"],
                    "check_has_price": True,
                    "check_no_iva_double": True,
                },
            ),
        ],
    },

    # ══════════════════════════════════════════════════════════════════════
    # BICOMPONENTES (catalizador obligatorio)
    # ══════════════════════════════════════════════════════════════════════
    {
        "name": "BICOMPONENTE → Pintucoat debe incluir catalizador",
        "category": "bicomponente",
        "turns": [
            (
                "Quiero Pintucoat para 100 m² de piso industrial",
                {
                    "tools_called": ["consultar_inventario"],
                    "response_contains": ["catalizador", "Catalizador", "kit", "Kit", "comp", "Comp"],
                },
            ),
        ],
    },
    {
        "name": "BICOMPONENTE → Interseal debe tener componente B",
        "category": "bicomponente",
        "turns": [
            (
                "Necesito Interseal para un tanque metálico, cuánto necesito para 50 m²",
                {
                    "tools_called": ["consultar_inventario"],
                    "response_contains": ["catalizador", "Catalizador", "comp", "Comp", "parte", "Parte", "kit", "Kit"],
                },
            ),
        ],
    },

    # ══════════════════════════════════════════════════════════════════════
    # 🔥 CÁMARA DE TORTURA — CASOS DE BORDE TÓXICOS
    # ══════════════════════════════════════════════════════════════════════
    {
        "name": "LA TRINIDAD INDUSTRIAL → Pintucoat + Catalizador + SOLVENTE",
        "category": "trinidad_ajustadores",
        "turns": [
            (
                "Necesito pintar el piso de mi taller, son 45 m2. Cotízame el Pintucoat gris, por favor.",
                {
                    "tools_called": ["consultar_conocimiento_tecnico", "consultar_inventario"],
                    "response_contains": ["Pintucoat", "catalizador", "solvente", "epóxico", "Intergard", "Interseal", "Kit"],
                    "response_excludes": ["Subtotal"],
                },
            ),
        ],
    },
    {
        "name": "MATEMÁTICA FRACCIONADA → Redondeo estricto hacia arriba (Anti-escasez)",
        "category": "matematica_fracciones",
        "turns": [
            (
                "Tengo una pared interior en estuco de 82 metros cuadrados. Cotízame Viniltex Advanced Blanco.",
                {
                    "tools_called": ["consultar_inventario"],
                    "response_contains": ["5 galones", "cuñete", "Sellomax", "Sellador"],
                    "response_excludes": ["4 galones", "4.1"],
                },
            ),
        ],
    },
    {
        "name": "EL CLIENTE TERCO → Presión de presupuesto vs Regla Técnica",
        "category": "guardia_calidad",
        "turns": [
            (
                "Voy a pintar una fachada de bloque nuevo de 50 m2. Solo cotízame la Koraza, no tengo plata para selladores ni bobadas.",
                {
                    "tools_called": ["consultar_conocimiento_tecnico"],
                    "response_contains": ["garant", "alcalinidad", "descascar", "sellador", "Koraza"],
                },
            ),
        ],
    },
    {
        "name": "AMNESIA Y DISTRACCIÓN → Cambio de contexto y regreso",
        "category": "memoria_largo_plazo",
        "turns": [
            (
                "Necesito pintar 100 m2 de piso industrial pesado con Intergard.",
                {
                    "tools_called": ["consultar_inventario"],
                    "response_contains": ["Intergard", "Cuarzo", "catalizador"],
                },
            ),
            (
                "Ah, espera. Y para una reja pequeña de 2 metros que está oxidada, ¿qué llevo?",
                {
                    "tools_called": ["consultar_conocimiento_tecnico"],
                    "response_contains": ["Corrotec", "óxido"],
                },
            ),
            (
                "Listo, agrégalo. Confírmame el total a pagar de todo junto (el piso y la reja).",
                {
                    "response_contains": ["100", "Intergard", "Corrotec", "Total"],
                    "response_excludes": ["¿Cuántos metros cuadrados tiene el piso?"],
                },
            ),
        ],
    },
    {
        "name": "EL TRAMPOSO DE LOS KITS → Intentar comprar Parte A sin Parte B",
        "category": "guardia_bicomponente",
        "turns": [
            (
                "Dame 2 galones de Interthane 990 blanco. Pero OJO, no me metas el catalizador PHA046 que aquí en la obra me sobró uno de ayer.",
                {
                    "response_contains": ["Kit", "completo"],
                    "response_excludes": ["solo", "Parte A sin catalizador"],
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
    print(f"  Tests: {len(RAG_TESTS)}")
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

    return passed, warned, failed, results


# ──────────────────────────────────────────────────────────────────────────────
# Helper: send agent request with retry on timeout
# ──────────────────────────────────────────────────────────────────────────────
def _agent_request(agent_test_url, payload, retries=MAX_RETRIES):
    """Send POST to /admin/agent-test with automatic retry on timeout."""
    last_error = None
    for attempt in range(1, retries + 1):
        try:
            t0 = time.time()
            resp = requests.post(
                agent_test_url,
                headers={"x-admin-key": ADMIN_KEY, "Content-Type": "application/json"},
                json=payload,
                timeout=AGENT_TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()
            if data.get("error"):
                raise RuntimeError(data["error"])
            elapsed_ms = int((time.time() - t0) * 1000)
            return data.get("result") or {}, elapsed_ms
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            last_error = e
            if attempt < retries:
                wait = 5 * attempt
                print(f"  ⏳ Timeout (intento {attempt}/{retries}), reintentando en {wait}s...")
                time.sleep(wait)
            continue
        except Exception as e:
            raise e
    raise last_error


# ──────────────────────────────────────────────────────────────────────────────
# AGENT Test Runner — Simula conversaciones multi-turno
# ──────────────────────────────────────────────────────────────────────────────
def run_agent_tests(category_filter=None):
    if category_filter:
        convs = [c for c in AGENT_CONVERSATIONS if c["category"] in category_filter]
    else:
        convs = AGENT_CONVERSATIONS
    total_turns = sum(len(conv["turns"]) for conv in convs)
    print("\n\n" + "=" * 90)
    print("PARTE 2: AGENTE COMPLETO — Flujo multi-turno con LLM + herramientas")
    if category_filter:
        print(f"  🎯 FILTRO: {', '.join(category_filter)}")
    print(f"  Conversaciones: {len(convs)} | Turnos: {total_turns} | Timeout: {AGENT_TIMEOUT}s | Retries: {MAX_RETRIES}")
    print("=" * 90)

    agent_test_url = f"{BACKEND_URL.rstrip('/')}/admin/agent-test"

    passed = 0
    warned = 0
    failed = 0
    conv_results = []

    for conv_idx, conv in enumerate(convs, 1):
        conv_name = conv["name"]
        conv_category = conv["category"]
        print(f"\n{'━' * 90}")
        print(f"🗣️ CONV {conv_idx}/{len(convs)}: {conv_name} [{conv_category}]")
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
                result, elapsed_ms = _agent_request(agent_test_url, {
                    "profile_name": "Test User",
                    "conversation_context": conversation_context,
                    "recent_messages": recent_messages,
                    "user_message": user_message,
                    "context": context,
                })
                try:
                    os.makedirs("artifacts/agent", exist_ok=True)
                    with open(f"artifacts/agent/conv_{conv_idx:03d}_turn_{turn_idx:02d}.json", "w", encoding="utf-8") as af:
                        json.dump({"user": user_message, "result": result}, af, ensure_ascii=False, indent=2)
                except Exception:
                    pass
            except Exception as e:
                print(f"  💥 ERROR: {e}")
                failed += 1
                conv_failed += 1
                continue

            response_text = result.get("response_text", "")
            tool_calls = result.get("tool_calls", [])
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

            ctx_updates = result.get("context_updates", {})
            for k, v in ctx_updates.items():
                if v is not None:
                    conversation_context[k] = v

            response_preview = response_text[:300].replace("\n", " ↵ ")
            print(f"  🤖 [{elapsed_ms}ms] Tools: {tools_used or '—'}")
            print(f"     \"{response_preview}\"")

            # ── Validate ──
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

            # Check response contains (ANY match = pass)
            if "response_contains" in validations:
                resp_norm = normalize(response_text)
                found_any = False
                missing_all = []
                for keyword in validations["response_contains"]:
                    kw_norm = normalize(keyword)
                    if kw_norm in resp_norm:
                        found_any = True
                        break
                    missing_all.append(keyword)
                if not found_any:
                    warnings.append(f"Respuesta no contiene ninguno de: {missing_all}")

            # Check response excludes (ANY match = fail)
            if "response_excludes" in validations:
                resp_norm = normalize(response_text)
                for keyword in validations["response_excludes"]:
                    kw_norm = normalize(keyword)
                    if kw_norm in resp_norm:
                        errors.append(f"Respuesta contiene '{keyword}' (PROHIBIDO)")

            # Check diagnostic mode
            if validations.get("check_diagnostic"):
                if "?" not in response_text:
                    warnings.append("Se esperaba pregunta diagnóstica pero no hay '?'")

            # Check has price ($)
            if validations.get("check_has_price"):
                if "$" not in response_text and "precio" not in response_text.lower():
                    warnings.append("Se esperaba precio ($) en la respuesta")

            # Check no IVA double
            if validations.get("check_no_iva_double"):
                resp_lower = response_text.lower()
                if "subtotal" in resp_lower and ("iva 19%" in resp_lower or "iva (19%)" in resp_lower):
                    errors.append("IVA DOBLE: muestra Subtotal + IVA 19% separado (precio ya incluye IVA)")

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

    return passed, warned, failed, conv_results


# ──────────────────────────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 90)
    print("  SUPER TEST AGENTE CRM FERREINOX V2 — Batería Exhaustiva")
    print("  Diagnóstico • RAG • Inventario • Pedidos • Abrasivos • Gaps")
    print("  Query Expansion • Bicomponentes • Anti-Rendición • Precios")
    print("=" * 90)

    skip_rag = os.environ.get("SKIP_RAG_TESTS", "").lower() in ("1", "true", "yes")
    rag_pass, rag_warn, rag_fail, rag_details = 0, 0, 0, []
    if skip_rag:
        print(f"\n⏭️  Saltando PARTE 1 (RAG Tests): SKIP_RAG_TESTS=1")
    else:
        rag_pass, rag_warn, rag_fail, rag_details = run_rag_tests()

    # Category filter: comma-separated list, e.g. AGENT_CATEGORIES=trinidad_ajustadores,guardia_calidad
    cat_env = os.environ.get("AGENT_CATEGORIES", "").strip()
    category_filter = [c.strip() for c in cat_env.split(",") if c.strip()] or None

    agent_pass, agent_warn, agent_fail = 0, 0, 0
    agent_details = []
    skip_agent = os.environ.get("SKIP_AGENT_TESTS", "").lower() in ("1", "true", "yes")
    if skip_agent:
        print(f"\n⏭️  Saltando PARTE 2 (Agent Tests): SKIP_AGENT_TESTS=1")
    else:
        try:
            _probe = requests.post(
                f"{BACKEND_URL}/admin/agent-test",
                headers={"x-admin-key": ADMIN_KEY, "Content-Type": "application/json"},
                json={"user_message": "ping", "profile_name": "probe"},
                timeout=20,
            )
            if _probe.status_code == 403:
                print("\n❌ Admin key rechazada por el backend. Verifica ADMIN_API_KEY.")
                skip_agent = True
            elif _probe.status_code >= 500:
                print(f"\n❌ Backend devolvió {_probe.status_code}. ¿Está desplegado?")
                skip_agent = True
        except Exception as _err:
            print(f"\n❌ No se pudo conectar al backend ({BACKEND_URL}): {_err}")
            skip_agent = True

        if not skip_agent:
            agent_pass, agent_warn, agent_fail, agent_details = run_agent_tests(category_filter)

    # ── Final summary ──
    total_pass = rag_pass + agent_pass
    total_warn = rag_warn + agent_warn
    total_fail = rag_fail + agent_fail
    total_all = total_pass + total_warn + total_fail

    print("\n\n" + "=" * 90)
    print("  RESULTADO FINAL V2")
    print("=" * 90)
    print(f"  RAG:   ✅ {rag_pass}  ⚠️ {rag_warn}  ❌ {rag_fail}  ({len(RAG_TESTS)} tests)")
    if agent_pass + agent_warn + agent_fail > 0:
        agent_total_turns = sum(len(c["turns"]) for c in AGENT_CONVERSATIONS)
        print(f"  Agent: ✅ {agent_pass}  ⚠️ {agent_warn}  ❌ {agent_fail}  ({agent_total_turns} turnos en {len(AGENT_CONVERSATIONS)} conversaciones)")
    print(f"  TOTAL: ✅ {total_pass}  ⚠️ {total_warn}  ❌ {total_fail}  ({total_all} tests)")

    pct = (total_pass / total_all * 100) if total_all > 0 else 0
    if total_fail == 0 and total_warn <= 3:
        print(f"\n  🏆 {pct:.0f}% — Excelente, sin fallos críticos")
    elif total_fail == 0:
        print(f"\n  ⚠️ {pct:.0f}% — Sin fallos, pero hay advertencias a revisar")
    elif total_fail <= 3:
        print(f"\n  ⚠️ {pct:.0f}% — Pocos fallos, revisar")
    else:
        print(f"\n  ❌ {pct:.0f}% — Fallos significativos, requiere ajuste")

    if agent_details:
        failed_convs = [c for c in agent_details if c["failed"] > 0]
        if failed_convs:
            print(f"\n  CONVERSACIONES CON FALLOS ({len(failed_convs)}):")
            for c in failed_convs:
                print(f"    ❌ {c['name']} [{c['category']}] — {c['failed']} fallo(s)")

    print("=" * 90)

    summary = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "version": "V2",
        "rag": {"pass": rag_pass, "warn": rag_warn, "fail": rag_fail, "total": len(RAG_TESTS)},
        "agent": {"pass": agent_pass, "warn": agent_warn, "fail": agent_fail},
        "total": {"pass": total_pass, "warn": total_warn, "fail": total_fail, "total": total_all},
        "agent_conversations": agent_details,
        "rag_details": rag_details,
    }
    with open("test_super_agent_results.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print(f"\nResultados guardados en test_super_agent_results.json")
