"""Helpers de la capa RAG/políticas/superficies — Fase C3 HITO 1.

Este módulo absorbe los helpers de coordinación del flujo RAG-comercial que
antes vivían en `backend.main` y eran consumidos vía un acceso perezoso desde
`backend.tool_handlers`. Después de Fase C3:

  - ``backend.tool_handlers`` importa directamente desde aquí (sin ``_m()``).
  - El acceso perezoso a ``backend.main`` queda **contenido** en este módulo,
    como única capa de borde, hasta que se complete la migración de los
    helpers primitivos (``normalize_text_value``, ``parse_numeric_value``,
    ``lookup_product_context``, ``fetch_product_companions``,
    ``get_exact_product_description``, ``build_product_audit_label``,
    ``infer_product_presentation_from_row``,
    ``prepare_product_request_for_search``,
    ``_derive_portfolio_candidates_from_question``,
    ``_expand_terms_with_portfolio_knowledge``,
    ``_get_expert_knowledge_cache``,
    ``PORTFOLIO_CATEGORY_MAP``) en una iteración futura.

Funciones movidas (Move & Wire — sin cambios de comportamiento):
  - ``fetch_expert_knowledge``
  - ``extract_candidate_products_from_rag_context``
  - ``_derive_policy_inventory_candidate_terms``
  - ``_text_matches_policy_product``
  - ``_infer_surface_types_from_query``
  - ``_filter_profiles_by_surface_compatibility``
  - ``_filter_rag_candidates_by_surface_and_policy``
  - ``_filter_inventory_candidates_by_policy``
  - ``lookup_inventory_candidates_from_terms``

Stubs explícitos (TODO: RECONSTRUIR LOGICA DE NEGOCIO):
  - ``_build_structured_diagnosis`` — REIMPLEMENTADO en Fase D1
    (extracción determinista de los 3 pilares — sustrato/estado/exposición —
    contra ``DiagnosisPayload`` Pydantic).
  - ``_build_structured_technical_guide`` — REIMPLEMENTADO en Fase D1
    (whitelist estricta de SKUs desde inventory + rag_chunks, validación
    bicomponente vs ``BICOMPONENT_CATALOG`` y alerta crítica si falta el
    catalizador).
"""

from __future__ import annotations

import logging
import re
from typing import Any, Optional

logger = logging.getLogger("ferreinox_agent")

# ── Imports directos a módulos ya extraídos (sin riesgo de ciclo) ────────────
try:
    from policies import _is_tool_policy_item, _split_policy_items
except ImportError:
    from backend.policies import _is_tool_policy_item, _split_policy_items

try:
    from technical_product_canonicalization import canonicalize_technical_product_term
except ImportError:
    from backend.technical_product_canonicalization import canonicalize_technical_product_term


def _m():
    """Acceso perezoso a ``backend.main`` para helpers aún no migrados.

    DEUDA TÉCNICA contenida: este accesor es el único punto de acoplamiento
    inverso entre ``rag_helpers`` y ``main``. Se elimina cuando los helpers
    primitivos listados en el docstring del módulo se extraigan a sus
    propios módulos (probable Fase C4).
    """
    try:
        from backend import main as _main
    except ImportError:
        import main as _main  # type: ignore
    return _main


# ─────────────────────────────────────────────────────────────────────────────
# Phase D1 — Implementaciones reales de _build_structured_diagnosis y
#            _build_structured_technical_guide
# ─────────────────────────────────────────────────────────────────────────────
# Las versiones stub (Fase C3) fueron reemplazadas por las implementaciones
# deterministas más abajo. Contratos Pydantic en backend/schemas/.

# ─────────────────────────────────────────────────────────────────────────────
# Phase D1 — Reimplementación determinista de los dos motores estructurados
# ─────────────────────────────────────────────────────────────────────────────
#
# Reglas inquebrantables (ver backend/schemas/):
#   - Cero alucinación comercial: ningún SKU entra a la guía sin venir de
#     inventory_candidates o rag_chunks (con metadata.sku poblada).
#   - Flujo consultivo estricto: el diagnóstico no se marca ready sin los
#     3 pilares (sustrato + estado + exposición).
#   - Validación química: si el sistema es bicomponente y falta el
#     catalizador en inventario → alerta crítica + pricing bloqueado.
#
# Implementación por extracción determinista de keywords (sin LLM).
# Fast, testable, reproducible. Si en el futuro se requiere mayor recall,
# añadir un LLM call estructurado a JSON como pre-paso opcional.

# ── Mapas de keywords para los 3 pilares del diagnóstico ────────────────
_SUBSTRATE_DETECT: dict[str, list[str]] = {
    "metal": [
        "metal", "metalic", "hierro", "acero", "galvaniz", "lamina",
        "tuberia metalica", "reja", "porton", "estructura metalica",
        "teja zinc", "teja metalica", "tubo metalico",
    ],
    "concreto": [
        "concreto", "cemento", "mamposteria", "ladrillo", "pared",
        "muro", "fachada", "estuco", "drywall", "bloque", "placa de concreto",
    ],
    "madera": [
        "madera", "mdf", "triplex", "mueble", "closet", "puerta de madera",
        "deck", "piso de madera",
    ],
    "fibrocemento": ["fibrocemento", "eternit", "asbesto"],
    "plastico": ["plastico", "pvc", "polietileno"],
    "ceramica": ["ceramica", "porcelanato", "azulejo", "ceramico"],
}

