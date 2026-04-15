"""
Módulo 6: Integración del Pipeline Determinístico con Agent V3

Este módulo es el puente entre el flujo existente del agente (agent_v3.py)
y el nuevo pipeline determinístico.

Estrategia de integración:
  - NO reemplaza el agente completo (sería muy disruptivo)
  - INTERCEPTA el flujo en el momento de cotización
  - El LLM sigue haciendo diagnóstico conversacional
  - Pero la cotización pasa por el pipeline determinístico

Punto de inyección:
  - Cuando se detecta intención de cotizar Y el diagnóstico está completo
  - Se invoca el pipeline en lugar de dejar que el LLM arme la cotización

Uso desde agent_v3.py:
  from pipeline_deterministico.integracion import interceptar_cotizacion_si_aplica
  
  # Después del loop de tools, ANTES de las guardias:
  intercepcion = interceptar_cotizacion_si_aplica(...)
  if intercepcion:
      return intercepcion
"""
import json
import logging
import re
import time
from typing import Optional

logger = logging.getLogger("pipeline.integracion")


def interceptar_cotizacion_si_aplica(
    main_module,
    openai_client,
    conversation_context: dict,
    user_message: str,
    tool_calls_made: list[dict],
    context: dict,
    messages: list,
    assistant_message,
) -> Optional[dict]:
    """
    Evalúa si la respuesta actual es una cotización y, de ser así,
    la redirige al pipeline determinístico.

    Condiciones para interceptar:
      1. Se llamó consultar_inventario o consultar_inventario_lote en este turno
      2. La respuesta contiene precios ($ + números)
      3. Hay respuesta RAG disponible (latest_technical_guidance)
      4. NO es empleado interno (ellos hacen pedidos directos)

    Returns:
        dict compatible con el return de generate_agent_reply_v3() si interceptó,
        None si no aplica.
    """
    # ── Guard: No interceptar empleados internos ──
    if conversation_context.get("internal_auth"):
        return None

    # ── Guard: No interceptar si no hay herramientas de inventario llamadas ──
    inventory_tools = {"consultar_inventario", "consultar_inventario_lote"}
    tools_used = {tc["name"] for tc in tool_calls_made}
    if not (tools_used & inventory_tools):
        return None

    # ── Guard: Verificar que hay respuesta RAG disponible ──
    latest_guidance = conversation_context.get("latest_technical_guidance")
    if not latest_guidance:
        logger.info("INTERCEPCIÓN: Sin guidance RAG — no interceptar")
        return None

    # ── Guard: Solo interceptar si la respuesta parece una cotización ──
    response_text = (assistant_message.content or "") if hasattr(assistant_message, "content") else ""
    tiene_precios = bool(re.findall(r'\$[\d.,]+', response_text))

    # También interceptar si se pidió cotización explícitamente
    user_lower = (user_message or "").lower()
    pide_cotizacion = any(
        kw in user_lower
        for kw in ["cotiza", "cotízame", "cotizame", "cuánto", "cuanto cuesta", "precio", "liquidame", "liquídame"]
    )

    if not tiene_precios and not pide_cotizacion:
        return None

    logger.info(
        "INTERCEPCIÓN: Activando pipeline determinístico | tiene_precios=%s pide_cotizacion=%s",
        tiene_precios, pide_cotizacion,
    )

    # ── Construir respuesta RAG del guidance almacenado ──
    respuesta_rag = {}
    if isinstance(latest_guidance, dict):
        respuesta_rag = latest_guidance
    
    # Enriquecer con datos de las tool calls actuales
    for tc in tool_calls_made:
        if tc["name"] == "consultar_conocimiento_tecnico":
            try:
                rag_result = json.loads(tc.get("result", "{}"))
                if isinstance(rag_result, dict):
                    for key in [
                        "guia_tecnica_estructurada",
                        "diagnostico_estructurado",
                        "respuesta_rag",
                        "conocimiento_comercial_ferreinox",
                        "politicas_duras_contexto",
                        "perfil_tecnico_principal",
                        "guias_tecnicas_relacionadas",
                    ]:
                        if key in rag_result and key not in respuesta_rag:
                            respuesta_rag[key] = rag_result[key]
            except (json.JSONDecodeError, TypeError):
                pass

    # ── Ejecutar pipeline ──
    try:
        from .orquestador import pipeline_cotizacion_desde_agente

        t0 = time.time()
        resultado = pipeline_cotizacion_desde_agente(
            main_module=main_module,
            openai_client=openai_client,
            conversation_context=conversation_context,
            user_message=user_message,
            respuesta_rag=respuesta_rag,
            conversation_id=context.get("conversation_id", "unknown"),
        )
        duracion = int((time.time() - t0) * 1000)

        logger.info(
            "INTERCEPCIÓN: Pipeline completado en %dms | exito=%s",
            duracion, resultado.get("exito"),
        )

        if not resultado.get("exito"):
            logger.warning(
                "INTERCEPCIÓN: Pipeline falló — evaluando ValidationFeedback"
            )
            # Si hay errores de cambio de producto, loggear para auditoría
            validacion = resultado.get("validacion", {})
            if validacion and isinstance(validacion, dict):
                for err in validacion.get("errores", []):
                    if "CAMBIO DE PRODUCTO" in err:
                        logger.error("AUDITORÍA: %s", err)

            # ── FRENTE 4: Si hay ValidationFeedback con suggested_message,
            #    NO hacer fallback al LLM. En su lugar, devolver el mensaje
            #    correctivo empático al cliente. ──
            if resultado.get("bloqueado_por_validacion") and resultado.get("suggested_message"):
                suggested = resultado["suggested_message"]
                feedbacks = resultado.get("feedbacks", [])
                
                # Si hay múltiples feedbacks bloqueantes, combinar mensajes
                blocking = [f for f in feedbacks if f.get("status") == "blocked"]
                if len(blocking) > 1:
                    msgs = [f["suggested_message"] for f in blocking if f.get("suggested_message")]
                    suggested = "\n\n".join(msgs[:3])  # Máximo 3 mensajes
                
                logger.info(
                    "INTERCEPCIÓN: Devolviendo mensaje correctivo empático al cliente "
                    "(action=%s, feedbacks=%d)",
                    resultado.get("suggested_action", ""),
                    len(blocking),
                )
                
                # Guardar feedbacks en contexto para que el agente los use
                # en el siguiente turno si el cliente responde
                conversation_context["_pending_validation_feedbacks"] = feedbacks
                conversation_context["_pending_validation_action"] = resultado.get("suggested_action", "")
                
                return _construir_return_agente(
                    suggested,
                    tool_calls_made,
                    conversation_context,
                    user_message,
                    main_module,
                    trace=resultado.get("trace"),
                )

            # Decidir: ¿usar respuesta del pipeline (error controlado) o del LLM?
            # Si el pipeline detectó un CAMBIO DE PRODUCTO, usar la del pipeline
            # porque la del LLM tiene el producto equivocado
            for err in (validacion or {}).get("errores", []):
                if "CAMBIO DE PRODUCTO" in err or "INCOMPATIBILIDAD" in err:
                    return _construir_return_agente(
                        resultado["respuesta_whatsapp"],
                        tool_calls_made,
                        conversation_context,
                        user_message,
                        main_module,
                        trace=resultado.get("trace"),
                    )

            # Para otros errores, darle chance a la respuesta del LLM
            return None

        # ── Pipeline exitoso → Usar su respuesta en lugar de la del LLM ──
        return _construir_return_agente(
            resultado["respuesta_whatsapp"],
            tool_calls_made,
            conversation_context,
            user_message,
            main_module,
            payload_pdf=resultado.get("payload_pdf"),
            trace=resultado.get("trace"),
        )

    except Exception as e:
        logger.error("INTERCEPCIÓN: Error en pipeline — %s", e, exc_info=True)
        # Fallback: dejar pasar la respuesta original del LLM
        return None


