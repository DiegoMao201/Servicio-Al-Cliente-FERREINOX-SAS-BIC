# 🔧 REPORTE DE SESIÓN — 10 de Abril 2026

## Resumen Ejecutivo

**Duración:** ~12 horas de trabajo continuo  
**Commits:** 4 (todos en `main`, desplegados automáticamente vía Coolify)  
**HEAD actual:** `24108e7`  

| Métrica | Resultado |
|---------|-----------|
| **Tests filtros semánticos** | ✅ 22/22 PASS (100%) |
| **Re-run categorías 502/503** | ✅ 16P / 1W / 0F (94%) |
| **Regresión agente completo** | ✅ 88P / 7W / 5F (100 turnos) |
| **Regresión RAG** | ⚠️ 71P / 9W / 14F (94 tests, 7 esperados) |
| **Auditoría RAG 50 escenarios** | ⚠️ 32P / 9W / 9F |
| **Productos Abracol integrados** | ✅ 783 importados, 778 enriquecidos en mv_productos |

---

## 📦 Commits (cronológico)

### 1. `f9e3198` — Filtros Semánticos POST-RAG + Query Expansion + Pintulac eliminado
**Fecha:** 2026-04-10 07:58  
**Archivos:** `backend/main.py`

**Cambios implementados:**
- **POST-RAG disambiguation guards** en bloque `<thinking>`: el agente ahora evalúa si los productos del RAG son relevantes antes de recomendarlos
- **PRE-RAG query expansion**: las consultas del usuario se expanden con sinónimos y contexto técnico antes de buscar en el RAG
- **Eliminación Pintulac**: guardias para impedir que el agente recomiende productos de la competencia (Pintulac) que aparecían en fichas técnicas indexadas
- **Nuevas reglas de superficie** (`_SURFACE_PRODUCT_RULES`): mapeo superficie→producto para barnex vs pintulux en interiores

---

### 2. `ad50e6a` — Expand PROBLEM_SIGNALS + barnex interior guard
**Fecha:** 2026-04-10 08:37  
**Archivos:** `backend/main.py`

**Cambios implementados:**
- Ampliación de **`_PROBLEM_SIGNALS`** (~línea 17683): más señales de problema que activan el flujo diagnóstico RAG (humedad, manchas, descascaramiento, etc.)
- **Barnex interior guard**: cuando el usuario pide pintar madera de blanco en interior, el sistema redirige a esmalte/pintulux en vez de barniz barnex
- Corrección de fallos donde el agente NO llamaba al RAG en consultas legítimas de superficie/problema

---

### 3. `4c07fee` — GUARDIA PREGUNTA-TÉCNICA
**Fecha:** 2026-04-10 09:33  
**Archivos:** `backend/main.py`

**Cambios implementados:**
- **GUARDIA PREGUNTA-TÉCNICA** (~línea 17822): impide que el agente genere cotización cuando el usuario hace preguntas técnicas puras (ej: "¿cuál es el rendimiento del koraza?", "¿a qué temperatura se aplica epóxico?")
- Refuerzo del prompt anti-inventario en preguntas técnicas: el agente responde con información técnica de la ficha sin forzar cotización ni verificar stock

---

### 4. `24108e7` — Integrar catálogo Abracol (787 productos)
**Fecha:** 2026-04-10 12:30  
**Archivos:** `backend/main.py`, `backend/postgrest_views.sql`, `backend/import_abracol_catalog.py`

**Cambios implementados:**

#### Base de datos
- Nueva tabla `abracol_productos` con campos: codigo, nombre_comercial, descripcion, grano, medida, familia, empaque, portafolio, descripcion_larga
- `mv_productos` ahora hace **LEFT JOIN** con `abracol_productos` sobre `ab.codigo = inv.referencia`
- `search_blob` enriquecido con: nombre_comercial, familia, descripcion_larga, portafolio, grano, medida
- `search_compact` enriquecido con: nombre_comercial, familia
- 4 nuevas columnas expuestas: `nombre_comercial_abracol`, `familia_abracol`, `descripcion_larga_abracol`, `portafolio_abracol`

#### Backend (main.py)
- **PORTFOLIO_ALIASES** +18 entradas: yale, tekbond, induma, norton, carborundum, phillips, inafer, delta, candado, cerrojo, manija, antipanico, fibrodisco, disco corte, disco desbaste, beartex, cinta enmascarar, espuma poliuretano
- **PORTFOLIO_CATEGORY_MAP** +35 entradas: cerraduras, candados, bisagras, herrajes, adhesivos, cintas, abrasivos detallados, aerosoles, herramientas de pintura
- Bloque `info_catalogo_complementario` en formateo de producto: muestra nombre comercial, familia, descripción y portafolio de Abracol
- SELECT queries actualizados en `fetch_smart_product_rows` y `fetch_products_from_catalog`
- Nuevo endpoint admin: `POST /admin/importar-catalogo-abracol`

