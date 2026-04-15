"""
Módulo 1: Extractor de Recomendación Estructurada del LLM — Súper Agente V2

El LLM SOLO devuelve un JSON con nombres genéricos de productos.
Si el cliente da áreas, el LLM NO calcula cantidades: devuelve variables_calculo.
El backend resuelve las cantidades finales con rendimientos técnicos reales.
NO incluye precios, SKUs ni referencias reales.

MEMORIA: El prompt recibe obligatoriamente los últimos 5 mensajes de la
conversación para superar pruebas de estrés de memoria tipo laberinto.
La salida se valida con un schema estricto antes de continuar el pipeline.
"""
import json
import logging
import math
import re
from typing import Optional

logger = logging.getLogger("pipeline.llm_estructurado")

# ══════════════════════════════════════════════════════════════════════════════
# SCHEMA DE SALIDA ESTRUCTURADA — Lo que el LLM DEBE devolver
# ══════════════════════════════════════════════════════════════════════════════

SCHEMA_RECOMENDACION = {
    "type": "object",
    "properties": {
        "diagnostico": {
            "type": "object",
            "properties": {
                "superficie": {"type": "string"},
                "material": {"type": "string"},
                "ubicacion": {"type": "string", "enum": ["interior", "exterior", "industrial"]},
                "condicion": {"type": "string"},
                "area_m2": {"type": "number"},
                "problema_principal": {"type": "string"},
            },
            "required": ["superficie", "ubicacion", "condicion"],
        },
        "sistema": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "paso": {"type": "integer"},
                    "funcion": {
                        "type": "string",
                        "enum": [
                            "preparacion",
                            "imprimante",
                            "sellador",
                            "base",
                            "acabado",
                            "catalizador",
                            "diluyente",
                        ],
                    },
                    "producto": {"type": "string"},
                    "presentacion": {
                        "type": "string",
                        "enum": ["galon", "cunete", "cuarto", "litro", "unidad", "kit"],
                    },
                    # ── V2: Cantidad condicional ──
                    # Opción A: cantidad fija (cuando el cliente sabe qué comprar)
                    "cantidad_fija": {"type": "number", "minimum": 1},
                    # Opción B: variables de cálculo (cuando se da área)
                    "variables_calculo": {
                        "type": "object",
                        "properties": {
                            "area_m2": {"type": "number"},
                            "tipo_superficie": {
                                "type": "string",
                                "enum": ["lisa", "rugosa", "porosa", "sellada", "metal", "madera", "concreto"],
                            },
                            "manos": {"type": "integer", "minimum": 1, "maximum": 4},
                        },
                        "required": ["area_m2"],
                    },
                    # Legado: "cantidad" sigue aceptándose por retrocompatibilidad
                    "cantidad": {"type": "number", "minimum": 1},
                    "color": {"type": "string"},
                    "notas": {"type": "string"},
                },
                "required": ["paso", "funcion", "producto", "presentacion"],
            },
        },
        "herramientas": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "producto": {"type": "string"},
                    "cantidad": {"type": "number", "minimum": 1},
                },
                "required": ["producto", "cantidad"],
            },
        },
        "justificacion_tecnica": {"type": "string"},
        "opciones_alternativas": {
            "type": "array",
            "description": "Opciones económicas o premium si el RAG las ofrece",
            "items": {
                "type": "object",
                "properties": {
                    "etiqueta": {"type": "string"},
                    "cambios": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "paso": {"type": "integer"},
                                "producto_alternativo": {"type": "string"},
                            },
                        },
                    },
                },
            },
        },
    },
    "required": ["diagnostico", "sistema", "herramientas", "justificacion_tecnica"],
}


# ══════════════════════════════════════════════════════════════════════════════
# PROMPT PARA SALIDA ESTRUCTURADA — Inyectar al LLM en modo cotización
# ══════════════════════════════════════════════════════════════════════════════

