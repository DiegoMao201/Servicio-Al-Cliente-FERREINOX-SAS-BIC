"""Comparar formato de referencia entre rotación y ventas."""
import os
from sqlalchemy import create_engine, text

engine = create_engine(os.environ["DATABASE_URL"])

with engine.connect() as c:
    print("=== SAMPLE raw_rotacion_inventarios.referencia ===")
    rows = c.execute(text(
        "SELECT DISTINCT referencia FROM raw_rotacion_inventarios ORDER BY referencia LIMIT 20"
    )).fetchall()
    for r in rows:
        print(f"  [{r[0]}]")

    print("\n=== SAMPLE raw_ventas_detalle.codigo_articulo ===")
    rows = c.execute(text(
        "SELECT DISTINCT codigo_articulo FROM raw_ventas_detalle ORDER BY codigo_articulo LIMIT 20"
    )).fetchall()
    for r in rows:
        print(f"  [{r[0]}]")

    # Try matching with some known sales ref
    print("\n=== Ventas top 10 refs más vendidas ===")
    rows = c.execute(text("""
        SELECT codigo_articulo, nombre_articulo, COUNT(*) AS n
        FROM raw_ventas_detalle
        GROUP BY codigo_articulo, nombre_articulo
        ORDER BY n DESC LIMIT 10
    """)).fetchall()
    for r in rows:
        print(f"  [{r[0]}] {r[1]} (n={r[2]})")

    # Check if those exist in rotacion
    print("\n=== Buscando esos códigos en rotación ===")
    for r in rows[:5]:
        code = r[0].strip()
        found = c.execute(text(
            "SELECT referencia, descripcion FROM raw_rotacion_inventarios "
            "WHERE TRIM(referencia) = :code OR referencia LIKE :pat LIMIT 3"
        ), {"code": code, "pat": f"%{code}%"}).fetchall()
        if found:
            for f in found:
                print(f"  MATCH: ventas [{code}] -> rotacion [{f[0]}] {f[1]}")
        else:
            print(f"  NO MATCH: ventas [{code}]")

    # Check referencia format in rotacion for a known product
    print("\n=== Rotación: buscando 'viniltex' ===")
    rows = c.execute(text(
        "SELECT referencia, descripcion FROM raw_rotacion_inventarios "
        "WHERE LOWER(descripcion) LIKE '%viniltex adv%' LIMIT 5"
    )).fetchall()
    for r in rows:
        print(f"  [{r[0]}] {r[1]}")
