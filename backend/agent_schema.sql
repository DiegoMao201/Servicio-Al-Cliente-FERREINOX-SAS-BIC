BEGIN;

CREATE TABLE IF NOT EXISTS public.whatsapp_contacto (
    id bigserial PRIMARY KEY,
    cliente_id bigint REFERENCES public.cliente(id) ON DELETE SET NULL,
    telefono_e164 varchar(30) NOT NULL,
    nombre_visible varchar(180),
    canal varchar(30) NOT NULL DEFAULT 'whatsapp',
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    ultima_interaccion_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_whatsapp_contacto_telefono UNIQUE (telefono_e164)
);

CREATE TABLE IF NOT EXISTS public.agent_conversation (
    id bigserial PRIMARY KEY,
    contacto_id bigint NOT NULL REFERENCES public.whatsapp_contacto(id) ON DELETE CASCADE,
    cliente_id bigint REFERENCES public.cliente(id) ON DELETE SET NULL,
    canal varchar(30) NOT NULL DEFAULT 'whatsapp',
    estado varchar(30) NOT NULL DEFAULT 'abierta',
    resumen text,
    contexto jsonb NOT NULL DEFAULT '{}'::jsonb,
    started_at timestamptz NOT NULL DEFAULT now(),
    last_message_at timestamptz,
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT chk_agent_conversation_estado CHECK (estado IN ('abierta', 'pendiente', 'cerrada', 'escalada'))
);

CREATE TABLE IF NOT EXISTS public.agent_message (
    id bigserial PRIMARY KEY,
    conversation_id bigint NOT NULL REFERENCES public.agent_conversation(id) ON DELETE CASCADE,
    provider_message_id varchar(120),
    direction varchar(20) NOT NULL,
    message_type varchar(30) NOT NULL DEFAULT 'text',
    intent_detectado varchar(80),
    contenido text,
    payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    estado varchar(30) NOT NULL DEFAULT 'recibido',
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT chk_agent_message_direction CHECK (direction IN ('inbound', 'outbound', 'system')),
    CONSTRAINT chk_agent_message_estado CHECK (estado IN ('recibido', 'procesado', 'respondido', 'error'))
);

CREATE TABLE IF NOT EXISTS public.agent_task (
    id bigserial PRIMARY KEY,
    conversation_id bigint REFERENCES public.agent_conversation(id) ON DELETE SET NULL,
    cliente_id bigint REFERENCES public.cliente(id) ON DELETE SET NULL,
    tipo_tarea varchar(50) NOT NULL,
    prioridad varchar(20) NOT NULL DEFAULT 'media',
    estado varchar(30) NOT NULL DEFAULT 'pendiente',
    resumen text NOT NULL,
    detalle jsonb NOT NULL DEFAULT '{}'::jsonb,
    due_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT chk_agent_task_prioridad CHECK (prioridad IN ('baja', 'media', 'alta', 'critica')),
    CONSTRAINT chk_agent_task_estado CHECK (estado IN ('pendiente', 'en_progreso', 'resuelta', 'cancelada'))
);

CREATE TABLE IF NOT EXISTS public.agent_product_learning (
    id bigserial PRIMARY KEY,
    normalized_phrase text NOT NULL,
    raw_phrase text NOT NULL,
    canonical_reference text NOT NULL,
    canonical_description text,
    canonical_brand text,
    canonical_presentation text,
    source_conversation_id bigint REFERENCES public.agent_conversation(id) ON DELETE SET NULL,
    source_message text,
    confidence numeric(5,4) NOT NULL DEFAULT 0.7500,
    usage_count integer NOT NULL DEFAULT 1,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_agent_product_learning UNIQUE (normalized_phrase, canonical_reference)
);

