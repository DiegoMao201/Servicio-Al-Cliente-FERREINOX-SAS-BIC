#!/usr/bin/env python3
"""
TEST E2E: 3 Casos del Peor Cliente — Pipeline Súper Agente Ferreinox

Simula 3 turnos independientes, cada uno con un escenario difícil:

CASO 1 — "Baño con humedad + cliente dice área, no cantidades"
  → Muro interior baño con salitre, 18 m².
  → LLM debe devolver variables_calculo, NO cantidad.
  → Backend calcula rendimientos reales.
  → Producto esperado: Viniltex Baños y Cocinas → debe matchear "PQ VINILTEX BYC SA".
  → Cotización exitosa con cantidades calculadas.

CASO 2 — "Fachada exterior + bicomponente Pintucoat sin catalizador"
  → Muro exterior fachada deteriorada, 40 m².
  → RAG sugiere Koraza + preparación con Pintucoat.
  → LLM incluye Pintucoat pero NO el Thinner Epóxico → DEBE bloquear.
  → ValidationFeedback debe sugerir: "¿Agrego el catalizador?"
  → suggested_message empático, NO error genérico.

CASO 3 — "Reja metálica + incompatibilidad química provocada"
  → Reja de hierro exterior, 12 m².
  → LLM mezcla Pintulux (alquídico) + Interthane (poliuretano) → INCOMPATIBLES.
  → Pipeline BLOQUEA con feedback de incompatibilidad química.
  → suggested_message debe proponer alternativa compatible.

Cada caso prueba:
  ✓ llm_estructurado: JSON schema, variables_calculo vs cantidad_fija
  ✓ matcher_productos: fuzzy + sinónimos ERP
  ✓ validaciones: 5 gates con ValidationFeedback
  ✓ orquestador: flujo completo, respuesta WhatsApp o bloqueo
  ✓ generador_cotizacion: texto formateado (solo caso 1)
"""
import json
import logging
import sys
import os
import traceback
from unittest.mock import MagicMock, patch
from datetime import datetime

# Agregar backend al path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

from pipeline_deterministico.llm_estructurado import (
    extraer_recomendacion_estructurada,
    resolver_cantidades_desde_variables,
    _validar_schema_recomendacion,
    RENDIMIENTO_BASE,
    FACTOR_SUPERFICIE,
)
from pipeline_deterministico.matcher_productos import (
    match_sistema_completo,
    match_producto_contra_inventario,
    normalizar_texto,
    expandir_sinonimos_erp,
    _calcular_score,
    _get_descripcion,
)
from pipeline_deterministico.validaciones import (
    ejecutar_validacion_completa,
    validar_coherencia_diagnostico,
    validar_completitud_match,
    validar_coherencia_recomendacion_match,
    validar_compatibilidad_quimica,
    validar_bicomponentes,
    ValidationFeedback,
    ResultadoValidacion,
)
from pipeline_deterministico.generador_cotizacion import (
    generar_respuesta_cotizacion_whatsapp,
    generar_payload_pdf,
)
from pipeline_deterministico.orquestador import ejecutar_pipeline_cotizacion

# ══════════════════════════════════════════════════════════════════════════════
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("test_super_agente")

# ══════════════════════════════════════════════════════════════════════════════
# INVENTARIO SIMULADO — Refleja el catálogo ERP Ferreinox real
# ══════════════════════════════════════════════════════════════════════════════

