"""
generate_agent_reply_v3 — Motor de agente V3 ultraligero.

Reemplaza generate_agent_reply_v2 con:
1. Prompt ultraligero (~200 líneas vs ~900).
2. Contexto de turno dinámico (Python decide, no el LLM).
3. Herramientas estrictas que fuerzan uso obligatorio.
4. Solo 3 guardias de seguridad críticas (química, bicomponente, IVA).
5. Cero guardias de flujo (el contexto dinámico las hace innecesarias).
"""

import json
import re
import time
import logging
from typing import Optional

logger = logging.getLogger("agent_v3")

# Importaciones diferidas de main.py (se configuran en init)
_main = None


def _get_main():
    global _main
    if _main is None:
        try:
            import main as _m
        except ImportError:
            from backend import main as _m
        _main = _m
    return _main


# ══════════════════════════════════════════════════════════════════════════════
# CORE: generate_agent_reply_v3
# ══════════════════════════════════════════════════════════════════════════════

def generate_agent_reply_v3(
    profile_name: Optional[str],
    conversation_context: dict,
    recent_messages: list[dict],
    user_message: str,
    context: dict,
):
    """
    Motor V3 del agente FERRO.
    Misma firma y mismo dict de retorno que generate_agent_reply_v2.
    """
    try:
        from agent_context import build_turn_context, classify_intent, extract_diagnostic_data
        from agent_prompt_v3 import AGENT_SYSTEM_PROMPT_V3, AGENT_TOOLS_V3
    except ImportError:
        from backend.agent_context import build_turn_context, classify_intent, extract_diagnostic_data
        from backend.agent_prompt_v3 import AGENT_SYSTEM_PROMPT_V3, AGENT_TOOLS_V3

    m = _get_main()
    client = m.get_openai_client()

    # ── Extraer estado (mismo código de V2, simplificado) ────────────────
    verified = bool(conversation_context.get("verified"))
    verified_cliente = conversation_context.get("verified_cliente_codigo")
    nombre_cliente = ""
    if verified and verified_cliente:
        try:
            cli = m.get_cliente_contexto(verified_cliente)
            nombre_cliente = cli.get("nombre_cliente", "")
        except Exception:
            pass

    commercial_draft = conversation_context.get("commercial_draft")
    claim_case = conversation_context.get("claim_case")

    internal_auth = conversation_context.get("internal_auth") or {}
    if internal_auth:
        emp = dict(internal_auth.get("employee_context") or {})
        cedula_empleado = str(emp.get("cedula") or "").strip()
        empleado_activo = json.dumps({
            "nombre": emp.get("full_name"),
            "cedula": cedula_empleado,
            "cargo": emp.get("cargo"),
            "sede": emp.get("sede"),
            "rol": internal_auth.get("role", "empleado"),
            "store_code": emp.get("store_code"),
        }, ensure_ascii=False)
        if cedula_empleado in m._AUTHORIZED_EXPERTS:
            nombre_exp = emp.get("full_name") or cedula_empleado
            es_experto_autorizado = (
                f"⚠️ SÍ — ESTÁS HABLANDO CON EL EXPERTO AUTORIZADO {nombre_exp} (cédula {cedula_empleado}). "
                f"TIENES PERMISO ABSOLUTO para ejecutar registrar_conocimiento_experto cuando diga ENSEÑAR."
            )
        else:
            es_experto_autorizado = "No"
    else:
        empleado_activo = "Ninguno"
        es_experto_autorizado = "No"

    teaching_result = _handle_explicit_teaching_message(user_message, conversation_context, m)
    if teaching_result is not None:
        return teaching_result

    # ── Construir contexto de turno dinámico ─────────────────────────────
    contexto_turno = build_turn_context(
        conversation_context=conversation_context,
        recent_messages=recent_messages,
        user_message=user_message,
        internal_auth=internal_auth,
        profile_name=profile_name,
    )

    # ── Formatear prompt V3 ──────────────────────────────────────────────
    system_content = AGENT_SYSTEM_PROMPT_V3.format(
        contexto_turno=contexto_turno,
        verificado="SÍ" if verified else "NO",
        cliente_codigo=verified_cliente or "No identificado",
        nombre_cliente=nombre_cliente or "No identificado",
        borrador_activo=m.safe_json_dumps(commercial_draft) if commercial_draft else "Ninguno",
        reclamo_activo=m.safe_json_dumps(claim_case) if claim_case else "Ninguno",
        empleado_activo=empleado_activo,
        es_experto_autorizado=es_experto_autorizado,
    )

    messages = [{"role": "system", "content": system_content}]

    # ── Historial (últimos 10 mensajes) ──────────────────────────────────
    for msg in recent_messages[-10:]:
        role = "assistant" if msg.get("direction") == "outbound" else "user"
        content_text = msg.get("contenido") or ""
        if content_text and msg.get("message_type") in ("text", "button", "interactive", None):
            messages.append({"role": role, "content": content_text})

    messages.append({"role": "user", "content": user_message})

    initial_intent = classify_intent(user_message, conversation_context, recent_messages, internal_auth)
    initial_diagnostic = extract_diagnostic_data(user_message, recent_messages)

    def _needs_forced_technical_retry() -> bool:
        if tool_calls_made or assistant_message.tool_calls:
            return False
        if initial_intent != "asesoria":
            return False
        if not (initial_diagnostic.get("surface") and initial_diagnostic.get("interior_exterior") and initial_diagnostic.get("condition")):
            return False
        draft_text = (assistant_message.content or "").lower()
        if any(token in draft_text for token in ["voy a consultar", "voy a revisar", "un momento", "déjame revisar", "dejame revisar"]):
            return True
        return False

    # ══════════════════════════════════════════════════════════════════════
    # LLM CALL + TOOL LOOP
    # ══════════════════════════════════════════════════════════════════════
    t_start = time.time()
    response = client.chat.completions.create(
        model=m.get_openai_model(),
        messages=messages,
        tools=AGENT_TOOLS_V3,
        tool_choice="auto",
        temperature=0.3,
    )
    t_first = time.time()
    logger.info("V3 LLM initial: %dms", int((t_first - t_start) * 1000))

    assistant_message = response.choices[0].message
    tool_calls_made = []

    if _needs_forced_technical_retry():
        logger.info("V3 retry: advisory response promised a technical lookup without calling tools")
        messages.append({
            "role": "assistant",
            "content": assistant_message.content or "",
        })
        messages.append({
            "role": "system",
            "content": (
                "CORRECCIÓN OBLIGATORIA: ya tienes superficie, ubicación y condición suficientes para asesoría técnica. "
                "Debes llamar consultar_conocimiento_tecnico AHORA en este mismo turno antes de responder al cliente. "
                "No prometas revisar más tarde; usa la herramienta y luego entrega la recomendación."
            ),
        })
        response = client.chat.completions.create(
            model=m.get_openai_model(),
            messages=messages,
            tools=AGENT_TOOLS_V3,
            tool_choice="auto",
            temperature=0.3,
        )
        assistant_message = response.choices[0].message
        logger.info("V3 retry completed after missed advisory tool call")

    max_iterations = 6
    iteration = 0
    _rag_cache: dict[str, str] = {}
    _tool_type_counts: dict[str, int] = {}
    _TOOL_MAX_CALLS = {"consultar_conocimiento_tecnico": 2, "buscar_documento_tecnico": 2}

    while assistant_message.tool_calls and max_iterations > 0:
        iteration += 1
        messages.append(assistant_message)
        for tc in assistant_message.tool_calls:
            fn_name_raw = tc.function.name if tc.function else ""
            _skip = False

            # Dedup RAG
            if fn_name_raw == "consultar_conocimiento_tecnico":
                try:
                    _tc_args = json.loads(tc.function.arguments or "{}")
                    _cache_key = m.normalize_text_value(
                        (_tc_args.get("pregunta") or "") + "|" + (_tc_args.get("producto") or "")
                    )
                    if _cache_key in _rag_cache:
                        _skip = True
                        result = _rag_cache[_cache_key]
                        fn_name, fn_args = fn_name_raw, _tc_args
                        logger.info("V3 RAG dedup HIT: '%s'", _cache_key[:60])
                except Exception:
                    pass

            # Per-tool budget
            if not _skip and fn_name_raw in _TOOL_MAX_CALLS:
                _tool_type_counts[fn_name_raw] = _tool_type_counts.get(fn_name_raw, 0) + 1
                if _tool_type_counts[fn_name_raw] > _TOOL_MAX_CALLS[fn_name_raw]:
                    _skip = True
                    fn_name, fn_args = fn_name_raw, {}
                    result = json.dumps(
                        {"mensaje": "Límite de llamadas alcanzado para esta herramienta. Usa la información ya obtenida."},
                        ensure_ascii=False,
                    )
                    logger.info("V3 tool budget exceeded: %s", fn_name_raw)

            if not _skip:
                fn_name, fn_args, result = m._execute_agent_tool(tc, context, conversation_context)
                if fn_name == "consultar_conocimiento_tecnico":
                    try:
                        _tc_args = json.loads(tc.function.arguments or "{}")
                        _cache_key = m.normalize_text_value(
                            (_tc_args.get("pregunta") or "") + "|" + (_tc_args.get("producto") or "")
                        )
                        _rag_cache[_cache_key] = result
                    except Exception:
                        pass

            tool_calls_made.append({"name": fn_name, "args": fn_args, "result": result})
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})

        t_loop = time.time()
        response = client.chat.completions.create(
            model=m.get_openai_model(),
            messages=messages,
            tools=AGENT_TOOLS_V3,
            tool_choice="auto",
            temperature=0.3,
        )
        logger.info("V3 LLM iteration %d: %dms", iteration, int((time.time() - t_loop) * 1000))
        assistant_message = response.choices[0].message
        max_iterations -= 1

    # ── Si se agotaron iteraciones sin texto final, forzar respuesta ────
    if not assistant_message.content and tool_calls_made:
        logger.warning("V3: iterations exhausted without text — forcing tool_choice=none")
        if assistant_message.tool_calls:
            messages.append(assistant_message)
            for tc in assistant_message.tool_calls:
                messages.append({"role": "tool", "tool_call_id": tc.id, "content": '{"mensaje": "Límite de iteraciones alcanzado. Resume toda la información obtenida."}'})
        messages.append({
            "role": "system",
            "content": (
                "IMPORTANTE: Ya tienes TODA la información de las herramientas. "
                "Genera tu respuesta FINAL consolidando TODOS los datos obtenidos. "
                "NO llames más herramientas."
            ),
        })
        t_force = time.time()
        resp_force = client.chat.completions.create(
            model=m.get_openai_model(),
            messages=messages,
            tools=AGENT_TOOLS_V3,
            tool_choice="none",
            temperature=0.3,
        )
        assistant_message = resp_force.choices[0].message
        logger.info("V3 forced text response: %dms", int((time.time() - t_force) * 1000))

    total_ms = int((time.time() - t_start) * 1000)
    tool_names = [tc["name"] for tc in tool_calls_made]
    logger.info("V3 agent TOTAL: %dms | tools=%s | iters=%d", total_ms, tool_names, iteration)

    # ══════════════════════════════════════════════════════════════════════
    # GUARDIAS CRÍTICAS DE SEGURIDAD (solo las que protegen al cliente)
    # ══════════════════════════════════════════════════════════════════════

    is_ensenar_msg = _detect_ensenar(user_message)
    is_greeting = m.is_simple_greeting(user_message or "")

    # ── GUARDIA QUÍMICA: incompatibilidad alquídico/epóxico/PU ───────────
    if not is_ensenar_msg and not is_greeting:
        assistant_message = _guardia_quimica(
            assistant_message, messages, tool_calls_made, context, conversation_context, m,
            user_message=user_message,
        )

    # ── GUARDIA BICOMPONENTE: catalizador obligatorio ────────────────────
    if not is_ensenar_msg and not is_greeting:
        assistant_message = _guardia_bicomponente(
            assistant_message, messages, tool_calls_made, context, conversation_context, m
        )

    # ── GUARDIA IVA: desglose obligatorio en cotizaciones ────────────────
    if not is_greeting:
        assistant_message = _guardia_iva(assistant_message, messages, m)

    # ══════════════════════════════════════════════════════════════════════
    # POST-PROCESAMIENTO
    # ══════════════════════════════════════════════════════════════════════

    # Intent clasificación para el retorno
    intent = _classify_return_intent(tool_calls_made, user_message, m)

    response_text = assistant_message.content or "Gracias por escribirnos. ¿En qué te puedo ayudar?"

    # Strip <thinking> tags
    response_text = re.sub(r'<thinking>.*?</thinking>\s*', '', response_text, flags=re.DOTALL).strip()
    if not response_text:
        response_text = "Gracias por escribirnos. ¿En qué te puedo ayudar?"

    confidence = m.score_agent_confidence(response_text, tool_calls_made, intent)
    is_farewell = m.detect_farewell(user_message)
    if is_farewell:
        intent = "despedida"

    return {
        "response_text": response_text,
        "intent": intent,
        "tool_calls": tool_calls_made,
        "context_updates": {
            "last_product_request": conversation_context.get("last_product_request"),
            "last_product_query": conversation_context.get("last_product_query"),
            "last_product_context": conversation_context.get("last_product_context"),
        } if conversation_context.get("last_product_request") else {},
        "should_create_task": False,
        "confidence": confidence,
        "is_farewell": is_farewell,
    }


