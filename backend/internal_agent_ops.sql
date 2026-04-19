BEGIN;

CREATE TABLE IF NOT EXISTS public.agent_role_profile (
    role_key varchar(80) PRIMARY KEY,
    display_name varchar(160) NOT NULL,
    base_role varchar(30) NOT NULL,
    prompt_mode varchar(60) NOT NULL,
    priority_focus jsonb NOT NULL DEFAULT '[]'::jsonb,
    allowed_kpis jsonb NOT NULL DEFAULT '[]'::jsonb,
    allowed_tools jsonb NOT NULL DEFAULT '[]'::jsonb,
    guidance_template text,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

INSERT INTO public.agent_role_profile (
    role_key, display_name, base_role, prompt_mode, priority_focus, allowed_kpis, allowed_tools, guidance_template
) VALUES
    (
        'gerencia_general',
        'Gerencia General',
        'gerente',
        'ejecutivo',
        '["ventas","cartera","inventario","alertas"]'::jsonb,
        '["ventas_hoy","ventas_mes","cartera_vencida","quiebres_criticos","sobrestock"]'::jsonb,
        '["consultar_ventas_internas","generar_lista_pendientes","sugerir_reposicion_bodega"]'::jsonb,
        'Prioriza resumen ejecutivo, desviaciones, riesgos inmediatos y siguientes acciones.'
    ),
    (
        'administracion',
        'Administracion',
        'administrador',
        'control',
        '["cartera","recaudo","pendientes"]'::jsonb,
        '["cartera_total","cartera_vencida","clientes_vencidos","recordatorios_abiertos"]'::jsonb,
        '["crear_recordatorio_interno","generar_lista_pendientes"]'::jsonb,
        'Prioriza control, vencimientos, seguimiento y bloqueos operativos.'
    ),
    (
        'cartera',
        'Cartera',
        'administrador',
        'cobranza',
        '["cartera","vencimientos","seguimiento"]'::jsonb,
        '["cartera_31_60","cartera_61_90","cartera_91_plus","clientes_criticos"]'::jsonb,
        '["crear_recordatorio_interno","generar_lista_pendientes"]'::jsonb,
        'Prioriza vencidos, clientes criticos, proximos compromisos y recaudo esperado.'
    ),
    (
        'compras',
        'Compras',
        'administrador',
        'abastecimiento',
        '["reposicion","sobrestock","sin_movimiento"]'::jsonb,
        '["quiebres_criticos","reposicion_recomendada","sobrestock","sin_movimiento"]'::jsonb,
        '["sugerir_reposicion_bodega","generar_lista_pendientes"]'::jsonb,
        'Prioriza faltantes, referencias a reponer y capital atrapado en inventario.'
    ),
    (
        'bodega',
        'Bodega',
        'operador',
        'operativo',
        '["quiebres","traslados_potenciales","reposicion"]'::jsonb,
        '["quiebres_criticos","reposicion_recomendada","stock_cero"]'::jsonb,
        '["sugerir_reposicion_bodega","crear_recordatorio_interno","generar_lista_pendientes"]'::jsonb,
        'Prioriza referencias agotadas, reabastecimiento y seguimiento por sede.'
    ),
    (
        'comercial',
        'Comercial',
        'vendedor',
        'ventas',
        '["ventas","clientes","oportunidades"]'::jsonb,
        '["ventas_hoy","ventas_mes","top_clientes","clientes_con_cartera"]'::jsonb,
        '["consultar_ventas_internas","crear_recordatorio_interno","generar_lista_pendientes"]'::jsonb,
        'Prioriza avance comercial, clientes con riesgo y acciones de seguimiento.'
    ),
    (
        'empleado_operativo',
        'Empleado Operativo',
        'empleado',
        'soporte',
        '["pendientes","inventario"]'::jsonb,
        '["quiebres_criticos","recordatorios_abiertos"]'::jsonb,
        '["crear_recordatorio_interno","generar_lista_pendientes"]'::jsonb,
        'Prioriza ayudas concretas, pendientes y datos operativos verificables.'
    )
ON CONFLICT (role_key) DO UPDATE SET
    display_name = EXCLUDED.display_name,
    base_role = EXCLUDED.base_role,
    prompt_mode = EXCLUDED.prompt_mode,
    priority_focus = EXCLUDED.priority_focus,
    allowed_kpis = EXCLUDED.allowed_kpis,
    allowed_tools = EXCLUDED.allowed_tools,
    guidance_template = EXCLUDED.guidance_template,
    updated_at = now();

CREATE TABLE IF NOT EXISTS public.agent_user_role_profile (
    id bigserial PRIMARY KEY,
    user_id bigint NOT NULL REFERENCES public.agent_user(id) ON DELETE CASCADE,
    role_key varchar(80) NOT NULL REFERENCES public.agent_role_profile(role_key) ON DELETE RESTRICT,
    is_active boolean NOT NULL DEFAULT true,
    assigned_by_user_id bigint REFERENCES public.agent_user(id) ON DELETE SET NULL,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_agent_user_role_profile UNIQUE (user_id, role_key)
);
CREATE INDEX IF NOT EXISTS idx_agent_user_role_profile_user_active ON public.agent_user_role_profile(user_id, is_active);

CREATE TABLE IF NOT EXISTS public.agent_internal_routine (
    routine_key varchar(80) PRIMARY KEY,
    display_name varchar(160) NOT NULL,
    command_token varchar(80) NOT NULL UNIQUE,
    role_key varchar(80) REFERENCES public.agent_role_profile(role_key) ON DELETE SET NULL,
    description text,
    prompt_hint text,
    default_filters jsonb NOT NULL DEFAULT '{}'::jsonb,
    is_active boolean NOT NULL DEFAULT true,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

INSERT INTO public.agent_internal_routine (
    routine_key, display_name, command_token, role_key, description, prompt_hint, default_filters
) VALUES
    (
        'rutina_diaria_gerencia',
        'Rutina Diaria Gerencia',
        '/rutina_diaria_gerencia',
        'gerencia_general',
        'Resumen ejecutivo de ventas, cartera e inventario critico.',
        'Entrega resumen ejecutivo corto: ventas hoy/mes, cartera vencida, quiebres criticos y acciones sugeridas.',
        '{"horizonte":"hoy"}'::jsonb
    ),
    (
        'rutina_cartera',
        'Rutina Cartera',
        '/rutina_cartera',
        'cartera',
        'Seguimiento de cartera vencida y compromisos del dia.',
        'Prioriza clientes 61-90 y 91+, promesas de pago y recordatorios proximos.',
        '{"bucket":"vencida"}'::jsonb
    ),
    (
        'rutina_bodega',
        'Rutina Bodega',
        '/rutina_bodega',
        'bodega',
        'Quiebres, referencias para reposicion y pendientes de sede.',
        'Prioriza quiebres criticos y referencias con stock por debajo del punto de reposicion.',
        '{"focus":"quiebres"}'::jsonb
    ),
    (
        'rutina_compras',
        'Rutina Compras',
        '/rutina_compras',
        'compras',
        'Reposicion sugerida y capital atrapado en sobrestock.',
        'Resume faltantes, sobrestock y referencias sin movimiento.',
        '{"focus":"reposicion"}'::jsonb
    ),
    (
        'rutina_comercial',
        'Rutina Comercial',
        '/rutina_comercial',
        'comercial',
        'Avance comercial y cuentas con riesgo de cartera.',
        'Resume ventas del periodo, asesores top y clientes a recuperar.',
        '{"focus":"ventas"}'::jsonb
    )
ON CONFLICT (routine_key) DO UPDATE SET
    display_name = EXCLUDED.display_name,
    command_token = EXCLUDED.command_token,
    role_key = EXCLUDED.role_key,
    description = EXCLUDED.description,
    prompt_hint = EXCLUDED.prompt_hint,
    default_filters = EXCLUDED.default_filters,
    is_active = true,
    updated_at = now();

CREATE TABLE IF NOT EXISTS public.agent_internal_routine_run (
    id bigserial PRIMARY KEY,
    routine_key varchar(80) NOT NULL REFERENCES public.agent_internal_routine(routine_key) ON DELETE RESTRICT,
    user_id bigint REFERENCES public.agent_user(id) ON DELETE SET NULL,
    conversation_id bigint REFERENCES public.agent_conversation(id) ON DELETE SET NULL,
    input_payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    output_summary text,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.agent_internal_memory_entry (
    id bigserial PRIMARY KEY,
    owner_user_id bigint REFERENCES public.agent_user(id) ON DELETE SET NULL,
    role_key varchar(80) REFERENCES public.agent_role_profile(role_key) ON DELETE SET NULL,
    item_type varchar(40) NOT NULL DEFAULT 'pendiente',
    title varchar(220) NOT NULL,
    summary text,
    status varchar(30) NOT NULL DEFAULT 'pendiente',
    priority varchar(20) NOT NULL DEFAULT 'media',
    due_at timestamptz,
    source_channel varchar(30) NOT NULL DEFAULT 'whatsapp',
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    resolved_at timestamptz,
    CONSTRAINT chk_agent_internal_memory_type CHECK (item_type IN ('pendiente', 'nota', 'seguimiento', 'hallazgo')),
    CONSTRAINT chk_agent_internal_memory_status CHECK (status IN ('pendiente', 'en_proceso', 'resuelto', 'cancelado')),
    CONSTRAINT chk_agent_internal_memory_priority CHECK (priority IN ('alta', 'media', 'baja'))
);
CREATE INDEX IF NOT EXISTS idx_agent_internal_memory_owner_status ON public.agent_internal_memory_entry(owner_user_id, status, due_at);
CREATE INDEX IF NOT EXISTS idx_agent_internal_memory_role_status ON public.agent_internal_memory_entry(role_key, status, due_at);

CREATE TABLE IF NOT EXISTS public.agent_internal_reminder (
    id bigserial PRIMARY KEY,
    owner_user_id bigint REFERENCES public.agent_user(id) ON DELETE SET NULL,
    role_key varchar(80) REFERENCES public.agent_role_profile(role_key) ON DELETE SET NULL,
    title varchar(220) NOT NULL,
    detail text,
    due_at timestamptz,
    priority varchar(20) NOT NULL DEFAULT 'media',
    status varchar(30) NOT NULL DEFAULT 'pendiente',
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    completed_at timestamptz,
    CONSTRAINT chk_agent_internal_reminder_priority CHECK (priority IN ('alta', 'media', 'baja')),
    CONSTRAINT chk_agent_internal_reminder_status CHECK (status IN ('pendiente', 'completado', 'cancelado'))
);
CREATE INDEX IF NOT EXISTS idx_agent_internal_reminder_owner_status ON public.agent_internal_reminder(owner_user_id, status, due_at);
CREATE INDEX IF NOT EXISTS idx_agent_internal_reminder_role_status ON public.agent_internal_reminder(role_key, status, due_at);

CREATE TABLE IF NOT EXISTS public.agent_internal_action_log (
    id bigserial PRIMARY KEY,
    user_id bigint REFERENCES public.agent_user(id) ON DELETE SET NULL,
    role_key varchar(80) REFERENCES public.agent_role_profile(role_key) ON DELETE SET NULL,
    tool_name varchar(120) NOT NULL,
    action_status varchar(30) NOT NULL DEFAULT 'ok',
    action_summary text,
    payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_agent_internal_action_log_user_tool ON public.agent_internal_action_log(user_id, tool_name, created_at DESC);

CREATE TABLE IF NOT EXISTS public.agent_internal_alert_event (
    id bigserial PRIMARY KEY,
    alert_type varchar(60) NOT NULL,
    alert_key varchar(180) NOT NULL,
    role_key varchar(80) REFERENCES public.agent_role_profile(role_key) ON DELETE SET NULL,
    severity varchar(20) NOT NULL DEFAULT 'media',
    title varchar(240) NOT NULL,
    detail text,
    payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    detected_at timestamptz NOT NULL DEFAULT now(),
    acknowledged_at timestamptz,
    resolved_at timestamptz,
    CONSTRAINT uq_agent_internal_alert_event UNIQUE (alert_type, alert_key)
);

DROP MATERIALIZED VIEW IF EXISTS public.mv_internal_sales_daily CASCADE;
CREATE MATERIALIZED VIEW public.mv_internal_sales_daily AS
SELECT
    fecha_venta AS sales_date,
    serie,
    codigo_vendedor,
    nom_vendedor,
    grupo_vendedor,
    COUNT(*) AS documents,
    COALESCE(SUM(valor_venta_neto), 0) AS net_sales,
    COALESCE(SUM(unidades_vendidas_netas), 0) AS net_units,
    COUNT(DISTINCT cliente_id) AS active_clients
FROM public.vw_ventas_netas
WHERE fecha_venta IS NOT NULL
GROUP BY fecha_venta, serie, codigo_vendedor, nom_vendedor, grupo_vendedor;
CREATE INDEX IF NOT EXISTS idx_mv_internal_sales_daily_date ON public.mv_internal_sales_daily(sales_date DESC);
CREATE INDEX IF NOT EXISTS idx_mv_internal_sales_daily_store ON public.mv_internal_sales_daily(serie, sales_date DESC);
CREATE INDEX IF NOT EXISTS idx_mv_internal_sales_daily_seller ON public.mv_internal_sales_daily(codigo_vendedor, sales_date DESC);

DROP MATERIALIZED VIEW IF EXISTS public.mv_internal_cartera_cliente CASCADE;
CREATE MATERIALIZED VIEW public.mv_internal_cartera_cliente AS
SELECT
    cod_cliente,
    MAX(nombre_cliente) AS nombre_cliente,
    MAX(nit) AS nit,
    MAX(nom_vendedor) AS nom_vendedor,
    MAX(zona) AS zona,
    COUNT(*) AS documentos,
    COALESCE(SUM(importe_normalizado), 0) AS balance_total,
    COALESCE(SUM(CASE WHEN COALESCE(dias_vencido, 0) <= 0 THEN importe_normalizado ELSE 0 END), 0) AS balance_corriente,
    COALESCE(SUM(CASE WHEN COALESCE(dias_vencido, 0) BETWEEN 1 AND 30 THEN importe_normalizado ELSE 0 END), 0) AS balance_1_30,
    COALESCE(SUM(CASE WHEN COALESCE(dias_vencido, 0) BETWEEN 31 AND 60 THEN importe_normalizado ELSE 0 END), 0) AS balance_31_60,
    COALESCE(SUM(CASE WHEN COALESCE(dias_vencido, 0) BETWEEN 61 AND 90 THEN importe_normalizado ELSE 0 END), 0) AS balance_61_90,
    COALESCE(SUM(CASE WHEN COALESCE(dias_vencido, 0) > 90 THEN importe_normalizado ELSE 0 END), 0) AS balance_91_plus,
    COALESCE(MAX(dias_vencido), 0) AS max_dias_vencido
FROM public.vw_estado_cartera
WHERE cod_cliente IS NOT NULL
GROUP BY cod_cliente;
CREATE INDEX IF NOT EXISTS idx_mv_internal_cartera_cliente_cliente ON public.mv_internal_cartera_cliente(cod_cliente);
CREATE INDEX IF NOT EXISTS idx_mv_internal_cartera_cliente_vendedor ON public.mv_internal_cartera_cliente(nom_vendedor);
CREATE INDEX IF NOT EXISTS idx_mv_internal_cartera_cliente_zona ON public.mv_internal_cartera_cliente(zona);

DROP MATERIALIZED VIEW IF EXISTS public.mv_internal_inventory_health CASCADE;
CREATE MATERIALIZED VIEW public.mv_internal_inventory_health AS
WITH base AS (
    SELECT
        cod_almacen,
        almacen_nombre,
        referencia_normalizada,
        MAX(referencia) AS referencia,
        MAX(descripcion) AS descripcion,
        MAX(marca) AS marca,
        MAX(familia_clasificacion) AS familia_clasificacion,
        COALESCE(SUM(stock_disponible), 0) AS stock_total,
        COALESCE(AVG(costo_promedio_und), 0) AS costo_promedio_und,
        COALESCE(SUM(unidades_vendidas), 0) AS unidades_vendidas_total,
        COALESCE(MAX(historial_ventas), 0) AS historial_ventas_metric,
        COALESCE(MAX(lead_time_proveedor), 0) AS lead_time_proveedor_dias
    FROM public.vw_inventario_agente
    GROUP BY cod_almacen, almacen_nombre, referencia_normalizada
)
SELECT
    cod_almacen,
    almacen_nombre,
    referencia_normalizada,
    referencia,
    descripcion,
    marca,
    familia_clasificacion,
    stock_total,
    costo_promedio_und,
    stock_total * costo_promedio_und AS inventory_value,
    unidades_vendidas_total,
    historial_ventas_metric,
    lead_time_proveedor_dias,
    GREATEST(
        CEIL(
            ((GREATEST(historial_ventas_metric, 0) / 30.0) * GREATEST(NULLIF(lead_time_proveedor_dias, 0), 7))
            + GREATEST(historial_ventas_metric * 0.25, 1)
        ),
        1
    )::numeric(18,2) AS reorder_point,
    GREATEST(
        CEIL(
            (((GREATEST(historial_ventas_metric, 0) / 30.0) * GREATEST(NULLIF(lead_time_proveedor_dias, 0), 7))
            + GREATEST(historial_ventas_metric * 0.25, 1)) - stock_total
        ),
        0
    )::numeric(18,2) AS reorder_qty_recommended,
    CASE
        WHEN stock_total <= 0 AND GREATEST(historial_ventas_metric, 0) > 0 THEN 'quiebre_critico'
        WHEN stock_total < GREATEST(
            CEIL(
                ((GREATEST(historial_ventas_metric, 0) / 30.0) * GREATEST(NULLIF(lead_time_proveedor_dias, 0), 7))
                + GREATEST(historial_ventas_metric * 0.25, 1)
            ),
            1
        ) THEN 'reposicion_recomendada'
        WHEN stock_total > GREATEST(historial_ventas_metric * 4, 12) AND GREATEST(historial_ventas_metric, 0) > 0 THEN 'sobrestock'
        WHEN stock_total > 0 AND GREATEST(historial_ventas_metric, 0) = 0 AND GREATEST(unidades_vendidas_total, 0) = 0 THEN 'sin_movimiento'
        ELSE 'saludable'
    END AS health_status
FROM base;
CREATE INDEX IF NOT EXISTS idx_mv_internal_inventory_health_store ON public.mv_internal_inventory_health(cod_almacen, health_status);
CREATE INDEX IF NOT EXISTS idx_mv_internal_inventory_health_ref ON public.mv_internal_inventory_health(referencia_normalizada);
CREATE INDEX IF NOT EXISTS idx_mv_internal_inventory_health_status ON public.mv_internal_inventory_health(health_status);

CREATE OR REPLACE VIEW public.vw_internal_alert_candidates AS
SELECT
    'cartera_critica'::varchar(60) AS alert_type,
    'CARTERA-' || cod_cliente AS alert_key,
    'cartera'::varchar(80) AS assigned_role_key,
    CASE
        WHEN balance_91_plus >= 5000000 THEN 'alta'
        WHEN (balance_61_90 + balance_91_plus) >= 2000000 THEN 'media'
        ELSE 'baja'
    END AS severity,
    ('Cliente con cartera vencida: ' || COALESCE(nombre_cliente, cod_cliente))::varchar(240) AS title,
    format(
        'Saldo total %s. Vencido 61-90: %s. Vencido >90: %s. Vendedor: %s.',
        balance_total,
        balance_61_90,
        balance_91_plus,
        COALESCE(nom_vendedor, 'SIN VENDEDOR')
    ) AS detail,
    jsonb_build_object(
        'cod_cliente', cod_cliente,
        'nombre_cliente', nombre_cliente,
        'nom_vendedor', nom_vendedor,
        'zona', zona,
        'balance_total', balance_total,
        'balance_61_90', balance_61_90,
        'balance_91_plus', balance_91_plus
    ) AS payload
FROM public.mv_internal_cartera_cliente
WHERE (balance_61_90 + balance_91_plus) > 0

UNION ALL

SELECT
    'quiebre_critico'::varchar(60) AS alert_type,
    'QUIEBRE-' || COALESCE(cod_almacen, 'NA') || '-' || referencia_normalizada AS alert_key,
    'bodega'::varchar(80) AS assigned_role_key,
    'alta'::varchar(20) AS severity,
    ('Quiebre critico en ' || COALESCE(almacen_nombre, cod_almacen))::varchar(240) AS title,
    format(
        'Referencia %s (%s) con stock %s y historial %s.',
        COALESCE(referencia, referencia_normalizada),
        COALESCE(descripcion, 'SIN DESCRIPCION'),
        stock_total,
        historial_ventas_metric
    ) AS detail,
    jsonb_build_object(
        'cod_almacen', cod_almacen,
        'almacen_nombre', almacen_nombre,
        'referencia', referencia,
        'descripcion', descripcion,
        'stock_total', stock_total,
        'reorder_qty_recommended', reorder_qty_recommended
    ) AS payload
FROM public.mv_internal_inventory_health
WHERE health_status = 'quiebre_critico'

UNION ALL

SELECT
    'sobrestock'::varchar(60) AS alert_type,
    'OVER-' || COALESCE(cod_almacen, 'NA') || '-' || referencia_normalizada AS alert_key,
    'compras'::varchar(80) AS assigned_role_key,
    'media'::varchar(20) AS severity,
    ('Sobrestock en ' || COALESCE(almacen_nombre, cod_almacen))::varchar(240) AS title,
    format(
        'Referencia %s (%s) con stock %s y valor inventario %s.',
        COALESCE(referencia, referencia_normalizada),
        COALESCE(descripcion, 'SIN DESCRIPCION'),
        stock_total,
        inventory_value
    ) AS detail,
    jsonb_build_object(
        'cod_almacen', cod_almacen,
        'almacen_nombre', almacen_nombre,
        'referencia', referencia,
        'descripcion', descripcion,
        'stock_total', stock_total,
        'inventory_value', inventory_value
    ) AS payload
FROM public.mv_internal_inventory_health
WHERE health_status = 'sobrestock';

CREATE OR REPLACE VIEW public.vw_internal_pending_queue AS
SELECT
    'recordatorio'::varchar(30) AS item_type,
    id AS item_id,
    owner_user_id,
    role_key,
    title,
    detail AS summary,
    due_at,
    priority,
    status,
    created_at,
    CASE priority WHEN 'alta' THEN 1 WHEN 'media' THEN 2 ELSE 3 END AS priority_rank
FROM public.agent_internal_reminder
WHERE status = 'pendiente'

UNION ALL

SELECT
    item_type::varchar(30) AS item_type,
    id AS item_id,
    owner_user_id,
    role_key,
    title,
    summary,
    due_at,
    priority,
    status,
    created_at,
    CASE priority WHEN 'alta' THEN 1 WHEN 'media' THEN 2 ELSE 3 END AS priority_rank
FROM public.agent_internal_memory_entry
WHERE status IN ('pendiente', 'en_proceso');

CREATE TABLE IF NOT EXISTS public.agent_operational_doc_chunk (
    id bigserial PRIMARY KEY,
    doc_filename text NOT NULL,
    doc_path_lower text NOT NULL,
    chunk_index integer NOT NULL DEFAULT 0,
    chunk_text text NOT NULL,
    area_key varchar(80),
    role_key varchar(80),
    tipo_documento varchar(40) NOT NULL DEFAULT 'procedimiento_operativo',
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    embedding vector(1536),
    token_count integer,
    ingested_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_agent_operational_doc_chunk UNIQUE (doc_path_lower, chunk_index)
);
CREATE INDEX IF NOT EXISTS idx_agent_operational_doc_chunk_area ON public.agent_operational_doc_chunk(area_key);
CREATE INDEX IF NOT EXISTS idx_agent_operational_doc_chunk_role ON public.agent_operational_doc_chunk(role_key);
CREATE INDEX IF NOT EXISTS idx_agent_operational_doc_chunk_tipo ON public.agent_operational_doc_chunk(tipo_documento);

CREATE TABLE IF NOT EXISTS public.agent_operational_profile (
    id bigserial PRIMARY KEY,
    profile_key varchar(120) NOT NULL UNIQUE,
    role_key varchar(80),
    area_key varchar(80),
    profile_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    extraction_status varchar(30) NOT NULL DEFAULT 'ready',
    source_doc_path_lower text,
    updated_at timestamptz NOT NULL DEFAULT now(),
    created_at timestamptz NOT NULL DEFAULT now()
);

COMMIT;