INVENTARIO_SIMULADO = [
    # ── Viniltex Baños y Cocinas ──
    {"codigo_articulo": "2001", "descripcion": "PQ VINILTEX BYC SA BLANCO 2001 3.79L",
     "descripcion_comercial": "Viniltex Baños y Cocinas Blanco Galón",
     "marca": "Pintuco", "presentacion": "galon", "precio_venta": 89900,
     "stock_total": 25, "unidad_medida": "3.79L"},
    {"codigo_articulo": "2002", "descripcion": "PQ VINILTEX BYC SA BLANCO 2001 18.93L",
     "descripcion_comercial": "Viniltex Baños y Cocinas Blanco Cuñete",
     "marca": "Pintuco", "presentacion": "cunete", "precio_venta": 399900,
     "stock_total": 8, "unidad_medida": "18.93L"},

    # ── Viniltex Advanced ──
    {"codigo_articulo": "2010", "descripcion": "PQ VINILTEX ADV SA BLANCO 2010 3.79L",
     "descripcion_comercial": "Viniltex Advanced Blanco Galón",
     "marca": "Pintuco", "presentacion": "galon", "precio_venta": 109900,
     "stock_total": 30, "unidad_medida": "3.79L"},

    # ── Koraza ──
    {"codigo_articulo": "3001", "descripcion": "PQ KORAZA SA BLANCO 3001 3.79L",
     "descripcion_comercial": "Koraza Blanco Galón",
     "marca": "Pintuco", "presentacion": "galon", "precio_venta": 119900,
     "stock_total": 15, "unidad_medida": "3.79L"},
    {"codigo_articulo": "3002", "descripcion": "PQ KORAZA SA BLANCO 3001 18.93L",
     "descripcion_comercial": "Koraza Blanco Cuñete",
     "marca": "Pintuco", "presentacion": "cunete", "precio_venta": 529900,
     "stock_total": 5, "unidad_medida": "18.93L"},

    # ── Aquablock ──
    {"codigo_articulo": "4001", "descripcion": "PQ AQUABLOCK ULTRA SA BLANCO 4001 3.79L",
     "descripcion_comercial": "Aquablock Ultra Blanco Galón",
     "marca": "Pintuco", "presentacion": "galon", "precio_venta": 129900,
     "stock_total": 12, "unidad_medida": "3.79L"},

    # ── Estuco ──
    {"codigo_articulo": "5001", "descripcion": "ESTUCO PROF ACRILICO EXT SA BLANCO 5001 3.79L",
     "descripcion_comercial": "Estuco Acrílico Profesional Exterior Blanco Galón",
     "marca": "Pintuco", "presentacion": "galon", "precio_venta": 49900,
     "stock_total": 20, "unidad_medida": "3.79L"},

    # ── Sellador ──
    {"codigo_articulo": "5010", "descripcion": "SELLADOR PROF ACRILICO SA 5010 3.79L",
     "descripcion_comercial": "Sellador Profesional Acrílico Galón",
     "marca": "Pintuco", "presentacion": "galon", "precio_venta": 39900,
     "stock_total": 18, "unidad_medida": "3.79L"},

    # ── Pintucoat Epóxico ──
    {"codigo_articulo": "6001", "descripcion": "PINTUCOAT EPOXICO SA GRIS 6001 3.79L",
     "descripcion_comercial": "Pintucoat Epóxico Gris Galón",
     "marca": "Pintuco", "presentacion": "galon", "precio_venta": 189900,
     "stock_total": 6, "unidad_medida": "3.79L"},

    # ── Thinner Epóxico (catalizador Pintucoat) ──
    {"codigo_articulo": "6010", "descripcion": "THINNER EPOXICO 6010 3.79L",
     "descripcion_comercial": "Thinner Epóxico Galón",
     "marca": "Pintuco", "presentacion": "galon", "precio_venta": 59900,
     "stock_total": 10, "unidad_medida": "3.79L"},

    # ── Pintulux (Alquídico) ──
    {"codigo_articulo": "7001", "descripcion": "PINTULUX PROF SA BLANCO 7001 3.79L",
     "descripcion_comercial": "Pintulux Profesional Blanco Galón",
     "marca": "Pintuco", "presentacion": "galon", "precio_venta": 79900,
     "stock_total": 14, "unidad_medida": "3.79L"},

    # ── Interthane 990 (Poliuretano) ──
    {"codigo_articulo": "8001", "descripcion": "INTERTHANE 990 SA GRIS 8001 3.79L",
     "descripcion_comercial": "Interthane 990 Gris Galón",
     "marca": "International", "presentacion": "galon", "precio_venta": 289900,
     "stock_total": 4, "unidad_medida": "3.79L"},

    # ── Anticorrosivo ──
    {"codigo_articulo": "7010", "descripcion": "CORROTEC ANTICORROSIVO GRIS 7010 3.79L",
     "descripcion_comercial": "Corrotec Anticorrosivo Gris Galón",
     "marca": "Pintuco", "presentacion": "galon", "precio_venta": 69900,
     "stock_total": 10, "unidad_medida": "3.79L"},

    # ── Lija ──
    {"codigo_articulo": "9001", "descripcion": "LIJA ABRACOL GRANO 80 9001",
     "descripcion_comercial": "Lija Abracol Grano 80",
     "marca": "Abracol", "presentacion": "unidad", "precio_venta": 2500,
     "stock_total": 200, "unidad_medida": "UND"},
    {"codigo_articulo": "9002", "descripcion": "LIJA ABRACOL GRANO 150 9002",
     "descripcion_comercial": "Lija Abracol Grano 150",
     "marca": "Abracol", "presentacion": "unidad", "precio_venta": 2500,
     "stock_total": 150, "unidad_medida": "UND"},

    # ── Rodillo y Brocha ──
    {"codigo_articulo": "9010", "descripcion": "RODILLO TOPLINE 9 PULGADAS 9010",
     "descripcion_comercial": "Rodillo Topline 9 Pulgadas",
     "marca": "Topline", "presentacion": "unidad", "precio_venta": 18900,
     "stock_total": 30, "unidad_medida": "UND"},
    {"codigo_articulo": "9011", "descripcion": "BROCHA GOYA PROF 3 PULGADAS 9011",
     "descripcion_comercial": "Brocha Goya Profesional 3 Pulgadas",
     "marca": "Goya", "presentacion": "unidad", "precio_venta": 12900,
     "stock_total": 25, "unidad_medida": "UND"},
]


