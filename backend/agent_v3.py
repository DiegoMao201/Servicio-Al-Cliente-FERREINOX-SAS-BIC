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

_TECHNICAL_PRODUCT_GUARD_SIGNALS = [
    "koraza", "intervinil", "pinturama", "viniltex", "aquablock", "sellomax",
    "pintucoat", "intergard", "interseal", "interthane", "corrotec", "pintulux",
    "barnex", "siliconite", "construcleaner", "wood stain", "pintoxido", "pintóxido",
    "lija abracol", "lijas de agua", "papel de lija",
]

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


def _user_explicitly_named_product(product_candidate: Optional[str], user_message: str, recent_messages: list[dict], m) -> bool:
    if not product_candidate:
        return False
    combined_user_text = " ".join(
        [(msg.get("contenido") or "") for msg in recent_messages if msg.get("direction") == "inbound"]
        + [user_message or ""]
    )
    normalized_user_text = f" {m.normalize_text_value(combined_user_text)} "
    normalized_candidate = m.normalize_text_value(product_candidate)
    if not normalized_candidate:
        return False
    if f" {normalized_candidate} " in normalized_user_text:
        return True

    generic_tokens = {
        "pintura", "pinturas", "acabado", "acabados", "sistema", "sistemas",
        "sellador", "selladores", "primer", "imprimante", "vinilo", "acrilico", "acrilica",
    }
    candidate_tokens = [
        token for token in re.findall(r"[a-z0-9áéíóúñ]+", normalized_candidate)
        if len(token) >= 4 and token not in generic_tokens
    ]
    return any(f" {token} " in normalized_user_text for token in candidate_tokens)


def _sanitize_technical_lookup_args(raw_args: dict, user_message: str, recent_messages: list[dict], m) -> dict:
    args = dict(raw_args or {})
    product_candidate = (args.get("producto") or "").strip()
    if product_candidate and not _user_explicitly_named_product(product_candidate, user_message, recent_messages, m):
        logger.info("V3 tech lookup sanitized guessed product: %s", product_candidate)
        args["producto"] = ""
    return args


def _collect_recent_inbound_text(user_message: str, recent_messages: list[dict], limit: int = 4) -> str:
    inbound_messages = [
        (msg.get("contenido") or "").strip()
        for msg in recent_messages or []
        if msg.get("direction") == "inbound" and (msg.get("contenido") or "").strip()
    ]
    combined = inbound_messages[-limit:]
    if (user_message or "").strip():
        combined.append(user_message.strip())
    return " ".join(combined).strip()


def _should_route_to_commercial_flow(initial_intent: str, conversation_context: dict, user_message: str, m) -> bool:
    draft = conversation_context.get("commercial_draft") or {}
    if draft.get("items"):
        return True

    if initial_intent in {"pedido_directo", "cotizacion", "confirmacion", "correccion"}:
        return True

    request_lines = m.split_commercial_line_items(user_message)
    matched_lines = 0
    for line in request_lines[:12]:
        request = m.extract_product_request(line)
        if request.get("requested_quantity") is not None and (
            request.get("product_codes")
            or request.get("core_terms")
            or request.get("requested_unit")
        ):
            matched_lines += 1
    return matched_lines >= 2


def _infer_commercial_intent(initial_intent: str, conversation_context: dict, user_message: str, m) -> str:
    draft_intent = (conversation_context.get("commercial_draft") or {}).get("intent")
    if draft_intent in {"pedido", "cotizacion"}:
        return draft_intent

    normalized_message = m.normalize_text_value(user_message)
    if initial_intent == "confirmacion":
        return "cotizacion"
    if any(token in normalized_message for token in ["pedido", "despacho", "separ", "separar"]):
        return "pedido"
    return "cotizacion"


