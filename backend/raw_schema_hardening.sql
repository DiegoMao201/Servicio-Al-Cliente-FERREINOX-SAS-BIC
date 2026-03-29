BEGIN;

ALTER TABLE IF EXISTS public.raw_ventas_detalle
    ALTER COLUMN anio TYPE text USING anio::text,
    ALTER COLUMN mes TYPE text USING mes::text,
    ALTER COLUMN fecha_venta TYPE text USING fecha_venta::text,
    ALTER COLUMN serie TYPE text USING serie::text,
    ALTER COLUMN tipo_documento TYPE text USING tipo_documento::text,
    ALTER COLUMN codigo_vendedor TYPE text USING codigo_vendedor::text,
    ALTER COLUMN nom_vendedor TYPE text USING nom_vendedor::text,
    ALTER COLUMN cliente_id TYPE text USING cliente_id::text,
    ALTER COLUMN nombre_cliente TYPE text USING nombre_cliente::text,
    ALTER COLUMN codigo_articulo TYPE text USING codigo_articulo::text,
    ALTER COLUMN nombre_articulo TYPE text USING nombre_articulo::text,
    ALTER COLUMN categoria_producto TYPE text USING categoria_producto::text,
    ALTER COLUMN linea_producto TYPE text USING linea_producto::text,
    ALTER COLUMN marca_producto TYPE text USING marca_producto::text,
    ALTER COLUMN valor_venta TYPE text USING valor_venta::text,
    ALTER COLUMN unidades_vendidas TYPE text USING unidades_vendidas::text,
    ALTER COLUMN costo_unitario TYPE text USING costo_unitario::text,
    ALTER COLUMN super_categoria TYPE text USING super_categoria::text;

ALTER TABLE IF EXISTS public.raw_rotacion_inventarios
    ALTER COLUMN departamento TYPE text USING departamento::text,
    ALTER COLUMN referencia TYPE text USING referencia::text,
    ALTER COLUMN descripcion TYPE text USING descripcion::text,
    ALTER COLUMN marca TYPE text USING marca::text,
    ALTER COLUMN peso_articulo TYPE text USING peso_articulo::text,
    ALTER COLUMN unidades_vendidas TYPE text USING unidades_vendidas::text,
    ALTER COLUMN stock TYPE text USING stock::text,
    ALTER COLUMN costo_promedio_und TYPE text USING costo_promedio_und::text,
    ALTER COLUMN cod_almacen TYPE text USING cod_almacen::text,
    ALTER COLUMN lead_time_proveedor TYPE text USING lead_time_proveedor::text;

ALTER TABLE IF EXISTS public.raw_cartera_detalle
    ALTER COLUMN serie TYPE text USING serie::text,
    ALTER COLUMN numero_documento TYPE text USING numero_documento::text,
    ALTER COLUMN fecha_documento TYPE text USING fecha_documento::text,
    ALTER COLUMN fecha_vencimiento TYPE text USING fecha_vencimiento::text,
    ALTER COLUMN cod_cliente TYPE text USING cod_cliente::text,
    ALTER COLUMN nombre_cliente TYPE text USING nombre_cliente::text,
    ALTER COLUMN nit TYPE text USING nit::text,
    ALTER COLUMN poblacion TYPE text USING poblacion::text,
    ALTER COLUMN provincia TYPE text USING provincia::text,
    ALTER COLUMN telefono1 TYPE text USING telefono1::text,
    ALTER COLUMN telefono2 TYPE text USING telefono2::text,
    ALTER COLUMN nom_vendedor TYPE text USING nom_vendedor::text,
    ALTER COLUMN entidad_autoriza TYPE text USING entidad_autoriza::text,
    ALTER COLUMN email TYPE text USING email::text,
    ALTER COLUMN importe TYPE text USING importe::text,
    ALTER COLUMN descuento TYPE text USING descuento::text,
    ALTER COLUMN cupo_aprobado TYPE text USING cupo_aprobado::text,
    ALTER COLUMN dias_vencido TYPE text USING dias_vencido::text;

ALTER TABLE IF EXISTS public.raw_cobros_detalle
    ALTER COLUMN anio TYPE text USING anio::text,
    ALTER COLUMN mes TYPE text USING mes::text,
    ALTER COLUMN fecha_cobro TYPE text USING fecha_cobro::text,
    ALTER COLUMN codigo_vendedor TYPE text USING codigo_vendedor::text,
    ALTER COLUMN valor_cobro TYPE text USING valor_cobro::text;

ALTER TABLE IF EXISTS public.raw_proveedores_pagos
    ALTER COLUMN nombre_proveedor_erp TYPE text USING nombre_proveedor_erp::text,
    ALTER COLUMN serie TYPE text USING serie::text,
    ALTER COLUMN num_entrada_erp TYPE text USING num_entrada_erp::text,
    ALTER COLUMN num_factura TYPE text USING num_factura::text,
    ALTER COLUMN doc_erp TYPE text USING doc_erp::text,
    ALTER COLUMN fecha_emision_erp TYPE text USING fecha_emision_erp::text,
    ALTER COLUMN fecha_vencimiento_erp TYPE text USING fecha_vencimiento_erp::text,
    ALTER COLUMN valor_total_erp TYPE text USING valor_total_erp::text;

COMMIT;