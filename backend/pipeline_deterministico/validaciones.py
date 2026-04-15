"""
Módulo 4: Validaciones Proactivas — Gate de calidad antes de cotizar

Los 5 Gates ya no bloquean en silencio. Retornan un ValidationFeedback
estructurado que el orquestador y el agente pueden usar para:
  - Generar mensajes correctivos empáticos al cliente
  - Sugerir productos faltantes (catalizadores)
  - Proponer alternativas compatibles

Si algún gate falla → NO se cotiza → pero se devuelve una sugerencia
de acción concreta, no un error genérico.
"""
import json
import logging
from typing import Optional

logger = logging.getLogger("pipeline.validaciones")


# ══════════════════════════════════════════════════════════════════════════════
# VALIDATION FEEDBACK — Respuesta estructurada de cada gate
# ══════════════════════════════════════════════════════════════════════════════

class ValidationFeedback:
    """
    Feedback proactivo de un gate de validación.
    
    status: "passed" | "blocked" | "warning"
    reason: Código máquina (ej. "missing_catalyst", "chemical_incompatibility")
    product_ref: Código del producto problemático (si aplica)
    suggested_message: Texto comercial empático para enviar al cliente por WhatsApp
    suggested_action: Acción que el agente debe tomar
    suggested_products: Productos a agregar/cambiar para resolver
    """
    def __init__(
        self,
        status: str,
        gate_name: str,
        reason: str = "",
        product_ref: str = "",
        suggested_message: str = "",
        suggested_action: str = "",
        suggested_products: list[dict] = None,
        details: str = "",
    ):
        self.status = status  # "passed", "blocked", "warning"
        self.gate_name = gate_name
        self.reason = reason
        self.product_ref = product_ref
        self.suggested_message = suggested_message
        self.suggested_action = suggested_action
        self.suggested_products = suggested_products or []
        self.details = details

    @property
    def is_blocked(self) -> bool:
        return self.status == "blocked"
    
    @property
    def is_warning(self) -> bool:
        return self.status == "warning"

    def to_dict(self) -> dict:
        d = {
            "status": self.status,
            "gate_name": self.gate_name,
            "reason": self.reason,
        }
        if self.product_ref:
            d["product_ref"] = self.product_ref
        if self.suggested_message:
            d["suggested_message"] = self.suggested_message
        if self.suggested_action:
            d["suggested_action"] = self.suggested_action
        if self.suggested_products:
            d["suggested_products"] = self.suggested_products
        if self.details:
            d["details"] = self.details
        return d


# ══════════════════════════════════════════════════════════════════════════════
# RESULTADO DE VALIDACIÓN (mantiene retrocompatibilidad + agrega feedbacks)
# ══════════════════════════════════════════════════════════════════════════════

class ResultadoValidacion:
    def __init__(self, valido: bool, errores: list[str] = None, advertencias: list[str] = None,
                 feedbacks: list[ValidationFeedback] = None):
        self.valido = valido
        self.errores = errores or []
        self.advertencias = advertencias or []
        self.feedbacks = feedbacks or []

    @property
    def blocking_feedbacks(self) -> list[ValidationFeedback]:
        return [f for f in self.feedbacks if f.is_blocked]

    @property
    def warning_feedbacks(self) -> list[ValidationFeedback]:
        return [f for f in self.feedbacks if f.is_warning]

    def to_dict(self) -> dict:
        return {
            "valido": self.valido,
            "errores": self.errores,
            "advertencias": self.advertencias,
            "feedbacks": [f.to_dict() for f in self.feedbacks],
        }


# ══════════════════════════════════════════════════════════════════════════════
# VALIDACIÓN 1: COHERENCIA DIAGNÓSTICO ↔ RECOMENDACIÓN
# ══════════════════════════════════════════════════════════════════════════════