#### Datos importados
- **783 productos** importados del Excel Abracol desde Dropbox
- **778 enriquecidos** en mv_productos (5 sin match de referencia)
- **19,694 productos totales** en vista materializada
- **15 portafolios**: ABRACOL(177), YALE(141), INDUMA(90), SEGUREX(77), GOYA(66), TEKBOND(56), PHILLIPS(45), NORTON(36), ARTECOLA(31), CARBORUNDUM(18), DELTA(18), INAFER(16), ATLAS(8), MASTDER(4), OTROS(4)

#### Verificación de búsqueda
Queries probados post-integración (todos retornando datos enriquecidos):
- ✅ "cerradura yale" → productos con familia/portafolio Abracol
- ✅ "lija agua 150" → grano y medida de Abracol
- ✅ "brocha profesional" → datos GOYA enriquecidos
- ✅ "candado" → familia cerraduras/candados
- ✅ "bisagra" → herrajes con descripción larga
- ✅ "aerosol alta temperatura" → portafolio correcto

---

## 🧪 Resultados de Tests

### Test 1: Filtros Semánticos — 22/22 PASS ✅

Ejecutado después del commit `ad50e6a`. Valida que los filtros POST-RAG y PRE-RAG funcionan correctamente.

**Resultado: 100% PASS** — todos los filtros semánticos operan como se diseñó.

---

### Test 2: Re-run categorías problemáticas (502/503) — 16P / 1W / 0F ✅

5 categorías re-ejecutadas que antes tenían fallos:

| Categoría | PASS | WARN | FAIL |
|-----------|------|------|------|
| flujo_completo | 3 | 0 | 0 |
| gap_portfolio | 3 | 0 | 0 |
| matematica_fracciones | 3 | 0 | 0 |
| memoria_largo_plazo | 3 | 1 | 0 |
| precio_negociacion | 4 | 0 | 0 |

**1 WARN:** secado Pintucoat saltó a cotización prematuramente.

---

### Test 3: Regresión Agente Completo — 88P / 7W / 5F (100 turnos)

Ejecutado después del commit `4c07fee` (GUARDIA PREGUNTA-TÉCNICA).

#### 5 FAILs detectados:

| # | Categoría | Descripción |
|---|-----------|-------------|
| 1 | `flujo_completo` | Techo eternit — agente no identificó correctamente el sustrato |
| 2 | `gap_portfolio` | Epóxica alimentaria — producto fuera del portafolio, agente no declaró gap |
| 3 | `matematica_fracciones` | Redondeo de galones — cálculo incorrecto en fracción |
| 4 | `memoria_largo_plazo` | Amnesia — agente olvidó dato previo de la conversación |
| 5 | `memoria_largo_plazo` | Amnesia — segundo caso de pérdida de contexto multi-turno |

#### 7 WARNs:
Mayormente respuestas correctas pero con verbosidad excesiva o formato subóptimo.

---

### Test 4: Regresión RAG — 71P / 9W / 14F (94 tests)

#### Detalle test por test:

| Test | Categoría | Estado | Query |
|------|-----------|--------|-------|
| 01-07 | humedad | ✅ PASS | (7 queries de humedad/salitre/filtración) |
| **08** | **humedad** | **❌ FAIL** | "la pintura se sopla y sale agua detrás" |
| 09-13 | fachada | ✅ PASS | (5 queries de fachada) |
| **14** | **fachada** | **❌ FAIL** | "muro medianero exterior que comparto con el vecino" |
| 15-19 | techo | ✅ PASS | (5 queries de techo) |
| 20-23 | metal | ✅ PASS | (4 queries de metal) |
| **24** | **metal** | **❌ FAIL** | "tanque metálico industrial expuesto a químicos" |
| 25 | metal | ⚠️ WARN | |
| 26-31 | piso | ✅ PASS | (6 queries) |
| 32-36 | interior | ✅ PASS | (5 queries) |
| 37, 40 | madera | ✅ PASS | |
| 38-39 | madera | ⚠️ WARN | |
| 41-45 | abrasivo | ✅ PASS | (5 queries) |
| 46-49 | especial | ✅ PASS | (4 queries) |
| 52 | bicomponente | ⚠️ WARN | |
| 53 | bicomponente | ✅ PASS | |
| **54** | **bicomponente** | **❌ FAIL** | "imprimante epóxico para metal industrial" |
| 55 | bicomponente | ⚠️ WARN | |
| 56-64 | tecnico | ✅ PASS | (9 queries) |
| **65** | **tecnico** | **❌ FAIL** | "temperatura mínima de aplicación para epóxicos" |
| 66-72, 76-77 | jerga | ✅ PASS | (9 queries) |
| **73** | **jerga** | **❌ FAIL** | "la bodega huele a guardado y las paredes tienen manchas negras" |
| **74** | **jerga** | **❌ FAIL** | "la pintura se puso como amarillenta y polvosa" |
| 75 | jerga | ⚠️ WARN | |
| **78-81** | **filtro_barnex** | **❌ FAIL (4)** | barniz/madera interior queries (ESPERADO — filtro post-RAG corrige) |
| 82-83 | filtro_barnex | ✅ PASS | |
| 84-85, 87 | filtro_fachada | ✅ PASS | |
| **86** | **filtro_fachada** | **❌ FAIL** | "frente de la casa se pela la pintura con el agua" |
| **88** | **filtro_piso** | **❌ FAIL** | "piso bodega con montacargas pesados" |
| 89 | filtro_piso | ⚠️ WARN | |
| **90** | **filtro_piso** | **❌ FAIL** | "piso garaje residencial carros livianos" |
| 91 | filtro_piso | ✅ PASS | |
| 92-94 | filtro_pintulac/plastico/industrial | ✅ PASS | |