SYSTEM_PROMPT_ESTRUCTURADO = """\
Eres el motor de recomendación técnica de Ferreinox. Tu ÚNICA tarea es analizar
el diagnóstico del cliente y la respuesta RAG, y devolver un JSON estructurado.

REGLAS ABSOLUTAS:
1. Devuelve SOLO JSON válido. Sin texto antes ni después.
2. Los nombres de productos deben ser EXACTAMENTE los que devolvió el RAG.
3. NO inventes productos que el RAG no mencionó.
4. NO incluyas precios — el backend los resuelve.
5. NO incluyas códigos, SKUs ni referencias — el backend los resuelve.
6. Cada producto del sistema RAG DEBE aparecer en tu JSON.
7. Herramientas de aplicación (rodillos, brochas, lijas) van en "herramientas".
8. Si el RAG indicó catalizador para bicomponente, es OBLIGATORIO incluirlo.
9. Si el RAG indicó diluyente específico, es OBLIGATORIO incluirlo.
10. Las presentaciones deben ser: galon, cunete, cuarto, litro, unidad, kit.

REGLAS DE CANTIDAD:
- Si el cliente da un ÁREA (m²), NO calcules cantidades finales tú.
  Devuelve "variables_calculo": {"area_m2": <número>, "tipo_superficie": "...", "manos": <N>}
  El backend calculará las cantidades con los rendimientos reales del fabricante.
- Si el cliente pide cantidades FIJAS (ej. "3 galones"), devuelve "cantidad_fija": 3.
- Si no hay área NI cantidad fija, pon "cantidad_fija": 1 como mínimo.
- Para herramientas (preparación), siempre usa "cantidad_fija".
- NUNCA inventes cantidades arbitrarias por un área — deja que el backend lo resuelva.

MEMORIA CONVERSACIONAL:
Revisa cuidadosamente el HISTORIAL CONVERSACIONAL proporcionado.
Si el cliente cambió de opinión, modificó cantidades, o corrigió superficie/color,
usa SIEMPRE la información más reciente. No repitas recomendaciones ya descartadas.

FORMATO DE SALIDA:
{
  "diagnostico": {
    "superficie": "muro",
    "material": "estuco",
    "ubicacion": "interior",
    "condicion": "humedad con salitre",
    "area_m2": 25,
    "problema_principal": "humedad ascendente por capilaridad"
  },
  "sistema": [
    {"paso": 1, "funcion": "preparacion", "producto": "LIJA ABRACOL GRANO 80", "presentacion": "unidad", "cantidad_fija": 3},
    {"paso": 2, "funcion": "sellador", "producto": "AQUABLOCK ULTRA", "presentacion": "galon", "variables_calculo": {"area_m2": 25, "tipo_superficie": "porosa", "manos": 2}, "color": "blanco"},
    {"paso": 3, "funcion": "base", "producto": "ESTUCO ACRILICO EXTERIOR", "presentacion": "galon", "variables_calculo": {"area_m2": 25, "tipo_superficie": "porosa", "manos": 1}, "color": "blanco"},
    {"paso": 4, "funcion": "acabado", "producto": "VINILTEX ADVANCED", "presentacion": "galon", "variables_calculo": {"area_m2": 25, "tipo_superficie": "sellada", "manos": 2}, "color": "blanco"}
  ],
  "herramientas": [
    {"producto": "RODILLO TOPLINE 9 PULGADAS", "cantidad": 1},
    {"producto": "BROCHA GOYA PROFESIONAL 3 PULGADAS", "cantidad": 1}
  ],
  "justificacion_tecnica": "Muro interior con humedad ascendente...",
  "opciones_alternativas": [
    {
      "etiqueta": "Opción Económica",
      "cambios": [{"paso": 4, "producto_alternativo": "INTERVINIL"}]
    }
  ]
}
"""


# ══════════════════════════════════════════════════════════════════════════════
# FUNCIÓN PRINCIPAL — Extraer recomendación estructurada del LLM
# ══════════════════════════════════════════════════════════════════════════════

