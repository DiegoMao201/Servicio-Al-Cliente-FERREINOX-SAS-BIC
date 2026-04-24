"""G1 — Sanitizer del output del agente.

Funciones puras que se aplican a la respuesta final del LLM ANTES de enviar
el mensaje a WhatsApp. Su única misión: garantizar que el usuario nunca vea
artefactos técnicos (bloques JSON, tool_call escapados, payloads internos)
incluso si el modelo se sale del contrato.

Reglas inquebrantables:
  1. Si la respuesta es 100% un objeto JSON, se reemplaza por un mensaje
     genérico de espera y se loguea CRITICAL (señal de fuga estructural).
  2. Bloques ```json ... ``` y ``` ... ``` se eliminan.
  3. Etiquetas internas <analisis>...</analisis> se eliminan.
  4. Tags <tool_call>, <function_call>, <tool>, <invoke> se eliminan.
  5. Si la respuesta queda vacía tras sanitizar, se sustituye por un
     mensaje seguro pidiendo reformular.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Optional

logger = logging.getLogger("ferreinox_agent.sanitizer")


_FENCED_CODE_RE = re.compile(r"```(?:json|JSON|tool_use|tool|python)?\s*[\s\S]*?```", re.MULTILINE)
_ANALISIS_RE = re.compile(r"<\s*analisis\s*>[\s\S]*?<\s*/\s*analisis\s*>", re.IGNORECASE)
_TOOL_TAG_RE = re.compile(
    r"<\s*(tool_call|tool_use|function_call|invoke|tool|function)[\s\S]*?<\s*/\s*\1\s*>",
    re.IGNORECASE,
)
_SELF_CLOSING_TOOL_TAG_RE = re.compile(
    r"<\s*(tool_call|tool_use|function_call|invoke)[^>]*/\s*>",
    re.IGNORECASE,
)


SAFE_FALLBACK_AFTER_LEAK = (
    "Estoy preparando la respuesta. Dame un momento y te confirmo en seguida."
)
SAFE_FALLBACK_EMPTY = (
    "¿Podrías reformular tu pregunta? Quiero asegurarme de darte la respuesta correcta."
)


def _looks_like_pure_json(text: str) -> bool:
    """True si la respuesta es básicamente un objeto/array JSON puro."""
    stripped = text.strip()
    if not stripped:
        return False
    if not (stripped.startswith("{") or stripped.startswith("[")):
        return False
    # Heurística: intentar parsear los primeros 4 KB.
    sample = stripped[:4096]
    try:
        json.loads(sample)
        return True
    except Exception:
        # Si arranca con { o [ y > 80% del texto es JSON-like, igual lo
        # tratamos como pure JSON (modelo emitió payload incompleto).
        json_chars = sum(1 for c in sample if c in '{}[]":,')
        return (json_chars / max(len(sample), 1)) > 0.18 and stripped.endswith(("}", "]"))


def sanitize_agent_response(
    text: Optional[str],
    *,
    conversation_id: Optional[int] = None,
) -> str:
    """Elimina artefactos técnicos del texto antes de enviarlo al usuario.

    Devuelve siempre un string no vacío y seguro para WhatsApp.
    """
    if text is None:
        return SAFE_FALLBACK_EMPTY

    original = text
    cleaned = text

    # 1) Si toda la respuesta es JSON puro → fuga estructural grave.
    if _looks_like_pure_json(cleaned):
        logger.critical(
            "AGENT JSON LEAK detected (conv=%s) — substituting safe fallback. payload_preview=%r",
            conversation_id,
            cleaned[:200],
        )
        return SAFE_FALLBACK_AFTER_LEAK

    # 2) Eliminar bloques fenced de código (```json ... ```, etc.).
    cleaned = _FENCED_CODE_RE.sub("", cleaned)

    # 3) Eliminar bloques internos <analisis>...</analisis>.
    cleaned = _ANALISIS_RE.sub("", cleaned)

    # 4) Eliminar tags estilo <tool_call>...</tool_call> y self-closing.
    cleaned = _TOOL_TAG_RE.sub("", cleaned)
    cleaned = _SELF_CLOSING_TOOL_TAG_RE.sub("", cleaned)

    # 5) Limpiar líneas duplicadas vacías.
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()

    if not cleaned:
        logger.warning(
            "AGENT response empty after sanitize (conv=%s). original_preview=%r",
            conversation_id,
            original[:200],
        )
        return SAFE_FALLBACK_EMPTY

    return cleaned


# ──────────────────────────────────────────────────────────────────────────
# G1 — Mensaje de fallback de degradación (LLM caído / timeout / API error)
# ──────────────────────────────────────────────────────────────────────────

GRACEFUL_DEGRADATION_MESSAGE = (
    "En este momento estoy actualizando mi base de datos técnica. "
    "Un asesor se comunicará contigo en breve. Gracias por tu paciencia."
)


__all__ = [
    "sanitize_agent_response",
    "SAFE_FALLBACK_AFTER_LEAK",
    "SAFE_FALLBACK_EMPTY",
    "GRACEFUL_DEGRADATION_MESSAGE",
]
