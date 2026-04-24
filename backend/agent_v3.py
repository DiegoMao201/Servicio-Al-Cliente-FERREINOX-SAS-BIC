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


def _load_agent_runtime_config() -> dict:
    try:
        from agent_profiles import get_agent_runtime_config
    except ImportError:
        from backend.agent_profiles import get_agent_runtime_config
    return get_agent_runtime_config()


def _get_active_agent_tools() -> list[dict]:
    return _load_agent_runtime_config()["tools"]

_TECHNICAL_PRODUCT_GUARD_SIGNALS = [
    "koraza", "intervinil", "pinturama", "viniltex", "aquablock", "sellomax",
    "pintucoat", "intergard", "interseal", "interthane", "corrotec", "pintulux",
    "barnex", "siliconite", "construcleaner", "wood stain", "pintoxido", "pintóxido",
    "lija abracol", "lijas de agua", "papel de lija",
]

logger = logging.getLogger("agent_v3")

_INTERNAL_REPORT_EMAIL_RE = re.compile(r"\b[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,}\b", re.IGNORECASE)
_INTERNAL_REPORT_EMAIL_SIGNALS = (
    "envialo",
    "envíalo",
    "enviamelo",
    "envíamelo",
    "mandalo",
    "mándalo",
    "mandamelo",
    "mándamelo",
    "reenvialo",
    "reenvíalo",
    "correo",
    "mail",
    "email",
)

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


def _should_force_internal_report_email_tool(agent_profile: str, user_message: str, conversation_context: dict) -> bool:
    if agent_profile != "internal":
        return False
    remembered_report = (conversation_context or {}).get("last_internal_report_request") or {}
    if not remembered_report:
        return False
    normalized = " ".join((user_message or "").lower().split())
    if not normalized:
        return False
    if not _INTERNAL_REPORT_EMAIL_RE.search(user_message or ""):
        return False
    return any(signal in normalized for signal in _INTERNAL_REPORT_EMAIL_SIGNALS)


_TECHNICAL_RESPONSE_SECTIONS = [
    "**Diagnóstico:**",
    "**Sistema Recomendado:**",
    "**Preparación de Superficie:**",
    "**Cantidades y Mezcla:**",
    "**Restricciones Técnicas:**",
    "**Cierre Comercial:**",
]


def _response_looks_like_technical_recommendation(response_text: str, m) -> bool:
    normalized = m.normalize_text_value(response_text or "")
    if not normalized:
        return False
    if any(section.lower() in (response_text or "").lower() for section in _TECHNICAL_RESPONSE_SECTIONS):
        return True
    recommendation_markers = [
        "recomiendo", "sistema recomendado", "aplica", "aplicar", "usa ", "usar ",
        "producto", "productos", "primer", "acabado", "sellador", "diluyente",
        "manos", "rendimiento", "mezcla", "catalizador",
    ]
    if any(marker in normalized for marker in recommendation_markers):
        return True
    return any(signal in normalized for signal in _TECHNICAL_PRODUCT_GUARD_SIGNALS)


def _enforce_verified_technical_guidance(
    response_text: str,
    *,
    effective_advisory_flow: bool,
    recommendation_ready: bool,
    best_effort_ready: bool,
    conversation_context: dict,
    technical_case: Optional[dict],
    m,
) -> str:
    if not effective_advisory_flow:
        return response_text
    if not (recommendation_ready or best_effort_ready):
        return response_text
    if conversation_context.get("latest_technical_guidance"):
        return response_text
    if not _response_looks_like_technical_recommendation(response_text, m):
        return response_text

    category = ((technical_case or {}).get("category") or "caso técnico").strip()
    return (
        "Tengo un diagnóstico base del caso, pero no te voy a cerrar un sistema ni productos sin respaldo técnico verificable del RAG. "
        f"En este momento no quedó una guía técnica confiable para {category}. "
        "Si me indicas el producto o la marca exacta que quieres validar, busco la ficha puntual; "
        "si no, mantengo la asesoría en diagnóstico y ruta técnica sin inventar recomendación."
    )


def _build_dynamic_consultive_questions(technical_case: Optional[dict], m) -> list[str]:
    case = dict(technical_case or {})
    category = (case.get("category") or "").strip().lower()
    conversation_history = case.get("conversation_history") or []
    normalized_context = m.normalize_text_value(
        " ".join([str(case.get("last_user_message") or "")] + [str(item) for item in conversation_history[-4:]])
    )

    questions: list[str] = []
    if hasattr(m, "build_technical_diagnostic_questions") and category in {"humedad", "fachada", "piso", "madera", "metal"}:
        try:
            questions.extend(m.build_technical_diagnostic_questions(case) or [])
        except Exception:
            pass

    if category == "metal" and any(token in normalized_context for token in ["teja", "zinc", "galvaniz", "cubierta metalica", "cubierta metálica"]):
        questions.insert(0, "¿La teja es nueva (galvanizada) o ya presenta oxidación?")

    if category in {"fachada", "humedad"} and any(token in normalized_context for token in ["fachada", "muro exterior", "exterior", "intemperie"]):
        questions.insert(0, "¿Presenta fisuras o humedad activa?")

    deduped: list[str] = []
    seen: set[str] = set()
    for question in questions:
        normalized_question = (question or "").strip().lower()
        if not normalized_question or normalized_question in seen:
            continue
        seen.add(normalized_question)
        deduped.append(question.strip())
    return deduped[:2]


