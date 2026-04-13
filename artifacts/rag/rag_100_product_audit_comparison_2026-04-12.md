# Comparación de Auditoría RAG

- Generado: 2026-04-12T20:08:06.026617
- Baseline: artifacts\rag\snapshots\2026-04-12-pre-reingest\rag_100_product_audit_2026-04-12.json
- Actual: artifacts\rag\rag_100_product_audit_2026-04-12.json

## Totales

- Ready baseline: 306
- Ready actual: 325
- Completitud promedio baseline: 0.6819
- Completitud promedio actual: 0.7703
- Delta completitud promedio: 0.0884

## Delta de Campos

- surface_targets: 91 -> 100 (delta 9)
- restricted_surfaces: 5 -> 33 (delta 28)
- application_methods: 83 -> 84 (delta 1)
- diagnostic_questions: 0 -> 100 (delta 100)
- alerts: 100 -> 100 (delta 0)
- source_excerpts: 49 -> 100 (delta 51)
- mixing_ratio: 0 -> 0 (delta 0)
- drying_times: 100 -> 100 (delta 0)
- dilution: 100 -> 100 (delta 0)

## Comparación de Productos

- Familias comparables: 86
- Mejoraron: 86
- Empeoraron: 0
- Sin cambio claro: 0

### Campos ganados más frecuentes

- diagnostic_questions: 86
- source_excerpts: 44
- surface_targets: 8
- application_methods: 1

### Campos perdidos más frecuentes

- mixing_ratio: 9

### Top Mejoras

- PINTUCO IMPADOC LISTO: score 0.8889 -> 0.9167 | ganó diagnostic_questions, source_excerpts, surface_targets
- PINTUCO AEROCOLOR MULTISUPERFICIE: score 0.7778 -> 0.9167 | ganó application_methods, diagnostic_questions
- PINTUCO CONSTRUCLEANER LIMPIADOR NO CORROSIVO: score 0.7778 -> 0.8333 | ganó diagnostic_questions, source_excerpts
- PINTUCO CONSTRUCLEANER LIMPIADOR ECOLOGICO LADRILLO: score 0.7778 -> 0.8333 | ganó diagnostic_questions, source_excerpts
- PINTUCO ALTA TEMPERATURA ALUMINIO 904: score 0.7778 -> 0.8333 | ganó diagnostic_questions, source_excerpts
- PINTUCO AEROCOLOR PARA RINES: score 0.7778 -> 0.8333 | ganó diagnostic_questions, surface_targets
- PINTUCO AEROCOLOR ALTAS TEMPERATURAS: score 0.7778 -> 0.8333 | ganó diagnostic_questions, source_excerpts
- PINTUCO ACRILICA PARA MANTENIMIENTO: score 0.7778 -> 0.8333 | ganó diagnostic_questions, source_excerpts
- MASTIC EPOXY ES: score 0.7778 -> 0.8333 | ganó diagnostic_questions, source_excerpts
- INTERTUF 262: score 0.7778 -> 0.8333 | ganó diagnostic_questions, source_excerpts
- INTERSEAL 670HS EN: score 0.7778 -> 0.8333 | ganó diagnostic_questions, surface_targets
- EPOXI POLIAMIDA ES: score 0.7778 -> 0.8333 | ganó diagnostic_questions, source_excerpts
- ACRILICA MANTENIMIENTO ES: score 0.7778 -> 0.8333 | ganó diagnostic_questions, source_excerpts
- REMOVEDOR PINTUCO 1020: score 0.8889 -> 0.9167 | ganó diagnostic_questions, surface_targets
- PINTUCOAT PLUS: score 0.8889 -> 0.9167 | ganó diagnostic_questions, source_excerpts

### Top Retrocesos

- Ninguno
