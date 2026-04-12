import json
from collections import Counter
from datetime import datetime
from pathlib import Path

from sqlalchemy import text

from backend import main as m


RAG_JSON_PATH = Path("artifacts/rag/rag_100_product_audit_2026-04-12.json")
RAG_MD_PATH = Path("artifacts/rag/rag_100_product_audit_2026-04-12.md")
CASE_JSON_PATH = Path("artifacts/agent/new_unique_case_battery_2026-04-12.json")
CASE_MD_PATH = Path("artifacts/agent/new_unique_case_battery_2026-04-12.md")


NEW_CASES = [
    {
        "id": "UC01",
        "title": "Cabina Ascensor Rayada",
        "anchor": "Quiero recuperar una cabina de ascensor en lámina pintada que quedó rayada y opaca por desinfectantes.",
        "turns": [
            "Quiero recuperar una cabina de ascensor en lámina pintada que quedó rayada y opaca por desinfectantes.",
            "Es interior, tráfico alto de personas, no quiero repintarla completa si existe una ruta de mantenimiento seria.",
            "Son 18 metros cuadrados y si sí aplica, necesito cotización formal."
        ],
        "goal": "Evaluar mantenimiento técnico sobre metal pintado interior con desgaste químico liviano.",
    },
    {
        "id": "UC02",
        "title": "Muro Cocina Vapor Grasa",
        "anchor": "Necesito corregir un muro de cocina industrial que se mancha por vapor y grasa cerca a la línea de cocción.",
        "turns": [
            "Necesito corregir un muro de cocina industrial que se mancha por vapor y grasa cerca a la línea de cocción.",
            "Es interior, lavan seguido, y me interesa una solución que aguante limpieza frecuente sin ampollarse.",
            "El frente completo suma 42 metros cuadrados."
        ],
        "goal": "Probar diagnóstico arquitectónico interior con exigencia de lavabilidad y ambiente agresivo liviano.",
    },
    {
        "id": "UC03",
        "title": "Teja Traslúcida Policarbonato",
        "anchor": "Voy a intervenir una cubierta en policarbonato alveolar y necesito saber si se pinta o se protege de otra forma.",
        "turns": [
            "Voy a intervenir una cubierta en policarbonato alveolar y necesito saber si se pinta o se protege de otra forma.",
            "Es exterior total, ya está amarillenta por UV y quiero una respuesta honesta si no conviene pintarla.",
            "El área aproximada es de 27 metros cuadrados."
        ],
        "goal": "Medir si el agente declara gap o limitación técnica en un sustrato menos típico.",
    },
    {
        "id": "UC04",
        "title": "Piso Cuarto Frío",
        "anchor": "Necesito recubrir el piso de un cuarto frío donde lavan con agua y químicos suaves todos los días.",
        "turns": [
            "Necesito recubrir el piso de un cuarto frío donde lavan con agua y químicos suaves todos los días.",
            "Es concreto interior, tráfico de carros de carga manual, y me preocupa el choque térmico con limpieza.",
            "Son 63 metros cuadrados y quiero sistema completo bien aterrizado."
        ],
        "goal": "Forzar evaluación de piso industrial interior con humedad recurrente y exigencia operativa nueva.",
    },
    {
        "id": "UC05",
        "title": "Madera Sauna Exterior",
        "anchor": "Tengo un cerramiento en madera termotratada alrededor de una zona de jacuzzi exterior y quiero protegerlo sin plastificarlo.",
        "turns": [
            "Tengo un cerramiento en madera termotratada alrededor de una zona de jacuzzi exterior y quiero protegerlo sin plastificarlo.",
            "Le pega vapor, algo de sol y salpicadura, pero quiero conservar tacto y veta natural.",
            "El proyecto son 31 metros cuadrados."
        ],
        "goal": "Probar asesoría de madera en ambiente húmedo exterior no igual a deck clásico.",
    },
    {
        "id": "UC06",
        "title": "Revestimiento Fibrocemento Fachada Ventilada",
        "anchor": "Estoy revisando paneles lisos de fibrocemento en una fachada ventilada y necesito saber la ruta correcta de repinte.",
        "turns": [
            "Estoy revisando paneles lisos de fibrocemento en una fachada ventilada y necesito saber la ruta correcta de repinte.",
            "Es exterior, ya tienen acabado viejo cuarteado y debo evitar lijado agresivo por seguridad.",
            "El frente intervenido tiene 86 metros cuadrados."
        ],
        "goal": "Separar fibrocemento arquitectónico de eternit clásico con exigencia de preparación segura.",
    },
    {
        "id": "UC07",
        "title": "Baranda Marina Hotel",
        "anchor": "Necesito sistema anticorrosivo para barandas metálicas de hotel frente al mar con mantenimiento premium.",
        "turns": [
            "Necesito sistema anticorrosivo para barandas metálicas de hotel frente al mar con mantenimiento premium.",
            "Es exterior total, brisa salina constante, y el cliente quiere retención de color y brillo serio.",
            "Son 54 metros cuadrados y si aplica, también quiero cotización."
        ],
        "goal": "Probar ruta industrial/marina de alta estética sin mezclarla con esmalte decorativo simple.",
    },
    {
        "id": "UC08",
        "title": "Muro Sótano Contra Terreno",
        "anchor": "Quiero corregir un muro de sótano que da contra terreno y marca humedad permanente con acabado levantado.",
        "turns": [
            "Quiero corregir un muro de sótano que da contra terreno y marca humedad permanente con acabado levantado.",
            "Es interior, la base está débil y no quiero pintura cosmética porque vuelve a botar sales.",
            "El paño total es de 39 metros cuadrados."
        ],
        "goal": "Medir si el sistema reconoce presión negativa real en ambiente interior distinto a lavandería.",
    },
    {
        "id": "UC09",
        "title": "Cubierta Domo Acrílico",
        "anchor": "Tengo unos domos acrílicos viejos en cubierta y necesito saber si existe recubrimiento válido o si toca reemplazo.",
        "turns": [
            "Tengo unos domos acrílicos viejos en cubierta y necesito saber si existe recubrimiento válido o si toca reemplazo.",
            "Están craquelados por sol y lo más importante es que no me vendan algo que falle al poco tiempo.",
            "Son 12 unidades, equivalente a unos 16 metros cuadrados."
        ],
        "goal": "Forzar respuesta honesta sobre un sustrato posiblemente fuera de ruta.",
    },
    {
        "id": "UC10",
        "title": "Piso Taller Motocicletas",
        "anchor": "Necesito un recubrimiento para el piso de un taller de motos con derrame de gasolina y aceites livianos.",
        "turns": [
            "Necesito un recubrimiento para el piso de un taller de motos con derrame de gasolina y aceites livianos.",
            "Es concreto interior, tráfico peatonal y de motos, y el dueño quiere que se pueda lavar fácil.",
            "El área son 74 metros cuadrados."
        ],
        "goal": "Agregar un caso industrial-comercial nuevo con exposición química ligera y tráfico mixto.",
    },
    {
        "id": "UC11",
        "title": "Tanque Agua Cruda No Potable",
        "anchor": "Necesito proteger por dentro un tanque metálico de agua cruda para proceso, no es agua potable pero sí queda en inmersión.",
        "turns": [
            "Necesito proteger por dentro un tanque metálico de agua cruda para proceso, no es agua potable pero sí queda en inmersión.",
            "Va sumergido permanentemente y necesito que el agente distinga eso de un tanque para consumo humano.",
            "El área mojada es de 44 metros cuadrados."
        ],
        "goal": "Medir si el motor diferencia inmersión no potable de agua potable sin alucinar.",
    },
    {
        "id": "UC12",
        "title": "Cubierta Zinc Envejecida Bodega Agrícola",
        "anchor": "Voy a repintar una cubierta en zinc envejecido de una bodega agrícola y necesito saber la ruta correcta sin que se descascare.",
        "turns": [
            "Voy a repintar una cubierta en zinc envejecido de una bodega agrícola y necesito saber la ruta correcta sin que se descascare.",
            "Está en exterior, tiene oxidación leve en traslapos y bastante radiación solar.",
            "El techo suma 118 metros cuadrados."
        ],
        "goal": "Introducir un caso de zinc envejecido distinto a galvanizado nuevo.",
    },
    {
        "id": "UC13",
        "title": "Fachada Estuco Mineral Centro Histórico",
        "anchor": "Necesito intervenir una fachada de estuco mineral en casa antigua del centro y debo respetar transpirabilidad.",
        "turns": [
            "Necesito intervenir una fachada de estuco mineral en casa antigua del centro y debo respetar transpirabilidad.",
            "La superficie tiene microfisuras y zonas resecas, pero no quiero encapsular humedad con cualquier pintura.",
            "Son 67 metros cuadrados."
        ],
        "goal": "Probar criterio técnico cuando el usuario restringe soluciones por transpirabilidad.",
    },
    {
        "id": "UC14",
        "title": "Señalización Piso Hospital",
        "anchor": "Necesito demarcar rutas peatonales en piso interior de hospital con olor bajo y salida rápida a servicio.",
        "turns": [
            "Necesito demarcar rutas peatonales en piso interior de hospital con olor bajo y salida rápida a servicio.",
            "Es un concreto sellado existente, no quiero algo que obligue a cerrar el área muchos días.",
            "La demarcación total son 190 metros lineales."
        ],
        "goal": "Agregar un caso de demarcación especial distinto a parqueaderos o canchas.",
    },
    {
        "id": "UC15",
        "title": "Portón Con Pintura Electroestática",
        "anchor": "Tengo un portón con pintura electrostática deteriorada y quiero saber si se repara por encima o si toca migrar de sistema.",
        "turns": [
            "Tengo un portón con pintura electrostática deteriorada y quiero saber si se repara por encima o si toca migrar de sistema.",
            "Es exterior, hay pérdida de brillo y pelado puntual, pero no quiero una recomendación incompatible.",
            "El elemento completo tiene 21 metros cuadrados."
        ],
        "goal": "Probar compatibilidad sobre recubrimiento previo especial sin caer en respuesta genérica.",
    },
]


