"""SessionContext inmutable + clasificación RBAC (Phase E1).

Clasifica cada conversación entrante en uno de dos roles antes de armar
las herramientas para el LLM:

  * ``UserRole.INTERNAL``  — empleado Ferreinox (asesor, admin, BI).
  * ``UserRole.EXTERNAL``  — cliente final (B2B comprador, contratista).

La fuente de verdad para el rol ES el número telefónico E.164 contra la
tabla de usuarios internos (``internal_users.phone_e164``). Si NO hay
match, el rol por defecto es EXTERNAL — política de mínimo privilegio.

El ``SessionContext`` resultante es ``frozen`` y se pasa por inyección de
dependencias al orquestador (``llm_client``) y a cada tool handler. El
orquestador NUNCA debe re-inferir el rol leyendo el cuerpo del mensaje.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional


class UserRole(str, Enum):
    INTERNAL = "internal"
    EXTERNAL = "external"


@dataclass(frozen=True)
class SessionContext:
    """Contexto inmutable de la sesión del usuario."""

    role: UserRole
    phone_e164: Optional[str]
    # Identidad enriquecida si role=INTERNAL.
    internal_user_id: Optional[int] = None
    internal_username: Optional[str] = None
    internal_full_name: Optional[str] = None
    internal_scopes: tuple[str, ...] = field(default_factory=tuple)
    # Identidad enriquecida si role=EXTERNAL y ya se verificó.
    external_customer_code: Optional[str] = None
    external_customer_name: Optional[str] = None
    external_verified: bool = False

    # Convenience flags expuestos al orquestador.
    @property
    def is_internal(self) -> bool:
        return self.role == UserRole.INTERNAL

    @property
    def is_external(self) -> bool:
        return self.role == UserRole.EXTERNAL

    def with_external_verification(
        self,
        *,
        customer_code: str,
        customer_name: str,
    ) -> "SessionContext":
        """Devuelve una nueva sesión con la verificación de cliente externo."""
        return SessionContext(
            role=self.role,
            phone_e164=self.phone_e164,
            internal_user_id=self.internal_user_id,
            internal_username=self.internal_username,
            internal_full_name=self.internal_full_name,
            internal_scopes=self.internal_scopes,
            external_customer_code=customer_code,
            external_customer_name=customer_name,
            external_verified=True,
        )

    def to_audit_dict(self) -> dict[str, Any]:
        """Serialización para logs de auditoría."""
        return {
            "role": self.role.value,
            "phone_e164": self.phone_e164,
            "internal_user_id": self.internal_user_id,
            "internal_username": self.internal_username,
            "internal_scopes": list(self.internal_scopes),
            "external_customer_code": self.external_customer_code,
            "external_verified": self.external_verified,
        }


# ─────────────────────────────────────────────────────────────────────────
# Clasificador
# ─────────────────────────────────────────────────────────────────────────

# Inyección de dependencias para los lookups: se reciben como argumentos para
# que los tests puedan pasar mocks deterministas sin tocar la BD.

InternalLookupFn = Callable[[str], Optional[dict]]


def classify_session_from_phone(
    phone_number: Optional[str],
    *,
    normalize_phone: Callable[[Optional[str]], Optional[str]],
    fetch_internal_user_by_phone: InternalLookupFn,
) -> SessionContext:
    """Determina el rol del usuario por teléfono.

    Args:
        phone_number: número crudo recibido por WhatsApp (cualquier formato).
        normalize_phone: callable que devuelve el número en E.164 o None.
            En producción: ``main.normalize_phone_e164``.
        fetch_internal_user_by_phone: callable que recibe un número en E.164
            y devuelve el dict del usuario interno (con scopes) si existe,
            o None. En producción: ``main.fetch_internal_user_by_phone``.

    Política: Cualquier teléfono que NO esté registrado en
    ``internal_users.phone_e164`` se considera EXTERNAL. Cero excepciones.
    """
    normalized = normalize_phone(phone_number)
    if not normalized:
        return SessionContext(role=UserRole.EXTERNAL, phone_e164=None)

    user_row = fetch_internal_user_by_phone(normalized)
    if not user_row or not user_row.get("is_active", True):
        return SessionContext(role=UserRole.EXTERNAL, phone_e164=normalized)

    return SessionContext(
        role=UserRole.INTERNAL,
        phone_e164=normalized,
        internal_user_id=user_row.get("id"),
        internal_username=user_row.get("username"),
        internal_full_name=user_row.get("full_name"),
        internal_scopes=tuple(user_row.get("scopes") or ()),
    )


__all__ = [
    "UserRole",
    "SessionContext",
    "classify_session_from_phone",
]
