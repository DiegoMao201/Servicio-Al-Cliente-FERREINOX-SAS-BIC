"""
Genera CSV de validación para los 203 INVENTARIO_SIN_CANON.
El usuario llena la columna REFERENCIA_CORRECTA y generamos las reglas.
Marca matches sospechosos automáticamente.
"""
import csv, os, re, unicodedata
from pathlib import Path
from sqlalchemy import create_engine, text

REPO_ROOT = Path(__file__).resolve().parents[2]
engine = create_engine(os.environ["DATABASE_URL"])


def norm(val):
    t = str(val or "").strip().lower()
    t = unicodedata.normalize("NFKD", t)
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = re.sub(r"[^a-z0-9 ]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


# Load audit results
audit_csv = REPO_ROOT / "artifacts" / "rag_product_universe" / "audit_rag_vs_inventario.csv"
with open(audit_csv, encoding="utf-8-sig") as f:
    reader = csv.DictReader(f)
    audit_rows = [r for r in reader if r["status"] == "INVENTARIO_SIN_CANON"]

print(f"Total INVENTARIO_SIN_CANON: {len(audit_rows)}")

# Load active inventory for better matching
with engine.connect() as c:
    inv_rows = c.execute(text("""
        SELECT DISTINCT referencia, descripcion, marca,
               COALESCE(SUM(stock_disponible), 0) AS stock
        FROM vw_inventario_agente_activo
        GROUP BY referencia, descripcion, marca
        ORDER BY stock DESC
    """)).fetchall()

inv_items = [{"referencia": r[0], "descripcion": r[1], "marca": r[2], "stock": r[3]} for r in inv_rows]
inv_blobs = [norm(f"{it['descripcion']} {it['referencia']} {it['marca']}") for it in inv_items]

print(f"Inventario activo: {len(inv_items)} refs únicas")


def smart_search(family_name, top_n=3):
    """Search with progressively longer tokens, prioritizing description match."""
    tokens = [t for t in norm(family_name).split() if len(t) >= 3]
    if not tokens:
        return []
    
    # Try all tokens
    for n_tokens in range(len(tokens), 0, -1):
        search_tokens = tokens[:n_tokens]
        matches = []
        for idx, blob in enumerate(inv_blobs):
            if all(tok in blob for tok in search_tokens):
                matches.append(inv_items[idx])
        if matches:
            matches.sort(key=lambda x: x["stock"], reverse=True)
            return matches[:top_n]
    return []


def assess_match_quality(family, match_desc):
    """Score how likely the match is correct."""
    fam_norm = norm(family)
    desc_norm = norm(match_desc)
    fam_tokens = set(fam_norm.split())
    desc_tokens = set(desc_norm.split())
    
    # Remove very short tokens and numbers for overlap
    fam_sig = {t for t in fam_tokens if len(t) >= 3 and not t.isdigit()}
    desc_sig = {t for t in desc_tokens if len(t) >= 3 and not t.isdigit()}
    
    if not fam_sig:
        return "SOSPECHOSO"
    
    overlap = fam_sig & desc_sig
    ratio = len(overlap) / len(fam_sig) if fam_sig else 0
    
    if ratio >= 0.5:
        return "PROBABLE_OK"
    elif ratio >= 0.25:
        return "REVISAR"
    else:
        return "SOSPECHOSO"


# Process each
results = []
for row in audit_rows:
    family = row["canonical_family"]
    segment = row["segment"]
    source_doc = row["source_doc"]
    
    # Re-search with better algorithm
    matches = smart_search(family, top_n=3)
    
    match1 = matches[0] if len(matches) >= 1 else {}
    match2 = matches[1] if len(matches) >= 2 else {}
    match3 = matches[2] if len(matches) >= 3 else {}
    
    quality = assess_match_quality(family, match1.get("descripcion", "")) if match1 else "SIN_MATCH"
    
    results.append({
        "segmento": segment,
        "familia_rag": family,
        "source_doc": source_doc,
        "calidad_match": quality,
        "match1_ref": match1.get("referencia", ""),
        "match1_desc": match1.get("descripcion", ""),
        "match1_stock": match1.get("stock", 0),
        "match2_ref": match2.get("referencia", ""),
        "match2_desc": match2.get("descripcion", ""),
        "match3_ref": match3.get("referencia", ""),
        "match3_desc": match3.get("descripcion", ""),
        "REFERENCIA_CORRECTA": "",
        "TEXTO_BUSQUEDA_INVENTARIO": "",
    })

# Sort by segment then quality
quality_order = {"PROBABLE_OK": 0, "REVISAR": 1, "SOSPECHOSO": 2, "SIN_MATCH": 3}
results.sort(key=lambda r: (r["segmento"], quality_order.get(r["calidad_match"], 9), r["familia_rag"]))

# Write
out_csv = REPO_ROOT / "artifacts" / "rag_product_universe" / "validacion_canon_faltantes.csv"
with open(out_csv, "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=list(results[0].keys()))
    w.writeheader()
    w.writerows(results)

# Summary
from collections import Counter
by_quality = Counter(r["calidad_match"] for r in results)
by_segment = Counter(r["segmento"] for r in results)

print(f"\n{'='*60}")
print(f"RESUMEN VALIDACIÓN")
print(f"{'='*60}")
print(f"Total productos sin canonización: {len(results)}")
print(f"\nPor calidad de match automático:")
for q, n in sorted(by_quality.items(), key=lambda x: quality_order.get(x[0], 9)):
    print(f"  {q}: {n}")
print(f"\nPor segmento:")
for s, n in sorted(by_segment.items()):
    print(f"  {s}: {n}")
print(f"\nCSV: {out_csv}")
print(f"\nINSTRUCCIONES:")
print(f"1. Abre el CSV")
print(f"2. Revisa match1_ref / match1_desc")
print(f"3. Si es correcto, copia match1_ref a REFERENCIA_CORRECTA")
print(f"4. Si es incorrecto, pon la referencia real en REFERENCIA_CORRECTA")
print(f"5. En TEXTO_BUSQUEDA_INVENTARIO pon el texto que quieres que el agente use para buscar")