def _build_consultive_block_message(technical_case: Optional[dict], m=None) -> str:
    profile = dict((technical_case or {}).get("recommendation_profile") or (technical_case or {}).get("project_profile") or {})
    missing_fields = profile.get("missing_fields") or []
    missing_labels = [item.get("description") or item.get("field") for item in missing_fields if isinstance(item, dict)]
    if not missing_labels:
        missing_labels = [
            "tipo de sustrato",
            "estado actual de la superficie",
            "ambiente de exposición",
        ]
    dynamic_questions = _build_dynamic_consultive_questions(technical_case, m) if m is not None else []
    if dynamic_questions:
        return (
            "BLOQUEO CONSULTIVO OBLIGATORIO: el perfil del proyecto sigue incompleto. "
            "Tienes PROHIBIDO recomendar productos, sistemas, rendimientos o inventario en este turno. "
            "Solo puedes hacer preguntas diagnósticas para destrabar el caso. "
            "Prioriza exactamente estas preguntas antes de cualquier recomendación: "
            + " ".join(dynamic_questions)
            + " Cuando el cliente las aclare, recién ahí podrás activar consultar_conocimiento_tecnico."
        )
    return (
        "BLOQUEO CONSULTIVO OBLIGATORIO: el perfil del proyecto sigue incompleto. "
        "Tienes PROHIBIDO recomendar productos, sistemas, rendimientos o inventario en este turno. "
        "Solo puedes hacer preguntas diagnósticas para cerrar estos puntos: "
        + ", ".join(missing_labels[:4])
        + ". Cuando el cliente aclare esos datos, recién ahí podrás activar consultar_conocimiento_tecnico."
    )


def _build_classifier_system_directives(technical_case: Optional[dict], m) -> Optional[str]:
    case = dict(technical_case or {})
    category = (case.get("category") or "").strip().lower()
    if not category:
        return None

    conversation_history = case.get("conversation_history") or []
    normalized_context = m.normalize_text_value(
        " ".join([str(case.get("last_user_message") or "")] + [str(item) for item in conversation_history[-4:]])
    )

    lines = [
        "INSTRUCCION TEMPORAL DEL CLASIFICADOR: usa esta categoría como marco operativo del turno.",
        f"categoria_dominante={category}",
    ]

    if category == "metal":
        lines.append("Trata el caso como sistema metálico y no como ruta arquitectónica decorativa.")
        lines.append("PROHIBIDO recomendar sistemas base agua arquitectónicos sin anticorrosivo o promotor de adherencia cuando el caso sea metálico.")
        if any(token in normalized_context for token in ["teja", "zinc", "galvaniz", "cubierta metalica", "cubierta metálica"]):
            lines.append("Antes de recomendar, valida si la teja es galvanizada nueva o si ya presenta oxidación.")
    elif category in {"fachada", "humedad"}:
        lines.append("No cierres la ruta como acabado decorativo mientras sigan abiertas fisuras o humedad activa.")
        if any(token in normalized_context for token in ["fachada", "muro exterior", "exterior", "intemperie"]):
            lines.append("Antes del sistema final, valida si hay fisuras o humedad activa en la fachada.")
    elif category == "piso":
        lines.append("Antes de recomendar, valida curado, tráfico e interior/exterior del piso.")
    elif category == "madera":
        lines.append("Antes de recomendar, valida si la madera es interior/exterior y si el cliente quiere veta natural o cubrimiento.")

    return " ".join(lines)


_MAX_DIAGNOSTIC_TURNS_BEFORE_BEST_EFFORT = 2


def _recommendation_ready_for_rag(technical_case: Optional[dict]) -> bool:
    case = dict(technical_case or {})
    if case.get("recommendation_ready"):
        return True
    profile = dict(case.get("recommendation_profile") or {})
    return bool(profile.get("complete"))


def _best_effort_ready_for_rag(
    effective_advisory_flow: bool,
    initial_diagnostic: dict,
    technical_case: Optional[dict],
) -> bool:
    if not effective_advisory_flow:
        return False
    if _recommendation_ready_for_rag(technical_case):
        return True

    case = dict(technical_case or {})
    diagnostic_turns = int(case.get("diagnostic_turns") or 0)
    if diagnostic_turns < _MAX_DIAGNOSTIC_TURNS_BEFORE_BEST_EFFORT:
        return False

    surface = initial_diagnostic.get("surface") or case.get("category")
    condition = initial_diagnostic.get("condition") or case.get("current_state")
    location = (
        initial_diagnostic.get("interior_exterior")
        or case.get("exposure_environment")
        or case.get("floor_location")
        or case.get("wall_location")
    )
    return bool(surface and condition and location)


def _technical_response_has_required_sections(response_text: str) -> bool:
    normalized = response_text or ""
    return all(section in normalized for section in _TECHNICAL_RESPONSE_SECTIONS)


def _should_route_to_inventory_lookup(initial_intent: str, conversation_context: dict, m) -> bool:
    if initial_intent != "consulta_productos":
        return False
    if (conversation_context.get("commercial_draft") or {}).get("items"):
        return False
    return hasattr(m, "build_inventory_lookup_reply")


