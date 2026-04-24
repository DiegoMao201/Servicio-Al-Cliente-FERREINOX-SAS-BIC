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
  - ``_build_structured_diagnosis``
  - ``_build_structured_technical_guide``

Estos dos últimos eran referenciados desde ``tool_handlers``,
``main.admin_rag_buscar``, ``test_global_policy_matrix*.py``,
``tools/audits/audit_rag_from_policy_batteries.py`` y
``tools/diagnostics/_diag_rag_fachada.py`` pero **nunca tuvieron una
definición** en el repositorio (verificado vía
``git log -p --all -S "def _build_structured_diagnosis"`` → 0 hits).
Los stubs devuelven la estructura mínima esperada por los consumidores
downstream para evitar ``AttributeError`` en producción y tests.
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
# STUBS — TODO: RECONSTRUIR LÓGICA DE NEGOCIO
# ─────────────────────────────────────────────────────────────────────────────
# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║                                                                           ║
# ║   ⚠️  STUBS TEMPORALES  ⚠️                                                ║
# ║                                                                           ║
# ║   Las funciones `_build_structured_diagnosis` y                           ║
# ║   `_build_structured_technical_guide` son referenciadas en todo el       ║
# ║   código (tool_handlers, main.admin_rag_buscar, 4 archivos de tests,     ║
# ║   2 herramientas de auditoría) pero NUNCA tuvieron una `def` en el      ║
# ║   repositorio. Probablemente se perdieron en una refactorización         ║
# ║   anterior al primer commit accesible (2026-04).                         ║
# ║                                                                           ║
# ║   Estos stubs retornan la estructura MÍNIMA esperada por los             ║
# ║   consumidores downstream:                                                ║
# ║                                                                           ║
# ║     - `_build_hard_policies_for_context(...)` lee:                       ║
# ║         diagnosis.get("...")  → consumido pasivamente                    ║
# ║         guide.get("required_validations") / .get("base_or_primer") /    ║
# ║         .get("finish_options") / .get("commercial_alternatives")        ║
# ║                                                                           ║
# ║     - `_derive_policy_inventory_candidate_terms(guide, ...)` lee:        ║
# ║         guide.get("base_or_primer") / .get("finish_options") /          ║
# ║         .get("commercial_alternatives")                                  ║
# ║                                                                           ║
# ║     - `_handle_tool_consultar_conocimiento_tecnico` lee:                ║
# ║         diagnosis.get("required_validations")  → preguntas_pendientes   ║
# ║         (campo expuesto al LLM)                                          ║
# ║                                                                           ║
# ║   Resultado neto: el endpoint funciona, no hay AttributeError, pero    ║
# ║   el motor de diagnóstico estructurado y la guía técnica destilada     ║
# ║   están NEUTRALIZADOS hasta que se reimplementen.                       ║
# ║                                                                           ║
# ║   TODO PARA SESIÓN DEDICADA:                                             ║
# ║     1. Definir el contrato exacto de `diagnosis` y `structured_guide`. ║
# ║     2. Implementar la lógica con base en los keywords usados por       ║
# ║        `_matches_global_policy_rule` (en backend/policies.py).         ║
# ║     3. Cubrir con tests de `test_global_policy_matrix*.py`.            ║
# ║                                                                           ║
# ╚═══════════════════════════════════════════════════════════════════════════╝

_STUB_WARN_KEY = "_rag_helpers_stub_warned"


def _warn_stub_once(name: str) -> None:
    """Emite warning una sola vez por proceso por nombre de stub."""
    state = getattr(_warn_stub_once, _STUB_WARN_KEY, None)
    if state is None:
        state = set()
        setattr(_warn_stub_once, _STUB_WARN_KEY, state)
    if name in state:
        return
    state.add(name)
    logger.warning(
        "rag_helpers.%s() es un STUB temporal — devuelve estructura vacía. "
        "Reimplementar con la lógica de diagnóstico estructurado original.",
        name,
    )


def _build_structured_diagnosis(question: str, product: str, best_similarity: float) -> dict[str, Any]:
    """STUB: reconstruir lógica de negocio.

    Estructura mínima válida consumida por:
      - ``_build_hard_policies_for_context`` (lee claves opcionales)
      - ``tool_handlers._handle_tool_consultar_conocimiento_tecnico``
        (lee ``required_validations``)
      - ``test_global_policy_matrix*.py`` (asserts sobre el dict completo)
    """
    _warn_stub_once("_build_structured_diagnosis")
    return {
        "category": "general",
        "ready": False,
        "system": "",
        "surface_type": "",
        "condition": "",
        "interior_exterior": "",
        "area_m2": None,
        "humidity_source": None,
        "traffic": None,
        "required_validations": [],
        "best_similarity": float(best_similarity or 0.0),
        "question": question or "",
        "product": product or "",
        "_stub": True,
    }


def _build_structured_technical_guide(
    question: str,
    product: str,
    diagnosis: dict[str, Any],
    expert_notes: list[dict[str, Any]],
    best_similarity: float,
) -> dict[str, Any]:
    """STUB: reconstruir lógica de negocio.

    Estructura mínima válida consumida por:
      - ``_derive_policy_inventory_candidate_terms`` (lee
        ``base_or_primer``, ``finish_options``, ``commercial_alternatives``)
      - ``_build_hard_policies_for_context`` (lee claves opcionales)
      - ``tool_handlers._handle_tool_consultar_conocimiento_tecnico`` (re-emite
        el dict como ``guia_tecnica_estructurada``)
    """
    _warn_stub_once("_build_structured_technical_guide")
    return {
        "preparation_steps": [],
        "base_or_primer": [],
        "finish_options": [],
        "commercial_alternatives": [],
        "restrictions": [],
        "pricing_ready": False,
        "pricing_gate": None,
        "best_similarity": float(best_similarity or 0.0),
        "_stub": True,
    }


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
