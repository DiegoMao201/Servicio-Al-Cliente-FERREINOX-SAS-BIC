SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_name IN (
    'raw_ventas_detalle',
    'raw_rotacion_inventarios',
    'raw_cartera_detalle',
    'raw_cobros_detalle',
    'raw_proveedores_pagos'
)
ORDER BY table_name;

SELECT routine_name
FROM information_schema.routines
WHERE specific_schema = 'public'
  AND routine_name IN (
    'fn_normalize_text',
    'fn_keep_alnum',
    'fn_digits_only',
    'fn_map_zona_from_serie'
)
ORDER BY routine_name;

SELECT table_name
FROM information_schema.views
WHERE table_schema = 'public'
  AND table_name IN (
    'vw_ventas_netas',
    'vw_albaranes_pendientes',
    'vw_estado_cartera',
    'vw_cuentas_por_pagar',
    'vw_recaudos',
    'vw_cliente_contexto_agente'
)
ORDER BY table_name;