_STATE_DETECT: dict[str, list[str]] = {
    "oxidado": ["oxido", "oxidad", "corrosion", "corroid", "herrumbre"],
    "descascarado": ["descascar", "desprend", "saltando", "saltad", "pelando"],
    "humedo": [
        "humedad", "humedo", "filtracion", "moho", "hongos",
        "salitre", "eflorescencia",
    ],
    "agrietado": ["grieta", "fisura", "agrietad", "fisurad"],
    "manchado": ["manchad", "negread", "ennegrec", "contaminad", "sucio"],
    "deteriorado": ["deteriorad", "envejecid", "decolorad", "entizad"],
    "intacto": [
        "obra blanca", "primera mano", "sin pintar", "sin pintura",
        "concreto nuevo", "estuco nuevo",
    ],
}

_EXPOSURE_DETECT: dict[str, list[str]] = {
    "sumergido": [
        "sumergid", "inmersion", "tanque de agua", "piscina", "agua potable",
    ],
    "alta_temperatura": [
        "alta temperatura", "horno", "caldera", "chimenea", "tuberia de vapor",
    ],
    "trafico_pesado": [
        "trafico pesado", "montacargas", "estibadores", "uso industrial",
    ],
    "trafico_liviano": [
        "trafico liviano", "peatonal", "garaje residencial",
    ],
    "exterior": ["exterior", "intemperie", "fachada", "patio", "techo exterior"],
    "interior": [
        "interior", "habitacion", "alcoba", "sala", "comedor",
        "oficina", "bano", "cocina",
    ],
}


def _detect_pillar(text: str, mapping: dict[str, list[str]]) -> Optional[str]:
    """Devuelve la primera categoría del mapa cuya keyword aparezca en text."""
    for label, keywords in mapping.items():
        for kw in keywords:
            if kw in text:
                return label
    return None


def _build_structured_diagnosis(
    question: str,
    product: str,
    best_similarity: float,
) -> dict[str, Any]:
    """Diagnóstico estructurado con los 3 pilares obligatorios (Fase D1).

    Reemplaza al stub. Extracción determinista por keywords sobre el texto
    normalizado de ``question + product``. El payload nunca se marca
    ``ready=True`` salvo que los 3 pilares (sustrato, estado, exposición)
    estén presentes. Cuando falta info, ``required_validations`` contiene
    instrucciones explícitas para que el agente las solicite.

    Returns:
        dict con el contrato legacy + campos Phase D1
        (``has_substrate``, ``has_state``, ``has_exposure``,
        ``technical_summary``, ``_schema_version="D1"``).
    """
    try:
        from schemas.diagnosis import DiagnosisPayload
    except ImportError:
        from backend.schemas.diagnosis import DiagnosisPayload

    main = _m()
    text = main.normalize_text_value(f"{question or ''} {product or ''}")

    detected_substrate = _detect_pillar(text, _SUBSTRATE_DETECT)
    detected_state = _detect_pillar(text, _STATE_DETECT)
    detected_exposure = _detect_pillar(text, _EXPOSURE_DETECT)

    has_substrate = detected_substrate is not None
    has_state = detected_state is not None
    has_exposure = detected_exposure is not None

    missing: list[str] = []
    if not has_substrate:
        missing.append(
            "Solicitar SUSTRATO: ¿qué material es la superficie? "
            "(metal, concreto, madera, fibrocemento, drywall, etc.)"
        )
    if not has_state:
        missing.append(
            "Solicitar ESTADO ACTUAL: ¿cómo se encuentra hoy? "
            "(oxidado, descascarado, con humedad, agrietado, intacto, etc.)"
        )
    if not has_exposure:
        missing.append(
            "Solicitar NIVEL DE EXPOSICIÓN: ¿interior, exterior, intemperie, "
            "sumergido, alta temperatura, tráfico pesado/liviano?"
        )

    technical_summary: Optional[str] = None
    if has_substrate and has_state and has_exposure:
        technical_summary = (
            f"Sustrato: {detected_substrate} | Estado: {detected_state} | "
            f"Exposición: {detected_exposure}"
        )

    payload = DiagnosisPayload(
        has_substrate=has_substrate,
        has_state=has_state,
        has_exposure=has_exposure,
        missing_info_requests=missing,
        technical_summary=technical_summary,
        detected_substrate=detected_substrate,
        detected_state=detected_state,
        detected_exposure=detected_exposure,
        category=detected_substrate or "general",
    )
    return payload.to_legacy_dict(
        question=question,
        product=product,
        best_similarity=best_similarity,
    )


# ── Indicadores de bicomponente (familias químicas que requieren catalizador) ─
_BICOMPONENT_INDICATORS: list[str] = [
    "epoxic", "epoxi", "epoxy",
    "poliuretano", "polyurethane",
    "polyurea", "poliurea",
]

