"""
AUDITORÍA COMPLETA: RAG (agent_technical_profile) vs Canonización vs Inventario ERP

Descarga TODO el inventario en una sola query, luego cruza localmente.
Produce CSV + resumen con CADA familia canónica del RAG y su estado.
"""
from __future__ import annotations

import csv
import json
import os
import re
import sys
import unicodedata
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND = REPO_ROOT / "backend"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from sqlalchemy import create_engine, text

from backend.technical_product_canonicalization import (
    TECHNICAL_PRODUCT_RULES,
    canonicalize_technical_product_term,
)

DATABASE_URL = os.environ.get("DATABASE_URL", "")
if not DATABASE_URL:
    print("ERROR: Falta DATABASE_URL en el entorno.")
    sys.exit(1)

engine = create_engine(DATABASE_URL)

OUTPUT_CSV = REPO_ROOT / "artifacts" / "rag_product_universe" / "audit_rag_vs_inventario.csv"
OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)


def norm(value: str) -> str:
    t = str(value or "").strip().lower()
    t = unicodedata.normalize("NFKD", t)
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = re.sub(r"[^a-z0-9 ]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


# ── 1. Cargar familias canónicas del RAG (1 query) ──
def load_rag_families() -> list[dict]:
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT canonical_family,
                   source_doc_filename,
                   marca,
                   tipo_documento,
                   extraction_status,
                   completeness_score,
                   COALESCE(profile_json -> 'product_identity' ->> 'portfolio_segment', 'portafolio_general') AS segment
            FROM public.agent_technical_profile
            WHERE extraction_status = 'ready'
            ORDER BY canonical_family
        """)).mappings().all()
    return [dict(r) for r in rows]


# ── 2. Descargar TODO el inventario de una vez ──
def load_full_inventory() -> list[dict]:
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT referencia, descripcion, marca,
                   COALESCE(search_blob, '') AS search_blob,
                   COALESCE(stock_disponible, 0) AS stock_disponible
            FROM public.vw_inventario_agente_activo
        """)).mappings().all()
    return [dict(r) for r in rows]


# ── 3. Agrupar inventario por referencia (sumar stock) ──
def build_inventory_index(inv_rows: list[dict]) -> tuple[list[dict], list[str]]:
    """Returns (grouped_items, norm_blobs) aligned by index for fast search."""
    by_ref: dict[str, dict] = {}
    for row in inv_rows:
        ref = row["referencia"]
        if ref not in by_ref:
            by_ref[ref] = {
                "referencia": ref,
                "descripcion": row["descripcion"],
                "marca": row["marca"],
                "search_blob": row["search_blob"],
                "stock_total": 0,
            }
        by_ref[ref]["stock_total"] += row["stock_disponible"]
        # Keep longest search_blob
        if len(row["search_blob"]) > len(by_ref[ref]["search_blob"]):
            by_ref[ref]["search_blob"] = row["search_blob"]
    items = list(by_ref.values())
    blobs = [norm(it["search_blob"] + " " + it["descripcion"]) for it in items]
    return items, blobs


def local_search(tokens: list[str], items: list[dict], blobs: list[str], limit: int = 3) -> list[dict]:
    """Search inventory locally using normalized token matching."""
    if not tokens:
        return []
    matches = []
    for idx, blob in enumerate(blobs):
        if all(tok in blob for tok in tokens):
            matches.append(items[idx])
    matches.sort(key=lambda x: x["stock_total"], reverse=True)
    return matches[:limit]


def search_product_in_inventory(
    search_text: str,
    items: list[dict],
    blobs: list[str],
) -> list[dict]:
    tokens = [t for t in norm(search_text).split() if len(t) >= 2][:6]
    if not tokens:
        return []
    # Try all tokens first
    result = local_search(tokens, items, blobs)
    if result:
        return result
    # Relax: drop last token progressively
    while len(tokens) > 1:
        tokens = tokens[:-1]
        result = local_search(tokens, items, blobs)
        if result:
            return result
    return []


