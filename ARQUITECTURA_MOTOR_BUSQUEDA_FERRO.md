# ARQUITECTURA DEL MOTOR DE BÚSQUEDA DE PRODUCTOS — FERRO (CRM Ferreinox)

> Documento técnico para el equipo de arquitectura IA.  
> Última actualización: 2026-04-09 | Commit: `e5ba148`

---

## 1. ESTADO ACTUAL DE HERRAMIENTAS (Function Calling)

### ✅ SÍ, FERRO tiene Function Calling implementado contra PostgreSQL en tiempo real.

El agente usa **OpenAI Function Calling** (`tool_choice="auto"`) dentro de `generate_agent_reply_v2()` (línea ~17435 de `backend/main.py`). El LLM puede invocar hasta **5 iteraciones** de tool calls por turno.

### Herramientas de inventario disponibles:

| Herramienta | Descripción | Parámetros |
|-------------|-------------|------------|
| `consultar_inventario` | Busca UN producto en PostgreSQL. Devuelve stock, precio, presentaciones. | `producto` (string, required): nombre, código o jerga comercial. Ej: `"8 galones viniltex blanco 1501"` |
| `consultar_inventario_lote` | Busca MÚLTIPLES productos (2-15) en UNA sola llamada. | `productos` (array of strings): lista de productos. Ej: `["8 galones viniltex 1501", "2 cuñetes koraza blanco"]` |

### Flujo completo cuando el LLM llama `consultar_inventario`:

```
LLM → tool_call("consultar_inventario", {"producto": "interseal blanco galon"})
  ↓
_handle_tool_consultar_inventario(args, conversation_context)
  ├── translate_customer_jargon("interseal blanco galon")    → Traduce jerga
  ├── extract_product_request(...)                           → Extrae: producto, color, presentación, cantidad
  ├── apply_deterministic_product_alias_rules(...)           → Aplica reglas de alias (P-11→Doméstico, T-11→Pintulux)
  ├── lookup_product_context(...)                            → MOTOR DE BÚSQUEDA (ver sección 3)
  ├── fetch_product_price(referencia)                        → Busca precio en agent_precios
  ├── fetch_product_companions(referencia)                   → Catalizadores y complementarios
  └── return JSON → LLM recibe: {encontrados, productos: [{codigo, descripcion, precio_unitario, precio_con_iva, stock, ...}]}
```

### Otras herramientas relevantes del agente:

| Herramienta | Uso |
|-------------|-----|
| `consultar_conocimiento_tecnico` | RAG semántico (pgvector) sobre fichas técnicas. Devuelve fragmentos + productos candidatos. |
| `buscar_documento_tecnico` | Envía el PDF completo de la ficha técnica al cliente vía WhatsApp. |
| `confirmar_pedido_y_generar_pdf` | Persiste el pedido y genera PDF con precios+IVA. |

---

## 2. ESTRUCTURA DE LA BASE DE DATOS (Tablas y Columnas Clave)

### 2.1 Vista materializada `mv_productos` — EL CATÁLOGO PRINCIPAL

> **19,708 productos** | Índices GIN trigram | Búsqueda ILIKE: ~0.6ms (vs 11,000ms en vista normal)

| Columna | Tipo | Descripción | Ejemplo |
|---------|------|-------------|---------|
| `producto_codigo` | text | Código primario ERP | `"5893596"` |
| `referencia` | text | Referencia/SKU del ERP | `"EGA130"` |
| `descripcion` | text | **Nombre comercial completo** | `"INTERSEAL 670HS LT GREY EGA130 GL"` |
| `marca` | text | Marca | `"INTERNATIONAL"` |
| `stock_total` | numeric | **Stock total** (suma de todas las tiendas) | `24` |
| `costo_promedio_und` | numeric | Costo promedio unitario | `185430.00` |
| `stock_por_tienda` | text | Desglose por tienda | `"Pereira: 12; Manizales: 8; Armenia: 4"` |
| `departamentos` | text | Lista de departamentos | `"PINTURAS, INDUSTRIAL"` |
| `linea_clasificacion` | text | Línea de producto | `"Recubrimientos Industriales"` |
| `marca_clasificacion` | text | Clasificación de marca | `"International"` |
| `familia_clasificacion` | text | **Familia del producto** | `"Interseal"` |
| `aplicacion_clasificacion` | text | Tipo de aplicación | `"Pisos industriales"` |
| `cat_producto` | text | Categoría | `"Epóxicos"` |
| `descripcion_ebs` | text | Descripción extendida ERP | — |
| `tipo_articulo` | text | Tipo de artículo | `"Producto terminado"` |
| `search_blob` | text | **Campo de búsqueda indexado** (concatenación normalizada de todos los campos anteriores) | — |
| `search_compact` | text | Campo alfanumérico compacto para búsqueda exacta | — |