_CATALYST_KEYWORDS: list[str] = [
    "catalizador", "comp b", "componente b", "endurecedor",
    "hardener", "activator", "activador", "parte b",
]

_PRIMER_KEYWORDS: list[str] = [
    "imprimante", "primer", "anticorrosivo", "wash primer", "interseal",
    "imprim",
]

_SOLVENT_KEYWORDS: list[str] = ["solvente", "thinner", "diluyente"]


def _classify_sku_role(descripcion_norm: str) -> str:
    """Detecta el rol (catalizador/imprimante/solvente/acabado) por keywords."""
    if any(k in descripcion_norm for k in _CATALYST_KEYWORDS):
        return "catalizador"
    if any(k in descripcion_norm for k in _PRIMER_KEYWORDS):
        return "imprimante"
    if any(k in descripcion_norm for k in _SOLVENT_KEYWORDS):
        return "solvente"
    return "acabado"


def _build_structured_technical_guide(
    question: str,
    product: str,
    diagnosis: dict[str, Any],
    expert_notes: list[dict[str, Any]],
    best_similarity: float,
    *,
    rag_chunks: Optional[list[dict[str, Any]]] = None,
    inventory_candidates: Optional[list[dict[str, Any]]] = None,
) -> dict[str, Any]:
    """Guía técnica destilada con SKUs verificados y validación bicomponente.

    Reemplaza al stub. Reglas estrictas:

      - ``approved_skus`` contiene SÓLO SKUs venidos de
        ``inventory_candidates`` (codigo) o ``rag_chunks`` (metadata.sku).
        Cualquier nombre que no provenga de una fuente verificada es
        rechazado.
      - Si se detecta familia química bicomponente (epóxico/poliuretano/
        polyurea) en el contexto y no hay un SKU con rol "catalizador" en
        inventario → ``bicomponent_verified=False`` + alerta crítica
        ``BICOMPONENT_MISSING_CATALYST``. Esto bloquea pricing aguas abajo
        (``pricing_ready=False``, ``pricing_gate="bicomponent_missing_catalyst"``).
      - Las preparaciones de superficie sólo se generan si el diagnóstico
        upstream está completo (``diagnosis.ready==True``).

    Args:
        rag_chunks: chunks devueltos por ``search_technical_chunks``
            (filtrados ya por ``RAG_PGVECTOR_DISTANCE_THRESHOLD``).
        inventory_candidates: rows de ``lookup_inventory_candidates_from_terms``.

    Returns:
        dict con el contrato legacy + campos Phase D1.
    """
    try:
        from schemas.technical_guide import (
            ApprovedSku,
            TechnicalAlert,
            TechnicalGuidePayload,
        )
    except ImportError:
        from backend.schemas.technical_guide import (
            ApprovedSku,
            TechnicalAlert,
            TechnicalGuidePayload,
        )
    try:
        from bicomponents import get_bicomponent_info
    except ImportError:
        from backend.bicomponents import get_bicomponent_info

    main = _m()
    rag_chunks = rag_chunks or []
    inventory_candidates = inventory_candidates or []

    def _norm(value: Any) -> str:
        return main.normalize_text_value(str(value or "")).strip()

    # ─── 1. Construir whitelist de SKUs desde fuentes verificadas ─────────
    approved_skus: list[ApprovedSku] = []
    seen_skus: set[str] = set()

    def _emit_sku(
        sku: str,
        descripcion: str,
        chem: Optional[str],
        source: str,
    ) -> None:
        sku_clean = (sku or "").strip()
        if not sku_clean or sku_clean in seen_skus:
            return
        descripcion_norm = _norm(descripcion or sku_clean)
        role = _classify_sku_role(descripcion_norm)
        try:
            sku_obj = ApprovedSku(
                sku=sku_clean,
                descripcion=descripcion or sku_clean,
                role=role,  # type: ignore[arg-type]
                chemical_family=(chem or None),
                source=source,  # type: ignore[arg-type]
            )
        except Exception:
            # Pydantic rechazó el rol o source — descartar silenciosamente
            return
        seen_skus.add(sku_clean)
        approved_skus.append(sku_obj)

    # Inventory primero (fuente más fuerte: efectivamente comprable)
    for inv in inventory_candidates:
        sku = inv.get("codigo") or inv.get("referencia")
        descripcion = inv.get("descripcion") or inv.get("etiqueta_auditable") or ""
        chem = (
            inv.get("chemical_family")
            or inv.get("familia_quimica")
            or inv.get("familia_producto")
        )
        _emit_sku(sku, descripcion, chem, "inventory")

    # RAG chunks segundo — sólo si exponen un SKU explícito en metadata
    for chunk in rag_chunks:
        meta = chunk.get("metadata") or {}
        sku = (meta.get("sku") or meta.get("codigo") or chunk.get("codigo") or "").strip()
        if not sku:
            continue
        descripcion = (
            meta.get("nombre_comercial")
            or chunk.get("doc_filename")
            or sku
        )
        chem = (
            meta.get("chemical_family")
            or meta.get("canonical_family")
            or chunk.get("familia_producto")
        )
        _emit_sku(sku, descripcion, chem, "rag_chunk")

    # ─── 2. Detección de requerimiento bicomponente ──────────────────────
    family_signals: list[str] = []
    for s in approved_skus:
        if s.chemical_family:
            family_signals.append(_norm(s.chemical_family))
        family_signals.append(_norm(s.descripcion))
    family_signals.append(_norm(product))
    family_signals.append(_norm(question))
    for chunk in rag_chunks:
        meta = chunk.get("metadata") or {}
        for key in ("chemical_family", "canonical_family"):
            value = meta.get(key)
            if value:
                family_signals.append(_norm(value))
    for note in expert_notes or []:
        for key in ("producto_recomendado", "nota_comercial", "contexto_tags"):
            value = note.get(key)
            if value:
                family_signals.append(_norm(value))

    full_text = " ".join(family_signals)
    bicomponent_required = any(ind in full_text for ind in _BICOMPONENT_INDICATORS)

    # Cross-check contra el catálogo curado (BICOMPONENT_CATALOG)
    if not bicomponent_required:
        for s in approved_skus:
            if get_bicomponent_info(s.descripcion):
                bicomponent_required = True
                break

    # ─── 3. Verificar presencia del catalizador en inventario ────────────
    alerts: list[TechnicalAlert] = []
    bicomponent_verified = False
    if bicomponent_required:
        catalyst_in_inventory = any(
            s.role == "catalizador" and s.source == "inventory"
            for s in approved_skus
        )
        if catalyst_in_inventory:
            bicomponent_verified = True
        else:
            alerts.append(
                TechnicalAlert(
                    severity="critical",
                    code="BICOMPONENT_MISSING_CATALYST",
                    message=(
                        "ALERTA TÉCNICA: el sistema detectado es BICOMPONENTE "
                        "(epóxico / poliuretano / polyurea) pero NO se encontró "
                        "el catalizador (Componente B / endurecedor / hardener) "
                        "en el inventario disponible. NO se puede ofrecer este "
                        "sistema sin la pareja completa. Solicitar al área de "
                        "compras o sugerir alternativa monocomponente."
                    ),
                )
            )

    # ─── 4. Pasos de preparación (sólo con diagnóstico completo) ─────────
    prep_steps: list[str] = []
    if (diagnosis or {}).get("ready"):
        substrate = (diagnosis or {}).get("surface_type") or ""
        state = (diagnosis or {}).get("condition") or ""
        if "metal" in substrate:
            if "oxido" in state or "oxidad" in state:
                prep_steps = [
                    "Limpieza mecánica SSPC-SP3 mínimo (cepillo de alambre rotatorio).",
                    "Para inmersión o ambiente severo: chorreado abrasivo SSPC-SP10 (Sa 2.5).",
                    "Eliminar polvo y residuos con aire comprimido seco.",
                    "Aplicar imprimante anticorrosivo dentro de las primeras 4 horas.",
                ]
            else:
                prep_steps = [
                    "Limpieza mecánica SSPC-SP2 / SP3.",
                    "Desengrasado con solvente apropiado.",
                    "Eliminar polvo y residuos.",
                ]
        elif "concreto" in substrate or "fibrocemento" in substrate:
            if "humed" in state or "salitre" in state:
                prep_steps = [
                    "Identificar y eliminar la fuente de humedad ANTES de pintar.",
                    "Lavado con solución desinfectante (hipoclorito 1:10) si hay moho.",
                    "Esperar 28 días de fragua si es concreto nuevo.",
                    "Aplicar imprimante anti-alcalino o sellador anti-humedad según el caso.",
                ]
            else:
                prep_steps = [
                    "Lavar con detergente neutro y enjuagar.",
                    "Reparar grietas con masilla acrílica o estuco.",
                    "Lijar y eliminar polvo.",
                ]
        elif "madera" in substrate:
            prep_steps = [
                "Lijar en sentido de la veta con grano 120-180.",
                "Eliminar polvo con paño seco.",
                "Aplicar sellador para madera antes del acabado.",
            ]

    # ─── 5. Ensamblar el payload ─────────────────────────────────────────
    payload = TechnicalGuidePayload(
        surface_preparation_steps=prep_steps,
        approved_skus=approved_skus,
        bicomponent_required=bicomponent_required,
        bicomponent_verified=bicomponent_verified,
        alerts=alerts,
    )
    return payload.to_legacy_dict(best_similarity=best_similarity)



