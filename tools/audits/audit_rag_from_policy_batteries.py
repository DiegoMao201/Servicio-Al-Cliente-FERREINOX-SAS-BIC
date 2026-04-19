import argparse
import json
import logging
from collections import Counter
from datetime import datetime
from pathlib import Path

from backend import main as m
from test_global_policy_matrix_200 import _scenario_specs as base_specs
from test_global_policy_matrix_multisurface_contradictions import (
    _contradiction_specs as mixed_contradiction_specs,
    _multi_surface_specs,
)
from test_global_policy_matrix_preparation_priority_negation import (
    _double_contradiction_specs,
    _negation_specs,
    _preparation_specs,
    _priority_specs,
)


OUTPUT_MD = Path("artifacts/rag/rag_policy_battery_audit.md")
OUTPUT_JSON = Path("artifacts/rag/rag_policy_battery_audit.json")

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)
logging.getLogger("ferreinox_agent").setLevel(logging.WARNING)


def _safe_list(value):
    if isinstance(value, list):
        return value
    return []


def _normalize(value: str) -> str:
    return m.normalize_text_value(value or "")


def _unique_keep_order(items):
    seen = set()
    result = []
    for item in items:
        cleaned = (item or "").strip()
        if not cleaned:
            continue
        key = _normalize(cleaned)
        if key in seen:
            continue
        seen.add(key)
        result.append(cleaned)
    return result


def _extract_structured_system_products(payload: dict) -> list[str]:
    guide = payload.get("guia_tecnica_estructurada") or {}
    hard = payload.get("politicas_duras_contexto") or {}

    recommended = []
    recommended.extend(_safe_list(hard.get("required_products")))
    recommended.extend(_safe_list(guide.get("base_or_primer")))
    recommended.extend(_safe_list(guide.get("intermediate_steps")))
    for item in _safe_list(guide.get("finish_options")):
        if isinstance(item, dict):
            recommended.append(item.get("producto") or "")
        else:
            recommended.append(str(item))

    return _unique_keep_order(recommended)


def _extract_inventory_candidate_products(payload: dict) -> list[str]:
    inventory = payload.get("productos_inventario_relacionados") or []
    recommended = []
    for item in inventory:
        if isinstance(item, dict):
            recommended.append(item.get("descripcion") or item.get("etiqueta_auditable") or item.get("codigo") or "")
            for comp in _safe_list(item.get("complementarios")):
                if isinstance(comp, dict):
                    recommended.append(comp.get("descripcion") or comp.get("producto") or comp.get("codigo") or "")
                else:
                    recommended.append(str(comp))
    return _unique_keep_order(recommended)


def _extract_forbidden_products(payload: dict) -> list[str]:
    guide = payload.get("guia_tecnica_estructurada") or {}
    hard = payload.get("politicas_duras_contexto") or {}
    forbidden = []
    forbidden.extend(_safe_list(hard.get("forbidden_products")))
    forbidden.extend(_safe_list(guide.get("forbidden_products_or_shortcuts")))
    return _unique_keep_order(forbidden)


def _extract_system_shape(payload: dict) -> dict:
    guide = payload.get("guia_tecnica_estructurada") or {}
    hard = payload.get("politicas_duras_contexto") or {}
    return {
        "preparation_steps": _safe_list(guide.get("preparation_steps")),
        "base_or_primer": _safe_list(guide.get("base_or_primer")),
        "intermediate_steps": _safe_list(guide.get("intermediate_steps")),
        "finish_options": [
            item.get("producto") if isinstance(item, dict) else str(item)
            for item in _safe_list(guide.get("finish_options"))
        ],
        "tools": _safe_list(guide.get("tools")),
        "required_questions": _safe_list(guide.get("required_questions")),
        "policy_names": _safe_list(hard.get("policy_names")),
        "critical_policy_names": _safe_list(hard.get("critical_policy_names")),
        "dominant_policy_names": _safe_list(hard.get("dominant_policy_names")),
        "highest_priority_level": hard.get("highest_priority_level") or "none",
        "mandatory_steps": _safe_list(hard.get("mandatory_steps")),
        "required_tools": _safe_list(hard.get("required_tools")),
        "forbidden_tools": _safe_list(hard.get("forbidden_tools")),
    }