def validar_coherencia_diagnostico(recomendacion: dict) -> ResultadoValidacion:
    """
    Verifica que la recomendación del LLM sea coherente con su propio diagnóstico.
    """
    errores = []
    advertencias = []
    feedbacks = []
    gate = "coherencia_diagnostico"
    
    diag = recomendacion.get("diagnostico", {})
    sistema = recomendacion.get("sistema", [])
    
    if not diag:
        errores.append("Sin diagnóstico — no se puede validar coherencia")
        feedbacks.append(ValidationFeedback(
            status="blocked", gate_name=gate, reason="missing_diagnosis",
            suggested_message="Necesito entender mejor tu situación. ¿Podrías describirme qué superficie vas a pintar y qué problema tiene?",
            suggested_action="ask_diagnosis",
        ))
        return ResultadoValidacion(False, errores, feedbacks=feedbacks)
    
    if not sistema:
        errores.append("Sin productos en el sistema — recomendación vacía")
        feedbacks.append(ValidationFeedback(
            status="blocked", gate_name=gate, reason="empty_system",
            suggested_message="No logré armar una recomendación con esa información. ¿Me cuentas más sobre lo que necesitas pintar?",
            suggested_action="ask_requirements",
        ))
        return ResultadoValidacion(False, errores, feedbacks=feedbacks)
    
    # ── Validar que hay al menos un acabado ──
    funciones = [s.get("funcion", "") for s in sistema]
    if "acabado" not in funciones:
        advertencias.append("No hay producto con función 'acabado' en el sistema")
        feedbacks.append(ValidationFeedback(
            status="warning", gate_name=gate, reason="missing_finish",
            suggested_message="Veo que no incluí un acabado final. ¿Quieres que te recomiende uno?",
            suggested_action="suggest_finish",
        ))
    
    # ── Validar que preparación siempre existe ──
    if "preparacion" not in funciones:
        advertencias.append("No hay paso de preparación en el sistema")
    
    # ── Validar que áreas grandes tienen cantidades coherentes ──
    area = diag.get("area_m2", 0)
    if area and area > 0:
        for item in sistema:
            if item.get("funcion") in ("acabado", "base", "sellador", "imprimante"):
                cant = item.get("cantidad", 1)
                pres = item.get("presentacion", "")
                if pres == "galon" and area > 0:
                    max_cobertura = cant * 15
                    if area > max_cobertura:
                        advertencias.append(
                            f"Cantidad posiblemente insuficiente: {cant} gal de "
                            f"'{item.get('producto')}' para {area} m²"
                        )
                        feedbacks.append(ValidationFeedback(
                            status="warning", gate_name=gate, reason="insufficient_quantity",
                            product_ref=item.get("producto", ""),
                            suggested_message=f"Para {area} m² puede que necesites más de {cant} galón(es) de {item.get('producto')}. ¿Quieres que ajuste la cantidad?",
                            suggested_action="adjust_quantity",
                        ))
    
    return ResultadoValidacion(len(errores) == 0, errores, advertencias, feedbacks)


# ══════════════════════════════════════════════════════════════════════════════
# VALIDACIÓN 2: COMPLETITUD DE MATCH
# ══════════════════════════════════════════════════════════════════════════════