def lookup_inventario_simulado(texto_busqueda: str) -> list[dict]:
    """Simula búsqueda en inventario. Busca por tokens en descripción."""
    texto_norm = normalizar_texto(texto_busqueda)
    tokens = [t for t in texto_norm.split() if len(t) > 2]
    if not tokens:
        return []

    resultados = []
    for prod in INVENTARIO_SIMULADO:
        desc_norm = normalizar_texto(
            prod.get("descripcion", "") + " " + prod.get("descripcion_comercial", "")
        )
        # Contar cuántos tokens del query aparecen en la descripción
        matches = sum(1 for t in tokens if t in desc_norm)
        if matches > 0:
            prod_copy = dict(prod)
            prod_copy["_match_tokens"] = matches
            prod_copy["_match_ratio"] = matches / len(tokens)
            resultados.append(prod_copy)

    # Ordenar por relevancia
    resultados.sort(key=lambda x: x["_match_ratio"], reverse=True)
    return resultados[:15]


def price_fn_simulado(codigo: str) -> dict:
    """Simula obtención de precio por código."""
    for prod in INVENTARIO_SIMULADO:
        if prod["codigo_articulo"] == str(codigo):
            return {"precio_mejor": prod["precio_venta"]}
    return {}


# ══════════════════════════════════════════════════════════════════════════════
# MOCK LLM — Respuestas predefinidas para cada caso
# ══════════════════════════════════════════════════════════════════════════════

# CASO 1: Baño con humedad, 18 m², cliente da área no cantidades
# RAG sugiere: Aquablock + Estuco + Viniltex Baños y Cocinas
MOCK_LLM_CASO_1 = {
    "diagnostico": {
        "superficie": "muro",
        "material": "estuco",
        "ubicacion": "interior",
        "condicion": "humedad con salitre en zona de baño",
        "area_m2": 18,
        "problema_principal": "humedad ascendente por capilaridad en baño"
    },
    "sistema": [
        {
            "paso": 1, "funcion": "preparacion",
            "producto": "LIJA ABRACOL GRANO 80",
            "presentacion": "unidad", "cantidad_fija": 4
        },
        {
            "paso": 2, "funcion": "sellador",
            "producto": "AQUABLOCK ULTRA",
            "presentacion": "galon",
            "variables_calculo": {"area_m2": 18, "tipo_superficie": "porosa", "manos": 2},
            "color": "blanco"
        },
        {
            "paso": 3, "funcion": "base",
            "producto": "ESTUCO ACRILICO PROFESIONAL EXTERIOR",
            "presentacion": "galon",
            "variables_calculo": {"area_m2": 18, "tipo_superficie": "porosa", "manos": 1},
            "color": "blanco"
        },
        {
            "paso": 4, "funcion": "acabado",
            "producto": "VINILTEX BAÑOS Y COCINAS",
            "presentacion": "galon",
            "variables_calculo": {"area_m2": 18, "tipo_superficie": "sellada", "manos": 2},
            "color": "blanco"
        }
    ],
    "herramientas": [
        {"producto": "RODILLO TOPLINE 9 PULGADAS", "cantidad": 1},
        {"producto": "BROCHA GOYA PROFESIONAL 3 PULGADAS", "cantidad": 1}
    ],
    "justificacion_tecnica": (
        "Muro interior de baño con humedad ascendente y salitre. "
        "Sistema: 1) Lijar salitre. 2) Aquablock Ultra como sellador impermeabilizante "
        "(apto concreto con humedad). 3) Estuco acrílico exterior para nivelar. "
        "4) Viniltex Baños y Cocinas como acabado — resistente a humedad y moho."
    ),
}

# CASO 2: Fachada exterior + Pintucoat SIN catalizador (debe bloquear)
# RAG sugiere: Koraza + Pintucoat como sellador de fachada industrial
MOCK_LLM_CASO_2 = {
    "diagnostico": {
        "superficie": "muro",
        "material": "concreto",
        "ubicacion": "exterior",
        "condicion": "fachada deteriorada con eflorescencia y grietas",
        "area_m2": 40,
        "problema_principal": "degradación por intemperie en fachada comercial"
    },
    "sistema": [
        {
            "paso": 1, "funcion": "preparacion",
            "producto": "LIJA ABRACOL GRANO 150",
            "presentacion": "unidad", "cantidad_fija": 6
        },
        {
            "paso": 2, "funcion": "sellador",
            "producto": "PINTUCOAT EPOXICO",
            "presentacion": "galon",
            "variables_calculo": {"area_m2": 40, "tipo_superficie": "concreto", "manos": 1},
            "color": "gris"
        },
        # ⚠️ FALTA el Thinner Epóxico (catalizador del Pintucoat)
        {
            "paso": 3, "funcion": "acabado",
            "producto": "KORAZA",
            "presentacion": "galon",
            "variables_calculo": {"area_m2": 40, "tipo_superficie": "sellada", "manos": 2},
            "color": "blanco"
        }
    ],
    "herramientas": [
        {"producto": "RODILLO TOPLINE 9 PULGADAS", "cantidad": 2},
        {"producto": "BROCHA GOYA PROFESIONAL 3 PULGADAS", "cantidad": 1}
    ],
    "justificacion_tecnica": (
        "Fachada exterior comercial con deterioro severo. "
        "1) Lijar eflorescencia. 2) Pintucoat Epóxico como sellador base — "
        "protección industrial. 3) Koraza como acabado exterior premium."
    ),
}

