"""F1 — Telemetría / Caja Negra del agente FerreAmigo.

Cada turno del agente genera un registro inmutable en `agent_audit_logs`
con: session_id, role, tokens, tools invocadas, safety score del RAG,
duración total, fallback, errores. Permite reconstruir post-mortem las
decisiones de la IA frente a un cliente.

Diseño:

  * Esquema Pydantic estricto (`extra="forbid"`).
  * Persistencia perezosa: si la tabla no existe (despliegue nuevo) o la
    DB no responde, se loguea WARNING y la respuesta al usuario sigue
    su curso. La auditoría NUNCA bloquea la conversación.
  * `record_agent_turn(...)` es síncrono pero rápido (un solo INSERT);
    se invoca tras enviar la respuesta a WhatsApp para no añadir latencia
    al usuario.
  * El DDL idempotente (`ensure_audit_table()`) se ejecuta una sola vez
    por proceso (flag `_ddl_applied`).
"""

from __future__ import annotations

import json
import logging
import threading
import time
from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger("ferreinox_agent.telemetry")


# ──────────────────────────────────────────────────────────────────────────
# DDL — ejecutado una sola vez por proceso
# ──────────────────────────────────────────────────────────────────────────

AGENT_AUDIT_LOGS_DDL = """
CREATE TABLE IF NOT EXISTS public.agent_audit_logs (
    id              BIGSERIAL PRIMARY KEY,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    session_id      TEXT,
    conversation_id BIGINT,
    role            TEXT NOT NULL CHECK (role IN ('internal', 'external', 'unknown')),
    phone_e164      TEXT,
    user_message    TEXT,
    response_text   TEXT,
    intent          TEXT,
    tools_invoked   JSONB NOT NULL DEFAULT '[]'::jsonb,
    tokens_prompt   INTEGER,
    tokens_completion INTEGER,
    tokens_total    INTEGER,
    safety_score    DOUBLE PRECISION,
    confidence_level TEXT,
    duration_ms     INTEGER,
    iterations      INTEGER,
    fallback_used   BOOLEAN NOT NULL DEFAULT FALSE,
    error_class     TEXT,
    error_message   TEXT,
    extra           JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_agent_audit_logs_created_at
    ON public.agent_audit_logs (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_agent_audit_logs_conversation
    ON public.agent_audit_logs (conversation_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_agent_audit_logs_phone
    ON public.agent_audit_logs (phone_e164, created_at DESC);
"""


# ──────────────────────────────────────────────────────────────────────────
# Schema Pydantic
# ──────────────────────────────────────────────────────────────────────────


class AgentAuditEntry(BaseModel):
    """Registro inmutable de un turno del agente."""

    model_config = ConfigDict(extra="forbid")

    session_id: Optional[str] = None
    conversation_id: Optional[int] = None
    role: str = Field(default="unknown")  # 'internal' | 'external' | 'unknown'
    phone_e164: Optional[str] = None
    user_message: Optional[str] = None
    response_text: Optional[str] = None
    intent: Optional[str] = None
    tools_invoked: list[dict[str, Any]] = Field(default_factory=list)
    tokens_prompt: Optional[int] = None
    tokens_completion: Optional[int] = None
    tokens_total: Optional[int] = None
    safety_score: Optional[float] = None
    confidence_level: Optional[str] = None
    duration_ms: Optional[int] = None
    iterations: Optional[int] = None
    fallback_used: bool = False
    error_class: Optional[str] = None
    error_message: Optional[str] = None
    extra: dict[str, Any] = Field(default_factory=dict)

    def to_db_params(self) -> dict[str, Any]:
        """Aplana para INSERT (JSONB se serializa a string)."""
        d = self.model_dump()
        d["tools_invoked"] = json.dumps(d.get("tools_invoked") or [], ensure_ascii=False)
        d["extra"] = json.dumps(d.get("extra") or {}, ensure_ascii=False)
        # Truncar campos textuales largos para evitar payloads gigantes.
        for k in ("user_message", "response_text"):
            v = d.get(k)
            if isinstance(v, str) and len(v) > 8000:
                d[k] = v[:8000] + "...[truncated]"
        return d


# ──────────────────────────────────────────────────────────────────────────
# AuditLogger — persistencia
# ──────────────────────────────────────────────────────────────────────────


_AUDIT_INSERT_SQL = """
INSERT INTO public.agent_audit_logs (
    session_id, conversation_id, role, phone_e164, user_message,
    response_text, intent, tools_invoked, tokens_prompt, tokens_completion,
    tokens_total, safety_score, confidence_level, duration_ms, iterations,
    fallback_used, error_class, error_message, extra
) VALUES (
    :session_id, :conversation_id, :role, :phone_e164, :user_message,
    :response_text, :intent, :tools_invoked::jsonb, :tokens_prompt, :tokens_completion,
    :tokens_total, :safety_score, :confidence_level, :duration_ms, :iterations,
    :fallback_used, :error_class, :error_message, :extra::jsonb
)
RETURNING id
"""