# ══════════════════════════════════════════════════════════════════════════════
# GUARDIAS CRÍTICAS (solo seguridad del cliente, no flujo)
# ══════════════════════════════════════════════════════════════════════════════

_CHEM_FAMILIES = {
    "alkyd": ["corrotec", "pintóxido", "pintoxido", "pintulux", "esmalte doméstico",
               "esmalte domestico", "pintulux 3en1", "anticorrosivo pintuco",
               # Términos genéricos que el cliente usa para describir base alquídica
               "alquídico", "alquidico", "alquídica", "alquidica",
               "base alquídica", "base alquidica", "anticorrosivo alquídico",
               "anticorrosivo alquidico", "pintura alquídica", "pintura alquidica"],
    "polyurethane": ["interthane", "interfine"],
    "epoxy": ["interseal", "intergard", "pintucoat", "primer 50rs", "primer 50 rs",
              # Términos genéricos que el cliente usa para pedir epóxicos
              "epóxico", "epoxico", "epóxica", "epoxica"],
}

_CHEM_INCOMPATIBLE_PAIRS = [
    ("alkyd", "polyurethane",
     "Los alquídicos (Corrotec, Pintulux, Pintóxido) son INCOMPATIBLES con poliuretanos (Interthane, Interfine). "
     "Los solventes alquídicos impiden la reticulación del poliuretano y causan desprendimiento. "
     "Sistema CORRECTO para metal industrial: Imprimante Epóxico (Interseal/Intergard) + Acabado Poliuretano (Interthane). "
     "Sistema CORRECTO para metal arquitectónico/económico: Anticorrosivo (Corrotec) + Esmalte alquídico (Pintulux 3en1)."),
    ("alkyd", "epoxy",
     "Los epóxicos (Interseal, Intergard, Pintucoat) son INCOMPATIBLES sobre bases alquídicas (Corrotec, Pintóxido). "
     "El solvente epóxico REMUEVE y ARRUGA la capa alquídica. Tampoco los alquídicos protegen sistemas epóxicos correctamente. "
     "Si el cliente tiene pintura alquídica vieja y quiere epóxico: DEBE REMOVER COMPLETAMENTE la pintura alquídica primero. "
     "Sistema CORRECTO industrial: Remover alquídico → Imprimante Epóxico (Interseal 670HS) + Acabado (Intergard/Interthane). "
     "Sistema CORRECTO económico SIN remover: Anticorrosivo alquídico (Corrotec) + Esmalte alquídico (Pintulux 3en1)."),
]