def _simulate_rag_lightweight(question: str) -> dict:
    producto = ""
    search_query = question
    segment_filters = m._infer_portfolio_segments_for_query(question, producto, None)
    marca_filter = None

    industrial_keywords = [
        "industrial", "international", "mpy", "akzonobel", "interseal", "interthane", "intergard",
        "interfine", "interchar", "sspc", "iso 12944", "agua potable", "tanque de agua",
        "inmersion", "sumergido", "nsf", "ansi 61", "ambiente quimico", "proteccion fuego", "intumescente",
    ]
    q_lower = (question + " " + producto).lower()
    if any(keyword in q_lower for keyword in industrial_keywords):
        marca_filter = "international"

    chunks = m.search_technical_chunks(search_query, top_k=6, marca_filter=marca_filter, segment_filters=segment_filters or None)
    guide_chunks = m.search_supporting_technical_guides(search_query, top_k=3, marca_filter=marca_filter, segment_filters=segment_filters or None)
    segment_fallback_used = False
    if not chunks and not guide_chunks and segment_filters:
        chunks = m.search_technical_chunks(search_query, top_k=6, marca_filter=marca_filter)
        guide_chunks = m.search_supporting_technical_guides(search_query, top_k=3, marca_filter=marca_filter)
        segment_fallback_used = True

    if not chunks and not guide_chunks:
        return {
            "encontrado": False,
            "respuesta_rag": None,
            "mensaje": "No encontré información técnica vectorizada para esa consulta.",
        }

    rag_context = m.build_rag_context(chunks, max_chunks=4)
    guide_context = m.build_rag_context(guide_chunks, max_chunks=2)
    source_files = list(dict.fromkeys(c.get("doc_filename", "") for c in chunks if c.get("similarity", 0) >= 0.25))
    best_similarity = max((c.get("similarity", 0) for c in chunks), default=max((c.get("similarity", 0) for c in guide_chunks), default=0))
    canonical_families = list(dict.fromkeys(
        (c.get("metadata") or {}).get("canonical_family") or c.get("familia_producto")
        for c in chunks
        if c.get("similarity", 0) >= 0.25
    ))
    technical_profiles = m.fetch_technical_profiles(canonical_families, source_files, limit=3, segment_filters=segment_filters or None)
    guide_canonical_families = list(dict.fromkeys(
        (c.get("metadata") or {}).get("canonical_family") or c.get("familia_producto")
        for c in guide_chunks
        if c.get("similarity", 0) >= 0.2
    ))
    guide_source_files = list(dict.fromkeys(c.get("doc_filename", "") for c in guide_chunks if c.get("similarity", 0) >= 0.2))
    guide_profiles = m.fetch_technical_profiles(guide_canonical_families, guide_source_files, limit=3, segment_filters=segment_filters or None)

    candidate_product_names = m.extract_candidate_products_from_rag_context(
        rag_context,
        source_files[0] if source_files else None,
        original_question=question,
    )
    inventory_candidates = m.lookup_inventory_candidates_from_terms(candidate_product_names, {}) if candidate_product_names else []

    structured_diagnosis = m._build_structured_diagnosis(question, producto, best_similarity)
    structured_guide = m._build_structured_technical_guide(question, producto, structured_diagnosis, expert_notes=[], best_similarity=best_similarity)
    hard_policies = m._build_hard_policies_for_context(question, producto, structured_diagnosis, structured_guide, expert_notes=[])

    payload = {
        "encontrado": True,
        "respuesta_rag": rag_context,
        "contexto_guias": guide_context,
        "archivos_fuente": source_files,
        "segmentos_portafolio_detectados": segment_filters,
        "segmento_fallback_sin_filtro": segment_fallback_used,
        "mejor_similitud": round(best_similarity, 4),
        "diagnostico_estructurado": structured_diagnosis,
        "guia_tecnica_estructurada": structured_guide,
        "politicas_duras_contexto": hard_policies,
        "preguntas_pendientes": structured_diagnosis.get("required_validations") or [],
    }
    if technical_profiles:
        payload["perfil_tecnico_principal"] = technical_profiles[0].get("profile_json")
        payload["perfiles_tecnicos_relacionados"] = [item.get("profile_json") for item in technical_profiles if item.get("profile_json")]
    if guide_profiles:
        payload["guias_tecnicas_relacionadas"] = [item.get("profile_json") for item in guide_profiles if item.get("profile_json")]
    if inventory_candidates:
        payload["productos_inventario_relacionados"] = [
            {
                "codigo": p.get("codigo"),
                "descripcion": p.get("descripcion"),
                "etiqueta_auditable": p.get("etiqueta_auditable"),
                "marca": p.get("marca"),
                "presentacion": p.get("presentacion"),
                "disponible": bool(p.get("stock_total") and m.parse_numeric_value(p.get("stock_total")) > 0),
                "complementarios": p.get("productos_complementarios") or [],
            }
            for p in inventory_candidates
        ]
    return payload


def _simulate_rag(question: str, use_handler: bool = False) -> dict:
    if use_handler:
        raw = m._handle_tool_consultar_conocimiento_tecnico(
            {"pregunta": question, "producto": ""},
            context={},
            conversation_context={},
        )
        if isinstance(raw, str):
            return json.loads(raw)
        return raw
    return _simulate_rag_lightweight(question)


