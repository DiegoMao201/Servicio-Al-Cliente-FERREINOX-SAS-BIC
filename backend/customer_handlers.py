"""Capa de Handlers de Cliente — Fase C3 HITO 3.

Extrae los handlers de creación/verificación de clientes desde
``backend.main``, aplicando inyección de dependencias (DI) explícita.

Patrón DI:
  Cada handler acepta un parámetro keyword opcional ``deps``. Si se omite,
  el handler resuelve sus dependencias mediante lazy import de
  ``backend.main`` (vía ``_default_deps()``). Esto preserva 100% la API
  pública del re-export en main.py mientras permite a tests/refactors
  futuros pasar mocks o implementaciones alternativas.

Handlers extraídos:
  - ``_handle_tool_verificar_identidad``  (96 líneas)
  - ``_handle_tool_registrar_cliente_nuevo`` (251 líneas)

DEUDA TÉCNICA EXPLÍCITA — handler NO extraído:
  - ``_handle_tool_confirmar_pedido`` (686 líneas, ~30 dependencias
    transitivas: pricing, descuentos, validación de inventario, generación
    de PDF, envío de WhatsApp, integración Siigo, persistencia).
    Mover este handler con el patrón "Move & Wire" trasladaría el
    monolito en lugar de modularizar. Requiere una sesión dedicada
    para extraer primero sus sub-componentes (pricing, pdf, siigo)
    antes de poder aislar el handler.
"""

from __future__ import annotations

import json
import re
from typing import Any, Callable, Optional, TypedDict

from sqlalchemy import text


class _CustomerDeps(TypedDict, total=False):
    """Contrato de dependencias para los customer handlers."""
    get_db_engine: Callable[[], Any]
    resolve_identity_candidate: Callable[..., Any]
    find_cliente_contexto_by_name: Callable[..., Any]
    find_cliente_contexto_by_document: Callable[..., Any]
    fetch_client_by_nif_or_codigo: Callable[..., Any]
    update_contact_cliente: Callable[..., Any]
    update_conversation_context: Callable[..., Any]
    normalize_phone_e164: Callable[..., Any]
    logger: Any


def _default_deps() -> _CustomerDeps:
    """Lazy resolución de dependencias desde ``backend.main``.

    El acoplamiento queda contenido en este único punto. Los tests
    pueden inyectar un dict propio para evitar tocar ``main``.
    """
    try:
        from backend import main as _main
    except ImportError:
        import main as _main  # type: ignore
    return {
        "get_db_engine": _main.get_db_engine,
        "resolve_identity_candidate": _main.resolve_identity_candidate,
        "find_cliente_contexto_by_name": _main.find_cliente_contexto_by_name,
        "find_cliente_contexto_by_document": _main.find_cliente_contexto_by_document,
        "fetch_client_by_nif_or_codigo": _main.fetch_client_by_nif_or_codigo,
        "update_contact_cliente": _main.update_contact_cliente,
        "update_conversation_context": _main.update_conversation_context,
        "normalize_phone_e164": _main.normalize_phone_e164,
        "logger": _main.logger,
    }


# ─────────────────────────────────────────────────────────────────────────────
# TOOL: verificar_identidad
# ─────────────────────────────────────────────────────────────────────────────

