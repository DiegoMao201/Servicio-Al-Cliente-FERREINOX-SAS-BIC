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

COMMIT;