_BICOMP_CHECKS = [
    (["interthane"], ["pha046", "catalizador interthane", "comp b interthane", "hardener interthane"],
     "Interthane 990", "PHA046 catalizador"),
    (["pintucoat"], ["13227", "catalizador pintucoat", "comp b pintucoat"],
     "Pintucoat", "13227 catalizador"),
    (["interseal"], ["catalizador interseal", "comp b interseal"],
     "Interseal", "Comp B catalizador (ver ficha técnica)"),
    (["intergard 740", "intergard 2002"], ["catalizador intergard", "comp b intergard"],
     "Intergard", "Comp B catalizador (ver ficha técnica)"),
]


def _detect_ensenar(user_message: str) -> bool:
    msg = (user_message or "").lower()
    return any(kw in msg for kw in ["enseñar", "ensenar", "anota esto", "guarda esto", "aprende esto"])


def _extract_teaching_payload(user_message: str) -> Optional[dict]:
    raw_text = (user_message or "").strip()
    if not raw_text:
        return None

    normalized = raw_text.lower()
    markers = ["enseñar:", "ensenar:", "anota esto:", "guarda esto:", "aprende esto:", "regla:"]
    content = raw_text
    for marker in markers:
        index = normalized.find(marker)
        if index != -1:
            content = raw_text[index + len(marker):].strip()
            break

    if len(content) < 20:
        return None

    lowered = content.lower()
    tipo = "proceso"
    if "alerta superficie" in lowered or "asbesto" in lowered:
        tipo = "alerta_superficie"
    elif "nunca recomendar" in lowered or "nunca aplicar" in lowered or "nunca usar" in lowered or "nunca recomendar," in lowered:
        tipo = "evitar"
    elif "siempre" in lowered:
        tipo = "proceso"

    contexto_match = re.search(r"para\s+(.+?)(?:\s+nunca|\s+siempre|\.|:)", lowered, flags=re.IGNORECASE)
    contexto_tags = (contexto_match.group(1).strip() if contexto_match else content[:140].strip())

    producto_recomendado = None
    rec_match = re.search(r"recomendar\s+(.+?)(?:\s+seguido de|\.|,|$)", content, flags=re.IGNORECASE)
    if rec_match:
        producto_recomendado = rec_match.group(1).strip()
    elif "sellomax" in lowered and "koraza" in lowered:
        producto_recomendado = "Sellomax + Koraza"

    producto_desestimado = None
    avoid_match = re.search(r"NUNCA\s+(?:recomendar|aplicar|usar|listar ni incluir)\s+(.+?)(?:\.|$)", content, flags=re.IGNORECASE)
    if avoid_match:
        producto_desestimado = avoid_match.group(1).strip()

    return {
        "contexto_tags": contexto_tags,
        "nota_comercial": content,
        "tipo": tipo,
        "producto_recomendado": producto_recomendado,
        "producto_desestimado": producto_desestimado,
    }


