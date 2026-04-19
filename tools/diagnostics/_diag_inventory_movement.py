"""Diagnóstico: artículos con/sin movimiento de ventas en el último año."""
import os, sys
from sqlalchemy import create_engine, text

DATABASE_URL = os.environ.get("DATABASE_URL", "")
if not DATABASE_URL:
    print("ERROR: DATABASE_URL requerida"); sys.exit(1)

engine = create_engine(DATABASE_URL)

with engine.connect() as c:
    # 1. Total artículos en rotación
    r = c.execute(text("SELECT COUNT(DISTINCT referencia) FROM raw_rotacion_inventarios")).scalar()
    print(f"Total artículos únicos en raw_rotacion: {r}")

    # 2. Total en vista de inventario
    r = c.execute(text("SELECT COUNT(DISTINCT referencia) FROM vw_inventario_agente")).scalar()
    print(f"Total artículos únicos en vw_inventario: {r}")

    # 3. Columnas de raw_ventas_detalle
    cols = c.execute(text(
        "SELECT column_name, data_type FROM information_schema.columns "
        "WHERE table_name = 'raw_ventas_detalle' ORDER BY ordinal_position"
    )).fetchall()
    print(f"\nColumnas raw_ventas_detalle:")
    for col_name, col_type in cols:
        print(f"  {col_name} ({col_type})")

    # 4. Rango de fechas y artículos vendidos
    r = c.execute(text(
        "SELECT MIN(fecha_venta), MAX(fecha_venta), COUNT(DISTINCT codigo_articulo) "
        "FROM raw_ventas_detalle"
    )).fetchone()
    print(f"\nVentas: desde {r[0]} hasta {r[1]}")
    print(f"Artículos únicos con ventas: {r[2]}")

    # 5. Sample
    rows = c.execute(text(
        "SELECT codigo_articulo, nombre_articulo, fecha_venta, unidades_vendidas "
        "FROM raw_ventas_detalle LIMIT 5"
    )).fetchall()
    print("\nEjemplos ventas:")
    for row in rows:
        print(f"  {row}")

    # 6. Artículos en inventario SIN ninguna venta
    r = c.execute(text("""
        SELECT COUNT(DISTINCT ri.referencia)
        FROM raw_rotacion_inventarios ri
        LEFT JOIN raw_ventas_detalle vd ON TRIM(vd.codigo_articulo) = TRIM(ri.referencia)
        WHERE vd.codigo_articulo IS NULL
    """)).scalar()
    print(f"\nArtículos en rotación SIN NINGUNA venta registrada: {r}")

    # 7. Artículos con última venta > 1 año
    r = c.execute(text("""
        WITH ultima_venta AS (
            SELECT TRIM(codigo_articulo) AS ref,
                   MAX(fecha_venta::date) AS last_sale
            FROM raw_ventas_detalle
            GROUP BY TRIM(codigo_articulo)
        )
        SELECT 
            COUNT(*) FILTER (WHERE uv.last_sale >= CURRENT_DATE - INTERVAL '1 year') AS activos_1y,
            COUNT(*) FILTER (WHERE uv.last_sale < CURRENT_DATE - INTERVAL '1 year') AS inactivos_1y,
            COUNT(*) FILTER (WHERE uv.ref IS NULL) AS sin_venta
        FROM raw_rotacion_inventarios ri
        LEFT JOIN ultima_venta uv ON uv.ref = TRIM(ri.referencia)
    """)).fetchone()
    print(f"\n{'='*60}")
    print(f"DIAGNÓSTICO DE MOVIMIENTO (inventario vs ventas)")
    print(f"{'='*60}")
    print(f"Artículos con venta en < 1 año (ACTIVOS):   {r[0]}")
    print(f"Artículos con venta hace > 1 año (INACTIVOS): {r[1]}")
    print(f"Artículos SIN ninguna venta registrada:       {r[2]}")
    total = (r[0] or 0) + (r[1] or 0) + (r[2] or 0)
    purgables = (r[1] or 0) + (r[2] or 0)
    print(f"TOTAL filas rotación:                         {total}")
    print(f"PURGABLES (> 1 año o sin ventas):             {purgables} ({100*purgables/total:.1f}%)")
    print(f"QUEDARÍAN activos:                            {r[0]} ({100*(r[0] or 0)/total:.1f}%)")

    # 8. Lo mismo pero por referencia UNICA (no filas)
    r2 = c.execute(text("""
        WITH ultima_venta AS (
            SELECT TRIM(codigo_articulo) AS ref,
                   MAX(fecha_venta::date) AS last_sale
            FROM raw_ventas_detalle
            GROUP BY TRIM(codigo_articulo)
        ),
        refs AS (
            SELECT DISTINCT TRIM(referencia) AS ref FROM raw_rotacion_inventarios
        )
        SELECT 
            COUNT(*) FILTER (WHERE uv.last_sale >= CURRENT_DATE - INTERVAL '1 year') AS activos_1y,
            COUNT(*) FILTER (WHERE uv.last_sale < CURRENT_DATE - INTERVAL '1 year') AS inactivos_1y,
            COUNT(*) FILTER (WHERE uv.ref IS NULL) AS sin_venta
        FROM refs r
        LEFT JOIN ultima_venta uv ON uv.ref = r.ref
    """)).fetchone()
    print(f"\n{'='*60}")
    print(f"POR REFERENCIA ÚNICA:")
    print(f"{'='*60}")
    print(f"Referencias con venta < 1 año:    {r2[0]}")
    print(f"Referencias inactivas > 1 año:    {r2[1]}")
    print(f"Referencias sin ventas:           {r2[2]}")
    total2 = (r2[0] or 0) + (r2[1] or 0) + (r2[2] or 0)
    purge2 = (r2[1] or 0) + (r2[2] or 0)
    print(f"Total referencias únicas:         {total2}")
    print(f"Purgables:                        {purge2} ({100*purge2/total2:.1f}%)")
    print(f"Quedarían:                        {r2[0]} ({100*(r2[0] or 0)/total2:.1f}%)")