def _build_commercial_flow_short_circuit(
    profile_name: Optional[str],
    conversation_context: dict,
    user_message: str,
    initial_intent: str,
    m,
):
    commercial_intent = _infer_commercial_intent(initial_intent, conversation_context, user_message, m)
    commercial_result = m.build_commercial_flow_reply(
        commercial_intent,
        profile_name,
        user_message,
        conversation_context,
    )
    response_text = (commercial_result or {}).get("response_text") or "Gracias por escribirnos. ¿En qué te puedo ayudar?"
    context_updates = dict((commercial_result or {}).get("conversation_context_updates") or {})
    if commercial_result and commercial_result.get("commercial_draft") and "commercial_draft" not in context_updates:
        context_updates["commercial_draft"] = commercial_result.get("commercial_draft")

    return {
        "response_text": response_text,
        "intent": (commercial_result or {}).get("intent") or commercial_intent,
        "tool_calls": [],
        "context_updates": context_updates,
        "should_create_task": bool((commercial_result or {}).get("should_create_task")),
        "confidence": m.score_agent_confidence(response_text, [], (commercial_result or {}).get("intent") or commercial_intent),
        "is_farewell": False,
    }


def _should_route_to_inventory_lookup(initial_intent: str, conversation_context: dict, m) -> bool:
    if initial_intent != "consulta_productos":
        return False
    if (conversation_context.get("commercial_draft") or {}).get("items"):
        return False
    return hasattr(m, "build_inventory_lookup_reply")


def _build_inventory_lookup_short_circuit(
    profile_name: Optional[str],
    conversation_context: dict,
    user_message: str,
    m,
):
    inventory_result = m.build_inventory_lookup_reply(
        profile_name,
        user_message,
        conversation_context,
    ) or {}
    response_text = inventory_result.get("response_text") or "No encontré un inventario claro para esa consulta."
    context_updates = dict(inventory_result.get("conversation_context_updates") or {})
    return {
        "response_text": response_text,
        "intent": inventory_result.get("intent") or "consulta_productos",
        "tool_calls": [],
        "context_updates": context_updates,
        "should_create_task": bool(inventory_result.get("should_create_task")),
        "confidence": m.score_agent_confidence(response_text, [], inventory_result.get("intent") or "consulta_productos"),
        "is_farewell": False,
    }


def _should_preload_technical_guidance(
    initial_intent: str,
    initial_diagnostic: dict,
    user_message: str,
    recent_messages: list[dict],
    conversation_context: dict,
    technical_case: Optional[dict],
    m,
) -> bool:
    if initial_intent != "asesoria":
        return False
    if conversation_context.get("latest_technical_guidance"):
        return False

    combined_text = _collect_recent_inbound_text(user_message, recent_messages, limit=5)
    normalized_text = m.normalize_text_value(combined_text)
    inbound_turns = sum(1 for msg in recent_messages or [] if msg.get("direction") == "inbound" and (msg.get("contenido") or "").strip())

    has_surface_context = bool(initial_diagnostic.get("surface") or (technical_case or {}).get("category"))
    has_structured_detail = bool(
        initial_diagnostic.get("condition")
        or initial_diagnostic.get("interior_exterior")
        or initial_diagnostic.get("area_m2")
        or initial_diagnostic.get("traffic")
        or initial_diagnostic.get("humidity_source")
    )
    has_decision_signal = any(
        token in normalized_text
        for token in [
            "que sistema", "que me recomiendas", "me recomiendas", "que va", "que aplico",
            "cual va", "sirve o no", "ruta correcta", "si aplica", "cotizame", "cotizar",
            "proteger", "impermeabil", "limpiar", "dejarla protegida", "dejarlo protegido",
        ]
    )
    has_high_risk_signal = any(
        token in normalized_text
        for token in [
            "agua potable", "tanque", "sumerg", "inmersion", "inmersion", "eternit", "fibrocemento",
            "ladrillo a la vista", "humedad", "salitre", "oxido", "óxido", "fachada", "cubierta",
            "terraza", "reja", "metal", "madera", "trafico pesado", "trafico liviano",
        ]
    )

    return bool(
        has_surface_context
        and (
            (technical_case or {}).get("ready")
            or has_structured_detail
            or has_decision_signal
            or has_high_risk_signal
            or inbound_turns >= 2
        )
    )


