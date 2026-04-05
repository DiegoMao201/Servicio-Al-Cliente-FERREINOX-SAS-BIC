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

CREATE OR REPLACE FUNCTION public.fn_map_almacen_nombre(cod_almacen_value text)
RETURNS text
LANGUAGE sql
IMMUTABLE
AS $$
    SELECT CASE public.fn_digits_only(cod_almacen_value)
        WHEN '155' THEN 'CEDI'
        WHEN '156' THEN 'TIENDA ARMENIA'
        WHEN '157' THEN 'TIENDA MANIZALES'
        WHEN '158' THEN 'TIENDA OPALO'
        WHEN '189' THEN 'TIENDA PEREIRA'
        WHEN '238' THEN 'TIENDA LAURES'
        WHEN '439' THEN 'TIENDA FERREBOX'
        WHEN '463' THEN 'TIENDA CERRITOS'
        ELSE COALESCE(public.fn_digits_only(cod_almacen_value), 'SIN_ALMACEN')
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
    -- search_blob enriquecido con clasificación
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

CREATE OR REPLACE VIEW public.vw_agente_clientes_lookup AS
WITH ventas AS (
    SELECT
        cliente_id AS cliente_codigo,
        MAX(nombre_cliente) AS nombre_cliente,
        MAX(nom_vendedor) AS vendedor,
        MAX(codigo_vendedor) AS vendedor_codigo,
        MAX(fecha_venta) AS ultima_compra,
        COALESCE(SUM(valor_venta_neto), 0) AS ventas_netas_total
    FROM public.vw_ventas_netas
    WHERE cliente_id IS NOT NULL
    GROUP BY cliente_id
),
cartera AS (
    SELECT
        cod_cliente AS cliente_codigo,
        MAX(nombre_cliente) AS nombre_cliente,
        MAX(nit) AS nit,
        MAX(telefono1) AS telefono1,
        MAX(telefono2) AS telefono2,
        MAX(email) AS email,
        MAX(nom_vendedor) AS vendedor,
        MAX(zona) AS zona,
        COALESCE(SUM(importe_normalizado), 0) AS saldo_cartera,
        COALESCE(MAX(dias_vencido), 0) AS max_dias_vencido,
        COUNT(*) FILTER (WHERE COALESCE(dias_vencido, 0) > 0) AS documentos_vencidos
    FROM public.vw_estado_cartera
    WHERE cod_cliente IS NOT NULL
    GROUP BY cod_cliente
),
clientes AS (
    SELECT
        public.fn_keep_alnum(codigo) AS cliente_codigo,
        public.fn_normalize_text(COALESCE(nombre_comercial, nombre_legal)) AS nombre_cliente,
        public.fn_keep_alnum(numero_documento) AS numero_documento,
        LOWER(NULLIF(TRIM(COALESCE(email, '')), '')) AS email,
        telefono AS telefono1,
        celular AS telefono2,
        public.fn_normalize_text(ciudad) AS ciudad
    FROM public.cliente
)
SELECT
    COALESCE(clientes.cliente_codigo, ventas.cliente_codigo, cartera.cliente_codigo) AS cliente_codigo,
    COALESCE(cartera.nombre_cliente, ventas.nombre_cliente, clientes.nombre_cliente) AS nombre_cliente,
    COALESCE(cartera.nit, clientes.numero_documento) AS nit,
    clientes.numero_documento,
    COALESCE(cartera.telefono1, clientes.telefono1) AS telefono1,
    COALESCE(cartera.telefono2, clientes.telefono2) AS telefono2,
    COALESCE(cartera.email, clientes.email) AS email,
    COALESCE(ventas.vendedor, cartera.vendedor) AS vendedor,
    ventas.vendedor_codigo,
    COALESCE(cartera.zona, clientes.ciudad) AS zona,
    ventas.ultima_compra,
    COALESCE(ventas.ventas_netas_total, 0) AS ventas_netas_total,
    COALESCE(cartera.saldo_cartera, 0) AS saldo_cartera,
    COALESCE(cartera.max_dias_vencido, 0) AS max_dias_vencido,
    COALESCE(cartera.documentos_vencidos, 0) AS documentos_vencidos,
    public.fn_normalize_text(
        COALESCE(cartera.nombre_cliente, ventas.nombre_cliente, clientes.nombre_cliente, '') || ' ' ||
        COALESCE(cartera.nit, clientes.numero_documento, '') || ' ' ||
        COALESCE(COALESCE(clientes.cliente_codigo, ventas.cliente_codigo, cartera.cliente_codigo), '') || ' ' ||
        COALESCE(ventas.vendedor, cartera.vendedor, '') || ' ' ||
        COALESCE(cartera.zona, clientes.ciudad, '')
    ) AS search_blob,
    public.fn_keep_alnum(
        COALESCE(cartera.nombre_cliente, ventas.nombre_cliente, clientes.nombre_cliente, '') || ' ' ||
        COALESCE(cartera.nit, clientes.numero_documento, '') || ' ' ||
        COALESCE(COALESCE(clientes.cliente_codigo, ventas.cliente_codigo, cartera.cliente_codigo), '')
    ) AS search_compact
