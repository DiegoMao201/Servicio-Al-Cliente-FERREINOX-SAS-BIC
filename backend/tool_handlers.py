"""Capa de Herramientas (Tool Handlers) — orquestación de tools del LLM.

Extraído de ``backend.main`` durante la Fase C2 (Step 5) y refinado en la
Fase C3 HITO 1 (eliminación del accesor lazy ``_m()``).

Contiene los handlers más voluminosos y aislables de la capa de tools del agente:
  - ``_handle_tool_consultar_conocimiento_tecnico``: pieza central del RAG.
  - ``_handle_tool_consultar_base_color``: lookup en LIBRO DE FORMULAS.
  - ``_handle_tool_consultar_referencia_international``: tabla AkzoNobel.

Reglas:
  - Lógica intacta (Move & Wire). Sin cambios de comportamiento.
  - Importa directamente de los módulos extraídos (``rag_search``,
    ``rag_helpers``, ``policies``, ``bicomponents``, ``agent_profiles``).
    NO depende de ``backend.main``.
  - El acoplamiento residual hacia helpers primitivos aún en ``main`` queda
    confinado dentro de ``rag_helpers`` (capa única de borde).
  - Las funciones se re-exportan desde ``backend.main`` para preservar la
    API pública (``main._handle_tool_consultar_conocimiento_tecnico(...)``
    sigue siendo válido).
"""

from __future__ import annotations

import json

# Imports directos desde módulos ya extraídos (sin riesgo de ciclo)
try:
    from rag_search import (
        _infer_portfolio_segments_for_query,
        _infer_technical_metadata_prefilters,
        build_rag_context,
        fetch_technical_profiles,
        search_multimodal_product_index,
        search_supporting_technical_guides,
        search_technical_chunks,
    )
except ImportError:
    from backend.rag_search import (
        _infer_portfolio_segments_for_query,
        _infer_technical_metadata_prefilters,
        build_rag_context,
        fetch_technical_profiles,
        search_multimodal_product_index,
        search_supporting_technical_guides,
        search_technical_chunks,
    )

try:
    from policies import _build_hard_policies_for_context
except ImportError:
    from backend.policies import _build_hard_policies_for_context

try:
    from bicomponents import BICOMPONENT_CATALOG, get_bicomponent_info
except ImportError:
    from backend.bicomponents import BICOMPONENT_CATALOG, get_bicomponent_info

try:
    from agent_profiles import get_agent_profile_name
except ImportError:
    from backend.agent_profiles import get_agent_profile_name

try:
    from rag_helpers import (
        _build_structured_diagnosis,
        _build_structured_technical_guide,
        _derive_policy_inventory_candidate_terms,
        _filter_inventory_candidates_by_policy,
        _filter_profiles_by_surface_compatibility,
        _filter_rag_candidates_by_surface_and_policy,
        _infer_surface_types_from_query,
        extract_candidate_products_from_rag_context,
        fetch_expert_knowledge,
        lookup_inventory_candidates_from_terms,
    )
except ImportError:
    from backend.rag_helpers import (
        _build_structured_diagnosis,
        _build_structured_technical_guide,
        _derive_policy_inventory_candidate_terms,
        _filter_inventory_candidates_by_policy,
        _filter_profiles_by_surface_compatibility,
        _filter_rag_candidates_by_surface_and_policy,
        _infer_surface_types_from_query,
        extract_candidate_products_from_rag_context,
        fetch_expert_knowledge,
        lookup_inventory_candidates_from_terms,
    )


def _main_primitives():
    """Acceso a primitivas aún residentes en ``backend.main``.

    Helpers que se usan dentro del cuerpo de los handlers pero todavía
    no se han extraído (``normalize_text_value``, ``parse_numeric_value``,
    ``PORTFOLIO_CATEGORY_MAP``). Migrar en Fase C4.
    """
    try:
        from backend import main as _main
    except ImportError:
        import main as _main  # type: ignore
    return _main


# ─────────────────────────────────────────────────────────────────────────────
# Tool: consultar_conocimiento_tecnico (pieza central del RAG)
# ─────────────────────────────────────────────────────────────────────────────

