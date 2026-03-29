BEGIN;

CREATE TABLE public.empresa (
    id bigserial PRIMARY KEY,
    nombre varchar(150) NOT NULL,
    nit varchar(30),
    email varchar(150),
    telefono varchar(50),
    direccion text,
    ciudad varchar(100),
    pais varchar(100) DEFAULT 'Colombia',
    activo boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_empresa_nit UNIQUE (nit)
);

CREATE TABLE public.cliente (
    id bigserial PRIMARY KEY,
    empresa_id bigint REFERENCES public.empresa(id) ON DELETE SET NULL,
    codigo varchar(50),
    tipo_documento varchar(20),
    numero_documento varchar(50),
    nombre_legal varchar(180) NOT NULL,
    nombre_comercial varchar(180),
    email varchar(150),
    telefono varchar(50),
    celular varchar(50),
    direccion text,
    ciudad varchar(100),
    departamento varchar(100),
    pais varchar(100) DEFAULT 'Colombia',
    segmento varchar(80),
    cupo_credito numeric(18,2) NOT NULL DEFAULT 0,
    saldo_cartera numeric(18,2) NOT NULL DEFAULT 0,
    activo boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_cliente_codigo UNIQUE (codigo),
    CONSTRAINT uq_cliente_documento UNIQUE (tipo_documento, numero_documento)
);

CREATE TABLE public.categoria_producto (
    id bigserial PRIMARY KEY,
    codigo varchar(50),
    nombre varchar(150) NOT NULL,
    descripcion text,
    parent_id bigint REFERENCES public.categoria_producto(id) ON DELETE SET NULL,
    activo boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_categoria_codigo UNIQUE (codigo),
    CONSTRAINT uq_categoria_nombre UNIQUE (nombre)
);

CREATE TABLE public.producto (
    id bigserial PRIMARY KEY,
    categoria_id bigint REFERENCES public.categoria_producto(id) ON DELETE SET NULL,
    sku varchar(80) NOT NULL,
    referencia varchar(100),
    nombre varchar(180) NOT NULL,
    descripcion text,
    marca varchar(100),
    unidad_medida varchar(30),
    peso numeric(18,4),
    costo_promedio numeric(18,2) NOT NULL DEFAULT 0,
    precio_venta numeric(18,2) NOT NULL DEFAULT 0,
    lead_time_proveedor_dias integer,
    activo boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_producto_sku UNIQUE (sku),
    CONSTRAINT uq_producto_referencia UNIQUE (referencia)
);

CREATE TABLE public.ubicacion (
    id bigserial PRIMARY KEY,
    codigo varchar(50) NOT NULL,
    nombre varchar(120) NOT NULL,
    descripcion text,
    tipo varchar(50),
    activo boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_ubicacion_codigo UNIQUE (codigo)
);

CREATE TABLE public.stock_por_ubicacion (
    id bigserial PRIMARY KEY,
    producto_id bigint NOT NULL REFERENCES public.producto(id) ON DELETE CASCADE,
    ubicacion_id bigint NOT NULL REFERENCES public.ubicacion(id) ON DELETE CASCADE,
    stock_actual numeric(18,3) NOT NULL DEFAULT 0,
    stock_reservado numeric(18,3) NOT NULL DEFAULT 0,
    stock_disponible numeric(18,3) GENERATED ALWAYS AS (stock_actual - stock_reservado) STORED,
    stock_minimo numeric(18,3) NOT NULL DEFAULT 0,
    stock_maximo numeric(18,3),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_stock_producto_ubicacion UNIQUE (producto_id, ubicacion_id)
);

CREATE TABLE public.movimiento_stock (
    id bigserial PRIMARY KEY,
    producto_id bigint NOT NULL REFERENCES public.producto(id) ON DELETE RESTRICT,
    ubicacion_id bigint REFERENCES public.ubicacion(id) ON DELETE SET NULL,
    tipo_movimiento varchar(30) NOT NULL,
    cantidad numeric(18,3) NOT NULL,
    costo_unitario numeric(18,2),
    referencia_origen varchar(80),
    documento_origen varchar(80),
    observacion text,
    fecha_movimiento timestamptz NOT NULL DEFAULT now(),
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT chk_movimiento_tipo CHECK (tipo_movimiento IN ('entrada', 'salida', 'ajuste', 'traslado', 'venta', 'compra'))
);