def _handle_explicit_teaching_message(user_message: str, conversation_context: dict, m):
    if not _detect_ensenar(user_message):
        return None

    payload = _extract_teaching_payload(user_message)
    if not payload:
        return {
            "response_text": "Para guardar la enseñanza necesito una regla más completa después de ENSEÑAR:.",
            "intent": "registrar_conocimiento_experto",
            "tool_calls": [],
            "context_updates": {},
            "should_create_task": False,
            "confidence": {"level": "alta"},
            "is_farewell": False,
        }

    result_raw = m._handle_tool_registrar_conocimiento_experto(payload, conversation_context)
    try:
        result = json.loads(result_raw)
    except Exception:
        result = {"guardado": False, "mensaje": result_raw}

    return {
        "response_text": result.get("mensaje") or "No fue posible procesar la enseñanza.",
        "intent": "registrar_conocimiento_experto",
        "tool_calls": [{"name": "registrar_conocimiento_experto", "args": payload, "result": result_raw}],
        "context_updates": {},
        "should_create_task": False,
        "confidence": {"level": "alta" if result.get("guardado") else "media"},
        "is_farewell": False,
    }


def _guardia_quimica(assistant_message, messages, tool_calls_made, context, conversation_context, m, user_message=""):
    """Detecta combinaciones químicas incompatibles y fuerza corrección.
    
    Estrategia de detección dual:
    - Nombres de producto (Corrotec, Intergard) → busca en respuesta + user_message
    - Términos genéricos (alquídico, epóxico) → busca SOLO en user_message
      para detectar cuando el cliente describe su situación (ej. "tengo alquídico, quiero epóxico")
    """
    response_text = (assistant_message.content or "").lower()
    user_text = (user_message or "").lower()
    combined_text = response_text + " " + user_text

    # Términos genéricos que solo deben matchear en el mensaje del usuario
    _GENERIC_TERMS = {
        "alkyd": ["alquídico", "alquidico", "alquídica", "alquidica",
                   "base alquídica", "base alquidica", "anticorrosivo alquídico",
                   "anticorrosivo alquidico", "pintura alquídica", "pintura alquidica"],
        "epoxy": ["epóxico", "epoxico", "epóxica", "epoxica"],
    }

    families_in_response = {}
    for fam, signals in _CHEM_FAMILIES.items():
        found = []
        for s in signals:
            if s in _GENERIC_TERMS.get(fam, []):
                # Término genérico → solo buscar en user_message
                if s in user_text:
                    found.append(s)
            else:
                # Nombre de producto → buscar en combined (respuesta + usuario)
                if s in combined_text:
                    found.append(s)
        if found:
            families_in_response[fam] = found

    for fam_a, fam_b, explanation in _CHEM_INCOMPATIBLE_PAIRS:
        if fam_a in families_in_response and fam_b in families_in_response:
            products_a = families_in_response[fam_a]
            products_b = families_in_response[fam_b]
            logger.warning(
                "⛔ V3 GUARDIA QUÍMICA: %s (%s) + %s (%s)",
                fam_a, products_a, fam_b, products_b,
            )
            try:
                from agent_prompt_v3 import AGENT_TOOLS_V3
            except ImportError:
                from backend.agent_prompt_v3 import AGENT_TOOLS_V3
            messages.append(assistant_message)
            messages.append({
                "role": "system",
                "content": (
                    f"⛔ BLOQUEO QUÍMICO — Tu respuesta contiene productos incompatibles.\n\n"
                    f"DETECTADO: {', '.join(products_a)} (familia {fam_a}) + "
                    f"{', '.join(products_b)} (familia {fam_b}) en el MISMO sistema.\n\n"
                    f"INCOMPATIBILIDAD:\n{explanation}\n\n"
                    f"Reescribe usando uno de los sistemas correctos descritos arriba. "
                    f"Llama consultar_inventario_lote con los productos del sistema correcto."
                ),
            })
            t = time.time()
            resp = m.get_openai_client().chat.completions.create(
                model=m.get_openai_model(), messages=messages,
                tools=AGENT_TOOLS_V3, tool_choice="auto", temperature=0.3,
            )
            assistant_message = resp.choices[0].message
            retries = 3
            while assistant_message.tool_calls and retries > 0:
                messages.append(assistant_message)
                for tc in assistant_message.tool_calls:
                    fn_name, fn_args, result = m._execute_agent_tool(tc, context, conversation_context)
                    tool_calls_made.append({"name": fn_name, "args": fn_args, "result": result})
                    messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})
                resp = m.get_openai_client().chat.completions.create(
                    model=m.get_openai_model(), messages=messages,
                    tools=AGENT_TOOLS_V3, tool_choice="auto", temperature=0.3,
                )
                assistant_message = resp.choices[0].message
                retries -= 1
            logger.info("V3 GUARDIA QUÍMICA completed: %dms", int((time.time() - t) * 1000))
            break  # Fix first incompatibility only

    return assistant_message


