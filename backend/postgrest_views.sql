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

CREATE OR REPLACE FUNCTION public.fn_parse_numeric(input_text text)
RETURNS numeric
LANGUAGE plpgsql
IMMUTABLE
AS $$
DECLARE
    cleaned text;
BEGIN
    cleaned := NULLIF(TRIM(COALESCE(input_text, '')), '');
    IF cleaned IS NULL THEN
        RETURN NULL;
    END IF;

    cleaned := REGEXP_REPLACE(cleaned, '[^0-9,.-]', '', 'g');
    IF cleaned = '' OR cleaned IN ('-', '.', ',') THEN
        RETURN NULL;
    END IF;

    IF POSITION(',' IN cleaned) > 0 AND POSITION('.' IN cleaned) > 0 THEN
        cleaned := REPLACE(cleaned, '.', '');
        cleaned := REPLACE(cleaned, ',', '.');
    ELSIF POSITION(',' IN cleaned) > 0 THEN
        cleaned := REPLACE(cleaned, ',', '.');
    END IF;

    RETURN cleaned::numeric;
EXCEPTION
    WHEN others THEN
        RETURN NULL;
END;
$$;

CREATE OR REPLACE FUNCTION public.fn_parse_integer(input_text text)
RETURNS integer
LANGUAGE plpgsql
IMMUTABLE
AS $$
DECLARE
    numeric_value numeric;
BEGIN
    numeric_value := public.fn_parse_numeric(input_text);
    IF numeric_value IS NULL THEN
        RETURN NULL;
    END IF;
    RETURN numeric_value::integer;
END;
$$;

CREATE OR REPLACE FUNCTION public.fn_parse_date(input_text text)
RETURNS date
LANGUAGE plpgsql
IMMUTABLE
AS $$
DECLARE
    cleaned text;
BEGIN
    cleaned := NULLIF(TRIM(COALESCE(input_text, '')), '');
    IF cleaned IS NULL THEN
        RETURN NULL;
    END IF;

    cleaned := LEFT(cleaned, 10);
    RETURN cleaned::date;
EXCEPTION
    WHEN others THEN
        RETURN NULL;
END;
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
    public.fn_parse_integer(anio) AS anio,
    public.fn_parse_integer(mes) AS mes,
    public.fn_parse_date(fecha_venta) AS fecha_venta,
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
        WHEN public.fn_normalize_text(tipo_documento) LIKE '%NOTA%CREDITO%' THEN public.fn_parse_numeric(valor_venta) * -1
        ELSE public.fn_parse_numeric(valor_venta)
    END AS valor_venta_neto,
    CASE
        WHEN public.fn_normalize_text(tipo_documento) LIKE '%NOTA%CREDITO%' THEN public.fn_parse_numeric(unidades_vendidas) * -1
        ELSE public.fn_parse_numeric(unidades_vendidas)
    END AS unidades_vendidas_netas,
    public.fn_parse_numeric(costo_unitario) AS costo_unitario,
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
        SUM(COALESCE(public.fn_parse_numeric(valor_venta), 0)) AS valor_total,
        SUM(COALESCE(public.fn_parse_numeric(unidades_vendidas), 0)) AS unidades_totales,
        MIN(public.fn_parse_date(fecha_venta)) AS fecha_primera,
        MAX(public.fn_parse_date(fecha_venta)) AS fecha_ultima
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
    public.fn_parse_integer(numero_documento) AS numero_documento,
    public.fn_parse_date(fecha_documento) AS fecha_documento,
    public.fn_parse_date(fecha_vencimiento) AS fecha_vencimiento,
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
        WHEN public.fn_parse_integer(numero_documento) < 0 THEN public.fn_parse_numeric(importe) * -1
        ELSE public.fn_parse_numeric(importe)
    END AS importe_normalizado,
    public.fn_parse_numeric(descuento) AS descuento,
    public.fn_parse_numeric(cupo_aprobado) AS cupo_aprobado,
    public.fn_parse_integer(dias_vencido) AS dias_vencido,
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
        WHEN public.fn_parse_numeric(valor_total_erp) < 0 AND NULLIF(TRIM(COALESCE(num_factura, '')), '') IS NULL THEN
            'NC-' || COALESCE(public.fn_keep_alnum(doc_erp), 'SIN_DOC') || '-' || ABS(public.fn_parse_numeric(valor_total_erp))::text
        ELSE public.fn_keep_alnum(num_factura)
    END AS num_factura_normalizado,
    public.fn_keep_alnum(doc_erp) AS doc_erp,
    public.fn_parse_date(fecha_emision_erp) AS fecha_emision_erp,
    public.fn_parse_date(fecha_vencimiento_erp) AS fecha_vencimiento_erp,
    public.fn_parse_numeric(valor_total_erp) AS valor_total_erp
FROM public.raw_proveedores_pagos;

CREATE OR REPLACE VIEW public.vw_recaudos AS
SELECT
    public.fn_parse_integer(anio) AS anio,
    public.fn_parse_integer(mes) AS mes,
    public.fn_parse_date(fecha_cobro) AS fecha_cobro,
    public.fn_keep_alnum(codigo_vendedor) AS codigo_vendedor,
    public.fn_parse_numeric(valor_cobro) AS valor_cobro
FROM public.raw_cobros_detalle;

CREATE OR REPLACE VIEW public.vw_cliente_contexto_agente AS
WITH ventas AS (
    SELECT
        cliente_id AS cliente_codigo,
        MAX(nombre_cliente) AS nombre_cliente,
        MAX(nom_vendedor) AS vendedor,
        MAX(fecha_venta) AS ultima_compra,
        COUNT(*) AS documentos_venta,
        COALESCE(SUM(valor_venta_neto), 0) AS ventas_netas_total,
        COALESCE(SUM(unidades_vendidas_netas), 0) AS unidades_netas_total
    FROM public.vw_ventas_netas
    WHERE cliente_id IS NOT NULL
    GROUP BY cliente_id
),
cartera AS (
    SELECT
        cod_cliente AS cliente_codigo,
        MAX(nombre_cliente) AS nombre_cliente,
        MAX(nom_vendedor) AS vendedor,
        MAX(zona) AS zona,
        COALESCE(SUM(importe_normalizado), 0) AS saldo_cartera,
        COALESCE(MAX(dias_vencido), 0) AS max_dias_vencido,
        COUNT(*) FILTER (WHERE COALESCE(dias_vencido, 0) > 0) AS documentos_vencidos
    FROM public.vw_estado_cartera
    WHERE cod_cliente IS NOT NULL
    GROUP BY cod_cliente
)
SELECT
    COALESCE(ventas.cliente_codigo, cartera.cliente_codigo) AS cliente_codigo,
    COALESCE(ventas.nombre_cliente, cartera.nombre_cliente) AS nombre_cliente,
    COALESCE(ventas.vendedor, cartera.vendedor) AS vendedor,
    cartera.zona,
    ventas.ultima_compra,
    COALESCE(ventas.documentos_venta, 0) AS documentos_venta,
    COALESCE(ventas.ventas_netas_total, 0) AS ventas_netas_total,
    COALESCE(ventas.unidades_netas_total, 0) AS unidades_netas_total,
    COALESCE(cartera.saldo_cartera, 0) AS saldo_cartera,
    COALESCE(cartera.max_dias_vencido, 0) AS max_dias_vencido,
    COALESCE(cartera.documentos_vencidos, 0) AS documentos_vencidos
FROM ventas
FULL OUTER JOIN cartera ON ventas.cliente_codigo = cartera.cliente_codigo;

COMMIT;