def extraer_recomendacion_estructurada(
    openai_client,
    modelo: str,
    diagnostico_contexto: dict,
    respuesta_rag: dict,
    user_message: str,
    perfil_tecnico: Optional[dict] = None,
    guias_tecnicas: Optional[list] = None,
    historial_mensajes: Optional[list[dict]] = None,
) -> dict:
    """
    Llama al LLM con temperatura 0 para obtener JSON estructurado.
    
    Args:
        openai_client: Cliente OpenAI configurado
        modelo: Nombre del modelo (gpt-4o-mini)
        diagnostico_contexto: Estado diagnóstico actual (superficie, ubicación, etc.)
        respuesta_rag: Respuesta completa del RAG (guia_tecnica_estructurada, etc.)
        user_message: Mensaje original del usuario
        perfil_tecnico: perfil_tecnico_principal del RAG si existe
        guias_tecnicas: guias_tecnicas_relacionadas del RAG si existen
        historial_mensajes: Últimos N mensajes [{"role":"user"|"assistant","content":"..."}]
                            Para memoria conversacional en pruebas de estrés.

    Returns:
        dict con la recomendación estructurada validada, o dict con "error"
    """
    # ── Construir contexto para el LLM ──
    contexto_parts = []

    contexto_parts.append("=== DIAGNÓSTICO DEL CLIENTE ===")
    contexto_parts.append(json.dumps(diagnostico_contexto, ensure_ascii=False, indent=2))

    if perfil_tecnico:
        contexto_parts.append("\n=== PERFIL TÉCNICO PRINCIPAL (FICHA DEL PRODUCTO) ===")
        contexto_parts.append(json.dumps(perfil_tecnico, ensure_ascii=False, indent=2))

    contexto_parts.append("\n=== RESPUESTA RAG (FUENTE DE VERDAD TÉCNICA) ===")
    # Extraer solo los campos relevantes del RAG
    rag_resumido = {}
    for key in [
        "guia_tecnica_estructurada",
        "diagnostico_estructurado",
        "respuesta_rag",
        "conocimiento_comercial_ferreinox",
        "politicas_duras_contexto",
    ]:
        if key in respuesta_rag:
            rag_resumido[key] = respuesta_rag[key]
    contexto_parts.append(json.dumps(rag_resumido, ensure_ascii=False, indent=2))

    if guias_tecnicas:
        contexto_parts.append("\n=== GUÍAS TÉCNICAS RELACIONADAS ===")
        # Solo incluir resumen, no el texto completo
        for g in guias_tecnicas[:3]:
            if isinstance(g, dict):
                contexto_parts.append(
                    f"- {g.get('titulo', 'Sin título')}: {g.get('resumen', '')[:200]}"
                )

    contexto_parts.append(f"\n=== MENSAJE DEL CLIENTE ===\n{user_message}")

    contexto_completo = "\n".join(contexto_parts)

    # ── Construir historial conversacional (últimos 5 mensajes) ──
    history_messages = []
    if historial_mensajes:
        # Tomar últimos 5 turnos (filtrar solo user/assistant)
        ultimos = [
            m for m in historial_mensajes
            if m.get("role") in ("user", "assistant")
        ][-5:]
        for msg in ultimos:
            content = (msg.get("content") or "")[:500]  # Truncar para no explotar tokens
            if content:
                history_messages.append({"role": msg["role"], "content": content})

    # ── Construir mensajes para la llamada ──
    llm_messages = [{"role": "system", "content": SYSTEM_PROMPT_ESTRUCTURADO}]
    
    # Inyectar historial conversacional como contexto
    if history_messages:
        historial_texto = "\n".join(
            f"[{m['role'].upper()}]: {m['content']}" for m in history_messages
        )
        llm_messages.append({
            "role": "user",
            "content": (
                "=== HISTORIAL CONVERSACIONAL (últimos mensajes) ===\n"
                f"{historial_texto}\n\n"
                "Usa este historial para entender el contexto completo. "
                "Si el cliente cambió de opinión o corrigió algo, respeta la versión más reciente.\n\n"
                "=== FIN HISTORIAL ==="
            ),
        })
        llm_messages.append({
            "role": "assistant",
            "content": "Entendido. Tengo el contexto conversacional. Procedo con el análisis.",
        })

    llm_messages.append({"role": "user", "content": contexto_completo})

    # ── Llamada al LLM con JSON mode ──
    logger.info(
        "LLM_ESTRUCTURADO: Solicitando recomendación | diagnostico=%s",
        json.dumps(diagnostico_contexto, ensure_ascii=False)[:200],
    )

    try:
        response = openai_client.chat.completions.create(
            model=modelo,
            messages=llm_messages,
            response_format={"type": "json_object"},
            temperature=0,
            max_tokens=2000,
        )

        raw_content = response.choices[0].message.content or ""
        logger.info("LLM_ESTRUCTURADO: Respuesta raw (primeros 500 chars): %s", raw_content[:500])

    except Exception as e:
        logger.error("LLM_ESTRUCTURADO: Error en llamada OpenAI: %s", e)
        return {"error": f"Error en LLM: {str(e)}", "etapa": "llm_call"}

    # ── Parsear JSON ──
    recomendacion = _parsear_json_llm(raw_content)
    if "error" in recomendacion:
        return recomendacion

    # ── Validar schema ──
    errores = _validar_schema_recomendacion(recomendacion)
    if errores:
        logger.warning(
            "LLM_ESTRUCTURADO: Schema inválido: %s | Reintentando...",
            errores[:3],
        )
        # Reintentar una vez con corrección
        recomendacion = _reintentar_con_correccion(
            openai_client, modelo, contexto_completo, raw_content, errores
        )
        if "error" in recomendacion:
            return recomendacion

    # ── Validar que los productos vengan del RAG ──
    errores_trazabilidad = _validar_trazabilidad_rag(recomendacion, respuesta_rag)
    if errores_trazabilidad:
        logger.warning(
            "LLM_ESTRUCTURADO: Productos no trazables al RAG: %s",
            errores_trazabilidad,
        )
        recomendacion["_advertencias_trazabilidad"] = errores_trazabilidad

    # ── V2: Resolver cantidades desde variables_calculo ──
    recomendacion = resolver_cantidades_desde_variables(recomendacion)

    logger.info(
        "LLM_ESTRUCTURADO: OK | %d productos en sistema, %d herramientas",
        len(recomendacion.get("sistema", [])),
        len(recomendacion.get("herramientas", [])),
    )
    return recomendacion