CREATE TABLE IF NOT EXISTS public.agent_quote (
    id bigserial PRIMARY KEY,
    conversation_id bigint REFERENCES public.agent_conversation(id) ON DELETE SET NULL,
    contacto_id bigint REFERENCES public.whatsapp_contacto(id) ON DELETE SET NULL,
    cliente_id bigint REFERENCES public.cliente(id) ON DELETE SET NULL,
    estado varchar(30) NOT NULL DEFAULT 'borrador',
    canal varchar(30) NOT NULL DEFAULT 'whatsapp',
    moneda varchar(10) NOT NULL DEFAULT 'COP',
    almacen_codigo varchar(20),
    almacen_nombre varchar(120),
    resumen text,
    observaciones text,
    subtotal numeric(18,2) NOT NULL DEFAULT 0,
    descuento_total numeric(18,2) NOT NULL DEFAULT 0,
    impuestos_total numeric(18,2) NOT NULL DEFAULT 0,
    total numeric(18,2) NOT NULL DEFAULT 0,
    valid_until timestamptz,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT chk_agent_quote_estado CHECK (estado IN ('borrador', 'confirmada', 'enviada', 'vencida', 'cancelada', 'convertida_pedido'))
);

CREATE TABLE IF NOT EXISTS public.agent_quote_line (
    id bigserial PRIMARY KEY,
    quote_id bigint NOT NULL REFERENCES public.agent_quote(id) ON DELETE CASCADE,
    line_number integer NOT NULL,
    producto_codigo varchar(100),
    referencia varchar(120),
    descripcion text NOT NULL,
    marca varchar(100),
    presentacion varchar(60),
    unidad_medida varchar(30),
    almacen_codigo varchar(20),
    almacen_nombre varchar(120),
    cantidad numeric(18,3) NOT NULL DEFAULT 0,
    stock_confirmado numeric(18,3),
    precio_unitario numeric(18,2),
    descuento_pct numeric(8,4) NOT NULL DEFAULT 0,
    subtotal numeric(18,2) NOT NULL DEFAULT 0,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_agent_quote_line UNIQUE (quote_id, line_number)
);

CREATE TABLE IF NOT EXISTS public.agent_order (
    id bigserial PRIMARY KEY,
    conversation_id bigint REFERENCES public.agent_conversation(id) ON DELETE SET NULL,
    contacto_id bigint REFERENCES public.whatsapp_contacto(id) ON DELETE SET NULL,
    cliente_id bigint REFERENCES public.cliente(id) ON DELETE SET NULL,
    quote_id bigint REFERENCES public.agent_quote(id) ON DELETE SET NULL,
    estado varchar(30) NOT NULL DEFAULT 'borrador',
    canal varchar(30) NOT NULL DEFAULT 'whatsapp',
    origen varchar(30) NOT NULL DEFAULT 'agente_ia',
    numero_externo varchar(120),
    almacen_codigo varchar(20),
    almacen_nombre varchar(120),
    resumen text,
    observaciones text,
    subtotal numeric(18,2) NOT NULL DEFAULT 0,
    descuento_total numeric(18,2) NOT NULL DEFAULT 0,
    impuestos_total numeric(18,2) NOT NULL DEFAULT 0,
    total numeric(18,2) NOT NULL DEFAULT 0,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    submitted_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT chk_agent_order_estado CHECK (estado IN ('borrador', 'pendiente_confirmacion', 'confirmado', 'enviado_erp', 'rechazado', 'cancelado'))
);

CREATE TABLE IF NOT EXISTS public.agent_order_line (
    id bigserial PRIMARY KEY,
    order_id bigint NOT NULL REFERENCES public.agent_order(id) ON DELETE CASCADE,
    line_number integer NOT NULL,
    producto_codigo varchar(100),
    referencia varchar(120),
    descripcion text NOT NULL,
    marca varchar(100),
    presentacion varchar(60),
    unidad_medida varchar(30),
    almacen_codigo varchar(20),
    almacen_nombre varchar(120),
    cantidad numeric(18,3) NOT NULL DEFAULT 0,
    stock_confirmado numeric(18,3),
    precio_unitario numeric(18,2),
    descuento_pct numeric(8,4) NOT NULL DEFAULT 0,
    subtotal numeric(18,2) NOT NULL DEFAULT 0,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_agent_order_line UNIQUE (order_id, line_number)
);