# CASO 3: Reja metálica + incompatibilidad Pintulux (alquídico) + Interthane (PU)
MOCK_LLM_CASO_3 = {
    "diagnostico": {
        "superficie": "metal",
        "material": "hierro",
        "ubicacion": "exterior",
        "condicion": "oxidación moderada en reja metálica",
        "area_m2": 12,
        "problema_principal": "corrosión y descascaramiento en reja exterior"
    },
    "sistema": [
        {
            "paso": 1, "funcion": "preparacion",
            "producto": "LIJA ABRACOL GRANO 80",
            "presentacion": "unidad", "cantidad_fija": 5
        },
        {
            "paso": 2, "funcion": "imprimante",
            "producto": "CORROTEC ANTICORROSIVO",
            "presentacion": "galon",
            "variables_calculo": {"area_m2": 12, "tipo_superficie": "metal", "manos": 1},
            "color": "gris"
        },
        {
            "paso": 3, "funcion": "base",
            "producto": "PINTULUX PROFESIONAL",  # ⚠️ ALQUÍDICO
            "presentacion": "galon",
            "variables_calculo": {"area_m2": 12, "tipo_superficie": "metal", "manos": 1},
            "color": "blanco"
        },
        {
            "paso": 4, "funcion": "acabado",
            "producto": "INTERTHANE 990",  # ⚠️ POLIURETANO — INCOMPATIBLE con alquídico
            "presentacion": "galon",
            "variables_calculo": {"area_m2": 12, "tipo_superficie": "metal", "manos": 2},
            "color": "gris"
        }
    ],
    "herramientas": [
        {"producto": "BROCHA GOYA PROFESIONAL 3 PULGADAS", "cantidad": 2}
    ],
    "justificacion_tecnica": (
        "Reja metálica exterior con oxidación. "
        "1) Lijar óxido. 2) Corrotec anticorrosivo como imprimante. "
        "3) Pintulux como base de color. 4) Interthane 990 como acabado de alta durabilidad."
    ),
}

# RAGs simulados
RAG_CASO_1 = {
    "respuesta_rag": (
        "Para un muro interior de baño con humedad ascendente y salitre, se recomienda:\n"
        "1. Lijar el salitre con LIJA ABRACOL GRANO 80\n"
        "2. Aplicar AQUABLOCK ULTRA como sellador impermeabilizante (2 manos)\n"
        "3. Nivelar con ESTUCO ACRILICO PROFESIONAL EXTERIOR (1 mano)\n"
        "4. Acabado con VINILTEX BAÑOS Y COCINAS — resistente a humedad y moho\n"
        "Herramientas: Rodillo Topline 9 pulgadas, Brocha Goya Profesional 3 pulgadas"
    ),
    "guia_tecnica_estructurada": {
        "base_or_primer": ["AQUABLOCK ULTRA"],
        "intermediate_steps": ["ESTUCO ACRILICO PROFESIONAL EXTERIOR"],
        "finish_options": ["VINILTEX BAÑOS Y COCINAS"],
    },
}

RAG_CASO_2 = {
    "respuesta_rag": (
        "Fachada exterior con deterioro severo, se recomienda sistema epóxico + acrílico:\n"
        "1. Lijar eflorescencia con LIJA ABRACOL GRANO 150\n"
        "2. Sellar con PINTUCOAT EPOXICO (requiere THINNER EPOXICO como catalizador)\n"
        "3. Acabado con KORAZA — máxima protección exterior\n"
        "IMPORTANTE: Pintucoat es bicomponente, NO funciona sin su catalizador."
    ),
    "guia_tecnica_estructurada": {
        "base_or_primer": ["PINTUCOAT EPOXICO"],
        "intermediate_steps": [],
        "finish_options": ["KORAZA"],
    },
}

RAG_CASO_3 = {
    "respuesta_rag": (
        "Reja metálica exterior con oxidación moderada:\n"
        "1. Lijar óxido con LIJA ABRACOL GRANO 80\n"
        "2. Aplicar CORROTEC ANTICORROSIVO como imprimante\n"
        "3. Acabado con PINTULUX PROFESIONAL o INTERTHANE 990\n"
        "NOTA: No mezclar alquídicos con poliuretanos — son incompatibles."
    ),
    "guia_tecnica_estructurada": {
        "base_or_primer": ["CORROTEC ANTICORROSIVO"],
        "intermediate_steps": [],
        "finish_options": ["PINTULUX PROFESIONAL", "INTERTHANE 990"],
    },
}


