"""
Módulo 5: Pipeline Orquestador — Control de flujo determinístico con trazabilidad

Este es el módulo central que orquesta todo el pipeline:
  usuario → diagnóstico → JSON LLM → match inventario → validación → cotización

Cada paso tiene logging completo para debugging en producción.
El LLM SOLO participa en el paso de diagnóstico/recomendación estructurada.
Todo lo demás es determinístico.
"""
import json
import logging
import time
import uuid
from datetime import datetime
from typing import Optional, Callable

from .llm_estructurado import extraer_recomendacion_estructurada
from .matcher_productos import match_sistema_completo
from .generador_cotizacion import (
    generar_respuesta_cotizacion_whatsapp,
    generar_payload_pdf,
)
from .validaciones import ejecutar_validacion_completa

logger = logging.getLogger("pipeline.orquestador")


# ══════════════════════════════════════════════════════════════════════════════
# TRACE — Trazabilidad completa de cada paso
# ══════════════════════════════════════════════════════════════════════════════

class PipelineTrace:
    """Registra cada paso del pipeline para debugging en producción."""

    def __init__(self, conversation_id: str, user_message: str):
        self.trace_id = str(uuid.uuid4())[:8]
        self.conversation_id = conversation_id
        self.user_message = user_message
        self.started_at = datetime.now()
        self.steps: list[dict] = []
        self.result: Optional[str] = None  # "exito", "error", "bloqueado"

    def log_step(
        self,
        paso: str,
        status: str,
        duracion_ms: int,
        data: Optional[dict] = None,
        error: Optional[str] = None,
    ):
        step = {
            "paso": paso,
            "status": status,
            "duracion_ms": duracion_ms,
            "timestamp": datetime.now().isoformat(),
        }
        if data:
            # Truncar para no explotar los logs
            step["data"] = _truncar_para_log(data)
        if error:
            step["error"] = error[:500]
        self.steps.append(step)

        log_fn = logger.info if status == "ok" else logger.error
        log_fn(
            "TRACE[%s] conv=%s | %s → %s | %dms%s",
            self.trace_id,
            self.conversation_id,
            paso,
            status,
            duracion_ms,
            f" | error={error[:100]}" if error else "",
        )

    def finalizar(self, result: str):
        self.result = result
        duracion_total = int((datetime.now() - self.started_at).total_seconds() * 1000)
        logger.info(
            "TRACE[%s] conv=%s | PIPELINE %s | total=%dms | pasos=%d",
            self.trace_id,
            self.conversation_id,
            result.upper(),
            duracion_total,
            len(self.steps),
        )

    def to_dict(self) -> dict:
        return {
            "trace_id": self.trace_id,
            "conversation_id": self.conversation_id,
            "user_message": self.user_message[:200],
            "started_at": self.started_at.isoformat(),
            "result": self.result,
            "steps": self.steps,
        }


# ══════════════════════════════════════════════════════════════════════════════
# PIPELINE PRINCIPAL
# ══════════════════════════════════════════════════════════════════════════════