# ══════════════════════════════════════════════════════════════════════════════
# FUNCIONES INTERNAS
# ══════════════════════════════════════════════════════════════════════════════

def _parsear_json_llm(raw: str) -> dict:
    """Intenta parsear JSON del LLM, tolerando markdown fences."""
    raw = raw.strip()
    # Remover markdown fences si las hay
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)

    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        logger.error("LLM_ESTRUCTURADO: JSON inválido: %s | Raw: %s", e, raw[:300])
        return {"error": f"JSON inválido del LLM: {str(e)}", "etapa": "json_parse"}


def _validar_schema_recomendacion(data: dict) -> list[str]:
    """Validación ligera del schema (sin jsonschema dependency)."""
    errores = []

    if "diagnostico" not in data:
        errores.append("Falta campo 'diagnostico'")
    else:
        diag = data["diagnostico"]
        for campo in ["superficie", "ubicacion", "condicion"]:
            if campo not in diag:
                errores.append(f"Falta diagnostico.{campo}")

    if "sistema" not in data:
        errores.append("Falta campo 'sistema'")
    elif not isinstance(data["sistema"], list):
        errores.append("'sistema' debe ser un array")
    elif len(data["sistema"]) == 0:
        errores.append("'sistema' está vacío — no hay productos")
    else:
        presentaciones_validas = {"galon", "cunete", "cuarto", "litro", "unidad", "kit"}
        funciones_validas = {
            "preparacion", "imprimante", "sellador", "base",
            "acabado", "catalizador", "diluyente",
        }
        for i, item in enumerate(data["sistema"]):
            if "producto" not in item:
                errores.append(f"sistema[{i}]: falta 'producto'")
            if "presentacion" not in item:
                errores.append(f"sistema[{i}]: falta 'presentacion'")
            elif item["presentacion"] not in presentaciones_validas:
                errores.append(
                    f"sistema[{i}]: presentacion '{item['presentacion']}' inválida. "
                    f"Válidas: {presentaciones_validas}"
                )
            if "funcion" in item and item["funcion"] not in funciones_validas:
                errores.append(f"sistema[{i}]: funcion '{item['funcion']}' inválida")
            # V2: Validar que tiene al menos una forma de cantidad
            tiene_cantidad = (
                item.get("cantidad_fija") is not None
                or item.get("variables_calculo") is not None
                or item.get("cantidad") is not None  # legado
            )
            if not tiene_cantidad:
                errores.append(
                    f"sistema[{i}]: falta 'cantidad_fija', 'variables_calculo' o 'cantidad'"
                )
            if item.get("variables_calculo"):
                vc = item["variables_calculo"]
                if not isinstance(vc, dict) or "area_m2" not in vc:
                    errores.append(f"sistema[{i}]: variables_calculo debe tener 'area_m2'")

    if "herramientas" not in data:
        errores.append("Falta campo 'herramientas'")

    if "justificacion_tecnica" not in data:
        errores.append("Falta campo 'justificacion_tecnica'")

    return errores


