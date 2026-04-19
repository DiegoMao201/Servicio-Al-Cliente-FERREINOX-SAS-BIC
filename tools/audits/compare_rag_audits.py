import json
from collections import Counter
from datetime import datetime
from pathlib import Path


BASELINE_PATH = Path("artifacts/rag/snapshots/2026-04-12-pre-reingest/rag_100_product_audit_2026-04-12.json")
CURRENT_PATH = Path("artifacts/rag/rag_100_product_audit_2026-04-12.json")
OUTPUT_JSON_PATH = Path("artifacts/rag/rag_100_product_audit_comparison_2026-04-12.json")
OUTPUT_MD_PATH = Path("artifacts/rag/rag_100_product_audit_comparison_2026-04-12.md")
KEY_FIELDS = [
    "surface_targets",
    "restricted_surfaces",
    "application_methods",
    "diagnostic_questions",
    "alerts",
    "source_excerpts",
    "mixing_ratio",
    "drying_times",
    "dilution",
]


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def build_product_map(products: list[dict]) -> dict[str, dict]:
    result = {}
    for product in products or []:
        canonical_family = product.get("canonical_family")
        if canonical_family:
            result[canonical_family] = product
    return result


def is_present(value) -> bool:
    return value not in (None, "", [], {}, ())


def field_presence(product: dict, field_name: str) -> bool:
    if field_name == "source_excerpts":
        return (product.get("source_excerpt_count") or 0) > 0
    return is_present(product.get(field_name))


def summarize_field_presence(products: list[dict]) -> dict[str, int]:
    summary = {}
    for field_name in KEY_FIELDS:
        summary[field_name] = sum(1 for product in products if field_presence(product, field_name))
    return summary


def compare_products(before_map: dict[str, dict], after_map: dict[str, dict]) -> dict:
    shared_families = sorted(set(before_map) & set(after_map))
    improved = []
    worsened = []
    unchanged = []
    gains_counter = Counter()
    losses_counter = Counter()

    for canonical_family in shared_families:
        before = before_map[canonical_family]
        after = after_map[canonical_family]
        before_missing = set(before.get("missing_fields") or [])
        after_missing = set(after.get("missing_fields") or [])
        gained_fields = sorted(before_missing - after_missing)
        lost_fields = sorted(after_missing - before_missing)
        score_delta = round((after.get("completeness_score") or 0) - (before.get("completeness_score") or 0), 4)

        for field_name in gained_fields:
            gains_counter[field_name] += 1
        for field_name in lost_fields:
            losses_counter[field_name] += 1

        record = {
            "canonical_family": canonical_family,
            "before_score": before.get("completeness_score") or 0,
            "after_score": after.get("completeness_score") or 0,
            "score_delta": score_delta,
            "gained_fields": gained_fields,
            "lost_fields": lost_fields,
            "before_schema": before.get("schema_version"),
            "after_schema": after.get("schema_version"),
        }

        if gained_fields or score_delta > 0:
            improved.append(record)
        elif lost_fields or score_delta < 0:
            worsened.append(record)
        else:
            unchanged.append(record)

    improved.sort(key=lambda item: (len(item["gained_fields"]), item["score_delta"], item["canonical_family"]), reverse=True)
    worsened.sort(key=lambda item: (len(item["lost_fields"]), item["score_delta"], item["canonical_family"]))

    return {
        "shared_families": len(shared_families),
        "improved_count": len(improved),
        "worsened_count": len(worsened),
        "unchanged_count": len(unchanged),
        "gains_counter": dict(gains_counter.most_common()),
        "losses_counter": dict(losses_counter.most_common()),
        "top_improved": improved[:25],
        "top_worsened": worsened[:25],
    }