def ejecutar_pipeline_cotizacion(
    openai_client,
    modelo: str,
    diagnostico_contexto: dict,
    respuesta_rag: dict,
    user_message: str,
    conversation_id: str,
    lookup_fn: Callable,
    price_fn: Optional[Callable] = None,
    nombre_cliente: str = "",
    perfil_tecnico: Optional[dict] = None,
    guias_tecnicas: Optional[list] = None,
) -> dict:
    """
    Pipeline determinístico completo:
      1. LLM → JSON estructurado (diagnóstico + recomendación)
      2. Backend → Match contra inventario real
      3. Validaciones → Gate de calidad
      4. Generador → Cotización sin LLM

    Args:
        openai_client: Cliente OpenAI
        modelo: Nombre del modelo
        diagnostico_contexto: Estado diagnóstico actual
        respuesta_rag: Respuesta completa del RAG
        user_message: Mensaje original del usuario
        conversation_id: ID de conversación para traza
        lookup_fn: Función que busca en inventario (recibe str, retorna list[dict])
        price_fn: Función que obtiene precio por código
        nombre_cliente: Nombre del cliente
        perfil_tecnico: Perfil técnico principal del RAG
        guias_tecnicas: Guías técnicas relacionadas

    Returns:
        {
            "exito": bool,
            "respuesta_whatsapp": str,  # Texto formateado para WhatsApp
            "payload_pdf": dict | None,  # Datos para generar PDF
            "trace": dict,  # Traza completa del pipeline
            "recomendacion_llm": dict,  # JSON del LLM (para auditoría)
            "match_result": dict,  # Resultado del match (para auditoría)
            "validacion": dict,  # Resultado de validaciones
        }
    """
    trace = PipelineTrace(conversation_id, user_message)

    # ═══════════════════════════════════════════════════════════════════════
    # PASO 1: LLM → Recomendación Estructurada (JSON)
    # ═══════════════════════════════════════════════════════════════════════
    t0 = time.time()
    logger.info(
        "PIPELINE[%s]: Paso 1 — Extrayendo recomendación del LLM",
        trace.trace_id,
    )

    recomendacion = extraer_recomendacion_estructurada(
        openai_client=openai_client,
        modelo=modelo,
        diagnostico_contexto=diagnostico_contexto,
        respuesta_rag=respuesta_rag,
        user_message=user_message,
        perfil_tecnico=perfil_tecnico,
        guias_tecnicas=guias_tecnicas,
    )

    duracion_llm = int((time.time() - t0) * 1000)

    if "error" in recomendacion:
        trace.log_step(
            "llm_estructurado", "error", duracion_llm,
            error=recomendacion["error"],
        )
        trace.finalizar("error")
        return {
            "exito": False,
            "respuesta_whatsapp": (
                "⚠️ Hubo un problema técnico procesando tu solicitud. "
                "Déjame conectarte con nuestro Asesor Técnico para ayudarte. ¿Te parece?"
            ),
            "payload_pdf": None,
            "trace": trace.to_dict(),
            "recomendacion_llm": recomendacion,
            "match_result": None,
            "validacion": None,
        }

    trace.log_step(
        "llm_estructurado", "ok", duracion_llm,
        data={
            "productos_en_sistema": len(recomendacion.get("sistema", [])),
            "herramientas": len(recomendacion.get("herramientas", [])),
            "tiene_alternativas": bool(recomendacion.get("opciones_alternativas")),
        },
    )

    # Loggear JSON completo del LLM para post-mortem
    logger.info(
        "PIPELINE[%s]: Recomendación LLM completa: %s",
        trace.trace_id,
        json.dumps(recomendacion, ensure_ascii=False)[:2000],
    )

    # ═══════════════════════════════════════════════════════════════════════
    # PASO 2: Backend → Match contra Inventario Real
    # ═══════════════════════════════════════════════════════════════════════
    t0 = time.time()
    logger.info(
        "PIPELINE[%s]: Paso 2 — Match contra inventario",
        trace.trace_id,
    )

    match_result = match_sistema_completo(
        recomendacion=recomendacion,
        lookup_fn=lookup_fn,
        price_fn=price_fn,
    )

    duracion_match = int((time.time() - t0) * 1000)

    trace.log_step(
        "match_inventario",
        "ok" if match_result.get("exito") else "parcial",
        duracion_match,
        data=match_result.get("resumen"),
    )

    # Loggear resultado del match para post-mortem
    logger.info(
        "PIPELINE[%s]: Match result: %s",
        trace.trace_id,
        json.dumps(match_result.get("resumen", {}), ensure_ascii=False),
    )

    # ═══════════════════════════════════════════════════════════════════════
    # PASO 3: Validaciones (GATE de calidad)
    # ═══════════════════════════════════════════════════════════════════════
    t0 = time.time()
    logger.info(
        "PIPELINE[%s]: Paso 3 — Validaciones de calidad",
        trace.trace_id,
    )

    validacion = ejecutar_validacion_completa(recomendacion, match_result, respuesta_rag)

    duracion_validacion = int((time.time() - t0) * 1000)

    trace.log_step(
        "validaciones",
        "ok" if validacion.valido else "bloqueado",
        duracion_validacion,
        data=validacion.to_dict(),
    )

    if not validacion.valido:
        trace.finalizar("bloqueado")
        logger.error(
            "PIPELINE[%s]: BLOQUEADO por validaciones: %s",
            trace.trace_id,
            validacion.errores,
        )
        # Usar ValidationFeedback proactivo si existe
        blocking_feedbacks = validacion.blocking_feedbacks
        if blocking_feedbacks:
            # El primer feedback bloqueante tiene el suggested_message más relevante
            primary_feedback = blocking_feedbacks[0]
            suggested_msg = primary_feedback.suggested_message
        else:
            suggested_msg = ""

        return {
            "exito": False,
            "bloqueado_por_validacion": True,
            "respuesta_whatsapp": suggested_msg or _generar_respuesta_bloqueo(validacion, match_result),
            "suggested_message": suggested_msg,
            "suggested_action": blocking_feedbacks[0].suggested_action if blocking_feedbacks else "",
            "feedbacks": [f.to_dict() for f in validacion.feedbacks],
            "payload_pdf": None,
            "trace": trace.to_dict(),
            "recomendacion_llm": recomendacion,
            "match_result": match_result,
            "validacion": validacion.to_dict(),
        }

    # ═══════════════════════════════════════════════════════════════════════
    # PASO 4: Generar Cotización (SIN LLM — determinístico)
    # ═══════════════════════════════════════════════════════════════════════
    t0 = time.time()
    logger.info(
        "PIPELINE[%s]: Paso 4 — Generando cotización determinística",
        trace.trace_id,
    )

    diagnostico = recomendacion.get("diagnostico", {})
    justificacion = recomendacion.get("justificacion_tecnica", "")

    respuesta_whatsapp = generar_respuesta_cotizacion_whatsapp(
        match_result=match_result,
        diagnostico=diagnostico,
        justificacion=justificacion,
        nombre_cliente=nombre_cliente,
    )

    payload_pdf = generar_payload_pdf(
        match_result=match_result,
        diagnostico=diagnostico,
        justificacion=justificacion,
        nombre_despacho=nombre_cliente,
        tipo_documento="cotizacion",
        conversation_id=conversation_id,
    )

    duracion_gen = int((time.time() - t0) * 1000)

    trace.log_step(
        "generacion_cotizacion", "ok", duracion_gen,
        data={
            "len_respuesta": len(respuesta_whatsapp),
            "items_pdf": len(payload_pdf.get("items", [])),
        },
    )

    # ═══════════════════════════════════════════════════════════════════════
    # PASO 5: Log de advertencias (no bloquean pero se registran)
    # ═══════════════════════════════════════════════════════════════════════
    if validacion.advertencias:
        logger.warning(
            "PIPELINE[%s]: Cotización generada con %d advertencias: %s",
            trace.trace_id,
            len(validacion.advertencias),
            validacion.advertencias,
        )

    trace.finalizar("exito")

    return {
        "exito": True,
        "bloqueado_por_validacion": False,
        "respuesta_whatsapp": respuesta_whatsapp,
        "payload_pdf": payload_pdf,
        "trace": trace.to_dict(),
        "recomendacion_llm": recomendacion,
        "match_result": match_result,
        "validacion": validacion.to_dict(),
        "feedbacks": [f.to_dict() for f in validacion.feedbacks] if validacion.feedbacks else [],
    }


