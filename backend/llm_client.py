"""Cliente LLM (DeepSeek vía SDK OpenAI-compatible).

Módulo extraído de `backend/main.py` durante la Fase C2 (modularización).
Centraliza la configuración del backend LLM y el caché del prompt NLU.

IMPORTANTE: El SDK `openai` se usa intencionalmente como transporte para
DeepSeek (API OpenAI-compatible). El fallback a `gpt-4o-mini` permanece
como red de seguridad y emite WARNING explícito.
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Optional

try:
    import tomllib
except ModuleNotFoundError:  # Python < 3.11
    import tomli as tomllib  # type: ignore[no-redef]

from openai import OpenAI


logger = logging.getLogger("ferreinox_agent")


# ── Paths ─────────────────────────────────────────────────────────────────
_REPO_ROOT = Path(__file__).resolve().parent.parent
_SECRETS_PATH = _REPO_ROOT / ".streamlit" / "secrets.toml"
_ARTIFACTS_PATH = _REPO_ROOT / "artifacts"
PRODUCT_NLU_PROMPT_PATH = _ARTIFACTS_PATH / "SYSTEM_PROMPT_NLU_EXTRACCION_PRODUCTO.md"
PRODUCT_NLU_PROMPT_FALLBACK = (
    "Eres un extractor NLU para pedidos ferreteros. Devuelve solo JSON válido con las claves "
    "cantidad_inferida, presentacion_canonica_inferida, producto_base, color y acabado. "
    "Si no sabes un valor, devuelve null. Interpreta 1/5 como cuñete, 1/1 como galon y 1/4 como cuarto. "
    "Conserva colores compuestos como verde bronce y no inventes acabados."
)
PRODUCT_NLU_PROMPT_CACHE: Optional[str] = None


# ── Helpers genéricos de configuración ────────────────────────────────────
def _read_streamlit_secret_value(*keys: str) -> Optional[str]:
    if not _SECRETS_PATH.exists() or not keys:
        return None
    try:
        raw_text = _SECRETS_PATH.read_text(encoding="utf-8")
    except Exception:
        return None

    last_key = re.escape(keys[-1])
    quoted_match = re.search(rf"(?mi)^\s*{last_key}\s*=\s*\"([^\"]+)\"\s*$", raw_text)
    if quoted_match:
        return quoted_match.group(1).strip()

    bare_match = re.search(rf"(?mi)^\s*{last_key}\s*=\s*([^#\r\n]+)", raw_text)
    if bare_match:
        return bare_match.group(1).strip().strip('"').strip("'")

    try:
        parsed = tomllib.loads(raw_text)
    except Exception:
        return None

    current = parsed
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
        if current is None:
            return None
    if isinstance(current, str):
        return current.strip()
    return None


def _first_configured_value(*values):
    for value in values:
        if value is None:
            continue
        stripped = value.strip() if isinstance(value, str) else value
        if stripped:
            return stripped
    return None


# ── Resolución de credenciales y endpoint ─────────────────────────────────
def get_openai_api_key():
    return _first_configured_value(
        os.getenv("OPENAI_API_KEY"),
        os.getenv("DEEPSEEK_API_KEY"),
        _read_streamlit_secret_value("openai", "api_key"),
        _read_streamlit_secret_value("deepseek", "api_key"),
    )


def get_openai_base_url():
    configured_base_url = _first_configured_value(
        os.getenv("OPENAI_BASE_URL"),
        os.getenv("LLM_BASE_URL"),
        os.getenv("DEEPSEEK_BASE_URL"),
    )
    if configured_base_url:
        return configured_base_url
    if os.getenv("DEEPSEEK_API_KEY") and not os.getenv("OPENAI_API_KEY"):
        return "https://api.deepseek.com"
    return None


def is_deepseek_backend():
    base_url = get_openai_base_url()
    if base_url and "deepseek" in base_url.lower():
        return True
    return bool(os.getenv("DEEPSEEK_API_KEY") and not os.getenv("OPENAI_API_KEY"))


def get_openai_model():
    if is_deepseek_backend():
        configured_model = _first_configured_value(
            os.getenv("DEEPSEEK_MODEL"),
            os.getenv("LLM_MODEL"),
            os.getenv("OPENAI_MODEL"),
        )
        return configured_model or "deepseek-chat"

    configured_model = _first_configured_value(
        os.getenv("OPENAI_MODEL"),
        os.getenv("LLM_MODEL"),
    )
    if configured_model:
        return configured_model
    return "gpt-4o-mini"


def get_openai_client():
    api_key = get_openai_api_key()
    if not api_key:
        raise RuntimeError("No se encontró OPENAI_API_KEY ni DEEPSEEK_API_KEY para generar respuestas del agente.")
    client_kwargs = {"api_key": api_key}
    base_url = get_openai_base_url()
    if base_url:
        client_kwargs["base_url"] = base_url
    else:
        # Fallback path: no DEEPSEEK_API_KEY ni OPENAI_BASE_URL configurados.
        # Cae al endpoint OpenAI por defecto. Producción debe usar DeepSeek.
        logger.warning(
            "LLM client fallback: usando endpoint OpenAI por defecto (modelo=%s). "
            "Configura DEEPSEEK_API_KEY o OPENAI_BASE_URL para evitar este fallback.",
            get_openai_model(),
        )
    return OpenAI(**client_kwargs)


def get_product_nlu_system_prompt():
    global PRODUCT_NLU_PROMPT_CACHE
    if PRODUCT_NLU_PROMPT_CACHE is not None:
        return PRODUCT_NLU_PROMPT_CACHE

    try:
        PRODUCT_NLU_PROMPT_CACHE = PRODUCT_NLU_PROMPT_PATH.read_text(encoding="utf-8").strip()
    except Exception:
        PRODUCT_NLU_PROMPT_CACHE = PRODUCT_NLU_PROMPT_FALLBACK

    if not PRODUCT_NLU_PROMPT_CACHE:
        PRODUCT_NLU_PROMPT_CACHE = PRODUCT_NLU_PROMPT_FALLBACK
    return PRODUCT_NLU_PROMPT_CACHE


__all__ = [
    "PRODUCT_NLU_PROMPT_PATH",
    "PRODUCT_NLU_PROMPT_FALLBACK",
    "PRODUCT_NLU_PROMPT_CACHE",
    "_first_configured_value",
    "_read_streamlit_secret_value",
    "get_openai_api_key",
    "get_openai_base_url",
    "is_deepseek_backend",
    "get_openai_model",
    "get_openai_client",
    "get_product_nlu_system_prompt",
    # Phase E1 — dynamic tool binding
    "build_llm_runtime_kwargs",
    "RBACToolViolationError",
]


# ─────────────────────────────────────────────────────────────────────────
# Phase E1 — Dynamic tool binding entrypoint.
#
# El llamador (típicamente el dispatcher de mensajes en main.py /
# customer_handlers.py) construye el SessionContext UNA VEZ y se lo
# pasa a esta función. La función devuelve el dict de kwargs que se
# pueden inyectar directamente a `client.chat.completions.create(...)`:
#
#     ctx = classify_session_from_phone(phone, ...)
#     kw = build_llm_runtime_kwargs(ctx, base_messages=...)
#     resp = client.chat.completions.create(model=..., **kw)
#
# Doble defensa: además del filtro por whitelist al armar `tools`, el
# dispatcher debe re-validar cada `tool_call.name` contra
# `is_tool_allowed_for_session` ANTES de invocar el handler real.
# ─────────────────────────────────────────────────────────────────────────


class RBACToolViolationError(PermissionError):
    """Se eleva si el LLM intenta llamar una tool fuera de su whitelist."""


def build_llm_runtime_kwargs(
    session,  # SessionContext
    *,
    base_messages: list[dict],
    extra_tool_definitions: list[dict] | None = None,
    tool_choice: str = "auto",
) -> dict:
    """Arma el payload listo para `client.chat.completions.create`.

    Inyecta:
      * ``messages``: messages base con el system prompt FERREAMIGO
        (con addendum interno si la sesión es INTERNAL).
      * ``tools``: array filtrado por whitelist RBAC.
      * ``tool_choice``: "auto" por defecto; permite forzar una tool.

    El array de tools se construye dinámicamente — el LLM jamás ve la
    definición de una tool para la que no tiene permiso.
    """
    try:
        from agent_prompt_ferreamigo import build_ferreamigo_system_prompt
        from rbac import build_tools_for_session
    except ImportError:
        from backend.agent_prompt_ferreamigo import build_ferreamigo_system_prompt
        from backend.rbac import build_tools_for_session

    system_prompt = build_ferreamigo_system_prompt(internal=session.is_internal)

    # Si el caller ya inyectó un system message, reemplazarlo; si no, anteponerlo.
    msgs = list(base_messages or [])
    if msgs and msgs[0].get("role") == "system":
        msgs[0] = {"role": "system", "content": system_prompt}
    else:
        msgs.insert(0, {"role": "system", "content": system_prompt})

    tools = build_tools_for_session(
        session,
        extra_tool_definitions=extra_tool_definitions,
    )

    kwargs: dict = {"messages": msgs}
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = tool_choice
    return kwargs