# ══════════════════════════════════════════════════════════════════════════════
# MOCK OPENAI CLIENT
# ══════════════════════════════════════════════════════════════════════════════

class MockOpenAIResponse:
    def __init__(self, content):
        self.choices = [MagicMock()]
        self.choices[0].message.content = json.dumps(content, ensure_ascii=False)


class MockOpenAIClient:
    def __init__(self):
        self.chat = MagicMock()
        self._responses = []
        self._call_idx = 0

    def set_response(self, data: dict):
        """Set next LLM response."""
        self._responses = [data]
        self._call_idx = 0
        self.chat.completions.create = MagicMock(
            return_value=MockOpenAIResponse(data)
        )


# ══════════════════════════════════════════════════════════════════════════════
# TEST RUNNER
# ══════════════════════════════════════════════════════════════════════════════

class TestResult:
    def __init__(self, caso: str):
        self.caso = caso
        self.checks: list[tuple[str, bool, str]] = []  # (nombre, pasó, detalle)

    def check(self, nombre: str, condicion: bool, detalle: str = ""):
        self.checks.append((nombre, condicion, detalle))
        status = "✅" if condicion else "❌"
        logger.info("  %s %s%s", status, nombre, f" — {detalle}" if detalle else "")

    @property
    def passed(self) -> int:
        return sum(1 for _, ok, _ in self.checks if ok)

    @property
    def failed(self) -> int:
        return sum(1 for _, ok, _ in self.checks if not ok)

    @property
    def total(self) -> int:
        return len(self.checks)


def run_pipeline_with_mock(mock_llm_response, rag, user_message, caso_name):
    """Ejecuta el pipeline completo con LLM mockeado."""
    client = MockOpenAIClient()
    client.set_response(mock_llm_response)

    resultado = ejecutar_pipeline_cotizacion(
        openai_client=client,
        modelo="gpt-4o-mini",
        diagnostico_contexto=mock_llm_response["diagnostico"],
        respuesta_rag=rag,
        user_message=user_message,
        conversation_id=f"test_{caso_name}",
        lookup_fn=lookup_inventario_simulado,
        price_fn=price_fn_simulado,
        nombre_cliente="Don Pedro (Test)",
        perfil_tecnico=None,
        guias_tecnicas=None,
    )
    return resultado


# ══════════════════════════════════════════════════════════════════════════════
# CASO 1: Baño con humedad — variables_calculo → cotización exitosa
# ══════════════════════════════════════════════════════════════════════════════