# ══════════════════════════════════════════════════════════════════════════════
# FUNCIÓN DE CONVENIENCIA — Para usar desde el agente V3 existente
# ══════════════════════════════════════════════════════════════════════════════

def pipeline_cotizacion_desde_agente(
    main_module,
    openai_client,
    conversation_context: dict,
    user_message: str,
    respuesta_rag: dict,
    conversation_id: str,
) -> dict:
    """
    Wrapper para integrar con el flujo existente de agent_v3.py.
    
    Usa las funciones de lookup y price del main.py existente
    como lookup_fn y price_fn.
    
    Args:
        main_module: Referencia al módulo main.py (para acceder a funciones de inventario)
        openai_client: Cliente OpenAI
        conversation_context: Contexto de conversación existente
        user_message: Mensaje del usuario
        respuesta_rag: Respuesta del RAG
        conversation_id: ID de conversación
    
    Returns:
        dict con resultado del pipeline
    """
    # ── Extraer diagnóstico del contexto de conversación ──
    diagnostic_data = conversation_context.get("diagnostic_data", {})
    diagnostico_contexto = {
        "superficie": diagnostic_data.get("surface_type", ""),
        "material": diagnostic_data.get("surface_material", ""),
        "ubicacion": diagnostic_data.get("location", ""),
        "condicion": diagnostic_data.get("condition", ""),
        "area_m2": diagnostic_data.get("area_m2", 0),
        "problema_principal": diagnostic_data.get("humidity_source", "")
            or diagnostic_data.get("condition", ""),
    }

    # ── Extraer nombre del cliente ──
    nombre_cliente = (
        conversation_context.get("customer_name")
        or conversation_context.get("profile_name")
        or ""
    )

    # ── Crear wrapper de lookup compatible ──
    def lookup_fn(texto_busqueda: str) -> list[dict]:
        """Wrapper que adapta el consultar_inventario existente."""
        try:
            # Usar la función existente del main.py
            args = {
                "nombre_base": texto_busqueda.split()[0] if texto_busqueda.split() else texto_busqueda,
                "variante_o_color": " ".join(texto_busqueda.split()[1:]) if len(texto_busqueda.split()) > 1 else "",
                "modo_consulta": "cotizacion",
            }
            result_str = main_module._handle_tool_consultar_inventario(args, conversation_context)
            result = json.loads(result_str)
            return result.get("productos", [])
        except Exception as e:
            logger.error("lookup_fn error: %s", e)
            return []

    def price_fn(codigo: str) -> Optional[dict]:
        """Wrapper para obtener precio."""
        try:
            if hasattr(main_module, "fetch_product_price"):
                return main_module.fetch_product_price(codigo)
        except Exception as e:
            logger.error("price_fn error: %s", e)
        return None

    # ── Ejecutar pipeline ──
    return ejecutar_pipeline_cotizacion(
        openai_client=openai_client,
        modelo=main_module.get_openai_model(),
        diagnostico_contexto=diagnostico_contexto,
        respuesta_rag=respuesta_rag,
        user_message=user_message,
        conversation_id=conversation_id,
        lookup_fn=lookup_fn,
        price_fn=price_fn,
        nombre_cliente=nombre_cliente,
        perfil_tecnico=respuesta_rag.get("perfil_tecnico_principal"),
        guias_tecnicas=respuesta_rag.get("guias_tecnicas_relacionadas"),
    )