def _safe_get(value, *path):
    current = value
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _as_dict(value):
    return value if isinstance(value, dict) else {}


def _as_list(value):
    if isinstance(value, list):
        return value
    if value is None:
        return []
    return [value]


def _truncate_list(items, limit=8):
    cleaned = [item for item in items if item not in (None, "", [], {})]
    return cleaned[:limit]


def _flatten_text_list(items):
    flattened = []
    for item in _as_list(items):
        if isinstance(item, dict):
            for value in item.values():
                if isinstance(value, str) and value.strip():
                    flattened.append(value.strip())
        elif isinstance(item, str) and item.strip():
            flattened.append(item.strip())
    return flattened


def _missing_fields(profile):
    checks = {
        "display_name": bool(_safe_get(profile, "product_identity", "display_name")),
        "brand": bool(_safe_get(profile, "product_identity", "brand")),
        "portfolio_segment": bool(_safe_get(profile, "product_identity", "portfolio_segment")),
        "surface_targets": bool(_flatten_text_list(profile.get("surface_targets") or _safe_get(profile, "commercial_context", "compatible_surfaces") or _safe_get(profile, "solution_guidance", "recommended_surfaces"))),
        "application_methods": bool(_flatten_text_list(profile.get("application_methods") or _safe_get(profile, "application", "application_methods"))),
        "performance_metrics": bool(_safe_get(profile, "performance")),
        "drying_times": bool(_flatten_text_list(_safe_get(profile, "application", "drying", "notes")) or _safe_get(profile, "application", "drying", "touch_dry") or _safe_get(profile, "application", "drying", "recoat") or _safe_get(profile, "application", "drying", "full_cure")),
        "mixing_ratio": bool(_flatten_text_list(_safe_get(profile, "application", "mixing"))),
        "dilution": bool(_safe_get(profile, "application", "dilution") or _safe_get(profile, "technical_specs", "dilution")),
        "alerts": bool(_flatten_text_list(profile.get("alerts")) or _flatten_text_list(_safe_get(profile, "alerts_detail", "critical")) or _flatten_text_list(_safe_get(profile, "alerts_detail", "dont")) or _flatten_text_list(_safe_get(profile, "alerts_detail", "do"))),
        "diagnostic_questions": bool(_flatten_text_list(profile.get("diagnostic_questions") or _safe_get(profile, "solution_guidance", "diagnostic_questions"))),
        "recommended_system": bool(_safe_get(profile, "solution_guidance")),
        "source_excerpts": bool(_safe_get(profile, "source_excerpts")),
    }
    return [field for field, ok in checks.items() if not ok]


