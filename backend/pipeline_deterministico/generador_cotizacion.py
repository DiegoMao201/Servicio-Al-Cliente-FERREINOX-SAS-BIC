"""
Módulo 3: Generador de Cotización Determinístico — SIN LLM

Este módulo genera la cotización/respuesta final usando SOLO datos del backend.
El LLM NO participa en:
  - Selección de precios
  - Selección de SKUs
  - Formato de la cotización
  - Cálculos financieros

Todo se genera por templates determinísticos.
"""
import json
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger("pipeline.generador_cotizacion")

# ══════════════════════════════════════════════════════════════════════════════
# CONSTANTES
# ══════════════════════════════════════════════════════════════════════════════

IVA_RATE = 0.19  # 19% Colombia
MARCAS_IVA_INCLUIDO = {"international"}  # Marcas donde precio YA incluye IVA

FUNCION_EMOJI = {
    "preparacion": "🔧",
    "imprimante": "🛡️",
    "sellador": "🛡️",
    "base": "🎨",
    "acabado": "✨",
    "catalizador": "⚗️",
    "diluyente": "🧪",
    "herramienta": "🔨",
}

FUNCION_LABEL = {
    "preparacion": "Preparación",
    "imprimante": "Imprimante",
    "sellador": "Sellador",
    "base": "Base / Fondo",
    "acabado": "Acabado",
    "catalizador": "Catalizador",
    "diluyente": "Diluyente",
    "herramienta": "Herramienta",
}


# ══════════════════════════════════════════════════════════════════════════════
# GENERADOR DE RESPUESTA WHATSAPP (TEXTO)
# ══════════════════════════════════════════════════════════════════════════════

def generar_respuesta_cotizacion_whatsapp(
    match_result: dict,
    diagnostico: dict,
    justificacion: str,
    nombre_cliente: str = "",
) -> str:
    """
    Genera el texto de cotización para WhatsApp usando SOLO datos del backend.

    Args:
        match_result: Output de matcher_productos.match_sistema_completo()
        diagnostico: Diagnóstico del LLM (superficie, ubicación, condición)
        justificacion: Justificación técnica del LLM
        nombre_cliente: Nombre del cliente si se conoce

    Returns:
        str con el mensaje formateado para WhatsApp
    """
    if not match_result.get("exito"):
        return _generar_respuesta_error(match_result, diagnostico)

    productos = match_result.get("productos_resueltos", [])
    herramientas = match_result.get("herramientas_resueltas", [])
    productos_fallidos = match_result.get("productos_fallidos", [])

    lines = []

    # ── Saludo ──
    if nombre_cliente:
        lines.append(f"¡Perfecto, {nombre_cliente}! Aquí tienes tu cotización: 📋\n")
    else:
        lines.append("¡Aquí tienes tu cotización! 📋\n")

    # ── Justificación técnica breve ──
    if justificacion:
        lines.append(f"💡 *{justificacion}*\n")

    # ── Sistema de productos ──
    lines.append("═══ *SISTEMA RECOMENDADO* ═══\n")

    subtotal_productos = 0.0
    subtotal_iva_incluido = 0.0

    for i, prod in enumerate(productos, 1):
        emoji = FUNCION_EMOJI.get(prod.get("funcion", ""), "▪️")
        funcion_label = FUNCION_LABEL.get(prod.get("funcion", ""), "")
        precio = float(prod.get("precio_unitario", 0))
        cantidad = int(prod.get("cantidad", 1))
        subtotal_linea = precio * cantidad
        marca = (prod.get("marca") or "").lower()

        disp = "✅" if prod.get("disponible") else "⚠️ Verificar"

        lines.append(
            f"{emoji} *Paso {i} — {funcion_label}*\n"
            f"   📦 {prod['descripcion_real']}\n"
            f"   Ref: {prod['codigo']} | Marca: {prod.get('marca', 'N/A')}\n"
            f"   Presentación: {prod.get('presentacion_real', 'N/A')}\n"
            f"   Cantidad: {cantidad} | Precio unit: ${precio:,.0f}\n"
            f"   Subtotal línea: ${subtotal_linea:,.0f} {disp}\n"
        )

        if marca in MARCAS_IVA_INCLUIDO:
            subtotal_iva_incluido += subtotal_linea
        else:
            subtotal_productos += subtotal_linea

    # ── Herramientas ──
    subtotal_herramientas = 0.0
    if herramientas:
        lines.append("═══ *HERRAMIENTAS* ═══\n")
        for h in herramientas:
            precio = float(h.get("precio_unitario", 0))
            cantidad = int(h.get("cantidad", 1))
            sub = precio * cantidad
            marca = (h.get("marca") or "").lower()
            disp = "✅" if h.get("disponible") else "⚠️"
            lines.append(
                f"🔨 {h['descripcion_real']}\n"
                f"   Ref: {h['codigo']} | Cant: {cantidad} | ${precio:,.0f} c/u | Sub: ${sub:,.0f} {disp}\n"
            )
            if marca in MARCAS_IVA_INCLUIDO:
                subtotal_iva_incluido += sub
            else:
                subtotal_herramientas += sub

    # ── Productos no encontrados ──
    if productos_fallidos:
        lines.append("\n⚠️ *Productos pendientes de verificación:*")
        for pf in productos_fallidos:
            lines.append(f"   • {pf['producto_solicitado']} — {pf.get('error', 'sin match')}")
        lines.append("   _Te confirmo disponibilidad con nuestro equipo._\n")

    # ── Resumen financiero (DETERMINÍSTICO — sin LLM) ──
    subtotal_antes_iva = subtotal_productos + subtotal_herramientas
    iva = subtotal_antes_iva * IVA_RATE
    total = subtotal_antes_iva + iva + subtotal_iva_incluido

    lines.append("═══ *RESUMEN FINANCIERO* ═══")
    if subtotal_antes_iva > 0:
        lines.append(f"   Subtotal (antes IVA): ${subtotal_antes_iva:,.0f}")
        lines.append(f"   IVA 19%: ${iva:,.0f}")
    if subtotal_iva_incluido > 0:
        lines.append(f"   Productos IVA incluido: ${subtotal_iva_incluido:,.0f}")
    lines.append(f"   💰 *TOTAL A PAGAR: ${total:,.0f}*\n")

    # ── Cierre ──
    lines.append(
        "¿Deseas que te genere la cotización en PDF o proceder con el pedido? 📄"
    )

    return "\n".join(lines)