def test_caso_1():
    logger.info("\n" + "=" * 80)
    logger.info("CASO 1: Baño con humedad, 18 m² — variables_calculo → cotización")
    logger.info("=" * 80)
    t = TestResult("caso_1")

    # ── 1A: Verificar resolver_cantidades_desde_variables ──
    logger.info("\n── 1A: Resolución de cantidades desde variables_calculo ──")
    recomendacion = json.loads(json.dumps(MOCK_LLM_CASO_1))
    recomendacion_resuelta = resolver_cantidades_desde_variables(recomendacion)

    for item in recomendacion_resuelta["sistema"]:
        prod = item.get("producto", "")
        cant = item.get("cantidad", 0)
        fuente = item.get("_fuente_cantidad", "")
        pres = item.get("presentacion", "")
        logger.info("    %s: %d %s (fuente: %s)", prod, cant, pres, fuente)
        if item.get("variables_calculo"):
            t.check(
                f"variables_calculo resuelto: {prod}",
                cant > 0 and fuente == "variables_calculo",
                f"cantidad={cant}, fuente={fuente}",
            )
        elif item.get("cantidad_fija"):
            t.check(
                f"cantidad_fija OK: {prod}",
                fuente == "cantidad_fija",
                f"cantidad={cant}",
            )

    # Verificar cálculos específicos
    # Aquablock: 18m² / (5/1.5) * 2 manos = 18/3.33 * 2 ≈ 11 gal → cuñete + 1 gal
    # Viniltex BYC: 18m² / (12/1.0) * 2 manos = 18/12 * 2 = 3 gal → 3 galones
    acabado = [i for i in recomendacion_resuelta["sistema"] if i.get("funcion") == "acabado"][0]
    t.check(
        "Viniltex BYC cantidad razonable (18m²/12rend*2manos=3gal)",
        1 <= acabado["cantidad"] <= 5,
        f"cantidad={acabado['cantidad']}",
    )

    # ── 1B: Schema validation ──
    logger.info("\n── 1B: Validación de schema ──")
    errores_schema = _validar_schema_recomendacion(MOCK_LLM_CASO_1)
    t.check("Schema LLM válido", len(errores_schema) == 0, str(errores_schema) if errores_schema else "OK")

    # ── 1C: Match de productos ──
    logger.info("\n── 1C: Match contra inventario ──")
    match_result = match_sistema_completo(
        recomendacion=recomendacion_resuelta,
        lookup_fn=lookup_inventario_simulado,
        price_fn=price_fn_simulado,
    )

    t.check("Match global exitoso", match_result["exito"], str(match_result.get("razon_fallo", "")))

    for pr in match_result["productos_resueltos"]:
        sol = pr["producto_solicitado"]
        real = pr["descripcion_real"]
        score = pr["score_match"]
        logger.info("    MATCH: '%s' → '%s' (score=%.3f)", sol, real, score)

    # ── Verificar que Viniltex BYC matcheó correctamente ──
    byc_matches = [
        p for p in match_result["productos_resueltos"]
        if "baños" in p["producto_solicitado"].lower() or "byc" in p["producto_solicitado"].lower()
    ]
    if byc_matches:
        byc = byc_matches[0]
        t.check(
            "Viniltex BYC → PQ VINILTEX BYC (sinónimo ERP)",
            "byc" in byc["descripcion_real"].lower() or "baños" in byc["descripcion_real"].lower(),
            f"→ {byc['descripcion_real']}",
        )
        t.check("BYC precio > 0", byc["precio_unitario"] > 0, f"${byc['precio_unitario']:,.0f}")
        t.check("BYC disponible", byc.get("disponible", False))
    else:
        t.check("Viniltex BYC encontrado en resueltos", False, "NO encontrado en resueltos")

    for pf in match_result["productos_fallidos"]:
        logger.info("    FALLIDO: '%s' — %s", pf["producto_solicitado"], pf.get("error", ""))

    t.check(
        "Sin productos fallidos críticos",
        len(match_result["productos_fallidos"]) == 0
        or not any(
            p.get("funcion") in ("acabado", "sellador", "base")
            for p in match_result["productos_fallidos"]
        ),
        f"fallidos: {[p['producto_solicitado'] for p in match_result['productos_fallidos']]}",
    )

    # ── 1D: Validaciones ──
    logger.info("\n── 1D: Validaciones ──")
    validacion = ejecutar_validacion_completa(recomendacion_resuelta, match_result, RAG_CASO_1)
    t.check("Validación aprobada", validacion.valido, str(validacion.errores[:3]) if validacion.errores else "OK")

    if validacion.advertencias:
        for adv in validacion.advertencias:
            logger.info("    ⚠️ %s", adv)

    if validacion.feedbacks:
        for fb in validacion.feedbacks:
            d = fb.to_dict()
            logger.info("    📋 Feedback: %s/%s — %s", d["status"], d["reason"], d.get("suggested_message", "")[:80])

    # ── 1E: Pipeline completo ──
    logger.info("\n── 1E: Pipeline orquestador completo ──")
    resultado = run_pipeline_with_mock(MOCK_LLM_CASO_1, RAG_CASO_1, 
        "Necesito pintar el baño, tiene humedad con salitre, son como 18 metros cuadrados", 
        "caso_1")

    t.check("Pipeline exitoso", resultado["exito"], str(resultado.get("validacion", {}).get("errores", []))[:200])

    if resultado["exito"]:
        wa = resultado["respuesta_whatsapp"]
        logger.info("\n── RESPUESTA WHATSAPP ──")
        for line in wa.split("\n")[:20]:
            logger.info("    %s", line)

        t.check("Respuesta tiene $", "$" in wa, "Precios incluidos")
        t.check("Respuesta tiene subtotal o total", 
                any(k in wa.lower() for k in ["subtotal", "total", "iva"]),
                "Desglose de totales")
        t.check("Payload PDF generado", resultado["payload_pdf"] is not None)

    return t


# ══════════════════════════════════════════════════════════════════════════════
# CASO 2: Fachada + bicomponente sin catalizador → bloqueo + feedback
# ══════════════════════════════════════════════════════════════════════════════