def main() -> None:
    baseline = load_json(BASELINE_PATH)
    current = load_json(CURRENT_PATH)

    baseline_products = baseline.get("products") or []
    current_products = current.get("products") or []
    baseline_map = build_product_map(baseline_products)
    current_map = build_product_map(current_products)

    baseline_presence = summarize_field_presence(baseline_products)
    current_presence = summarize_field_presence(current_products)
    presence_delta = {
        field_name: current_presence[field_name] - baseline_presence[field_name]
        for field_name in KEY_FIELDS
    }

    comparison = {
        "generated_at": datetime.now().isoformat(),
        "baseline_path": str(BASELINE_PATH),
        "current_path": str(CURRENT_PATH),
        "totals": {
            "baseline_ready_profiles": (baseline.get("totals") or {}).get("total_ready_profiles", 0),
            "current_ready_profiles": (current.get("totals") or {}).get("total_ready_profiles", 0),
            "baseline_exported_profiles": (baseline.get("totals") or {}).get("exported_profiles", 0),
            "current_exported_profiles": (current.get("totals") or {}).get("exported_profiles", 0),
            "baseline_avg_completeness": (baseline.get("totals") or {}).get("avg_completeness_score_ready", 0),
            "current_avg_completeness": (current.get("totals") or {}).get("avg_completeness_score_ready", 0),
            "avg_completeness_delta": round(
                ((current.get("totals") or {}).get("avg_completeness_score_ready", 0) or 0)
                - ((baseline.get("totals") or {}).get("avg_completeness_score_ready", 0) or 0),
                4,
            ),
        },
        "field_presence": {
            "baseline": baseline_presence,
            "current": current_presence,
            "delta": presence_delta,
        },
        "distribution_delta": {
            "missing_fields_before": (baseline.get("distribution") or {}).get("missing_fields", {}),
            "missing_fields_after": (current.get("distribution") or {}).get("missing_fields", {}),
        },
        "product_comparison": compare_products(baseline_map, current_map),
    }

    OUTPUT_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON_PATH.write_text(json.dumps(comparison, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# Comparación de Auditoría RAG",
        "",
        f"- Generado: {comparison['generated_at']}",
        f"- Baseline: {comparison['baseline_path']}",
        f"- Actual: {comparison['current_path']}",
        "",
        "## Totales",
        "",
        f"- Ready baseline: {comparison['totals']['baseline_ready_profiles']}",
        f"- Ready actual: {comparison['totals']['current_ready_profiles']}",
        f"- Completitud promedio baseline: {comparison['totals']['baseline_avg_completeness']}",
        f"- Completitud promedio actual: {comparison['totals']['current_avg_completeness']}",
        f"- Delta completitud promedio: {comparison['totals']['avg_completeness_delta']}",
        "",
        "## Delta de Campos",
        "",
    ]

    for field_name in KEY_FIELDS:
        lines.append(
            f"- {field_name}: {comparison['field_presence']['baseline'][field_name]} -> {comparison['field_presence']['current'][field_name]} (delta {comparison['field_presence']['delta'][field_name]})"
        )

    lines.extend([
        "",
        "## Comparación de Productos",
        "",
        f"- Familias comparables: {comparison['product_comparison']['shared_families']}",
        f"- Mejoraron: {comparison['product_comparison']['improved_count']}",
        f"- Empeoraron: {comparison['product_comparison']['worsened_count']}",
        f"- Sin cambio claro: {comparison['product_comparison']['unchanged_count']}",
        "",
        "### Campos ganados más frecuentes",
        "",
    ])

    for field_name, count in comparison["product_comparison"]["gains_counter"].items():
        lines.append(f"- {field_name}: {count}")

    lines.extend(["", "### Campos perdidos más frecuentes", ""])

    if comparison["product_comparison"]["losses_counter"]:
        for field_name, count in comparison["product_comparison"]["losses_counter"].items():
            lines.append(f"- {field_name}: {count}")
    else:
        lines.append("- Ninguno")

    lines.extend(["", "### Top Mejoras", ""])

    for item in comparison["product_comparison"]["top_improved"][:15]:
        lines.append(
            f"- {item['canonical_family']}: score {item['before_score']} -> {item['after_score']} | ganó {', '.join(item['gained_fields']) or 'sin_campos_nuevos'}"
        )

    lines.extend(["", "### Top Retrocesos", ""])

    if comparison["product_comparison"]["top_worsened"]:
        for item in comparison["product_comparison"]["top_worsened"][:15]:
            lines.append(
                f"- {item['canonical_family']}: score {item['before_score']} -> {item['after_score']} | perdió {', '.join(item['lost_fields']) or 'sin_campos_perdidos'}"
            )
    else:
        lines.append("- Ninguno")

    OUTPUT_MD_PATH.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
    print(json.dumps({
        "comparison_json": str(OUTPUT_JSON_PATH),
        "comparison_md": str(OUTPUT_MD_PATH),
        "avg_delta": comparison["totals"]["avg_completeness_delta"],
        "improved": comparison["product_comparison"]["improved_count"],
        "worsened": comparison["product_comparison"]["worsened_count"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()