def _generar_respuesta_error(match_result: dict, diagnostico: dict) -> str:
    """Genera respuesta de error cuando el match falla."""
    fallidos = match_result.get("productos_fallidos", [])
    razon = match_result.get("razon_fallo", "Productos críticos no encontrados")

    lines = [
        "⚠️ No puedo generar la cotización completa en este momento.\n",
        f"*Razón:* {razon}\n",
    ]

    if fallidos:
        lines.append("*Productos sin match en inventario:*")
        for pf in fallidos:
            lines.append(f"   • {pf['producto_solicitado']}")
            if pf.get("candidatos_cercanos"):
                lines.append("     Candidatos cercanos:")
                for c in pf["candidatos_cercanos"][:2]:
                    lines.append(f"       → {c['descripcion']} (score: {c['score']})")

    resueltos = match_result.get("productos_resueltos", [])
    if resueltos:
        lines.append(f"\n✅ {len(resueltos)} productos SÍ encontrados.")

    lines.append(
        "\nTe conecto con nuestro Asesor Técnico Comercial para completar "
        "la cotización. ¿Te parece?"
    )

    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════════════════
# GENERADOR DE DATOS PARA PDF (DETERMINÍSTICO)
# ══════════════════════════════════════════════════════════════════════════════

def generar_payload_pdf(
    match_result: dict,
    diagnostico: dict,
    justificacion: str,
    nombre_despacho: str,
    cedula_nit: str = "",
    tipo_documento: str = "cotizacion",
    conversation_id: str = "",
) -> dict:
    """
    Genera el payload para el PDF generator existente (pdf_generator.py).
    NO usa LLM — solo datos del backend.

    Returns:
        dict compatible con generate_commercial_pdf_v2()
    """
    items = []
    for prod in match_result.get("productos_resueltos", []):
        items.append({
            "status": "matched",
            "referencia": prod["codigo"],
            "matched_product": {
                "codigo_articulo": prod["codigo"],
                "descripcion": prod["descripcion_real"],
                "marca": prod.get("marca", ""),
                "presentacion": prod.get("presentacion_real", ""),
                "precio_venta": prod["precio_unitario"],
            },
            "cantidad": prod["cantidad"],
            "product_request": {
                "producto_solicitado": prod["producto_solicitado"],
                "funcion": prod.get("funcion", ""),
            },
        })

    for herr in match_result.get("herramientas_resueltas", []):
        items.append({
            "status": "matched",
            "referencia": herr["codigo"],
            "matched_product": {
                "codigo_articulo": herr["codigo"],
                "descripcion": herr["descripcion_real"],
                "marca": herr.get("marca", ""),
                "presentacion": herr.get("presentacion_real", ""),
                "precio_venta": herr["precio_unitario"],
            },
            "cantidad": herr["cantidad"],
            "product_request": {
                "producto_solicitado": herr["producto_solicitado"],
                "funcion": "herramienta",
            },
        })

    return {
        "items": items,
        "customer_context": {
            "nombre_despacho": nombre_despacho,
            "cedula_nit": cedula_nit,
        },
        "nombre_despacho": nombre_despacho,
        "resumen_asesoria": justificacion,
        "diagnostico": diagnostico,
        "tipo_documento": tipo_documento,
        "conversation_id": conversation_id,
        "generado_por": "pipeline_deterministico",
        "timestamp": datetime.now().isoformat(),
    }


# ══════════════════════════════════════════════════════════════════════════════
# UTILIDADES DE FORMATO
# ══════════════════════════════════════════════════════════════════════════════

def formatear_producto_whatsapp(prod: dict, numero: int) -> str:
    """Formatea un producto individual para WhatsApp."""
    emoji = FUNCION_EMOJI.get(prod.get("funcion", ""), "▪️")
    precio = float(prod.get("precio_unitario", 0))
    cantidad = int(prod.get("cantidad", 1))
    subtotal = precio * cantidad
    disp = "✅" if prod.get("disponible") else "⚠️"

    return (
        f"{emoji} *{numero}. {prod['descripcion_real']}*\n"
        f"   Ref: {prod['codigo']} | {cantidad} × ${precio:,.0f} = ${subtotal:,.0f} {disp}"
    )