#### Clasificación de los 14 FAILs:

**7 FAILs ESPERADOS (filtros POST-RAG):**
- Tests 78-81 (filtro_barnex): RAG devuelve barnex pero el agente corrige a esmalte/pintulux
- Tests 86 (filtro_fachada), 88, 90 (filtro_piso): RAG devuelve candidato incorrecto, agente corrige

> Estos fallan a nivel RAG puro pero el agente los maneja correctamente gracias a los filtros semánticos implementados en commit `f9e3198`.

**7 FAILs PRE-EXISTENTES:**
- Test 08 (humedad): "la pintura se sopla y sale agua detrás" — ambigüedad pintura vs humedad
- Test 14 (fachada): muro medianero — query ambiguo
- Test 24 (metal): tanque químico industrial — falta International en índice
- Test 54 (bicomponente): imprimante epóxico — indexación pobre de International
- Test 65 (tecnico): temperatura mínima epóxicos — dato técnico no indexado
- Test 73 (jerga): "huele a guardado, manchas negras" — no mapea a antihumedad
- Test 74 (jerga): "pintura amarillenta y polvosa" — no mapea a deterioro UV

---

### Test 5: Auditoría RAG 50 escenarios — 32P / 9W / 9F

#### 9 FAILs:

| Query | Problema |
|-------|----------|
| "sendero peatonal concreto parque" | No encuentra Pintura Canchas correctamente |
| "cicloruta asfalto exterior" | No encuentra Pintura Canchas, devuelve Pegante Tachas |
| "piso bodega con montacargas pesados" | Devuelve Pintura Canchas en vez de Intergard |
| "rampa vehicular edificio estacionamiento" | No encuentra Pintucoat |
| "puerta madera interior color blanco" | Devuelve Barnex en vez de Pintulux/Esmalte |
| "pared exterior descascarando lluvia" | Koraza aparece pero no en top ranking |
| "pintar mesa madera comedor interior" | Devuelve Barnex en vez de Pintulac/Esmalte |
| "pintar silla plástica jardín" | No encuentra Aerocolor |
| "pared planta procesadora alimentos" | No encuentra Pintucoat industrial |

#### 9 WARNs:

| Query | Problema |
|-------|----------|
| "tubería metálica industrial exterior" | Falta Intergard en top |
| "tanque metálico almacenamiento industrial" | Falta Intergard en top |
| "pintar habitación interior económico" | Falta Pinturama en resultados |
| "cielo raso bodega económico" | Falta Intervinil en resultados |
| "proteger piso concreto taller mecánico" | Falta Intergard, devuelve Pintucoat |
| "acabado poliuretano sobre epóxica" | Falta Interfine/Interthane |
| "ambiente marino salino estructura costera" | Falta Interseal |
| "pintura especial para piscina" | GAP: productos misleading |
| "pintura tanque agua potable inmersión" | GAP: productos misleading |

---

## 📊 Resumen por categoría RAG

| Categoría | PASS | WARN | FAIL |
|-----------|------|------|------|
| humedad | 7 | 0 | 1 |
| fachada | 5 | 0 | 1 |
| techo | 5 | 0 | 0 |
| metal | 4 | 1 | 1 |
| piso | 6 | 0 | 0 |
| interior | 5 | 0 | 0 |
| madera | 2 | 2 | 0 |
| abrasivo | 5 | 0 | 0 |
| especial | 4 | 0 | 0 |
| bicomponente | 1 | 2 | 1 |
| tecnico | 9 | 0 | 1 |
| jerga | 9 | 1 | 2 |
| filtro_barnex | 2 | 0 | 4 |
| filtro_fachada | 3 | 0 | 1 |
| filtro_piso | 1 | 1 | 2 |
| filtro_pintulac | 1 | 0 | 0 |
| filtro_plastico | 1 | 0 | 0 |
| filtro_industrial | 1 | 0 | 0 |