def main():
    print("Cargando familias del RAG...")
    rag_families = load_rag_families()
    print(f"  → {len(rag_families)} perfiles técnicos (ready)")

    print("Descargando inventario completo (1 sola query)...")
    raw_inv = load_full_inventory()
    print(f"  → {len(raw_inv)} filas de inventario descargadas")
    items, blobs = build_inventory_index(raw_inv)
    print(f"  → {len(items)} artículos únicos por referencia")

    results = []
    for i, family_row in enumerate(rag_families):
        family = family_row["canonical_family"]
        source_file = family_row["source_doc_filename"]
        marca = family_row["marca"]
        segment = family_row["segment"]
        tipo_doc = family_row["tipo_documento"]
        score = family_row["completeness_score"]

        # Check canonicalization
        canon_result = canonicalize_technical_product_term(family)
        canon_label = (canon_result or {}).get("canonical_label", "")
        preferred_lookup = (canon_result or {}).get("preferred_lookup_text", "")
        has_canon_rule = bool(canon_result)

        # Search locally: preferred_lookup → family → canon_label
        inv_rows = []
        search_used = ""
        if preferred_lookup:
            inv_rows = search_product_in_inventory(preferred_lookup, items, blobs)
            search_used = preferred_lookup
        if not inv_rows:
            inv_rows = search_product_in_inventory(family, items, blobs)
            search_used = family
        if not inv_rows and canon_label and canon_label != family:
            inv_rows = search_product_in_inventory(canon_label, items, blobs)
            search_used = canon_label

        found_in_inventory = len(inv_rows) > 0
        best_ref = inv_rows[0]["referencia"] if inv_rows else ""
        best_desc = inv_rows[0]["descripcion"] if inv_rows else ""
        best_stock = inv_rows[0]["stock_total"] if inv_rows else 0

        if has_canon_rule and found_in_inventory:
            status = "OK_COMPLETO"
        elif has_canon_rule and not found_in_inventory:
            status = "CANON_SIN_INVENTARIO"
        elif not has_canon_rule and found_in_inventory:
            status = "INVENTARIO_SIN_CANON"
        else:
            status = "SIN_MAPEO"

        results.append({
            "canonical_family": family,
            "source_doc": source_file,
            "marca": marca,
            "tipo_documento": tipo_doc,
            "segment": segment,
            "completeness": score,
            "tiene_regla_canonizacion": "SI" if has_canon_rule else "NO",
            "canonical_label": canon_label,
            "preferred_lookup_text": preferred_lookup,
            "encontrado_en_inventario": "SI" if found_in_inventory else "NO",
            "busqueda_usada": search_used,
            "referencia_erp": best_ref,
            "descripcion_erp": best_desc,
            "stock_total": best_stock,
            "status": status,
        })

    # Write CSV
    fieldnames = list(results[0].keys()) if results else []
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    # Summary
    ok = sum(1 for r in results if r["status"] == "OK_COMPLETO")
    canon_no_inv = sum(1 for r in results if r["status"] == "CANON_SIN_INVENTARIO")
    inv_no_canon = sum(1 for r in results if r["status"] == "INVENTARIO_SIN_CANON")
    sin_mapeo = sum(1 for r in results if r["status"] == "SIN_MAPEO")

    summary = {
        "total_familias_rag": len(results),
        "OK_COMPLETO": ok,
        "CANON_SIN_INVENTARIO": canon_no_inv,
        "INVENTARIO_SIN_CANON": inv_no_canon,
        "SIN_MAPEO": sin_mapeo,
        "output_csv": str(OUTPUT_CSV),
    }
    summary_path = OUTPUT_CSV.with_suffix(".json")
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n{'='*60}")
    print(f"RESULTADO AUDITORÍA RAG vs INVENTARIO")
    print(f"{'='*60}")
    print(f"Total familias RAG:         {len(results)}")
    print(f"  OK_COMPLETO:              {ok} (canonización + inventario)")
    print(f"  CANON_SIN_INVENTARIO:     {canon_no_inv} (tiene regla pero no encuentra ERP)")
    print(f"  INVENTARIO_SIN_CANON:     {inv_no_canon} (encuentra ERP pero sin regla)")
    print(f"  SIN_MAPEO:                {sin_mapeo} (ni canonización ni inventario)")
    print(f"\nCSV: {OUTPUT_CSV}")
    print(f"JSON: {summary_path}")

    # Show problems
    problems = [r for r in results if r["status"] in ("SIN_MAPEO", "CANON_SIN_INVENTARIO")]
    if problems:
        print(f"\n{'='*60}")
        print("FAMILIAS QUE NECESITAN TU REFERENCIA:")
        print(f"{'='*60}")
        for r in problems:
            print(f"  -> {r['canonical_family']}  [{r['marca'] or '?'}]  status={r['status']}")

    # Also show ones without canonization rule
    no_canon = [r for r in results if r["status"] == "INVENTARIO_SIN_CANON"]
    if no_canon:
        print(f"\n{'='*60}")
        print("ENCUENTRAN INVENTARIO PERO SIN REGLA DE CANONIZACIÓN:")
        print(f"{'='*60}")
        for r in no_canon:
            print(f"  -> {r['canonical_family']}  =>  {r['referencia_erp']} | {r['descripcion_erp']}")


if __name__ == "__main__":
    main()