def _build_catalog() -> list[dict]:
    catalog = []
    for spec in base_specs():
        catalog.append({
            "battery": "base_200",
            "group": "base",
            "name": spec["name"],
            "question": spec["anchor"],
        })
    for spec in _multi_surface_specs():
        catalog.append({
            "battery": "multisurface_320",
            "group": "multi_surface",
            "name": spec["name"],
            "question": spec["anchor"],
        })
    for spec in mixed_contradiction_specs():
        catalog.append({
            "battery": "multisurface_320",
            "group": "contradiction",
            "name": spec["name"],
            "question": spec["anchor"],
        })
    for spec in _preparation_specs():
        catalog.append({
            "battery": "prep_priority_negation_208",
            "group": "preparation",
            "name": spec["name"],
            "question": spec["anchor"],
        })
    for spec in _priority_specs():
        catalog.append({
            "battery": "prep_priority_negation_208",
            "group": "priority",
            "name": spec["name"],
            "question": spec["anchor"],
        })
    for spec in _negation_specs():
        catalog.append({
            "battery": "prep_priority_negation_208",
            "group": "negation",
            "name": spec["name"],
            "question": spec["anchor"],
        })
    for spec in _double_contradiction_specs():
        catalog.append({
            "battery": "prep_priority_negation_208",
            "group": "double_contradiction",
            "name": spec["name"],
            "question": spec["anchor"],
        })
    return catalog


def _summarize_portfolio(records: list[dict]) -> dict:
    recommended_counter = Counter()
    forbidden_counter = Counter()
    policy_counter = Counter()
    critical_counter = Counter()
    finish_counter = Counter()

    for record in records:
        for item in record.get("productos_recomendados") or []:
            recommended_counter[item] += 1
        for item in record.get("productos_portafolio_relacionado") or []:
            recommended_counter[item] += 1
        for item in record.get("productos_prohibidos") or []:
            forbidden_counter[item] += 1
        for item in record.get("policy_names") or []:
            policy_counter[item] += 1
        for item in record.get("critical_policy_names") or []:
            critical_counter[item] += 1
        for item in record.get("finish_options") or []:
            finish_counter[item] += 1

    return {
        "top_recommended": recommended_counter.most_common(25),
        "top_forbidden": forbidden_counter.most_common(25),
        "top_policies": policy_counter.most_common(25),
        "top_critical": critical_counter.most_common(10),
        "top_finish_options": finish_counter.most_common(20),
    }