def _handle_tool_verificar_identidad(
    args: dict,
    context: dict,
    conversation_context: dict,
    *,
    deps: Optional[_CustomerDeps] = None,
) -> str:
    d = deps or _default_deps()
    resolve_identity_candidate = d["resolve_identity_candidate"]
    find_cliente_contexto_by_name = d["find_cliente_contexto_by_name"]
    update_contact_cliente = d["update_contact_cliente"]
    update_conversation_context = d["update_conversation_context"]
    fetch_client_by_nif_or_codigo = d["fetch_client_by_nif_or_codigo"]

    criterio = args.get("criterio_busqueda", "").strip()
    if not criterio:
        return json.dumps({"verificado": False, "mensaje": "No se proporcionó criterio de búsqueda."}, ensure_ascii=False)

    is_numeric = bool(re.fullmatch(r"[\d\-\.]+", criterio.replace(" ", "")))

    verified_context = None
    verified_by = None

    if is_numeric:
        identity_candidate = {"type": "numeric_lookup", "value": criterio}
        try:
            verified_context, verified_by = resolve_identity_candidate(
                identity_candidate, context.get("telefono_e164", "")
            )
        except Exception:
            verified_context, verified_by = None, None
    else:
        try:
            name_result = find_cliente_contexto_by_name(criterio)
            if name_result:
                verified_context = name_result
                verified_by = "name"
        except Exception:
            verified_context, verified_by = None, None

    if verified_context:
        cliente_codigo = verified_context.get("cliente_codigo")
        try:
            cliente_id = update_contact_cliente(context["contact_id"], cliente_codigo)
            context["cliente_id"] = cliente_id
        except Exception:
            pass
        update_conversation_context(
            context["conversation_id"],
            {
                "verified": True,
                "verified_document": criterio if is_numeric else None,
                "verified_by": verified_by,
                "verified_cliente_codigo": cliente_codigo,
                "awaiting_verification": False,
                "awaiting_name_confirmation": False,
            },
        )
        conversation_context.update(
            {
                "verified": True,
                "verified_document": criterio if is_numeric else None,
                "verified_by": verified_by,
                "verified_cliente_codigo": cliente_codigo,
            }
        )
        result = {
                "verificado": True,
                "nombre_cliente": verified_context.get("nombre_cliente"),
                "cliente_codigo": cliente_codigo,
                "ciudad": verified_context.get("ciudad"),
                "nit": verified_context.get("nit"),
            }
        # Enrich with agent_clientes data (by NIF, cliente_codigo, or criterio)
        enrich_keys = [verified_context.get("nit"), cliente_codigo, criterio if is_numeric else None]
        client_extra = None
        for ek in enrich_keys:
            if ek and not client_extra:
                client_extra = fetch_client_by_nif_or_codigo(str(ek))
        if client_extra:
            if client_extra.get("categoria"):
                result["categoria_cliente"] = client_extra["categoria"]
            if client_extra.get("ciudad"):
                result["ciudad"] = result.get("ciudad") or client_extra["ciudad"]
            if client_extra.get("email"):
                result["email"] = client_extra["email"]
            if client_extra.get("segmento"):
                result["segmento"] = client_extra["segmento"]
            if client_extra.get("direccion"):
                result["direccion"] = client_extra["direccion"]
            if client_extra.get("razon_social"):
                result["razon_social"] = client_extra["razon_social"]
        return json.dumps(result, ensure_ascii=False, default=str)
    else:
        tipo = "documento" if is_numeric else "nombre"
        return json.dumps(
            {
                "verificado": False,
                "mensaje": f"No se encontró un cliente con ese {tipo}: {criterio}. "
                "Puede estar incorrecto o no estar registrado.",
            },
            ensure_ascii=False,
        )


# ─────────────────────────────────────────────────────────────────────────────
# TOOL: registrar_cliente_nuevo
# ─────────────────────────────────────────────────────────────────────────────