# ─────────────────────────────────────────────────────────────────────────────
# Expert knowledge retrieval (movido desde main.py)
# ─────────────────────────────────────────────────────────────────────────────

def fetch_expert_knowledge(query: str, limit: int = 8) -> list[dict[str, Any]]:
    """Fetch commercial expert knowledge matching the query context.

    Uses an in-memory cache (refreshed every 120s) to avoid DB round-trips
    on every tool call. With ~50 rows this is negligible memory.
    """
    if not query:
        return []
    main = _m()
    try:
        normalized = main.normalize_text_value(query)
        raw_terms = re.findall(r"[a-z0-9áéíóúñ]+", normalized)
        stop_terms = {
            "para", "con", "sin", "por", "que", "como", "sobre", "entre", "desde",
            "hasta", "este", "esta", "estos", "estas", "solo", "necesito", "quiero",
            "techo", "techos", "pintar", "pintado", "exterior", "interior", "anos",
            "ano", "hace", "viejo", "vieja", "nuevo", "nueva", "usar", "aplicar",
            "producto", "productos", "sistema", "recomendar", "recomendacion",
        }
        terms: list[str] = []
        for term in raw_terms:
            if len(term) < 3 or term in stop_terms or term in terms:
                continue
            terms.append(term)
        if not terms:
            terms = [t for t in raw_terms if len(t) >= 2][:10]
        if not terms:
            return []

        all_rows = main._get_expert_knowledge_cache()

        scored = []
        seen_keys = set()
        anchor_terms = [
            t for t in terms
            if len(t) >= 6 or t in {"eternit", "fibrocemento", "asbesto", "sellomax", "koraza", "intervinil"}
        ]
        for row in all_rows:
            context_text = main.normalize_text_value(row.get("contexto_tags") or "")
            note_text = main.normalize_text_value(row.get("nota_comercial") or "")
            recommended_text = main.normalize_text_value(row.get("producto_recomendado") or "")
            rejected_text = main.normalize_text_value(row.get("producto_desestimado") or "")
            searchable = (
                context_text
                + " " + note_text
                + " " + recommended_text
                + " " + rejected_text
            )
            matched_terms = [t for t in terms if t in searchable]
            if not matched_terms:
                continue

            score = 0.0
            context_hits = 0
            for term in matched_terms:
                score += 1.0
                if term in context_text:
                    score += 2.0
                    context_hits += 1
                elif term in note_text:
                    score += 1.0
                elif term in recommended_text or term in rejected_text:
                    score += 0.4
                if len(term) >= 7:
                    score += 0.35

            anchor_context_hits = sum(1 for term in anchor_terms if term in context_text)
            if anchor_context_hits:
                score += 2.5 * anchor_context_hits
            elif anchor_terms:
                score -= 1.5

            if row.get("tipo") == "alerta_superficie" and context_hits:
                score += 1.5
            if row.get("tipo") == "evitar" and any(term in rejected_text for term in matched_terms):
                score += 0.75

            dedupe_key = (
                row.get("tipo") or "",
                context_text,
                note_text,
                recommended_text,
                rejected_text,
            )
            if dedupe_key in seen_keys:
                continue
            seen_keys.add(dedupe_key)

            if score >= 2.0:
                scored.append((score, len(matched_terms), row))
        scored.sort(key=lambda item: (-item[0], -item[1], -(item[2].get("_ts") or 0)))
        results = []
        for score_val, _match_count, row in scored[:limit]:
            row_copy = dict(row)
            row_copy["_expert_score"] = round(score_val, 2)
            results.append(row_copy)
        return results
    except Exception as exc:
        logger.debug("fetch_expert_knowledge error: %s", exc)
        return []


