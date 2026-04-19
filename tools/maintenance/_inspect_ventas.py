"""Inspeccionar raw_ventas_detalle: ver las primeras filas con todas las columnas."""
import os
from sqlalchemy import create_engine, text

engine = create_engine(os.environ["DATABASE_URL"])

with engine.connect() as c:
    cols = c.execute(text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = 'raw_ventas_detalle' ORDER BY ordinal_position"
    )).fetchall()
    col_names = [r[0] for r in cols]
    print(f"COLUMNAS ({len(col_names)}): {col_names}\n")

    rows = c.execute(text("SELECT * FROM raw_ventas_detalle LIMIT 5")).fetchall()
    for i, row in enumerate(rows):
        print(f"--- Fila {i+1} ---")
        for col, val in zip(col_names, row):
            print(f"  {col:25s} = [{val}]")
        print()

    # Check: what does codigo_articulo look like for a known product
    print("=== Buscando viniltex adv en ventas ===")
    rows = c.execute(text(
        "SELECT codigo_articulo, nombre_articulo, fecha_venta "
        "FROM raw_ventas_detalle WHERE LOWER(nombre_articulo) LIKE '%viniltex adv%' LIMIT 5"
    )).fetchall()
    for r in rows:
        print(f"  codigo=[{r[0]}] nombre=[{r[1]}] fecha=[{r[2]}]")

    # And what does that same product look like in rotacion
    print("\n=== Buscando viniltex adv en rotación ===")
    rows = c.execute(text(
        "SELECT referencia, descripcion FROM raw_rotacion_inventarios "
        "WHERE LOWER(descripcion) LIKE '%viniltex adv%blanco%18%' LIMIT 5"
    )).fetchall()
    for r in rows:
        print(f"  ref=[{r[0]}] desc=[{r[1]}]")