def _build_preemptive_technical_lookup_args(
    user_message: str,
    recent_messages: list[dict],
    conversation_context: dict,
    technical_case: Optional[dict],
    m,
) -> dict:
    combined_text = _collect_recent_inbound_text(user_message, recent_messages, limit=5)
    enriched_case = technical_case or {}
    if hasattr(m, "extract_technical_advisory_case") and (not enriched_case or enriched_case.get("category") in {None, "general"}):
        try:
            enriched_case = m.extract_technical_advisory_case(combined_text, conversation_context)
        except Exception:
            enriched_case = technical_case or {}

    search_query = ""
    if enriched_case and hasattr(m, "build_technical_search_query"):
        try:
            search_query = (m.build_technical_search_query(enriched_case, combined_text or user_message) or "").strip()
        except Exception:
            search_query = ""

    if not search_query:
        search_query = combined_text

    search_query = " ".join(search_query.split())[:600]
    if not search_query:
        return {}

    return {"pregunta": search_query}


def _preload_technical_guidance(args: dict, context: dict, conversation_context: dict, m) -> Optional[str]:
    if not args.get("pregunta"):
        return None
    result = m._handle_tool_consultar_conocimiento_tecnico(args, context, conversation_context)
    try:
        parsed_result = json.loads(result)
    except Exception:
        parsed_result = {}
    if isinstance(parsed_result, dict) and parsed_result.get("encontrado"):
        conversation_context["latest_technical_guidance"] = m._build_latest_technical_guidance_snapshot(parsed_result, args)
    return result


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

    initial_intent = classify_intent(user_message, conversation_context, recent_messages, internal_auth)
    if initial_intent == "saludo" and m.is_simple_greeting(user_message or ""):
        greeting_name = (profile_name or nombre_cliente or "").strip()
        if greeting_name:
            response_text = f"Hola, {greeting_name}. Soy FerreAmigo de Ferreinox. ¿Qué producto o necesidad tienes hoy?"
        else:
            response_text = "Hola, soy FerreAmigo de Ferreinox. ¿Qué producto o necesidad tienes hoy?"
        return {
            "response_text": response_text,
            "intent": "saludo",
            "tool_calls": [],
            "context_updates": {},
            "should_create_task": False,
            "confidence": m.score_agent_confidence(response_text, [], "saludo"),
            "is_farewell": False,
        }

    if _should_route_to_commercial_flow(initial_intent, conversation_context, user_message, m):
        return _build_commercial_flow_short_circuit(
            profile_name,
            conversation_context,
            user_message,
            initial_intent,
            m,
        )

    if _should_route_to_inventory_lookup(initial_intent, conversation_context, m):
        return _build_inventory_lookup_short_circuit(
            profile_name,
            conversation_context,
            user_message,
            m,
        )

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

    initial_diagnostic = extract_diagnostic_data(user_message, recent_messages)
    normalized_user_message = m.normalize_text_value(user_message)
    tool_calls_made = []
    _rag_cache: dict[str, str] = {}
    _tool_type_counts: dict[str, int] = {}
    has_active_technical_guidance = bool(conversation_context.get("latest_technical_guidance"))
    _TOOL_MAX_CALLS = {
        "consultar_conocimiento_tecnico": 1 if has_active_technical_guidance else 2,
        "buscar_documento_tecnico": 2,
    }

    technical_case = None
    if hasattr(m, "extract_technical_advisory_case"):
        try:
            technical_case = m.extract_technical_advisory_case(user_message, conversation_context)
        except Exception:
            technical_case = None

    if _should_preload_technical_guidance(
        initial_intent,
        initial_diagnostic,
        user_message,
        recent_messages,
        conversation_context,
        technical_case,
        m,
    ):
        preload_args = _build_preemptive_technical_lookup_args(
            user_message,
            recent_messages,
            conversation_context,
            technical_case,
            m,
        )
        preload_result = _preload_technical_guidance(preload_args, context, conversation_context, m)
        if preload_result:
            logger.info("V3 preloaded technical guidance before first LLM turn")
            tool_calls_made.append({"name": "consultar_conocimiento_tecnico", "args": preload_args, "result": preload_result})
            cache_key = m.normalize_text_value(
                (preload_args.get("pregunta") or "") + "|" + (preload_args.get("producto") or "")
            )
            if cache_key:
                _rag_cache[cache_key] = preload_result
            messages.append({
                "role": "system",
                "content": (
                    "CONSULTA TÉCNICA YA EJECUTADA EN ESTE TURNO. "
                    "Usa este resultado como fuente obligatoria antes de responder y antes de decidir si requieres otras herramientas. "
                    "No vuelvas a llamar consultar_conocimiento_tecnico salvo que el cliente cambie de superficie, material o problema.\n"
                    f"Args consultar_conocimiento_tecnico: {json.dumps(preload_args, ensure_ascii=False)}\n"
                    f"Resultado: {preload_result}"
                ),
            })

    if has_active_technical_guidance:
        active_guidance = conversation_context.get("latest_technical_guidance") or {}
        active_products = ", ".join(active_guidance.get("required_products") or active_guidance.get("prioritized_products") or [])
        active_problem = active_guidance.get("problem_class") or "caso técnico activo"
        messages.append({
            "role": "system",
            "content": (
                "YA EXISTE UNA GUÍA TÉCNICA ACTIVA PARA ESTE CASO. "
                f"Problema: {active_problem}. "
                f"Productos priorizados: {active_products or 'no definidos'}. "
                "Reutiliza esa guía como verdad operativa del turno actual. "
                "NO vuelvas a llamar consultar_conocimiento_tecnico salvo cambio real de superficie, material o patología."
            ),
        })

    def _needs_forced_technical_retry() -> bool:
        if tool_calls_made or assistant_message.tool_calls:
            return False
        if initial_intent != "asesoria":
            return False
        high_risk_tokens = [
            "humedad", "salitre", "capilaridad", "eternit", "fibrocemento", "asbesto", "ladrillo",
            "metal", "reja", "porton", "interseal", "interthane", "intergard", "pintucoat",
            "koraza", "aquablock", "siliconite", "construcleaner", "barnex", "wood stain",
            "montacargas", "estibadores", "trafico pesado", "poliuretano alto trafico",
        ]
        decision_tokens = [
            "que sistema", "que me recomiendas", "me recomiendan", "se puede directo",
            "me sirve", "que va", "que aplico", "cual va", "sirve o no",
        ]
        has_high_risk_context = any(token in normalized_user_message for token in high_risk_tokens)
        asks_for_decision = any(token in normalized_user_message for token in decision_tokens)
        if not (initial_diagnostic.get("surface") and initial_diagnostic.get("interior_exterior") and initial_diagnostic.get("condition")):
            draft_text = (assistant_message.content or "").lower()
            return has_high_risk_context and asks_for_decision and any(
                token in draft_text for token in ["koraza", "aquablock", "interseal", "interthane", "intergard", "pintucoat", "siliconite", "construcleaner", "barnex"]
            )
        draft_text = (assistant_message.content or "").lower()
        if any(token in draft_text for token in ["voy a consultar", "voy a revisar", "un momento", "déjame revisar", "dejame revisar"]):
            return True
        return has_high_risk_context and asks_for_decision

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
                if fn_name_raw == "consultar_conocimiento_tecnico":
                    original_args = json.loads(tc.function.arguments or "{}")
                    fn_args = _sanitize_technical_lookup_args(original_args, user_message, recent_messages, m)
                    fn_name = fn_name_raw
                    result = m._handle_tool_consultar_conocimiento_tecnico(fn_args, context, conversation_context)
                else:
                    fn_name, fn_args, result = m._execute_agent_tool(tc, context, conversation_context)
                if fn_name == "consultar_conocimiento_tecnico":
                    try:
                        _tc_args = fn_args
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

    # ── GUARDIA CONSISTENCIA TÉCNICA: expert rules / RAG duro vs respuesta final ─────
    assistant_message = _guardia_consistencia_tecnica(
        assistant_message, messages, tool_calls_made, context, conversation_context, m
    )

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
            key: value
            for key, value in {
                "last_product_request": conversation_context.get("last_product_request"),
                "last_product_query": conversation_context.get("last_product_query"),
                "last_product_context": conversation_context.get("last_product_context"),
                "latest_technical_guidance": conversation_context.get("latest_technical_guidance"),
                "commercial_draft": conversation_context.get("commercial_draft"),
            }.items()
            if value is not None
        },
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

    structured_fields = {}
    for raw_chunk in re.split(r"[\n;]+", content):
        chunk = raw_chunk.strip()
        if not chunk:
            continue
        match = re.match(r"^(tipo|contexto|ctx|sustrato|ubicacion|ubicación|estado|etapa|recomendar|evitar|regla|nota)\s*[:=]\s*(.+)$", chunk, flags=re.IGNORECASE)
        if not match:
            continue
        field = match.group(1).strip().lower()
        value = match.group(2).strip()
        structured_fields[field] = value

    explicit_context_parts = []
    if structured_fields.get("contexto"):
        explicit_context_parts.append(structured_fields["contexto"])
    if structured_fields.get("ctx"):
        explicit_context_parts.append(structured_fields["ctx"])
    for field in ["sustrato", "ubicacion", "ubicación", "estado", "etapa"]:
        if structured_fields.get(field):
            explicit_context_parts.append(structured_fields[field])

    explicit_note = structured_fields.get("regla") or structured_fields.get("nota")
    explicit_tipo = (structured_fields.get("tipo") or "").strip().lower()
    explicit_recomendar = structured_fields.get("recomendar")
    explicit_evitar = structured_fields.get("evitar")

    lowered = content.lower()
    tipo = "proceso"
    if explicit_tipo in {"recomendar", "evitar", "proceso", "sustitucion", "sustitución", "alerta_superficie"}:
        tipo = "sustitucion" if explicit_tipo == "sustitución" else explicit_tipo
    elif "alerta superficie" in lowered or "asbesto" in lowered:
        tipo = "alerta_superficie"
    elif "nunca recomendar" in lowered or "nunca aplicar" in lowered or "nunca usar" in lowered or "nunca recomendar," in lowered:
        tipo = "evitar"
    elif "siempre" in lowered:
        tipo = "proceso"

    contexto_match = re.search(r"para\s+(.+?)(?:\s+nunca|\s+siempre|\.|:)", lowered, flags=re.IGNORECASE)
    if explicit_context_parts:
        contexto_tags = ", ".join(part.strip() for part in explicit_context_parts if part.strip())[:220]
    else:
        contexto_tags = (contexto_match.group(1).strip() if contexto_match else content[:140].strip())
    contexto_tags = contexto_tags.strip(" ,.;:")

    producto_recomendado = None
    rec_match = re.search(r"recomendar\s+(.+?)(?:\s+seguido de|\.|,|$)", content, flags=re.IGNORECASE)
    if explicit_recomendar:
        producto_recomendado = explicit_recomendar.strip()
    elif rec_match and not re.search(r"nunca\s+recomendar", content, flags=re.IGNORECASE):
        producto_recomendado = rec_match.group(1).strip()
    elif "sellomax" in lowered and "koraza" in lowered:
        producto_recomendado = "Sellomax + Koraza"

    producto_desestimado = None
    avoid_match = re.search(r"NUNCA\s+(?:recomendar|aplicar|usar|listar ni incluir)\s+(.+?)(?:\.|$)", content, flags=re.IGNORECASE)
    if explicit_evitar:
        producto_desestimado = explicit_evitar.strip()
    elif avoid_match:
        producto_desestimado = avoid_match.group(1).strip()

    nota_comercial = explicit_note.strip() if explicit_note else content

    return {
        "contexto_tags": contexto_tags,
        "nota_comercial": nota_comercial,
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


def _extract_latest_technical_payload(tool_calls_made: list) -> Optional[dict]:
    for tool_call in reversed(tool_calls_made or []):
        if tool_call.get("name") != "consultar_conocimiento_tecnico":
            continue
        raw_result = tool_call.get("result")
        if not raw_result:
            continue
        try:
            return json.loads(raw_result) if isinstance(raw_result, str) else raw_result
        except Exception:
            continue
    return None


def _split_policy_values(raw_value: Optional[str], m) -> list[str]:
    if not raw_value:
        return []
    cleaned = raw_value.replace("\n", ",")
    chunks = re.split(r"[;,]|\s+\|\s+", cleaned)
    results = []
    for chunk in chunks:
        value = (chunk or "").strip(" .:-")
        normalized = m.normalize_text_value(value)
        if len(normalized) < 3:
            continue
        if value not in results:
            results.append(value)
    return results


def _extract_forbidden_phrases_from_notes(expert_notes: list, m) -> list[str]:
    phrases = []
    patterns = [
        r"nunca\s+(?:recomendar|usar|aplicar|listar ni incluir|incluir)\s+(.+?)(?:\.|$)",
        r"prohibido\s+(?:usar|recomendar|incluir)\s+(.+?)(?:\.|$)",
        r"evitar\s+(.+?)(?:\.|$)",
    ]
    for note in expert_notes or []:
        for phrase in _split_policy_values(note.get("evitar"), m):
            if phrase not in phrases:
                phrases.append(phrase)
        note_text = note.get("nota") or ""
        for pattern in patterns:
            for match in re.finditer(pattern, note_text, flags=re.IGNORECASE):
                for phrase in _split_policy_values(match.group(1), m):
                    if phrase not in phrases:
                        phrases.append(phrase)
    return phrases


def _mention_is_negated(normalized_response: str, start_index: int) -> bool:
    window = normalized_response[max(0, start_index - 35):start_index]
    negation_cues = [" no ", " nunca ", " evita ", " evitar ", " prohibido ", " sin ", " jamas ", " jamás "]
    return any(cue in f" {window} " for cue in negation_cues)


def _find_positive_mentions(response_text: str, phrases: list[str], m) -> list[str]:
    normalized_response = f" {m.normalize_text_value(response_text or '')} "
    hits = []
    for phrase in phrases:
        normalized_phrase = m.normalize_text_value(phrase)
        if len(normalized_phrase) < 3:
            continue
        search_token = f" {normalized_phrase} "
        start = normalized_response.find(search_token)
        while start != -1:
            if not _mention_is_negated(normalized_response, start):
                if phrase not in hits:
                    hits.append(phrase)
                break
            start = normalized_response.find(search_token, start + len(search_token))
    return hits


def _find_missing_mentions(response_text: str, phrases: list[str], m) -> list[str]:
    normalized_response = f" {m.normalize_text_value(response_text or '')} "
    missing = []
    for phrase in phrases:
        normalized_phrase = m.normalize_text_value(phrase)
        if len(normalized_phrase) < 3:
            continue
        if f" {normalized_phrase} " not in normalized_response:
            missing.append(phrase)
    return missing


def _collect_technical_evidence_text(technical_payload: dict, tool_calls_made: list, m) -> str:
    parts = []
    for key in [
        "diagnostico_estructurado",
        "guia_tecnica_estructurada",
        "perfil_tecnico_principal",
        "guias_tecnicas_relacionadas",
        "contexto_guias",
        "conocimiento_comercial_ferreinox",
        "respuesta_rag",
    ]:
        value = technical_payload.get(key)
        if not value:
            continue
        try:
            parts.append(json.dumps(value, ensure_ascii=False, default=str))
        except Exception:
            parts.append(str(value))

    for tool_call in tool_calls_made or []:
        if tool_call.get("name") != "consultar_conocimiento_tecnico":
            continue
        args = tool_call.get("args") or {}
        if args:
            try:
                parts.append(json.dumps(args, ensure_ascii=False, default=str))
            except Exception:
                parts.append(str(args))

    return m.normalize_text_value(" ".join(parts))


def _guardia_consistencia_tecnica(assistant_message, messages, tool_calls_made, context, conversation_context, m):
    technical_payload = _extract_latest_technical_payload(tool_calls_made)
    if not technical_payload:
        return assistant_message

    response_text = assistant_message.content or ""
    if not response_text.strip():
        return assistant_message

    expert_notes = technical_payload.get("conocimiento_comercial_ferreinox") or []
    structured_guide = technical_payload.get("guia_tecnica_estructurada") or {}
    hard_policies = technical_payload.get("politicas_duras_contexto") or {}
    forbidden_phrases = _extract_forbidden_phrases_from_notes(expert_notes, m)
    for forbidden in structured_guide.get("forbidden_products_or_shortcuts") or []:
        for phrase in _split_policy_values(forbidden, m):
            if phrase not in forbidden_phrases:
                forbidden_phrases.append(phrase)
    for forbidden in (hard_policies.get("forbidden_products") or []) + (hard_policies.get("forbidden_tools") or []):
        if forbidden not in forbidden_phrases:
            forbidden_phrases.append(forbidden)

    forbidden_hits = _find_positive_mentions(response_text, forbidden_phrases, m)
    required_items = list(dict.fromkeys((hard_policies.get("required_products") or []) + (hard_policies.get("required_tools") or [])))
    missing_required_items = _find_missing_mentions(response_text, required_items, m) if required_items else []
    mandatory_step_signals = hard_policies.get("mandatory_step_signals") or []
    missing_mandatory_steps = _find_missing_mentions(response_text, mandatory_step_signals, m) if mandatory_step_signals else []

    evidence_text = _collect_technical_evidence_text(technical_payload, tool_calls_made, m)
    unsupported_products = []
    normalized_response = m.normalize_text_value(response_text)
    for product_name in _TECHNICAL_PRODUCT_GUARD_SIGNALS:
        normalized_product = m.normalize_text_value(product_name)
        if f" {normalized_product} " not in f" {normalized_response} ":
            continue
        if f" {normalized_product} " in f" {evidence_text} ":
            continue
        response_index = normalized_response.find(normalized_product)
        if _mention_is_negated(f" {normalized_response} ", response_index + 1):
            continue
        if product_name not in unsupported_products:
            unsupported_products.append(product_name)

    if not forbidden_hits and not unsupported_products and not missing_required_items and not missing_mandatory_steps:
        return assistant_message

    try:
        from agent_prompt_v3 import AGENT_TOOLS_V3
    except ImportError:
        from backend.agent_prompt_v3 import AGENT_TOOLS_V3

    correction_lines = [
        "⛔ INCONSISTENCIA TÉCNICA DETECTADA.",
        "Tu respuesta final contradice reglas duras o está ofreciendo productos no respaldados por las herramientas de este turno.",
    ]
    if forbidden_hits:
        correction_lines.append("PROHIBIDOS mencionados como opción válida: " + ", ".join(forbidden_hits[:8]))
    if unsupported_products:
        correction_lines.append("PRODUCTOS SIN RESPALDO en herramientas de este turno: " + ", ".join(unsupported_products[:8]))
    if missing_required_items:
        correction_lines.append("ELEMENTOS OBLIGATORIOS AUSENTES en la respuesta: " + ", ".join(missing_required_items[:8]))
    if missing_mandatory_steps:
        correction_lines.append("PASOS O SEÑALES OBLIGATORIAS AUSENTES en la respuesta: " + ", ".join(missing_mandatory_steps[:8]))

    if hard_policies:
        correction_lines.append("POLÍTICAS DURAS ACTIVAS:")
        if hard_policies.get("policy_names"):
            correction_lines.append("- Paquetes activos: " + ", ".join(hard_policies.get("policy_names")[:8]))
        if hard_policies.get("critical_policy_names"):
            correction_lines.append("- Políticas críticas dominantes: " + ", ".join(hard_policies.get("critical_policy_names")[:6]))
        elif hard_policies.get("dominant_policy_names"):
            correction_lines.append("- Rutas dominantes a priorizar: " + ", ".join(hard_policies.get("dominant_policy_names")[:6]))
        if hard_policies.get("required_products"):
            correction_lines.append("- Productos obligatorios: " + ", ".join(hard_policies.get("required_products")[:8]))
        if hard_policies.get("forbidden_products"):
            correction_lines.append("- Productos prohibidos: " + ", ".join(hard_policies.get("forbidden_products")[:8]))
        if hard_policies.get("required_tools"):
            correction_lines.append("- Herramientas obligatorias: " + ", ".join(hard_policies.get("required_tools")[:8]))
        if hard_policies.get("forbidden_tools"):
            correction_lines.append("- Herramientas prohibidas: " + ", ".join(hard_policies.get("forbidden_tools")[:8]))
        if hard_policies.get("mandatory_steps"):
            correction_lines.append("- Pasos obligatorios: " + "; ".join(hard_policies.get("mandatory_steps")[:6]))
        if hard_policies.get("mandatory_step_signals"):
            correction_lines.append("- Señales mínimas que deben quedar explícitas: " + ", ".join(hard_policies.get("mandatory_step_signals")[:8]))

    if expert_notes:
        correction_lines.append("REGLAS EXPERTAS ACTIVAS:")
        for note in expert_notes[:6]:
            line = f"- [{(note.get('tipo') or '').upper()}] {note.get('nota') or ''}"
            if note.get("recomendar"):
                line += f" | RECOMENDAR: {note.get('recomendar')}"
            if note.get("evitar"):
                line += f" | EVITAR: {note.get('evitar')}"
            correction_lines.append(line)

    if structured_guide.get("forbidden_products_or_shortcuts"):
        correction_lines.append(
            "ATAJOS / PROHIBICIONES DE LA GUÍA: "
            + "; ".join(structured_guide.get("forbidden_products_or_shortcuts")[:6])
        )

    correction_lines.extend([
        "REESCRIBE la respuesta FINAL usando SOLO productos, procesos y herramientas respaldados por las herramientas ya ejecutadas.",
        "Si no tienes evidencia suficiente para un producto, NO lo ofrezcas como alternativa.",
        "Puedes advertir explícitamente lo prohibido, pero NO listarlo como opción de compra o aplicación.",
        "No llames más herramientas.",
    ])

    messages.append(assistant_message)
    messages.append({"role": "system", "content": "\n".join(correction_lines)})

    t = time.time()
    resp = m.get_openai_client().chat.completions.create(
        model=m.get_openai_model(), messages=messages,
        tools=AGENT_TOOLS_V3, tool_choice="none", temperature=0.2,
    )
    assistant_message = resp.choices[0].message
    logger.info("V3 GUARDIA CONSISTENCIA TÉCNICA completed: %dms", int((time.time() - t) * 1000))
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
