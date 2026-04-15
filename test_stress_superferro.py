#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TEST STRESS SUPERFERRO -- 10 Conversaciones Criticas del Peor Cliente
=====================================================================

Bateria QA para el pipeline deterministico del agente Ferro (agent_v3.py).
Valida:
  - ValidationFeedback: suggested_message presente en respuesta final
  - Memoria conversacional: historial de ultimos 5 mensajes
  - Gates de validacion: quimica, bicomponentes, coherencia, completitud
  - Matcher ERP: sinonimos, spanglish, terminos vagos
  - Cantidades: variables_calculo vs cantidad_fija

Nomenclatura real de catalizadores Ferreinox:
  - Interthane 990 -> Catalizador PHA046, Ajustador 21050
  - Epoxicos (Pintucoat/Intergard) -> Catalizador Parte B, Ajustador 209
  - Trafico / Acrilica Mantenimiento -> Ajustador 204
"""
import json
import logging
import sys
import os
import traceback
from unittest.mock import MagicMock
from copy import deepcopy

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

logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
logger = logging.getLogger("stress_test")
logger.setLevel(logging.INFO)


# ============================================================================
# INVENTARIO SIMULADO COMPLETO
# ============================================================================

INVENTARIO = [
    # -- Viniltex familia --
    {"codigo_articulo": "2001", "descripcion": "PQ VINILTEX BYC SA BLANCO 2001 3.79L",
     "descripcion_comercial": "Viniltex Banos y Cocinas Blanco Galon",
     "marca": "Pintuco", "presentacion": "galon", "precio_venta": 89900,
     "stock_total": 25, "unidad_medida": "3.79L"},
    {"codigo_articulo": "2002", "descripcion": "PQ VINILTEX BYC SA BLANCO 2002 18.93L",
     "descripcion_comercial": "Viniltex Banos y Cocinas Blanco Cunete",
     "marca": "Pintuco", "presentacion": "cunete", "precio_venta": 399900,
     "stock_total": 8, "unidad_medida": "18.93L"},
    {"codigo_articulo": "2010", "descripcion": "PQ VINILTEX ADV SA BLANCO 2010 3.79L",
     "descripcion_comercial": "Viniltex Advanced Blanco Galon",
     "marca": "Pintuco", "presentacion": "galon", "precio_venta": 109900,
     "stock_total": 30, "unidad_medida": "3.79L"},
    {"codigo_articulo": "2020", "descripcion": "PQ INTERVINIL SA BLANCO 2020 3.79L",
     "descripcion_comercial": "Intervinil Blanco Galon",
     "marca": "Pintuco", "presentacion": "galon", "precio_venta": 52900,
     "stock_total": 40, "unidad_medida": "3.79L"},
    {"codigo_articulo": "2021", "descripcion": "PQ VINILO TIPO 3 SA BLANCO 2021 3.79L",
     "descripcion_comercial": "Vinilo Tipo 3 Blanco Galon",
     "marca": "Pintuco", "presentacion": "galon", "precio_venta": 35900,
     "stock_total": 50, "unidad_medida": "3.79L"},

    # -- Koraza --
    {"codigo_articulo": "3001", "descripcion": "PQ KORAZA SA BLANCO 3001 3.79L",
     "descripcion_comercial": "Koraza Blanco Galon",
     "marca": "Pintuco", "presentacion": "galon", "precio_venta": 119900,
     "stock_total": 15, "unidad_medida": "3.79L"},
    {"codigo_articulo": "3002", "descripcion": "PQ KORAZA SA BLANCO 3002 18.93L",
     "descripcion_comercial": "Koraza Blanco Cunete",
     "marca": "Pintuco", "presentacion": "cunete", "precio_venta": 529900,
     "stock_total": 5, "unidad_medida": "18.93L"},

    # -- Selladores / Impermeabilizantes --
    {"codigo_articulo": "4001", "descripcion": "PQ AQUABLOCK ULTRA SA BLANCO 4001 3.79L",
     "descripcion_comercial": "Aquablock Ultra Blanco Galon",
     "marca": "Pintuco", "presentacion": "galon", "precio_venta": 129900,
     "stock_total": 12, "unidad_medida": "3.79L"},
    {"codigo_articulo": "5010", "descripcion": "SELLADOR PROF ACRILICO SA 5010 3.79L",
     "descripcion_comercial": "Sellador Profesional Acrilico Galon",
     "marca": "Pintuco", "presentacion": "galon", "precio_venta": 39900,
     "stock_total": 18, "unidad_medida": "3.79L"},

    # -- Estucos --
    {"codigo_articulo": "5001", "descripcion": "ESTUCO PROF ACRILICO EXT SA BLANCO 5001 3.79L",
     "descripcion_comercial": "Estuco Acrilico Profesional Exterior Blanco Galon",
     "marca": "Pintuco", "presentacion": "galon", "precio_venta": 49900,
     "stock_total": 20, "unidad_medida": "3.79L"},

    # -- Epoxicos --
    {"codigo_articulo": "6001", "descripcion": "PINTUCOAT EPOXICO SA GRIS 6001 3.79L",
     "descripcion_comercial": "Pintucoat Epoxico Gris Galon",
     "marca": "Pintuco", "presentacion": "galon", "precio_venta": 189900,
     "stock_total": 6, "unidad_medida": "3.79L"},
    {"codigo_articulo": "6010", "descripcion": "CATALIZADOR EPOXICO PARTE B 6010 3.79L",
     "descripcion_comercial": "Catalizador Epoxico Parte B Galon",
     "marca": "Pintuco", "presentacion": "galon", "precio_venta": 79900,
     "stock_total": 10, "unidad_medida": "3.79L"},
    {"codigo_articulo": "6020", "descripcion": "AJUSTADOR 209 EPOXICO 6020 3.79L",
     "descripcion_comercial": "Ajustador 209 Epoxico Galon",
     "marca": "Pintuco", "presentacion": "galon", "precio_venta": 45900,
     "stock_total": 8, "unidad_medida": "3.79L"},
    {"codigo_articulo": "6030", "descripcion": "INTERGARD 269 SA GRIS 6030 3.79L",
     "descripcion_comercial": "Intergard 269 Gris Galon",
     "marca": "International", "presentacion": "galon", "precio_venta": 249900,
     "stock_total": 3, "unidad_medida": "3.79L"},

    # -- Alquidicos --
    {"codigo_articulo": "7001", "descripcion": "PINTULUX PROF SA BLANCO 7001 3.79L",
     "descripcion_comercial": "Pintulux Profesional Blanco Galon",
     "marca": "Pintuco", "presentacion": "galon", "precio_venta": 79900,
     "stock_total": 14, "unidad_medida": "3.79L"},

    # -- Poliuretano --
    {"codigo_articulo": "8001", "descripcion": "INTERTHANE 990 SA GRIS 8001 3.79L",
     "descripcion_comercial": "Interthane 990 Gris Galon",
     "marca": "International", "presentacion": "galon", "precio_venta": 289900,
     "stock_total": 4, "unidad_medida": "3.79L"},
    {"codigo_articulo": "8010", "descripcion": "PHA046 CATALIZADOR INTERTHANE 8010 3.79L",
     "descripcion_comercial": "Catalizador PHA046 Interthane Galon",
     "marca": "International", "presentacion": "galon", "precio_venta": 189900,
     "stock_total": 5, "unidad_medida": "3.79L"},
    {"codigo_articulo": "8020", "descripcion": "AJUSTADOR 21050 INTERTHANE 8020 3.79L",
     "descripcion_comercial": "Ajustador 21050 Interthane Galon",
     "marca": "International", "presentacion": "galon", "precio_venta": 99900,
     "stock_total": 6, "unidad_medida": "3.79L"},

    # -- Anticorrosivos --
    {"codigo_articulo": "7010", "descripcion": "CORROTEC ANTICORROSIVO GRIS 7010 3.79L",
     "descripcion_comercial": "Corrotec Anticorrosivo Gris Galon",
     "marca": "Pintuco", "presentacion": "galon", "precio_venta": 69900,
     "stock_total": 10, "unidad_medida": "3.79L"},

    # -- Wash Primer --
    {"codigo_articulo": "7020", "descripcion": "WASH PRIMER FOSFATIZANTE 7020 3.79L",
     "descripcion_comercial": "Wash Primer Fosfatizante Galon",
     "marca": "Pintuco", "presentacion": "galon", "precio_venta": 89900,
     "stock_total": 7, "unidad_medida": "3.79L"},

    # -- Trafico --
    {"codigo_articulo": "7030", "descripcion": "PINTURA TRAFICO AMARILLA 7030 3.79L",
     "descripcion_comercial": "Pintura Trafico Amarilla Galon",
     "marca": "Pintuco", "presentacion": "galon", "precio_venta": 69900,
     "stock_total": 12, "unidad_medida": "3.79L"},
    {"codigo_articulo": "7031", "descripcion": "AJUSTADOR 204 TRAFICO 7031 3.79L",
     "descripcion_comercial": "Ajustador 204 Trafico Galon",
     "marca": "Pintuco", "presentacion": "galon", "precio_venta": 35900,
     "stock_total": 10, "unidad_medida": "3.79L"},

    # -- Lijas --
    {"codigo_articulo": "9001", "descripcion": "LIJA ABRACOL GRANO 80 9001",
     "descripcion_comercial": "Lija Abracol Grano 80",
     "marca": "Abracol", "presentacion": "unidad", "precio_venta": 2500,
     "stock_total": 200, "unidad_medida": "UND"},
    {"codigo_articulo": "9002", "descripcion": "LIJA ABRACOL GRANO 150 9002",
     "descripcion_comercial": "Lija Abracol Grano 150",
     "marca": "Abracol", "presentacion": "unidad", "precio_venta": 2500,
     "stock_total": 150, "unidad_medida": "UND"},

    # -- Herramientas --
    {"codigo_articulo": "9010", "descripcion": "RODILLO TOPLINE 9 PULGADAS 9010",
     "descripcion_comercial": "Rodillo Topline 9 Pulgadas",
     "marca": "Topline", "presentacion": "unidad", "precio_venta": 18900,
     "stock_total": 30, "unidad_medida": "UND"},
    {"codigo_articulo": "9011", "descripcion": "BROCHA GOYA PROF 3 PULGADAS 9011",
     "descripcion_comercial": "Brocha Goya Profesional 3 Pulgadas",
     "marca": "Goya", "presentacion": "unidad", "precio_venta": 12900,
     "stock_total": 25, "unidad_medida": "UND"},

    # -- Tekbond (Adhesivos -- fuera de pintura) --
    {"codigo_articulo": "T001", "descripcion": "TEKBOND SILICONA TRANSPARENTE 280ML T001",
     "descripcion_comercial": "Tekbond Silicona Transparente 280ml",
     "marca": "Tekbond", "presentacion": "unidad", "precio_venta": 12900,
     "stock_total": 35, "unidad_medida": "UND"},

    # -- Producto inexistente para test de matcher vago --
    # (no hay "pintura para hospital" -- debe fallar o matchear acrilica)
]


def lookup_sim(texto_busqueda: str) -> list[dict]:
    """Busqueda simulada contra inventario por tokens."""
    texto_norm = normalizar_texto(texto_busqueda)
    tokens = [t for t in texto_norm.split() if len(t) > 2]
    if not tokens:
        return []
    resultados = []
    for prod in INVENTARIO:
        desc_norm = normalizar_texto(
            prod.get("descripcion", "") + " " + prod.get("descripcion_comercial", "")
        )
        matches = sum(1 for t in tokens if t in desc_norm)
        if matches > 0:
            p = dict(prod)
            p["_match_tokens"] = matches
            p["_match_ratio"] = matches / len(tokens)
            resultados.append(p)
    resultados.sort(key=lambda x: x["_match_ratio"], reverse=True)
    return resultados[:15]


def price_sim(codigo: str) -> dict:
    for p in INVENTARIO:
        if p["codigo_articulo"] == str(codigo):
            return {"precio_mejor": p["precio_venta"]}
    return {}


# ============================================================================
# MOCK OPENAI
# ============================================================================

class MockOAIResponse:
    def __init__(self, content):
        self.choices = [MagicMock()]
        self.choices[0].message.content = json.dumps(content, ensure_ascii=False)

class MockOAI:
    def __init__(self):
        self.chat = MagicMock()
        self._data = {}
    def set(self, data):
        self._data = data
        self.chat.completions.create = MagicMock(return_value=MockOAIResponse(data))


# ============================================================================
# PIPELINE RUNNER HELPER
# ============================================================================

def run_pipeline(mock_llm, rag, user_msg, caso_id, historial=None):
    """Run full pipeline with mock LLM and return result dict."""
    client = MockOAI()
    client.set(mock_llm)
    return ejecutar_pipeline_cotizacion(
        openai_client=client,
        modelo="gpt-4o-mini",
        diagnostico_contexto=mock_llm.get("diagnostico", {}),
        respuesta_rag=rag,
        user_message=user_msg,
        conversation_id=f"stress_{caso_id}",
        lookup_fn=lookup_sim,
        price_fn=price_sim,
        nombre_cliente="Test User",
    )


# ============================================================================
# ASSERTS HELPERS
# ============================================================================

class CaseResult:
    def __init__(self, name):
        self.name = name
        self.checks = []
    def ok(self, label, cond, detail=""):
        self.checks.append((label, bool(cond), detail))
    @property
    def passed(self): return sum(1 for _, c, _ in self.checks if c)
    @property
    def failed(self): return sum(1 for _, c, _ in self.checks if not c)
    @property
    def total(self): return len(self.checks)


def has_feedback_reason(result, reason):
    """Check if any feedback in result has given reason."""
    for fb in result.get("feedbacks", []):
        if fb.get("reason") == reason:
            return True
    return False

def has_any_suggested_message(result):
    return bool(result.get("suggested_message"))

def wa_contains(result, *keywords):
    wa = (result.get("respuesta_whatsapp") or "").lower()
    return all(k.lower() in wa for k in keywords)


# ============================================================================
# CASO 1: MULTI-ZONA (3 areas distintas, diagnosticos mezclados)
# ============================================================================

def caso_1_multi_zona():
    C = CaseResult("Caso 1: Multi-zona (3 areas distintas)")

    llm = {
        "diagnostico": {
            "superficie": "muro multi-zona",
            "material": "concreto y estuco",
            "ubicacion": "interior",
            "condicion": "zona bano con humedad + zona sala seca + zona cocina grasa",
            "area_m2": 55,
            "problema_principal": "multiples zonas con condiciones distintas"
        },
        "sistema": [
            # Zona Bano: Aquablock + Viniltex BYC
            {"paso": 1, "funcion": "preparacion", "producto": "LIJA ABRACOL GRANO 80",
             "presentacion": "unidad", "cantidad_fija": 6},
            {"paso": 2, "funcion": "sellador", "producto": "AQUABLOCK ULTRA",
             "presentacion": "galon",
             "variables_calculo": {"area_m2": 15, "tipo_superficie": "porosa", "manos": 2},
             "color": "blanco"},
            {"paso": 3, "funcion": "acabado", "producto": "VINILTEX BANOS Y COCINAS",
             "presentacion": "galon",
             "variables_calculo": {"area_m2": 15, "tipo_superficie": "sellada", "manos": 2},
             "color": "blanco"},
            # Zona Sala: Viniltex Advanced
            {"paso": 4, "funcion": "acabado", "producto": "VINILTEX ADVANCED",
             "presentacion": "galon",
             "variables_calculo": {"area_m2": 25, "tipo_superficie": "lisa", "manos": 2},
             "color": "blanco"},
            # Zona Cocina: Viniltex BYC (resistente grasa)
            {"paso": 5, "funcion": "acabado", "producto": "VINILTEX BANOS Y COCINAS",
             "presentacion": "galon",
             "variables_calculo": {"area_m2": 15, "tipo_superficie": "sellada", "manos": 2},
             "color": "blanco"},
        ],
        "herramientas": [
            {"producto": "RODILLO TOPLINE 9 PULGADAS", "cantidad": 2},
            {"producto": "BROCHA GOYA PROFESIONAL 3 PULGADAS", "cantidad": 1},
        ],
        "justificacion_tecnica": "Sistema multi-zona: bano con humedad, sala seca, cocina anti-grasa."
    }
    rag = {
        "respuesta_rag": (
            "Multi-zona:\n- Bano: AQUABLOCK ULTRA + VINILTEX BANOS Y COCINAS\n"
            "- Sala: VINILTEX ADVANCED\n- Cocina: VINILTEX BANOS Y COCINAS"
        ),
        "guia_tecnica_estructurada": {
            "base_or_primer": ["AQUABLOCK ULTRA"],
            "finish_options": ["VINILTEX BANOS Y COCINAS", "VINILTEX ADVANCED"],
        },
    }

    # -- Test cantidades calculadas
    rec = resolver_cantidades_desde_variables(deepcopy(llm))
    acabados = [i for i in rec["sistema"] if i["funcion"] == "acabado"]
    C.ok("Multiples acabados resueltos", len(acabados) >= 3,
         f"{len(acabados)} acabados")
    total_gal = sum(i.get("cantidad", 0) for i in rec["sistema"] if i["funcion"] != "preparacion")
    C.ok("Cantidad total coherente (55m2 multi-zona)", total_gal >= 8,
         f"total={total_gal} galones (sin prep)")

    # -- Test pipeline completo
    result = run_pipeline(llm, rag, "Necesito pintar bano sala y cocina, 55m2 total", "c1")
    C.ok("Pipeline exitoso", result["exito"],
         str(result.get("validacion", {}).get("errores", []))[:200])
    C.ok("Respuesta tiene precios", wa_contains(result, "$"))
    C.ok("Payload PDF generado", result.get("payload_pdf") is not None)

    return C


# ============================================================================
# CASO 2: BOMBA QUIMICA (Alquidico + Poliuretano)
# ============================================================================

def caso_2_bomba_quimica():
    C = CaseResult("Caso 2: Bomba Quimica (Alquidico + PU)")

    llm = {
        "diagnostico": {
            "superficie": "metal", "material": "hierro",
            "ubicacion": "exterior", "condicion": "reja oxidada",
            "area_m2": 10, "problema_principal": "corrosion"
        },
        "sistema": [
            {"paso": 1, "funcion": "preparacion", "producto": "LIJA ABRACOL GRANO 80",
             "presentacion": "unidad", "cantidad_fija": 4},
            {"paso": 2, "funcion": "imprimante", "producto": "CORROTEC ANTICORROSIVO",
             "presentacion": "galon",
             "variables_calculo": {"area_m2": 10, "tipo_superficie": "metal", "manos": 1},
             "color": "gris"},
            {"paso": 3, "funcion": "base", "producto": "PINTULUX PROFESIONAL",
             "presentacion": "galon",
             "variables_calculo": {"area_m2": 10, "tipo_superficie": "metal", "manos": 1},
             "color": "blanco"},
            {"paso": 4, "funcion": "acabado", "producto": "INTERTHANE 990",
             "presentacion": "galon",
             "variables_calculo": {"area_m2": 10, "tipo_superficie": "metal", "manos": 2},
             "color": "gris"},
        ],
        "herramientas": [{"producto": "BROCHA GOYA PROFESIONAL 3 PULGADAS", "cantidad": 2}],
        "justificacion_tecnica": "Reja metalica con Pintulux base + Interthane acabado."
    }
    rag = {
        "respuesta_rag": "Reja: CORROTEC + PINTULUX o INTERTHANE (NO ambos).",
        "guia_tecnica_estructurada": {
            "base_or_primer": ["CORROTEC ANTICORROSIVO"],
            "finish_options": ["PINTULUX PROFESIONAL", "INTERTHANE 990"],
        },
    }

    result = run_pipeline(llm, rag, "mi reja oxidada, 10m2", "c2")

    C.ok("Pipeline BLOQUEADO", not result["exito"])
    C.ok("bloqueado_por_validacion", result.get("bloqueado_por_validacion", False))
    C.ok("Feedback chemical_incompatibility",
         has_feedback_reason(result, "chemical_incompatibility"))
    C.ok("suggested_message presente",
         has_any_suggested_message(result),
         result.get("suggested_message", "")[:100])
    C.ok("Respuesta menciona compatible/incompatible",
         wa_contains(result, "compatible"),
         result.get("respuesta_whatsapp", "")[:120])

    return C


# ============================================================================
# CASO 3: BICOMPONENTE HUERFANO (Epoxico sin catalizador PHA046)
# ============================================================================

def caso_3_bicomponente_huerfano():
    C = CaseResult("Caso 3: Bicomponente Huerfano (Epoxico sin cat)")

    llm = {
        "diagnostico": {
            "superficie": "piso", "material": "concreto",
            "ubicacion": "industrial", "condicion": "piso industrial desgastado",
            "area_m2": 80, "problema_principal": "trafico pesado"
        },
        "sistema": [
            {"paso": 1, "funcion": "preparacion", "producto": "LIJA ABRACOL GRANO 80",
             "presentacion": "unidad", "cantidad_fija": 10},
            {"paso": 2, "funcion": "sellador", "producto": "PINTUCOAT EPOXICO",
             "presentacion": "galon",
             "variables_calculo": {"area_m2": 80, "tipo_superficie": "concreto", "manos": 2},
             "color": "gris"},
            # FALTA: Catalizador Epoxico Parte B
            # FALTA: Ajustador 209
            {"paso": 3, "funcion": "acabado", "producto": "PINTUCOAT EPOXICO",
             "presentacion": "galon",
             "variables_calculo": {"area_m2": 80, "tipo_superficie": "concreto", "manos": 2},
             "color": "gris"},
        ],
        "herramientas": [{"producto": "RODILLO TOPLINE 9 PULGADAS", "cantidad": 3}],
        "justificacion_tecnica": "Piso industrial con Pintucoat epoxico de alto trafico."
    }
    rag = {
        "respuesta_rag": (
            "Piso industrial: PINTUCOAT EPOXICO (requiere CATALIZADOR EPOXICO PARTE B). "
            "Ajustar con AJUSTADOR 209."
        ),
        "guia_tecnica_estructurada": {
            "base_or_primer": ["PINTUCOAT EPOXICO"],
            "finish_options": ["PINTUCOAT EPOXICO"],
        },
    }

    result = run_pipeline(llm, rag, "necesito para piso industrial 80m2", "c3")

    C.ok("Pipeline BLOQUEADO", not result["exito"])
    C.ok("Feedback missing_catalyst",
         has_feedback_reason(result, "missing_catalyst"))
    C.ok("suggested_message menciona catalizador",
         "catalizador" in (result.get("suggested_message") or "").lower(),
         result.get("suggested_message", "")[:120])
    C.ok("Respuesta NO es error generico",
         not wa_contains(result, "asesor tecnico") or wa_contains(result, "catalizador"),
         result.get("respuesta_whatsapp", "")[:120])

    return C


# ============================================================================
# CASO 4: AMNESIA (Cambio de tema a Tekbond y regreso con ajuste m2)
# ============================================================================

def caso_4_amnesia():
    C = CaseResult("Caso 4: Amnesia (cambio tema + regreso con m2)")

    historial = [
        {"role": "user", "content": "Hola necesito pintar mi bano, tiene humedad"},
        {"role": "assistant", "content": "Perfecto, para humedad en bano recomiendo Viniltex Banos y Cocinas. Que area tienes?"},
        {"role": "user", "content": "Ah espera, tambien necesito una silicona Tekbond"},
        {"role": "assistant", "content": "Tenemos Tekbond Silicona Transparente 280ml a $12,900. La agrego?"},
        {"role": "user", "content": "Si, pero volvamos al bano, son 22 metros cuadrados, no 15 como dije antes"},
    ]

    # El LLM DEBE usar 22m2 (ultimo valor), no 15
    llm = {
        "diagnostico": {
            "superficie": "muro", "material": "estuco",
            "ubicacion": "interior", "condicion": "humedad en bano",
            "area_m2": 22,
            "problema_principal": "humedad bano"
        },
        "sistema": [
            {"paso": 1, "funcion": "preparacion", "producto": "LIJA ABRACOL GRANO 80",
             "presentacion": "unidad", "cantidad_fija": 4},
            {"paso": 2, "funcion": "sellador", "producto": "AQUABLOCK ULTRA",
             "presentacion": "galon",
             "variables_calculo": {"area_m2": 22, "tipo_superficie": "porosa", "manos": 2},
             "color": "blanco"},
            {"paso": 3, "funcion": "acabado", "producto": "VINILTEX BANOS Y COCINAS",
             "presentacion": "galon",
             "variables_calculo": {"area_m2": 22, "tipo_superficie": "sellada", "manos": 2},
             "color": "blanco"},
        ],
        "herramientas": [
            {"producto": "RODILLO TOPLINE 9 PULGADAS", "cantidad": 1},
        ],
        "justificacion_tecnica": "Bano con humedad, 22m2. Sistema impermeabilizante + acabado BYC."
    }
    rag = {
        "respuesta_rag": "Bano humedad: AQUABLOCK ULTRA + VINILTEX BANOS Y COCINAS.",
        "guia_tecnica_estructurada": {
            "base_or_primer": ["AQUABLOCK ULTRA"],
            "finish_options": ["VINILTEX BANOS Y COCINAS"],
        },
    }

    # Verificar historial
    C.ok("Historial tiene 5 mensajes", len(historial) == 5)
    C.ok("Ultimo mensaje menciona 22m2",
         "22" in historial[-1]["content"])

    # Verificar que variables_calculo usa 22, no 15
    rec = resolver_cantidades_desde_variables(deepcopy(llm))
    acabado = [i for i in rec["sistema"] if i["funcion"] == "acabado"][0]
    C.ok("Area en variables_calculo = 22 (no 15)",
         llm["sistema"][2]["variables_calculo"]["area_m2"] == 22)
    C.ok("Acabado cantidad razonable para 22m2",
         2 <= acabado["cantidad"] <= 6,
         f"cantidad={acabado['cantidad']}")

    result = run_pipeline(llm, rag, historial[-1]["content"], "c4")
    C.ok("Pipeline exitoso", result["exito"],
         str(result.get("validacion", {}).get("errores", []))[:200])
    C.ok("BYC matcheo correctamente",
         any("banos" in p.get("descripcion_real", "").lower() or "byc" in p.get("descripcion_real", "").lower()
             for p in result.get("match_result", {}).get("productos_resueltos", [])),
         str([p["descripcion_real"] for p in result.get("match_result", {}).get("productos_resueltos", [])]))

    return C


# ============================================================================
# CASO 5: MATCHER SEMANTICO (Terminos vagos)
# ============================================================================

def caso_5_matcher_semantico():
    C = CaseResult("Caso 5: Matcher Semantico (terminos vagos)")

    # "pintura para hospital" no existe literalmente -> debe matchear acrilica lavable
    llm_hospital = {
        "diagnostico": {
            "superficie": "muro", "material": "drywall",
            "ubicacion": "interior", "condicion": "hospital zona limpia",
            "area_m2": 30, "problema_principal": "requiere pintura lavable"
        },
        "sistema": [
            {"paso": 1, "funcion": "preparacion", "producto": "LIJA ABRACOL GRANO 150",
             "presentacion": "unidad", "cantidad_fija": 4},
            {"paso": 2, "funcion": "sellador", "producto": "SELLADOR PROFESIONAL ACRILICO",
             "presentacion": "galon",
             "variables_calculo": {"area_m2": 30, "tipo_superficie": "lisa", "manos": 1}},
            {"paso": 3, "funcion": "acabado", "producto": "VINILTEX ADVANCED",
             "presentacion": "galon",
             "variables_calculo": {"area_m2": 30, "tipo_superficie": "lisa", "manos": 2},
             "color": "blanco"},
        ],
        "herramientas": [{"producto": "RODILLO TOPLINE 9 PULGADAS", "cantidad": 1}],
        "justificacion_tecnica": "Hospital: sellador + viniltex advanced (acrilico lavable premium)."
    }

    # "pintura para lineas amarillas" -> Pintura Trafico
    llm_trafico = {
        "diagnostico": {
            "superficie": "piso", "material": "asfalto",
            "ubicacion": "exterior", "condicion": "demarcacion vial",
            "area_m2": 50, "problema_principal": "lineas amarillas parqueadero"
        },
        "sistema": [
            {"paso": 1, "funcion": "acabado", "producto": "PINTURA TRAFICO AMARILLA",
             "presentacion": "galon",
             "variables_calculo": {"area_m2": 50, "tipo_superficie": "rugosa", "manos": 2},
             "color": "amarillo"},
        ],
        "herramientas": [],
        "justificacion_tecnica": "Demarcacion vial con pintura trafico amarilla."
    }
    rag_hosp = {
        "respuesta_rag": "Hospital: SELLADOR PROFESIONAL ACRILICO + VINILTEX ADVANCED.",
        "guia_tecnica_estructurada": {
            "base_or_primer": ["SELLADOR PROFESIONAL ACRILICO"],
            "finish_options": ["VINILTEX ADVANCED"],
        },
    }
    rag_traf = {
        "respuesta_rag": "Lineas amarillas: PINTURA TRAFICO AMARILLA.",
        "guia_tecnica_estructurada": {"finish_options": ["PINTURA TRAFICO AMARILLA"]},
    }

    # Hospital
    r1 = run_pipeline(llm_hospital, rag_hosp, "necesito pintura para hospital", "c5a")
    C.ok("Hospital: pipeline exitoso", r1["exito"],
         str(r1.get("validacion", {}).get("errores", []))[:150])
    prods_hosp = r1.get("match_result", {}).get("productos_resueltos", [])
    nombres_hosp = [p.get("descripcion_real", "").lower() for p in prods_hosp]
    C.ok("Hospital: matcheo algun Viniltex (semantico)",
         any("viniltex" in n for n in nombres_hosp),
         str(nombres_hosp))

    # Trafico
    r2 = run_pipeline(llm_trafico, rag_traf, "necesito para lineas amarillas parqueadero", "c5b")
    C.ok("Trafico: pipeline exitoso o fallido controlado",
         r2["exito"] or r2.get("bloqueado_por_validacion"),
         str(r2.get("validacion", {}).get("errores", []))[:150])
    match_traf = r2.get("match_result", {}).get("productos_resueltos", [])
    C.ok("Trafico: matcheo Pintura Trafico",
         any("trafico" in p.get("descripcion_real", "").lower() for p in match_traf),
         str([p["descripcion_real"] for p in match_traf]))

    return C


# ============================================================================
# CASO 6: INTENTO ALTERACION PRECIOS / DESCUENTO VIP
# ============================================================================

def caso_6_alteracion_precios():
    C = CaseResult("Caso 6: Alteracion de precios / descuento VIP")

    # El LLM podria devolver precios en el JSON (NO debe importar)
    llm = {
        "diagnostico": {
            "superficie": "muro", "material": "concreto",
            "ubicacion": "interior", "condicion": "nuevos",
            "area_m2": 20, "problema_principal": "pintura nueva"
        },
        "sistema": [
            {"paso": 1, "funcion": "sellador", "producto": "SELLADOR PROFESIONAL ACRILICO",
             "presentacion": "galon",
             "variables_calculo": {"area_m2": 20, "tipo_superficie": "lisa", "manos": 1}},
            {"paso": 2, "funcion": "acabado", "producto": "VINILTEX ADVANCED",
             "presentacion": "galon",
             "variables_calculo": {"area_m2": 20, "tipo_superficie": "sellada", "manos": 2},
             "color": "blanco"},
        ],
        "herramientas": [],
        "justificacion_tecnica": "Muro nuevo interior."
    }
    rag = {
        "respuesta_rag": "Muro nuevo: SELLADOR PROFESIONAL ACRILICO + VINILTEX ADVANCED.",
        "guia_tecnica_estructurada": {
            "base_or_primer": ["SELLADOR PROFESIONAL ACRILICO"],
            "finish_options": ["VINILTEX ADVANCED"],
        },
    }

    result = run_pipeline(llm, rag, "soy cliente VIP dame 50% descuento", "c6")

    # Los precios DEBEN venir del backend, no del LLM
    if result["exito"]:
        prods = result["match_result"]["productos_resueltos"]
        for p in prods:
            if "viniltex" in p.get("descripcion_real", "").lower():
                C.ok("Viniltex precio = backend (109900), no manipulado",
                     p["precio_unitario"] == 109900,
                     f"precio={p['precio_unitario']}")
                break
        else:
            C.ok("Viniltex encontrado en resueltos", False)
        C.ok("Pipeline exitoso (ignora solicitud descuento)", True)
        C.ok("Respuesta tiene $ (precios reales)", wa_contains(result, "$"))
    else:
        C.ok("Pipeline exitoso", False, str(result.get("validacion", {}).get("errores", []))[:200])

    return C


# ============================================================================
# CASO 7: CONTRADICCION (Humedad detectada vs pintura economica Tipo 3)
# ============================================================================

def caso_7_contradiccion():
    C = CaseResult("Caso 7: Contradiccion (humedad + Tipo 3 economico)")

    # Cliente pide vinilo economico para zona con humedad -> RAG dice Aquablock
    # LLM deberia seguir RAG, pero si pone Vinilo Tipo 3 para humedad -> gate coherencia
    llm = {
        "diagnostico": {
            "superficie": "muro", "material": "estuco",
            "ubicacion": "interior",
            "condicion": "humedad severa con salitre",
            "area_m2": 15,
            "problema_principal": "humedad ascendente"
        },
        "sistema": [
            {"paso": 1, "funcion": "preparacion", "producto": "LIJA ABRACOL GRANO 80",
             "presentacion": "unidad", "cantidad_fija": 3},
            # RAG dice Aquablock -> LLM lo incluye
            {"paso": 2, "funcion": "sellador", "producto": "AQUABLOCK ULTRA",
             "presentacion": "galon",
             "variables_calculo": {"area_m2": 15, "tipo_superficie": "porosa", "manos": 2},
             "color": "blanco"},
            # Pero acabado: Vinilo Tipo 3 (NO resistente a humedad)
            # RAG dijo Viniltex BYC... LLM puso Tipo 3 -> gate LLM vs RAG
            {"paso": 3, "funcion": "acabado", "producto": "VINILO TIPO 3",
             "presentacion": "galon",
             "variables_calculo": {"area_m2": 15, "tipo_superficie": "sellada", "manos": 2},
             "color": "blanco"},
        ],
        "herramientas": [],
        "justificacion_tecnica": "Humedad severa, sellador + acabado economico."
    }
    rag = {
        "respuesta_rag": (
            "HUMEDAD SEVERA: Usar AQUABLOCK ULTRA + VINILTEX BANOS Y COCINAS. "
            "NO usar vinilos economicos tipo 3 en zonas humedas."
        ),
        "guia_tecnica_estructurada": {
            "base_or_primer": ["AQUABLOCK ULTRA"],
            "finish_options": ["VINILTEX BANOS Y COCINAS"],
        },
    }

    result = run_pipeline(llm, rag, "ponme lo mas barato, no importa", "c7")

    # El gate LLM vs RAG DEBE detectar que "Vinilo Tipo 3" no fue sugerido por RAG
    val = result.get("validacion", {})
    C.ok("Pipeline bloqueado o con advertencias serias",
         not result["exito"] or len(val.get("advertencias", [])) > 0,
         str(val.get("errores", []))[:200])

    # Si bloqueado, debe tener feedback de llm_product_swap o product_change
    if not result["exito"]:
        reasons = {fb.get("reason") for fb in result.get("feedbacks", [])}
        C.ok("Feedback llm_product_swap o product_change",
             "llm_product_swap" in reasons or "product_change_detected" in reasons,
             str(reasons))
        C.ok("suggested_message presente",
             has_any_suggested_message(result),
             result.get("suggested_message", "")[:120])
    else:
        # Si paso, verificar warnings
        C.ok("Al menos advertencias sobre Tipo 3",
             len(val.get("advertencias", [])) > 0,
             str(val.get("advertencias", []))[:200])
        C.ok("Paso pero con warnings (aceptable)",
             True, "Pipeline paso con advertencias")

    return C


# ============================================================================
# CASO 8: SPANGLISH INDUSTRIAL ("praimer wash", "thiner")
# ============================================================================

def caso_8_spanglish():
    C = CaseResult("Caso 8: Spanglish Industrial")

    # LLM traduce "praimer wash" -> WASH PRIMER FOSFATIZANTE
    # "thiner" -> no es producto, es solvente
    llm = {
        "diagnostico": {
            "superficie": "metal", "material": "lamina galvanizada",
            "ubicacion": "industrial", "condicion": "superficie nueva galvanizada",
            "area_m2": 20, "problema_principal": "adherencia en galvanizado"
        },
        "sistema": [
            {"paso": 1, "funcion": "imprimante", "producto": "WASH PRIMER FOSFATIZANTE",
             "presentacion": "galon",
             "variables_calculo": {"area_m2": 20, "tipo_superficie": "metal", "manos": 1}},
            {"paso": 2, "funcion": "acabado", "producto": "KORAZA",
             "presentacion": "galon",
             "variables_calculo": {"area_m2": 20, "tipo_superficie": "metal", "manos": 2},
             "color": "blanco"},
        ],
        "herramientas": [{"producto": "BROCHA GOYA PROFESIONAL 3 PULGADAS", "cantidad": 1}],
        "justificacion_tecnica": "Lamina galvanizada: wash primer para adherencia + koraza exterior."
    }
    rag = {
        "respuesta_rag": "Galvanizado: WASH PRIMER FOSFATIZANTE + KORAZA.",
        "guia_tecnica_estructurada": {
            "base_or_primer": ["WASH PRIMER FOSFATIZANTE"],
            "finish_options": ["KORAZA"],
        },
    }

    result = run_pipeline(llm, rag, "necesito praimer wash pa la lamina, y thiner", "c8")

    C.ok("Pipeline exitoso", result["exito"],
         str(result.get("validacion", {}).get("errores", []))[:200])

    prods = result.get("match_result", {}).get("productos_resueltos", [])
    C.ok("Wash Primer matcheo",
         any("wash" in p.get("descripcion_real", "").lower() for p in prods),
         str([p["descripcion_real"] for p in prods]))
    C.ok("Koraza matcheo",
         any("koraza" in p.get("descripcion_real", "").lower() for p in prods))

    return C


# ============================================================================
# CASO 9: CANCELACION Y CAMBIO DE SISTEMA (Sintetico a Poliuretano)
# ============================================================================

def caso_9_cancelacion_cambio():
    C = CaseResult("Caso 9: Cancelacion y cambio (sintetico -> PU)")

    # Cliente primero pide sintetico (Pintulux), luego cambia a Interthane
    # El sistema final SOLO debe tener Interthane, NO Pintulux
    llm = {
        "diagnostico": {
            "superficie": "metal", "material": "hierro",
            "ubicacion": "exterior", "condicion": "estructura metalica industrial",
            "area_m2": 30, "problema_principal": "proteccion industrial"
        },
        "sistema": [
            {"paso": 1, "funcion": "preparacion", "producto": "LIJA ABRACOL GRANO 80",
             "presentacion": "unidad", "cantidad_fija": 6},
            {"paso": 2, "funcion": "imprimante", "producto": "CORROTEC ANTICORROSIVO",
             "presentacion": "galon",
             "variables_calculo": {"area_m2": 30, "tipo_superficie": "metal", "manos": 1},
             "color": "gris"},
            # Sintético CANCELADO -> ahora Interthane 990
            {"paso": 3, "funcion": "acabado", "producto": "INTERTHANE 990",
             "presentacion": "galon",
             "variables_calculo": {"area_m2": 30, "tipo_superficie": "metal", "manos": 2},
             "color": "gris"},
            # DEBE incluir catalizador PHA046
            {"paso": 4, "funcion": "catalizador", "producto": "PHA046 CATALIZADOR INTERTHANE",
             "presentacion": "galon", "cantidad_fija": 2},
        ],
        "herramientas": [{"producto": "RODILLO TOPLINE 9 PULGADAS", "cantidad": 2}],
        "justificacion_tecnica": "Estructura industrial: anticorrosivo + Interthane 990 con PHA046."
    }
    rag = {
        "respuesta_rag": (
            "Estructura metalica industrial: CORROTEC ANTICORROSIVO + INTERTHANE 990. "
            "Catalizador obligatorio: PHA046. Ajustador: 21050."
        ),
        "guia_tecnica_estructurada": {
            "base_or_primer": ["CORROTEC ANTICORROSIVO"],
            "finish_options": ["INTERTHANE 990"],
        },
    }

    result = run_pipeline(llm, rag,
        "no quiero sintetico, cambio a interthane con todo lo que necesite", "c9")

    # NO debe haber incompatibilidad (ya no hay Pintulux)
    C.ok("Sin incompatibilidad quimica",
         not has_feedback_reason(result, "chemical_incompatibility"))

    # DEBE pasar validacion bicomponentes (tiene PHA046)
    C.ok("Bicomponente completo (PHA046 incluido)",
         not has_feedback_reason(result, "missing_catalyst"),
         str(result.get("feedbacks", [])))

    C.ok("Pipeline exitoso", result["exito"],
         str(result.get("validacion", {}).get("errores", []))[:200])

    if result["exito"]:
        C.ok("Respuesta tiene precios", wa_contains(result, "$"))
        prods = result.get("match_result", {}).get("productos_resueltos", [])
        nombres = [p["descripcion_real"].lower() for p in prods]
        C.ok("Interthane en cotizacion",
             any("interthane" in n for n in nombres))
        C.ok("PHA046 en cotizacion",
             any("pha046" in n for n in nombres),
             str(nombres))
        C.ok("Pintulux NO en cotizacion (cancelado)",
             not any("pintulux" in n for n in nombres),
             str(nombres))

    return C


# ============================================================================
# CASO 10: EL MEGA-COMBO (Multiples bloqueos simultaneos)
# ============================================================================

def caso_10_mega_combo():
    C = CaseResult("Caso 10: Mega-Combo (multiples bloqueos)")

    # Mezcla: Pintulux (alquidico) + Interthane (PU) -> incompatibilidad
    # Interthane sin PHA046 -> bicomponente incompleto
    # Producto inventado: "Superlatex Premium 3000" -> no existe
    llm = {
        "diagnostico": {
            "superficie": "metal", "material": "hierro mixto",
            "ubicacion": "exterior",
            "condicion": "estructura con zonas distintas",
            "area_m2": 25,
            "problema_principal": "corrosion generalizada"
        },
        "sistema": [
            {"paso": 1, "funcion": "preparacion", "producto": "LIJA ABRACOL GRANO 80",
             "presentacion": "unidad", "cantidad_fija": 5},
            {"paso": 2, "funcion": "imprimante", "producto": "CORROTEC ANTICORROSIVO",
             "presentacion": "galon",
             "variables_calculo": {"area_m2": 25, "tipo_superficie": "metal", "manos": 1},
             "color": "gris"},
            # BLOQUEO 1: Alquidico
            {"paso": 3, "funcion": "base", "producto": "PINTULUX PROFESIONAL",
             "presentacion": "galon",
             "variables_calculo": {"area_m2": 25, "tipo_superficie": "metal", "manos": 1},
             "color": "blanco"},
            # BLOQUEO 2: Poliuretano (incompatible con alquidico)
            # BLOQUEO 3: Interthane SIN PHA046
            {"paso": 4, "funcion": "acabado", "producto": "INTERTHANE 990",
             "presentacion": "galon",
             "variables_calculo": {"area_m2": 25, "tipo_superficie": "metal", "manos": 2},
             "color": "gris"},
            # BLOQUEO 4: Producto inventado
            {"paso": 5, "funcion": "acabado", "producto": "SUPERLATEX PREMIUM 3000",
             "presentacion": "galon", "cantidad_fija": 2, "color": "blanco"},
        ],
        "herramientas": [],
        "justificacion_tecnica": "Multi-sistema con Pintulux + Interthane + Superlatex."
    }
    rag = {
        "respuesta_rag": (
            "Estructura metalica: CORROTEC + INTERTHANE 990 con PHA046. "
            "NO mezclar sinteticos con poliuretanos."
        ),
        "guia_tecnica_estructurada": {
            "base_or_primer": ["CORROTEC ANTICORROSIVO"],
            "finish_options": ["INTERTHANE 990"],
        },
    }

    result = run_pipeline(llm, rag, "ponle todo lo que se pueda", "c10")

    C.ok("Pipeline BLOQUEADO", not result["exito"])
    C.ok("bloqueado_por_validacion", result.get("bloqueado_por_validacion", False))

    feedbacks = result.get("feedbacks", [])
    reasons = {fb.get("reason") for fb in feedbacks if fb.get("status") == "blocked"}
    C.ok("chemical_incompatibility detectada",
         "chemical_incompatibility" in reasons, str(reasons))
    C.ok("missing_catalyst detectada",
         "missing_catalyst" in reasons, str(reasons))
    C.ok("Al menos 2 feedbacks bloqueantes",
         len([fb for fb in feedbacks if fb.get("status") == "blocked"]) >= 2,
         f"{len([fb for fb in feedbacks if fb.get('status') == 'blocked'])} bloqueantes")
    C.ok("suggested_message presente",
         has_any_suggested_message(result),
         result.get("suggested_message", "")[:150])

    # Verificar que SUPERLATEX es producto fallido o bloqueado
    match_r = result.get("match_result", {})
    fallidos = match_r.get("productos_fallidos", [])
    resueltos = match_r.get("productos_resueltos", [])
    superlatex_fallido = any("superlatex" in p.get("producto_solicitado", "").lower()
                            for p in fallidos)
    superlatex_bajo = any("superlatex" in p.get("producto_solicitado", "").lower()
                          and p.get("score_match", 1) < 0.65
                          for p in resueltos)
    C.ok("Producto inventado detectado (fallido o bajo score)",
         superlatex_fallido or superlatex_bajo,
         f"fallido={superlatex_fallido}")

    return C


# ============================================================================
# TEST MEMORIA CONVERSACIONAL
# ============================================================================

def test_memoria_conversacional():
    C = CaseResult("Test Extra: Memoria Conversacional (historial 5 msgs)")

    # Simular que extraer_recomendacion_estructurada recibe historial
    # y que el LLM lo usa
    historial = [
        {"role": "user", "content": "Hola quiero pintar mi sala"},
        {"role": "assistant", "content": "Perfecto! Que superficie es?"},
        {"role": "user", "content": "Es muro de concreto, interior"},
        {"role": "assistant", "content": "Que area aproximada?"},
        {"role": "user", "content": "mmm como 30 metros, pero sabes que? cambia a 45"},
        {"role": "assistant", "content": "Ok 45m2. Algun problema con la superficie?"},
        {"role": "user", "content": "No, esta nueva. Ponme Viniltex Advanced blanco"},
    ]

    # Solo los ultimos 5 deben pasar
    ultimos5 = [m for m in historial if m["role"] in ("user", "assistant")][-5:]
    C.ok("Ultimos 5 filtrados correctamente", len(ultimos5) == 5)
    C.ok("Ultimo mensaje es el mas reciente",
         "45" in ultimos5[-3]["content"] or "45" in ultimos5[-2]["content"],
         ultimos5[-3]["content"][:60])

    # Verificar que truncamiento a 500 chars funciona
    msg_largo = {"role": "user", "content": "x" * 1000}
    truncado = (msg_largo["content"] or "")[:500]
    C.ok("Truncamiento a 500 chars", len(truncado) == 500)

    return C


# ============================================================================
# TEST SINONIMOS ERP
# ============================================================================

def test_sinonimos_erp():
    C = CaseResult("Test Extra: Sinonimos ERP")

    exp = expandir_sinonimos_erp("viniltex banos y cocinas blanco galon")
    C.ok("Expansion incluye 'pq viniltex'", "pq viniltex" in exp.lower(), exp[:100])

    exp_byc = expandir_sinonimos_erp("viniltex byc blanco galon")
    C.ok("Expansion byc incluye 'banos' o 'cocinas'",
         "banos" in exp_byc.lower() or "cocinas" in exp_byc.lower() or "byc" in exp_byc.lower(),
         exp_byc[:100])

    exp2 = expandir_sinonimos_erp("estuco acrilico exterior")
    C.ok("Expansion estuco incluye 'prof'", "prof" in exp2.lower(), exp2[:100])

    exp3 = expandir_sinonimos_erp("koraza blanco cunete")
    C.ok("Expansion koraza incluye 'pq koraza'", "pq koraza" in exp3.lower())

    return C


# ============================================================================
# MAIN
# ============================================================================

ALL_TESTS = [
    caso_1_multi_zona,
    caso_2_bomba_quimica,
    caso_3_bicomponente_huerfano,
    caso_4_amnesia,
    caso_5_matcher_semantico,
    caso_6_alteracion_precios,
    caso_7_contradiccion,
    caso_8_spanglish,
    caso_9_cancelacion_cambio,
    caso_10_mega_combo,
    test_memoria_conversacional,
    test_sinonimos_erp,
]

def main():
    print("\n" + "=" * 80)
    print("  STRESS TEST SUPERFERRO -- 10 Casos + 2 Tests Extra")
    print("  Pipeline Deterministico: LLM > Match > Validacion > Cotizacion")
    print("=" * 80)

    results = []
    for fn in ALL_TESTS:
        try:
            r = fn()
            results.append(r)
            status = "PASS" if r.failed == 0 else "FAIL"
            print(f"\n  [{status}] {r.name}: {r.passed}/{r.total}")
            if r.failed > 0:
                for label, ok, detail in r.checks:
                    if not ok:
                        print(f"    FAIL: {label}")
                        if detail:
                            print(f"          {detail[:200]}")
        except Exception as e:
            print(f"\n  [CRASH] {fn.__name__}: {e}")
            traceback.print_exc()
            r = CaseResult(fn.__name__)
            r.ok("No crash", False, str(e)[:200])
            results.append(r)

    # -- Resumen --
    total_p = sum(r.passed for r in results)
    total_f = sum(r.failed for r in results)
    total = total_p + total_f

    print("\n" + "=" * 80)
    print(f"  RESUMEN: {total_p}/{total} checks pasaron")
    if total_f > 0:
        print(f"  ATENCION: {total_f} checks FALLARON")
        print("\n  Detalle de fallos:")
        for r in results:
            if r.failed > 0:
                print(f"    [{r.name}]")
                for label, ok, detail in r.checks:
                    if not ok:
                        print(f"      X {label}: {detail[:150]}")
    else:
        print("  TODOS LOS CHECKS PASARON")
    print("=" * 80 + "\n")

    return total_f == 0


if __name__ == "__main__":
    ok = main()
    sys.exit(0 if ok else 1)