def _handle_tool_consultar_conocimiento_tecnico(args, context, conversation_context):
    pregunta = (args.get("pregunta") or "").strip()
    producto = (args.get("producto") or "").strip()
    marca_filter = (args.get("marca") or "").strip() or None
    explicit_segment = (args.get("segmento") or "").strip() or None
    if not pregunta:
        return json.dumps(
            {"encontrado": False, "mensaje": "Se requiere una pregunta técnica."},
            ensure_ascii=False,
        )

    primitives = _main_primitives()

    # Build search query combining question + product context
    search_query = pregunta
    if producto:
        search_query = f"{producto}: {pregunta}"

    # ── Auto-detect Industrial/MPY context → prioritize International brand guide ──────
    # When the query involves industrial maintenance, International/AkzoNobel products,
    # structures, ISO/SSPC specs, or fire protection — force marca_filter="international"
    # so the agent pulls from GUIA-Sistemas Mantenimiento Industria almost exclusivamente.
    _INDUSTRIAL_MPY_KEYWORDS = [
        "industrial", "international", "mpy", "akzonobel",
        "interseal", "interthane", "intergard", "interfine", "interchar",
        "estructura acero", "estructura metalica industrial", "sspc", "iso 12944",
        "mantenimiento industrial", "planta industrial", "bodega quimica",
        "almacenamiento quimico", "proteccion fuego", "intumescente",
        "poliuretano industrial", "epoxica industrial pesado",
        "recubrimiento industrial", "sistema mantenimiento", "ambientes agresivos",
        "ambiente quimico", "corrosion industrial", "anticorrosivo industrial",
        # Conditional applications — require RAG lookup from International guide
        "agua potable", "tanque agua", "tanque de agua", "inmercion", "inmersion",
        "sumergido", "sumergida", "servicio inmerso", "nsf", "ansi 61", "interline",
        "lining", "revestimiento interior tanque", "temperatura extrema",
        "superficies calientes", "resistencia quimica alta", "ambiente marino",
    ]
    _q_lower = (pregunta + " " + producto).lower()
    if not marca_filter and any(kw in _q_lower for kw in _INDUSTRIAL_MPY_KEYWORDS):
        marca_filter = "international"
    segment_filters = _infer_portfolio_segments_for_query(pregunta, producto, explicit_segment)
    prefilter_diagnosis = _build_structured_diagnosis(pregunta, producto, 0.0)
    metadata_prefilters = _infer_technical_metadata_prefilters(pregunta, producto, prefilter_diagnosis)
    metadata_prefilter_active = bool(metadata_prefilters.get("canonical_family_patterns") or metadata_prefilters.get("chemical_family_terms"))
    metadata_prefilter_fallback = False

    chunks = search_technical_chunks(
        search_query,
        top_k=6,
        marca_filter=marca_filter,
        segment_filters=segment_filters or None,
        metadata_prefilters=metadata_prefilters if metadata_prefilter_active else None,
    )
    guide_chunks = search_supporting_technical_guides(search_query, top_k=3, marca_filter=marca_filter, segment_filters=segment_filters or None)
    if not chunks and metadata_prefilter_active:
        metadata_prefilter_fallback = True
        chunks = search_technical_chunks(search_query, top_k=6, marca_filter=marca_filter, segment_filters=segment_filters or None)
    segment_fallback_used = False
    if not chunks and not guide_chunks and segment_filters:
        chunks = search_technical_chunks(search_query, top_k=6, marca_filter=marca_filter)
        guide_chunks = search_supporting_technical_guides(search_query, top_k=3, marca_filter=marca_filter)
        segment_fallback_used = True

    # ── Portfolio-aware second search pass ──────────────────────────
    # If the initial RAG search returned weak/wrong results AND no specific
    # product was provided, try again with portfolio-expanded terms.
    # Threshold 0.70: most correct product-level queries score >0.70,
    # so anything below that likely means the RAG didn't find the right product.
    best_sim_initial = max((c.get("similarity", 0) for c in chunks), default=0)
    if best_sim_initial < 0.70 and not producto:
        # Extract key terms from the question and expand via portfolio map
        pregunta_norm = primitives.normalize_text_value(pregunta)
        portfolio_products: list[str] = []
        # Check full question and individual words against PORTFOLIO_CATEGORY_MAP
        for category_key, brand_terms in primitives.PORTFOLIO_CATEGORY_MAP.items():
            if category_key in pregunta_norm or pregunta_norm in category_key:
                for bt in brand_terms:
                    if bt != "__SIN_PRODUCTO_FERREINOX__" and bt not in portfolio_products:
                        portfolio_products.append(bt)
        for word in pregunta_norm.split():
            if len(word) < 4:
                continue
            if word in primitives.PORTFOLIO_CATEGORY_MAP:
                for bt in primitives.PORTFOLIO_CATEGORY_MAP[word]:
                    if bt != "__SIN_PRODUCTO_FERREINOX__" and bt not in portfolio_products:
                        portfolio_products.append(bt)
        # Do targeted RAG searches for top portfolio products
        if portfolio_products:
            extra_chunks: list[dict] = []
            for pp in portfolio_products[:3]:  # Top 3 most relevant
                pp_chunks = search_technical_chunks(
                    f"{pp}: {pregunta}",
                    top_k=3,
                    marca_filter=marca_filter,
                    segment_filters=segment_filters or None,
                    metadata_prefilters=metadata_prefilters if metadata_prefilter_active else None,
                )
                extra_chunks.extend(pp_chunks)
            # Merge: keep best chunks from both searches, deduplicate by text
            seen_texts: set[str] = set()
            seen_families: set[str] = set()
            merged: list[dict] = []
            all_chunks = sorted(chunks + extra_chunks, key=lambda c: c.get("similarity", 0), reverse=True)
            for ch in all_chunks:
                txt_key = (ch.get("chunk_text") or "")[:80]
                metadata = ch.get("metadata") or {}
                family_key = (metadata.get("canonical_family") or ch.get("familia_producto") or "").strip().lower()
                if txt_key in seen_texts:
                    continue
                if family_key and family_key in seen_families and ch.get("similarity", 0) < 0.78:
                    continue
                seen_texts.add(txt_key)
                if family_key:
                    seen_families.add(family_key)
                merged.append(ch)
            chunks = merged[:8]

    if not chunks and not guide_chunks:
        return json.dumps(
            {"encontrado": False, "respuesta_rag": None,
             "mensaje": "No encontré información técnica vectorizada para esa consulta. "
                        "Intenta con `buscar_documento_tecnico` para enviar el PDF completo."},
            ensure_ascii=False,
        )

    rag_context = build_rag_context(chunks, max_chunks=4)
    guide_context = build_rag_context(guide_chunks, max_chunks=2)
    source_files = list(dict.fromkeys(c.get("doc_filename", "") for c in chunks if c.get("similarity", 0) >= 0.25))
    best_similarity = max((c.get("similarity", 0) for c in chunks), default=max((c.get("similarity", 0) for c in guide_chunks), default=0))
    canonical_families = list(dict.fromkeys(
        (c.get("metadata") or {}).get("canonical_family") or c.get("familia_producto")
        for c in chunks
        if c.get("similarity", 0) >= 0.25
    ))
    technical_profiles = fetch_technical_profiles(canonical_families, source_files, limit=3, segment_filters=segment_filters or None)
    guide_canonical_families = list(dict.fromkeys(
        (c.get("metadata") or {}).get("canonical_family") or c.get("familia_producto")
        for c in guide_chunks
        if c.get("similarity", 0) >= 0.2
    ))
    guide_source_files = list(dict.fromkeys(c.get("doc_filename", "") for c in guide_chunks if c.get("similarity", 0) >= 0.2))
    guide_profiles = fetch_technical_profiles(guide_canonical_families, guide_source_files, limit=3, segment_filters=segment_filters or None)
    multimodal_products = search_multimodal_product_index(search_query, top_k=3, marca_filter=marca_filter)

    expert_notes = fetch_expert_knowledge(f"{producto} {pregunta}", limit=8)
    structured_diagnosis = _build_structured_diagnosis(pregunta, producto, best_similarity)
    structured_guide = _build_structured_technical_guide(
        pregunta,
        producto,
        structured_diagnosis,
        expert_notes,
        best_similarity,
    )
    hard_policies = _build_hard_policies_for_context(
        pregunta,
        producto,
        structured_diagnosis,
        structured_guide,
        expert_notes,
    )

    # ── Surface-aware filtering ──────────────────────────────────────────
    # Detect what surface the user is asking about, then use profile
    # metadata (restricted_surfaces) to filter out incompatible products.
    # This replaces thousands of specific rules with data-driven filtering.
    diagnosed_surfaces = _infer_surface_types_from_query(pregunta, producto)
    all_profiles = technical_profiles + guide_profiles
    surface_restricted_families = _filter_profiles_by_surface_compatibility(
        all_profiles, diagnosed_surfaces, query_text=f"{pregunta} {producto}",
    )

    # Derive commercial candidates from the structured guide/policies first.
    # RAG-only extraction is kept as a fallback, but it must not override
    # products that the contextual policies already marked as required/prohibited.
    candidate_product_names = _derive_policy_inventory_candidate_terms(
        structured_guide,
        hard_policies,
        expert_notes=expert_notes,
        explicit_product=producto,
    )
    rag_candidate_names = extract_candidate_products_from_rag_context(
        rag_context,
        source_files[0] if source_files else None,
        original_question=pregunta,
    )
    # ── CLOSE THE FUGA: filter RAG candidates against policies AND surface metadata ──
    # Before: RAG candidates were appended unconditionally, re-injecting wrong products.
    # Now: filter against forbidden_products AND surface-restricted families.
    forbidden_list = hard_policies.get("forbidden_products") or []
    rag_candidate_names = _filter_rag_candidates_by_surface_and_policy(
        rag_candidate_names, forbidden_list, surface_restricted_families,
    )
    for candidate_name in rag_candidate_names:
        if candidate_name not in candidate_product_names:
            candidate_product_names.append(candidate_name)
    for multimodal_entry in multimodal_products:
        multimodal_family = (multimodal_entry.get("canonical_family") or "").strip()
        if multimodal_family and multimodal_family not in candidate_product_names:
            candidate_product_names.append(multimodal_family)

    inventory_candidates = []
    if candidate_product_names:
        inventory_candidates = lookup_inventory_candidates_from_terms(
            candidate_product_names,
            conversation_context,
            allow_portfolio_expansion=False,
        )
        inventory_candidates = _filter_inventory_candidates_by_policy(inventory_candidates, hard_policies)

    # ── Síntesis canónica única (las reglas de tono/anti-invención viven en el system prompt) ──
    cierre_comercial = (
        "Si quieres, te conecto con un asesor comercial para cotizar los productos."
        if get_agent_profile_name() == "internal"
        else "¿Deseas que te arme la cotización formal o prefieres realizar el pedido directamente?"
    )
    instruccion_sintesis = (
        "Orden de lectura: politicas_duras_contexto → conocimiento_comercial_ferreinox → "
        "perfil_tecnico_principal → diagnostico_estructurado → guia_tecnica_estructurada → "
        "guias_tecnicas_relacionadas/contexto_guias → respuesta_rag (sintetiza, no copies). "
        "Si pricing_ready=false o pricing_gate='m2_required', no cotices: pide el dato faltante. "
        "Cálculo: m² ÷ rendimiento_mínimo del RAG = galones (redondear ARRIBA). "
        f"Cierre del turno: \"{cierre_comercial}\""
    )

    result_payload = {
        "encontrado": True,
        "respuesta_rag": rag_context,
        "contexto_guias": guide_context,
        "archivos_fuente": source_files,
        "segmentos_portafolio_detectados": segment_filters,
        "segmento_fallback_sin_filtro": segment_fallback_used,
        "metadata_prefiltros_rag": metadata_prefilters if metadata_prefilter_active else {},
        "metadata_prefiltro_fallback": metadata_prefilter_fallback,
        "mejor_similitud": round(best_similarity, 4),
        "diagnostico_estructurado": structured_diagnosis,
        "guia_tecnica_estructurada": structured_guide,
        "politicas_duras_contexto": hard_policies,
        "productos_sistema_prioritarios": candidate_product_names[:8],
        "productos_multimodales_relacionados": multimodal_products,
        "preguntas_pendientes": structured_diagnosis.get("required_validations") or [],
        "instruccion_sintesis": instruccion_sintesis,
    }

    if technical_profiles:
        result_payload["perfil_tecnico_principal"] = technical_profiles[0].get("profile_json")
        result_payload["perfiles_tecnicos_relacionados"] = [
            item.get("profile_json")
            for item in technical_profiles
            if item.get("profile_json")
        ]
    if guide_profiles:
        result_payload["guias_tecnicas_relacionadas"] = [
            item.get("profile_json")
            for item in guide_profiles
            if item.get("profile_json")
        ]

    # ── Bandera escenario industrial (instrucciones de formato viven en el system prompt) ──
    if marca_filter == "international":
        result_payload["escenario_industrial"] = True

    # ── Bicomponente: pasamos solo DATOS estructurados (no doctrina prosa) ──
    _bicomp_info = get_bicomponent_info(f"{pregunta} {producto}")
    if _bicomp_info:
        _bkey = _bicomp_info.get("producto_base", "")
        _catalog_entry = BICOMPONENT_CATALOG.get(_bkey, {})
        result_payload["bicomponente"] = {
            "producto_base": _bkey,
            "componente_b_codigo": _catalog_entry.get("componente_b_codigo") or "ver ficha técnica",
            "proporcion_galon": _catalog_entry.get("proporcion_galon") or _catalog_entry.get("nota") or "ver ficha técnica",
            "restriccion_exterior": _catalog_entry.get("restriccion_exterior") or None,
        }
        # Aplicación condicional agua potable / inmersión (solo dato verificado del catálogo)
        _q_agua = primitives.normalize_text_value(f"{pregunta} {producto}")
        _agua_keywords = ["agua potable", "tanque agua", "inmercion", "inmersion", "nsf", "ansi", "sumergido", "lining"]
        if _bkey == "interseal" and any(kw in _q_agua for kw in _agua_keywords):
            _agua_note = _catalog_entry.get("aplicacion_condicional_agua_potable", "")
            if _agua_note:
                result_payload["aplicacion_agua_potable"] = _agua_note

    if inventory_candidates:
        result_payload["productos_inventario_relacionados"] = [
            {
                "codigo": p.get("codigo"),
                "descripcion": p.get("descripcion"),
                "etiqueta_auditable": p.get("etiqueta_auditable"),
                "marca": p.get("marca"),
                "presentacion": p.get("presentacion"),
                "disponible": bool(p.get("stock_total") and primitives.parse_numeric_value(p.get("stock_total")) > 0),
                "complementarios": p.get("productos_complementarios") or [],
            }
            for p in inventory_candidates
        ]
        # Recordatorio operativo corto: estos son CANDIDATOS, no confirmación de stock.
        result_payload["nota_inventario_candidatos"] = (
            "Candidatos técnicos del portafolio (NO confirma stock). Antes de presentar al cliente, "
            "llama `consultar_inventario` o `consultar_inventario_lote` con los nombres canónicos de "
            "`productos_sistema_prioritarios` para confirmar disponibilidad y referencia ERP."
        )

    # ── Conocimiento experto Ferreinox (sigue siendo dato estructurado consumido aguas abajo) ──
    if expert_notes:
        result_payload["conocimiento_comercial_ferreinox"] = [
            {
                "id": n["id"],
                "tipo": n["tipo"],
                "contexto": n["contexto_tags"],
                "recomendar": n["producto_recomendado"],
                "evitar": n["producto_desestimado"],
                "nota": n["nota_comercial"],
            }
            for n in expert_notes
        ]

    return json.dumps(result_payload, ensure_ascii=False, default=str)