#### ⚠️ HALLAZGO CRÍTICO — NO existe columna dedicada para "Base", "Blanco" o "Transparente"

La información de color/base está **EMBEBIDA dentro de `descripcion`**. El sistema la extrae dinámicamente con la función `infer_product_color_from_row()`:

```
"INTERSEAL 670HS LT GREY EGA130 GL"  → color inferido: "gris"
"KORAZA BLANCO 1501 GL"              → color inferido: "blanco"
"BARNEX TRANSPARENTE GL"             → color inferido: "transparente"
"INTERGARD 2002 ECA011 GL"           → color inferido: NINGUNO (no tiene color en descripción)
```

Lo mismo aplica para presentación:
```
"KORAZA BLANCO 1501 GL"     → presentación: "galon" (por "GL")
"KORAZA BLANCO 1501 CUÑ"    → presentación: "cuñete" (por "CUÑ")
"KORAZA BLANCO 1501 1/4"    → presentación: "cuarto" (por "1/4")
```

### 2.2 Tabla `agent_precios` — PRECIOS

> **21,665 filas** | 4,999 con PVP>0 | 2,780 con precio + inventario activo

| Columna | Tipo | Descripción |
|---------|------|-------------|
| `referencia` | text | **Clave de unión** con mv_productos.referencia |
| `descripcion` | text | Descripción del producto |
| `marca` | text | Marca |
| `pvp_sap` | numeric | **Precio de lista SAP** (Pintuco, MPY, International) |
| `pvp_franquicia` | numeric | **Precio franquicia** (Goya, Yale, Abracol, etc.) |
| `precio_mejor` | computed | `COALESCE(NULLIF(pvp_sap, 0), NULLIF(pvp_franquicia, 0))` — Toma SAP si existe, sino franquicia |

#### Lógica de precio en el handler:
```python
price_info = fetch_product_price(referencia)  # SELECT WHERE referencia = :ref AND (pvp_sap > 0 OR pvp_franquicia > 0)

if price_info and price_info["precio_mejor"]:
    item["precio_unitario"] = pvp                    # Precio base
    item["precio_con_iva"]  = round(pvp * 1.19)      # +19% IVA Colombia
```

### 2.3 Vista `vw_inventario_agente` — INVENTARIO POR TIENDA

Usada cuando el cliente pide stock de una tienda específica. Mismas columnas que `mv_productos` pero desglosada por almacén (`almacen_nombre`, `stock_disponible`).

### 2.4 Vista materializada `mv_product_rotation` — ROTACIÓN HISTÓRICA

| Columna | Descripción |
|---------|-------------|
| `producto_codigo` | Referencia del producto |
| `rotation_score` | Puntuación de velocidad de venta (0.0 a 1.0). Top: Lija 150 Agua Abracol = 0.79 |

### 2.5 Tabla `agent_product_companion` — COMPLEMENTARIOS

| Columna | Descripción |
|---------|-------------|
| `producto_referencia` | Producto principal (ej: `"Pintucoat"`) |
| `companion_referencia` | Complemento (ej: `"13227"` = catalizador) |
| `tipo_relacion` | `catalizador`, `diluyente`, `base`, `complemento`, `sellador`, `imprimante`, `acabado` |

---

## 3. EL MOTOR DE BÚSQUEDA — Cómo Python va a PostgreSQL

### NO es búsqueda semántica (pgvector). Es un motor HÍBRIDO de 5 estrategias en cascada.

> pgvector se usa SOLO para el RAG de fichas técnicas (`consultar_conocimiento_tecnico`).  
> La búsqueda de productos usa **trigram similarity (pg_trgm)** + **fonética española** + **scoring multi-dimensional**.