def validar_completitud_match(match_result: dict) -> ResultadoValidacion:
    """
    Verifica que los productos críticos hayan matcheado correctamente.
    """
    errores = []
    advertencias = []
    feedbacks = []
    gate = "completitud_match"
    
    resueltos = match_result.get("productos_resueltos", [])
    fallidos = match_result.get("productos_fallidos", [])
    
    if not resueltos and not fallidos:
        errores.append("No hay productos para cotizar")
        feedbacks.append(ValidationFeedback(
            status="blocked", gate_name=gate, reason="no_products",
            suggested_message="No encontré productos que coincidan con tu solicitud. ¿Podrías ser más específico con el nombre o la marca?",
            suggested_action="ask_product_clarification",
        ))
        return ResultadoValidacion(False, errores, feedbacks=feedbacks)
    
    # ── Productos críticos que fallaron ──
    funciones_criticas = {"sellador", "imprimante", "base", "acabado"}
    for pf in fallidos:
        funcion = pf.get("funcion", "")
        prod_sol = pf.get("producto_solicitado", "")
        if funcion in funciones_criticas:
            errores.append(
                f"Producto crítico sin match: '{prod_sol}' "
                f"(función: {funcion})"
            )
            feedbacks.append(ValidationFeedback(
                status="blocked", gate_name=gate, reason="critical_product_not_found",
                product_ref=prod_sol,
                suggested_message=f"No encontré '{prod_sol}' en mi inventario. ¿Tienes el nombre exacto o la referencia del producto?",
                suggested_action="ask_product_name",
            ))
        else:
            advertencias.append(
                f"Producto auxiliar sin match: '{prod_sol}' "
                f"(función: {funcion})"
            )
            feedbacks.append(ValidationFeedback(
                status="warning", gate_name=gate, reason="auxiliary_product_not_found",
                product_ref=prod_sol,
                suggested_message=f"No encontré '{prod_sol}' como auxiliar, pero puedo cotizar sin él. ¿Lo necesitas?",
                suggested_action="confirm_skip_auxiliary",
            ))
    
    # ── Productos con fuzzy match sospechoso — posible invención ──
    UMBRAL_FUZZY_SOSPECHOSO = 0.80
    for pr in resueltos:
        score = pr.get("score_match", 1.0)
        if score < UMBRAL_FUZZY_SOSPECHOSO:
            solicitado = pr.get("producto_solicitado", "")
            real = pr.get("descripcion_real", "")
            nombre_base = _extraer_nombre_base(solicitado.lower())
            real_lower = real.lower()
            coincidencias = sum(1 for p in nombre_base if p in real_lower)
            if nombre_base and coincidencias < len(nombre_base) * 0.5:
                errores.append(
                    f"Producto crítico sin match fiable: '{solicitado}' → '{real}' "
                    f"(score: {score:.3f}). Posible producto inventado por el LLM."
                )
                feedbacks.append(ValidationFeedback(
                    status="blocked", gate_name=gate, reason="invented_product",
                    product_ref=solicitado,
                    suggested_message=f"No estoy seguro de haber encontrado '{solicitado}' correctamente. ¿Te refieres a '{real}' o es otro producto?",
                    suggested_action="confirm_product_identity",
                    details=f"Score: {score:.3f}, match: '{real}'",
                ))

    # ── Productos sin precio ──
    for pr in resueltos:
        if not pr.get("precio_unitario") or pr["precio_unitario"] <= 0:
            advertencias.append(
                f"Producto sin precio: '{pr['descripcion_real']}' (ref: {pr.get('codigo', '')})"
            )
            feedbacks.append(ValidationFeedback(
                status="warning", gate_name=gate, reason="no_price",
                product_ref=pr.get("codigo", ""),
                suggested_message=f"El producto '{pr['descripcion_real']}' no tiene precio registrado. Lo incluyo en la cotización pendiente de precio.",
                suggested_action="include_pending_price",
            ))
    
    # ── Productos no disponibles ──
    no_disponibles = [pr for pr in resueltos if not pr.get("disponible")]
    if no_disponibles:
        for nd in no_disponibles:
            advertencias.append(
                f"Producto sin stock: '{nd['descripcion_real']}'"
            )
            feedbacks.append(ValidationFeedback(
                status="warning", gate_name=gate, reason="out_of_stock",
                product_ref=nd.get("codigo", ""),
                suggested_message=f"'{nd['descripcion_real']}' no tiene stock disponible actualmente. ¿Quieres que te avise cuando llegue o busco una alternativa?",
                suggested_action="offer_alternative_or_notify",
            ))
    
    return ResultadoValidacion(len(errores) == 0, errores, advertencias, feedbacks)


# ══════════════════════════════════════════════════════════════════════════════
# VALIDACIÓN 3: COHERENCIA RECOMENDACIÓN ↔ MATCH
# ══════════════════════════════════════════════════════════════════════════════