def _is_explicit_inventory_query(user_message: str) -> bool:
    """Detect messages that are clearly inventory lookups (e.g. 'inventario de sd1')."""
    msg_lower = (user_message or "").strip().lower()
    if re.search(r'\binventario\s+de\b', msg_lower):
        return True
    if re.search(r'\bdame\b.*\binventario\b', msg_lower):
        return True
    return False


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
    # If the initial diagnostic is already substantially complete
    # (surface + condition + location), we want to preload RAG even if
    # the technical_case hasn't been promoted to ready=True yet.
    # Otherwise apply the conservative best-effort gate.
    diagnostic_substantially_complete = bool(
        initial_diagnostic.get("surface")
        and initial_diagnostic.get("condition")
        and (
            initial_diagnostic.get("interior_exterior")
            or initial_diagnostic.get("traffic")
            or initial_diagnostic.get("humidity_source")
        )
    )
    if (
        technical_case
        and not diagnostic_substantially_complete
        and not _best_effort_ready_for_rag(True, initial_diagnostic, technical_case)
    ):
        return False

    # ── CRITICAL: never preload if diagnostic is still incomplete ──
    # This prevents the agent from skipping diagnostic questions.
    try:
        from agent_context import is_diagnostic_incomplete
    except ImportError:
        from backend.agent_context import is_diagnostic_incomplete
    if is_diagnostic_incomplete(initial_intent, initial_diagnostic):
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

    # If we have surface context AND any structured detail (condition, location, etc.),
    # ALWAYS preload RAG. This is the #1 defense against hallucinated recommendations.
    if has_surface_context and has_structured_detail:
        return True

    return bool(
        has_surface_context
        and (
            (technical_case or {}).get("ready")
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


def _infer_active_technical_category(conversation_context: dict, m) -> Optional[str]:
    active_case = dict((conversation_context or {}).get("technical_advisory_case") or {})
    active_category = (active_case.get("category") or "").strip().lower()
    if active_category and active_category != "general":
        return active_category

    draft = dict((conversation_context or {}).get("commercial_draft") or {})
    guidance = draft.get("technical_guidance") or (conversation_context or {}).get("latest_technical_guidance") or {}
    if not isinstance(guidance, dict) or not guidance:
        return None

    diagnosis = dict(guidance.get("diagnostico_estructurado") or {})
    problem_class = m.normalize_text_value(diagnosis.get("problem_class") or "")
    if any(token in problem_class for token in ["metal", "oxid", "galvan", "interthane", "intergard", "interseal", "pintucoat"]):
        return "metal"
    if any(token in problem_class for token in ["madera", "barnex", "wood stain"]):
        return "madera"
    if any(token in problem_class for token in ["piso", "trafico", "cancha"]):
        return "piso"
    if any(token in problem_class for token in ["humedad", "fachada", "eternit", "fibrocemento", "ladrillo", "cubierta", "terraza"]):
        return "humedad"

    source_text = " ".join(
        part for part in [
            str(guidance.get("source_question") or ""),
            str(guidance.get("source_product") or ""),
        ]
        if part
    )
    inferred = m.infer_technical_problem_category(source_text or None)
    if inferred and inferred != "general":
        return inferred
    return None


def _detect_new_technical_topic_switch(user_message: str, conversation_context: dict, m) -> Optional[dict]:
    if not user_message:
        return None
    context = conversation_context or {}
    if not (context.get("commercial_draft") or context.get("latest_technical_guidance") or context.get("technical_advisory_case")):
        return None

    try:
        fresh_case = m.extract_technical_advisory_case(user_message, {})
    except Exception:
        return None

    new_category = (fresh_case.get("category") or "").strip().lower()
    if not new_category or new_category == "general":
        return None

    active_category = _infer_active_technical_category(context, m)
    if not active_category or active_category == "general":
        return None
    if active_category == new_category:
        return None

    return {
        "active_category": active_category,
        "new_category": new_category,
        "technical_case": fresh_case,
    }


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
        from agent_context import build_turn_context, classify_intent, extract_diagnostic_data, is_diagnostic_incomplete
    except ImportError:
        from backend.agent_context import build_turn_context, classify_intent, extract_diagnostic_data, is_diagnostic_incomplete

    agent_runtime = _load_agent_runtime_config()
    active_tools = agent_runtime["tools"]
    system_prompt_template = agent_runtime["system_prompt"]
    agent_profile = agent_runtime["profile"]
    force_first_advisory_depth_turn = agent_runtime.get("force_first_advisory_depth_turn", True)

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

    case_reference = m.resolve_referenced_technical_case(user_message, conversation_context)
    if case_reference.get("status") == "ambiguous":
        candidate_summaries = [candidate.get("summary") or candidate.get("case_id") for candidate in (case_reference.get("candidates") or [])]
        if candidate_summaries:
            if len(candidate_summaries) == 1:
                options_text = candidate_summaries[0]
            elif len(candidate_summaries) == 2:
                options_text = f"{candidate_summaries[0]} o {candidate_summaries[1]}"
            else:
                options_text = ", ".join(candidate_summaries[:-1]) + f" o {candidate_summaries[-1]}"
            response_text = (
                "Tengo varios casos abiertos y no quiero cruzarte los sistemas. "
                f"¿Te refieres a {options_text}?"
            )
            return {
                "response_text": response_text,
                "intent": "asesoria_tecnica",
                "tool_calls": [],
                "context_updates": {
                    "pending_case_resolution_candidates": case_reference.get("candidates") or [],
                },
                "should_create_task": False,
                "confidence": m.score_agent_confidence(response_text, [], "asesoria_tecnica"),
                "is_farewell": False,
            }

    if case_reference.get("status") == "matched":
        target_case_id = case_reference.get("case_id")
        if target_case_id and target_case_id != conversation_context.get("active_technical_case_id"):
            logger.info("V3 reactivating prior technical case: %s", target_case_id)
            activated_case_updates = m.activate_technical_case(target_case_id, conversation_context)
            if activated_case_updates:
                conversation_context.update(activated_case_updates)
                conversation_context["_advisory_diagnostic_turn_done"] = conversation_context.get("_advisory_diagnostic_turn_done", False)

    conversation_context["pending_case_resolution_candidates"] = []

    topic_switch = _detect_new_technical_topic_switch(user_message, conversation_context, m)
    if topic_switch:
        logger.info(
            "V3 technical topic switch detected: %s -> %s; clearing stale draft/guidance",
            topic_switch.get("active_category"),
            topic_switch.get("new_category"),
        )
        current_case = dict((conversation_context or {}).get("technical_advisory_case") or {})
        if current_case:
            current_case_updates = m.sync_technical_case_registry(
                conversation_context,
                current_case,
                commercial_draft=conversation_context.get("commercial_draft"),
                technical_guidance=conversation_context.get("latest_technical_guidance") or (conversation_context.get("commercial_draft") or {}).get("technical_guidance"),
            )
            conversation_context.update(current_case_updates)

        new_case_updates = m.sync_technical_case_registry(
            conversation_context,
            dict(topic_switch.get("technical_case") or {}),
            force_new_case=True,
        )
        conversation_context.update(new_case_updates)
        conversation_context["commercial_draft"] = {}
        conversation_context["latest_technical_guidance"] = {}
        conversation_context["_advisory_diagnostic_turn_done"] = False
        initial_intent = "asesoria"

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

    # ── Farewell short-circuit — no LLM needed ──
    if initial_intent == "despedida" and m.detect_farewell(user_message or ""):
        greeting_name = (profile_name or nombre_cliente or "").strip()
        if greeting_name:
            response_text = f"¡Con gusto, {greeting_name}! Aquí estaré cuando me necesites. ¡Que te vaya bien! 👋"
        else:
            response_text = "¡Con gusto! Aquí estaré cuando me necesites. ¡Que te vaya bien! 👋"
        return {
            "response_text": response_text,
            "intent": "despedida",
            "tool_calls": [],
            "context_updates": {},
            "should_create_task": False,
            "confidence": m.score_agent_confidence(response_text, [], "despedida"),
            "is_farewell": True,
        }

    # ── Explicit inventory query with active draft → clear draft so LLM sees clean state ──
    if _is_explicit_inventory_query(user_message):
        conversation_context.pop("commercial_draft", None)

    # ══════════════════════════════════════════════════════════════════════
    # PIPELINE PEDIDO DETERMINÍSTICO — Intercepta pedidos directos antes
    # del LLM. Resuelve productos, genera Excel, envía correos, todo sin IA.
    # ══════════════════════════════════════════════════════════════════════
    if agent_runtime.get("enable_order_pipeline", True):
        try:
            from pipeline_pedido.integracion_pedido import (
                interceptar_pedido_si_aplica,
                interceptar_respuesta_ral_pedido,
            )

            # Primero: ¿está respondiendo un RAL pendiente?
            ral_pendiente = interceptar_respuesta_ral_pedido(
                conversation_context, user_message,
            )
            if ral_pendiente:
                logger.info("V3 pipeline_pedido: RAL pendiente detectado → %s", ral_pendiente)

            # Segundo: ¿es un pedido directo nuevo?
            intercepcion = interceptar_pedido_si_aplica(
                main_module=m,
                conversation_context=conversation_context,
                user_message=user_message,
                tool_calls_made=[],
                context=context,
                lookup_fn=getattr(m, "lookup_product_context", None),
                price_fn=getattr(m, "fetch_product_price", None),
            )
            if intercepcion:
                logger.info(
                    "V3 pipeline_pedido: INTERCEPTADO — %d resueltos, intent=%s",
                    len((intercepcion.get("context_updates", {}).get("_pedido_match_result") or {}).get("productos_resueltos", [])),
                    intercepcion.get("intent", "pedido"),
                )
                return intercepcion

        except ImportError:
            logger.debug("pipeline_pedido no disponible, continuando con LLM")
        except Exception as e:
            logger.error("pipeline_pedido error: %s", e, exc_info=True)
    else:
        logger.info("V3 order pipeline disabled for profile=%s", agent_profile)

    # ══════════════════════════════════════════════════════════════════════
    # LLM AS CONVERSATIONAL BRAIN — no more short-circuits for inventory
    # or commercial.  The LLM decides which tools to call.  Python executes.
    # ══════════════════════════════════════════════════════════════════════

    # ── Construir contexto de turno dinámico ─────────────────────────────
    contexto_turno = build_turn_context(
        conversation_context=conversation_context,
        recent_messages=recent_messages,
        user_message=user_message,
        internal_auth=internal_auth,
        profile_name=profile_name,
    )

    # ── Formatear prompt V3 ──────────────────────────────────────────────
    system_content = system_prompt_template.format(
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
    _location_optional_surfaces = {"fachada", "exterior", "madera exterior", "piso deportivo"}
    _has_actionable_diagnostic = bool(
        initial_diagnostic.get("surface")
        and initial_diagnostic.get("condition")
        and (
            initial_diagnostic.get("interior_exterior")
            or initial_diagnostic.get("surface") in _location_optional_surfaces
        )
    )
    effective_advisory_flow = initial_intent == "asesoria" or _has_actionable_diagnostic
    if effective_advisory_flow and initial_intent != "asesoria":
        logger.info(
            "V3 advisory promotion: intent=%s surface=%s condition=%s location=%s",
            initial_intent,
            initial_diagnostic.get("surface"),
            initial_diagnostic.get("condition"),
            initial_diagnostic.get("interior_exterior"),
        )
    normalized_user_message = m.normalize_text_value(user_message)
    tool_calls_made = []
    _rag_cache: dict[str, str] = {}
    _tool_type_counts: dict[str, int] = {}
    has_active_technical_guidance = bool(conversation_context.get("latest_technical_guidance"))
    _TOOL_MAX_CALLS = {
        "consultar_conocimiento_tecnico": 1 if has_active_technical_guidance else 2,
        "buscar_documento_tecnico": 2,
        "confirmar_pedido_y_generar_pdf": 1,
        "registrar_reclamo": 1,
    }

    technical_case = None
    if hasattr(m, "extract_technical_advisory_case"):
        try:
            technical_case = m.extract_technical_advisory_case(user_message, conversation_context)
            case_updates = m.sync_technical_case_registry(
                conversation_context,
                technical_case,
                commercial_draft=conversation_context.get("commercial_draft"),
                technical_guidance=conversation_context.get("latest_technical_guidance") or (conversation_context.get("commercial_draft") or {}).get("technical_guidance"),
            )
            conversation_context.update(case_updates)
            technical_case = dict(conversation_context.get("technical_advisory_case") or technical_case)
        except Exception:
            technical_case = None

    project_profile = dict((technical_case or {}).get("project_profile") or {})
    project_profile_complete = bool((technical_case or {}).get("ready") and project_profile.get("complete"))
    recommendation_profile = dict((technical_case or {}).get("recommendation_profile") or {})
    recommendation_ready = _recommendation_ready_for_rag(technical_case)
    best_effort_ready = _best_effort_ready_for_rag(effective_advisory_flow, initial_diagnostic, technical_case)
    classifier_system_directive = _build_classifier_system_directives(technical_case, m)
    if classifier_system_directive:
        messages.append({"role": "system", "content": classifier_system_directive})

    # ══════════════════════════════════════════════════════════════════════
    # PYTHON-LEVEL DIAGNOSTIC ENFORCEMENT
    # Two layers:
    #   1. BROAD CHECK: surface + condition + location must be present
    #      (keyword detection is reliable for broad categories)
    #   2. PROCESS CHECK: first advisory turn always requires a diagnostic
    #      exchange — the LLM (IA) asks the right depth questions
    #      (material, m², specific conditions) without keyword matching.
    # ══════════════════════════════════════════════════════════════════════
    _diagnostic_blocked = is_diagnostic_incomplete("asesoria" if effective_advisory_flow else initial_intent, initial_diagnostic)
    if effective_advisory_flow and not best_effort_ready:
        _diagnostic_blocked = True

    # Process gate: on the FIRST advisory turn (no prior RAG, no prior
    # diagnostic exchange), block tools so the LLM must ask depth questions.
    # The LLM is the AI — it understands what the client said and knows
    # what to ask. Python only enforces the PROCESS (diagnose → RAG → recommend).
    _first_advisory_turn = (
        effective_advisory_flow
        and not _diagnostic_blocked  # broad checks already passed
        and not conversation_context.get("_advisory_diagnostic_turn_done")
        and not conversation_context.get("latest_technical_guidance")
    )
    if _first_advisory_turn and force_first_advisory_depth_turn:
        _diagnostic_blocked = True
        logger.info("V3 FIRST ADVISORY TURN: broad diagnostic OK but forcing depth questions — LLM (IA) decides what to ask")

    if _diagnostic_blocked:
        logger.info("V3 BLOQUEO ACTIVO: tools stripped, skipping preload")
        if conversation_context.get("technical_advisory_case"):
            conversation_context["technical_advisory_case"]["stage"] = "diagnosing"
        if effective_advisory_flow:
            messages.append({
                "role": "system",
                "content": _build_consultive_block_message(technical_case, m),
            })
    elif conversation_context.get("technical_advisory_case"):
        conversation_context["technical_advisory_case"]["stage"] = "advising"

    if not _diagnostic_blocked and _should_preload_technical_guidance(
        "asesoria" if effective_advisory_flow else initial_intent,
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

    _force_internal_report_email_tool = _should_force_internal_report_email_tool(
        agent_profile,
        user_message,
        conversation_context,
    )
    if _force_internal_report_email_tool:
        remembered_report = dict(conversation_context.get("last_internal_report_request") or {})
        messages.append({
            "role": "system",
            "content": (
                "CONTINUIDAD OBLIGATORIA DE REPORTE INTERNO: el colaborador está pidiendo enviar o reenviar por correo el último reporte interno ya consultado. "
                "Debes llamar enviar_reporte_interno_correo en este turno usando el correo mencionado por el usuario y reutilizando los filtros del último reporte recordado. "
                "Nunca confirmes envío exitoso sin ejecutar esa herramienta.\n"
                f"Último reporte recordado: {json.dumps(remembered_report, ensure_ascii=False)}"
            ),
        })

    def _needs_forced_technical_retry() -> bool:
        if tool_calls_made or assistant_message.tool_calls:
            return False
        if not effective_advisory_flow:
            return False
        if not best_effort_ready:
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
    _llm_extra_kwargs: dict = {}
    if _diagnostic_blocked:
        # Omit tools AND tool_choice entirely — OpenAI rejects tool_choice without tools
        pass
    else:
        _llm_extra_kwargs["tools"] = active_tools
        # For advisory with complete diagnosis, FORCE at least one tool call
        # so the LLM cannot skip RAG and hallucinate product recommendations.
        _advisory_complete = (
            effective_advisory_flow
            and not _diagnostic_blocked
            and (recommendation_ready or best_effort_ready)
        )
        if _force_internal_report_email_tool:
            _llm_extra_kwargs["tool_choice"] = {
                "type": "function",
                "function": {"name": "enviar_reporte_interno_correo"},
            }
            _llm_extra_kwargs["parallel_tool_calls"] = False
            logger.info("V3 internal report email continuation — forcing enviar_reporte_interno_correo")
        elif _advisory_complete and not tool_calls_made:
            _llm_extra_kwargs["tool_choice"] = "required"
            logger.info("V3 advisory complete — forcing tool_choice=required")
        else:
            _llm_extra_kwargs["tool_choice"] = "auto"
            _llm_extra_kwargs["parallel_tool_calls"] = True

    t_start = time.time()
    response = client.chat.completions.create(
        model=m.get_openai_model(),
        messages=messages,
        temperature=0.2,
        **_llm_extra_kwargs,
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
            tools=active_tools,
            tool_choice="auto",
            parallel_tool_calls=True,
            temperature=0.2,
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

        # After successful PDF generation, force the LLM to produce only a short
        # confirmation text — no more tool calls allowed.
        _pdf_succeeded = any(
            tc_info["name"] == "confirmar_pedido_y_generar_pdf"
            and '"exito": true' in (tc_info.get("result") or "").lower()
            for tc_info in tool_calls_made
        )

        t_loop = time.time()
        response = client.chat.completions.create(
            model=m.get_openai_model(),
            messages=messages,
            tools=active_tools,
            tool_choice="none" if _pdf_succeeded else "auto",
            parallel_tool_calls=True,
            temperature=0.2,
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
            tools=active_tools,
            tool_choice="none",
            temperature=0.3,
        )
        assistant_message = resp_force.choices[0].message
        logger.info("V3 forced text response: %dms", int((time.time() - t_force) * 1000))

    total_ms = int((time.time() - t_start) * 1000)
    tool_names = [tc["name"] for tc in tool_calls_made]
    logger.info("V3 agent TOTAL: %dms | tools=%s | iters=%d", total_ms, tool_names, iteration)

    # ══════════════════════════════════════════════════════════════════════
    # PIPELINE DETERMINÍSTICO — Intercepta cotizaciones antes de las guardias
    # Si la respuesta es una cotización, el pipeline la reemplaza con datos
    # 100% del backend. El LLM NO participa en precios/SKUs/cantidades.
    # ══════════════════════════════════════════════════════════════════════
    if agent_runtime.get("enable_quote_pipeline", True):
        try:
            from pipeline_deterministico.integracion import interceptar_cotizacion_si_aplica
            _pipeline_result = interceptar_cotizacion_si_aplica(
                main_module=m,
                openai_client=client,
                conversation_context=conversation_context,
                user_message=user_message,
                tool_calls_made=tool_calls_made,
                context=context,
                messages=messages,
                assistant_message=assistant_message,
            )
            if _pipeline_result:
                logger.info("V3: Pipeline determinístico interceptó la cotización")
                return _pipeline_result
        except Exception as _pipe_err:
            logger.warning("V3: Pipeline determinístico falló, continuando con flujo normal: %s", _pipe_err)
    else:
        logger.info("V3 quote pipeline disabled for profile=%s", agent_profile)

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
    if agent_runtime.get("enable_iva_guard", True) and not is_greeting:
        assistant_message = _guardia_iva(assistant_message, messages, m)

    # ── GUARDIA CONSISTENCIA TÉCNICA: expert rules / RAG duro vs respuesta final ─────
    assistant_message = _guardia_consistencia_tecnica(
        assistant_message, messages, tool_calls_made, context, conversation_context, m
    )

    # ── GUARDIA DE FORMATO TÉCNICO: estructura final obligatoria ─────
    assistant_message = _guardia_formato_tecnico(
        assistant_message, messages, tool_calls_made, conversation_context, m
    )

    # ── GUARDIA UNIVERSAL DE PRODUCTO: todo producto debe venir de herramientas ──
    if not is_ensenar_msg and not is_greeting:
        assistant_message = _guardia_universal_producto(
            assistant_message, messages, tool_calls_made, context, conversation_context, m
        )

    # ══════════════════════════════════════════════════════════════════════
    # POST-PROCESAMIENTO
    # ══════════════════════════════════════════════════════════════════════

    # Intent clasificación para el retorno
    intent = _classify_return_intent(tool_calls_made, user_message, m)

    response_text = assistant_message.content or "Gracias por escribirnos. ¿En qué te puedo ayudar?"

    # Strip <thinking> and <analisis> tags (hidden chain-of-thought)
    response_text = re.sub(r'<thinking>.*?</thinking>\s*', '', response_text, flags=re.DOTALL).strip()
    response_text = re.sub(r'<analisis>.*?</analisis>\s*', '', response_text, flags=re.DOTALL).strip()
    response_text = _enforce_verified_technical_guidance(
        response_text,
        effective_advisory_flow=effective_advisory_flow,
        recommendation_ready=recommendation_ready,
        best_effort_ready=best_effort_ready,
        conversation_context=conversation_context,
        technical_case=technical_case,
        m=m,
    )
    if not response_text:
        response_text = "Gracias por escribirnos. ¿En qué te puedo ayudar?"

    # ── G1: Sanitizer final (defensa #N) — bloquea fugas de JSON / tags
    # internas / payloads de tool_call ANTES de enviar al usuario.
    try:
        from agent_response_sanitizer import sanitize_agent_response
    except ImportError:
        from backend.agent_response_sanitizer import sanitize_agent_response  # type: ignore
    response_text = sanitize_agent_response(
        response_text,
        conversation_id=(context or {}).get("conversation_id") if isinstance(context, dict) else None,
    )

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
                "technical_advisory_case": conversation_context.get("technical_advisory_case"),
                "technical_cases": conversation_context.get("technical_cases"),
                "active_technical_case_id": conversation_context.get("active_technical_case_id"),
                "technical_case_sequence": conversation_context.get("technical_case_sequence"),
                "pending_case_resolution_candidates": conversation_context.get("pending_case_resolution_candidates"),
                # Process gate: after first advisory turn, mark diagnostic exchange done
                # so the NEXT turn allows tools and RAG preload.
                "_advisory_diagnostic_turn_done": True if _first_advisory_turn else conversation_context.get("_advisory_diagnostic_turn_done"),
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
                tools=_get_active_agent_tools(), tool_choice="auto", temperature=0.3,
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
                    tools=_get_active_agent_tools(), tool_choice="auto", temperature=0.3,
                )
                assistant_message = resp.choices[0].message
                retries -= 1
            logger.info("V3 GUARDIA QUÍMICA completed: %dms", int((time.time() - t) * 1000))
            break  # Fix first incompatibility only

    return assistant_message


def _guardia_bicomponente(assistant_message, messages, tool_calls_made, context, conversation_context, m):
    """Detecta bicomponentes sin catalizador y fuerza corrección."""
    tools_used = {tc.get("name") for tc in (tool_calls_made or [])}
    knowledge_or_inventory_tools = {
        "consultar_conocimiento_tecnico",
        "consultar_inventario",
        "consultar_inventario_lote",
    }
    bi_tools = {
        "consultar_indicadores_internos",
        "consultar_bi_universal",
        "consultar_ventas_internas",
        "enviar_reporte_interno_correo",
    }

    # Never let product-completeness guards contaminate BI/indicator/report turns.
    # For bicomponent enforcement, stay strictly inside product/inventory/technical flows.
    if tools_used & bi_tools and not (tools_used & knowledge_or_inventory_tools):
        return assistant_message
    if not (tools_used & knowledge_or_inventory_tools):
        return assistant_message

    response_text = (assistant_message.content or "").lower()

    # Also scan tool results — if inventory returned a bicomponent product,
    # the LLM might have renamed it but the guard still needs to catch it.
    tool_results_text = " ".join(
        (tc.get("result") or "").lower() for tc in tool_calls_made
        if tc.get("name") in ("consultar_inventario", "consultar_inventario_lote")
    )
    combined_text = response_text + " " + tool_results_text

    for prod_signals, cat_signals, prod_name, cat_name in _BICOMP_CHECKS:
        has_product = any(s in combined_text for s in prod_signals)
        has_catalyst = any(s in combined_text for s in cat_signals)
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
                tools=_get_active_agent_tools(), tool_choice="auto", temperature=0.3,
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
                    tools=_get_active_agent_tools(), tool_choice="auto", temperature=0.3,
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
        tools=_get_active_agent_tools(), tool_choice="none", temperature=0.2,
    )
    assistant_message = resp.choices[0].message
    logger.info("V3 GUARDIA CONSISTENCIA TÉCNICA completed: %dms", int((time.time() - t) * 1000))
    return assistant_message


def _guardia_formato_tecnico(assistant_message, messages, tool_calls_made, conversation_context, m):
    technical_payload = _extract_latest_technical_payload(tool_calls_made)
    if not technical_payload:
        return assistant_message

    response_text = assistant_message.content or ""
    if not response_text.strip() or _technical_response_has_required_sections(response_text):
        return assistant_message

    project_profile = dict((conversation_context or {}).get("technical_advisory_case") or {}).get("project_profile") or {}
    missing_fields = ", ".join(
        item.get("description") or item.get("field")
        for item in (project_profile.get("missing_fields") or [])
        if isinstance(item, dict)
    )

    messages.append(assistant_message)
    messages.append({
        "role": "system",
        "content": (
            "CORRECCIÓN DE FORMATO TÉCNICO OBLIGATORIA: reescribe la respuesta FINAL usando exactamente estos encabezados Markdown, en este orden: "
            + ", ".join(_TECHNICAL_RESPONSE_SECTIONS)
            + ". Si falta evidencia para cantidades o mezcla, dilo explícitamente dentro de '**Cantidades y Mezcla:**'. "
            + (f"Si el perfil del proyecto aún está incompleto, menciona los faltantes ({missing_fields}) dentro de '**Diagnóstico:**' y no cierres con recomendación final. " if missing_fields else "")
            + "No llames más herramientas y no cambies los productos respaldados."
        ),
    })
    resp = m.get_openai_client().chat.completions.create(
        model=m.get_openai_model(),
        messages=messages,
        tools=_get_active_agent_tools(),
        tool_choice="none",
        temperature=0.2,
    )
    return resp.choices[0].message


def _guardia_iva(assistant_message, messages, m):
    """Si la cotización no tiene desglose de IVA, fuerza corrección."""
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
                tools=_get_active_agent_tools(), tool_choice="none", temperature=0.3,
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


# ── Patterns that signal the LLM is recommending products ──────────────
_RECOMMENDATION_SIGNALS_RE = re.compile(
    r"(?:te\s+recomiendo|recomiendo\s+(?:el|la|usar)|"
    r"el\s+sistema\s+(?:correcto|ideal|recomendado)|"
    r"(?:preparaci[oó]n|sellador|imprimante|acabado)\s*:\s*\*{0,2}\s*[A-Z]|"
    r"(?:🔹|•)\s*(?:preparaci[oó]n|sellador|imprimante|acabado|base)\s*:)",
    re.IGNORECASE,
)

# ── COMPREHENSIVE PRODUCT BRAND DETECTION ────────────────────────────
# Matches ALL known product/brand names in the Ferreinox portfolio.
# NOT a blocklist — a detection list.  Any mention is validated against
# tool results + system context.  If NOT found → hallucination.
_ALL_PRODUCT_BRANDS_RE = re.compile(
    r"\b(?:"
    # Pintuco arquitectónico
    r"viniltex|koraza|intervinil|acriltex|toptex|acryl[ií]tex|"
    # Pintuco especialidad / impermeabilización
    r"aquablock|sellomax|sellamur|siliconite|construcleaner|"
    r"pintuco\s+fill|pintutecho|pintutrafico|"
    r"pintura\s+(?:para\s+)?canchas|"
    # Pintuco metal / anticorrosivos
    r"pintulux|pintoxido|pintóxido|corrotec|"
    r"altas\s+temperaturas|wash\s+primer|"
    # Pintuco madera
    r"barnex|wood\s+stain|"
    # International / industrial
    r"pintucoat|intergard|interseal|interthane|intertherm|interfine|"
    r"primer\s+50\s*rs|"
    # Variantes / apellidos de producto
    r"baños\s+y\s+cocinas|ultralavable|doble\s+vida|"
    r"estuco\s+(?:profesional|prof(?:\s+ext)?|multiuso|acrílico)|"
    # Otras marcas
    r"pinturama|epoxipoliamida"
    r")\b",
    re.IGNORECASE,
)


def _guardia_universal_producto(
    assistant_message, messages, tool_calls_made, context, conversation_context, m
):
    """GUARDIA UNIVERSAL DE PRODUCTO — reemplaza todas las guardias por-producto.

    Principio: CADA nombre de producto/marca en la respuesta del LLM DEBE
    existir en los resultados de herramientas o en el contexto del sistema.
    Si no está en ninguna fuente → es alucinación y se bloquea.

    Cubre todos los casos:
    - LLM no llamó herramientas → fuerza re-generación con tool_choice="required"
    - LLM llamó herramientas pero inventó productos → los elimina de la respuesta
    - Diagnóstico bloqueado → elimina todo nombre de producto
    Sin reglas por producto.  Sin listas de productos prohibidos.
    UN SOLO principio: si no vino de una herramienta, no existe.
    """
    response_text = assistant_message.content or ""
    if not response_text.strip():
        return assistant_message

    # Skip for internal employees (direct orders)
    if (conversation_context or {}).get("internal_auth"):
        return assistant_message

    # ── 1. Extract ALL product brand mentions from the response ──────────
    product_mentions = set()
    for match in _ALL_PRODUCT_BRANDS_RE.finditer(response_text):
        product_mentions.add(match.group(0).lower().strip())

    if not product_mentions:
        return assistant_message  # No product names → nothing to validate

    def _msg_role(msg):
        if isinstance(msg, dict):
            return msg.get("role")
        return getattr(msg, "role", None)

    def _msg_content(msg):
        if isinstance(msg, dict):
            return msg.get("content") or ""
        return getattr(msg, "content", "") or ""

    # ── 2. Collect ALL allowed source text ───────────────────────────────
    source_texts = []
    # Tool results
    for tc in tool_calls_made:
        source_texts.append((tc.get("result") or "").lower())
    # System messages (turn context, corrections, injected directives)
    for msg in messages:
        if _msg_role(msg) == "system":
            content = _msg_content(msg)
            if isinstance(content, str):
                source_texts.append(content.lower())
    all_source_text = " ".join(source_texts)

    # ── 3. Cross-reference: is each product backed by a source? ──────────
    unsupported = []
    for product in product_mentions:
        normalized = re.sub(r'\s+', ' ', product).strip()
        if normalized in all_source_text:
            continue
        # Check if it's a negated mention in the response ("no uses X", "nunca X")
        pos = response_text.lower().find(normalized)
        if pos >= 0:
            prefix_start = max(0, pos - 50)
            prefix = response_text[prefix_start:pos].lower()
            if any(neg in prefix for neg in (
                "no ", "nunca ", "prohibido ", "no recomend", "no apliqu",
                "no use", "evitar ", "no es ", "no va ", "no sirve",
            )):
                continue  # Negated mention is fine (e.g. "NO uses Koraza aquí")
        unsupported.append(product)

    if not unsupported:
        return assistant_message  # All products validated ✓

    logger.warning(
        "GUARDIA UNIVERSAL: productos sin respaldo: %s | conv=%s | tools_used=%s",
        unsupported,
        context.get("conversation_id"),
        [tc["name"] for tc in tool_calls_made],
    )

    # ── 4. Check diagnostic state ────────────────────────────────────────
    try:
        from agent_context import is_diagnostic_incomplete, extract_diagnostic_data, classify_intent
    except ImportError:
        from backend.agent_context import is_diagnostic_incomplete, extract_diagnostic_data, classify_intent

    _user_msg = ""
    for msg in reversed(messages):
        if _msg_role(msg) == "user":
            content = _msg_content(msg)
            _user_msg = content if isinstance(content, str) else ""
            break

    _diag = extract_diagnostic_data(_user_msg, [])
    _intent = classify_intent(_user_msg, conversation_context, [], {})
    _blocked = is_diagnostic_incomplete(_intent, _diag)

    # ── 5A. Diagnostic BLOCKED → strip ALL product names (no tools allowed) ──
    if _blocked:
        logger.warning("GUARDIA UNIVERSAL: diagnostic blocked + products → stripping all product names")
        cleaned = response_text
        for match in _ALL_PRODUCT_BRANDS_RE.finditer(cleaned):
            cleaned = cleaned.replace(match.group(0), "[producto]", 1)
        cleaned = _RECOMMENDATION_SIGNALS_RE.sub("", cleaned)
        from types import SimpleNamespace
        return SimpleNamespace(content=cleaned.strip(), tool_calls=None)

    # ── 5B. NO knowledge tools called → force re-gen with tools ──────────
    tools_used = {tc["name"] for tc in tool_calls_made}
    _knowledge_tools = {"consultar_conocimiento_tecnico", "consultar_inventario", "consultar_inventario_lote"}
    if not (tools_used & _knowledge_tools):
        logger.warning("GUARDIA UNIVERSAL: products without ANY knowledge tool → forcing re-gen")
        messages_copy = list(messages)
        messages_copy.append({
            "role": "system",
            "content": (
                "CORRECCIÓN OBLIGATORIA: Tu respuesta mencionó productos específicos "
                "sin haber consultado NINGUNA herramienta. Eso viola la REGLA ABSOLUTA. "
                "Llama consultar_conocimiento_tecnico AHORA con la superficie y condición "
                "del cliente. Después, responde SOLO con los productos que devuelva."
            ),
        })

        _GUARD_TOOLS = _get_active_agent_tools()

        try:
            t_fix = time.time()
            resp_fix = m.get_openai_client().chat.completions.create(
                model=m.get_openai_model(),
                messages=messages_copy,
                tools=_GUARD_TOOLS,
                tool_choice="required",
                temperature=0.2,
            )
            fixed_message = resp_fix.choices[0].message
            logger.info("GUARDIA UNIVERSAL re-gen: %dms tools=%s",
                        int((time.time() - t_fix) * 1000), bool(fixed_message.tool_calls))

            if fixed_message.tool_calls:
                messages_copy.append(fixed_message)
                for tc in fixed_message.tool_calls:
                    fn_name = tc.function.name
                    if fn_name == "consultar_conocimiento_tecnico":
                        args = json.loads(tc.function.arguments or "{}")
                        args = _sanitize_technical_lookup_args(args, None, [], m)
                        result = m._handle_tool_consultar_conocimiento_tecnico(args, context, conversation_context)
                    else:
                        _, _, result = m._execute_agent_tool(tc, context, conversation_context)
                    tool_calls_made.append({"name": fn_name, "args": json.loads(tc.function.arguments or "{}"), "result": result})
                    messages_copy.append({"role": "tool", "tool_call_id": tc.id, "content": result})

                resp_final = m.get_openai_client().chat.completions.create(
                    model=m.get_openai_model(),
                    messages=messages_copy,
                    tools=_GUARD_TOOLS,
                    tool_choice="none",
                    temperature=0.2,
                )
                return resp_final.choices[0].message
            return fixed_message
        except Exception as exc:
            logger.error("GUARDIA UNIVERSAL re-gen error: %s", exc)
            # Fallback: strip unsupported products
            cleaned = response_text
            for p in unsupported:
                cleaned = re.sub(r'\b' + re.escape(p) + r'\b',
                                 "[producto — verificar con equipo]", cleaned, flags=re.IGNORECASE)
            from types import SimpleNamespace
            return SimpleNamespace(content=cleaned, tool_calls=None)

    # ── 5C. Tools WERE called but some products aren't in results ────────
    # Strip only the unsupported products — the rest are validated.
    logger.warning("GUARDIA UNIVERSAL: stripping %d unsupported products: %s", len(unsupported), unsupported)
    cleaned = response_text
    for p in unsupported:
        cleaned = re.sub(
            r'\b' + re.escape(p) + r'\b',
            "[verificar con equipo técnico]",
            cleaned, flags=re.IGNORECASE,
        )

    # One quick re-gen to make the response natural after stripping
    messages_copy = list(messages)
    messages_copy.append({"role": "assistant", "content": cleaned})
    messages_copy.append({
        "role": "system",
        "content": (
            "Algunos productos fueron reemplazados por [verificar con equipo técnico] "
            "porque NO estaban en los resultados de las herramientas que llamaste. "
            "Reescribe tu respuesta de forma natural. Mantén SOLO los productos "
            "que SÍ vinieron de las herramientas. Para los demás, dile al cliente "
            "que lo verificarás con el equipo técnico. No inventes reemplazos."
        ),
    })

    _GUARD_TOOLS = _get_active_agent_tools()

    try:
        t_clean = time.time()
        resp_clean = m.get_openai_client().chat.completions.create(
            model=m.get_openai_model(),
            messages=messages_copy,
            tools=_GUARD_TOOLS,
            tool_choice="none",
            temperature=0.2,
        )
        logger.info("GUARDIA UNIVERSAL cleanup: %dms", int((time.time() - t_clean) * 1000))
        return resp_clean.choices[0].message
    except Exception as exc:
        logger.error("GUARDIA UNIVERSAL cleanup error: %s", exc)
        from types import SimpleNamespace
        return SimpleNamespace(content=cleaned, tool_calls=None)