def test_caso_2():
    logger.info("\n" + "=" * 80)
    logger.info("CASO 2: Fachada exterior — Pintucoat SIN catalizador → bloqueo")
    logger.info("=" * 80)
    t = TestResult("caso_2")

    # ── 2A: Resolver cantidades ──
    logger.info("\n── 2A: Resolución de cantidades ──")
    recomendacion = json.loads(json.dumps(MOCK_LLM_CASO_2))
    recomendacion_resuelta = resolver_cantidades_desde_variables(recomendacion)

    for item in recomendacion_resuelta["sistema"]:
        prod = item.get("producto", "")
        cant = item.get("cantidad", 0)
        pres = item.get("presentacion", "")
        logger.info("    %s: %d %s", prod, cant, pres)

    # ── 2B: Match ──
    logger.info("\n── 2B: Match contra inventario ──")
    match_result = match_sistema_completo(
        recomendacion=recomendacion_resuelta,
        lookup_fn=lookup_inventario_simulado,
        price_fn=price_fn_simulado,
    )

    for pr in match_result["productos_resueltos"]:
        logger.info("    MATCH: '%s' → '%s' (score=%.3f)", 
                     pr["producto_solicitado"], pr["descripcion_real"], pr["score_match"])

    t.check(
        "Pintucoat matcheó",
        any("pintucoat" in p["descripcion_real"].lower() for p in match_result["productos_resueltos"]),
    )
    t.check(
        "Koraza matcheó",
        any("koraza" in p["descripcion_real"].lower() for p in match_result["productos_resueltos"]),
    )

    # ── 2C: Validación de bicomponentes → DEBE BLOQUEAR ──
    logger.info("\n── 2C: Validación bicomponentes ──")
    val_bico = validar_bicomponentes(match_result)
    t.check(
        "Gate bicomponentes BLOQUEA (falta catalizador)",
        not val_bico.valido,
        str(val_bico.errores[:2]) if val_bico.errores else "NO BLOQUEÓ (ERROR!)",
    )

    if val_bico.feedbacks:
        fb = val_bico.feedbacks[0].to_dict()
        t.check(
            "Feedback es 'missing_catalyst'",
            fb.get("reason") == "missing_catalyst",
            fb.get("reason", "?"),
        )
        t.check(
            "suggested_message menciona catalizador",
            "catalizador" in fb.get("suggested_message", "").lower()
            or "thinner" in fb.get("suggested_message", "").lower(),
            fb.get("suggested_message", "")[:100],
        )
        t.check(
            "suggested_action es 'add_catalyst'",
            fb.get("suggested_action") == "add_catalyst",
        )
        logger.info("    💬 suggested_message: %s", fb.get("suggested_message", ""))
    else:
        t.check("ValidationFeedback generado", False, "No se generó feedback")

    # ── 2D: Pipeline completo → DEBE BLOQUEAR ──
    logger.info("\n── 2D: Pipeline completo ──")
    resultado = run_pipeline_with_mock(MOCK_LLM_CASO_2, RAG_CASO_2,
        "Necesito renovar la fachada del local, tiene grietas y se ve feo, son 40 metros",
        "caso_2")

    t.check("Pipeline NO exitoso (bloqueado)", not resultado["exito"])
    t.check(
        "bloqueado_por_validacion=True",
        resultado.get("bloqueado_por_validacion", False),
    )
    t.check(
        "suggested_message presente",
        bool(resultado.get("suggested_message")),
        resultado.get("suggested_message", "")[:100],
    )
    t.check(
        "feedbacks en resultado",
        len(resultado.get("feedbacks", [])) > 0,
        f"{len(resultado.get('feedbacks', []))} feedbacks",
    )

    wa = resultado.get("respuesta_whatsapp", "")
    logger.info("\n── RESPUESTA WHATSAPP (bloqueo empático) ──")
    for line in wa.split("\n"):
        logger.info("    %s", line)

    t.check(
        "Respuesta WhatsApp es empática (no error genérico)",
        "catalizador" in wa.lower() or "thinner" in wa.lower() or "agrego" in wa.lower(),
        wa[:120],
    )

    return t


# ══════════════════════════════════════════════════════════════════════════════
# CASO 3: Reja metálica + incompatibilidad química → bloqueo
# ══════════════════════════════════════════════════════════════════════════════

