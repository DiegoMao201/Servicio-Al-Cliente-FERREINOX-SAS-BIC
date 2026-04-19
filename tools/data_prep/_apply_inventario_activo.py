"""Aplica la nueva vista de inventario activo a la BD."""
import os
from sqlalchemy import create_engine, text

engine = create_engine(os.environ["DATABASE_URL"])

SQL = """
-- Tabla de refs activas
CREATE TABLE IF NOT EXISTS public.inventario_refs_activas (
    descripcion_normalizada TEXT PRIMARY KEY,
    ultima_venta DATE NOT NULL,
    total_transacciones INT NOT NULL DEFAULT 0
);

-- Poblar
DELETE FROM public.inventario_refs_activas;
INSERT INTO public.inventario_refs_activas (descripcion_normalizada, ultima_venta, total_transacciones)
SELECT
    public.fn_normalize_text(nombre_articulo) AS descripcion_normalizada,
    MAX(fecha_venta::date) AS ultima_venta,
    COUNT(*) AS total_transacciones
FROM public.raw_ventas_detalle
WHERE NULLIF(TRIM(nombre_articulo), '') IS NOT NULL
  AND codigo_articulo != '0'
GROUP BY public.fn_normalize_text(nombre_articulo)
HAVING MAX(fecha_venta::date) >= CURRENT_DATE - INTERVAL '1 year';

-- Vista filtrada
CREATE OR REPLACE VIEW public.vw_inventario_agente_activo AS
SELECT inv.*
FROM public.vw_inventario_agente inv
WHERE EXISTS (
    SELECT 1
    FROM public.inventario_refs_activas act
    WHERE act.descripcion_normalizada = inv.descripcion_normalizada
);
"""

with engine.begin() as conn:
    for stmt in SQL.split(";"):
        stmt = stmt.strip()
        if stmt:
            conn.execute(text(stmt))
    
    # Verificar
    total_inv = conn.execute(text("SELECT COUNT(DISTINCT referencia) FROM vw_inventario_agente")).scalar()
    total_activas = conn.execute(text("SELECT COUNT(*) FROM inventario_refs_activas")).scalar()
    total_inv_activo = conn.execute(text("SELECT COUNT(DISTINCT referencia) FROM vw_inventario_agente_activo")).scalar()
    
    print(f"Total refs inventario completo:  {total_inv}")
    print(f"Total descripciones activas:     {total_activas}")
    print(f"Total refs inventario activo:    {total_inv_activo}")
    print(f"Reducción:                       {total_inv - total_inv_activo} refs eliminadas ({100*(total_inv - total_inv_activo)/total_inv:.1f}%)")
