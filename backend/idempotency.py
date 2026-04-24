"""F1 — Idempotencia ligera de webhooks WhatsApp.

Objetivo: descartar reintentos automáticos de Meta (mismo `message_id`)
ANTES de gastar tokens del LLM. Defensa #1 (in-memory TTL); la defensa #2
sigue siendo `inbound_message_already_processed` (DB).

Diseño:

  * Cache en memoria con TTL configurable (default 5 min).
  * Thread-safe vía `threading.Lock`.
  * Limpieza perezosa (lazy eviction) en cada acceso.
  * Sin dependencias externas (no Redis).
  * Estados: `processing` (en curso) y `done` (terminado). Ambos cuentan
    como "ya procesado" para idempotencia.

NOTA: Si el proceso se reinicia, la cache se pierde — la defensa de DB
absorbe el caso edge. Por eso es defensa #1, no #2.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Iterable, Optional

logger = logging.getLogger("ferreinox_agent.idempotency")


class WebhookIdempotencyCache:
    """TTL set en memoria para `message_id` ya vistos."""

    def __init__(self, ttl_seconds: int = 300):
        self._ttl = max(1, int(ttl_seconds))
        self._store: dict[str, float] = {}
        self._lock = threading.Lock()

    def _evict_expired(self, now: float) -> None:
        # Caller must hold the lock.
        expired = [k for k, ts in self._store.items() if now - ts > self._ttl]
        for k in expired:
            self._store.pop(k, None)

    def is_processed(self, message_id: Optional[str]) -> bool:
        """True si el message_id está en cache y no expiró."""
        if not message_id:
            return False
        now = time.time()
        with self._lock:
            self._evict_expired(now)
            ts = self._store.get(message_id)
            if ts is None:
                return False
            if now - ts > self._ttl:
                self._store.pop(message_id, None)
                return False
            return True

    def mark_processing(self, message_id: Optional[str]) -> None:
        """Registra que el message_id entró al pipeline."""
        if not message_id:
            return
        with self._lock:
            self._store[message_id] = time.time()

    def mark_processing_many(self, message_ids: Iterable[Optional[str]]) -> None:
        for mid in message_ids:
            self.mark_processing(mid)

    def filter_new(self, message_ids: Iterable[Optional[str]]) -> list[str]:
        """Devuelve sólo los IDs nuevos (no procesados)."""
        return [mid for mid in message_ids if mid and not self.is_processed(mid)]

    def clear(self) -> None:
        with self._lock:
            self._store.clear()

    def size(self) -> int:
        with self._lock:
            return len(self._store)


# Instancia global del proceso. El TTL se puede ajustar por env var.
import os as _os

_default_ttl = int(_os.getenv("WEBHOOK_IDEMPOTENCY_TTL_SECONDS", "300") or "300")
webhook_idempotency_cache = WebhookIdempotencyCache(ttl_seconds=_default_ttl)


def extract_inbound_message_ids(payload: dict) -> list[str]:
    """Extrae todos los `message_id` entrantes del payload de Meta."""
    ids: list[str] = []
    if not isinstance(payload, dict):
        return ids
    for entry in payload.get("entry", []) or []:
        for change in (entry or {}).get("changes", []) or []:
            value = (change or {}).get("value", {}) or {}
            for message in value.get("messages", []) or []:
                mid = (message or {}).get("id")
                if mid:
                    ids.append(mid)
    return ids


__all__ = [
    "WebhookIdempotencyCache",
    "webhook_idempotency_cache",
    "extract_inbound_message_ids",
]