def validar_coherencia_recomendacion_match(
    recomendacion: dict,
    match_result: dict,
    respuesta_rag: dict = None,
) -> ResultadoValidacion:
    """
    Verifica que lo que se va a cotizar corresponde a lo que se recomendó.
    Previene el problema central: LLM dice "Baños y Cocinas" pero se cotiza "Viniltex Advanced".
    
    Si se pasa respuesta_rag, también verifica que los productos del LLM
    estén alineados con lo que el RAG sugirió (detecta cambios de producto por LLM).
    """
    errores = []
    advertencias = []
    feedbacks = []
    gate = "coherencia_recomendacion_match"
    
    sistema_original = recomendacion.get("sistema", [])
    productos_resueltos = match_result.get("productos_resueltos", [])
    
    # ── Verificar que cada producto resuelto corresponde al solicitado ──
    for resuelto in productos_resueltos:
        solicitado = resuelto.get("producto_solicitado", "").lower()
        descripcion_real = resuelto.get("descripcion_real", "").lower()
        
        # Si el fuzzy match cambió demasiado el producto, es sospechoso
        score = resuelto.get("score_match", 0)
        if score < 0.7:
            advertencias.append(
                f"Match de baja confianza: '{resuelto['producto_solicitado']}' → "
                f"'{resuelto['descripcion_real']}' (score: {score:.3f})"
            )
            feedbacks.append(ValidationFeedback(
                status="warning", gate_name=gate, reason="low_confidence_match",
                product_ref=resuelto.get("codigo", ""),
                suggested_message=f"Encontré '{resuelto['descripcion_real']}' para '{resuelto['producto_solicitado']}', pero no estoy 100% seguro. ¿Es correcto?",
                suggested_action="confirm_match",
            ))
        
        # Verificar que el nombre base del producto solicitado 
        # aparece en la descripción real
        palabras_clave = _extraer_nombre_base(solicitado)
        desc_norm = descripcion_real
        match_count = sum(1 for p in palabras_clave if p in desc_norm)
        if palabras_clave and match_count == 0:
            errores.append(
                f"CAMBIO DE PRODUCTO DETECTADO: Se solicitó '{resuelto['producto_solicitado']}' "
                f"pero el inventario devolvió '{resuelto['descripcion_real']}'. "
                f"Ninguna palabra clave del producto original existe en el match."
            )
            feedbacks.append(ValidationFeedback(
                status="blocked", gate_name=gate, reason="product_change_detected",
                product_ref=resuelto.get("producto_solicitado", ""),
                suggested_message=f"Pediste '{resuelto['producto_solicitado']}' pero lo más cercano que encontré es '{resuelto['descripcion_real']}'. ¿Te sirve ese producto o prefieres otro?",
                suggested_action="confirm_or_change_product",
            ))
    
    # ── Verificar coherencia LLM ↔ RAG ──
    if respuesta_rag:
        _validar_llm_vs_rag(errores, advertencias, feedbacks, sistema_original, respuesta_rag)

    # ── Verificar que las cantidades se mantuvieron ──
    for original in sistema_original:
        prod_original = (original.get("producto", "")).lower()
        cant_original = original.get("cantidad", 1)
        
        for resuelto in productos_resueltos:
            if resuelto.get("producto_solicitado", "").lower() == prod_original:
                cant_resuelta = resuelto.get("cantidad", 1)
                if cant_resuelta != cant_original:
                    advertencias.append(
                        f"Cantidad cambió: '{prod_original}' "
                        f"original={cant_original} → resuelto={cant_resuelta}"
                    )
    
    # ── Verificar que las presentaciones se respetaron ──
    for original in sistema_original:
        prod_original = (original.get("producto", "")).lower()
        pres_original = original.get("presentacion", "")
        
        for resuelto in productos_resueltos:
            if resuelto.get("producto_solicitado", "").lower() == prod_original:
                pres_real = resuelto.get("presentacion_real", "")
                if pres_original and pres_real:
                    if not _presentaciones_equivalentes(pres_original, pres_real):
                        advertencias.append(
                            f"Presentación cambió: '{prod_original}' "
                            f"solicitada='{pres_original}' → real='{pres_real}'"
                        )
    
    return ResultadoValidacion(len(errores) == 0, errores, advertencias, feedbacks)


