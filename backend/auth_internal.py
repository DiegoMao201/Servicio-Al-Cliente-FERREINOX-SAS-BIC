"""Capa de autenticación interna — núcleo crypto-puro.

Extraído de ``backend.main`` durante la Fase C2 (Modularización).
Contiene únicamente las primitivas crypto sin acoplamiento (hashlib/hmac/secrets).
El resto del flujo (session lifecycle DB-bound, employee directory,
``ensure_internal_auth_tables``, ``upsert_internal_user``, etc.) permanece en
``backend.main`` por su alto acoplamiento con get_db_engine, Pydantic models y
caches definidas lejos del bloque. Se extraerá en una iteración futura
dedicada.

Las funciones aquí se re-exportan desde ``backend.main`` para mantener
compatibilidad con todos los call-sites existentes (``main.hash_password_with_salt``
sigue siendo válido).
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets

from fastapi import HTTPException


# Iteraciones PBKDF2-HMAC-SHA256 para hash de contraseñas internas.
# Configurable vía env var; default 390k (recomendación OWASP 2023 para SHA-256).
INTERNAL_PASSWORD_ITERATIONS = int(os.getenv("INTERNAL_AUTH_PASSWORD_ITERATIONS", "390000"))


def hash_password_with_salt(password: str, salt_hex: str) -> str:
    """Calcula el hash PBKDF2-HMAC-SHA256 de ``password`` con la salt hex dada."""
    return hashlib.pbkdf2_hmac(
        "sha256",
        (password or "").encode("utf-8"),
        bytes.fromhex(salt_hex),
        INTERNAL_PASSWORD_ITERATIONS,
    ).hex()


def build_password_credentials(password: str) -> tuple[str, str]:
    """Genera ``(salt_hex, password_hash)`` para una contraseña interna nueva.

    Lanza HTTP 400 si la contraseña no cumple longitud mínima (8 caracteres).
    """
    if not password or len(password) < 8:
        raise HTTPException(
            status_code=400,
            detail="La contraseña interna debe tener al menos 8 caracteres.",
        )
    salt_hex = secrets.token_hex(16)
    return salt_hex, hash_password_with_salt(password, salt_hex)


def verify_password_hash(password: str, salt_hex: str, expected_hash: str) -> bool:
    """Verifica una contraseña contra el par ``(salt_hex, expected_hash)``.

    Usa ``hmac.compare_digest`` para evitar timing attacks.
    """
    calculated_hash = hash_password_with_salt(password, salt_hex)
    return hmac.compare_digest(calculated_hash, expected_hash)


def hash_session_token(raw_token: str) -> str:
    """Hash SHA-256 hex del token de sesión bruto, para almacenarlo en BD."""
    return hashlib.sha256((raw_token or "").encode("utf-8")).hexdigest()


__all__ = [
    "INTERNAL_PASSWORD_ITERATIONS",
    "hash_password_with_salt",
    "build_password_credentials",
    "verify_password_hash",
    "hash_session_token",
]