FROM clientes
FULL OUTER JOIN ventas
    ON clientes.cliente_codigo = ventas.cliente_codigo
FULL OUTER JOIN cartera
    ON COALESCE(clientes.cliente_codigo, ventas.cliente_codigo) = cartera.cliente_codigo;

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

CREATE OR REPLACE VIEW public.vw_agent_catalog_product_search AS
SELECT
    producto_codigo,
    referencia,
    descripcion_base,
    descripcion_inventario,
    marca,
    linea_producto,
    categoria_producto,
    super_categoria,
    departamentos,
    stock_total,
    stock_por_tienda,
    costo_promedio_und,
    inventario_unidades_metric,
    ventas_unidades_total,
    ventas_valor_total,
    ultima_venta,
    prioridad_origen,
    tiene_stock,
    tiene_historial_ventas,
    color_detectado,
    color_raiz,
    acabado_detectado,
    presentacion_canonica,
    core_descriptor,
    producto_padre_busqueda_sugerido,
    familia_consulta_sugerida,
    variant_label,
    workbook_version,
    public.fn_normalize_text(
        COALESCE(descripcion_base, '') || ' ' ||
        COALESCE(descripcion_inventario, '') || ' ' ||
        COALESCE(marca, '') || ' ' ||
        COALESCE(linea_producto, '') || ' ' ||
        COALESCE(categoria_producto, '') || ' ' ||
        COALESCE(super_categoria, '') || ' ' ||
        COALESCE(color_detectado, '') || ' ' ||
        COALESCE(color_raiz, '') || ' ' ||
        COALESCE(acabado_detectado, '') || ' ' ||
        COALESCE(presentacion_canonica, '') || ' ' ||
        COALESCE(core_descriptor, '') || ' ' ||
        COALESCE(producto_padre_busqueda_sugerido, '') || ' ' ||
        COALESCE(familia_consulta_sugerida, '') || ' ' ||
        COALESCE(variant_label, '') || ' ' ||
        COALESCE(referencia, '') || ' ' ||
        COALESCE(producto_codigo, '')
    ) AS search_blob,
    public.fn_keep_alnum(
        COALESCE(descripcion_base, '') || ' ' ||
        COALESCE(descripcion_inventario, '') || ' ' ||
        COALESCE(marca, '') || ' ' ||
        COALESCE(referencia, '') || ' ' ||
        COALESCE(producto_codigo, '')
    ) AS search_compact
FROM public.agent_catalog_product;

CREATE OR REPLACE VIEW public.vw_agent_catalog_alias_active AS
SELECT
    a.id,
    a.producto_codigo,
    p.referencia,
    p.descripcion_base,
    p.descripcion_inventario,
    p.marca,
    p.presentacion_canonica,
    p.producto_padre_busqueda_sugerido,
    p.familia_consulta_sugerida,
    a.alias_type,
    a.alias_value,
    a.alias_order,
    a.familia_consulta,
    a.producto_padre_busqueda,
    a.pregunta_desambiguacion,
    a.estrategia_busqueda,
    a.variantes_familia,
    a.terminos_excluir,
    a.activo_agente,
    a.observaciones_equipo,
    a.workbook_version,
    public.fn_normalize_text(a.alias_value) AS alias_normalizado,
    public.fn_keep_alnum(a.alias_value) AS alias_compacto
FROM public.agent_catalog_alias a
JOIN public.agent_catalog_product p
    ON p.producto_codigo = a.producto_codigo
WHERE a.activo_agente = true;

CREATE OR REPLACE VIEW public.vw_agent_order_dispatch_pending AS
SELECT
    d.id,
    d.order_id,
    d.conversation_id,
    d.contacto_id,
    d.cliente_id,
    d.destination_store_code,
    d.destination_store_name,
    d.facturador_name,
    d.facturador_email,
    d.facturador_phone,
    d.export_filename,
    d.dropbox_folder,
    d.dropbox_path,
    d.status,
    d.observations,
    d.metadata,
    d.exported_at,
    d.notified_email_at,
    d.notified_whatsapp_at,
    o.numero_externo,
    o.resumen AS order_summary,
    wc.nombre_visible AS contacto_nombre
FROM public.agent_order_dispatch d
LEFT JOIN public.agent_order o ON o.id = d.order_id
LEFT JOIN public.whatsapp_contacto wc ON wc.id = d.contacto_id
WHERE d.status IN ('pendiente', 'en_transito');

CREATE OR REPLACE VIEW public.vw_agent_transfer_request_active AS
SELECT
    tr.id,
    tr.order_dispatch_id,
    tr.order_id,
    tr.requested_by_user_id,
    tr.requested_via,
    tr.source_store_code,
    tr.source_store_name,
    tr.destination_store_code,
    tr.destination_store_name,
    tr.referencia,
    tr.descripcion,
    tr.quantity_requested,
    tr.status,
    tr.summary,
    tr.notes,
    tr.metadata,
    tr.created_at,
    tr.updated_at
FROM public.agent_transfer_request tr
WHERE tr.status IN ('pendiente', 'aprobado', 'en_transito');

COMMIT;