# Orden Del Repo Y De Las Pruebas

## Problema Actual

Hoy el repo mezcla en raiz:

- tests funcionales
- scripts de diagnostico
- scripts de auditoria
- scripts de exploracion
- resultados de baterias
- reportes markdown
- utilidades temporales con prefijo `_`

Eso dificulta entender:

1. Que es produccion.
2. Que es prueba formal.
3. Que es experimento.
4. Que archivo genera que resultado.

## Regla De Limpieza

No mover de golpe los archivos existentes hasta actualizar imports, comandos y habitos de ejecucion.

Primero clasificar.
Despues mover por grupos.

## Estructura Objetivo Recomendada

```text
backend/
frontend/
docs/
tools/
tools/diagnostics/
tools/diagnostics/legacy/
tools/audits/
tools/exploration/
tools/maintenance/
tools/data_prep/
tools/validation/
tests/
tests/internal/
tests/customer/
tests/rag/
tests/regression/
tests/fixtures/
reports/
reports/audits/
reports/regressions/
reports/rag/
artifacts/
data/
```

## Clasificacion Inicial De Archivos Actuales

### Tests De Regresion Y Comportamiento

Mover a `tests/regression/`:

- `test_behavioral_rules.py`
- `test_commercial_close_regression.py`
- `test_conversational.py`
- `test_diagnostic_first.py`
- `test_inventory_flow_regression.py`
- `test_name_confirm.py`
- `test_question_filter.py`
- `test_quality_system.py`
- `test_fixes_targeted.py`
- `test_agent_v3_preload.py`

### Tests RAG Y Tecnicos

Mover a `tests/rag/`:

- `test_rag_masivo.py`
- `test_rag_quality.py`
- `test_rag_validation.py`
- `test_expert_retrieval.py`
- `test_technical_commercial_bridge.py`
- `test_technical_product_canonicalization.py`
- `test_technical_profile_extraction.py`
- `rag_spot_test.py`

### Tests E2E

Mover a `tests/internal/` o `tests/customer/` segun el caso:

- `test_pipeline_e2e.py`
- `test_pipeline_super_agente.py`
- `test_e2e_advisory_enforcement.py`
- `test_claims_flow.py`
- `test_super_agent.py`
- `test_stress_superferro.py`
- `test_omega.py`

### Baterias De Politicas

Mover a `tests/regression/`:

- `test_global_policy_matrix.py`
- `test_global_policy_matrix_200.py`
- `test_global_policy_matrix_multisurface_contradictions.py`
- `test_global_policy_matrix_preparation_priority_negation.py`

### Scripts Temporales O Legacy

Ubicados en `tools/diagnostics/legacy/`:

- `_test_embudo_cierre.py`
- `_test_new_fixes.py`
- `_test_surface_filtering.py`
- `_test_universal_guard.py`
- `_diag_guardia_retest.py`

### Auditorias

Ubicadas en `tools/audits/`:

- `audit_expert_full.py`
- `audit_expert_knowledge.py`
- `audit_rag_from_policy_batteries.py`
- `audit_rag_portfolio.py`
- `audit_rag_vs_inventario.py`
- `compare_rag_audits.py`
- `_audit_full_rag.py`
- `_audit_rag_diagnostic.py`

### Diagnosticos Y Exploracion

Ubicadas en `tools/diagnostics/` o `tools/exploration/`:

- `_diag_inventory_by_desc.py`
- `_diag_inventory_movement.py`
- `_diag_prices.py`
- `_diag_rag_docs.py`
- `_diag_rag_fachada.py`
- `_diag_rag_live.py`
- `_diag_ref_format.py`
- `_diag_scoring.py`
- `explore_cat.py`
- `explore_catalog.py`
- `explore_rag.py`
- `explore_xlsx.py`
- `_explore_abracol.py`

### PostgREST

Ubicado en `tools/postgrest/` y `docs/postgrest/`:

- `tools/postgrest/sync_official_postgrest.py`
- `docs/postgrest/POSTGRES_ESTRUCTURA_LIMPIA.txt`
- `docs/postgrest/POSTGRES_EXPOSICION_Y_AUTOMATIZACION.txt`
- `docs/postgrest/POSTGRES_RESET_Y_PRUEBA.txt`
- `docs/postgrest/SETUP_PGVECTOR_COOLIFY.sql`

### Resultados Y Reportes

Mover a `reports/`:

- `_full_regression_results.txt`
- `_rag_regression_results.txt`
- `reports/audits/_audit_results.json`
- `test_omega_results.json`
- `RESULTADO_BATERIA_MATRIZ_GLOBAL_200.md`
- `RESULTADO_BATERIA_MULTI_SUPERFICIE_Y_CONTRADICCIONES.md`
- `RESULTADO_BATERIA_PREPARACION_PRIORIDAD_NEGACION_DOBLE_CONTRADICCION.md`

### Parsers De Reportes

Ubicados en `tools/maintenance/`:

- `_parse_all_results.py`
- `_parse_report.py`
- `_read_results.py`
- `parse_results.py`

### Mantenimiento Y Chequeos Puntuales

Ubicados en `tools/maintenance/`:

- `_read_rules.py`
- `_read_all_rules.py`
- `_check_altas_temp_profile.py`
- `_check_schema.py`
- `_check_surface2.py`
- `_check_surface_metadata.py`
- `_inspect_ventas.py`

### Preparacion De Datos

Ubicados en `tools/data_prep/`:

- `_analyze_abracol.py`
- `_apply_all_fixes.py`
- `_apply_canon_from_csv.py`
- `_apply_inventario_activo.py`
- `_enrich_guides.py`
- `_gen_validacion_canon.py`
- `_setup_abracol.py`

### Validacion Ligera

Ubicados en `tools/validation/`:

- `_count_guides.py`
- `_validate_guides.py`
- `_rag_check.py`

## Orden De Ejecucion Recomendado

### Paso 1

Crear carpetas nuevas sin mover nada.

### Paso 2

Agregar un README corto dentro de cada carpeta nueva explicando que vive ahi.

### Paso 3

Mover primero solo reportes y auditorias, porque rompen menos.

### Paso 4

Mover tests con wrappers temporales en raiz si todavia ejecutas por nombre antiguo.

### Paso 5

Mover scripts diagnosticos y experimentales.

## Orden Para El Agente Internal

El arbol objetivo de pruebas para `internal` debe ser:

```text
tests/internal/
  test_internal_inventory.py
  test_internal_store_availability.py
  test_internal_prices.py
  test_internal_sales_bi.py
  test_internal_rag_technical.py
  test_internal_technical_documents.py
  test_internal_guardrails.py
```

## Orden Para El Agente Customer

El arbol objetivo de pruebas para `customer` debe ser:

```text
tests/customer/
  test_customer_rag_guidance.py
  test_customer_technical_documents.py
  test_customer_identity_validation.py
  test_customer_portfolio.py
  test_customer_purchase_history.py
  test_customer_claims_validation.py
  test_customer_handoff_summary.py
```

## Recomendacion Practica

No hagas una reconstruccion total del repo antes de sacar `internal`.

Haz esto:

1. Separar primero agentes y toolsets.
2. Congelar features nuevas.
3. Reordenar reportes y auditorias.
4. Luego mover tests por familia.

Eso te da limpieza sin parar el avance.