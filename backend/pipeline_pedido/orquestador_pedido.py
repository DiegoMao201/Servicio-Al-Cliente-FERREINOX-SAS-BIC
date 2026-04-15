"""
orquestador_pedido.py — Orquestador central del pipeline de pedidos directos
=============================================================================

Flujo completo:
  1. Validar tienda (si no hay, retornar pregunta)
  2. Matchear cada línea contra inventario + International + bicomponentes
  3. Validar resultado (stock, RAL, bicomponentes, completitud)
  4. Si válido → generar Excel + subir Dropbox + enviar email
  5. Construir respuesta WhatsApp determinística
"""
from __future__ import annotations

import logging
import time
import uuid
from typing import Callable, Optional

from .matcher_inventario import (
    ResultadoMatchPedido,
    match_pedido_completo,
)
from .validador_pedido import (
    ResultadoValidacion,
    ejecutar_validacion_pedido,
    resolver_tienda,
    FeedbackPedido,
)
from .generador_excel import (
    generar_excel_pedido,
    build_nombre_archivo_pedido,
)
from .notificador import (
    ResultadoNotificacion,
    notificar_pedido,
)

logger = logging.getLogger("pipeline_pedido.orquestador")


# ============================================================================
# RESPUESTA WHATSAPP DETERMINÍSTICA
# ============================================================================

def _formato_precio(valor: float) -> str:
    if not valor:
        return "$0"
    return f"${valor:,.0f}".replace(",", ".")


def construir_respuesta_whatsapp(
    match_result: ResultadoMatchPedido,
    validacion: ResultadoValidacion,
    notificacion: ResultadoNotificacion | None = None,
    cliente_nombre: str = "",
) -> str:
    """Construye respuesta WhatsApp profesional y determinística (CERO alucinación)."""
    lines = []

    # ── Acciones requeridas primero ──
    if not validacion.puede_continuar:
        for fb in validacion.feedbacks:
            if fb.status == "action_required":
                return fb.mensaje_usuario
        return "Necesito mas informacion para procesar tu pedido."

    # Header
    tienda_label = match_result.tienda_nombre or match_result.tienda_codigo
    lines.append(f"*PEDIDO - {tienda_label}*")
    lines.append("")

    # ── Productos resueltos ──
    total_bruto = 0
    total_con_dto = 0

    for prod in match_result.productos_resueltos:
        disp = "OK" if prod.disponible else "AGOTADO"
        disp_icon = "+" if prod.disponible else "x"
        subtotal = prod.precio_unitario * prod.cantidad
        total_bruto += subtotal
        if prod.descuento_pct:
            subtotal_dto = subtotal * (1 - prod.descuento_pct / 100)
        else:
            subtotal_dto = subtotal
        total_con_dto += subtotal_dto

        ref = prod.codigo_encontrado
        desc = prod.descripcion_real
        cant = int(prod.cantidad)
        precio = _formato_precio(prod.precio_unitario)
        sub = _formato_precio(subtotal_dto)

        line = f"[{disp_icon}] *[{ref}]* | {disp}"
        lines.append(line)
        lines.append(f"    {desc}")
        lines.append(f"    Cant: {cant} | {precio} c/u | Sub: {sub}")
        if prod.descuento_pct:
            lines.append(f"    Dto: {prod.descuento_pct}%")
        if prod.ral_detectado:
            lines.append(f"    RAL: {prod.ral_detectado}")
        if not prod.disponible:
            lines.append(f"    Stock: {int(prod.stock_disponible)} disponibles")
        lines.append("")

    # ── Bicomponentes inyectados ──
    for bico in match_result.bicomponentes_inyectados:
        if bico.codigo_encontrado and bico.disponible:
            total_con_dto += bico.precio_unitario * bico.cantidad_sugerida
            lines.append(
                f"[*] *[{bico.codigo_encontrado}]* | {bico.tipo.upper()}"
            )
            lines.append(f"    {bico.descripcion_real}")
            lines.append(
                f"    (Requerido para {bico.para_producto}) | "
                f"{_formato_precio(bico.precio_unitario)} c/u"
            )
            lines.append("")
        elif bico.nombre:
            lines.append(
                f"[!] {bico.tipo.upper()}: *{bico.nombre}* requerido "
                f"para {bico.para_producto} - verificar disponibilidad"
            )
            lines.append("")

    # ── Productos no encontrados ──
    for fallido in match_result.productos_fallidos:
        lines.append(
            f"[?] *{fallido.producto_solicitado}*: necesito la referencia "
            f"exacta o presentacion para ubicarlo."
        )
        lines.append("")

    # ── Pendientes (RAL) ──
    for pend in match_result.productos_pendientes:
        lines.append(f"[!] {pend.mensaje_usuario}")
        lines.append("")

    # ── Totales ──
    lines.append("---")
    if match_result.descuentos_aplicados:
        lines.append(f"Subtotal bruto: {_formato_precio(total_bruto)}")
    lines.append(f"*Total: {_formato_precio(total_con_dto)}*")

    # ── Advertencias ──
    warnings_stock = [
        fb for fb in validacion.feedbacks
        if fb.gate == "stock" and fb.status == "warning"
    ]
    if warnings_stock:
        lines.append("")
        lines.append("_Advertencias de stock:_")
        for w in warnings_stock:
            lines.append(f"  - {w.mensaje_usuario}")

    # ── Notificación ──
    if notificacion:
        lines.append("")
        if notificacion.email_enviado:
            lines.append(
                f"Correo enviado a {tienda_label} "
                f"(CC: compras@ferreinox.co)"
            )
        if notificacion.dropbox_subido:
            lines.append("Excel guardado en Dropbox")
        if notificacion.errores:
            for err in notificacion.errores:
                lines.append(f"Nota: {err}")

    return "\n".join(lines)