# ══════════════════════════════════════════════════════════════════════════════
# VALIDACIÓN 4: COMPATIBILIDAD QUÍMICA
# ══════════════════════════════════════════════════════════════════════════════

# Familias químicas y sus señales
FAMILIAS_QUIMICAS = {
    "alquidica": ["pintulux", "alquidico", "esmalte sintetico", "alto brillo alquidico"],
    "epoxica": ["epoxica", "epoxico", "pintucoat", "intergard", "interseal", "epoxy"],
    "poliuretano": ["poliuretano", "interthane", "interlac"],
    "acrilica": ["viniltex", "koraza", "intervinil", "acrilica", "vinilo"],
}

# Pares incompatibles
INCOMPATIBLES = [
    ("alquidica", "poliuretano", "Solventes alquídicos destruyen el poliuretano"),
    ("alquidica", "epoxica", "Alquídico no tiene dureza suficiente sobre epóxico"),
]


def validar_compatibilidad_quimica(match_result: dict) -> ResultadoValidacion:
    """Verifica que no haya combinaciones químicas incompatibles."""
    errores = []
    feedbacks = []
    gate = "compatibilidad_quimica"
    
    productos_resueltos = match_result.get("productos_resueltos", [])
    
    familias_presentes = set()
    for prod in productos_resueltos:
        desc = (prod.get("descripcion_real", "") + " " + prod.get("producto_solicitado", "")).lower()
        for familia, señales in FAMILIAS_QUIMICAS.items():
            if any(s in desc for s in señales):
                familias_presentes.add(familia)
    
    for fam_a, fam_b, razon in INCOMPATIBLES:
        if fam_a in familias_presentes and fam_b in familias_presentes:
            errores.append(f"INCOMPATIBILIDAD QUÍMICA: {fam_a} + {fam_b} — {razon}")
            feedbacks.append(ValidationFeedback(
                status="blocked", gate_name=gate, reason="chemical_incompatibility",
                suggested_message=f"Detecté que los productos que llevas no son compatibles entre sí ({fam_a} + {fam_b}). ¿Te ajusto la recomendación con productos que sí sean compatibles?",
                suggested_action="replace_incompatible",
                details=razon,
            ))
    
    return ResultadoValidacion(len(errores) == 0, errores, feedbacks=feedbacks)


# ══════════════════════════════════════════════════════════════════════════════
# VALIDACIÓN 5: BICOMPONENTES COMPLETOS
# ══════════════════════════════════════════════════════════════════════════════

BICOMPONENTES = [
    {
        "señales_producto": ["interthane 990", "interthane990", "interthane"],
        "señales_catalizador": ["pha046", "pha 046", "catalizador interthane"],
        "señales_ajustador": ["21050", "ajustador 21050"],
        "nombre": "Interthane 990",
        "catalizador": "Catalizador PHA046",
        "ajustador": "Ajustador 21050",
    },
    {
        "señales_producto": ["pintucoat", "epoxico", "epoxica", "intergard", "interseal"],
        "señales_catalizador": ["catalizador epoxi", "parte b epoxi", "componente b"],
        "señales_ajustador": ["ajustador 209", "209"],
        "nombre": "Epóxico (Pintucoat/Intergard)",
        "catalizador": "Catalizador Epóxico (Parte B)",
        "ajustador": "Ajustador 209",
    },
    {
        "señales_producto": ["trafico", "demarcacion", "acrilica mantenimiento"],
        "señales_catalizador": [],  # No requieren catalizador
        "señales_ajustador": ["ajustador 204", "204"],
        "nombre": "Tráfico / Acrílica Mantenimiento",
        "catalizador": "",
        "ajustador": "Ajustador 204",
    },
]