def _construir_return_agente(
    response_text: str,
    tool_calls_made: list,
    conversation_context: dict,
    user_message: str,
    main_module,
    payload_pdf: dict = None,
    trace: dict = None,
) -> dict:
    """
    Construye un dict de retorno compatible con generate_agent_reply_v3().
    """
    intent = "cotizacion"

    # Almacenar payload PDF en el draft para cuando el cliente confirme
    if payload_pdf:
        commercial_draft = dict(conversation_context.get("commercial_draft") or {})
        commercial_draft["pipeline_payload_pdf"] = payload_pdf
        commercial_draft["_generado_por_pipeline"] = True
        conversation_context["commercial_draft"] = commercial_draft

    # Almacenar trace para debugging
    if trace:
        conversation_context["_ultimo_pipeline_trace"] = trace

    return {
        "response_text": response_text,
        "intent": intent,
        "tool_calls": tool_calls_made,
        "context_updates": {
            key: value
            for key, value in {
                "latest_technical_guidance": conversation_context.get("latest_technical_guidance"),
                "commercial_draft": conversation_context.get("commercial_draft"),
                "technical_advisory_case": conversation_context.get("technical_advisory_case"),
                "_ultimo_pipeline_trace": trace,
            }.items()
            if value is not None
        },
        "should_create_task": False,
        "confidence": 0.95,  # Alta confianza: pipeline determinístico
        "is_farewell": False,
    }


# ══════════════════════════════════════════════════════════════════════════════
# INTERCEPTOR PARA CONFIRMACIÓN DE PDF
# ══════════════════════════════════════════════════════════════════════════════

def interceptar_confirmacion_pdf(
    main_module,
    conversation_context: dict,
    context: dict,
    user_message: str,
) -> Optional[dict]:
    """
    Cuando el cliente confirma "sí, genera el PDF", usa los datos ya
    resueltos por el pipeline en lugar de dejar que el LLM los reinterprete.

    Returns:
        dict con resultado si interceptó, None si no aplica.
    """
    commercial_draft = conversation_context.get("commercial_draft", {})
    
    if not commercial_draft.get("_generado_por_pipeline"):
        return None

    payload_pdf = commercial_draft.get("pipeline_payload_pdf")
    if not payload_pdf:
        return None

    # ── Verificar que el usuario está confirmando ──
    user_lower = (user_message or "").lower()
    señales_confirmacion = [
        "sí", "si", "dale", "genera", "pdf", "cotización", "cotizacion",
        "envía", "envia", "mándame", "mandame", "procede", "confirmo",
    ]
    if not any(s in user_lower for s in señales_confirmacion):
        return None

    logger.info("INTERCEPCIÓN PDF: Usando payload del pipeline para generar PDF")
    
    # Los datos del payload ya son 100% del backend — no pasan por LLM
    return payload_pdf
