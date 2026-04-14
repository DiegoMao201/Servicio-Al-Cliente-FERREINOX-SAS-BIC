import json
from pathlib import Path

from sqlalchemy import text

try:
    from backend.main import GLOBAL_TECHNICAL_POLICY_RULES, PRODUCT_TECHNICAL_HARD_RULES, get_db_engine
    from backend.technical_product_canonicalization import canonicalize_technical_product_term, get_technical_product_universe
except ImportError:
    from main import GLOBAL_TECHNICAL_POLICY_RULES, PRODUCT_TECHNICAL_HARD_RULES, get_db_engine
    from technical_product_canonicalization import canonicalize_technical_product_term, get_technical_product_universe


OUT_DIR = Path("artifacts") / "rag_product_universe"
JSON_PATH = OUT_DIR / "rag_product_universe.json"
MD_PATH = OUT_DIR / "rag_product_universe.md"


def collect_policy_terms() -> list[str]:
    terms = []
    for rule in GLOBAL_TECHNICAL_POLICY_RULES:
        for bucket in ("required_products", "forbidden_products"):
            for value in rule.get(bucket) or []:
                terms.append(str(value))
    for key in PRODUCT_TECHNICAL_HARD_RULES:
        terms.append(str(key))
    return terms


def fetch_rag_canonical_families() -> list[str]:
    engine = get_db_engine()
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT DISTINCT canonical_family FROM public.agent_technical_profile WHERE canonical_family IS NOT NULL AND canonical_family <> '' ORDER BY canonical_family")).scalars().all()
    return [str(row) for row in rows if str(row).strip()]


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    universe = {entry["canonical_label"]: dict(entry) for entry in get_technical_product_universe()}
    sources = {label: {"canonical_rules"} for label in universe}

    for term in collect_policy_terms() + fetch_rag_canonical_families():
        resolved = canonicalize_technical_product_term(term)
        if resolved:
            label = resolved["canonical_label"]
            sources.setdefault(label, set()).add("policies_or_rag")
            continue
        label = str(term).strip()
        if not label:
            continue
        if label not in universe:
            universe[label] = {"canonical_label": label, "preferred_lookup_text": label, "brand_filters": [], "aliases": []}
        sources.setdefault(label, set()).add("policies_or_rag")

    payload = []
    for label in sorted(universe):
        item = dict(universe[label])
        item["sources"] = sorted(sources.get(label) or [])
        item["erp_reference_placeholder"] = None
        payload.append(item)

    JSON_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# Universo de productos RAG / políticas",
        "",
        "Este archivo lista familias y nombres canónicos que hoy pueden salir del RAG o de las políticas duras.",
        "Puedes usarlo para mapear referencias ERP o validar alias faltantes.",
        "",
        "| Canonico | Lookup inventario | Marcas | Fuentes |",
        "|---|---|---|---|",
    ]
    for item in payload:
        lines.append(f"| {item['canonical_label']} | {item['preferred_lookup_text']} | {', '.join(item['brand_filters']) or '-'} | {', '.join(item['sources'])} |")
    MD_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"json_path": str(JSON_PATH), "md_path": str(MD_PATH), "total": len(payload)}, ensure_ascii=False))


if __name__ == "__main__":
    main()