# ─────────────────────────────────────────────────────────────────────────────
# Tool: consultar_base_color (LIBRO DE FORMULAS)
# ─────────────────────────────────────────────────────────────────────────────

def _handle_tool_consultar_base_color(fn_args: dict) -> str:
    color = fn_args.get("color", "")
    producto = fn_args.get("producto", "")
    results = _main_primitives().lookup_color_base(color, producto)
    if not results:
        return json.dumps({
            "encontrado": False,
            "mensaje": f"No encontré el color '{color}' en el catálogo de fórmulas. El cliente puede visitar www.ferreinox.co sección Cartas de Colores para ver la gama completa. Si tiene el código del color (ej: 1502), búscalo por código.",
        }, ensure_ascii=False)
    items = []
    for r in results:
        items.append({
            "codigo": r["codigo"],
            "nombre_color": r["nombre"],
            "base_requerida": r["base"],
            "linea_producto": r["producto"],
        })
    return json.dumps({
        "encontrado": True,
        "colores": items,
        "instruccion": (
            "Usa la BASE indicada para buscar en inventario. "
            "Ej: si base='Base Deep' y producto='Viniltex' → buscar 'Viniltex Base Deep galón'. "
            "La tintometría se realiza en tienda con la fórmula del color. "
            "⚠️ REGLA DOMÉSTICO: Doméstico NO viene en Base Accent. Si el color requiere Base Accent "
            "y el cliente pide Doméstico → decir: 'Ese color no viene en Doméstico porque requiere "
            "Base Accent. Te lo puedo ofrecer en Pintulux 3en1 o Pintulux Máxima Protección.' "
            "Los colores de Doméstico y Pintulux usan las mismas bases que Viniltex (excepto Accent en Doméstico). "
            "Menciona al cliente: 'Puedes ver toda nuestra gama de colores en www.ferreinox.co sección Cartas de Colores'."
        ),
    }, ensure_ascii=False)


