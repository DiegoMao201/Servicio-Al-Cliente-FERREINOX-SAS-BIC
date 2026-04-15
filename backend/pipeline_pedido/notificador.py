"""
notificador.py — Notificaciones email + Dropbox para pedidos
============================================================

Responsabilidades:
  1. Subir Excel del pedido a Dropbox
  2. Enviar email HTML profesional a la tienda de despacho
  3. CC a compras@ferreinox.co
  4. Adjuntar Excel como attachment
"""
from __future__ import annotations

import base64
import logging
from dataclasses import dataclass, asdict
from datetime import datetime
from html import escape
from typing import Callable, Optional

from .matcher_inventario import ResultadoMatchPedido

logger = logging.getLogger("pipeline_pedido.notificador")

# ============================================================================
# CONFIGURACIÓN — importar de main.py para evitar duplicación
# ============================================================================

def _get_config():
    """Carga config lazily desde main.py (evita circular imports)."""
    try:
        import main as _m
        return {
            "TIENDA_EMAILS": getattr(_m, "DEFAULT_TRANSFER_DESTINATION_EMAILS", {}),
            "CC_COMPRAS": getattr(_m, "DEFAULT_TRANSFER_CC_EMAILS", ["compras@ferreinox.co"]),
            "CORPORATE_BRAND": getattr(_m, "CORPORATE_BRAND", {}),
        }
    except ImportError:
        return {}

# Fallback local (para tests sin main.py)
_TIENDA_EMAILS_LOCAL = {
    "189": "tiendapintucopereira@ferreinox.co",
    "157": "tiendapintucomanizales@ferreinox.co",
    "158": "tiendapintucodosquebradas@ferreinox.co",
    "156": "tiendapintucoarmenia@ferreinox.co",
    "463": "tiendapintucocerritos@ferreinox.co",
    "238": "tiendapintucolaureles@ferreinox.co",
}

_CC_COMPRAS_LOCAL = ["compras@ferreinox.co"]

_CORPORATE_BRAND_LOCAL = {
    "company_name": "FERREINOX S.A.S. BIC",
    "nit": "800.224.617-8",
    "address": "CR 13 19-26, Pereira, Risaralda, Colombia",
    "website": "https://www.ferreinox.co",
    "service_email": "hola@ferreinox.co",
    "phone": "(606) 333 0101",
    "brand_dark": "#111827",
    "brand_accent": "#F59E0B",
    "brand_light": "#F9FAFB",
    "brand_border": "#E5E7EB",
}


def _tienda_emails():
    cfg = _get_config()
    return cfg.get("TIENDA_EMAILS") or _TIENDA_EMAILS_LOCAL


def _cc_compras():
    cfg = _get_config()
    return cfg.get("CC_COMPRAS") or _CC_COMPRAS_LOCAL


def _corporate_brand():
    cfg = _get_config()
    return cfg.get("CORPORATE_BRAND") or _CORPORATE_BRAND_LOCAL


# ============================================================================
# HTML EMAIL BUILDER
# ============================================================================

def _brand_email_shell(title: str, body_html: str) -> str:
    """Envuelve contenido en template Ferreinox corporativo."""
    b = _corporate_brand()
    return (
        "<div style='margin:0;padding:24px;background:#f3f4f6;font-family:Segoe UI,Arial,sans-serif;color:#111827;'>"
        f"<div style='max-width:760px;margin:0 auto;background:#fff;border:1px solid {b['brand_border']};border-radius:18px;overflow:hidden;'>"
        f"<div style='background:{b['brand_dark']};padding:28px 32px;color:#fff;'>"
        "<div style='font-size:12px;letter-spacing:1.2px;text-transform:uppercase;opacity:.8;'>Ferreinox SAS BIC</div>"
        f"<div style='font-size:28px;font-weight:700;margin-top:6px;'>{escape(title)}</div>"
        f"<div style='margin-top:10px;font-size:13px;color:#d1d5db;'>NIT {escape(b['nit'])} | {escape(b['address'])}</div>"
        "</div>"
        f"<div style='padding:28px 32px;background:{b['brand_light']};'>{body_html}</div>"
        f"<div style='padding:22px 32px;background:#fff;border-top:1px solid {b['brand_border']};font-size:12px;color:#6b7280;'>"
        f"<strong style='color:#111827;'>{escape(b['company_name'])}</strong><br>"
        f"Sitio web: <a href='{escape(b['website'])}' style='color:{b['brand_accent']};'>{escape(b['website'])}</a><br>"
        f"Correo: {escape(b['service_email'])} | Tel: {escape(b['phone'])}"
        "</div></div></div>"
    )