# ============================================================================
# PIPELINE PRINCIPAL
# ============================================================================

def ejecutar_pipeline_pedido(
    lineas_parseadas: list[dict],
    tienda_texto: str = "",
    cliente_nombre: str = "",
    notas: str = "",
    descuentos: list[dict] | None = None,
    lookup_fn: Callable = None,
    price_fn: Callable = None,
    send_email_fn: Callable | None = None,
    upload_dropbox_fn: Callable | None = None,
    conversation_id: str = "",
    pedido_id: int | str = 0,
    dropbox_folder: str = "/data/pedidos",
) -> dict:
    """
    Ejecuta el pipeline completo de pedido directo.

    Parámetros:
        lineas_parseadas: Lista de líneas parseadas del mensaje del cliente
        tienda_texto: Texto libre con la tienda de despacho
        cliente_nombre: Nombre del cliente
        notas: Notas adicionales
        descuentos: [{marca: str, porcentaje: float}]
        lookup_fn: Función de búsqueda en inventario
        price_fn: Función de precio por código
        send_email_fn: Función para enviar email (inyectada de main.py)
        upload_dropbox_fn: Función para subir a Dropbox (inyectada de main.py)
        conversation_id: ID de conversación WhatsApp
        pedido_id: ID del pedido
        dropbox_folder: Carpeta Dropbox destino

    Retorna: dict con:
        exito: bool
        bloqueado: bool
        respuesta_whatsapp: str
        match_result: dict
        validacion: dict
        notificacion: dict | None
        excel_filename: str
        feedbacks: list[dict]
        trace: dict
    """
    trace_id = uuid.uuid4().hex[:8]
    t_start = time.time()
    logger.info("PIPELINE_PEDIDO[%s] conv=%s inicio", trace_id, conversation_id)

    # ── 1. Resolver tienda ── (ANTES de lookup para no gastar API sin tienda)
    tienda_codigo, tienda_nombre = resolver_tienda(tienda_texto)

    if not tienda_codigo:
        # Sin tienda → preguntar ANTES de hacer los lookups (evita 20+ API calls)
        placeholder = ResultadoMatchPedido(
            tienda_codigo="", tienda_nombre="",
        )
        validacion = ejecutar_validacion_pedido(placeholder)
        respuesta = construir_respuesta_whatsapp(
            placeholder, validacion, None, cliente_nombre,
        )
        elapsed = int((time.time() - t_start) * 1000)
        logger.info(
            "PIPELINE_PEDIDO[%s] bloqueado (sin tienda, sin lookup) | %dms",
            trace_id, elapsed,
        )
        return {
            "exito": False,
            "bloqueado": True,
            "respuesta_whatsapp": respuesta,
            "match_result": placeholder.to_dict(),
            "validacion": validacion.to_dict(),
            "notificacion": None,
            "excel_filename": "",
            "feedbacks": [f.to_dict() for f in validacion.feedbacks],
            "trace": {
                "trace_id": trace_id,
                "conversation_id": conversation_id,
                "elapsed_ms": elapsed,
                "stage": "validacion_tienda",
            },
        }

    # ── 2. Match contra inventario ──
    match_result = match_pedido_completo(
        lineas_parseadas=lineas_parseadas,
        lookup_fn=lookup_fn or (lambda x: []),
        price_fn=price_fn or (lambda x: {}),
        tienda_codigo=tienda_codigo,
        tienda_nombre=tienda_nombre,
        descuentos=descuentos,
    )

    # ── 3. Validar ──
    validacion = ejecutar_validacion_pedido(match_result)

    # ── 4. Si no puede continuar → retorno inmediato ──
    if not validacion.puede_continuar:
        respuesta = construir_respuesta_whatsapp(
            match_result, validacion, None, cliente_nombre,
        )
        elapsed = int((time.time() - t_start) * 1000)
        logger.info(
            "PIPELINE_PEDIDO[%s] bloqueado (tienda) | %dms", trace_id, elapsed,
        )
        return {
            "exito": False,
            "bloqueado": True,
            "respuesta_whatsapp": respuesta,
            "match_result": match_result.to_dict(),
            "validacion": validacion.to_dict(),
            "notificacion": None,
            "excel_filename": "",
            "feedbacks": [f.to_dict() for f in validacion.feedbacks],
            "trace": {
                "trace_id": trace_id,
                "conversation_id": conversation_id,
                "elapsed_ms": elapsed,
                "stage": "validacion_tienda",
            },
        }

    # ── 5. Generar Excel ──
    excel_bytes = None
    excel_filename = ""
    icg_rows = []

    if match_result.total_resueltos > 0:
        try:
            excel_bytes, icg_rows = generar_excel_pedido(
                match_result, cliente_nombre, notas,
            )
            excel_filename = build_nombre_archivo_pedido(
                cliente_nombre, tienda_codigo, tienda_nombre, pedido_id,
            )
            logger.info(
                "PIPELINE_PEDIDO[%s] Excel generado: %s (%d filas ICG)",
                trace_id, excel_filename, len(icg_rows),
            )
        except Exception as exc:
            logger.error("PIPELINE_PEDIDO[%s] Error Excel: %s", trace_id, exc)

    # ── 6. Notificar (email + Dropbox) ──
    notificacion = None
    if excel_bytes and validacion.valido:
        notificacion = notificar_pedido(
            match_result=match_result,
            excel_bytes=excel_bytes,
            excel_filename=excel_filename,
            cliente_nombre=cliente_nombre,
            notas=notas,
            send_email_fn=send_email_fn,
            upload_dropbox_fn=upload_dropbox_fn,
            dropbox_folder=dropbox_folder,
        )

    # ── 7. Construir respuesta WhatsApp ──
    respuesta = construir_respuesta_whatsapp(
        match_result, validacion, notificacion, cliente_nombre,
    )

    elapsed = int((time.time() - t_start) * 1000)
    exito = validacion.valido and match_result.total_resueltos > 0

    logger.info(
        "PIPELINE_PEDIDO[%s] completado | exito=%s | %d resueltos | "
        "%d fallidos | %d pendientes | %dms",
        trace_id, exito, match_result.total_resueltos,
        len(match_result.productos_fallidos),
        len(match_result.productos_pendientes),
        elapsed,
    )

    return {
        "exito": exito,
        "bloqueado": not validacion.puede_continuar,
        "respuesta_whatsapp": respuesta,
        "match_result": match_result.to_dict(),
        "validacion": validacion.to_dict(),
        "notificacion": notificacion.to_dict() if notificacion else None,
        "excel_filename": excel_filename,
        "excel_bytes": excel_bytes,
        "icg_rows": icg_rows,
        "feedbacks": [f.to_dict() for f in validacion.feedbacks],
        "trace": {
            "trace_id": trace_id,
            "conversation_id": conversation_id,
            "elapsed_ms": elapsed,
            "stage": "completado",
            "resueltos": match_result.total_resueltos,
            "fallidos": len(match_result.productos_fallidos),
            "pendientes": len(match_result.productos_pendientes),
        },
    }