# ─────────────────────────────────────────────────────────────────────────────
# Candidate extraction & policy derivation (movido desde main.py)
# ─────────────────────────────────────────────────────────────────────────────

def extract_candidate_products_from_rag_context(
    rag_context: str,
    source_file: Optional[str] = None,
    original_question: str = "",
) -> list[str]:
    main = _m()
    candidates: list[str] = []
    # A) Extract explicitly tagged products from RAG chunks
    # Skip FDS/HDS (safety data sheets) — they match broadly but are not
    # product recommendations. Only keep FT (ficha técnica) product tags.
    for match in re.finditer(r"\[PRODUCTO:\s*([^\]]+)\]", rag_context or "", flags=re.IGNORECASE):
        candidate = match.group(1).strip()
        if candidate and candidate not in candidates:
            candidate_upper = candidate.upper()
            if candidate_upper.startswith("FDS") or candidate_upper.startswith("HDS"):
                continue
            candidates.append(candidate)
    # B) Extract brand/product names mentioned in the RAG text that match known portfolio
    if rag_context:
        rag_lower = main.normalize_text_value(rag_context)
        _KNOWN_PRODUCT_NAMES = [
            # Pintuco líneas principales
            "pintucoat", "pintura canchas", "corrotec", "pintulac", "aerocolor", "koraza",
            "viniltex", "pintulux", "domestico", "pinturama", "intervinil", "vinil latex",
            "vinilux", "vinil max", "icolatex", "vinil plus", "pintacrom",
            "pintuco fill", "world color", "wash primer", "imprimante",
            "pintoxido", "pintura trafico", "barniz marino", "barnex", "wood stain",
            "estuco anti humedad", "impercoat", "tela de refuerzo",
            "pintura cielos", "pintuobra", "aislante", "emulsion asfaltica",
            "viniltex banos y cocinas", "viniltex advanced", "viniltex ultralavable",
            "madetec", "construmastic", "pintulac nitro",
            # International / AkzoNobel
            "interseal", "interthane", "intergard", "interfine", "interchar",
            # Impermeabilizantes / selladores
            "aquablock", "aquablock ultra", "sellamur", "siliconite", "sika",
            "koraza elastomerica", "koraza xp", "koraza sol y lluvia",
        ]
        for product_name in _KNOWN_PRODUCT_NAMES:
            if product_name in rag_lower and product_name not in candidates:
                candidates.append(product_name)
    # C) Preserve only explicit commercial names already present in the question.
    # Never infer brand candidates from generic category words.
    if original_question:
        portfolio_candidates = main._derive_portfolio_candidates_from_question(original_question)
        for pc in portfolio_candidates:
            if pc not in candidates:
                candidates.append(pc)
    if source_file:
        normalized_file = re.sub(r"\.pdf$", "", source_file, flags=re.IGNORECASE).strip()
        normalized_file = re.sub(r"\s*\(.*?\)\s*", " ", normalized_file).strip()
        if normalized_file and normalized_file not in candidates:
            candidates.insert(0, normalized_file)
    return candidates[:12]