def _render_md(records: list[dict], portfolio_summary: dict) -> str:
    lines = []
    lines.append("# Auditoria RAG desde baterias de politicas")
    lines.append("")
    lines.append(f"- Generado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"- Escenarios auditados: {len(records)}")
    lines.append("- Fuente: RAG local real + diagnóstico/guía/políticas filtradas para lectura humana")
    lines.append("- Objetivo: ver portafolio sugerido/prohibido y señales de sistema completo sin leer logs interminables")
    lines.append("")

    lines.append("## Vista global")
    lines.append("")
    lines.append("### Productos recomendados mas visibles")
    lines.append("")
    for item, count in portfolio_summary["top_recommended"]:
        lines.append(f"- {item}: {count}")
    lines.append("")

    lines.append("### Productos prohibidos mas visibles")
    lines.append("")
    for item, count in portfolio_summary["top_forbidden"]:
        lines.append(f"- {item}: {count}")
    lines.append("")

    lines.append("### Politicas activas mas frecuentes")
    lines.append("")
    for item, count in portfolio_summary["top_policies"]:
        lines.append(f"- {item}: {count}")
    lines.append("")

    lines.append("### Acabados o familias finales mas repetidas")
    lines.append("")
    for item, count in portfolio_summary["top_finish_options"]:
        lines.append(f"- {item}: {count}")
    lines.append("")

    current_group = None
    for record in records:
        if record["group"] != current_group:
            current_group = record["group"]
            lines.append(f"## Grupo: {current_group}")
            lines.append("")

        lines.append(f"### {record['battery']} :: {record['name']}")
        lines.append("")
        lines.append(f"- Consulta: {record['question']}")
        lines.append(f"- Problema inferido: {record['problem_class'] or 'none'}")
        lines.append(f"- Similitud RAG: {record['mejor_similitud']}")
        lines.append(f"- Prioridad dominante: {record['highest_priority_level']}")
        lines.append(f"- Politicas: {', '.join(record['policy_names']) if record['policy_names'] else 'ninguna'}")
        lines.append(f"- Politicas criticas: {', '.join(record['critical_policy_names']) if record['critical_policy_names'] else 'ninguna'}")
        lines.append(f"- Dominantes: {', '.join(record['dominant_policy_names']) if record['dominant_policy_names'] else 'ninguna'}")
        lines.append(f"- Sistema recomendado estructurado: {', '.join(record['productos_recomendados']) if record['productos_recomendados'] else 'ninguno'}")
        lines.append(f"- Portafolio relacionado por inventario/RAG: {', '.join(record['productos_portafolio_relacionado']) if record['productos_portafolio_relacionado'] else 'ninguno'}")
        lines.append(f"- Productos prohibidos: {', '.join(record['productos_prohibidos']) if record['productos_prohibidos'] else 'ninguno'}")
        lines.append(f"- Base / imprimante: {', '.join(record['base_or_primer']) if record['base_or_primer'] else 'ninguno'}")
        lines.append(f"- Intermedios: {', '.join(record['intermediate_steps']) if record['intermediate_steps'] else 'ninguno'}")
        lines.append(f"- Acabados finales: {', '.join(record['finish_options']) if record['finish_options'] else 'ninguno'}")
        lines.append(f"- Herramientas: {', '.join(record['tools']) if record['tools'] else 'ninguna'}")
        lines.append(f"- Herramientas obligatorias: {', '.join(record['required_tools']) if record['required_tools'] else 'ninguna'}")
        lines.append(f"- Herramientas prohibidas: {', '.join(record['forbidden_tools']) if record['forbidden_tools'] else 'ninguna'}")
        lines.append(f"- Pasos obligatorios: {'; '.join(record['mandatory_steps']) if record['mandatory_steps'] else 'ninguno'}")
        lines.append(f"- Preguntas pendientes: {'; '.join(record['required_questions']) if record['required_questions'] else 'ninguna'}")
        lines.append(f"- Archivos fuente: {', '.join(record['source_files']) if record['source_files'] else 'ninguno'}")
        lines.append("")

    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Audita el RAG real usando los anchors de las baterias de políticas.")
    parser.add_argument("--limit", type=int, default=0, help="Limita la cantidad de escenarios auditados. 0 = todos.")
    parser.add_argument("--group", type=str, default="", help="Filtra por grupo: base, multi_surface, contradiction, preparation, priority, negation, double_contradiction.")
    parser.add_argument("--use-handler", action="store_true", help="Usa el handler completo. Por defecto usa una ruta lightweight con RAG real y menos ruido/costo.")
    args = parser.parse_args()

    records = []
    catalog = _build_catalog()
    if args.group:
        catalog = [item for item in catalog if item["group"] == args.group]
    if args.limit:
        catalog = catalog[: args.limit]

    for item in catalog:
        payload = _simulate_rag(item["question"], use_handler=args.use_handler)
        guide = payload.get("guia_tecnica_estructurada") or {}
        system_shape = _extract_system_shape(payload)
        record = {
            "battery": item["battery"],
            "group": item["group"],
            "name": item["name"],
            "question": item["question"],
            "problem_class": (payload.get("diagnostico_estructurado") or {}).get("problem_class"),
            "mejor_similitud": payload.get("mejor_similitud"),
            "source_files": payload.get("archivos_fuente") or [],
            "productos_recomendados": _extract_structured_system_products(payload),
            "productos_portafolio_relacionado": _extract_inventory_candidate_products(payload),
            "productos_prohibidos": _extract_forbidden_products(payload),
            "base_or_primer": system_shape["base_or_primer"],
            "intermediate_steps": system_shape["intermediate_steps"],
            "finish_options": system_shape["finish_options"],
            "tools": system_shape["tools"],
            "required_tools": system_shape["required_tools"],
            "forbidden_tools": system_shape["forbidden_tools"],
            "mandatory_steps": system_shape["mandatory_steps"],
            "required_questions": system_shape["required_questions"],
            "policy_names": system_shape["policy_names"],
            "critical_policy_names": system_shape["critical_policy_names"],
            "dominant_policy_names": system_shape["dominant_policy_names"],
            "highest_priority_level": system_shape["highest_priority_level"],
            "pricing_gate": guide.get("pricing_gate"),
            "inventory_candidates": payload.get("productos_inventario_relacionados") or [],
        }
        records.append(record)

    portfolio_summary = _summarize_portfolio(records)

    OUTPUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_MD.write_text(_render_md(records, portfolio_summary), encoding="utf-8")
    OUTPUT_JSON.write_text(
        json.dumps({"records": records, "summary": portfolio_summary}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"Escenarios auditados: {len(records)}")
    print(f"Markdown: {OUTPUT_MD}")
    print(f"JSON: {OUTPUT_JSON}")


if __name__ == "__main__":
    main()