# ─────────────────────────────────────────────────────────────────────────────
# Tool: consultar_referencia_international (tabla AkzoNobel)
# ─────────────────────────────────────────────────────────────────────────────

def _handle_tool_consultar_referencia_international(fn_args: dict) -> str:
    producto = fn_args.get("producto", "")
    base = fn_args.get("base", "")
    ral = fn_args.get("ral", "")

    # ── Intergard 2002 is SOBRE PEDIDO — block lookup, force escalation ──
    if "2002" in producto:
        return json.dumps({
            "encontrado": False,
            "sobre_pedido": True,
            "producto": "Intergard 2002",
            "mensaje": (
                "⚠️ Intergard 2002 es un PRODUCTO SOBRE PEDIDO. NO cotices precio. "
                "Este sistema de alto desempeño para pisos de tráfico pesado requiere "
                "asesoría técnica personalizada. Pregunta al cliente: "
                "'¿Deseas que te contacte con nuestro Asesor Técnico Comercial para "
                "estructurar tu proyecto?' Si acepta → escalar a tiendapintucopereira@ferreinox.co."
            ),
        }, ensure_ascii=False)

    # ── Default RAL 7038 if no RAL specified ──
    _used_default_ral = False
    if not ral:
        ral = "7038"
        _used_default_ral = True

    results = _main_primitives().lookup_international_product(producto, base, ral)
    if not results:
        return json.dumps({
            "encontrado": False,
            "mensaje": f"No encontré '{producto}' en la tabla de referencia International. Usa consultar_inventario para buscar por nombre comercial.",
        }, ensure_ascii=False)
    items = []
    for r in results:
        entry = {"producto": r.get("producto", ""), "base": r.get("base", ""), "ral": r.get("ral", "")}
        if r.get("kit_galon"):
            entry["precio_kit_galon_iva_inc"] = r["kit_galon"]
        if r.get("precio_galon"):
            entry["precio_base_galon_iva_inc"] = r["precio_galon"]
        if r.get("codigo_base_galon"):
            entry["codigo_base_galon"] = r["codigo_base_galon"]
        if r.get("codigo_cat_galon"):
            entry["codigo_catalizador_galon"] = r["codigo_cat_galon"]
        if r.get("precio_cat_galon"):
            entry["precio_catalizador_galon_iva_inc"] = r["precio_cat_galon"]
        if r.get("kit_cunete"):
            entry["precio_kit_cunete_iva_inc"] = r["kit_cunete"]
        if r.get("precio_cunete"):
            entry["precio_base_cunete_iva_inc"] = r["precio_cunete"]
        if r.get("codigo_cunete"):
            entry["codigo_base_cunete"] = r["codigo_cunete"]
        if r.get("codigo_cat_cunete"):
            entry["codigo_catalizador_cunete"] = r["codigo_cat_cunete"]
        if r.get("precio_cat_cunete"):
            entry["precio_catalizador_cunete_iva_inc"] = r["precio_cat_cunete"]
        # Acrilica Mantenimiento fields
        if r.get("codigo_galon"):
            entry["codigo_galon"] = r["codigo_galon"]
            entry["precio_galon_iva_inc"] = r.get("precio_galon", "")
        if r.get("codigo_cunete"):
            entry["codigo_cunete"] = r["codigo_cunete"]
            entry["precio_cunete_iva_inc"] = r.get("precio_cunete", "")
        if r.get("tonalidad"):
            entry["tonalidad"] = r["tonalidad"]
        items.append(entry)
    return json.dumps({
        "encontrado": True,
        "productos": items,
        "total_resultados": len(items),
        "ral_usado": ral,
        "ral_default_aplicado": _used_default_ral,
        "instruccion": (
            "⚠️ IMPORTANTE: Los precios de esta tabla YA INCLUYEN IVA. "
            "NO sumes IVA de nuevo. El precio KIT galón = base + catalizador ya con IVA. "
            "Para cotizar: precio_kit × cantidad = subtotal. El total YA es con IVA incluido. "
            "Usa los CÓDIGOS de referencia para buscar disponibilidad con consultar_inventario."
            + (" Se usó RAL 7038 (gris claro) por defecto porque el cliente no especificó color. "
               "SIEMPRE agrega: 'Para más colores RAL disponibles, visita www.ferreinox.co'" if _used_default_ral else "")
        ),
    }, ensure_ascii=False)


__all__ = [
    "_handle_tool_consultar_conocimiento_tecnico",
    "_handle_tool_consultar_base_color",
    "_handle_tool_consultar_referencia_international",
]
