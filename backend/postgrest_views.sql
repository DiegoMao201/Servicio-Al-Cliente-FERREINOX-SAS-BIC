BEGIN;

CREATE EXTENSION IF NOT EXISTS unaccent;

CREATE OR REPLACE FUNCTION public.fn_normalize_text(input_text text)
RETURNS text
LANGUAGE sql
IMMUTABLE
AS $$
    SELECT NULLIF(UPPER(unaccent(TRIM(COALESCE(input_text, '')))), '');
$$;

CREATE OR REPLACE FUNCTION public.fn_keep_alnum(input_text text)
RETURNS text
LANGUAGE sql
IMMUTABLE
AS $$
    SELECT NULLIF(REGEXP_REPLACE(public.fn_normalize_text(input_text), '[^A-Z0-9]', '', 'g'), '');
$$;

CREATE OR REPLACE FUNCTION public.fn_digits_only(input_text text)
RETURNS text
LANGUAGE sql
IMMUTABLE
AS $$
    SELECT NULLIF(REGEXP_REPLACE(COALESCE(input_text, ''), '\D', '', 'g'), '');
$$;

CREATE OR REPLACE FUNCTION public.fn_map_zona_from_serie(serie_value text)
RETURNS text
LANGUAGE sql
IMMUTABLE
AS $$
    SELECT CASE public.fn_digits_only(serie_value)
        WHEN '155' THEN 'PEREIRA'
        WHEN '189' THEN 'PEREIRA'
        WHEN '158' THEN 'PEREIRA'
        WHEN '439' THEN 'PEREIRA'
        WHEN '157' THEN 'MANIZALES'
        WHEN '238' THEN 'MANIZALES'
        WHEN '156' THEN 'ARMENIA'
        ELSE 'SIN_ZONA'
    END;
$$;

CREATE OR REPLACE VIEW public.vw_ventas_netas AS
SELECT
    anio,
    mes,
    fecha_venta,
    public.fn_normalize_text(serie) AS serie,
    public.fn_normalize_text(tipo_documento) AS tipo_documento,
    public.fn_keep_alnum(codigo_vendedor) AS codigo_vendedor,
    public.fn_normalize_text(nom_vendedor) AS nom_vendedor,
    public.fn_keep_alnum(cliente_id) AS cliente_id,
    public.fn_normalize_text(nombre_cliente) AS nombre_cliente,
    public.fn_keep_alnum(codigo_articulo) AS codigo_articulo,
    public.fn_normalize_text(nombre_articulo) AS nombre_articulo,
    public.fn_normalize_text(categoria_producto) AS categoria_producto,
    public.fn_normalize_text(linea_producto) AS linea_producto,
    public.fn_keep_alnum(marca_producto) AS marca_producto,
    CASE
        WHEN public.fn_normalize_text(tipo_documento) LIKE '%NOTA%CREDITO%' THEN valor_venta * -1
        ELSE valor_venta
    END AS valor_venta_neto,
    CASE
        WHEN public.fn_normalize_text(tipo_documento) LIKE '%NOTA%CREDITO%' THEN unidades_vendidas * -1
        ELSE unidades_vendidas
    END AS unidades_vendidas_netas,
    costo_unitario,
    public.fn_normalize_text(super_categoria) AS super_categoria
FROM public.raw_ventas_detalle
WHERE public.fn_normalize_text(tipo_documento) LIKE '%FACTURA%'
   OR public.fn_normalize_text(tipo_documento) LIKE '%NOTA%CREDITO%';

CREATE OR REPLACE VIEW public.vw_albaranes_pendientes AS
WITH albaranes AS (
    SELECT
        public.fn_normalize_text(serie) AS serie,
        public.fn_keep_alnum(cliente_id) AS cliente_id,
        public.fn_keep_alnum(codigo_articulo) AS codigo_articulo,
        public.fn_keep_alnum(codigo_vendedor) AS codigo_vendedor,
        SUM(COALESCE(valor_venta, 0)) AS valor_total,
        SUM(COALESCE(unidades_vendidas, 0)) AS unidades_totales,
        MIN(fecha_venta) AS fecha_primera,
        MAX(fecha_venta) AS fecha_ultima
    FROM public.raw_ventas_detalle
    WHERE public.fn_normalize_text(tipo_documento) LIKE '%ALBARAN%'
    GROUP BY 1, 2, 3, 4
)
SELECT *
FROM albaranes
WHERE COALESCE(valor_total, 0) <> 0;

CREATE OR REPLACE VIEW public.vw_estado_cartera AS
SELECT
    public.fn_normalize_text(serie) AS serie,
    numero_documento,
    fecha_documento,
    fecha_vencimiento,
    public.fn_keep_alnum(cod_cliente) AS cod_cliente,
    public.fn_normalize_text(nombre_cliente) AS nombre_cliente,
    public.fn_keep_alnum(nit) AS nit,
    public.fn_normalize_text(poblacion) AS poblacion,
    public.fn_normalize_text(provincia) AS provincia,
    telefono1,
    telefono2,
    public.fn_normalize_text(nom_vendedor) AS nom_vendedor,
    public.fn_normalize_text(entidad_autoriza) AS entidad_autoriza,
    LOWER(NULLIF(TRIM(COALESCE(email, '')), '')) AS email,
    CASE
        WHEN numero_documento < 0 THEN importe * -1
        ELSE importe
    END AS importe_normalizado,
    descuento,
    cupo_aprobado,
    dias_vencido,
    public.fn_map_zona_from_serie(serie) AS zona
FROM public.raw_cartera_detalle
WHERE public.fn_normalize_text(serie) NOT LIKE '%W%'
  AND public.fn_normalize_text(serie) NOT LIKE '%X%';

CREATE OR REPLACE VIEW public.vw_cuentas_por_pagar AS
SELECT
    public.fn_normalize_text(nombre_proveedor_erp) AS nombre_proveedor_erp,
    public.fn_normalize_text(serie) AS serie,
    public.fn_keep_alnum(num_entrada_erp) AS num_entrada_erp,
    CASE
        WHEN valor_total_erp < 0 AND NULLIF(TRIM(COALESCE(num_factura, '')), '') IS NULL THEN
            'NC-' || COALESCE(public.fn_keep_alnum(doc_erp), 'SIN_DOC') || '-' || ABS(valor_total_erp)::text
        ELSE public.fn_keep_alnum(num_factura)
    END AS num_factura_normalizado,
    public.fn_keep_alnum(doc_erp) AS doc_erp,
    fecha_emision_erp,
    fecha_vencimiento_erp,
    valor_total_erp
FROM public.raw_proveedores_pagos;

CREATE OR REPLACE VIEW public.vw_recaudos AS
SELECT
    anio,
    mes,
    fecha_cobro,
    public.fn_keep_alnum(codigo_vendedor) AS codigo_vendedor,
    valor_cobro
FROM public.raw_cobros_detalle;

COMMIT;