# ══════════════════════════════════════════════════════════════════════════════
# UTILIDADES INTERNAS
# ══════════════════════════════════════════════════════════════════════════════

def _generar_respuesta_bloqueo(validacion, match_result) -> str:
    """Genera respuesta de error controlado cuando las validaciones bloquean."""
    lines = ["⚠️ Detecté un problema con la cotización y prefiero no enviarte datos incorrectos.\n"]

    for error in validacion.errores[:3]:
        # Limpiar prefijos de validación para el cliente
        error_limpio = error.split("] ", 1)[-1] if "] " in error else error
        if "CAMBIO DE PRODUCTO" in error:
            lines.append(
                "🔍 Uno de los productos no coincide exactamente con lo que tenemos en inventario. "
                "Necesito verificar la referencia correcta."
            )
        elif "INCOMPATIBILIDAD QUÍMICA" in error:
            lines.append(
                "⛔ Detecté una incompatibilidad entre productos del sistema. "
                "Necesito ajustar la recomendación."
            )
        elif "BICOMPONENTE INCOMPLETO" in error:
            lines.append(
                "⚗️ Falta el catalizador de un producto bicomponente. "
                "Es obligatorio para que funcione."
            )
        elif "crítico sin match" in error.lower():
            lines.append(
                "📦 Uno de los productos principales no está disponible en nuestro inventario actual."
            )

    lines.append(
        "\nTe conecto con nuestro Asesor Técnico Comercial para completar "
        "tu cotización correctamente. ¿Te parece? 👤"
    )

    return "\n".join(lines)


def _truncar_para_log(data: dict, max_len: int = 500) -> dict:
    """Trunca valores largos en un dict para logging."""
    resultado = {}
    for k, v in data.items():
        if isinstance(v, str) and len(v) > max_len:
            resultado[k] = v[:max_len] + "..."
        elif isinstance(v, (list, dict)):
            s = json.dumps(v, ensure_ascii=False)
            if len(s) > max_len:
                resultado[k] = s[:max_len] + "..."
            else:
                resultado[k] = v
        else:
            resultado[k] = v
    return resultado