def test_caso_3():
    logger.info("\n" + "=" * 80)
    logger.info("CASO 3: Reja metálica — Pintulux + Interthane = INCOMPATIBLES")
    logger.info("=" * 80)
    t = TestResult("caso_3")

    # ── 3A: Cantidades ──
    logger.info("\n── 3A: Resolución de cantidades (12 m² metal) ──")
    recomendacion = json.loads(json.dumps(MOCK_LLM_CASO_3))
    recomendacion_resuelta = resolver_cantidades_desde_variables(recomendacion)

    for item in recomendacion_resuelta["sistema"]:
        prod = item.get("producto", "")
        cant = item.get("cantidad", 0)
        pres = item.get("presentacion", "")
        logger.info("    %s: %d %s", prod, cant, pres)

    # Metal factor = 0.9, Corrotec rendimiento = 10
    # Corrotec: 12/(10/0.9)*1 = 12/11.1 = 1.08 → 2 gal
    corrotec = [i for i in recomendacion_resuelta["sistema"] if "corrotec" in i.get("producto", "").lower()]
    if corrotec:
        t.check("Corrotec cantidad razonable (12m² metal)", 
                1 <= corrotec[0]["cantidad"] <= 3,
                f"cantidad={corrotec[0]['cantidad']}")

    # ── 3B: Match ──
    logger.info("\n── 3B: Match contra inventario ──")
    match_result = match_sistema_completo(
        recomendacion=recomendacion_resuelta,
        lookup_fn=lookup_inventario_simulado,
        price_fn=price_fn_simulado,
    )

    for pr in match_result["productos_resueltos"]:
        logger.info("    MATCH: '%s' → '%s' (score=%.3f)",
                     pr["producto_solicitado"], pr["descripcion_real"], pr["score_match"])

    t.check("Pintulux matcheó", 
            any("pintulux" in p["descripcion_real"].lower() for p in match_result["productos_resueltos"]))
    t.check("Interthane matcheó",
            any("interthane" in p["descripcion_real"].lower() for p in match_result["productos_resueltos"]))
    t.check("Corrotec matcheó",
            any("corrotec" in p["descripcion_real"].lower() for p in match_result["productos_resueltos"]))

    # ── 3C: Validación química → DEBE BLOQUEAR ──
    logger.info("\n── 3C: Validación compatibilidad química ──")
    val_quim = validar_compatibilidad_quimica(match_result)
    t.check(
        "Gate químico BLOQUEA (alquídico + poliuretano)",
        not val_quim.valido,
        str(val_quim.errores[:2]) if val_quim.errores else "NO BLOQUEÓ (ERROR!)",
    )

    if val_quim.feedbacks:
        fb = val_quim.feedbacks[0].to_dict()
        t.check(
            "Feedback es 'chemical_incompatibility'",
            fb.get("reason") == "chemical_incompatibility",
            fb.get("reason", "?"),
        )
        t.check(
            "suggested_message menciona incompatibilidad",
            "compatib" in fb.get("suggested_message", "").lower()
            or "incompatib" in fb.get("suggested_message", "").lower(),
            fb.get("suggested_message", "")[:100],
        )
        logger.info("    💬 suggested_message: %s", fb.get("suggested_message", ""))
    else:
        t.check("ValidationFeedback generado", False, "No se generó feedback")

    # ── 3D: También debe detectar falta de catalizador Interthane ──
    logger.info("\n── 3D: También debe bloquear por bicomponente Interthane ──")
    val_bico = validar_bicomponentes(match_result)
    t.check(
        "Gate bicomponentes BLOQUEA (Interthane sin UFA151)",
        not val_bico.valido,
        str(val_bico.errores[:2]) if val_bico.errores else "NO BLOQUEÓ",
    )

    # ── 3E: Pipeline completo → DEBE BLOQUEAR (múltiples razones) ──
    logger.info("\n── 3E: Pipeline completo ──")
    resultado = run_pipeline_with_mock(MOCK_LLM_CASO_3, RAG_CASO_3,
        "Necesito pintar la reja del frente, está toda oxidada, son unos 12 metros",
        "caso_3")

    t.check("Pipeline NO exitoso", not resultado["exito"])
    t.check("bloqueado_por_validacion", resultado.get("bloqueado_por_validacion", False))

    feedbacks = resultado.get("feedbacks", [])
    blocking = [f for f in feedbacks if f.get("status") == "blocked"]
    t.check(
        "Múltiples feedbacks bloqueantes (químico + bicomponente)",
        len(blocking) >= 2,
        f"{len(blocking)} feedbacks bloqueantes",
    )

    reasons = {f.get("reason") for f in blocking}
    t.check("chemical_incompatibility en razones", "chemical_incompatibility" in reasons, str(reasons))
    t.check("missing_catalyst en razones", "missing_catalyst" in reasons, str(reasons))

    wa = resultado.get("respuesta_whatsapp", "")
    logger.info("\n── RESPUESTA WHATSAPP (bloqueo empático) ──")
    for line in wa.split("\n"):
        logger.info("    %s", line)

    t.check("Respuesta NO es error genérico",
            "compatible" in wa.lower() or "catalizador" in wa.lower() or "thinner" in wa.lower(),
            wa[:150])

    return t


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    print("\n" + "=" * 80)
    print("  TEST SUPER AGENTE -- 3 Casos del Peor Cliente")
    print("  Pipeline E2E: LLM > Match > Validacion > Cotizacion")
    print("=" * 80 + "\n")

    resultados = []
    for test_fn in [test_caso_1, test_caso_2, test_caso_3]:
        try:
            r = test_fn()
            resultados.append(r)
        except Exception as e:
            logger.error("💥 CRASH en %s: %s", test_fn.__name__, e)
            traceback.print_exc()
            r = TestResult(test_fn.__name__)
            r.check("Test ejecutó sin crash", False, str(e)[:200])
            resultados.append(r)

    # ══════════════════════════════════════════════════════════════════════
    # RESUMEN FINAL
    # ══════════════════════════════════════════════════════════════════════
    print("\n" + "=" * 80)
    print("  RESUMEN FINAL DE RESULTADOS")
    print("=" * 80)

    total_passed = 0
    total_failed = 0

    for r in resultados:
        total_passed += r.passed
        total_failed += r.failed
        status = "PASS" if r.failed == 0 else "FAIL"
        print(f"\n  {status} -- {r.caso.upper()}: {r.passed}/{r.total} checks")
        if r.failed > 0:
            for nombre, ok, detalle in r.checks:
                if not ok:
                    print(f"    FAIL: {nombre}: {detalle}")

    total = total_passed + total_failed
    print(f"\n{'=' * 80}")
    print(f"  TOTAL: {total_passed}/{total} checks pasaron")
    if total_failed > 0:
        print(f"  WARNING: {total_failed} checks FALLARON")
    else:
        print(f"  OK: TODOS LOS CHECKS PASARON")
    print(f"{'=' * 80}\n")

    return total_failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