def _handle_tool_registrar_cliente_nuevo(
    args: dict,
    context: dict,
    conversation_context: dict,
    *,
    deps: Optional[_CustomerDeps] = None,
) -> str:
    """Register a new client in agent_clientes and link to WhatsApp contact."""
    d = deps or _default_deps()
    get_db_engine = d["get_db_engine"]
    find_cliente_contexto_by_document = d["find_cliente_contexto_by_document"]
    update_contact_cliente = d["update_contact_cliente"]
    update_conversation_context = d["update_conversation_context"]
    normalize_phone_e164 = d["normalize_phone_e164"]
    logger = d["logger"]

    modo_registro = (args.get("modo_registro") or args.get("tipo_documento") or "").strip().lower()
    if modo_registro not in {"cotizacion", "pedido"}:
        modo_registro = (conversation_context.get("commercial_draft") or {}).get("tipo_documento") or "pedido"
    if modo_registro not in {"cotizacion", "pedido"}:
        modo_registro = "pedido"

    nombre = (args.get("nombre_completo") or "").strip()
    cedula_nit = (args.get("cedula_nit") or "").strip()
    telefono = (args.get("telefono") or context.get("telefono_e164") or "").strip()
    direccion = (args.get("direccion_entrega") or "").strip()
    ciudad = (args.get("ciudad") or "").strip()
    email = (args.get("email") or "").strip()

    if not nombre:
        return json.dumps({"registrado": False, "mensaje": "Falta el nombre completo del cliente."}, ensure_ascii=False)
    if not cedula_nit:
        return json.dumps({"registrado": False, "mensaje": "Falta la cédula o NIT del cliente."}, ensure_ascii=False)
    if modo_registro == "pedido" and not direccion:
        return json.dumps({"registrado": False, "mensaje": "Falta la dirección de entrega."}, ensure_ascii=False)
    if modo_registro == "pedido" and not ciudad:
        return json.dumps({"registrado": False, "mensaje": "Falta la ciudad de entrega."}, ensure_ascii=False)

    cedula_clean = cedula_nit.replace(".", "").replace("-", "").replace(" ", "")
    telefono_normalizado = normalize_phone_e164(telefono) or telefono
    document_type = "NIT" if len(cedula_clean) > 10 else "CC"

    def _split_customer_name(full_name: str):
        parts = [part for part in full_name.split() if part]
        return {
            "nombre_1": parts[0] if len(parts) > 0 else "",
            "otros_nombres": " ".join(parts[1:-2]) if len(parts) > 3 else (parts[1] if len(parts) > 1 else ""),
            "apellido_1": parts[-2] if len(parts) >= 3 else "",
            "apellido_2": parts[-1] if len(parts) >= 4 else "",
        }

    def _next_digital_customer_code(connection):
        max_agent = connection.execute(text(
            "SELECT COALESCE(MAX(codigo), 900000) FROM public.agent_clientes WHERE codigo >= 900000"
        )).scalar() or 900000
        max_public = connection.execute(text(
            "SELECT COALESCE(MAX(CASE WHEN codigo ~ '^[0-9]+$' THEN codigo::bigint END), 900000) FROM public.cliente"
        )).scalar() or 900000
        return int(max(max_agent, max_public)) + 1

    existing_context = None
    try:
        existing_context = find_cliente_contexto_by_document(cedula_clean)
    except Exception:
        existing_context = None

    ciudad_lower = ciudad.lower().strip()
    ciudades_eje_cafetero = ["pereira", "manizales", "armenia", "dosquebradas", "santa rosa", "chinchiná", "chinchina"]
    ciudad_despacho = ciudad if any(c in ciudad_lower for c in ciudades_eje_cafetero) else "Pereira"
    nota_logistica = ""
    if modo_registro == "pedido" and ciudad_despacho == "Pereira" and not any(c in ciudad_lower for c in ciudades_eje_cafetero):
        nota_logistica = (
            f"⚠️ La ciudad '{ciudad}' está fuera de las zonas principales del Eje Cafetero. "
            "El despacho se centraliza desde Pereira. El equipo de logística se comunicará "
            "con el cliente lo antes posible para coordinar la entrega."
        )

    try:
        registration_result = None
        registered_customer_code = None
        engine = get_db_engine()
        with engine.begin() as conn:
            existing_codigo = None
            if existing_context:
                existing_codigo = existing_context.get("cliente_codigo") or existing_context.get("verified_cliente_codigo")
            codigo_cliente = int(existing_codigo) if str(existing_codigo or "").isdigit() else _next_digital_customer_code(conn)

            conn.execute(text(
                """
                INSERT INTO public.cliente (
                    codigo, tipo_documento, numero_documento, nombre_legal, nombre_comercial,
                    email, telefono, celular, direccion, ciudad, segmento, updated_at
                ) VALUES (
                    :codigo, :tipo_documento, :numero_documento, :nombre_legal, :nombre_comercial,
                    :email, :telefono, :celular, :direccion, :ciudad, :segmento, now()
                )
                ON CONFLICT (tipo_documento, numero_documento)
                DO UPDATE SET
                    codigo = COALESCE(public.cliente.codigo, EXCLUDED.codigo),
                    nombre_legal = EXCLUDED.nombre_legal,
                    nombre_comercial = COALESCE(NULLIF(EXCLUDED.nombre_comercial, ''), public.cliente.nombre_comercial),
                    email = COALESCE(NULLIF(EXCLUDED.email, ''), public.cliente.email),
                    telefono = COALESCE(NULLIF(EXCLUDED.telefono, ''), public.cliente.telefono),
                    celular = COALESCE(NULLIF(EXCLUDED.celular, ''), public.cliente.celular),
                    direccion = COALESCE(NULLIF(EXCLUDED.direccion, ''), public.cliente.direccion),
                    ciudad = COALESCE(NULLIF(EXCLUDED.ciudad, ''), public.cliente.ciudad),
                    segmento = COALESCE(NULLIF(EXCLUDED.segmento, ''), public.cliente.segmento),
                    updated_at = now()
                """
            ), {
                "codigo": str(codigo_cliente),
                "tipo_documento": document_type,
                "numero_documento": cedula_clean,
                "nombre_legal": nombre.upper(),
                "nombre_comercial": nombre.upper(),
                "email": email,
                "telefono": telefono_normalizado,
                "celular": telefono_normalizado,
                "direccion": direccion,
                "ciudad": ciudad.upper(),
                "segmento": "WHATSAPP",
            })

            name_parts = _split_customer_name(nombre)
            name_payload = {key: value.upper() for key, value in name_parts.items()}
            existing_agent = conn.execute(text(
                """
                SELECT id
                FROM public.agent_clientes
                WHERE REPLACE(REPLACE(COALESCE(nif, ''), '.', ''), '-', '') = :nif
                   OR codigo = :codigo
                LIMIT 1
                """
            ), {"nif": cedula_clean, "codigo": codigo_cliente}).mappings().first()

            if existing_agent:
                conn.execute(text(
                    """
                    UPDATE public.agent_clientes
                    SET codigo = :codigo,
                        nombre = :nombre,
                        nif = :nif,
                        direccion = COALESCE(NULLIF(:direccion, ''), direccion),
                        telefono = COALESCE(NULLIF(:telefono, ''), telefono),
                        ciudad = COALESCE(NULLIF(:ciudad, ''), ciudad),
                        email = COALESCE(NULLIF(:email, ''), email),
                        nombre_1 = :nombre_1,
                        otros_nombres = :otros_nombres,
                        apellido_1 = :apellido_1,
                        apellido_2 = :apellido_2,
                        categoria = COALESCE(categoria, 'NUEVO'),
                        segmento = 'WHATSAPP',
                        clasificacion = 'CLIENTE_DIGITAL'
                    WHERE id = :id
                    """
                ), {
                    "id": existing_agent["id"],
                    "codigo": codigo_cliente,
                    "nombre": nombre.upper(),
                    "nif": cedula_clean,
                    "direccion": direccion,
                    "telefono": telefono_normalizado,
                    "ciudad": ciudad.upper(),
                    "email": email,
                    **name_payload,
                })
            else:
                conn.execute(text(
                    """
                    INSERT INTO public.agent_clientes
                        (codigo, nombre, nif, direccion, telefono, ciudad, email,
                         nombre_1, otros_nombres, apellido_1, apellido_2,
                         categoria, segmento, clasificacion)
                    VALUES
                        (:codigo, :nombre, :nif, :direccion, :telefono, :ciudad, :email,
                         :nombre_1, :otros_nombres, :apellido_1, :apellido_2,
                         'NUEVO', 'WHATSAPP', 'CLIENTE_DIGITAL')
                    """
                ), {
                    "codigo": codigo_cliente,
                    "nombre": nombre.upper(),
                    "nif": cedula_clean,
                    "direccion": direccion,
                    "telefono": telefono_normalizado,
                    "ciudad": ciudad.upper(),
                    "email": email,
                    **name_payload,
                })

            contact_id = context.get("contact_id")
            if contact_id:
                try:
                    conn.execute(text(
                        """
                        UPDATE public.whatsapp_contacto
                        SET nombre_visible = :nombre,
                            metadata = COALESCE(metadata, '{}'::jsonb) || CAST(:meta AS jsonb),
                            updated_at = NOW()
                        WHERE id = :cid
                        """
                    ), {
                        "nombre": nombre,
                        "meta": json.dumps({"cliente_codigo": codigo_cliente, "cedula": cedula_clean}),
                        "cid": contact_id,
                    })
                except Exception:
                    pass

            registration_result = {
                "registrado": True,
                "codigo_cliente": codigo_cliente,
                "nombre": nombre.upper(),
                "cedula_nit": cedula_clean,
                "telefono": telefono_normalizado,
                "direccion": direccion,
                "ciudad": ciudad.upper(),
                "ciudad_despacho": ciudad_despacho.upper(),
                "modo_registro": modo_registro,
                "mensaje": (
                    f"Cliente {nombre} validado exitosamente con código {codigo_cliente}."
                    if existing_context else
                    f"Cliente {nombre} registrado exitosamente con código {codigo_cliente}."
                ),
            }
            if modo_registro == "cotizacion":
                registration_result["datos_pendientes_para_pedido"] = ["direccion_entrega", "ciudad"]
            if nota_logistica:
                registration_result["nota_logistica"] = nota_logistica
            registered_customer_code = str(codigo_cliente)

        try:
            cliente_id = update_contact_cliente(contact_id, registered_customer_code) if contact_id and registered_customer_code else None
            if cliente_id:
                context["cliente_id"] = cliente_id
        except Exception:
            pass

        verified_customer_code = int(registered_customer_code) if registered_customer_code and registered_customer_code.isdigit() else registered_customer_code
        update_conversation_context(
            context["conversation_id"],
            {
                "verified": True,
                "verified_document": cedula_clean,
                "verified_by": "registration",
                "verified_cliente_codigo": verified_customer_code,
                "client_registered_now": True,
            },
        )
        conversation_context.update({
            "verified": True,
            "verified_document": cedula_clean,
            "verified_by": "registration",
            "verified_cliente_codigo": verified_customer_code,
        })

        return json.dumps(registration_result or {"registrado": False, "mensaje": "No fue posible completar el registro."}, ensure_ascii=False)

    except Exception as exc:
        logger.error("Error registrando cliente nuevo: %s", exc)
        return json.dumps(
            {"registrado": False, "mensaje": f"Error técnico al registrar: {exc}"},
            ensure_ascii=False,
        )


__all__ = [
    "_handle_tool_verificar_identidad",
    "_handle_tool_registrar_cliente_nuevo",
]