def _build_order_email_html(
    match_result: ResultadoMatchPedido,
    cliente_nombre: str = "",
    notas: str = "",
) -> str:
    """Construye el HTML del email de pedido."""
    tienda = match_result.tienda_nombre or match_result.tienda_codigo or "N/A"
    fecha = datetime.now().strftime("%d/%m/%Y %H:%M")

    # Header info
    cb = _corporate_brand()
    body = (
        "<p style='margin:0 0 14px;font-size:15px;'>"
        "Se genero un nuevo pedido desde el agente WhatsApp.</p>"
        f"<div style='background:#fff;border:1px solid {cb['brand_border']};"
        "border-radius:14px;padding:18px 20px;margin-bottom:18px;'>"
        f"<p style='margin:0 0 8px;'><strong>Cliente:</strong> {escape(cliente_nombre or 'N/A')}</p>"
        f"<p style='margin:0 0 8px;'><strong>Tienda despacho:</strong> {escape(tienda)}</p>"
        f"<p style='margin:0 0 8px;'><strong>Fecha:</strong> {escape(fecha)}</p>"
        f"<p style='margin:0;'><strong>Productos:</strong> {match_result.total_resueltos} resueltos"
    )
    if match_result.productos_fallidos:
        body += f", {len(match_result.productos_fallidos)} no encontrados"
    if match_result.bicomponentes_inyectados:
        body += f", {len(match_result.bicomponentes_inyectados)} complementos"
    body += "</p></div>"

    # Tabla de productos
    body += (
        "<table style='width:100%;border-collapse:collapse;background:#fff;"
        "border:1px solid #e5e7eb;border-radius:12px;overflow:hidden;'>"
        "<thead><tr style='background:#111827;color:#fff;'>"
        "<th style='padding:12px;text-align:left;'>Referencia</th>"
        "<th style='padding:12px;text-align:left;'>Descripcion</th>"
        "<th style='padding:12px;text-align:center;'>Cant.</th>"
        "<th style='padding:12px;text-align:right;'>Precio</th>"
        "<th style='padding:12px;text-align:center;'>Dto%</th>"
        "<th style='padding:12px;text-align:center;'>Disp.</th>"
        "</tr></thead><tbody>"
    )

    total_bruto = 0
    for prod in match_result.productos_resueltos:
        subtotal = prod.precio_unitario * prod.cantidad
        total_bruto += subtotal
        disp = "SI" if prod.disponible else "NO"
        disp_color = "#059669" if prod.disponible else "#DC2626"
        body += (
            f"<tr><td style='padding:10px 12px;border-top:1px solid #e5e7eb;'>{escape(prod.codigo_encontrado)}</td>"
            f"<td style='padding:10px 12px;border-top:1px solid #e5e7eb;'>{escape(prod.descripcion_real)}</td>"
            f"<td style='padding:10px 12px;border-top:1px solid #e5e7eb;text-align:center;'>{int(prod.cantidad)}</td>"
            f"<td style='padding:10px 12px;border-top:1px solid #e5e7eb;text-align:right;'>${prod.precio_unitario:,.0f}</td>"
            f"<td style='padding:10px 12px;border-top:1px solid #e5e7eb;text-align:center;'>{prod.descuento_pct}%</td>"
            f"<td style='padding:10px 12px;border-top:1px solid #e5e7eb;text-align:center;"
            f"color:{disp_color};font-weight:700;'>{disp}</td></tr>"
        )

    # Bicomponentes
    for bico in match_result.bicomponentes_inyectados:
        if bico.codigo_encontrado:
            body += (
                f"<tr style='background:#FEF3C7;'>"
                f"<td style='padding:10px 12px;border-top:1px solid #e5e7eb;'>{escape(bico.codigo_encontrado)}</td>"
                f"<td style='padding:10px 12px;border-top:1px solid #e5e7eb;font-style:italic;'>"
                f"[AUTO] {escape(bico.tipo.upper())}: {escape(bico.descripcion_real)}</td>"
                f"<td style='padding:10px 12px;border-top:1px solid #e5e7eb;text-align:center;'>{int(bico.cantidad_sugerida)}</td>"
                f"<td style='padding:10px 12px;border-top:1px solid #e5e7eb;text-align:right;'>${bico.precio_unitario:,.0f}</td>"
                f"<td style='padding:10px 12px;border-top:1px solid #e5e7eb;text-align:center;'>0%</td>"
                f"<td style='padding:10px 12px;border-top:1px solid #e5e7eb;text-align:center;"
                f"color:{'#059669' if bico.disponible else '#DC2626'};font-weight:700;'>{'SI' if bico.disponible else 'NO'}</td></tr>"
            )

    body += "</tbody></table>"

    # Descuentos
    if match_result.descuentos_aplicados:
        body += "<p style='margin-top:14px;'><strong>Descuentos:</strong> "
        body += ", ".join(
            f"{d.get('marca', 'General')} {d.get('porcentaje', 0)}%"
            for d in match_result.descuentos_aplicados
        )
        body += "</p>"

    # Notas
    if notas:
        body += f"<p style='margin-top:14px;'><strong>Notas:</strong> {escape(notas)}</p>"

    body += "<p style='margin-top:18px;'>Se adjunta archivo Excel con el detalle del pedido.</p>"

    return _brand_email_shell("Nuevo Pedido WhatsApp", body)