class AuditLogger:
    """Capa fina sobre SQLAlchemy para escribir a `agent_audit_logs`.

    El `engine_provider` es una callable() -> Engine; se inyecta para
    facilitar tests (mock) y para evitar import circular con `main`.
    """

    def __init__(self, engine_provider):
        self._engine_provider = engine_provider
        self._ddl_applied = False
        self._ddl_lock = threading.Lock()
        self._ddl_failed_once = False

    def _ensure_table(self) -> None:
        if self._ddl_applied or self._ddl_failed_once:
            return
        with self._ddl_lock:
            if self._ddl_applied or self._ddl_failed_once:
                return
            try:
                from sqlalchemy import text
                engine = self._engine_provider()
                with engine.begin() as conn:
                    conn.execute(text(AGENT_AUDIT_LOGS_DDL))
                self._ddl_applied = True
                logger.info("AuditLogger: tabla agent_audit_logs lista.")
            except Exception as exc:
                self._ddl_failed_once = True
                logger.warning("AuditLogger: no se pudo crear/verificar tabla (%s). Auditoría desactivada.", exc)

    def record_agent_turn(self, entry: AgentAuditEntry) -> Optional[int]:
        """Persiste un turno. Devuelve id si tuvo éxito, None si silenció el error."""
        self._ensure_table()
        if self._ddl_failed_once:
            return None
        try:
            from sqlalchemy import text
            engine = self._engine_provider()
            params = entry.to_db_params()
            with engine.begin() as conn:
                row = conn.execute(text(_AUDIT_INSERT_SQL), params).fetchone()
                return int(row[0]) if row else None
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "AuditLogger: no se pudo persistir turno (conv=%s, err=%s)",
                entry.conversation_id,
                exc,
            )
            return None


# ──────────────────────────────────────────────────────────────────────────
# Helpers para construir el AgentAuditEntry desde el resultado de agent_v3
# ──────────────────────────────────────────────────────────────────────────


def build_entry_from_ai_result(
    *,
    ai_result: dict,
    role: str,
    phone_e164: Optional[str],
    conversation_id: Optional[int],
    user_message: Optional[str],
    duration_ms: Optional[int] = None,
    fallback_used: bool = False,
    error: Optional[BaseException] = None,
) -> AgentAuditEntry:
    """Convierte el dict que retorna `generate_agent_reply_v3` a AuditEntry."""
    ai_result = ai_result or {}
    tool_calls = ai_result.get("tool_calls") or []
    # Empacar tools (sólo metadata, sin payloads gigantes).
    tools_invoked: list[dict[str, Any]] = []
    safety_score: Optional[float] = None
    for tc in tool_calls:
        if not isinstance(tc, dict):
            continue
        compact = {"name": tc.get("name")}
        args = tc.get("args")
        if isinstance(args, dict):
            compact["args_keys"] = sorted(args.keys())
        result = tc.get("result")
        if isinstance(result, str):
            compact["result_chars"] = len(result)
            # Intentar extraer safety_score del JSON de RAG.
            if safety_score is None and "safety_score" in result:
                try:
                    parsed = json.loads(result)
                    sc = parsed.get("safety_score") if isinstance(parsed, dict) else None
                    if isinstance(sc, (int, float)):
                        safety_score = float(sc)
                except Exception:
                    pass
        tools_invoked.append(compact)

    confidence = ai_result.get("confidence") or {}
    usage = ai_result.get("usage") or {}

    return AgentAuditEntry(
        session_id=ai_result.get("session_id"),
        conversation_id=conversation_id,
        role=role if role in ("internal", "external") else "unknown",
        phone_e164=phone_e164,
        user_message=user_message,
        response_text=ai_result.get("response_text"),
        intent=ai_result.get("intent"),
        tools_invoked=tools_invoked,
        tokens_prompt=usage.get("prompt_tokens"),
        tokens_completion=usage.get("completion_tokens"),
        tokens_total=usage.get("total_tokens"),
        safety_score=safety_score,
        confidence_level=(confidence or {}).get("level"),
        duration_ms=duration_ms,
        iterations=ai_result.get("iterations"),
        fallback_used=fallback_used,
        error_class=type(error).__name__ if error else None,
        error_message=str(error)[:500] if error else None,
        extra={},
    )


# ──────────────────────────────────────────────────────────────────────────
# Singleton perezoso del logger (inyectable en tests)
# ──────────────────────────────────────────────────────────────────────────

_audit_logger_singleton: Optional[AuditLogger] = None
_audit_logger_lock = threading.Lock()


def get_audit_logger() -> AuditLogger:
    """Devuelve el AuditLogger singleton (cableado a `main.engine`)."""
    global _audit_logger_singleton
    if _audit_logger_singleton is not None:
        return _audit_logger_singleton
    with _audit_logger_lock:
        if _audit_logger_singleton is not None:
            return _audit_logger_singleton

        def _engine_provider():
            try:
                from main import engine  # type: ignore
                return engine
            except ImportError:
                from backend.main import engine  # type: ignore
                return engine

        _audit_logger_singleton = AuditLogger(_engine_provider)
        return _audit_logger_singleton


def set_audit_logger_for_tests(logger_instance: AuditLogger) -> None:
    """Inyecta un AuditLogger custom (con engine_provider mockeado) para tests."""
    global _audit_logger_singleton
    _audit_logger_singleton = logger_instance


__all__ = [
    "AGENT_AUDIT_LOGS_DDL",
    "AgentAuditEntry",
    "AuditLogger",
    "build_entry_from_ai_result",
    "get_audit_logger",
    "set_audit_logger_for_tests",
]
