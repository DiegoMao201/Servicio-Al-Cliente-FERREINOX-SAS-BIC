"""Cruzar inventario con ventas por DESCRIPCION normalizada (no por referencia)."""
import os, csv, json, re, unicodedata
from pathlib import Path
from sqlalchemy import create_engine, text

engine = create_engine(os.environ["DATABASE_URL"])
ROOT = Path(__file__).resolve().parent


def norm(val: str) -> str:
    t = str(val or "").strip().lower()
    t = unicodedata.normalize("NFKD", t)
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = re.sub(r"[^a-z0-9 ]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


with engine.connect() as c:
    # 1. Build ventas index: nombre_articulo → max(fecha_venta), count ventas
    print("Cargando ventas...")
    ventas = c.execute(text("""
        SELECT nombre_articulo, 
               MAX(fecha_venta) AS ultima_venta,
               SUM(CASE WHEN unidades_vendidas ~ '^-?[0-9.]+$' 
                   THEN unidades_vendidas::numeric ELSE 0 END) AS total_uds,
               COUNT(*) AS n_transacciones
        FROM raw_ventas_detalle
        WHERE codigo_articulo != '0'
        GROUP BY nombre_articulo
    """)).fetchall()
    print(f"  → {len(ventas)} nombres de artículo únicos con ventas")

    # Index by normalized name
    ventas_idx: dict[str, dict] = {}
    for name, last_sale, total_uds, n_tx in ventas:
        key = norm(name)
        if key:
            ventas_idx[key] = {
                "nombre_venta": name,
                "ultima_venta": str(last_sale),
                "total_uds": float(total_uds or 0),
                "n_transacciones": int(n_tx),
            }

    # 2. Load all inventory references
    print("Cargando inventario...")
    inv = c.execute(text("""
        SELECT DISTINCT referencia, descripcion, marca, 
               COALESCE(stock_disponible, 0) AS stock
        FROM vw_inventario_agente
    """)).fetchall()
    print(f"  → {len(inv)} filas de inventario")

    # Group by referencia
    inv_by_ref: dict[str, dict] = {}
    for ref, desc, marca, stock in inv:
        if ref not in inv_by_ref:
            inv_by_ref[ref] = {"descripcion": desc, "marca": marca, "stock_total": 0}
        inv_by_ref[ref]["stock_total"] += (stock or 0)
    print(f"  → {len(inv_by_ref)} referencias únicas")

    # 3. Cross: for each inv ref, find matching venta by normalized description
    matched = 0
    unmatched = 0
    active_1y = 0
    inactive_1y = 0
    results = []

    for ref, info in inv_by_ref.items():
        desc_norm = norm(info["descripcion"])
        venta = ventas_idx.get(desc_norm)

        if venta:
            matched += 1
            last = venta["ultima_venta"]
            if last >= "2025-04-13":  # 1 year ago from today 2026-04-13
                active_1y += 1
                estado = "ACTIVO"
            else:
                inactive_1y += 1
                estado = "INACTIVO"
            results.append({
                "referencia": ref,
                "descripcion": info["descripcion"],
                "marca": info["marca"],
                "stock": info["stock_total"],
                "ultima_venta": last,
                "total_uds_vendidas": venta["total_uds"],
                "n_transacciones": venta["n_transacciones"],
                "estado": estado,
            })
        else:
            unmatched += 1
            results.append({
                "referencia": ref,
                "descripcion": info["descripcion"],
                "marca": info["marca"],
                "stock": info["stock_total"],
                "ultima_venta": "",
                "total_uds_vendidas": 0,
                "n_transacciones": 0,
                "estado": "SIN_VENTAS",
            })

    print(f"\n{'='*60}")
    print(f"CRUCE INVENTARIO vs VENTAS (por descripción)")
    print(f"{'='*60}")
    print(f"Total referencias inventario:     {len(inv_by_ref)}")
    print(f"Con match en ventas:              {matched}")
    print(f"Sin match en ventas:              {unmatched}")
    print(f"  ACTIVOS (venta < 1 año):        {active_1y}")
    print(f"  INACTIVOS (venta > 1 año):      {inactive_1y}")
    print(f"  SIN_VENTAS:                     {unmatched}")
    print(f"")
    purgables = inactive_1y + unmatched
    print(f"PURGABLES (inactivos + sin ventas): {purgables} ({100*purgables/len(inv_by_ref):.1f}%)")
    print(f"QUEDARÍAN ACTIVOS:                  {active_1y} ({100*active_1y/len(inv_by_ref):.1f}%)")

    # Save detail
    out_csv = ROOT / "artifacts" / "rag_product_universe" / "inventario_movimiento.csv"
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with open(out_csv, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        w.writeheader()
        w.writerows(sorted(results, key=lambda x: x["estado"]))
    print(f"\nCSV detalle: {out_csv}")

    # Top inactivos con stock
    print(f"\n=== TOP 20 artículos con STOCK pero SIN VENTAS ===")
    sin_ventas_con_stock = [r for r in results if r["estado"] == "SIN_VENTAS" and r["stock"] > 0]
    sin_ventas_con_stock.sort(key=lambda x: x["stock"], reverse=True)
    for r in sin_ventas_con_stock[:20]:
        print(f"  {r['referencia']} | stock={r['stock']:,.0f} | {r['descripcion']}")