CREATE TABLE IF NOT EXISTS public.agent_order_dispatch (
    id bigserial PRIMARY KEY,
    order_id bigint NOT NULL REFERENCES public.agent_order(id) ON DELETE CASCADE,
    conversation_id bigint REFERENCES public.agent_conversation(id) ON DELETE SET NULL,
    contacto_id bigint REFERENCES public.whatsapp_contacto(id) ON DELETE SET NULL,
    cliente_id bigint REFERENCES public.cliente(id) ON DELETE SET NULL,
    exported_by_user_id bigint REFERENCES public.agent_user(id) ON DELETE SET NULL,
    destination_store_code varchar(20),
    destination_store_name varchar(120),
    facturador_name varchar(180),
    facturador_email varchar(180),
    facturador_phone varchar(30),
    export_filename varchar(255) NOT NULL,
    dropbox_folder varchar(255),
    dropbox_path varchar(255),
    status varchar(30) NOT NULL DEFAULT 'pendiente',
    observations text,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    exported_at timestamptz,
    notified_email_at timestamptz,
    notified_whatsapp_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_agent_order_dispatch_order UNIQUE (order_id),
    CONSTRAINT chk_agent_order_dispatch_status CHECK (status IN ('pendiente', 'en_transito', 'recibido', 'cancelado'))
);

CREATE TABLE IF NOT EXISTS public.agent_transfer_request (
    id bigserial PRIMARY KEY,
    order_dispatch_id bigint REFERENCES public.agent_order_dispatch(id) ON DELETE SET NULL,
    order_id bigint REFERENCES public.agent_order(id) ON DELETE SET NULL,
    requested_by_user_id bigint REFERENCES public.agent_user(id) ON DELETE SET NULL,
    requested_via varchar(40) NOT NULL DEFAULT 'whatsapp_interno',
    source_store_code varchar(20),
    source_store_name varchar(120),
    destination_store_code varchar(20),
    destination_store_name varchar(120),
    referencia varchar(120) NOT NULL,
    descripcion text,
    quantity_requested numeric(18,3) NOT NULL DEFAULT 0,
    status varchar(30) NOT NULL DEFAULT 'pendiente',
    summary text,
    notes text,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT chk_agent_transfer_request_status CHECK (status IN ('pendiente', 'aprobado', 'en_transito', 'recibido', 'cancelado'))
);

CREATE TABLE IF NOT EXISTS public.agent_user (
    id bigserial PRIMARY KEY,
    username varchar(80) NOT NULL,
    full_name varchar(180) NOT NULL,
    role varchar(30) NOT NULL,
    password_salt varchar(128) NOT NULL,
    password_hash varchar(256) NOT NULL,
    phone_e164 varchar(30),
    email varchar(180),
    is_active boolean NOT NULL DEFAULT true,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_agent_user_username UNIQUE (username),
    CONSTRAINT uq_agent_user_phone UNIQUE (phone_e164),
        CONSTRAINT chk_agent_user_role CHECK (role IN ('empleado', 'vendedor', 'gerente', 'operador', 'administrador'))
);

CREATE TABLE IF NOT EXISTS public.agent_user_scope (
    id bigserial PRIMARY KEY,
    user_id bigint NOT NULL REFERENCES public.agent_user(id) ON DELETE CASCADE,
    scope_type varchar(40) NOT NULL,
    scope_value varchar(180) NOT NULL,
    scope_label varchar(180),
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_agent_user_scope UNIQUE (user_id, scope_type, scope_value),
    CONSTRAINT chk_agent_user_scope_type CHECK (scope_type IN ('cliente', 'vendedor_codigo', 'vendedor_nombre', 'zona', 'almacen'))
);

