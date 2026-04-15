"""
TEST E2E — Pipeline Determinístico de Cotización
=================================================
Simula 10 flujos reales de WhatsApp end-to-end:
  usuario → diagnóstico → JSON LLM → match backend → validación → cotización

Usa mocks de OpenAI y del inventario con datos realistas de Ferreinox.
Cada caso recorre TODO el pipeline y valida cada capa.
"""
import json
import sys
import os
import logging
import traceback
from typing import Optional
from unittest.mock import MagicMock, patch
from datetime import datetime

# ── Setup path ──
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))
sys.path.insert(0, os.path.dirname(__file__))

from backend.pipeline_deterministico.llm_estructurado import (
    extraer_recomendacion_estructurada,
    _validar_schema_recomendacion,
    _validar_trazabilidad_rag,
    _parsear_json_llm,
)
from backend.pipeline_deterministico.matcher_productos import (
    match_producto_contra_inventario,
    match_sistema_completo,
    normalizar_texto,
    _calcular_score,
    ResultadoMatch,
)
from backend.pipeline_deterministico.validaciones import (
    ejecutar_validacion_completa,
    validar_coherencia_diagnostico,
    validar_completitud_match,
    validar_coherencia_recomendacion_match,
    validar_compatibilidad_quimica,
    validar_bicomponentes,
)
from backend.pipeline_deterministico.generador_cotizacion import (
    generar_respuesta_cotizacion_whatsapp,
    generar_payload_pdf,
)
from backend.pipeline_deterministico.orquestador import (
    ejecutar_pipeline_cotizacion,
    PipelineTrace,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger("test_e2e")

# ══════════════════════════════════════════════════════════════════════════════
# INVENTARIO SIMULADO REALISTA (datos tipo Ferreinox)
# ══════════════════════════════════════════════════════════════════════════════

INVENTARIO_MOCK = [
    # ── Vinilos / Pinturas de acabado ──
    {"codigo_articulo": "1501", "descripcion": "VINILTEX ADVANCED BLANCO 1501 GALON", "descripcion_comercial": "Viniltex Advanced Blanco Galón", "marca": "PINTUCO", "presentacion": "galon", "precio_venta": 89900, "stock_total": 45},
    {"codigo_articulo": "1502", "descripcion": "VINILTEX ADVANCED BLANCO 1501 CUNETE", "descripcion_comercial": "Viniltex Advanced Blanco Cuñete", "marca": "PINTUCO", "presentacion": "cunete", "precio_venta": 399000, "stock_total": 12},
    {"codigo_articulo": "1510", "descripcion": "VINILTEX BANOS Y COCINAS BLANCO GALON", "descripcion_comercial": "Viniltex Baños y Cocinas Blanco Galón", "marca": "PINTUCO", "presentacion": "galon", "precio_venta": 109900, "stock_total": 20},
    {"codigo_articulo": "1511", "descripcion": "VINILTEX BANOS Y COCINAS BLANCO CUNETE", "descripcion_comercial": "Viniltex Baños y Cocinas Blanco Cuñete", "marca": "PINTUCO", "presentacion": "cunete", "precio_venta": 489000, "stock_total": 5},
    {"codigo_articulo": "1600", "descripcion": "INTERVINIL BLANCO GALON", "descripcion_comercial": "Intervinil Blanco Galón", "marca": "PINTUCO", "presentacion": "galon", "precio_venta": 54900, "stock_total": 60},
    {"codigo_articulo": "1601", "descripcion": "INTERVINIL BLANCO CUNETE", "descripcion_comercial": "Intervinil Blanco Cuñete", "marca": "PINTUCO", "presentacion": "cunete", "precio_venta": 249000, "stock_total": 15},
    {"codigo_articulo": "1700", "descripcion": "KORAZA BLANCO GALON", "descripcion_comercial": "Koraza Blanco Galón", "marca": "PINTUCO", "presentacion": "galon", "precio_venta": 119900, "stock_total": 30},
    {"codigo_articulo": "1701", "descripcion": "KORAZA BLANCO CUNETE", "descripcion_comercial": "Koraza Blanco Cuñete", "marca": "PINTUCO", "presentacion": "cunete", "precio_venta": 529000, "stock_total": 8},

    # ── Impermeabilizantes / Selladores ──
    {"codigo_articulo": "2001", "descripcion": "AQUABLOCK ULTRA BLANCO GALON", "descripcion_comercial": "Aquablock Ultra Blanco Galón", "marca": "PINTUCO", "presentacion": "galon", "precio_venta": 139900, "stock_total": 25},
    {"codigo_articulo": "2002", "descripcion": "AQUABLOCK ULTRA BLANCO CUNETE", "descripcion_comercial": "Aquablock Ultra Blanco Cuñete", "marca": "PINTUCO", "presentacion": "cunete", "precio_venta": 619000, "stock_total": 6},

    # ── Estucos ──
    {"codigo_articulo": "3001", "descripcion": "ESTUCO PROF EXT BLANCO GALON", "descripcion_comercial": "Estuco Acrílico Profesional Exterior Blanco Galón", "marca": "PINTUCO", "presentacion": "galon", "precio_venta": 69900, "stock_total": 35},
    {"codigo_articulo": "3002", "descripcion": "ESTUCO PROF EXT BLANCO CUNETE", "descripcion_comercial": "Estuco Acrílico Profesional Exterior Blanco Cuñete", "marca": "PINTUCO", "presentacion": "cunete", "precio_venta": 299000, "stock_total": 10},

    # ── Anticorrosivos / Metal ──
    {"codigo_articulo": "4001", "descripcion": "CORROTEC GRIS GALON", "descripcion_comercial": "Corrotec Anticorrosivo Gris Galón", "marca": "PINTUCO", "presentacion": "galon", "precio_venta": 95900, "stock_total": 20},
    {"codigo_articulo": "4002", "descripcion": "PINTULUX 3EN1 BLANCO GALON", "descripcion_comercial": "Pintulux 3en1 Blanco Brillante Galón", "marca": "PINTUCO", "presentacion": "galon", "precio_venta": 119900, "stock_total": 18},

    # ── Industrial International ──
    {"codigo_articulo": "5001", "descripcion": "INTERSEAL 670HS GRIS RAL7038 GALON KIT", "descripcion_comercial": "Interseal 670 HS Gris RAL 7038 Galón Kit", "marca": "INTERNATIONAL", "presentacion": "kit", "precio_venta": 389000, "stock_total": 4},
    {"codigo_articulo": "5002", "descripcion": "INTERTHANE 990 BLANCO RAL9016 GALON KIT", "descripcion_comercial": "Interthane 990 Blanco RAL 9016 Galón Kit", "marca": "INTERNATIONAL", "presentacion": "kit", "precio_venta": 459000, "stock_total": 3},
    {"codigo_articulo": "5003", "descripcion": "THINNER UFA151 GALON", "descripcion_comercial": "Thinner UFA151 Galón", "marca": "INTERNATIONAL", "presentacion": "galon", "precio_venta": 85000, "stock_total": 10},

    # ── Pisos ──
    {"codigo_articulo": "6001", "descripcion": "PINTUCOAT GRIS GALON KIT", "descripcion_comercial": "Pintucoat Epóxico Gris Galón Kit", "marca": "PINTUCO", "presentacion": "kit", "precio_venta": 189000, "stock_total": 8},
    {"codigo_articulo": "6002", "descripcion": "THINNER EPOXICO PINTUCO GALON", "descripcion_comercial": "Thinner Epóxico Pintuco Galón", "marca": "PINTUCO", "presentacion": "galon", "precio_venta": 45000, "stock_total": 15},

    # ── Herramientas ──
    {"codigo_articulo": "H001", "descripcion": "RODILLO TOPLINE 9 PULGADAS", "descripcion_comercial": "Rodillo TopLine 9 Pulgadas", "marca": "GOYA", "presentacion": "unidad", "precio_venta": 18900, "stock_total": 50},
    {"codigo_articulo": "H002", "descripcion": "BROCHA GOYA PROFESIONAL 3 PULGADAS", "descripcion_comercial": "Brocha Goya Profesional 3 Pulgadas", "marca": "GOYA", "presentacion": "unidad", "precio_venta": 15900, "stock_total": 40},
    {"codigo_articulo": "H003", "descripcion": "LIJA ABRACOL GRANO 80 PLIEGO", "descripcion_comercial": "Lija Abracol Grano 80 Pliego", "marca": "ABRACOL", "presentacion": "unidad", "precio_venta": 3200, "stock_total": 200},
    {"codigo_articulo": "H004", "descripcion": "LIJA ABRACOL GRANO 150 PLIEGO", "descripcion_comercial": "Lija Abracol Grano 150 Pliego", "marca": "ABRACOL", "presentacion": "unidad", "precio_venta": 3200, "stock_total": 150},
    {"codigo_articulo": "H005", "descripcion": "BANDEJA PLASTICA PARA PINTURA", "descripcion_comercial": "Bandeja Plástica para Pintura", "marca": "GOYA", "presentacion": "unidad", "precio_venta": 8500, "stock_total": 30},

    # ── Madera ──
    {"codigo_articulo": "7001", "descripcion": "BARNEX ROBLE GALON", "descripcion_comercial": "Barnex Tinte y Barniz Roble Galón", "marca": "PINTUCO", "presentacion": "galon", "precio_venta": 98900, "stock_total": 12},
    {"codigo_articulo": "7002", "descripcion": "WOOD STAIN NATURAL GALON", "descripcion_comercial": "Wood Stain Natural Galón", "marca": "PINTUCO", "presentacion": "galon", "precio_venta": 85900, "stock_total": 8},

    # ── Pintura de tráfico ──
    {"codigo_articulo": "8001", "descripcion": "PINTURA DE TRAFICO AMARILLO GALON", "descripcion_comercial": "Pintura de Tráfico Amarillo Galón", "marca": "PINTUCO", "presentacion": "galon", "precio_venta": 79900, "stock_total": 15},
    {"codigo_articulo": "8002", "descripcion": "THINNER 21204 BOTELLA", "descripcion_comercial": "Thinner 21204 Botella", "marca": "PINTUCO", "presentacion": "unidad", "precio_venta": 12500, "stock_total": 40},
]

PRECIOS_MOCK = {
    item["codigo_articulo"]: {
        "referencia": item["codigo_articulo"],
        "descripcion": item["descripcion"],
        "marca": item["marca"],
        "precio_mejor": item["precio_venta"],
    }
    for item in INVENTARIO_MOCK
}


def mock_lookup_fn(texto_busqueda: str) -> list[dict]:
    """Simula búsqueda en inventario con fuzzy matching básico."""
    texto_norm = normalizar_texto(texto_busqueda)
    resultados = []
    for item in INVENTARIO_MOCK:
        desc_norm = normalizar_texto(item["descripcion"])
        desc_com_norm = normalizar_texto(item.get("descripcion_comercial", ""))
        # Match si al menos 2 palabras significativas coinciden
        palabras_query = set(texto_norm.split()) - {"blanco", "gris", "galon", "cunete", "de", "para"}
        palabras_desc = set(desc_norm.split()) | set(desc_com_norm.split())
        overlap = len(palabras_query & palabras_desc)
        if overlap >= 1 or any(p in desc_norm or p in desc_com_norm for p in palabras_query):
            resultados.append(item)
    return resultados[:10]


def mock_price_fn(codigo: str) -> Optional[dict]:
    return PRECIOS_MOCK.get(codigo)


# ══════════════════════════════════════════════════════════════════════════════
# MOCK DE OPENAI CLIENT — Configurable por caso.
# Cada caso define qué JSON devuelve el "LLM".
# ══════════════════════════════════════════════════════════════════════════════

def crear_mock_openai(respuesta_json: dict):
    """Crea un mock de OpenAI que devuelve el JSON dado."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_choice = MagicMock()
    mock_message = MagicMock()
    mock_message.content = json.dumps(respuesta_json, ensure_ascii=False)
    mock_choice.message = mock_message
    mock_response.choices = [mock_choice]
    mock_client.chat.completions.create.return_value = mock_response
    return mock_client


# ══════════════════════════════════════════════════════════════════════════════
# LOS 10 CASOS DE PRUEBA
# ══════════════════════════════════════════════════════════════════════════════

CASOS_TEST = []

# -----------------------------------------------------------------------
# CASO 1: Humedad interior clásica — muro con salitre (caso más común)
# -----------------------------------------------------------------------
CASOS_TEST.append({
    "id": 1,
    "titulo": "Humedad interior clásica — muro estucado con salitre",
    "input_usuario": "Hola, tengo un muro interior en mi apartamento que tiene humedad y salitre blanco, se está pelando la pintura. Son como 4x3 metros, o sea unos 12 m². ¿Qué me recomiendan?",
    "diagnostico_contexto": {
        "superficie": "muro",
        "material": "estuco",
        "ubicacion": "interior",
        "condicion": "humedad con salitre, pintura descascarada",
        "area_m2": 12,
        "problema_principal": "humedad ascendente por capilaridad con eflorescencia salina",
    },
    "respuesta_rag": {
        "encontrado": True,
        "respuesta_rag": "Para muro interior con humedad y salitre: 1) Remover pintura dañada, raspar salitre. 2) Lijar con grano 80. 3) Aplicar Aquablock Ultra como impermeabilizante (2 manos). 4) Estuco Acrílico para Exterior/humedad. 5) Acabado con Viniltex Baños y Cocinas (zonas húmedas) o Viniltex Advanced (zonas secas). Herramientas: lija 80, rodillo, brocha.",
        "guia_tecnica_estructurada": {
            "preparation_steps": ["Remover pintura dañada", "Raspar salitre", "Lijar con grano 80"],
            "base_or_primer": "Aquablock Ultra",
            "intermediate_steps": ["Estuco Acrílico para Exterior"],
            "finish_options": ["Viniltex Baños y Cocinas", "Viniltex Advanced"],
            "forbidden_products_or_shortcuts": ["Koraza como imprimante interior", "Koraza como acabado interior humedad"],
        },
        "diagnostico_estructurado": {
            "problem_class": "humedad_interior_capilaridad",
            "required_validations": [],
            "pricing_ready": True,
        },
        "conocimiento_comercial_ferreinox": [
            "En humedad interior con salitre: Aquablock Ultra + Estuco Acrílico + Viniltex B&C",
            "Nunca Koraza como imprimante interior",
        ],
    },
    "json_llm_simulado": {
        "diagnostico": {
            "superficie": "muro",
            "material": "estuco",
            "ubicacion": "interior",
            "condicion": "humedad con salitre, pintura descascarada",
            "area_m2": 12,
            "problema_principal": "humedad ascendente por capilaridad",
        },
        "sistema": [
            {"paso": 1, "funcion": "preparacion", "producto": "LIJA ABRACOL GRANO 80", "presentacion": "unidad", "cantidad": 4},
            {"paso": 2, "funcion": "sellador", "producto": "AQUABLOCK ULTRA BLANCO", "presentacion": "galon", "cantidad": 2, "color": "blanco"},
            {"paso": 3, "funcion": "base", "producto": "ESTUCO ACRILICO EXTERIOR BLANCO", "presentacion": "galon", "cantidad": 2, "color": "blanco"},
            {"paso": 4, "funcion": "acabado", "producto": "VINILTEX BANOS Y COCINAS BLANCO", "presentacion": "galon", "cantidad": 2, "color": "blanco"},
        ],
        "herramientas": [
            {"producto": "RODILLO TOPLINE 9 PULGADAS", "cantidad": 1},
            {"producto": "BROCHA GOYA PROFESIONAL 3 PULGADAS", "cantidad": 1},
        ],
        "justificacion_tecnica": "Muro interior con humedad ascendente y salitre requiere impermeabilización con Aquablock Ultra, estuco acrílico para nivelar y Viniltex Baños y Cocinas como acabado resistente a humedad.",
    },
    "validaciones_esperadas": {
        "productos_deben_matchear": ["AQUABLOCK", "ESTUCO", "VINILTEX BA", "LIJA"],
        "herramientas_deben_matchear": ["RODILLO", "BROCHA"],
        "debe_tener_iva": True,
        "no_debe_contener": ["Koraza", "Viniltex Advanced"],
    },
})

# -----------------------------------------------------------------------
# CASO 2: TRAMPA — LLM cambia producto (dice B&C, cotiza Advanced)
# Este es el bug central que el pipeline debe detectar.
# -----------------------------------------------------------------------
CASOS_TEST.append({
    "id": 2,
    "titulo": "TRAMPA: LLM cambia Baños y Cocinas por Viniltex Advanced",
    "input_usuario": "Necesito pintar el baño de mi casa, tiene algo de humedad. Son unos 8 m².",
    "diagnostico_contexto": {
        "superficie": "muro",
        "material": "estuco",
        "ubicacion": "interior",
        "condicion": "humedad leve en baño",
        "area_m2": 8,
        "problema_principal": "condensación en baño",
    },
    "respuesta_rag": {
        "encontrado": True,
        "respuesta_rag": "Para baño con humedad: Preparar superficie, Aquablock Ultra, Viniltex Baños y Cocinas como acabado.",
        "guia_tecnica_estructurada": {
            "preparation_steps": ["Lijar", "Limpiar"],
            "base_or_primer": "Aquablock Ultra",
            "finish_options": ["Viniltex Baños y Cocinas"],
        },
        "diagnostico_estructurado": {"problem_class": "humedad_condensacion_bano", "pricing_ready": True},
        "conocimiento_comercial_ferreinox": ["Para baños SIEMPRE Viniltex Baños y Cocinas"],
    },
    "json_llm_simulado": {
        "diagnostico": {
            "superficie": "muro",
            "material": "estuco",
            "ubicacion": "interior",
            "condicion": "humedad en baño",
            "area_m2": 8,
            "problema_principal": "condensación",
        },
        "sistema": [
            {"paso": 1, "funcion": "preparacion", "producto": "LIJA ABRACOL GRANO 150", "presentacion": "unidad", "cantidad": 3},
            {"paso": 2, "funcion": "sellador", "producto": "AQUABLOCK ULTRA BLANCO", "presentacion": "galon", "cantidad": 1, "color": "blanco"},
            # ⚠️ AQUÍ ESTÁ LA TRAMPA: El RAG dice "Baños y Cocinas" pero el LLM pone "VINILTEX ADVANCED"
            {"paso": 3, "funcion": "acabado", "producto": "VINILTEX ADVANCED BLANCO", "presentacion": "galon", "cantidad": 1, "color": "blanco"},
        ],
        "herramientas": [
            {"producto": "RODILLO TOPLINE 9 PULGADAS", "cantidad": 1},
        ],
        "justificacion_tecnica": "Baño con humedad leve, sellado con Aquablock y acabado lavable.",
    },
    "validaciones_esperadas": {
        "debe_detectar_cambio_producto": True,
        "producto_cambiado_de": "VINILTEX BANOS Y COCINAS",
        "producto_cambiado_a": "VINILTEX ADVANCED",
        "trazabilidad_debe_fallar": True,
    },
})

# -----------------------------------------------------------------------
# CASO 3: Fachada exterior con Koraza — caso legítimo
# -----------------------------------------------------------------------
CASOS_TEST.append({
    "id": 3,
    "titulo": "Fachada exterior con Koraza — caso legítimo",
    "input_usuario": "Necesito pintar la fachada de mi casa, está toda deteriorada por el sol y la lluvia. Son unos 30 m².",
    "diagnostico_contexto": {
        "superficie": "fachada",
        "material": "estuco",
        "ubicacion": "exterior",
        "condicion": "deterioro por intemperie, pintura descascarada",
        "area_m2": 30,
        "problema_principal": "degradación UV y exposición a lluvia",
    },
    "respuesta_rag": {
        "encontrado": True,
        "respuesta_rag": "Para fachada exterior deteriorada: lijar, aplicar Koraza como acabado exterior de alta durabilidad.",
        "guia_tecnica_estructurada": {
            "preparation_steps": ["Raspar pintura suelta", "Lijar con grano 80"],
            "finish_options": ["Koraza"],
        },
        "diagnostico_estructurado": {"problem_class": "repintura_fachada", "pricing_ready": True},
    },
    "json_llm_simulado": {
        "diagnostico": {
            "superficie": "fachada",
            "material": "estuco",
            "ubicacion": "exterior",
            "condicion": "deterioro por intemperie",
            "area_m2": 30,
            "problema_principal": "degradación UV y lluvia",
        },
        "sistema": [
            {"paso": 1, "funcion": "preparacion", "producto": "LIJA ABRACOL GRANO 80", "presentacion": "unidad", "cantidad": 6},
            # 30m² ÷ 10m²/gal ≈ 3 gal → debería sugerir presentación eficiente
            {"paso": 2, "funcion": "acabado", "producto": "KORAZA BLANCO", "presentacion": "cunete", "cantidad": 1, "color": "blanco"},
            {"paso": 3, "funcion": "acabado", "producto": "KORAZA BLANCO", "presentacion": "galon", "cantidad": 1, "color": "blanco"},
        ],
        "herramientas": [
            {"producto": "RODILLO TOPLINE 9 PULGADAS", "cantidad": 2},
            {"producto": "BROCHA GOYA PROFESIONAL 3 PULGADAS", "cantidad": 1},
        ],
        "justificacion_tecnica": "Fachada exterior necesita Koraza por su resistencia UV y lluvia. 1 cuñete + 1 galón para 30 m².",
    },
    "validaciones_esperadas": {
        "productos_deben_matchear": ["KORAZA", "LIJA"],
        "herramientas_deben_matchear": ["RODILLO", "BROCHA"],
    },
})

# -----------------------------------------------------------------------
# CASO 4: Piso industrial con epóxico + catalizador (bicomponente)
# -----------------------------------------------------------------------
CASOS_TEST.append({
    "id": 4,
    "titulo": "Piso industrial con Pintucoat — bicomponente con catalizador",
    "input_usuario": "Necesito pintar el piso de la bodega, es concreto, tráfico de montacargas. Unos 50 m².",
    "diagnostico_contexto": {
        "superficie": "piso",
        "material": "concreto",
        "ubicacion": "industrial",
        "condicion": "concreto nuevo, tráfico pesado",
        "area_m2": 50,
        "problema_principal": "protección de piso industrial tráfico pesado",
    },
    "respuesta_rag": {
        "encontrado": True,
        "respuesta_rag": "Piso concreto industrial: Pintucoat epóxico + Thinner Epóxico Pintuco. Bicomponente obligatorio.",
        "guia_tecnica_estructurada": {
            "preparation_steps": ["Escarificar superficie", "Limpiar polvo"],
            "finish_options": ["Pintucoat"],
            "forbidden_products_or_shortcuts": ["Viniltex en pisos"],
        },
        "diagnostico_estructurado": {"problem_class": "piso_industrial_epoxico", "pricing_ready": True},
    },
    "json_llm_simulado": {
        "diagnostico": {
            "superficie": "piso",
            "material": "concreto",
            "ubicacion": "industrial",
            "condicion": "nuevo, tráfico pesado",
            "area_m2": 50,
            "problema_principal": "piso industrial para montacargas",
        },
        "sistema": [
            {"paso": 1, "funcion": "preparacion", "producto": "LIJA ABRACOL GRANO 80", "presentacion": "unidad", "cantidad": 10},
            {"paso": 2, "funcion": "acabado", "producto": "PINTUCOAT GRIS", "presentacion": "kit", "cantidad": 5, "color": "gris"},
            {"paso": 3, "funcion": "diluyente", "producto": "THINNER EPOXICO PINTUCO", "presentacion": "galon", "cantidad": 3},
        ],
        "herramientas": [
            {"producto": "RODILLO TOPLINE 9 PULGADAS", "cantidad": 3},
        ],
        "justificacion_tecnica": "Piso industrial requiere Pintucoat epóxico para resistir tráfico de montacargas. Incluye thinner epóxico obligatorio.",
    },
    "validaciones_esperadas": {
        "bicomponente_completo": True,
        "productos_deben_matchear": ["PINTUCOAT", "THINNER EP"],
    },
})

# -----------------------------------------------------------------------
# CASO 5: TRAMPA — Incompatibilidad química (alquídico + epóxico)
# -----------------------------------------------------------------------
CASOS_TEST.append({
    "id": 5,
    "titulo": "TRAMPA: Incompatibilidad química — Corrotec (alquídico) + Pintucoat (epóxico)",
    "input_usuario": "Quiero pintar una reja metálica y luego el piso al lado. ¿Me cotizas todo?",
    "diagnostico_contexto": {
        "superficie": "reja metálica + piso",
        "material": "metal + concreto",
        "ubicacion": "exterior",
        "condicion": "óxido leve en reja, piso nuevo",
        "area_m2": 15,
        "problema_principal": "protección de metal y piso",
    },
    "respuesta_rag": {
        "encontrado": True,
        "respuesta_rag": "Reja: Corrotec anticorrosivo + Pintulux. Piso: sistema independiente.",
        "guia_tecnica_estructurada": {},
        "diagnostico_estructurado": {"problem_class": "metal_y_piso", "pricing_ready": True},
    },
    "json_llm_simulado": {
        "diagnostico": {
            "superficie": "reja + piso",
            "material": "metal y concreto",
            "ubicacion": "exterior",
            "condicion": "óxido leve y piso nuevo",
            "area_m2": 15,
            "problema_principal": "protección metal y piso",
        },
        "sistema": [
            {"paso": 1, "funcion": "preparacion", "producto": "LIJA ABRACOL GRANO 80", "presentacion": "unidad", "cantidad": 5},
            {"paso": 2, "funcion": "base", "producto": "CORROTEC GRIS", "presentacion": "galon", "cantidad": 1, "color": "gris"},
            {"paso": 3, "funcion": "acabado", "producto": "PINTULUX 3EN1 BLANCO", "presentacion": "galon", "cantidad": 1, "color": "blanco"},
            # ⚠️ NO hay incompatibilidad aquí realmente — alquídico sobre metal es correcto.
            # Pero si LLM pone Pintucoat epóxico en la MISMA cotización SOBRE el alquídico...
            # En este caso CORROTEC(alquídico) + PINTULUX(alquídico) es compatible.
            # Solo es incompatible si mezclas familias en el MISMO sistema/superficie.
        ],
        "herramientas": [
            {"producto": "BROCHA GOYA PROFESIONAL 3 PULGADAS", "cantidad": 2},
        ],
        "justificacion_tecnica": "Sistema alquídico completo: Corrotec anticorrosivo + Pintulux 3en1 como acabado.",
    },
    "validaciones_esperadas": {
        "compatibilidad_quimica_ok": True,  # Es compatible: ambos alquídicos
        "productos_deben_matchear": ["CORROTEC", "PINTULUX"],
    },
})

# -----------------------------------------------------------------------
# CASO 6: TRAMPA — Bicomponente sin catalizador (Interthane sin UFA151)
# -----------------------------------------------------------------------
CASOS_TEST.append({
    "id": 6,
    "titulo": "TRAMPA: Interthane 990 sin Thinner UFA151 (bicomponente incompleto)",
    "input_usuario": "Necesito un acabado poliuretano para una estructura metálica industrial, ya tiene anticorrosivo. 20 m².",
    "diagnostico_contexto": {
        "superficie": "estructura metálica",
        "material": "metal ferroso",
        "ubicacion": "industrial",
        "condicion": "con anticorrosivo previo",
        "area_m2": 20,
        "problema_principal": "acabado poliuretano sobre anticorrosivo",
    },
    "respuesta_rag": {
        "encontrado": True,
        "respuesta_rag": "Acabado PU industrial: Interthane 990 + Thinner UFA151 obligatorio.",
        "guia_tecnica_estructurada": {
            "finish_options": ["Interthane 990"],
            "preparation_steps": ["Verificar anticorrosivo curado"],
        },
        "diagnostico_estructurado": {"problem_class": "acabado_pu_industrial", "pricing_ready": True},
    },
    "json_llm_simulado": {
        "diagnostico": {
            "superficie": "estructura metálica",
            "material": "metal ferroso",
            "ubicacion": "industrial",
            "condicion": "anticorrosivo previo curado",
            "area_m2": 20,
            "problema_principal": "acabado PU industrial",
        },
        "sistema": [
            {"paso": 1, "funcion": "acabado", "producto": "INTERTHANE 990 BLANCO", "presentacion": "kit", "cantidad": 2, "color": "blanco"},
            # ⚠️ FALTA EL THINNER UFA151 — bicomponente incompleto!!
        ],
        "herramientas": [
            {"producto": "RODILLO TOPLINE 9 PULGADAS", "cantidad": 1},
        ],
        "justificacion_tecnica": "Interthane 990 como acabado PU de alta durabilidad sobre anticorrosivo.",
    },
    "validaciones_esperadas": {
        "bicomponente_incompleto": True,
        "catalizador_faltante": "Thinner UFA151",
    },
})

# -----------------------------------------------------------------------
# CASO 7: Presentación incorrecta — pide galón pero LLM pone cuñete
# -----------------------------------------------------------------------
CASOS_TEST.append({
    "id": 7,
    "titulo": "Presentación incorrecta — 4 m² de baño no necesita cuñete",
    "input_usuario": "Voy a pintar un bañito de visitas, son como 4 metros cuadrados nomás.",
    "diagnostico_contexto": {
        "superficie": "muro",
        "material": "estuco",
        "ubicacion": "interior",
        "condicion": "repintura normal",
        "area_m2": 4,
        "problema_principal": "repintura baño pequeño",
    },
    "respuesta_rag": {
        "encontrado": True,
        "respuesta_rag": "Repintura baño: Viniltex Baños y Cocinas.",
        "guia_tecnica_estructurada": {"finish_options": ["Viniltex Baños y Cocinas"]},
        "diagnostico_estructurado": {"problem_class": "repintura_bano", "pricing_ready": True},
    },
    "json_llm_simulado": {
        "diagnostico": {
            "superficie": "muro",
            "material": "estuco",
            "ubicacion": "interior",
            "condicion": "repintura",
            "area_m2": 4,
            "problema_principal": "repintura baño visitantes",
        },
        "sistema": [
            {"paso": 1, "funcion": "preparacion", "producto": "LIJA ABRACOL GRANO 150", "presentacion": "unidad", "cantidad": 2},
            # ⚠️ Cuñete para 4 m² es exagerado — debería ser galón
            {"paso": 2, "funcion": "acabado", "producto": "VINILTEX BANOS Y COCINAS BLANCO", "presentacion": "cunete", "cantidad": 1, "color": "blanco"},
        ],
        "herramientas": [
            {"producto": "RODILLO TOPLINE 9 PULGADAS", "cantidad": 1},
        ],
        "justificacion_tecnica": "Baño pequeño de visitas, solo requiere acabado lavable.",
    },
    "validaciones_esperadas": {
        "advertencia_presentacion": True,
        "nota": "Cuñete para 4 m² es excesivo, debería ser galón",
    },
})

# -----------------------------------------------------------------------
# CASO 8: Madera exterior — barniz con herramientas completas
# -----------------------------------------------------------------------
CASOS_TEST.append({
    "id": 8,
    "titulo": "Mueble de madera exterior — barniz con preparación completa",
    "input_usuario": "Tengo una pérgola de madera en el jardín que la quiero proteger, como 10 m².",
    "diagnostico_contexto": {
        "superficie": "madera",
        "material": "madera",
        "ubicacion": "exterior",
        "condicion": "madera expuesta sin protección",
        "area_m2": 10,
        "problema_principal": "protección de madera exterior contra intemperie",
    },
    "respuesta_rag": {
        "encontrado": True,
        "respuesta_rag": "Madera exterior: lijar, aplicar Wood Stain o Barnex para protección UV.",
        "guia_tecnica_estructurada": {
            "preparation_steps": ["Lijar con grano 150", "Limpiar polvo"],
            "finish_options": ["Wood Stain", "Barnex"],
        },
        "diagnostico_estructurado": {"problem_class": "madera_exterior", "pricing_ready": True},
    },
    "json_llm_simulado": {
        "diagnostico": {
            "superficie": "madera",
            "material": "madera natural",
            "ubicacion": "exterior",
            "condicion": "sin protección previa",
            "area_m2": 10,
            "problema_principal": "protección UV y lluvia para pérgola",
        },
        "sistema": [
            {"paso": 1, "funcion": "preparacion", "producto": "LIJA ABRACOL GRANO 150", "presentacion": "unidad", "cantidad": 5},
            {"paso": 2, "funcion": "acabado", "producto": "BARNEX ROBLE", "presentacion": "galon", "cantidad": 2, "color": "roble"},
        ],
        "herramientas": [
            {"producto": "BROCHA GOYA PROFESIONAL 3 PULGADAS", "cantidad": 2},
        ],
        "justificacion_tecnica": "Pérgola de madera exterior requiere Barnex para protección UV y lluvia.",
    },
    "validaciones_esperadas": {
        "productos_deben_matchear": ["BARNEX", "LIJA"],
        "herramientas_deben_matchear": ["BROCHA"],
    },
})

# -----------------------------------------------------------------------
# CASO 9: Producto inexistente — LLM inventa producto "SELLOMAX ULTRA"
# -----------------------------------------------------------------------
CASOS_TEST.append({
    "id": 9,
    "titulo": "TRAMPA: Producto inventado por el LLM (Sellomax Ultra no existe)",
    "input_usuario": "Necesito sellar una terraza que tiene filtraciones, unos 15 m².",
    "diagnostico_contexto": {
        "superficie": "terraza",
        "material": "concreto",
        "ubicacion": "exterior",
        "condicion": "filtraciones",
        "area_m2": 15,
        "problema_principal": "impermeabilización de terraza",
    },
    "respuesta_rag": {
        "encontrado": True,
        "respuesta_rag": "Terraza con filtraciones: Aquablock Ultra como impermeabilizante.",
        "guia_tecnica_estructurada": {
            "preparation_steps": ["Limpiar terraza", "Lijar"],
            "base_or_primer": "Aquablock Ultra",
        },
        "diagnostico_estructurado": {"problem_class": "impermeabilizacion_terraza", "pricing_ready": True},
    },
    "json_llm_simulado": {
        "diagnostico": {
            "superficie": "terraza",
            "material": "concreto",
            "ubicacion": "exterior",
            "condicion": "filtraciones",
            "area_m2": 15,
            "problema_principal": "impermeabilización terraza",
        },
        "sistema": [
            {"paso": 1, "funcion": "preparacion", "producto": "LIJA ABRACOL GRANO 80", "presentacion": "unidad", "cantidad": 5},
            # ⚠️ PRODUCTO INVENTADO: "SELLOMAX ULTRA" no existe en inventario
            {"paso": 2, "funcion": "sellador", "producto": "SELLOMAX ULTRA BLANCO", "presentacion": "galon", "cantidad": 3, "color": "blanco"},
            {"paso": 3, "funcion": "acabado", "producto": "KORAZA BLANCO", "presentacion": "galon", "cantidad": 3, "color": "blanco"},
        ],
        "herramientas": [
            {"producto": "RODILLO TOPLINE 9 PULGADAS", "cantidad": 2},
        ],
        "justificacion_tecnica": "Terraza con filtraciones requiere sellado completo y acabado exterior.",
    },
    "validaciones_esperadas": {
        "producto_inventado": True,
        "producto_inventado_nombre": "SELLOMAX ULTRA",
        "debe_bloquear_cotizacion": True,
    },
})

# -----------------------------------------------------------------------
# CASO 10: Pedido simple sin diagnóstico complejo — solo cotizar
# -----------------------------------------------------------------------
CASOS_TEST.append({
    "id": 10,
    "titulo": "Pedido directo — cliente sabe lo que quiere",
    "input_usuario": "Necesito 3 galones de Viniltex Advanced blanco y un rodillo, por favor cotízame.",
    "diagnostico_contexto": {
        "superficie": "muro",
        "material": "estuco",
        "ubicacion": "interior",
        "condicion": "repintura simple",
        "area_m2": 30,
        "problema_principal": "repintura estándar",
    },
    "respuesta_rag": {
        "encontrado": True,
        "respuesta_rag": "Viniltex Advanced para muros interiores.",
        "guia_tecnica_estructurada": {"finish_options": ["Viniltex Advanced"]},
        "diagnostico_estructurado": {"problem_class": "repintura_interior", "pricing_ready": True},
    },
    "json_llm_simulado": {
        "diagnostico": {
            "superficie": "muro",
            "material": "estuco",
            "ubicacion": "interior",
            "condicion": "repintura",
            "area_m2": 30,
            "problema_principal": "repintura estándar",
        },
        "sistema": [
            {"paso": 1, "funcion": "acabado", "producto": "VINILTEX ADVANCED BLANCO", "presentacion": "galon", "cantidad": 3, "color": "blanco"},
        ],
        "herramientas": [
            {"producto": "RODILLO TOPLINE 9 PULGADAS", "cantidad": 1},
        ],
        "justificacion_tecnica": "Pedido directo de Viniltex Advanced para repintura interior.",
    },
    "validaciones_esperadas": {
        "productos_deben_matchear": ["VINILTEX ADVANCED"],
        "herramientas_deben_matchear": ["RODILLO"],
    },
})


# ══════════════════════════════════════════════════════════════════════════════
# MOTOR DE PRUEBAS E2E
# ══════════════════════════════════════════════════════════════════════════════

class ResultadoPrueba:
    def __init__(self, caso_id: int, titulo: str):
        self.caso_id = caso_id
        self.titulo = titulo
        self.pasos = []
        self.resultado_final = "PENDIENTE"
        self.errores_detectados = []
        self.advertencias = []
        self.capa_error = ""  # LLM / backend / validacion / integracion

    def log_paso(self, paso: str, status: str, detalle: str = ""):
        self.pasos.append({"paso": paso, "status": status, "detalle": detalle[:300]})

    def to_report(self) -> str:
        lines = [
            f"\n{'='*70}",
            f"CASO #{self.caso_id}: {self.titulo}",
            f"{'='*70}",
        ]
        for p in self.pasos:
            icon = "✅" if p["status"] == "OK" else "❌" if p["status"] == "ERROR" else "⚠️"
            lines.append(f"  {icon} {p['paso']}: {p['status']}")
            if p["detalle"]:
                lines.append(f"     → {p['detalle']}")

        lines.append(f"\n  RESULTADO: {'✅ ' + self.resultado_final if self.resultado_final == 'OK' else '❌ ' + self.resultado_final}")

        if self.errores_detectados:
            lines.append(f"  ERRORES ({len(self.errores_detectados)}):")
            for e in self.errores_detectados:
                lines.append(f"    ❌ [{e['capa']}] {e['mensaje']}")

        if self.advertencias:
            lines.append(f"  ADVERTENCIAS ({len(self.advertencias)}):")
            for a in self.advertencias:
                lines.append(f"    ⚠️ {a}")

        return "\n".join(lines)


def ejecutar_caso_e2e(caso: dict) -> ResultadoPrueba:
    """Ejecuta un caso de prueba E2E completo a través de todo el pipeline."""
    resultado = ResultadoPrueba(caso["id"], caso["titulo"])
    logger.info("\n%s CASO #%d: %s %s", "="*20, caso["id"], caso["titulo"], "="*20)

    # ═══════════════════════════════════════════════════════════════════
    # PASO 1: Validar schema del JSON "LLM"
    # ═══════════════════════════════════════════════════════════════════
    json_llm = caso["json_llm_simulado"]

    errores_schema = _validar_schema_recomendacion(json_llm)
    if errores_schema:
        resultado.log_paso("1-SCHEMA_LLM", "ERROR", f"Errores: {errores_schema}")
        resultado.errores_detectados.append({
            "capa": "LLM",
            "mensaje": f"Schema inválido: {errores_schema}",
        })
        resultado.resultado_final = "ERROR"
        resultado.capa_error = "LLM"
        return resultado
    resultado.log_paso("1-SCHEMA_LLM", "OK", f"{len(json_llm.get('sistema', []))} productos, {len(json_llm.get('herramientas', []))} herramientas")

    # ═══════════════════════════════════════════════════════════════════
    # PASO 2: Validar trazabilidad RAG
    # ═══════════════════════════════════════════════════════════════════
    no_trazables = _validar_trazabilidad_rag(json_llm, caso["respuesta_rag"])
    if no_trazables:
        resultado.log_paso("2-TRAZABILIDAD_RAG", "WARN", f"Productos no trazables: {no_trazables}")
        resultado.advertencias.append(f"Productos no trazables al RAG: {no_trazables}")
        if caso.get("validaciones_esperadas", {}).get("trazabilidad_debe_fallar"):
            resultado.log_paso("2-TRAZABILIDAD_RAG", "OK", "Correctamente detectó producto no-trazable")
    else:
        resultado.log_paso("2-TRAZABILIDAD_RAG", "OK", "Todos los productos trazables al RAG")

    # ═══════════════════════════════════════════════════════════════════
    # PASO 3: Match contra inventario (BACKEND)
    # ═══════════════════════════════════════════════════════════════════
    match_result = match_sistema_completo(
        recomendacion=json_llm,
        lookup_fn=mock_lookup_fn,
        price_fn=mock_price_fn,
    )

    n_ok = match_result["resumen"]["exitosos"]
    n_fail = match_result["resumen"]["fallidos"]
    n_herr_ok = match_result["resumen"]["herramientas_ok"]
    n_herr_fail = match_result["resumen"]["herramientas_fallidas"]

    resultado.log_paso(
        "3-MATCH_INVENTARIO",
        "OK" if match_result["exito"] else "ERROR",
        f"Productos: {n_ok}/{n_ok+n_fail} OK | Herramientas: {n_herr_ok}/{n_herr_ok+n_herr_fail} OK",
    )

    # Validar tipos de match
    for prod in match_result.get("productos_resueltos", []):
        if prod["tipo_match"] == "fuzzy":
            resultado.advertencias.append(
                f"Match fuzzy (no exacto): '{prod['producto_solicitado']}' → '{prod['descripcion_real']}' (score: {prod['score_match']})"
            )

    # Validar productos fallidos
    for prod_f in match_result.get("productos_fallidos", []):
        resultado.errores_detectados.append({
            "capa": "backend",
            "mensaje": f"Sin match: '{prod_f['producto_solicitado']}' — {prod_f.get('error', '')}",
        })

    # Validar herramientas fallidas
    for herr_f in match_result.get("herramientas_fallidas", []):
        resultado.advertencias.append(
            f"Herramienta sin match: '{herr_f['producto_solicitado']}'"
        )

    # ═══════════════════════════════════════════════════════════════════
    # PASO 4: Validaciones de calidad (GATE)
    # ═══════════════════════════════════════════════════════════════════
    validacion = ejecutar_validacion_completa(json_llm, match_result, caso.get("respuesta_rag"))

    resultado.log_paso(
        "4-VALIDACIONES",
        "OK" if validacion.valido else "BLOQUEADO",
        f"Errores: {len(validacion.errores)} | Advertencias: {len(validacion.advertencias)}",
    )

    for err in validacion.errores:
        resultado.errores_detectados.append({"capa": "validacion", "mensaje": err})
    for adv in validacion.advertencias:
        resultado.advertencias.append(f"[Validación] {adv}")

    # ═══════════════════════════════════════════════════════════════════
    # PASO 5: Generar cotización (SIN LLM — determinístico)
    # ═══════════════════════════════════════════════════════════════════
    if validacion.valido and match_result["exito"]:
        cotizacion_texto = generar_respuesta_cotizacion_whatsapp(
            match_result=match_result,
            diagnostico=json_llm.get("diagnostico", {}),
            justificacion=json_llm.get("justificacion_tecnica", ""),
            nombre_cliente="Cliente Test",
        )
        resultado.log_paso(
            "5-COTIZACION",
            "OK",
            f"Generada ({len(cotizacion_texto)} chars)",
        )

        # Validar que la cotización tenga IVA
        if "$" in cotizacion_texto and "IVA 19%" not in cotizacion_texto and "IVA" not in cotizacion_texto:
            resultado.errores_detectados.append({
                "capa": "generacion",
                "mensaje": "Cotización con precios pero SIN desglose de IVA",
            })

        # Validar que tenga total
        if "TOTAL" not in cotizacion_texto.upper():
            resultado.errores_detectados.append({
                "capa": "generacion",
                "mensaje": "Cotización sin TOTAL",
            })

        # Validar payload PDF
        payload_pdf = generar_payload_pdf(
            match_result=match_result,
            diagnostico=json_llm.get("diagnostico", {}),
            justificacion=json_llm.get("justificacion_tecnica", ""),
            nombre_despacho="Cliente Test",
        )
        if not payload_pdf.get("items"):
            resultado.errores_detectados.append({
                "capa": "generacion",
                "mensaje": "Payload PDF sin items",
            })
        else:
            resultado.log_paso("5-PAYLOAD_PDF", "OK", f"{len(payload_pdf['items'])} items")

    else:
        resultado.log_paso(
            "5-COTIZACION",
            "BLOQUEADA",
            "Validaciones impidieron generar cotización",
        )

    # ═══════════════════════════════════════════════════════════════════
    # PASO 6: Validar expectativas del caso
    # ═══════════════════════════════════════════════════════════════════
    esperadas = caso.get("validaciones_esperadas", {})
    _validar_expectativas(resultado, match_result, validacion, json_llm, esperadas, caso)

    # ═══════════════════════════════════════════════════════════════════
    # RESULTADO FINAL
    # ═══════════════════════════════════════════════════════════════════
    errores_criticos = [e for e in resultado.errores_detectados if e["capa"] in ("LLM", "validacion")]
    errores_backend = [e for e in resultado.errores_detectados if e["capa"] == "backend"]

    # Casos trampa: si detectaron el error esperado → es ÉXITO
    if esperadas.get("debe_detectar_cambio_producto") and any("CAMBIO" in e["mensaje"] for e in resultado.errores_detectados):
        resultado.resultado_final = "OK (Trampa detectada correctamente)"
    elif esperadas.get("bicomponente_incompleto") and any("BICOMPONENTE" in e["mensaje"] for e in resultado.errores_detectados):
        resultado.resultado_final = "OK (Bicomponente incompleto detectado)"
    elif esperadas.get("producto_inventado") and any("sin match fiable" in e["mensaje"].lower() or "sin match" in e["mensaje"].lower() for e in resultado.errores_detectados):
        resultado.resultado_final = "OK (Producto inventado detectado)"
    elif esperadas.get("debe_bloquear_cotizacion") and not validacion.valido:
        resultado.resultado_final = "OK (Cotización bloqueada correctamente)"
    elif errores_criticos:
        resultado.resultado_final = f"ERROR CRÍTICO ({len(errores_criticos)} errores)"
        resultado.capa_error = errores_criticos[0]["capa"]
    elif errores_backend:
        resultado.resultado_final = f"ERROR BACKEND ({len(errores_backend)} errores)"
        resultado.capa_error = "backend"
    else:
        resultado.resultado_final = "OK"

    return resultado


def _validar_expectativas(resultado, match_result, validacion, json_llm, esperadas, caso):
    """Valida expectativas específicas de cada caso."""
    # Productos que deben matchear
    for prod_exp in esperadas.get("productos_deben_matchear", []):
        encontrado = False
        for pr in match_result.get("productos_resueltos", []):
            if prod_exp.lower() in pr.get("descripcion_real", "").lower():
                encontrado = True
                break
        if not encontrado:
            resultado.errores_detectados.append({
                "capa": "backend",
                "mensaje": f"Producto esperado NO encontrado en match: '{prod_exp}'",
            })

    # Herramientas que deben matchear
    for herr_exp in esperadas.get("herramientas_deben_matchear", []):
        encontrado = False
        for hr in match_result.get("herramientas_resueltas", []):
            if herr_exp.lower() in hr.get("descripcion_real", "").lower():
                encontrado = True
                break
        if not encontrado:
            resultado.log_paso(
                "6-EXPECTATIVA_HERRAMIENTA",
                "WARN",
                f"Herramienta esperada no encontrada: '{herr_exp}'",
            )
            resultado.advertencias.append(f"Herramienta esperada no matcheó: '{herr_exp}'")

    # Compatibilidad química
    if esperadas.get("compatibilidad_quimica_ok"):
        val_quimica = validar_compatibilidad_quimica(match_result)
        if not val_quimica.valido:
            resultado.errores_detectados.append({
                "capa": "validacion",
                "mensaje": f"Se esperaba compatibilidad OK pero falló: {val_quimica.errores}",
            })

    # Detección de cambio de producto
    if esperadas.get("debe_detectar_cambio_producto"):
        val_coherencia = validar_coherencia_recomendacion_match(json_llm, match_result, caso.get("respuesta_rag"))
        if val_coherencia.valido:
            # El pipeline NO detectó el cambio → es un fallo del pipeline
            resultado.errores_detectados.append({
                "capa": "validacion",
                "mensaje": f"NO se detectó el cambio de producto esperado: "
                           f"'{esperadas.get('producto_cambiado_de')}' → '{esperadas.get('producto_cambiado_a')}'",
            })


# ══════════════════════════════════════════════════════════════════════════════
# EJECUCIÓN Y REPORTE
# ══════════════════════════════════════════════════════════════════════════════

def ejecutar_todos_los_casos():
    resultados = []
    for caso in CASOS_TEST:
        try:
            r = ejecutar_caso_e2e(caso)
        except Exception as e:
            r = ResultadoPrueba(caso["id"], caso["titulo"])
            r.resultado_final = f"EXCEPCIÓN: {e}"
            r.capa_error = "sistema"
            r.errores_detectados.append({
                "capa": "sistema",
                "mensaje": f"Excepción no controlada: {traceback.format_exc()[:500]}",
            })
        resultados.append(r)

    # ═══════════════════════════════════════════════════════════════════
    # REPORTE FINAL
    # ═══════════════════════════════════════════════════════════════════
    print("\n" + "█" * 70)
    print("█  REPORTE E2E — PIPELINE DETERMINÍSTICO FERREINOX")
    print(f"█  Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("█" * 70)

    for r in resultados:
        print(r.to_report())

    # Resumen
    total = len(resultados)
    ok = sum(1 for r in resultados if "OK" in r.resultado_final)
    errores = total - ok

    print(f"\n{'='*70}")
    print(f"RESUMEN GENERAL")
    print(f"{'='*70}")
    print(f"  Total casos: {total}")
    print(f"  ✅ Exitosos: {ok} ({ok/total*100:.0f}%)")
    print(f"  ❌ Fallidos: {errores} ({errores/total*100:.0f}%)")

    # Clasificación de errores
    todos_errores = []
    for r in resultados:
        for e in r.errores_detectados:
            todos_errores.append({"caso": r.caso_id, **e})

    if todos_errores:
        print(f"\n  ERRORES POR CAPA:")
        capas = {}
        for e in todos_errores:
            capas.setdefault(e["capa"], []).append(e)
        for capa, errs in sorted(capas.items()):
            print(f"    {capa}: {len(errs)} errores")
            for err in errs[:3]:
                print(f"      Caso #{err['caso']}: {err['mensaje'][:100]}")

    # Todas las advertencias
    todas_advertencias = []
    for r in resultados:
        for a in r.advertencias:
            todas_advertencias.append({"caso": r.caso_id, "mensaje": a})

    if todas_advertencias:
        print(f"\n  ADVERTENCIAS TOTALES: {len(todas_advertencias)}")
        for a in todas_advertencias[:10]:
            print(f"    Caso #{a['caso']}: {a['mensaje'][:100]}")

    print(f"\n{'='*70}")
    print(f"DECISIÓN PARA PRODUCCIÓN")
    print(f"{'='*70}")

    if ok == total:
        print("  ✅ LISTO PARA PRODUCCIÓN — Todos los casos pasaron")
    elif ok / total >= 0.8:
        print(f"  ⚠️ CASI LISTO — {ok}/{total} OK, corregir errores restantes antes de deploy")
    else:
        print(f"  ❌ NO LISTO — {errores}/{total} casos fallaron")

    # Listar correcciones necesarias
    casos_fallidos = [r for r in resultados if "OK" not in r.resultado_final]
    if casos_fallidos:
        print(f"\n  CORRECCIONES REQUERIDAS:")
        for r in casos_fallidos:
            print(f"    Caso #{r.caso_id} ({r.titulo}):")
            print(f"      Capa: {r.capa_error}")
            for e in r.errores_detectados[:2]:
                print(f"      → {e['mensaje'][:120]}")

    return resultados


if __name__ == "__main__":
    ejecutar_todos_los_casos()