def _build_order_email_text(
    match_result: ResultadoMatchPedido,
    cliente_nombre: str = "",
    notas: str = "",
) -> str:
    """Versión texto plano del email."""
    lines = [
        "NUEVO PEDIDO WHATSAPP - FERREINOX",
        f"Cliente: {cliente_nombre or 'N/A'}",
        f"Tienda: {match_result.tienda_nombre or 'N/A'} ({match_result.tienda_codigo})",
        f"Fecha: {datetime.now().strftime('%d/%m/%Y %H:%M')}",
        f"Productos: {match_result.total_resueltos}",
        "",
        "DETALLE:",
    ]
    for prod in match_result.productos_resueltos:
        disp = "DISP" if prod.disponible else "AGOTADO"
        lines.append(
            f"  [{prod.codigo_encontrado}] {prod.descripcion_real} "
            f"x{int(prod.cantidad)} ${prod.precio_unitario:,.0f} ({disp})"
        )
    for bico in match_result.bicomponentes_inyectados:
        if bico.codigo_encontrado:
            lines.append(f"  [AUTO] {bico.tipo}: {bico.descripcion_real} x{int(bico.cantidad_sugerida)}")
    if notas:
        lines.extend(["", f"Notas: {notas}"])
    lines.append("\nSe adjunta Excel con detalle completo.")
    return "\n".join(lines)


# ============================================================================
# RESULTADO DE NOTIFICACIÓN
# ============================================================================

@dataclass
class ResultadoNotificacion:
    email_enviado: bool = False
    email_destino: str = ""
    email_cc: list[str] = None
    dropbox_subido: bool = False
    dropbox_path: str = ""
    excel_filename: str = ""
    errores: list[str] = None

    def __post_init__(self):
        if self.email_cc is None:
            self.email_cc = []
        if self.errores is None:
            self.errores = []

    def to_dict(self) -> dict:
        return {
            "email_enviado": self.email_enviado,
            "email_destino": self.email_destino,
            "email_cc": self.email_cc,
            "dropbox_subido": self.dropbox_subido,
            "dropbox_path": self.dropbox_path,
            "excel_filename": self.excel_filename,
            "errores": self.errores,
        }


# ============================================================================
# FUNCIONES DE NOTIFICACIÓN
# ============================================================================

def notificar_pedido(
    match_result: ResultadoMatchPedido,
    excel_bytes: bytes,
    excel_filename: str,
    cliente_nombre: str = "",
    notas: str = "",
    send_email_fn: Optional[Callable] = None,
    upload_dropbox_fn: Optional[Callable] = None,
    dropbox_folder: str = "/data/pedidos",
) -> ResultadoNotificacion:
    """
    Envía email a tienda + sube Excel a Dropbox.

    Parámetros:
        match_result: Resultado del matching
        excel_bytes: Bytes del Excel generado
        excel_filename: Nombre del archivo
        cliente_nombre: Nombre del cliente
        notas: Notas adicionales
        send_email_fn: Función inyectada para enviar email
            Firma: send_email_fn(to, subject, html, text, cc_emails, attachments)
        upload_dropbox_fn: Función inyectada para subir a Dropbox
            Firma: upload_dropbox_fn(bytes, path) -> path_display
        dropbox_folder: Carpeta destino en Dropbox
    """
    resultado = ResultadoNotificacion(excel_filename=excel_filename)

    # ── Subir a Dropbox ──
    if upload_dropbox_fn and excel_bytes:
        try:
            dropbox_path = f"{dropbox_folder.rstrip('/')}/{excel_filename}"
            path_display = upload_dropbox_fn(excel_bytes, dropbox_path)
            resultado.dropbox_subido = True
            resultado.dropbox_path = path_display or dropbox_path
            logger.info("Excel subido a Dropbox: %s", resultado.dropbox_path)
        except Exception as exc:
            resultado.errores.append(f"Dropbox: {exc}")
            logger.error("Error subiendo a Dropbox: %s", exc)

    # ── Enviar email ──
    tienda_code = match_result.tienda_codigo
    to_email = _tienda_emails().get(tienda_code)

    if send_email_fn and to_email and excel_bytes:
        try:
            html = _build_order_email_html(match_result, cliente_nombre, notas)
            text = _build_order_email_text(match_result, cliente_nombre, notas)
            subject = (
                f"Pedido WhatsApp | {cliente_nombre or 'Cliente'} | "
                f"{match_result.tienda_nombre or tienda_code}"
            )

            attachment = {
                "content": base64.b64encode(excel_bytes).decode("ascii"),
                "filename": excel_filename,
                "type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "disposition": "attachment",
            }

            send_email_fn(
                to_email,
                subject,
                html,
                text,
                cc_emails=list(_cc_compras()),
                attachments=[attachment],
            )

            resultado.email_enviado = True
            resultado.email_destino = to_email
            resultado.email_cc = list(_cc_compras())
            logger.info("Email enviado a %s (CC: %s)", to_email, _cc_compras())

        except Exception as exc:
            resultado.errores.append(f"Email: {exc}")
            logger.error("Error enviando email: %s", exc)
    elif not to_email:
        resultado.errores.append(
            f"No hay email configurado para tienda {tienda_code}"
        )

    return resultado
