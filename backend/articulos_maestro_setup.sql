-- ============================================================================
-- MIGRACIÓN: articulos_maestro + enriquecimiento de vistas de inventario
-- Fuente: articulos.xlsx (22,000+ artículos con clasificación ERP/SAP)
--
-- Ejecutar DESPUÉS de import_articulos_maestro.py
-- ============================================================================

BEGIN;

-- ============================================================================
-- 1. TABLA MAESTRA DE ARTÍCULOS
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.articulos_maestro (
    id bigserial PRIMARY KEY,
    codigo_articulo text,
    referencia text NOT NULL,
    referencia_normalizada text,
    codigo_barras text,
    descripcion text,
    descripcion_adicional text,
    descripcion_ebs text,
    departamento text,
    seccion text,
    familia text,
    subfamilia text,
    marca_erp text,
    linea_erp text,
    proveedor text,
    udm text,
    cat_producto text,
    aplicacion text,
    linea_clasificacion text,
    sublinea text,
    marca_clasificacion text,
    familia_clasificacion text,
    subfamilia_clasificacion text,
    tipo text,
    activo boolean DEFAULT true,
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_articulos_maestro_ref
    ON public.articulos_maestro (referencia);
CREATE INDEX IF NOT EXISTS idx_articulos_maestro_ref_norm
    ON public.articulos_maestro (referencia_normalizada);
CREATE INDEX IF NOT EXISTS idx_articulos_maestro_codigo
    ON public.articulos_maestro (codigo_articulo);

-- ============================================================================
-- 2. VISTA vw_inventario_agente  (ENRIQUECIDA con clasificación)
-- ============================================================================

CREATE OR REPLACE VIEW public.vw_inventario_agente AS
SELECT
    public.fn_digits_only(r.cod_almacen) AS cod_almacen,
    public.fn_map_almacen_nombre(r.cod_almacen) AS almacen_nombre,
    public.fn_normalize_text(r.departamento) AS departamento,
    public.fn_keep_alnum(r.referencia) AS referencia_normalizada,
    TRIM(COALESCE(r.referencia, '')) AS referencia,
    public.fn_normalize_text(r.descripcion) AS descripcion_normalizada,
    TRIM(COALESCE(r.descripcion, '')) AS descripcion,
    public.fn_keep_alnum(r.marca) AS marca_normalizada,
    public.fn_normalize_text(r.marca) AS marca,
    public.fn_parse_numeric(r.stock) AS stock_disponible,
    public.fn_parse_numeric(r.costo_promedio_und) AS costo_promedio_und,
    public.fn_parse_numeric(r.unidades_vendidas) AS unidades_vendidas,
    public.fn_parse_numeric(r.lead_time_proveedor) AS lead_time_proveedor,
    public.fn_parse_numeric(r.historial_ventas) AS historial_ventas,
    -- Columnas de clasificación desde articulos_maestro
    NULLIF(TRIM(COALESCE(am.linea_clasificacion, '')), '') AS linea_clasificacion,
    NULLIF(TRIM(COALESCE(am.sublinea, '')), '') AS sublinea_clasificacion,
    NULLIF(TRIM(COALESCE(am.marca_clasificacion, '')), '') AS marca_clasificacion,
    NULLIF(TRIM(COALESCE(am.familia_clasificacion, '')), '') AS familia_clasificacion,
    NULLIF(TRIM(COALESCE(am.subfamilia_clasificacion, '')), '') AS subfamilia_clasificacion,
    NULLIF(TRIM(COALESCE(am.aplicacion, '')), '') AS aplicacion_clasificacion,
    NULLIF(TRIM(COALESCE(am.cat_producto, '')), '') AS cat_producto,
    NULLIF(TRIM(COALESCE(am.descripcion_ebs, '')), '') AS descripcion_ebs,
    NULLIF(TRIM(COALESCE(am.tipo, '')), '') AS tipo_articulo,
    -- search_blob enriquecido con TODA la metadata de clasificación
    public.fn_normalize_text(
        COALESCE(r.descripcion, '') || ' ' ||
        COALESCE(r.referencia, '') || ' ' ||
        COALESCE(r.marca, '') || ' ' ||
        COALESCE(r.departamento, '') || ' ' ||
        COALESCE(public.fn_map_almacen_nombre(r.cod_almacen), '') || ' ' ||
        COALESCE(am.linea_clasificacion, '') || ' ' ||
        COALESCE(am.sublinea, '') || ' ' ||
        COALESCE(am.marca_clasificacion, '') || ' ' ||
        COALESCE(am.familia_clasificacion, '') || ' ' ||
        COALESCE(am.subfamilia_clasificacion, '') || ' ' ||
        COALESCE(am.aplicacion, '') || ' ' ||
        COALESCE(am.cat_producto, '') || ' ' ||
        COALESCE(am.descripcion_ebs, '') || ' ' ||
        COALESCE(am.tipo, '') || ' ' ||
        COALESCE(am.seccion, '') || ' ' ||
        COALESCE(am.descripcion_adicional, '')
    ) AS search_blob
FROM public.raw_rotacion_inventarios r
LEFT JOIN public.articulos_maestro am
    ON am.referencia_normalizada = public.fn_keep_alnum(r.referencia);


-- ============================================================================
-- 3. VISTA productos  (ENRIQUECIDA — agrega clasificación en search_blob y output)
-- ============================================================================

CREATE OR REPLACE VIEW public.productos AS
SELECT
    referencia_normalizada AS producto_codigo,
    referencia,
    descripcion,
    descripcion_normalizada,
    marca,
    marca_normalizada,
    STRING_AGG(DISTINCT departamento, ', ' ORDER BY departamento) AS departamentos,
    COALESCE(SUM(stock_disponible), 0) AS stock_total,
    AVG(costo_promedio_und) AS costo_promedio_und,
    COALESCE(SUM(unidades_vendidas), 0) AS unidades_vendidas,
    AVG(lead_time_proveedor) AS lead_time_proveedor,
    AVG(historial_ventas) AS historial_ventas,
    STRING_AGG(
        almacen_nombre || ': ' || COALESCE(stock_disponible::text, '0'),
        '; '
        ORDER BY almacen_nombre
    ) FILTER (WHERE COALESCE(stock_disponible, 0) > 0) AS stock_por_tienda,
    -- search_blob enriquecido con clasificación
    public.fn_normalize_text(
        COALESCE(descripcion, '') || ' ' ||
        COALESCE(referencia, '') || ' ' ||
        COALESCE(marca, '') || ' ' ||
        COALESCE(STRING_AGG(DISTINCT departamento, ' ' ORDER BY departamento), '') || ' ' ||
        REPLACE(COALESCE(descripcion, ''), '-', ' ') || ' ' ||
        REPLACE(COALESCE(referencia, ''), '-', ' ') || ' ' ||
        REPLACE(COALESCE(descripcion, ''), '/', ' ') || ' ' ||
        REPLACE(COALESCE(referencia, ''), '/', ' ') || ' ' ||
        COALESCE(MAX(linea_clasificacion), '') || ' ' ||
        COALESCE(MAX(sublinea_clasificacion), '') || ' ' ||
        COALESCE(MAX(marca_clasificacion), '') || ' ' ||
        COALESCE(MAX(familia_clasificacion), '') || ' ' ||
        COALESCE(MAX(subfamilia_clasificacion), '') || ' ' ||
        COALESCE(MAX(aplicacion_clasificacion), '') || ' ' ||
        COALESCE(MAX(cat_producto), '') || ' ' ||
        COALESCE(MAX(descripcion_ebs), '') || ' ' ||
        COALESCE(MAX(tipo_articulo), '')
    ) AS search_blob,
    public.fn_keep_alnum(
        COALESCE(descripcion, '') || ' ' ||
        COALESCE(referencia, '') || ' ' ||
        COALESCE(marca, '')
    ) AS search_compact,
    -- Columnas de clasificación disponibles para el agente
    MAX(linea_clasificacion) AS linea_clasificacion,
    MAX(sublinea_clasificacion) AS sublinea_clasificacion,
    MAX(marca_clasificacion) AS marca_clasificacion,
    MAX(familia_clasificacion) AS familia_clasificacion,
    MAX(aplicacion_clasificacion) AS aplicacion_clasificacion,
    MAX(cat_producto) AS cat_producto,
    MAX(descripcion_ebs) AS descripcion_ebs,
    MAX(tipo_articulo) AS tipo_articulo
FROM public.vw_inventario_agente
GROUP BY
    referencia_normalizada,
    referencia,
    descripcion,
    descripcion_normalizada,
    marca,
    marca_normalizada;


-- ============================================================================
-- 4. RE-CREAR vistas dependientes (sin cambio lógico, pero dependen de las anteriores)
-- ============================================================================

CREATE OR REPLACE VIEW public.vw_agente_producto_disponibilidad AS
SELECT
    referencia_normalizada AS producto_codigo,
    referencia,
    descripcion,
    marca,
    cod_almacen,
    almacen_nombre,
    departamento,
    stock_disponible,
    costo_promedio_und,
    unidades_vendidas,
    lead_time_proveedor,
    historial_ventas,
    linea_clasificacion,
    marca_clasificacion,
    familia_clasificacion,
    aplicacion_clasificacion,
    search_blob
FROM public.vw_inventario_agente;


COMMIT;