### Diagrama de prioridad (función `lookup_product_context`, línea ~13318):

```
PRIORIDAD 1 → Learned References (memoria de resoluciones pasadas, TTL 90 días)
    ↓ si no hay match
PRIORIDAD 2 → Exact Code Match (referencia exacta: "5893596" o "EGA130")
    ↓ si no hay match, intenta fuzzy codes (transposiciones de dígitos)
PRIORIDAD 3 → Catálogo Curado (agent_catalog_product — productos de alto valor manualmente curados)
    ↓ se mergea con
PRIORIDAD 4 → Smart Full-Catalog Search (pg_trgm + fonética sobre mv_productos — 19,708 productos)
    ↓ si < 3 buenos resultados
PRIORIDAD 5 → Legacy Term Search (ILIKE puro sobre vw_inventario_agente)
    ↓ si todo falla  
PRIORIDAD 6 → Sales History (búsqueda en vw_ventas_netas — productos vendidos recientemente)
```

### 3.1 Smart Search (Prioridad 4) — La búsqueda principal

Función: `fetch_smart_product_rows()` (línea ~5538)

**Tabla consultada:** `mv_productos` (vista materializada con índices GIN trigram)

**SQL generado dinámicamente:**
```sql
SELECT p.producto_codigo, p.referencia, p.descripcion, p.marca,
       p.stock_total, p.costo_promedio_und, p.stock_por_tienda,
       p.familia_clasificacion, p.marca_clasificacion, p.cat_producto,
       p.descripcion_ebs, p.tipo_articulo,
       (CASE WHEN search_blob ILIKE '%interseal%' THEN 1 ELSE 0 END
      + CASE WHEN search_blob ILIKE '%blanco%' THEN 1 ELSE 0 END
      + CASE WHEN search_blob ILIKE '%galon%' THEN 1 ELSE 0 END
      + CASE WHEN referencia = '5893596' THEN 50 ELSE 0 END  -- Bonus por código exacto
       ) AS match_score,
       COALESCE(rot.rotation_score, 0) AS rotation_score
FROM mv_productos p
LEFT JOIN mv_product_rotation rot ON rot.producto_codigo = p.producto_codigo
WHERE (search_blob ILIKE '%interseal%' OR search_blob ILIKE '%blanco%' OR search_blob ILIKE '%galon%')
ORDER BY match_score DESC, rotation_score DESC, stock_total DESC
LIMIT 30
```

**Expansiones automáticas del motor:**
- **Fonética española:** `spanish_phonetic_key()` convierte: `rodillo→rodiyo`, `brocha→brosha`, `barniz→barnis`
- **Variantes de término:** `_SEARCH_TERM_VARIANTS` (19 entradas bidireccionales): `profesional↔prof`, `barniz↔barn`, etc.
- **Código numérico exacto:** Si el término es `\d{4,}`, se busca directamente en `referencia = :term` con bonus +50 puntos

### 3.2 Sistema de Ranking (16 dimensiones)

Función: `rank_product_match_rows()` (línea ~13132)

Después de que PostgreSQL devuelve los candidatos, Python los re-rankea con **16 scores**:

| Score | Peso/Rango | Qué mide |
|-------|-----------|----------|
| `kit_promo_penalty` | -10 | Penaliza KITs, promos, "PAGUE 2 LLEVE 3" |
| `exact_code_score` | 10 o 1 | Match exacto de referencia vs substring |
| `specific_score` | 0-N | Cuántos términos específicos del producto coinciden |
| `match_score` | 0-N | Score del SQL (cuántos ILIKEs matchearon) |
| `smart_score` | -1.5 a 1.0 | Score unificado: rotación(0.4) + texto(0.3) + stock(0.2) - penalizaciones |
| `rotation_score` | 0.0-1.0 | Velocidad de venta histórica |
| `presentation_score` | 0 o 1 | ¿La presentación coincide? (galón, cuarto, cuñete) |
| `color_score` | 0 o 1 | ¿El color coincide? (blanco, gris, transparente) |
| `finish_score` | 0 o 1 | ¿El acabado coincide? (mate, brillante, satinado) |
| `brand_score` | 0 o 1 | ¿La marca coincide? |
| `family_score` | 0 o 1 | ¿La familia de producto coincide? |
| `size_score` | 0 o 1 | ¿El tamaño coincide? (para herramientas: 1/2", 3") |
| `direction_score` | 0 o 1 | ¿La dirección coincide? (horizontal, vertical) |
| `fuzzy_score` | 0.0-1.0 | Similitud de secuencia (SequenceMatcher) |
| `base_exact_score` | 0 o 1 | Match exacto de base |
| stock_total | numérico | Desempate final: más stock gana |