CREATE TABLE public.venta (
    id bigserial PRIMARY KEY,
    empresa_id bigint REFERENCES public.empresa(id) ON DELETE SET NULL,
    cliente_id bigint REFERENCES public.cliente(id) ON DELETE SET NULL,
    numero_documento varchar(80) NOT NULL,
    canal varchar(50),
    estado varchar(30) NOT NULL DEFAULT 'borrador',
    moneda varchar(10) NOT NULL DEFAULT 'COP',
    subtotal numeric(18,2) NOT NULL DEFAULT 0,
    descuento_total numeric(18,2) NOT NULL DEFAULT 0,
    impuesto_total numeric(18,2) NOT NULL DEFAULT 0,
    total numeric(18,2) NOT NULL DEFAULT 0,
    fecha_venta timestamptz NOT NULL DEFAULT now(),
    observacion text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_venta_numero_documento UNIQUE (numero_documento),
    CONSTRAINT chk_venta_estado CHECK (estado IN ('borrador', 'emitida', 'pagada', 'anulada', 'vencida'))
);

CREATE TABLE public.venta_linea (
    id bigserial PRIMARY KEY,
    venta_id bigint NOT NULL REFERENCES public.venta(id) ON DELETE CASCADE,
    producto_id bigint NOT NULL REFERENCES public.producto(id) ON DELETE RESTRICT,
    cantidad numeric(18,3) NOT NULL,
    precio_unitario numeric(18,2) NOT NULL,
    descuento numeric(18,2) NOT NULL DEFAULT 0,
    impuesto numeric(18,2) NOT NULL DEFAULT 0,
    total_linea numeric(18,2) NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE public.orden_compra (
    id bigserial PRIMARY KEY,
    empresa_id bigint REFERENCES public.empresa(id) ON DELETE SET NULL,
    numero_orden varchar(80) NOT NULL,
    proveedor_nombre varchar(180) NOT NULL,
    proveedor_nit varchar(50),
    estado varchar(30) NOT NULL DEFAULT 'borrador',
    moneda varchar(10) NOT NULL DEFAULT 'COP',
    subtotal numeric(18,2) NOT NULL DEFAULT 0,
    impuesto_total numeric(18,2) NOT NULL DEFAULT 0,
    total numeric(18,2) NOT NULL DEFAULT 0,
    fecha_orden timestamptz NOT NULL DEFAULT now(),
    fecha_entrega_estimada timestamptz,
    observacion text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_orden_compra_numero UNIQUE (numero_orden),
    CONSTRAINT chk_orden_compra_estado CHECK (estado IN ('borrador', 'emitida', 'parcial', 'recibida', 'cancelada'))
);

CREATE TABLE public.orden_compra_linea (
    id bigserial PRIMARY KEY,
    orden_compra_id bigint NOT NULL REFERENCES public.orden_compra(id) ON DELETE CASCADE,
    producto_id bigint NOT NULL REFERENCES public.producto(id) ON DELETE RESTRICT,
    cantidad numeric(18,3) NOT NULL,
    costo_unitario numeric(18,2) NOT NULL,
    impuesto numeric(18,2) NOT NULL DEFAULT 0,
    total_linea numeric(18,2) NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE public.cartera_cliente (
    id bigserial PRIMARY KEY,
    cliente_id bigint NOT NULL REFERENCES public.cliente(id) ON DELETE CASCADE,
    venta_id bigint REFERENCES public.venta(id) ON DELETE SET NULL,
    documento_referencia varchar(80) NOT NULL,
    fecha_emision timestamptz NOT NULL,
    fecha_vencimiento timestamptz,
    valor_original numeric(18,2) NOT NULL,
    saldo_pendiente numeric(18,2) NOT NULL,
    estado varchar(30) NOT NULL DEFAULT 'pendiente',
    dias_mora integer NOT NULL DEFAULT 0,
    observacion text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT chk_cartera_estado CHECK (estado IN ('pendiente', 'pagado', 'vencido', 'acuerdo', 'castigado'))
);

CREATE TABLE public.raw_ventas_detalle (
    anio integer,
    mes integer,
    fecha_venta date,
    serie varchar(50),
    tipo_documento varchar(100),
    codigo_vendedor varchar(50),
    nom_vendedor varchar(150),
    cliente_id varchar(50),
    nombre_cliente varchar(200),
    codigo_articulo varchar(50),
    nombre_articulo varchar(255),
    categoria_producto varchar(100),
    linea_producto varchar(100),
    marca_producto varchar(50),
    valor_venta numeric(14,2),
    unidades_vendidas numeric(10,2),
    costo_unitario numeric(14,2),
    super_categoria varchar(100)
);

CREATE TABLE public.raw_rotacion_inventarios (
    departamento varchar(100),
    referencia varchar(50),
    descripcion varchar(255),
    marca varchar(50),
    peso_articulo numeric(10,2),
    unidades_vendidas integer,
    stock numeric(10,2),
    costo_promedio_und numeric(14,2),
    cod_almacen varchar(50),
    lead_time_proveedor integer,
    historial_ventas text
);

CREATE TABLE public.raw_cartera_detalle (
    serie varchar(50),
    numero_documento integer,
    fecha_documento date,
    fecha_vencimiento date,
    cod_cliente varchar(50),
    nombre_cliente varchar(200),
    nit varchar(50),
    poblacion varchar(100),
    provincia varchar(100),
    telefono1 varchar(50),
    telefono2 varchar(50),
    nom_vendedor varchar(150),
    entidad_autoriza varchar(100),
    email varchar(150),
    importe numeric(14,2),
    descuento numeric(14,2),
    cupo_aprobado numeric(14,2),
    dias_vencido integer
);

CREATE TABLE public.raw_cobros_detalle (
    anio integer,
    mes integer,
    fecha_cobro date,
    codigo_vendedor varchar(50),
    valor_cobro numeric(14,2)
);

CREATE TABLE public.raw_proveedores_pagos (
    nombre_proveedor_erp varchar(200),
    serie varchar(50),
    num_entrada_erp varchar(50),
    num_factura varchar(50),
    doc_erp varchar(50),
    fecha_emision_erp date,
    fecha_vencimiento_erp date,
    valor_total_erp numeric(14,2)
);

CREATE TABLE public.sync_schema_registry (
    id bigserial PRIMARY KEY,
    source_label varchar(120) NOT NULL,
    dropbox_folder varchar(255) NOT NULL,
    file_name varchar(255) NOT NULL,
    file_path varchar(255) NOT NULL,
    target_table varchar(150) NOT NULL,
    has_header boolean NOT NULL DEFAULT false,
    columns_json jsonb NOT NULL,
    delimiter varchar(10),
    encoding varchar(30),
    is_active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_sync_schema_registry UNIQUE (source_label, file_path)
);

CREATE TABLE public.sync_run_log (
    id bigserial PRIMARY KEY,
    registry_id bigint REFERENCES public.sync_schema_registry(id) ON DELETE SET NULL,
    source_label varchar(120) NOT NULL,
    file_name varchar(255) NOT NULL,
    target_table varchar(150) NOT NULL,
    status varchar(20) NOT NULL,
    row_count integer,
    message text,
    executed_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_cliente_empresa_id ON public.cliente(empresa_id);
CREATE INDEX idx_producto_categoria_id ON public.producto(categoria_id);
CREATE INDEX idx_stock_producto_id ON public.stock_por_ubicacion(producto_id);
CREATE INDEX idx_stock_ubicacion_id ON public.stock_por_ubicacion(ubicacion_id);
CREATE INDEX idx_movimiento_stock_producto_id ON public.movimiento_stock(producto_id);
CREATE INDEX idx_movimiento_stock_fecha ON public.movimiento_stock(fecha_movimiento);
CREATE INDEX idx_venta_cliente_id ON public.venta(cliente_id);
CREATE INDEX idx_venta_fecha ON public.venta(fecha_venta);
CREATE INDEX idx_venta_linea_venta_id ON public.venta_linea(venta_id);
CREATE INDEX idx_orden_compra_fecha ON public.orden_compra(fecha_orden);
CREATE INDEX idx_orden_compra_linea_orden_id ON public.orden_compra_linea(orden_compra_id);
CREATE INDEX idx_cartera_cliente_id ON public.cartera_cliente(cliente_id);
CREATE INDEX idx_cartera_estado ON public.cartera_cliente(estado);
CREATE INDEX idx_cartera_vencimiento ON public.cartera_cliente(fecha_vencimiento);
CREATE INDEX idx_raw_ventas_fecha ON public.raw_ventas_detalle(fecha_venta);
CREATE INDEX idx_raw_ventas_tipo_documento ON public.raw_ventas_detalle(tipo_documento);
CREATE INDEX idx_raw_ventas_cliente ON public.raw_ventas_detalle(cliente_id);
CREATE INDEX idx_raw_rotacion_referencia ON public.raw_rotacion_inventarios(referencia);
CREATE INDEX idx_raw_cartera_cliente ON public.raw_cartera_detalle(cod_cliente);
CREATE INDEX idx_raw_cartera_serie ON public.raw_cartera_detalle(serie);
CREATE INDEX idx_raw_cobros_fecha ON public.raw_cobros_detalle(fecha_cobro);
CREATE INDEX idx_raw_proveedores_factura ON public.raw_proveedores_pagos(num_factura);
CREATE INDEX idx_sync_schema_registry_source ON public.sync_schema_registry(source_label);
CREATE INDEX idx_sync_run_log_executed_at ON public.sync_run_log(executed_at);

COMMIT;