def _guardia_bicomponente(assistant_message, messages, tool_calls_made, context, conversation_context, m):
    """Detecta bicomponentes sin catalizador y fuerza corrección."""
    try:
        from agent_prompt_v3 import AGENT_TOOLS_V3
    except ImportError:
        from backend.agent_prompt_v3 import AGENT_TOOLS_V3
    response_text = (assistant_message.content or "").lower()

    for prod_signals, cat_signals, prod_name, cat_name in _BICOMP_CHECKS:
        has_product = any(s in response_text for s in prod_signals)
        has_catalyst = any(s in response_text for s in cat_signals)
        if has_product and not has_catalyst:
            logger.warning("⛔ V3 GUARDIA BICOMPONENTE: %s sin catalizador %s", prod_name, cat_name)
            messages.append(assistant_message)
            messages.append({
                "role": "system",
                "content": (
                    f"⛔ BICOMPONENTE INCOMPLETO — {prod_name} requiere su catalizador ({cat_name}).\n"
                    f"Sin catalizador el producto NO endurece. Es como vender una cerradura sin llave.\n"
                    f"Agrega {cat_name} al sistema con cantidad proporcional. "
                    f"Cada línea debe decir '(Kit A+B)'. "
                    f"Llama consultar_inventario con '{cat_name}' si no tienes su precio."
                ),
            })
            t = time.time()
            resp = m.get_openai_client().chat.completions.create(
                model=m.get_openai_model(), messages=messages,
                tools=AGENT_TOOLS_V3, tool_choice="auto", temperature=0.3,
            )
            assistant_message = resp.choices[0].message
            retries = 3
            while assistant_message.tool_calls and retries > 0:
                messages.append(assistant_message)
                for tc in assistant_message.tool_calls:
                    fn_name, fn_args, result = m._execute_agent_tool(tc, context, conversation_context)
                    tool_calls_made.append({"name": fn_name, "args": fn_args, "result": result})
                    messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})
                resp = m.get_openai_client().chat.completions.create(
                    model=m.get_openai_model(), messages=messages,
                    tools=AGENT_TOOLS_V3, tool_choice="auto", temperature=0.3,
                )
                assistant_message = resp.choices[0].message
                retries -= 1
            logger.info("V3 GUARDIA BICOMPONENTE completed: %dms", int((time.time() - t) * 1000))
            response_text = (assistant_message.content or "").lower()

    return assistant_message