**Post-filtrado:**
1. Si hay match de código exacto → solo mantiene esos
2. Si `specific_score >= 2` en el top → filtra resto
3. Si pidió presentación (galón) → filtra a solo galones
4. Si pidió color (blanco) → filtra a solo blancos

### 3.3 ¿Cómo detecta "Blanco", "Base", "Transparente"?

La función `infer_product_color_from_row()` (línea ~7130) **parsea la descripción del ERP** con regex:

```python
# Colores compuestos (prioridad alta)
"verde bronce", "blanco puro", "rojo fiesta", "verde esmeralda"

# Colores simples (word boundary match)
"blanco", "negro", "gris", "rojo", "verde", "azul", "amarillo", 
"naranja", "marfil", "crema", "bronce", "transparente"
```

Y `row_matches_requested_colors()` cruza el color del request con el color inferido para filtrar.

---

## 4. DIAGNÓSTICO: ¿POR QUÉ "NO TENGO EL PRECIO"?

### El flujo donde se pierde el precio:

```
1. LLM llama consultar_conocimiento_tecnico("piso industrial montacargas")
   → RAG devuelve: "Intergard 2002 + cuarzo" + productos_inventario_relacionados
   → PERO estos son CANDIDATOS TÉCNICOS, no tienen precio ni stock confirmado

2. El LLM DEBERÍA llamar consultar_inventario("intergard 2002 galon")
   → Buscaría en mv_productos → encontraría la referencia ECA011
   → fetch_product_price("ECA011") → buscaría en agent_precios

3. ❌ PROBLEMA: El LLM a veces NO llama consultar_inventario después del RAG.
   Se queda con los "candidatos técnicos" del RAG (que NO traen precio)
   y responde directamente → "no tengo el precio"
```

### Las 3 razones raíz del problema:

| # | Causa | Ubicación | Estado |
|---|-------|-----------|--------|
| 1 | **El LLM no encadena RAG → Inventario automáticamente.** Recibe candidatos del RAG pero no busca cada uno en inventario. | System prompt | ⚠️ El prompt dice "OBLIGATORIO: llama consultar_inventario para confirmar disponibilidad", pero el LLM a veces lo ignora en proyectos complejos con muchos productos. |
| 2 | **El RAG devuelve nombres genéricos, no terms buscables.** Ej: devuelve `"Interseal 670HS"` pero el inventario tiene `"INTERSEAL 670HS LT GREY EGA130 GL"`. La búsqueda fuzzy lo encuentra, pero solo si el LLM la ejecuta. | `_handle_tool_consultar_conocimiento_tecnico` | El campo `productos_inventario_relacionados` ya intenta resolver esto, pero el LLM no siempre usa esos candidatos para buscar precio. |
| 3 | **Productos sobre pedido NO están en `agent_precios`.** Intergard 2002 puede no tener fila en la tabla de precios → `fetch_product_price()` devuelve `None` → el handler pone `precio_nota: "Precio pendiente de confirmación"` → el LLM interpreta como "no hay precio". | `agent_precios` table + handler | El prompt ahora dice que escale al Asesor Técnico Comercial en vez de rendirse (commit e5ba148), pero el problema de fondo persiste. |

### Posibles soluciones de arquitectura:

