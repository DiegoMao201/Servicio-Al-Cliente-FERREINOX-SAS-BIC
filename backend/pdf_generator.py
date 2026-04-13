# -*- coding: utf-8 -*-
"""
PDF Generator for CRM Ferreinox Agent.

Standalone module that generates professional commercial PDFs (Pedidos/Cotizaciones)
using FPDF2, replicating the visual style of the Cotizador Ferreinox app.

Usage from main.py:
    from pdf_generator import generate_commercial_pdf_v2
    buffer = generate_commercial_pdf_v2(conversation_id, request_type, ...)
"""

from __future__ import annotations

import io
import os
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from fpdf import FPDF


# ---------------------------------------------------------------------------
# Theme (matches Cotizador Ferreinox exactly)
# ---------------------------------------------------------------------------

class Theme:
    PRIMARY      = (12, 39, 84)       # #0C2754  dark-blue header
    PRIMARY_DARK = (8, 25, 55)        # #081937  financial summary bg
    SECONDARY    = (34, 74, 122)      # #224A7A  accent cards
    ACCENT       = (201, 92, 43)      # #C95C2B  orange bar
    TEXT_MAIN    = (34, 38, 43)       # #22262B  body text
    TEXT_MUTED   = (103, 111, 121)    # #676F79  labels / captions
    BORDER       = (223, 228, 235)    # #DFE4EB  lines / borders
    PANEL        = (246, 248, 251)    # #F6F8FB  light card bg
    TABLE_ALT    = (250, 251, 253)    # #FAFBFD  alt row bg
    WHITE        = (255, 255, 255)
    GREEN_BG     = (236, 253, 245)    # #ECFDF5  justification box
    GREEN_BD     = (16, 185, 129)     # #10B981
    BLUE_BG      = (239, 246, 255)    # #EFF6FF  system box
    BLUE_BD      = (96, 165, 250)     # #60A5FA


# ---------------------------------------------------------------------------
# Corporate constants
# ---------------------------------------------------------------------------

CORPORATE = {
    "company_name": "FERREINOX S.A.S. BIC",
    "nit": "800.224.617-8",
    "address": "CR 13 19-26, Pereira, Risaralda, Colombia",
    "website": "www.ferreinox.co",
    "service_email": "hola@ferreinox.co",
    "phone": "(606) 333 0101",
}

# Logo: resolve relative to this file's parent (backend/) → project root
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOGO_PATH = _PROJECT_ROOT / "LOGO FERREINOX SAS BIC 2024.png"


# ---------------------------------------------------------------------------
# Text helpers (ASCII-safe for FPDF core fonts)
# ---------------------------------------------------------------------------

_REPLACEMENTS = {
    "\u201c": '"', "\u201d": '"', "\u2018": "'", "\u2019": "'",
    "\u2013": "-", "\u2014": "-", "\u2026": "...",
    "\u2022": "-", "\u00b4": "'", "\u00ab": '"', "\u00bb": '"',
    "\u00b0": "o",
    "\u00e1": "a", "\u00e9": "e", "\u00ed": "i", "\u00f3": "o", "\u00fa": "u",
    "\u00c1": "A", "\u00c9": "E", "\u00cd": "I", "\u00d3": "O", "\u00da": "U",
    "\u00f1": "n", "\u00d1": "N",
}


def _safe(text: Any) -> str:
    """Convert to ASCII-safe string for FPDF core fonts."""
    s = str(text) if text is not None else ""
    for k, v in _REPLACEMENTS.items():
        s = s.replace(k, v)
    return s.encode("ascii", "ignore").decode("ascii")


def _truncate(text: str, max_chars: int) -> str:
    s = _safe(text)
    return s if len(s) <= max_chars else s[: max_chars - 3].rstrip() + "..."