def _build_product_record(row):
    profile = row[5]
    if isinstance(profile, str):
        profile = json.loads(profile)

    performance = _as_dict(_safe_get(profile, "performance"))
    application = _as_dict(_safe_get(profile, "application"))
    solution_guidance = _as_dict(_safe_get(profile, "solution_guidance"))
    alerts = _flatten_text_list(profile.get("alerts") or _safe_get(profile, "alerts_detail", "critical"))
    surfaces = _flatten_text_list(profile.get("surface_targets") or _safe_get(profile, "commercial_context", "compatible_surfaces") or solution_guidance.get("recommended_surfaces"))
    methods = _flatten_text_list(profile.get("application_methods") or application.get("application_methods"))
    drying = _flatten_text_list(_safe_get(profile, "application", "drying", "notes"))
    excerpts = _safe_get(profile, "source_excerpts") or []
    drying_summary = {
        "touch_dry": _safe_get(profile, "application", "drying", "touch_dry"),
        "recoat": _safe_get(profile, "application", "drying", "recoat"),
        "full_cure": _safe_get(profile, "application", "drying", "full_cure"),
        "notes": drying,
    }

    missing = _missing_fields(profile)
    return {
        "canonical_family": row[0],
        "source_doc_filename": row[1],
        "marca": row[2],
        "tipo_documento": row[3],
        "completeness_score": float(row[4] or 0),
        "display_name": _safe_get(profile, "product_identity", "display_name"),
        "aliases": _truncate_list(_as_list(_safe_get(profile, "product_identity", "aliases")), 6),
        "portfolio_segment": _safe_get(profile, "product_identity", "portfolio_segment"),
        "portfolio_subsegment": _safe_get(profile, "product_identity", "portfolio_subsegment"),
        "product_role": _safe_get(profile, "product_identity", "product_role"),
        "schema_version": profile.get("schema_version"),
        "surface_targets": _truncate_list(surfaces, 8),
        "restricted_surfaces": _truncate_list(_flatten_text_list(profile.get("restricted_surfaces") or _safe_get(profile, "commercial_context", "incompatible_surfaces") or solution_guidance.get("restricted_surfaces")), 8),
        "application_methods": _truncate_list(methods, 8),
        "diagnostic_questions": _truncate_list(_flatten_text_list(profile.get("diagnostic_questions") or solution_guidance.get("diagnostic_questions")), 8),
        "dilution": application.get("dilution"),
        "mix_ratio": _truncate_list(_flatten_text_list(_safe_get(profile, "application", "mixing")), 8),
        "drying_times": drying_summary,
        "coverage": performance.get("coverage"),
        "resistances": performance.get("resistances") or performance.get("chemical_resistance"),
        "recommended_system": solution_guidance,
        "alerts": {
            "critical": _truncate_list(alerts, 8),
            "do": _truncate_list(_flatten_text_list(_safe_get(profile, "alerts_detail", "do")), 8),
            "dont": _truncate_list(_flatten_text_list(_safe_get(profile, "alerts_detail", "dont")), 8),
        },
        "source_excerpt_count": len(excerpts),
        "missing_fields": missing,
        "top_level_keys": sorted(list(profile.keys())),
    }