CREATE TABLE IF NOT EXISTS public.agent_user_session (
    id bigserial PRIMARY KEY,
    user_id bigint NOT NULL REFERENCES public.agent_user(id) ON DELETE CASCADE,
    token_hash varchar(128) NOT NULL,
    channel varchar(30) NOT NULL DEFAULT 'api',
    contact_id bigint REFERENCES public.whatsapp_contacto(id) ON DELETE SET NULL,
    phone_e164 varchar(30),
    expires_at timestamptz NOT NULL,
    last_used_at timestamptz,
    revoked_at timestamptz,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_agent_user_session_token UNIQUE (token_hash),
    CONSTRAINT chk_agent_user_session_channel CHECK (channel IN ('api', 'whatsapp'))
);

CREATE TABLE IF NOT EXISTS public.agent_catalog_product (
    producto_codigo varchar(100) PRIMARY KEY,
    referencia varchar(120),
    descripcion_base text,
    descripcion_inventario text,
    marca varchar(120),
    linea_producto varchar(180),
    categoria_producto varchar(180),
    super_categoria varchar(180),
    departamentos text,
    stock_total numeric(18,3),
    stock_por_tienda text,
    costo_promedio_und numeric(18,4),
    inventario_unidades_metric numeric(18,3),
    ventas_unidades_total numeric(18,3),
    ventas_valor_total numeric(18,2),
    ultima_venta date,
    prioridad_origen varchar(40),
    tiene_stock boolean NOT NULL DEFAULT false,
    tiene_historial_ventas boolean NOT NULL DEFAULT false,
    color_detectado varchar(120),
    color_raiz varchar(120),
    acabado_detectado varchar(120),
    presentacion_canonica varchar(120),
    core_descriptor text,
    producto_padre_busqueda_sugerido text,
    familia_consulta_sugerida text,
    variant_label text,
    workbook_version varchar(40) NOT NULL DEFAULT 'v2',
    source_file varchar(240),
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.agent_catalog_alias (
    id bigserial PRIMARY KEY,
    producto_codigo varchar(100) NOT NULL REFERENCES public.agent_catalog_product(producto_codigo) ON DELETE CASCADE,
    referencia varchar(120),
    alias_type varchar(40) NOT NULL,
    alias_value text NOT NULL,
    alias_order integer NOT NULL DEFAULT 1,
    familia_consulta text,
    producto_padre_busqueda text,
    pregunta_desambiguacion text,
    estrategia_busqueda varchar(80),
    variantes_familia text,
    terminos_excluir text,
    activo_agente boolean NOT NULL DEFAULT true,
    observaciones_equipo text,
    workbook_version varchar(40) NOT NULL DEFAULT 'v2',
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT chk_agent_catalog_alias_type CHECK (alias_type IN ('producto', 'presentacion', 'color')),
    CONSTRAINT uq_agent_catalog_alias UNIQUE (producto_codigo, alias_type, alias_value)
);

CREATE TABLE IF NOT EXISTS public.agent_catalog_family (
    id bigserial PRIMARY KEY,
    familia_consulta_sugerida text NOT NULL,
    producto_padre_busqueda text,
    marca varchar(120),
    core_descriptor text,
    color_raiz varchar(120),
    productos integer,
    ventas_unidades_total numeric(18,3),
    ventas_valor_total numeric(18,2),
    stock_total numeric(18,3),
    requiere_desambiguacion boolean NOT NULL DEFAULT false,
    pregunta_desambiguacion_sugerida text,
    estrategia_busqueda varchar(80),
    variantes_top text,
    workbook_version varchar(40) NOT NULL DEFAULT 'v2',
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.agent_catalog_presentation_alias (
    id bigserial PRIMARY KEY,
    presentacion_canonica varchar(120) NOT NULL,
    alias_presentacion text NOT NULL,
    tokens_regla text,
    prioridad integer NOT NULL DEFAULT 1,
    workbook_version varchar(40) NOT NULL DEFAULT 'v2',
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_agent_catalog_presentation_alias UNIQUE (presentacion_canonica, alias_presentacion)
);

CREATE TABLE IF NOT EXISTS public.agent_catalog_rule (
    id bigserial PRIMARY KEY,
    regla_clave varchar(120) NOT NULL,
    tipo_regla varchar(60),
    aplicacion varchar(120),
    valor_regla text,
    detalle text,
    prioridad integer NOT NULL DEFAULT 1,
    activo boolean NOT NULL DEFAULT true,
    workbook_version varchar(40) NOT NULL DEFAULT 'v2',
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

-- ============================================================
-- Tabla: agent_product_companion
-- Relaciones entre productos: catalizadores, diluyentes, bases, etc.
-- ============================================================
CREATE TABLE IF NOT EXISTS public.agent_product_companion (
    id bigserial PRIMARY KEY,
    producto_referencia text NOT NULL,
    producto_descripcion text,
    companion_referencia text NOT NULL,
    companion_descripcion text,
    tipo_relacion varchar(60) NOT NULL,
    proporcion text,
    notas text,
    source_conversation_id bigint REFERENCES public.agent_conversation(id) ON DELETE SET NULL,
    confidence numeric(5,4) NOT NULL DEFAULT 0.9500,
    activo boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_agent_product_companion UNIQUE (producto_referencia, companion_referencia, tipo_relacion)
);
CREATE INDEX IF NOT EXISTS idx_agent_product_companion_ref ON public.agent_product_companion(producto_referencia);
CREATE INDEX IF NOT EXISTS idx_agent_product_companion_companion ON public.agent_product_companion(companion_referencia);

-- ============================================================
-- Extensión pgvector (requiere instalación en el servidor Docker)
-- ============================================================
CREATE EXTENSION IF NOT EXISTS vector;

-- ============================================================
-- Tabla: agent_technical_doc_chunk
-- Chunks vectorizados de fichas técnicas para RAG semántico.
-- Cada fila = un fragmento de ~500-800 tokens de un PDF técnico,
-- con embedding vector(1536) de text-embedding-3-small de OpenAI.
-- ============================================================
CREATE TABLE IF NOT EXISTS public.agent_technical_doc_chunk (
    id bigserial PRIMARY KEY,
    doc_filename text NOT NULL,
    doc_path_lower text NOT NULL,
    chunk_index integer NOT NULL DEFAULT 0,
    chunk_text text NOT NULL,
    marca text,
    familia_producto text,
    tipo_documento varchar(30) NOT NULL DEFAULT 'ficha_tecnica',
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    embedding vector(1536) NOT NULL,
    token_count integer,
    ingested_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_agent_doc_chunk UNIQUE (doc_path_lower, chunk_index)
);
CREATE INDEX IF NOT EXISTS idx_agent_doc_chunk_filename ON public.agent_technical_doc_chunk(doc_filename);
CREATE INDEX IF NOT EXISTS idx_agent_doc_chunk_marca ON public.agent_technical_doc_chunk(marca);
CREATE INDEX IF NOT EXISTS idx_agent_doc_chunk_familia ON public.agent_technical_doc_chunk(familia_producto);
CREATE INDEX IF NOT EXISTS idx_agent_doc_chunk_tipo ON public.agent_technical_doc_chunk(tipo_documento);
-- Índice vectorial HNSW para búsqueda semántica rápida (cosine distance)
CREATE INDEX IF NOT EXISTS idx_agent_doc_chunk_embedding
    ON public.agent_technical_doc_chunk
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

CREATE TABLE IF NOT EXISTS public.agent_technical_profile (
    id bigserial PRIMARY KEY,
    canonical_family text NOT NULL,
    source_doc_filename text NOT NULL,
    source_doc_path_lower text NOT NULL,
    marca text,
    tipo_documento varchar(30) NOT NULL DEFAULT 'ficha_tecnica',
    profile_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    completeness_score numeric(6,4) NOT NULL DEFAULT 0,
    extraction_method varchar(30) NOT NULL DEFAULT 'hybrid',
    extraction_status varchar(30) NOT NULL DEFAULT 'ready',
    content_hash text,
    text_fingerprint text,
    generated_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_agent_technical_profile_family UNIQUE (canonical_family)
);
CREATE INDEX IF NOT EXISTS idx_agent_technical_profile_path ON public.agent_technical_profile(source_doc_path_lower);
CREATE INDEX IF NOT EXISTS idx_agent_technical_profile_marca ON public.agent_technical_profile(marca);
CREATE INDEX IF NOT EXISTS idx_agent_technical_profile_status ON public.agent_technical_profile(extraction_status);

CREATE INDEX IF NOT EXISTS idx_whatsapp_contacto_cliente ON public.whatsapp_contacto(cliente_id);
CREATE INDEX IF NOT EXISTS idx_agent_conversation_contacto ON public.agent_conversation(contacto_id);
CREATE INDEX IF NOT EXISTS idx_agent_conversation_estado ON public.agent_conversation(estado);
CREATE INDEX IF NOT EXISTS idx_agent_message_conversation ON public.agent_message(conversation_id);
CREATE INDEX IF NOT EXISTS idx_agent_message_provider ON public.agent_message(provider_message_id);
CREATE INDEX IF NOT EXISTS idx_agent_task_conversation ON public.agent_task(conversation_id);
CREATE INDEX IF NOT EXISTS idx_agent_task_estado ON public.agent_task(estado);
CREATE INDEX IF NOT EXISTS idx_agent_product_learning_phrase ON public.agent_product_learning(normalized_phrase);
CREATE INDEX IF NOT EXISTS idx_agent_quote_conversation ON public.agent_quote(conversation_id);
CREATE INDEX IF NOT EXISTS idx_agent_quote_cliente_estado ON public.agent_quote(cliente_id, estado);
CREATE INDEX IF NOT EXISTS idx_agent_quote_line_quote ON public.agent_quote_line(quote_id);
CREATE INDEX IF NOT EXISTS idx_agent_order_conversation ON public.agent_order(conversation_id);
CREATE INDEX IF NOT EXISTS idx_agent_order_cliente_estado ON public.agent_order(cliente_id, estado);
CREATE INDEX IF NOT EXISTS idx_agent_order_quote ON public.agent_order(quote_id);
CREATE INDEX IF NOT EXISTS idx_agent_order_line_order ON public.agent_order_line(order_id);
CREATE INDEX IF NOT EXISTS idx_agent_order_dispatch_status ON public.agent_order_dispatch(status, destination_store_code);
CREATE INDEX IF NOT EXISTS idx_agent_order_dispatch_conversation ON public.agent_order_dispatch(conversation_id);
CREATE INDEX IF NOT EXISTS idx_agent_transfer_request_status ON public.agent_transfer_request(status, destination_store_code);
CREATE INDEX IF NOT EXISTS idx_agent_transfer_request_order ON public.agent_transfer_request(order_id, order_dispatch_id);
CREATE INDEX IF NOT EXISTS idx_agent_user_role_active ON public.agent_user(role, is_active);
CREATE INDEX IF NOT EXISTS idx_agent_user_scope_user ON public.agent_user_scope(user_id);
CREATE INDEX IF NOT EXISTS idx_agent_user_scope_lookup ON public.agent_user_scope(scope_type, scope_value);
CREATE INDEX IF NOT EXISTS idx_agent_user_session_user ON public.agent_user_session(user_id);
CREATE INDEX IF NOT EXISTS idx_agent_user_session_token ON public.agent_user_session(token_hash);
CREATE INDEX IF NOT EXISTS idx_agent_user_session_active ON public.agent_user_session(expires_at, revoked_at);
CREATE INDEX IF NOT EXISTS idx_agent_catalog_product_marca ON public.agent_catalog_product(marca);
CREATE INDEX IF NOT EXISTS idx_agent_catalog_product_familia ON public.agent_catalog_product(familia_consulta_sugerida);
CREATE INDEX IF NOT EXISTS idx_agent_catalog_product_presentacion ON public.agent_catalog_product(presentacion_canonica);
CREATE INDEX IF NOT EXISTS idx_agent_catalog_alias_producto ON public.agent_catalog_alias(producto_codigo);
CREATE INDEX IF NOT EXISTS idx_agent_catalog_alias_lookup ON public.agent_catalog_alias(alias_type, alias_value);
CREATE INDEX IF NOT EXISTS idx_agent_catalog_family_lookup ON public.agent_catalog_family(familia_consulta_sugerida, marca);
CREATE INDEX IF NOT EXISTS idx_agent_catalog_presentation_lookup ON public.agent_catalog_presentation_alias(presentacion_canonica, alias_presentacion);
CREATE INDEX IF NOT EXISTS idx_agent_catalog_rule_lookup ON public.agent_catalog_rule(regla_clave, activo);
CREATE UNIQUE INDEX IF NOT EXISTS uq_agent_catalog_family_key
    ON public.agent_catalog_family (familia_consulta_sugerida, COALESCE(marca, ''), COALESCE(color_raiz, ''));
CREATE UNIQUE INDEX IF NOT EXISTS uq_agent_catalog_rule_key
    ON public.agent_catalog_rule (regla_clave, COALESCE(tipo_regla, ''), COALESCE(aplicacion, ''));

-- ===== PRECIOS Y CLIENTES =====
CREATE TABLE IF NOT EXISTS public.agent_precios (
    id SERIAL PRIMARY KEY,
    codigo INTEGER,
    descripcion_adicional TEXT,
    descripcion TEXT,
    referencia TEXT,
    codigo_barras TEXT,
    familia TEXT,
    subfamilia TEXT,
    marca TEXT,
    linea TEXT,
    cat_producto TEXT,
    aplicacion TEXT,
    departamento TEXT,
    seccion TEXT,
    sublinea TEXT,
    peso_articulo NUMERIC,
    pvp_sap NUMERIC DEFAULT 0,
    pvp_franquicia NUMERIC DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_agent_precios_referencia ON public.agent_precios(referencia);
CREATE INDEX IF NOT EXISTS idx_agent_precios_codigo ON public.agent_precios(codigo);

CREATE TABLE IF NOT EXISTS public.agent_clientes (
    id SERIAL PRIMARY KEY,
    codigo INTEGER,
    nombre TEXT,
    nif TEXT,
    direccion TEXT,
    telefono TEXT,
    poblacion TEXT,
    codigo_postal TEXT,
    provincia TEXT,
    riesgo_concedido NUMERIC,
    telefono_2 TEXT,
    tipo_documento TEXT,
    email TEXT,
    persona_contacto TEXT,
    ciudad TEXT,
    categoria TEXT,
    segmento TEXT,
    negocio TEXT,
    tipocliente2 TEXT,
    tipo_de_documento TEXT,
    nombre_1 TEXT,
    otros_nombres TEXT,
    apellido_1 TEXT,
    apellido_2 TEXT,
    razon_social TEXT,
    dv TEXT,
    clasificacion TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_agent_clientes_nif ON public.agent_clientes(nif);
CREATE INDEX IF NOT EXISTS idx_agent_clientes_codigo ON public.agent_clientes(codigo);
CREATE INDEX IF NOT EXISTS idx_agent_clientes_telefono ON public.agent_clientes(telefono);

COMMIT;