---

## 🔴 Problemas Conocidos y Pendientes

### Prioridad ALTA

1. **Indexación International/Intergard pobre** — Los productos de la línea International (Intergard, Interseal, Interfine, Interthane) no rankean bien en el RAG. Causante de múltiples FAILs en metal, bicomponente y auditoría industrial.
   
2. **Memoria largo plazo (amnesia)** — 2 FAILs donde el agente olvida datos mencionados turnos antes. Requiere revisión del manejo del historial de conversación.

3. **Cálculo de fracciones/galones** — Redondeo incorrecto en matematica_fracciones. Regla de negocio: siempre redondear al galón entero superior.

### Prioridad MEDIA

4. **Barnex vs Esmalte en madera interior** — A nivel RAG puro, Barnex sigue apareciendo como top para queries de "madera interior blanco". El filtro POST-RAG lo corrige, pero el RAG debería mejorarse.

5. **Ambigüedad jerga** — "huele a guardado + manchas negras" y "pintura amarillenta" no se conectan bien con productos de antihumedad/mantenimiento.

6. **Productos de piso industrial** — Intergard 2002 no aparece para "bodega montacargas", Pintucoat no para "rampa vehicular".

7. **Aerocolor para plásticos** — El RAG no encuentra Aerocolor para "pintar silla plástica", devuelve Primer Plásticos.

### Prioridad BAJA

8. **GAP products (piscina, tanque agua potable)** — Productos fuera del portafolio. El agente debería declarar gap limpiamente.

9. **Tests filtro_barnex marcan FAIL en RAG** — Son FAILs esperados. Considerar remover assertions de exclusión en tests de filtro o marcarlos como "expected_fail".

---

## ✅ Mejoras Implementadas (Resumen)

| Mejora | Impacto |
|--------|---------|
| Filtros semánticos POST-RAG | Corrige barnex→esmalte, elimina Pintulac, filtra productos irrelevantes |
| Query expansion PRE-RAG | Mejora recall en queries ambiguos con sinónimos y contexto |
| Guardia Barnex interior | Redirige madera blanco interior a pintulux/esmalte |
| PROBLEM_SIGNALS ampliados | Más queries activan flujo diagnóstico (menos no-RAG-call) |
| GUARDIA PREGUNTA-TÉCNICA | Impide cotización en preguntas puramente técnicas |
| Catálogo Abracol | 783 productos enriquecidos (yale, norton, induma, goya, etc.) |
| PORTFOLIO_ALIASES +18 | Reconoce marcas como yale, tekbond, norton, induma |
| PORTFOLIO_CATEGORY_MAP +35 | Mapea cerraduras, candados, bisagras, abrasivos, etc. |
| Endpoint admin Abracol | `POST /admin/importar-catalogo-abracol` para re-importar |

---

## 🚀 Siguientes Pasos Recomendados

### Inmediato
1. **Mejorar indexación International** — Agregar fichas técnicas de Intergard, Interseal, Interfine, Interthane al RAG con embeddings dedicados
2. **Fix memoria largo plazo** — Revisar cómo se pasa el historial al LLM, posible truncamiento o resumen demasiado agresivo
3. **Fix redondeo galones** — Regla explícita: `math.ceil()` siempre para cantidades de producto

### Corto plazo
4. **Agregar fichas técnicas Sika** al RAG (productos de construcción referenciados pero no indexados)
5. **Mejorar embeddings de jerga colombiana** — "huele a guardado", "se puso amarillenta" deberían conectarse con categorías de problema
6. **Refrescar mv_productos periódicamente** — Crear cron job o endpoint para `REFRESH MATERIALIZED VIEW`
7. **Convertir test filtro_barnex FAILs a expected_fail** — Evita noise en regresión RAG

### Mediano plazo
8. **Dashboard frontend para operaciones** — Monitor de importaciones, estado RAG, métricas de agente
9. **Re-run regresión completa post-fixes** — Cuando se implementen fixes 1-3
10. **Ampliar batería de tests** — Más escenarios de Abracol (yale, cerraduras, abrasivos)

---

> **Generado:** 2026-04-10 ~13:30 COT  
> **Último commit:** `24108e7` (main)  
> **Base de datos:** 19,694 productos en mv_productos, 778 Abracol-enriquecidos  
> **Deploy:** Coolify auto-deploy activo