def export_rag_100_products():
    engine = m.get_db_engine()
    with engine.begin() as conn:
        total_ready = conn.execute(text("SELECT COUNT(*) FROM public.agent_technical_profile WHERE extraction_status = 'ready'" )).scalar()
        avg_score = conn.execute(text("SELECT AVG(completeness_score) FROM public.agent_technical_profile WHERE extraction_status = 'ready'" )).scalar()
        rows = conn.execute(text("""
            SELECT canonical_family, source_doc_filename, marca, tipo_documento, completeness_score, profile_json
            FROM public.agent_technical_profile
            WHERE extraction_status = 'ready'
            ORDER BY completeness_score DESC, canonical_family
            LIMIT 100
        """)).fetchall()

    products = [_build_product_record(row) for row in rows]
    missing_counter = Counter()
    segment_counter = Counter()
    brand_counter = Counter()

    for product in products:
        segment_counter[product.get("portfolio_segment") or "sin_segmento"] += 1
        brand_counter[product.get("marca") or "sin_marca"] += 1
        missing_counter.update(product.get("missing_fields") or [])

    payload = {
        "generated_at": datetime.now().isoformat(),
        "source_table": "public.agent_technical_profile",
        "selection": "Top 100 profiles ordered by completeness_score desc, canonical_family",
        "totals": {
            "total_ready_profiles": int(total_ready or 0),
            "exported_profiles": len(products),
            "avg_completeness_score_ready": round(float(avg_score or 0), 4),
        },
        "distribution": {
            "portfolio_segments": dict(segment_counter.most_common()),
            "brands": dict(brand_counter.most_common()),
            "missing_fields": dict(missing_counter.most_common()),
        },
        "products": products,
    }

    RAG_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    RAG_JSON_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# Auditoría de 100 Productos del RAG",
        "",
        f"- Generado: {payload['generated_at']}",
        f"- Tabla fuente: {payload['source_table']}",
        f"- Perfiles ready en total: {payload['totals']['total_ready_profiles']}",
        f"- Perfiles exportados: {payload['totals']['exported_profiles']}",
        f"- Completitud promedio corpus ready: {payload['totals']['avg_completeness_score_ready']}",
        "",
        "## Qué mirar",
        "",
        "- Este documento no evalúa si la recomendación final del agente fue correcta; muestra qué información estructurada sí existe hoy por producto.",
        "- `missing_fields` muestra vacíos claros por perfil: por ejemplo faltan tiempos de secado, dilución, alertas o excerptos fuente.",
        "- Si un producto sale con completitud alta pero igual tiene vacíos críticos, el problema no es solo cantidad de extracción sino calidad de shape.",
        "",
        "## Distribución",
        "",
        "### Segmentos",
        "",
    ]
    for key, value in payload["distribution"]["portfolio_segments"].items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "### Marcas", ""])
    for key, value in payload["distribution"]["brands"].items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "### Faltantes más frecuentes", ""])
    for key, value in list(payload["distribution"]["missing_fields"].items())[:20]:
        lines.append(f"- {key}: {value}")

    lines.extend(["", "## Productos", ""])
    for index, product in enumerate(products, start=1):
        lines.extend([
            f"### {index}. {product.get('display_name') or product['canonical_family']}",
            "",
            f"- Familia canónica: {product['canonical_family']}",
            f"- Documento fuente: {product['source_doc_filename']}",
            f"- Marca: {product.get('marca') or 'sin_marca'}",
            f"- Segmento: {product.get('portfolio_segment') or 'sin_segmento'}",
            f"- Subsegmento: {product.get('portfolio_subsegment') or 'sin_subsegmento'}",
            f"- Rol: {product.get('product_role') or 'sin_rol'}",
            f"- Schema: {product.get('schema_version') or 'sin_schema'}",
            f"- Completitud: {product['completeness_score']}",
            f"- Alias: {', '.join(product.get('aliases') or []) or 'sin_alias'}",
            f"- Superficies: {', '.join(product.get('surface_targets') or []) or 'sin_superficies'}",
            f"- Superficies restringidas: {', '.join(product.get('restricted_surfaces') or []) or 'sin_restricciones_superficie'}",
            f"- Métodos de aplicación: {', '.join(product.get('application_methods') or []) or 'sin_metodos'}",
            f"- Preguntas diagnósticas: {json.dumps(product.get('diagnostic_questions'), ensure_ascii=False) if product.get('diagnostic_questions') not in (None, '', [], {}) else 'sin_preguntas_diagnosticas'}",
            f"- Dilución: {json.dumps(product.get('dilution'), ensure_ascii=False) if product.get('dilution') not in (None, '', [], {}) else 'sin_dilucion'}",
            f"- Relación de mezcla: {json.dumps(product.get('mix_ratio'), ensure_ascii=False) if product.get('mix_ratio') not in (None, '', [], {}) else 'sin_mix_ratio'}",
            f"- Secados: {json.dumps(product.get('drying_times'), ensure_ascii=False) if product.get('drying_times') not in (None, '', [], {}) else 'sin_secados'}",
            f"- Cobertura/rendimiento: {json.dumps(product.get('coverage'), ensure_ascii=False) if product.get('coverage') not in (None, '', [], {}) else 'sin_cobertura'}",
            f"- Resistencias: {json.dumps(product.get('resistances'), ensure_ascii=False) if product.get('resistances') not in (None, '', [], {}) else 'sin_resistencias'}",
            f"- Alertas: {json.dumps(product.get('alerts'), ensure_ascii=False) if product.get('alerts') not in (None, '', [], {}) else 'sin_alertas'}",
            f"- Sistema sugerido: {json.dumps(product.get('recommended_system'), ensure_ascii=False) if product.get('recommended_system') not in (None, '', [], {}) else 'sin_sistema_sugerido'}",
            f"- Source excerpts detectados: {product.get('source_excerpt_count', 0)}",
            f"- Faltantes detectados: {', '.join(product.get('missing_fields') or []) or 'ninguno'}",
            "",
        ])

    RAG_MD_PATH.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
    return payload