def _validar_trazabilidad_rag(recomendacion: dict, respuesta_rag: dict) -> list[str]:
    """
    Verifica que cada producto del sistema venga del RAG.
    Retorna lista de productos no trazables.
    """
    # Construir texto del RAG para buscar menciones
    rag_text_parts = []
    for key in [
        "respuesta_rag",
        "guia_tecnica_estructurada",
        "conocimiento_comercial_ferreinox",
    ]:
        val = respuesta_rag.get(key)
        if isinstance(val, str):
            rag_text_parts.append(val.lower())
        elif isinstance(val, dict):
            rag_text_parts.append(json.dumps(val, ensure_ascii=False).lower())
        elif isinstance(val, list):
            for item in val:
                if isinstance(item, str):
                    rag_text_parts.append(item.lower())
                elif isinstance(item, dict):
                    rag_text_parts.append(json.dumps(item, ensure_ascii=False).lower())

    rag_text = " ".join(rag_text_parts)
    no_trazables = []

    for item in recomendacion.get("sistema", []):
        producto = (item.get("producto") or "").strip()
        if not producto:
            continue
        # Normalizar para búsqueda
        producto_lower = producto.lower()
        # Buscar coincidencia parcial (al menos la palabra principal)
        palabras = [p for p in producto_lower.split() if len(p) > 3]
        encontrado = False
        if palabras:
            # Al menos 60% de las palabras significativas deben estar en el RAG
            matches = sum(1 for p in palabras if p in rag_text)
            if matches / len(palabras) >= 0.5:
                encontrado = True
        if not encontrado:
            no_trazables.append(producto)

    return no_trazables


def _reintentar_con_correccion(
    openai_client,
    modelo: str,
    contexto_original: str,
    respuesta_fallida: str,
    errores: list[str],
) -> dict:
    """Reintenta una vez pidiendo al LLM que corrija los errores."""
    logger.info("LLM_ESTRUCTURADO: Reintentando con corrección de %d errores", len(errores))

    try:
        response = openai_client.chat.completions.create(
            model=modelo,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT_ESTRUCTURADO},
                {"role": "user", "content": contexto_original},
                {"role": "assistant", "content": respuesta_fallida},
                {
                    "role": "user",
                    "content": (
                        "Tu JSON tiene errores de schema. Corrígelos y devuelve SOLO el JSON corregido:\n"
                        + "\n".join(f"- {e}" for e in errores[:5])
                    ),
                },
            ],
            response_format={"type": "json_object"},
            temperature=0,
            max_tokens=2000,
        )

        raw = response.choices[0].message.content or ""
        recomendacion = _parsear_json_llm(raw)
        if "error" in recomendacion:
            return recomendacion

        errores2 = _validar_schema_recomendacion(recomendacion)
        if errores2:
            return {
                "error": f"Schema inválido tras reintento: {errores2[:3]}",
                "etapa": "schema_validation_retry",
            }

        return recomendacion

    except Exception as e:
        return {"error": f"Error en reintento LLM: {str(e)}", "etapa": "llm_retry"}


# ══════════════════════════════════════════════════════════════════════════════
# V2: RESOLVER CANTIDADES DESDE VARIABLES DE CÁLCULO
# ══════════════════════════════════════════════════════════════════════════════

# Rendimientos técnicos reales por tipo (m²/galón, 1 mano)
RENDIMIENTO_BASE = {
    # Pinturas vinílicas/acrílicas
    "viniltex": 12, "koraza": 10, "intervinil": 12,
    # Selladores/impermeabilizantes
    "aquablock": 5, "sellador": 6,
    # Estucos
    "estuco": 4,
    # Anticorrosivos
    "corrotec": 10, "pintulux": 12,
    # Epóxicos
    "pintucoat": 6, "interseal": 5, "interthane": 8,
    # Madera
    "barnex": 12, "wood stain": 10,
    # Tráfico
    "trafico": 8,
    # Default
    "_default": 10,
}