| Estrategia | Complejidad | Impacto |
|------------|-------------|---------|
| **A) Auto-lookup en el handler RAG:** Que `_handle_tool_consultar_conocimiento_tecnico` llame internamente a `fetch_product_price()` para cada candidato y devuelva el precio al LLM junto con los datos técnicos. | Media | Alto — elimina la dependencia de que el LLM encadene dos herramientas. |
| **B) Default base rule en el prompt:** Enseñar al LLM que siempre busque la variante "Blanco" o "Base Light" como default cuando recomiende un producto sin color específico. | Baja | Medio — funciona para la mayoría de pinturas, no para industriales especializados. |
| **C) Tabla de precios de sistema:** Crear una tabla `agent_system_prices` con precios por SISTEMA (no por producto individual), curada manualmente. Ej: "Sistema Intergard 2002 + Cuarzo = $X/m²". | Alta | Alto — eliminería el problema para los top 20 sistemas más consultados. |
| **D) Enrichment automático de candidatos RAG:** Que `lookup_inventory_candidates_from_terms()` (ya existe, línea ~16890) también busque precio y lo inyecte en `productos_inventario_relacionados`. | Baja-Media | Alto — ya existe la infraestructura, solo falta agregar el paso de precio. |

---

## 5. TABLAS Y VISTAS — RESUMEN COMPLETO

```
┌─────────────────────────────────┐
│        CATÁLOGO PRODUCTOS       │
├─────────────────────────────────┤
│ mv_productos (matview, 19,708)  │ ← Búsqueda principal (ILIKE + pg_trgm)
│ vw_inventario_agente (view)     │ ← Stock por tienda
│ agent_catalog_product (table)   │ ← Catálogo curado manual (~1,700)
│ agent_catalog_alias (table)     │ ← Alias comerciales (P-11→Doméstico)
│ mv_product_rotation (matview)   │ ← Scores de rotación por ventas
│ agent_product_learning (table)  │ ← Memoria de resoluciones pasadas
│ agent_product_companion (table) │ ← Catalizadores y complementarios
├─────────────────────────────────┤
│           PRECIOS               │
├─────────────────────────────────┤
│ agent_precios (table, 21,665)   │ ← pvp_sap + pvp_franquicia → precio_mejor
├─────────────────────────────────┤
│        RAG TÉCNICO              │
├─────────────────────────────────┤
│ agent_technical_doc_chunk       │ ← pgvector (142,936 chunks, 790 docs)
│ agent_expert_knowledge          │ ← Reglas de Pablo y Diego (~46 activas)
└─────────────────────────────────┘
```

---

## 6. CÓDIGO FUENTE — MAPA DE LÍNEAS

> Archivo: `backend/main.py` (~18,000+ líneas)

| Función | Línea aprox. | Descripción |
|---------|-------------|-------------|
| `AGENT_SYSTEM_PROMPT_V2` | 13760-14108 | System prompt completo del agente |
| `AGENT_TOOLS` | 14112-14650 | Definición de function calling |
| `_handle_tool_consultar_inventario` | 14687-14820 | Handler de búsqueda individual |
| `_handle_tool_consultar_inventario_lote` | 14858-14950 | Handler de búsqueda batch |
| `lookup_product_context` | 13318-13420 | Orquestador maestro (5 estrategias) |
| `fetch_smart_product_rows` | 5538-5710 | Búsqueda fuzzy pg_trgm sobre mv_productos |
| `fetch_code_product_rows` | 12777-12830 | Búsqueda por código exacto |
| `fetch_term_product_rows` | 12833-12900 | Búsqueda legacy por términos |
| `fetch_curated_catalog_product_rows` | 12937-13050 | Catálogo curado |
| `rank_product_match_rows` | 13132-13260 | Ranking 16 dimensiones |
| `smart_score_product` | 5434-5540 | Score unificado (rotación+texto+stock) |
| `fetch_product_price` | 6627-6661 | Lookup de precios en agent_precios |
| `fetch_product_companions` | 6693-6725 | Complementarios (catalizadores) |
| `infer_product_color_from_row` | 7130-7154 | Inferencia de color desde descripción |
| `infer_product_presentation_from_row` | 7066-7080 | Inferencia de presentación |
| `_handle_tool_consultar_conocimiento_tecnico` | 16785-17313 | Handler RAG técnico |
| `generate_agent_reply_v2` | 17370-17860+ | Función principal del agente |

---

*Documento generado para diseño de estrategia con arquitecto IA. No modificar sin contexto de los commits e2bd178 → e5ba148.*