def _derive_policy_inventory_candidate_terms(
    guide: Optional[dict],
    hard_policies: Optional[dict],
    expert_notes: Optional[list[dict]] = None,
    explicit_product: str = "",
) -> list[str]:
    main = _m()
    candidates: list[str] = []
    seen: set[str] = set()

    def _append(value: Optional[str]) -> None:
        cleaned = (value or "").strip()
        if not cleaned:
            return
        normalized = main.normalize_text_value(cleaned)
        if len(normalized) < 3 or normalized in seen:
            return
        seen.add(normalized)
        candidates.append(cleaned)

    if explicit_product:
        _append(explicit_product)

    for value in (hard_policies or {}).get("required_products") or []:
        for item in _split_policy_items(value):
            _append(item)

    structured_guide = guide or {}
    for value in structured_guide.get("base_or_primer") or []:
        for item in _split_policy_items(value):
            if not _is_tool_policy_item(item):
                _append(item)

    for option in structured_guide.get("finish_options") or []:
        if isinstance(option, dict):
            _append(option.get("producto"))
        else:
            _append(str(option))

    for value in structured_guide.get("commercial_alternatives") or []:
        if isinstance(value, dict):
            _append(value.get("producto"))
        else:
            _append(str(value))

    for note in expert_notes or []:
        note_score = note.get("_expert_score") or note.get("score") or 0
        if note_score < 5.0:
            continue  # Skip low-relevance expert notes to avoid product contamination
        for item in _split_policy_items(note.get("producto_recomendado")):
            if not _is_tool_policy_item(item):
                _append(item)

    return candidates[:12]


def _text_matches_policy_product(text_value: Optional[str], policy_value: Optional[str]) -> bool:
    main = _m()
    text_canonical = canonicalize_technical_product_term(text_value)
    policy_canonical = canonicalize_technical_product_term(policy_value)
    if (
        text_canonical
        and policy_canonical
        and main.normalize_text_value(text_canonical["canonical_label"])
        == main.normalize_text_value(policy_canonical["canonical_label"])
    ):
        return True

    normalized_text = main.normalize_text_value(text_value)
    normalized_policy = main.normalize_text_value(policy_value)
    if not normalized_text or not normalized_policy:
        return False
    if normalized_policy in normalized_text or normalized_text in normalized_policy:
        return True

    policy_tokens = [token for token in normalized_policy.split() if len(token) >= 4]
    if not policy_tokens:
        return False
    matched_tokens = sum(1 for token in policy_tokens if token in normalized_text)
    if len(policy_tokens) == 1:
        return matched_tokens == 1
    return matched_tokens >= max(2, min(len(policy_tokens), 3))


# ─────────────────────────────────────────────────────────────────────────────
# Surface-aware RAG filtering (movido desde main.py)
# ─────────────────────────────────────────────────────────────────────────────

_SURFACE_KEYWORDS: dict[str, list[str]] = {
    "metal": [
        "metal", "metalic", "hierro", "acero", "galvanizado", "galvanizada",
        "reja", "porton", "portón", "teja metalica", "teja metálica",
        "cubierta metalica", "cubierta metálica", "techo metalico", "techo metálico",
        "teja zinc", "lamina", "lámina", "tubo", "tuberia", "tubería",
        "estructura metalica", "estructura metálica", "baranda",
    ],
    "concreto": [
        "concreto", "cemento", "mamposteria", "mampostería", "ladrillo",
        "pared", "muro", "fachada", "estuco", "drywall", "bloque",
    ],
    "madera": [
        "madera", "mdf", "triplex", "puerta madera", "mueble", "closet",
        "piso madera", "deck",
    ],
    "piso": [
        "piso", "bodega", "garaje", "parqueadero", "anden", "andén",
        "cancha", "montacargas",
    ],
    "cubierta": [
        "techo", "terraza", "cubierta", "losa", "plancha", "gotera",
        "impermeabilizar", "fibrocemento", "eternit", "teja",
    ],
    "interior": [
        "interior", "habitacion", "habitación", "alcoba", "sala",
        "comedor", "oficina",
    ],
    "exterior": [
        "exterior", "fachada", "intemperie",
    ],
}