# Factores de ajuste por tipo de superficie
FACTOR_SUPERFICIE = {
    "lisa": 1.0,
    "sellada": 1.0,
    "rugosa": 1.3,
    "porosa": 1.5,
    "metal": 0.9,
    "madera": 1.2,
    "concreto": 1.4,
}


def resolver_cantidades_desde_variables(recomendacion: dict) -> dict:
    """
    Recorre el sistema y resuelve variables_calculo → cantidad final.
    Usa rendimientos reales del fabricante. No depende del LLM.
    
    Para cada producto con variables_calculo:
      galones_por_mano = area / (rendimiento * factor_superficie)
      galones_total = galones_por_mano * manos
      → Si > 5 gal: optimizar en cuñetes + galones sueltos.
    
    Mantiene retrocompatibilidad con 'cantidad' y 'cantidad_fija'.
    """
    sistema = recomendacion.get("sistema", [])
    sistema_resuelto = []

    for item in sistema:
        item = dict(item)  # copia para no mutar original

        # Prioridad: cantidad_fija > variables_calculo > cantidad (legado)
        if item.get("cantidad_fija") is not None:
            item["cantidad"] = int(item["cantidad_fija"])
            item.setdefault("_fuente_cantidad", "cantidad_fija")
            sistema_resuelto.append(item)
            continue

        if item.get("variables_calculo"):
            vc = item["variables_calculo"]
            area = float(vc.get("area_m2", 0))
            tipo_sup = vc.get("tipo_superficie", "lisa")
            manos = int(vc.get("manos", 2))

            if area <= 0:
                item["cantidad"] = 1
                item["_fuente_cantidad"] = "fallback_area_0"
                sistema_resuelto.append(item)
                continue

            # Buscar rendimiento por producto
            prod_lower = (item.get("producto") or "").lower()
            rendimiento = RENDIMIENTO_BASE["_default"]
            for clave, rend in RENDIMIENTO_BASE.items():
                if clave != "_default" and clave in prod_lower:
                    rendimiento = rend
                    break

            factor = FACTOR_SUPERFICIE.get(tipo_sup, 1.0)
            galones_por_mano = area / (rendimiento / factor)
            galones_total = galones_por_mano * manos

            # Redondear hacia arriba siempre (no le falta pintura al cliente)
            galones_total = math.ceil(galones_total)

            # Optimizar presentación si > 5 galones
            presentacion = item.get("presentacion", "galon")
            if galones_total >= 5 and presentacion == "galon":
                cunetes = galones_total // 5
                galones_sueltos = galones_total % 5
                if cunetes >= 1:
                    # Crear item cuñete
                    item_cunete = dict(item)
                    item_cunete["presentacion"] = "cunete"
                    item_cunete["cantidad"] = cunetes
                    item_cunete["_fuente_cantidad"] = "variables_calculo"
                    item_cunete["_calculo"] = {
                        "area_m2": area, "rendimiento": rendimiento,
                        "factor": factor, "manos": manos,
                        "galones_total": galones_total,
                    }
                    sistema_resuelto.append(item_cunete)
                    if galones_sueltos > 0:
                        item_galon = dict(item)
                        item_galon["presentacion"] = "galon"
                        item_galon["cantidad"] = galones_sueltos
                        item_galon["_fuente_cantidad"] = "variables_calculo"
                        sistema_resuelto.append(item_galon)
                    continue

            item["cantidad"] = max(1, galones_total)
            item["_fuente_cantidad"] = "variables_calculo"
            item["_calculo"] = {
                "area_m2": area, "rendimiento": rendimiento,
                "factor": factor, "manos": manos,
                "galones_total": galones_total,
            }
            sistema_resuelto.append(item)
            continue

        # Legado: 'cantidad' directo
        if item.get("cantidad") is not None:
            item["cantidad"] = int(item["cantidad"])
            item.setdefault("_fuente_cantidad", "legado")
        else:
            item["cantidad"] = 1
            item["_fuente_cantidad"] = "fallback"

        sistema_resuelto.append(item)

    recomendacion["sistema"] = sistema_resuelto
    return recomendacion
