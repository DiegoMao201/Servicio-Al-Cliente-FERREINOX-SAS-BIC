"""Reglas y políticas técnicas — capa de lógica de negocio.

Módulo extraído de `backend/main.py` durante la Fase C2 (modularización).
Contiene:
- Helpers de matching/negación de queries para reglas globales.
- Splitters/clasificadores de items de política.
- `_build_hard_policies_for_context`: agrega políticas duras (required/forbidden
  products/tools/steps) a partir del diagnóstico, la guía estructurada, las
  notas del experto y `GLOBAL_TECHNICAL_POLICY_RULES`.
- Constantes `RAG_METADATA_CANONICAL_HINTS` / `RAG_METADATA_CHEMICAL_HINTS`
  usadas por el prefilter de RAG.

NOTA sobre dependencias: `_build_hard_policies_for_context` lee la lista
`GLOBAL_TECHNICAL_POLICY_RULES` desde `backend.main` mediante import diferido
(late binding) para evitar el ciclo `main → policies → main` en el momento
de la importación. La lógica interna NO fue modificada; solo movida.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Optional


# ── Normalizador local (réplica funcional de main.normalize_text_value) ───
def _normalize_text_value(text_value: Optional[str]) -> str:
    if not text_value:
        return ""
    normalized = unicodedata.normalize("NFKD", text_value)
    normalized = "".join(character for character in normalized if not unicodedata.combining(character))
    normalized = normalized.lower()
    normalized = re.sub(r"[^a-z0-9./+-]+", " ", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


# ── Matching helpers ──────────────────────────────────────────────────────
def _mention_is_negated_in_query(normalized_query: str, start_index: int) -> bool:
    window = normalized_query[max(0, start_index - 45):start_index]
    negation_cues = [
        " no ", " nunca ", " evita ", " evitar ", " prohibido ", " jamas ", " jamás ",
        " no quiero ", " no usar ", " no voy a usar ", " no pienso usar ", " no aplicar ",
    ]
    return any(cue in f" {window} " for cue in negation_cues)


def _query_matches_token(normalized_query: str, token: str, allow_negated: bool = True) -> bool:
    padded_query = f" {normalized_query} "
    normalized_token = _normalize_text_value(token)
    if not normalized_token:
        return False

    search_candidates = [f" {normalized_token} ", normalized_token]
    for search_token in search_candidates:
        start = padded_query.find(search_token)
        while start != -1:
            if allow_negated or not _mention_is_negated_in_query(padded_query, start):
                return True
            start = padded_query.find(search_token, start + len(search_token))
    return False


def _query_matches_all_tokens(normalized_query: str, tokens: list[str], allow_negated: bool = True) -> bool:
    return all(_query_matches_token(normalized_query, token, allow_negated=allow_negated) for token in tokens or [])


def _query_matches_any_token(normalized_query: str, tokens: list[str], allow_negated: bool = True) -> bool:
    return any(_query_matches_token(normalized_query, token, allow_negated=allow_negated) for token in tokens or [])


def _matches_global_policy_rule(rule: dict, normalized_query: str, diagnosis: dict) -> bool:
    problem_class = diagnosis.get("problem_class")
    problem_classes = rule.get("problem_classes") or set()
    if problem_classes and problem_class not in problem_classes:
        return False
    if rule.get("match_all") and not _query_matches_all_tokens(normalized_query, rule.get("match_all") or []):
        return False
    if rule.get("match_all_non_negated") and not _query_matches_all_tokens(normalized_query, rule.get("match_all_non_negated") or [], allow_negated=False):
        return False
    if rule.get("match_any") and not _query_matches_any_token(normalized_query, rule.get("match_any") or []):
        return False
    if rule.get("match_any_non_negated") and not _query_matches_any_token(normalized_query, rule.get("match_any_non_negated") or [], allow_negated=False):
        return False
    if rule.get("exclude_any") and _query_matches_any_token(normalized_query, rule.get("exclude_any") or []):
        return False
    return bool(problem_classes or rule.get("match_all") or rule.get("match_all_non_negated") or rule.get("match_any") or rule.get("match_any_non_negated"))


# ── Splitters / clasificadores ────────────────────────────────────────────
def _split_policy_items(raw_value: Optional[str]) -> list[str]:
    if not raw_value:
        return []
    cleaned = raw_value.replace("\n", ",")
    chunks = re.split(r"[;,]|\s+\+\s+|\s+y\s+", cleaned, flags=re.IGNORECASE)
    results = []
    for chunk in chunks:
        value = (chunk or "").strip(" .:-")
        normalized = _normalize_text_value(value)
        if len(normalized) < 3:
            continue
        if value not in results:
            results.append(value)
    return results


def _is_tool_policy_item(item: str) -> bool:
    normalized = _normalize_text_value(item)
    tool_tokens = {
        "hidrolavadora", "escoba", "cepillo", "brocha", "rodillo", "lija", "lijas",
        "rasqueta", "espatula", "espátula", "grata", "disco flap", "pulidora",
        "pistola", "airless", "thinner", "solvente", "jabón", "jabon", "hipoclorito",
    }
    return any(token in normalized for token in tool_tokens)


def _extract_forbidden_note_items(note_text: str) -> list[str]:
    items = []
    patterns = [
        r"nunca\s+(?:recomendar|usar|aplicar|incluir|listar ni incluir)\s+(.+?)(?:\.|$)",
        r"prohibido\s+(?:usar|recomendar|incluir)\s+(.+?)(?:\.|$)",
        r"evitar\s+(.+?)(?:\.|$)",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, note_text or "", flags=re.IGNORECASE):
            for item in _split_policy_items(match.group(1)):
                if item not in items:
                    items.append(item)
    return items


# ── Constantes RAG metadata (usadas por el prefilter del search RAG) ──────
RAG_METADATA_CANONICAL_HINTS = {
    "eternit_fibrocemento": ["%sellomax%", "%koraza%"],
    "ladrillo_vista": ["%siliconite%", "%construcleaner%"],
    "metal_pintado_alquidico": ["%wash primer%", "%corrotec%", "%pintoxido%", "%intergard%"],
    "humedad_interior_capilaridad": ["%aquablock%"],
    "humedad_interior_general": ["%aquablock%"],
    "fachada_exterior": ["%koraza%"],
    "metal_oxidado": ["%corrotec%", "%pintoxido%", "%wash primer%"],
    "piso_industrial": ["%pintucoat%", "%intergard 740%", "%intergard 2002%"],
    "madera": ["%barnex%", "%wood stain%", "%barniz%"],
}

RAG_METADATA_CHEMICAL_HINTS = {
    "metal_pintado_alquidico": ["epoxico", "epoxi", "anticorrosivo"],
    "humedad_interior_capilaridad": ["impermeabilizante"],
    "humedad_interior_general": ["impermeabilizante"],
    "fachada_exterior": ["elastomerico", "impermeabilizante"],
    "metal_oxidado": ["anticorrosivo", "wash_primer"],
    "piso_industrial": ["epoxico", "poliuretano"],
    "madera": ["barniz", "protector_madera"],
}


# ── Constructor de políticas duras de contexto ────────────────────────────
def _build_hard_policies_for_context(question: str, product: str, diagnosis: dict, guide: dict, expert_notes: list[dict]) -> dict:
    # Late import: GLOBAL_TECHNICAL_POLICY_RULES vive en main como tabla de
    # datos de gran tamaño y otras partes del sistema lo consultan ahí. Lo
    # importamos en tiempo de llamada para evitar el ciclo con backend.main.
    try:
        from main import GLOBAL_TECHNICAL_POLICY_RULES  # type: ignore[no-redef]
    except ImportError:
        from backend.main import GLOBAL_TECHNICAL_POLICY_RULES  # type: ignore[no-redef]

    policies = {
        "problem_class": diagnosis.get("problem_class"),
        "required_products": [],
        "forbidden_products": [],
        "required_tools": [],
        "forbidden_tools": [],
        "mandatory_steps": [],
        "mandatory_step_signals": [],
        "rules_text": [],
        "policy_names": [],
        "critical_policy_names": [],
        "high_priority_policy_names": [],
        "dominant_policy_names": [],
        "highest_priority_level": "none",
    }

    def _append_unique(bucket: str, value: str):
        cleaned = (value or "").strip()
        if not cleaned:
            return
        if cleaned not in policies[bucket]:
            policies[bucket].append(cleaned)

    for step in (guide.get("preparation_steps") or []):
        _append_unique("mandatory_steps", step)

    for step in (guide.get("preparation_steps") or []):
        lowered_step = _normalize_text_value(step)
        for candidate in ["preparacion humeda", "sellomax", "koraza", "aquablock", "retirar el acabado", "metal desnudo", "intergard 2002", "cuarzo", "interthane", "28 dias", "curado", "construcleaner", "siliconite", "barnex", "wood stain", "poliuretano alto trafico"]:
            if candidate in lowered_step:
                _append_unique("mandatory_step_signals", candidate)

    for note in expert_notes or []:
        note_text = (note.get("nota_comercial") or "").strip()
        if note_text:
            _append_unique("rules_text", note_text)

        # Only inject products into required/forbidden from high-relevance notes.
        # Low-scoring notes still contribute their text (rules_text) for LLM context
        # but should not override product recommendations from better-matched rules.
        note_score = note.get("_expert_score") or 0.0
        inject_products = note_score >= 5.0

        if inject_products:
            for item in _split_policy_items(note.get("producto_recomendado")):
                bucket = "required_tools" if _is_tool_policy_item(item) else "required_products"
                _append_unique(bucket, item)

            explicit_avoid_items = _split_policy_items(note.get("producto_desestimado"))
            note_avoid_items = _extract_forbidden_note_items(note_text)
            for item in explicit_avoid_items + note_avoid_items:
                bucket = "forbidden_tools" if _is_tool_policy_item(item) else "forbidden_products"
                _append_unique(bucket, item)

        normalized_note = _normalize_text_value(note_text)
        for candidate in ["preparacion humeda", "sellomax", "koraza", "aquablock", "metal desnudo", "intergard 2002", "cuarzo", "interthane", "28 dias", "curado", "construcleaner", "siliconite", "barnex", "wood stain", "poliuretano alto trafico", "misma familia", "agua con agua"]:
            if candidate in normalized_note:
                _append_unique("mandatory_step_signals", candidate)

    for forbidden in (guide.get("forbidden_products_or_shortcuts") or []):
        _append_unique("rules_text", forbidden)
        for item in _split_policy_items(forbidden):
            bucket = "forbidden_tools" if _is_tool_policy_item(item) else "forbidden_products"
            _append_unique(bucket, item)

    normalized_query = _normalize_text_value(f"{question} {product}")
    matched_global_required_by_product: dict[str, set[str]] = {}
    matched_global_forbidden_by_product: dict[str, set[str]] = {}

    def _track_rule_product(bucket: dict[str, set[str]], value: str, rule_name: str):
        normalized_value = _normalize_text_value(value)
        if not normalized_value:
            return
        bucket.setdefault(normalized_value, set()).add(rule_name)

    for rule in GLOBAL_TECHNICAL_POLICY_RULES:
        if not _matches_global_policy_rule(rule, normalized_query, diagnosis):
            continue
        rule_name = rule.get("name") or "regla_contextual"
        _append_unique("policy_names", rule_name)
        priority = _normalize_text_value(rule.get("priority") or "normal")
        if priority == "critical":
            _append_unique("critical_policy_names", rule_name)
        elif priority == "high":
            _append_unique("high_priority_policy_names", rule_name)
        for value in rule.get("required_products") or []:
            _append_unique("required_products", value)
            _track_rule_product(matched_global_required_by_product, value, rule_name)
        for value in rule.get("forbidden_products") or []:
            _append_unique("forbidden_products", value)
            _track_rule_product(matched_global_forbidden_by_product, value, rule_name)
        for value in rule.get("required_tools") or []:
            _append_unique("required_tools", value)
        for value in rule.get("forbidden_tools") or []:
            _append_unique("forbidden_tools", value)
        for value in rule.get("mandatory_steps") or []:
            _append_unique("mandatory_steps", value)
        for value in rule.get("mandatory_step_signals") or []:
            _append_unique("mandatory_step_signals", value)
        for value in rule.get("rules_text") or []:
            _append_unique("rules_text", value)

    if any(token in normalized_query for token in ["eternit", "fibrocemento", "asbesto"]):
        _append_unique("mandatory_steps", "Preparación húmeda obligatoria; nunca lijar en seco ni rasquetear.")
        _append_unique("mandatory_step_signals", "preparacion humeda")

    if policies["critical_policy_names"]:
        policies["dominant_policy_names"] = list(policies["critical_policy_names"])
        policies["highest_priority_level"] = "critical"
    elif policies["high_priority_policy_names"]:
        policies["dominant_policy_names"] = list(policies["high_priority_policy_names"])
        policies["highest_priority_level"] = "high"
    elif policies["policy_names"]:
        policies["dominant_policy_names"] = [policies["policy_names"][0]]
        policies["highest_priority_level"] = "normal"

    # ── Resolve contradictions: product in both required AND forbidden ─────
    # GLOBAL_TECHNICAL_POLICY_RULES are authoritative (already filtered by
    # problem_class).  Expert notes may inject conflicting recommendations
    # from different contexts (e.g., interior-humidity rule forbids Koraza
    # while facade rule requires it).  Use the global rules as tiebreaker.
    required_set = {_normalize_text_value(p) for p in policies["required_products"]}
    forbidden_set = {_normalize_text_value(p) for p in policies["forbidden_products"]}
    norm_to_original_req = {_normalize_text_value(p): p for p in policies["required_products"]}
    norm_to_original_forb = {_normalize_text_value(p): p for p in policies["forbidden_products"]}
    conflicts = required_set & forbidden_set
    if conflicts:
        # Also collect what the structured guide recommends
        guide_product_norms: set[str] = set()
        for opt in guide.get("finish_options") or []:
            if isinstance(opt, dict) and opt.get("producto"):
                guide_product_norms.add(_normalize_text_value(opt["producto"]))
        for primer_text in guide.get("base_or_primer") or []:
            guide_product_norms.add(_normalize_text_value(primer_text))

        for norm_product in conflicts:
            required_rule_names = matched_global_required_by_product.get(norm_product, set())
            forbidden_rule_names = matched_global_forbidden_by_product.get(norm_product, set())
            in_global_req = bool(required_rule_names)
            in_global_forb = bool(forbidden_rule_names)
            in_guide = norm_product in guide_product_norms

            # If two matched global policies intentionally disagree for the same
            # product, preserve both sides. The tests assert this accumulation in
            # mixed-surface and double-contradiction scenarios.
            if in_global_req and in_global_forb:
                continue

            if in_global_req and not in_global_forb:
                # Global rule requires it → remove from forbidden
                original = norm_to_original_forb.get(norm_product)
                if original and original in policies["forbidden_products"]:
                    policies["forbidden_products"].remove(original)
            elif in_global_forb and not in_global_req:
                # Global rule forbids it → remove from required
                original = norm_to_original_req.get(norm_product)
                if original and original in policies["required_products"]:
                    policies["required_products"].remove(original)
            elif in_guide:
                # Structured guide recommends it → favour required
                original = norm_to_original_forb.get(norm_product)
                if original and original in policies["forbidden_products"]:
                    policies["forbidden_products"].remove(original)
            else:
                # Ambiguous → remove from required (conservative: do not mandate)
                original = norm_to_original_req.get(norm_product)
                if original and original in policies["required_products"]:
                    policies["required_products"].remove(original)

    return policies


__all__ = [
    "_mention_is_negated_in_query",
    "_query_matches_token",
    "_query_matches_all_tokens",
    "_query_matches_any_token",
    "_matches_global_policy_rule",
    "_split_policy_items",
    "_is_tool_policy_item",
    "_extract_forbidden_note_items",
    "_build_hard_policies_for_context",
    "RAG_METADATA_CANONICAL_HINTS",
    "RAG_METADATA_CHEMICAL_HINTS",
]