def _infer_surface_types_from_query(question: str, product: str = "") -> list[str]:
    """Detect which surface types the user is asking about from the query text.

    Returns a list like ["metal", "exterior"] that can be used to filter
    RAG profiles via their surface_targets / restricted_surfaces metadata.
    """
    main = _m()
    normalized = main.normalize_text_value(f"{question} {product}")
    surfaces: list[str] = []
    for surface, keywords in _SURFACE_KEYWORDS.items():
        # Check multi-word keywords first (longest match)
        for kw in sorted(keywords, key=len, reverse=True):
            if kw in normalized:
                if surface not in surfaces:
                    surfaces.append(surface)
                break
    return surfaces


def _filter_profiles_by_surface_compatibility(
    profiles: list[dict],
    diagnosed_surfaces: list[str],
    query_text: str = "",
) -> list[str]:
    """Check profiles against diagnosed surfaces and return list of
    canonical_family names that are RESTRICTED for the diagnosed surface.

    Also detects specialty-use-case mismatches: products designed for
    extreme conditions (high temperature, immersion, etc.) when the
    query doesn't mention those conditions.
    """
    main = _m()
    restricted_families: list[str] = []
    if not diagnosed_surfaces or not profiles:
        return restricted_families

    query_norm = main.normalize_text_value(query_text)

    # Specialty condition keywords — if a profile mentions these but the
    # query doesn't, the product is likely wrong for the use case
    _SPECIALTY_CONDITIONS = {
        "alta_temperatura": {
            "profile_signals": ["232", "590", "900", "horno", "caldera", "chimenea", "tuberia de vapor", "alta temperatura", "altas temperaturas"],
            "query_signals": ["temperatura", "horno", "caldera", "chimenea", "tuberia vapor", "escape", "motor", "silenciador"],
        },
        "inmersion": {
            "profile_signals": ["inmersion", "sumergido", "tanque de agua"],
            "query_signals": ["inmersion", "sumergido", "tanque", "piscina"],
        },
    }

    for profile in profiles:
        pj = profile.get("profile_json") or {}
        restricted = pj.get("restricted_surfaces") or []
        guidance_restricted = (pj.get("solution_guidance") or {}).get("restricted_surfaces") or []
        all_restricted = set(main.normalize_text_value(s) for s in restricted + guidance_restricted if s)
        surface_targets = set(main.normalize_text_value(s) for s in (pj.get("surface_targets") or []) if s)
        compatible_surfaces = {
            main.normalize_text_value(surface)
            for surface in diagnosed_surfaces
            if main.normalize_text_value(surface) in surface_targets
        }

        family = profile.get("canonical_family") or ""
        is_restricted = False

        # Check 1: direct surface restriction
        for surface in diagnosed_surfaces:
            surf_norm = main.normalize_text_value(surface)
            if surf_norm in surface_targets:
                continue
            if surf_norm in all_restricted:
                is_restricted = True
                break

        # Check 2: specialty use-case mismatch
        if not is_restricted and query_norm and not compatible_surfaces:
            uses = (pj.get("commercial_context") or {}).get("recommended_uses") or []
            uses_text = main.normalize_text_value(" ".join(str(u) for u in uses))
            for _condition, signals in _SPECIALTY_CONDITIONS.items():
                profile_has_specialty = any(sig in uses_text for sig in signals["profile_signals"])
                query_has_specialty = any(sig in query_norm for sig in signals["query_signals"])
                if profile_has_specialty and not query_has_specialty:
                    is_restricted = True
                    break

        if is_restricted and family not in restricted_families:
            restricted_families.append(family)

    return restricted_families


def _filter_rag_candidates_by_surface_and_policy(
    rag_candidate_names: list[str],
    forbidden_products: list[str],
    surface_restricted_families: list[str],
) -> list[str]:
    """Filter RAG-extracted candidate names against:
      1. Policy forbidden_products (from GLOBAL_TECHNICAL_POLICY_RULES)
      2. Surface-restricted products (from profile metadata)

    Closes the 'fuga' where raw RAG text extraction re-injects products
    that the policy or surface analysis already rejected.
    """
    main = _m()
    filtered: list[str] = []
    for name in rag_candidate_names:
        name_norm = main.normalize_text_value(name)
        if not name_norm:
            continue
        is_forbidden = False
        for forbidden in forbidden_products:
            forbidden_norm = main.normalize_text_value(forbidden)
            if forbidden_norm and (forbidden_norm in name_norm or name_norm in forbidden_norm):
                is_forbidden = True
                break
        if is_forbidden:
            continue
        is_restricted = False
        for family in surface_restricted_families:
            family_norm = main.normalize_text_value(family)
            if family_norm and (family_norm in name_norm or name_norm in family_norm):
                is_restricted = True
                break
        if is_restricted:
            continue
        filtered.append(name)
    return filtered