def _wrap(pdf: FPDF, text: str, width_mm: float) -> List[str]:
    """Word-wrap text to fit within width_mm using current font metrics."""
    cleaned = _safe(text)
    if not cleaned:
        return [""]
    words = cleaned.split()
    if not words:
        return [cleaned]
    lines: List[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        if pdf.get_string_width(candidate) <= width_mm:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def _fmt_money(value: float) -> str:
    """Format number as Colombian pesos: $1.234.567"""
    return f"${value:,.0f}".replace(",", ".")


# ---------------------------------------------------------------------------
# Main PDF class
# ---------------------------------------------------------------------------

class _CommercialPDF(FPDF):
    """FPDF subclass with custom footer."""

    def __init__(self, ref_label: str, request_label: str):
        super().__init__()
        self._ref_label = ref_label
        self._request_label = request_label

    def footer(self):
        self.set_y(-12)
        self.set_draw_color(*Theme.BORDER)
        self.set_line_width(0.2)
        self.line(10, self.get_y(), 200, self.get_y())
        self.set_y(-10)
        self.set_font("Arial", "", 7)
        self.set_text_color(*Theme.TEXT_MUTED)
        self.cell(
            0, 4,
            f"Ferreinox SAS BIC | {CORPORATE['website']} | {self._request_label} {self._ref_label} | Pagina {self.page_no()}",
            0, 0, "C",
        )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_commercial_pdf_v2(
    conversation_id: int,
    request_type: str,
    profile_name: Optional[str],
    cliente_contexto: Optional[dict],
    detail: dict,
    *,
    price_resolver: Optional[Callable[[str], dict]] = None,
    store_labels: Optional[dict] = None,
) -> io.BytesIO:
    """
    Generate a professional commercial PDF replicating the Cotizador style.

    Parameters
    ----------
    conversation_id : int
        CRM conversation / order ID.
    request_type : str
        "pedido" or "cotizacion".
    profile_name : str | None
        WhatsApp profile name (fallback for client name).
    cliente_contexto : dict | None
        Customer data from DB.
    detail : dict
        Commercial draft with items, customer_context, metadata, etc.
    price_resolver : callable | None
        func(reference) -> {"unit_price": float, "price_includes_iva": bool}
    store_labels : dict | None
        Store code -> label mapping.

    Returns
    -------
    io.BytesIO with PDF bytes, seeked to 0.
    """
    items_all = detail.get("items") or []
    matched_items = [i for i in items_all if i.get("status") == "matched"]
    store_labels = store_labels or {}

    request_label = "Pedido" if request_type == "pedido" else "Cotizacion"
    case_ref = f"CRM-{conversation_id}"
    now = datetime.now()
    fecha_str = now.strftime("%d/%m/%Y %H:%M")

    # --- Customer data ---
    cc = dict(detail.get("customer_context") or cliente_contexto or {})
    cliente_nombre = cc.get("nombre_cliente") or profile_name or "Cliente Ferreinox"
    cliente_nit = cc.get("nit") or cc.get("documento") or ""
    cliente_email = cc.get("email") or ""
    cliente_telefono = cc.get("telefono") or cc.get("celular") or ""
    cliente_codigo = cc.get("cliente_codigo") or ""

    # Store
    store_filters = detail.get("store_filters") or []
    if len(store_filters) == 1:
        tienda = store_labels.get(store_filters[0], store_filters[0])
    elif store_filters:
        tienda = ", ".join(store_labels.get(c, c) for c in store_filters)
    else:
        tienda = "Por definir"

    delivery_channel = (detail.get("delivery_channel") or "chat").title()
    dispatch_name = detail.get("nombre_despacho") or cliente_nombre
    observations = detail.get("facturador_notes") or detail.get("observaciones") or ""
    justificacion = (detail.get("justificacion_comercial_pdf") or "").strip()
    sistema_completo = detail.get("sistema_completo_pdf") or []
    componentes_pendientes = detail.get("componentes_pendientes_pdf") or []
    herramientas_sugeridas = detail.get("herramientas_sugeridas_pdf") or []
    nota_color = (detail.get("nota_color_pdf") or "").strip()
    resumen_asesoria = (detail.get("resumen_asesoria") or "").strip()

    # ======================================================================
    # Build PDF
    # ======================================================================
    pdf = _CommercialPDF(ref_label=case_ref, request_label=request_label)
    pdf.set_margins(10, 10, 10)
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()

    # ------------------------------------------------------------------
    # HEADER BAND (dark-blue + orange accent)
    # ------------------------------------------------------------------
    pdf.set_fill_color(*Theme.PRIMARY)
    pdf.rect(0, 0, 210, 34, "F")
    pdf.set_fill_color(*Theme.ACCENT)
    pdf.rect(0, 34, 210, 2.5, "F")

    # Logo
    if LOGO_PATH.exists():
        try:
            pdf.image(str(LOGO_PATH), x=10, y=8, w=48)
        except Exception:
            pass

    # Title
    pdf.set_xy(95, 8)
    pdf.set_font("Arial", "B", 21)
    pdf.set_text_color(*Theme.WHITE)
    title_text = "PEDIDO COMERCIAL" if request_type == "pedido" else "COTIZACION COMERCIAL"
    pdf.cell(105, 8, _safe(title_text), 0, 1, "R")
    pdf.set_x(95)
    pdf.set_font("Arial", "", 9)
    pdf.cell(105, 5, _safe(f"Ref. {case_ref}"), 0, 1, "R")
    pdf.set_x(95)
    pdf.cell(105, 5, _safe(f"Emitida {fecha_str}"), 0, 1, "R")
    pdf.set_x(95)
    pdf.cell(105, 5, CORPORATE["website"], 0, 1, "R")

    # Subtitle line
    pdf.set_xy(10, 42)
    pdf.set_font("Arial", "B", 12)
    pdf.set_text_color(*Theme.PRIMARY_DARK)
    subtitle = "Solicitud preparada para su proceso comercial"
    pdf.cell(0, 6, _safe(subtitle), 0, 1)
    pdf.set_font("Arial", "", 9)
    pdf.set_text_color(*Theme.TEXT_MUTED)
    pdf.multi_cell(
        190, 5,
        _safe(
            "Documento generado por el CRM Ferreinox con detalle tecnico, "
            "condiciones comerciales y resumen financiero."
        ),
    )

    # ------------------------------------------------------------------
    # INFO CARDS (Cliente + Gestion Comercial)
    # ------------------------------------------------------------------
    card_y = 56

    def _draw_info_card(x: float, y: float, w: float, title: str, rows: list, h: float = 47):
        pdf.set_fill_color(*Theme.PANEL)
        pdf.set_draw_color(*Theme.BORDER)
        pdf.rect(x, y, w, h, "FD")
        pdf.set_fill_color(*Theme.PRIMARY)
        pdf.rect(x, y, w, 8, "F")
        pdf.set_xy(x + 3, y + 1.5)
        pdf.set_font("Arial", "B", 9)
        pdf.set_text_color(*Theme.WHITE)
        pdf.cell(w - 6, 4, _safe(title), 0, 1)
        cy = y + 11
        for label, value in rows:
            if cy > y + h - 8:
                break
            pdf.set_xy(x + 3, cy)
            pdf.set_font("Arial", "B", 7)
            pdf.set_text_color(*Theme.TEXT_MUTED)
            pdf.cell(w - 6, 3.2, _safe(label.upper()), 0, 1)
            pdf.set_x(x + 3)
            pdf.set_font("Arial", "", 9)
            pdf.set_text_color(*Theme.TEXT_MAIN)
            pdf.cell(w - 6, 4.2, _truncate(value or "-", 50), 0, 1)
            cy += 7.1

    _draw_info_card(10, card_y, 92, "Cliente", [
        ("Cliente", cliente_nombre),
        ("NIT / C.C.", cliente_nit or "No registrado"),
        ("Correo", cliente_email or "No registrado"),
        ("Telefono", cliente_telefono or "No registrado"),
        ("Cod. Cliente", cliente_codigo or "No registrado"),
    ])
    _draw_info_card(108, card_y, 92, "Gestion Comercial", [
        ("Solicita", dispatch_name),
        ("Tienda / Ciudad", tienda),
        ("Canal", delivery_channel),
        ("Fecha de emision", now.strftime("%d/%m/%Y")),
        ("Vigencia", "15 dias habiles"),
    ])

    # ------------------------------------------------------------------
    # Compute pricing for summary cards (need totals first)
    # ------------------------------------------------------------------
    line_items: List[Dict[str, Any]] = []
    grand_subtotal = 0.0
    subtotal_iva_inc = 0.0

    for item in matched_items:
        mp = item.get("matched_product") or {}
        desc = (
            _get_description(mp)
            or item.get("descripcion_comercial")
            or item.get("original_text")
            or "Producto"
        )
        ref_code = (
            mp.get("referencia")
            or mp.get("codigo_articulo")
            or item.get("referencia")
            or item.get("codigo_articulo")
            or "-"
        )
        req = item.get("product_request") or {}
        qty_val = req.get("requested_quantity") or item.get("cantidad")
        qty_unit = req.get("requested_unit") or item.get("unidad_medida")
        qty_num = float(qty_val) if qty_val else 0

        if qty_val and qty_unit:
            qty_label = f"{_fmt_qty(qty_val)} {qty_unit}"
        elif qty_val:
            qty_label = _fmt_qty(qty_val)
        else:
            qty_label = "Por confirmar"

        # Price lookup
        price_info = price_resolver(str(ref_code)) if price_resolver else {}
        unit_price = float(price_info.get("unit_price") or 0)
        includes_iva = price_info.get("price_includes_iva", False)
        line_sub = unit_price * qty_num
        if includes_iva:
            subtotal_iva_inc += line_sub
        else:
            grand_subtotal += line_sub

        auto_note = item.get("auto_note") or ""

        line_items.append({
            "desc": desc,
            "ref": ref_code,
            "qty_label": qty_label,
            "unit_price": unit_price,
            "line_sub": line_sub,
            "auto_note": auto_note,
        })

    total_items = len(matched_items)
    total_unidades = int(sum(
        float((i.get("product_request") or {}).get("requested_quantity") or i.get("cantidad") or 0)
        for i in matched_items
    ))
    iva_amount = round(grand_subtotal * 0.19)
    grand_total = round(grand_subtotal + iva_amount + subtotal_iva_inc)

    # ------------------------------------------------------------------
    # SUMMARY CARDS
    # ------------------------------------------------------------------
    summary_y = 110

    def _draw_summary_card(x, y, w, title, value, accent=False):
        fill = Theme.SECONDARY if accent else Theme.WHITE
        bd = Theme.SECONDARY if accent else Theme.BORDER
        tc_title = Theme.WHITE if accent else Theme.TEXT_MUTED
        tc_val = Theme.WHITE if accent else Theme.PRIMARY
        pdf.set_fill_color(*fill)
        pdf.set_draw_color(*bd)
        pdf.rect(x, y, w, 16, "FD")
        pdf.set_xy(x + 3, y + 2.5)
        pdf.set_font("Arial", "B", 7)
        pdf.set_text_color(*tc_title)
        pdf.cell(w - 6, 3.2, _safe(title.upper()), 0, 1)
        pdf.set_x(x + 3)
        pdf.set_font("Arial", "B", 11)
        pdf.set_text_color(*tc_val)
        pdf.cell(w - 6, 5.5, _safe(value), 0, 1)

    _draw_summary_card(10, summary_y, 44, "Items", str(total_items))
    _draw_summary_card(58, summary_y, 44, "Unidades", f"{total_unidades:,}")
    _draw_summary_card(106, summary_y, 44, "Subtotal", _fmt_money(grand_subtotal))
    _draw_summary_card(154, summary_y, 46, "Total", _fmt_money(grand_total), accent=True)

    # ------------------------------------------------------------------
    # RESUMEN ASESORIA / PEDIDO DEL CLIENTE
    # ------------------------------------------------------------------
    pdf.set_xy(10, 132)
    if resumen_asesoria:
        pdf.set_font("Arial", "B", 11)
        pdf.set_text_color(*Theme.PRIMARY_DARK)
        section_title = "Pedido del Cliente" if request_type in {"pedido", "cotizacion"} else "Resumen de la Asesoria"
        pdf.cell(0, 6, _safe(section_title), 0, 1)
        _draw_separator(pdf)
        lines = [l.strip(" -*\t") for l in resumen_asesoria.splitlines() if l.strip()]
        pdf.set_font("Arial", "", 8.5)
        pdf.set_text_color(*Theme.TEXT_MAIN)
        for line in lines:
            _ensure_space(pdf, 6)
            pdf.cell(0, 4.8, _safe(f"  - {line}"), 0, 1)
        pdf.ln(3)

    # ------------------------------------------------------------------
    # JUSTIFICACION COMERCIAL (green box)
    # ------------------------------------------------------------------
    if justificacion:
        _ensure_space(pdf, 25)
        pdf.set_font("Arial", "B", 11)
        pdf.set_text_color(*Theme.PRIMARY_DARK)
        pdf.cell(0, 6, _safe("Por Que Este Sistema"), 0, 1)
        _draw_separator(pdf)
        _draw_colored_box(pdf, justificacion, Theme.GREEN_BG, Theme.GREEN_BD)
        pdf.ln(3)

    # ------------------------------------------------------------------
    # SISTEMA COMPLETO (blue box)
    # ------------------------------------------------------------------
    has_system = sistema_completo or componentes_pendientes or herramientas_sugeridas or nota_color
    if has_system:
        _ensure_space(pdf, 25)
        pdf.set_font("Arial", "B", 11)
        pdf.set_text_color(*Theme.PRIMARY_DARK)
        pdf.cell(0, 6, _safe("Sistema Completo y Cierre"), 0, 1)
        _draw_separator(pdf)
        checklist: List[str] = []
        checklist.extend(f"  - {s}" for s in sistema_completo if s)
        checklist.extend(f"  - Pendiente: {s}" for s in componentes_pendientes if s)
        checklist.extend(f"  - Herramienta sugerida: {s}" for s in herramientas_sugeridas if s)
        if nota_color:
            checklist.append(f"  - {nota_color}")
        _draw_colored_box(pdf, "\n".join(checklist), Theme.BLUE_BG, Theme.BLUE_BD)
        pdf.ln(3)

    # ------------------------------------------------------------------
    # PRODUCT TABLE
    # ------------------------------------------------------------------
    _ensure_space(pdf, 30)
    pdf.set_font("Arial", "B", 11)
    pdf.set_text_color(*Theme.PRIMARY_DARK)
    pdf.cell(0, 6, _safe(f"Detalle de productos ({request_label.lower()})"), 0, 1)
    pdf.set_font("Arial", "", 8.5)
    pdf.set_text_color(*Theme.TEXT_MUTED)
    pdf.cell(0, 5, _safe("Valores expresados en pesos colombianos. Precios sujetos a disponibilidad."), 0, 1)
    pdf.ln(1.5)

    _draw_table_header(pdf)

    for idx, li in enumerate(line_items):
        desc_lines = _wrap(pdf, li["desc"], 70)[:3]
        if li["auto_note"]:
            # Add auto_note as a small gray sub-line
            desc_lines.append("")  # placeholder processed below
        row_height = max(8, len(desc_lines) * 4.6 + 2)

        _ensure_space(pdf, row_height + 2, header_fn=lambda: _draw_table_header(pdf))
        row_y = pdf.get_y()

        # Alternating row background
        if idx % 2 == 1:
            pdf.set_fill_color(*Theme.TABLE_ALT)
            pdf.rect(10, row_y, 190, row_height, "F")

        # Vertical grid lines
        pdf.set_draw_color(*Theme.BORDER)
        pdf.set_line_width(0.15)
        col_xs = [10, 32, 106, 122, 148, 200]
        for x in col_xs:
            pdf.line(x, row_y, x, row_y + row_height)
        pdf.line(10, row_y + row_height, 200, row_y + row_height)

        # Reference
        pdf.set_xy(11, row_y + 2)
        pdf.set_font("Arial", "B", 8)
        pdf.set_text_color(*Theme.TEXT_MAIN)
        pdf.cell(20, row_height - 2, _truncate(li["ref"], 18), 0, 0, "C")

        # Description (multi-line)
        pdf.set_xy(33, row_y + 2)
        pdf.set_font("Arial", "", 8.2)
        main_lines = _wrap(pdf, li["desc"], 70)[:3]
        pdf.multi_cell(72, 4.6, _safe("\n".join(main_lines)), 0, "L")
        if li["auto_note"]:
            note_y = pdf.get_y()
            if note_y < row_y + row_height - 4:
                pdf.set_xy(33, note_y)
                pdf.set_font("Arial", "I", 7)
                pdf.set_text_color(*Theme.TEXT_MUTED)
                pdf.cell(72, 3.5, _truncate(li["auto_note"], 60), 0, 0, "L")
                pdf.set_text_color(*Theme.TEXT_MAIN)

        # Quantity
        pdf.set_xy(106, row_y + 2)
        pdf.set_font("Arial", "", 8)
        pdf.set_text_color(*Theme.TEXT_MAIN)
        pdf.cell(16, row_height - 2, _safe(li["qty_label"]), 0, 0, "C")

        # Unit price
        pdf.set_xy(122, row_y + 2)
        price_lbl = _fmt_money(li["unit_price"]) if li["unit_price"] > 0 else "Pendiente"
        pdf.cell(26, row_height - 2, _safe(price_lbl), 0, 0, "R")

        # Subtotal
        pdf.set_xy(148, row_y + 2)
        pdf.set_font("Arial", "B", 8.2)
        sub_lbl = _fmt_money(li["line_sub"]) if li["line_sub"] > 0 else "-"
        pdf.cell(51, row_height - 2, _safe(sub_lbl), 0, 0, "R")

        pdf.set_y(row_y + row_height)

    if not line_items:
        pdf.set_font("Arial", "I", 9)
        pdf.set_text_color(*Theme.TEXT_MUTED)
        pdf.cell(0, 8, _safe("No hay productos confirmados en este documento."), 0, 1, "C")

    pdf.ln(7)

    # ------------------------------------------------------------------
    # OBSERVATIONS + FINANCIAL SUMMARY (side-by-side)
    # ------------------------------------------------------------------
    _ensure_space(pdf, 56)
    block_y = pdf.get_y()

    # Left: Observations
    pdf.set_fill_color(*Theme.PANEL)
    pdf.set_draw_color(*Theme.BORDER)
    pdf.rect(10, block_y, 112, 46, "FD")
    pdf.set_fill_color(*Theme.PRIMARY)
    pdf.rect(10, block_y, 112, 8, "F")
    pdf.set_xy(13, block_y + 1.6)
    pdf.set_font("Arial", "B", 9)
    pdf.set_text_color(*Theme.WHITE)
    pdf.cell(100, 4, "OBSERVACIONES Y CONDICIONES COMERCIALES", 0, 1)
    pdf.set_xy(13, block_y + 11)
    pdf.set_font("Arial", "", 8.5)
    pdf.set_text_color(*Theme.TEXT_MAIN)
    obs_text = str(observations).strip() if observations else (
        "Forma de pago sujeta a negociacion final. Disponibilidad y tiempos de entrega "
        "segun validacion de inventario al momento del cierre."
    )
    pdf.multi_cell(106, 4.8, _safe(obs_text))

    # Right: Financial summary
    pdf.set_fill_color(*Theme.PRIMARY_DARK)
    pdf.rect(128, block_y, 72, 46, "F")
    pdf.set_xy(132, block_y + 3)
    pdf.set_font("Arial", "B", 10)
    pdf.set_text_color(*Theme.WHITE)
    pdf.cell(64, 5, "RESUMEN FINANCIERO", 0, 1)

    def _fin_row(label, value, y, bold=False):
        pdf.set_xy(132, y)
        pdf.set_font("Arial", "B" if bold else "", 9.3)
        pdf.set_text_color(*Theme.WHITE)
        pdf.cell(32, 5, _safe(label), 0, 0, "L")
        pdf.cell(32, 5, _safe(value), 0, 1, "R")

    _fin_row("Subtotal", _fmt_money(grand_subtotal), block_y + 12)
    _fin_row("IVA 19%", _fmt_money(iva_amount), block_y + 18)
    if subtotal_iva_inc > 0:
        _fin_row("IVA incluido", _fmt_money(subtotal_iva_inc), block_y + 24)
    pdf.set_draw_color(255, 255, 255)
    pdf.line(132, block_y + 31, 196, block_y + 31)
    _fin_row("TOTAL", _fmt_money(grand_total), block_y + 34, bold=True)

    # ------------------------------------------------------------------
    # CLOSING
    # ------------------------------------------------------------------
    pdf.set_xy(10, block_y + 52)
    pdf.set_font("Arial", "B", 10)
    pdf.set_text_color(*Theme.PRIMARY_DARK)
    pdf.cell(0, 5, "Cierre comercial", 0, 1)
    pdf.set_font("Arial", "", 8.5)
    pdf.set_text_color(*Theme.TEXT_MUTED)
    cierre = (
        f"Generado por el agente CRM Ferreinox. "
        f"Precios antes de IVA (19%). Precios sujetos a disponibilidad y cambio sin previo aviso. "
        f"No constituye factura y esta sujeto a validacion operativa por Ferreinox SAS BIC."
    )
    pdf.multi_cell(190, 4.8, _safe(cierre))
    pdf.ln(2)
    pdf.set_font("Arial", "", 7)
    pdf.set_text_color(*Theme.TEXT_MUTED)
    pdf.cell(
        0, 4,
        _safe(
            f"{CORPORATE['company_name']} | {CORPORATE['service_email']} | "
            f"{CORPORATE['phone']} | {CORPORATE['website']} | {now.strftime('%d/%m/%Y')}"
        ),
        0, 0, "C",
    )

    # ------------------------------------------------------------------
    # Output
    # ------------------------------------------------------------------
    raw = pdf.output(dest="S")
    buf = io.BytesIO()
    if isinstance(raw, str):
        buf.write(raw.encode("latin1"))
    else:
        buf.write(bytes(raw))
    buf.seek(0)
    return buf


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_description(product_row: dict) -> str:
    raw = product_row.get("descripcion") or product_row.get("nombre_articulo") or ""
    return re.sub(r"\s+", " ", str(raw).strip())


def _fmt_qty(value) -> str:
    try:
        n = float(value)
        return f"{int(n)}" if n == int(n) else f"{n:g}"
    except (TypeError, ValueError):
        return str(value)


def _draw_separator(pdf: FPDF):
    pdf.set_draw_color(*Theme.BORDER)
    pdf.set_line_width(0.4)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(2)


def _draw_colored_box(pdf: FPDF, text: str, bg_rgb: tuple, border_rgb: tuple):
    """Draw a rounded-ish colored box with multi-line text."""
    x = 10
    w = 190
    pdf.set_fill_color(*bg_rgb)
    pdf.set_draw_color(*border_rgb)
    pdf.set_line_width(0.5)

    lines = [l for l in _safe(text).splitlines() if l.strip()]
    box_h = max(12, len(lines) * 5 + 10)

    y = pdf.get_y()
    pdf.rect(x, y, w, box_h, "FD")
    pdf.set_xy(x + 6, y + 4)
    pdf.set_font("Arial", "", 8.5)
    pdf.set_text_color(*Theme.TEXT_MAIN)
    for line in lines:
        pdf.set_x(x + 6)
        pdf.cell(w - 12, 4.8, line, 0, 1)
    pdf.set_y(y + box_h)


def _draw_table_header(pdf: FPDF):
    pdf.set_fill_color(*Theme.PRIMARY)
    pdf.set_text_color(*Theme.WHITE)
    pdf.set_font("Arial", "B", 8)
    headers = [
        (10, 22, "REFERENCIA", "C"),
        (32, 74, "DESCRIPCION", "L"),
        (106, 16, "CANT.", "C"),
        (122, 26, "VR UNIT.", "R"),
        (148, 52, "TOTAL", "R"),
    ]
    hy = pdf.get_y()
    for x, w, label, align in headers:
        pdf.set_xy(x, hy)
        pdf.cell(w, 8, label, 0, 0, align, True)
    pdf.ln(8)


def _ensure_space(pdf: FPDF, height_needed: float, header_fn=None):
    if pdf.get_y() + height_needed > 270:
        pdf.add_page()
        pdf.set_y(18)
        if header_fn:
            header_fn()