def validar_bicomponentes(match_result: dict) -> ResultadoValidacion:
    """Verifica que los bicomponentes incluyan su catalizador y/o ajustador."""
    errores = []
    feedbacks = []
    gate = "bicomponentes"
    
    todos_productos = (
        match_result.get("productos_resueltos", [])
        + match_result.get("herramientas_resueltas", [])
    )
    texto_completo = " ".join(
        (p.get("descripcion_real", "") + " " + p.get("producto_solicitado", "")).lower()
        for p in todos_productos
    )
    
    for bico in BICOMPONENTES:
        tiene_producto = any(s in texto_completo for s in bico["señales_producto"])
        if not tiene_producto:
            continue

        # Verificar catalizador (si aplica)
        if bico["catalizador"] and bico["señales_catalizador"]:
            tiene_catalizador = any(s in texto_completo for s in bico["señales_catalizador"])
            if not tiene_catalizador:
                errores.append(
                    f"BICOMPONENTE INCOMPLETO: {bico['nombre']} sin {bico['catalizador']}. "
                    f"El producto NO funciona sin su catalizador."
                )
                feedbacks.append(ValidationFeedback(
                    status="blocked", gate_name=gate, reason="missing_catalyst",
                    product_ref=bico["nombre"],
                    suggested_message=f"Veo que llevas {bico['nombre']}, pero falta el {bico['catalizador']} que es indispensable para que funcione. ¿Lo agrego a la cotización?",
                    suggested_action="add_catalyst",
                    suggested_products=[{"nombre": bico["catalizador"], "relacion": "catalizador"}],
                ))
    
    return ResultadoValidacion(len(errores) == 0, errores, feedbacks=feedbacks)


# ══════════════════════════════════════════════════════════════════════════════
# GATE PRINCIPAL — Ejecuta TODAS las validaciones
# ══════════════════════════════════════════════════════════════════════════════

def ejecutar_validacion_completa(
    recomendacion: dict,
    match_result: dict,
    respuesta_rag: dict = None,
) -> ResultadoValidacion:
    """
    Ejecuta todas las validaciones y produce un veredicto consolidado.
    
    Returns:
        ResultadoValidacion consolidado. Si valido=False, NO se debe cotizar.
        Los feedbacks contienen sugerencias de acción para el agente.
    """
    todos_errores = []
    todas_advertencias = []
    todos_feedbacks = []
    
    validaciones = [
        ("coherencia_diagnostico", validar_coherencia_diagnostico(recomendacion)),
        ("completitud_match", validar_completitud_match(match_result)),
        ("coherencia_recomendacion_match", validar_coherencia_recomendacion_match(recomendacion, match_result, respuesta_rag)),
        ("compatibilidad_quimica", validar_compatibilidad_quimica(match_result)),
        ("bicomponentes", validar_bicomponentes(match_result)),
    ]
    
    for nombre, resultado in validaciones:
        if resultado.errores:
            logger.error("VALIDACIÓN %s: FALLO — %s", nombre, resultado.errores)
            todos_errores.extend([f"[{nombre}] {e}" for e in resultado.errores])
        if resultado.advertencias:
            logger.warning("VALIDACIÓN %s: advertencias — %s", nombre, resultado.advertencias)
            todas_advertencias.extend([f"[{nombre}] {a}" for a in resultado.advertencias])
        if resultado.feedbacks:
            todos_feedbacks.extend(resultado.feedbacks)
        if resultado.valido:
            logger.info("VALIDACIÓN %s: OK", nombre)
    
    valido = len(todos_errores) == 0
    
    if not valido:
        blocking = [f for f in todos_feedbacks if f.is_blocked]
        logger.error(
            "GATE VALIDACIÓN: BLOQUEADO — %d errores, %d advertencias, %d feedbacks bloqueantes",
            len(todos_errores), len(todas_advertencias), len(blocking),
        )
    else:
        logger.info(
            "GATE VALIDACIÓN: APROBADO — %d advertencias, %d feedbacks informativos",
            len(todas_advertencias), len(todos_feedbacks),
        )
    
    return ResultadoValidacion(valido, todos_errores, todas_advertencias, todos_feedbacks)


