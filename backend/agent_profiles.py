import os


def get_agent_profile_name() -> str:
    raw_profile = (os.getenv("AGENT_PROFILE") or "legacy").strip().lower()
    if raw_profile in {"internal", "interno", "operativo", "internal_operativo"}:
        return "internal"
    if raw_profile in {"customer", "cliente", "clientes", "customer_public", "publico"}:
        return "customer"
    if raw_profile in {"ferreamigo", "ferreamigo_b2b", "b2b", "d2"}:
        return "ferreamigo"
    return "legacy"


def _filter_tools_by_name(tool_definitions: list[dict], allowed_names: set[str]) -> list[dict]:
    filtered_tools = []
    for tool in tool_definitions:
        tool_name = ((tool or {}).get("function") or {}).get("name")
        if tool_name in allowed_names:
            filtered_tools.append(tool)
    return filtered_tools


def get_agent_runtime_config() -> dict:
    try:
        from agent_prompt_v3 import AGENT_SYSTEM_PROMPT_V3, AGENT_TOOLS_V3
        from agent_prompt_internal import AGENT_SYSTEM_PROMPT_INTERNAL, AGENT_INTERNAL_ALLOWED_TOOL_NAMES
        from agent_prompt_customer import AGENT_SYSTEM_PROMPT_CUSTOMER, AGENT_CUSTOMER_ALLOWED_TOOL_NAMES
        from agent_prompt_ferreamigo import (
            FERREAMIGO_SYSTEM_PROMPT,
            FERREAMIGO_ALLOWED_TOOL_NAMES,
        )
    except ImportError:
        from backend.agent_prompt_v3 import AGENT_SYSTEM_PROMPT_V3, AGENT_TOOLS_V3
        from backend.agent_prompt_internal import AGENT_SYSTEM_PROMPT_INTERNAL, AGENT_INTERNAL_ALLOWED_TOOL_NAMES
        from backend.agent_prompt_customer import AGENT_SYSTEM_PROMPT_CUSTOMER, AGENT_CUSTOMER_ALLOWED_TOOL_NAMES
        from backend.agent_prompt_ferreamigo import (
            FERREAMIGO_SYSTEM_PROMPT,
            FERREAMIGO_ALLOWED_TOOL_NAMES,
        )

    profile = get_agent_profile_name()
    if profile == "internal":
        return {
            "profile": "internal",
            "system_prompt": AGENT_SYSTEM_PROMPT_INTERNAL,
            "tools": _filter_tools_by_name(AGENT_TOOLS_V3, AGENT_INTERNAL_ALLOWED_TOOL_NAMES),
            "enable_order_pipeline": True,
            "enable_quote_pipeline": True,
            "enable_iva_guard": False,
            "force_first_advisory_depth_turn": False,
        }

    if profile == "customer":
        return {
            "profile": "customer",
            "system_prompt": AGENT_SYSTEM_PROMPT_CUSTOMER,
            "tools": _filter_tools_by_name(AGENT_TOOLS_V3, AGENT_CUSTOMER_ALLOWED_TOOL_NAMES),
            "enable_order_pipeline": False,
            "enable_quote_pipeline": False,
            "enable_iva_guard": False,
            "force_first_advisory_depth_turn": True,
        }

    if profile == "ferreamigo":
        # Phase D2 — state machine prompt (TRIAGE → DIAGNOSIS_GATHERING →
        # TECHNICAL_RECOMMENDATION → ORDER_PREP). Tool surface idéntica al
        # canal customer pero con routing determinista forzado por prompt.
        return {
            "profile": "ferreamigo",
            "system_prompt": FERREAMIGO_SYSTEM_PROMPT,
            "tools": _filter_tools_by_name(AGENT_TOOLS_V3, FERREAMIGO_ALLOWED_TOOL_NAMES),
            "enable_order_pipeline": False,
            "enable_quote_pipeline": False,
            "enable_iva_guard": False,
            "force_first_advisory_depth_turn": True,
        }

    # Legacy = technical advisory (no commercial tools)
    _LEGACY_ALLOWED_TOOL_NAMES = {
        "consultar_conocimiento_tecnico",
        "buscar_documento_tecnico",
        "verificar_identidad",
        "consultar_cartera",
        "consultar_compras",
        "radicar_reclamo",
        "registrar_conocimiento_experto",
    }
    return {
        "profile": "legacy",
        "system_prompt": AGENT_SYSTEM_PROMPT_V3,
        "tools": _filter_tools_by_name(AGENT_TOOLS_V3, _LEGACY_ALLOWED_TOOL_NAMES),
        "enable_order_pipeline": False,
        "enable_quote_pipeline": False,
        "enable_iva_guard": False,
        "force_first_advisory_depth_turn": True,
    }