def _filter_inventory_candidates_by_policy(
    candidates: list[dict],
    hard_policies: Optional[dict],
) -> list[dict]:
    if not candidates:
        return []

    policies = hard_policies or {}
    required_products: list[str] = []
    for value in policies.get("required_products") or []:
        for item in _split_policy_items(value):
            if not _is_tool_policy_item(item) and item not in required_products:
                required_products.append(item)

    forbidden_products: list[str] = []
    for value in policies.get("forbidden_products") or []:
        for item in _split_policy_items(value):
            if not _is_tool_policy_item(item) and item not in forbidden_products:
                forbidden_products.append(item)

    filtered = []
    for candidate in candidates:
        candidate_text = " ".join(
            str(value)
            for value in [
                candidate.get("descripcion"),
                candidate.get("etiqueta_auditable"),
                candidate.get("codigo"),
                candidate.get("marca"),
            ]
            if value
        )
        if any(_text_matches_policy_product(candidate_text, forbidden) for forbidden in forbidden_products):
            continue
        filtered.append(candidate)

    if not filtered:
        return []

    if required_products:
        required_matches = [
            candidate
            for candidate in filtered
            if any(
                _text_matches_policy_product(
                    " ".join(
                        str(value)
                        for value in [
                            candidate.get("descripcion"),
                            candidate.get("etiqueta_auditable"),
                            candidate.get("codigo"),
                            candidate.get("marca"),
                        ]
                        if value
                    ),
                    required,
                )
                for required in required_products
            )
        ]
        if required_matches:
            filtered = required_matches

    return filtered


# ─────────────────────────────────────────────────────────────────────────────
# Inventory candidate lookup (movido desde main.py)
# ─────────────────────────────────────────────────────────────────────────────

def lookup_inventory_candidates_from_terms(
    terms: list[str],
    conversation_context: Optional[dict],
    *,
    allow_portfolio_expansion: bool = True,
) -> list[dict]:
    main = _m()
    seen_codes: set[str] = set()
    resolved: list[dict] = []
    local_context = dict(conversation_context or {})

    # First pass: search with original terms
    for term in terms:
        if not term:
            continue
        rows = main.lookup_product_context(term, main.prepare_product_request_for_search(term))
        for row in rows[:2]:
            code = row.get("codigo_articulo") or row.get("referencia") or row.get("codigo")
            if not code or code in seen_codes:
                continue
            seen_codes.add(code)
            resolved.append(
                {
                    "codigo": code,
                    "descripcion": main.get_exact_product_description(row),
                    "etiqueta_auditable": main.build_product_audit_label(row),
                    "marca": row.get("marca") or row.get("marca_producto"),
                    "presentacion": main.infer_product_presentation_from_row(row),
                    "stock_total": main.parse_numeric_value(row.get("stock_total")),
                    "precio": row.get("precio_venta"),
                    "productos_complementarios": [
                        {
                            "referencia": c.get("companion_referencia"),
                            "descripcion": c.get("companion_descripcion") or c.get("descripcion_inventario"),
                            "tipo": c.get("tipo_relacion"),
                            "proporcion": c.get("proporcion"),
                        }
                        for c in main.fetch_product_companions(code)
                    ],
                }
            )
            local_context["last_product_query"] = term
        if len(resolved) >= 4:
            break

    # Second pass: if first pass found nothing, expand terms using portfolio knowledge.
    if not resolved and allow_portfolio_expansion:
        expanded_terms = main._expand_terms_with_portfolio_knowledge(terms)
        original_normalized = {main.normalize_text_value(t) for t in terms if t}
        new_terms = [t for t in expanded_terms if t not in original_normalized]
        for term in new_terms:
            if not term:
                continue
            rows = main.lookup_product_context(term, main.prepare_product_request_for_search(term))
            for row in rows[:2]:
                code = row.get("codigo_articulo") or row.get("referencia") or row.get("codigo")
                if not code or code in seen_codes:
                    continue
                seen_codes.add(code)
                resolved.append(
                    {
                        "codigo": code,
                        "descripcion": main.get_exact_product_description(row),
                        "etiqueta_auditable": main.build_product_audit_label(row),
                        "marca": row.get("marca") or row.get("marca_producto"),
                        "presentacion": main.infer_product_presentation_from_row(row),
                        "stock_total": main.parse_numeric_value(row.get("stock_total")),
                        "precio": row.get("precio_venta"),
                        "productos_complementarios": [
                            {
                                "referencia": c.get("companion_referencia"),
                                "descripcion": c.get("companion_descripcion") or c.get("descripcion_inventario"),
                                "tipo": c.get("tipo_relacion"),
                                "proporcion": c.get("proporcion"),
                            }
                            for c in main.fetch_product_companions(code)
                        ],
                    }
                )
                local_context["last_product_query"] = term
            if len(resolved) >= 4:
                break

    return resolved[:4]


__all__ = [
    "_build_structured_diagnosis",
    "_build_structured_technical_guide",
    "fetch_expert_knowledge",
    "extract_candidate_products_from_rag_context",
    "_derive_policy_inventory_candidate_terms",
    "_text_matches_policy_product",
    "_infer_surface_types_from_query",
    "_filter_profiles_by_surface_compatibility",
    "_filter_rag_candidates_by_surface_and_policy",
    "_filter_inventory_candidates_by_policy",
    "lookup_inventory_candidates_from_terms",
]
