import os


def get_agent_profile_name() -> str:
    raw_profile = (os.getenv("AGENT_PROFILE") or "legacy").strip().lower()
    if raw_profile in {"internal", "interno", "operativo", "internal_operativo"}:
        return "internal"
    if raw_profile in {"customer", "cliente", "clientes", "customer_public", "publico"}:
        return "customer"
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
    except ImportError:
        from backend.agent_prompt_v3 import AGENT_SYSTEM_PROMPT_V3, AGENT_TOOLS_V3
        from backend.agent_prompt_internal import AGENT_SYSTEM_PROMPT_INTERNAL, AGENT_INTERNAL_ALLOWED_TOOL_NAMES
        from backend.agent_prompt_customer import AGENT_SYSTEM_PROMPT_CUSTOMER, AGENT_CUSTOMER_ALLOWED_TOOL_NAMES

    profile = get_agent_profile_name()
    if profile == "internal":
        return {
            "profile": "internal",
            "system_prompt": AGENT_SYSTEM_PROMPT_INTERNAL,
            "tools": _filter_tools_by_name(AGENT_TOOLS_V3, AGENT_INTERNAL_ALLOWED_TOOL_NAMES),
            "enable_order_pipeline": False,
            "enable_quote_pipeline": False,
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

    return {
        "profile": "legacy",
        "system_prompt": AGENT_SYSTEM_PROMPT_V3,
        "tools": AGENT_TOOLS_V3,
        "enable_order_pipeline": True,
        "enable_quote_pipeline": True,
        "enable_iva_guard": True,
        "force_first_advisory_depth_turn": True,
    }