# ══════════════════════════════════════════════════════════════════════════════
# UTILIDADES INTERNAS
# ══════════════════════════════════════════════════════════════════════════════

def _validar_llm_vs_rag(errores: list, advertencias: list, feedbacks: list, sistema_llm: list, respuesta_rag: dict):
    """Detecta cuando el LLM ignora o cambia productos que el RAG sugirió."""
    rag_text = ""
    guia = respuesta_rag.get("guia_tecnica_estructurada", {})
    if guia:
        # Extraer todos los productos que el RAG menciona
        for key in ("base_or_primer", "finish_options", "intermediate_steps"):
            val = guia.get(key)
            if isinstance(val, list):
                for v in val:
                    rag_text += " " + v.lower()
            elif isinstance(val, str):
                rag_text += " " + val.lower()
    # También tomar del texto narrativo
    rag_narr = respuesta_rag.get("respuesta_rag", "")
    rag_text += " " + rag_narr.lower()
    
    if not rag_text.strip():
        return
    
    for item in sistema_llm:
        func = item.get("funcion", "")
        if func not in ("acabado", "sellador", "imprimante", "base"):
            continue
        prod_llm = item.get("producto", "").lower()
        nombre_base = _extraer_nombre_base(prod_llm)
        # Verificar que las palabras distintivas del producto LLM
        # aparecen en lo que el RAG sugirió.
        # Requiere que AL MENOS la mayoría de palabras clave estén presentes.
        if nombre_base:
            palabras_en_rag = sum(1 for p in nombre_base if p in rag_text and len(p) > 3)
            ratio = palabras_en_rag / len([p for p in nombre_base if len(p) > 3]) if any(len(p) > 3 for p in nombre_base) else 1.0
            if ratio < 0.8:
                errores.append(
                    f"CAMBIO DE PRODUCTO POR LLM: El producto '{item.get('producto')}' "
                    f"(función: {func}) NO fue sugerido por el RAG. "
                    f"Posible hallucination o sustitución no autorizada."
                )
                feedbacks.append(ValidationFeedback(
                    status="blocked", gate_name="coherencia_recomendacion_match",
                    reason="llm_product_swap",
                    product_ref=item.get("producto", ""),
                    suggested_message=f"Noté que '{item.get('producto')}' no coincide con lo que tenemos registrado para tu caso. Déjame verificar y darte la opción correcta.",
                    suggested_action="rerun_with_rag_products",
                ))


def _extraer_nombre_base(producto: str) -> list[str]:
    """Extrae palabras clave del nombre base de un producto."""
    stopwords = {"de", "del", "la", "el", "para", "con", "en", "blanco", "gris", "negro"}
    palabras = producto.lower().split()
    return [p for p in palabras if p not in stopwords and len(p) > 2]


def _presentaciones_equivalentes(pres_a: str, pres_b: str) -> bool:
    """Verifica si dos presentaciones son equivalentes."""
    equivalencias = {
        "galon": {"galon", "gl", "gal", "3.79l"},
        "cunete": {"cunete", "cuñete", "5gl", "18.93l", "20l"},
        "cuarto": {"cuarto", "1/4", "qt", "0.946l"},
        "litro": {"litro", "lt", "1l"},
        "unidad": {"unidad", "und", "un", "pza"},
    }
    
    a_norm = pres_a.lower().strip()
    b_norm = pres_b.lower().strip()
    
    for _, sinonimos in equivalencias.items():
        if a_norm in sinonimos and b_norm in sinonimos:
            return True
    
    return a_norm == b_norm