def _guardia_iva(assistant_message, messages, m):
    """Si la cotización no tiene desglose de IVA, fuerza corrección."""
    try:
        from agent_prompt_v3 import AGENT_TOOLS_V3
    except ImportError:
        from backend.agent_prompt_v3 import AGENT_TOOLS_V3
    text = assistant_message.content or ""
    has_prices = "$" in text and any(
        kw in text.lower() for kw in ["total", "precio", "cotización", "cotizacion", "pedido"]
    )
    has_iva = any(
        kw in text.lower() for kw in ["iva 19%", "iva (19%)", "iva:", "19% iva"]
    )
    if has_prices and not has_iva:
        price_count = len(re.findall(r'\$[\d.,]+', text))
        if price_count >= 2:
            logger.warning("⛔ V3 GUARDIA IVA: cotización sin desglose de IVA")
            messages.append(assistant_message)
            messages.append({
                "role": "system",
                "content": (
                    "⛔ FALTA IVA. Los precios son ANTES DE IVA. Agrega al final:\n"
                    "- **Subtotal:** $X\n- **IVA 19%:** $Y\n- **Total a Pagar:** $Z\n"
                    "Mantén toda la info de productos intacta."
                ),
            })
            t = time.time()
            resp = m.get_openai_client().chat.completions.create(
                model=m.get_openai_model(), messages=messages,
                tools=AGENT_TOOLS_V3, tool_choice="none", temperature=0.3,
            )
            assistant_message = resp.choices[0].message
            logger.info("V3 GUARDIA IVA completed: %dms", int((time.time() - t) * 1000))

    return assistant_message


def _classify_return_intent(tool_calls_made: list, user_message: str, m) -> str:
    """Clasifica el intent basado en herramientas llamadas (para retorno)."""
    intent = "consulta_general"
    for tc in tool_calls_made:
        name = tc["name"]
        if name == "verificar_identidad":
            intent = "verificacion_identidad"
        elif name in ("consultar_inventario", "consultar_inventario_lote"):
            intent = "consulta_productos"
        elif name == "consultar_cartera":
            intent = "consulta_cartera"
        elif name == "consultar_compras":
            intent = "consulta_compras"
        elif name == "consultar_ventas_internas":
            intent = "consulta_ventas_internas"
        elif name == "buscar_documento_tecnico":
            intent = "consulta_documentacion"
        elif name == "consultar_conocimiento_tecnico":
            intent = "asesoria_tecnica"
        elif name == "radicar_reclamo":
            intent = "reclamo_servicio"
        elif name == "confirmar_pedido_y_generar_pdf":
            intent = "pedido"
    return intent