def export_new_cases():
    CASE_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now().isoformat(),
        "purpose": "Casos completamente nuevos redactados para evaluación manual o batería futura, distintos a los anchors usados en tests y reportes actuales.",
        "case_count": len(NEW_CASES),
        "cases": NEW_CASES,
    }
    CASE_JSON_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# Batería de Casos Nuevos",
        "",
        f"- Generado: {payload['generated_at']}",
        f"- Casos: {payload['case_count']}",
        "- Nota: estos casos se redactaron con phrasing nuevo para no reciclar los anchors ya usados en tests y reportes previos.",
        "",
    ]
    for case in NEW_CASES:
        lines.extend([
            f"## {case['id']} — {case['title']}",
            "",
            f"- Anchor nuevo: {case['anchor']}",
            f"- Objetivo: {case['goal']}",
            "- Turnos:",
        ])
        for turn in case["turns"]:
            lines.append(f"- {turn}")
        lines.append("")

    CASE_MD_PATH.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
    return payload


def main():
    rag_payload = export_rag_100_products()
    case_payload = export_new_cases()
    print(json.dumps({
        "rag_json": str(RAG_JSON_PATH),
        "rag_md": str(RAG_MD_PATH),
        "case_json": str(CASE_JSON_PATH),
        "case_md": str(CASE_MD_PATH),
        "ready_profiles_total": rag_payload["totals"]["total_ready_profiles"],
        "exported_profiles": rag_payload["totals"]["exported_profiles"],
        "new_cases": case_payload["case_count"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()