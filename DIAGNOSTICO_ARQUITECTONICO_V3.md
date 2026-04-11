# Diagnóstico Arquitectónico — FERRO Agent V3

> Generado: 2026-04-11 | Archivos analizados: `agent_context.py`, `agent_v3.py`, `agent_prompt_v3.py`, `main.py`, `agent_schema.sql`

---

## 1. Estructura del RAG Actual

### 1.1 Generación y almacenamiento de embeddings

**Modelo de embeddings:** `text-embedding-3-small` (OpenAI), 1536 dimensiones.

**Ingesta** (`backend/ingest_technical_sheets.py`):
- Fuente: PDFs de fichas técnicas descargados desde Dropbox (`/data/FICHAS TÉCNICAS Y HOJAS DE SEGURIDAD/`).
- Extracción: PyMuPDF → texto plano → chunking (~2000 chars max, 300 chars overlap).
- Cada chunk se embebe con `text-embedding-3-small` y se inserta en PostgreSQL/pgvector.
- Modos: `--full` (re-ingesta completa), incremental (solo PDFs nuevos), `--dry-run`.
- **Volumen actual:** 790 documentos, 675 familias únicas, ~142,936 chunks.

**Generación del embedding de consulta** (`main.py:7009`):
```python
def _generate_query_embedding(query_text: str) -> list[float] | None:
    client = get_openai_client()
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=query_text.strip(),
        dimensions=1536,
    )
    return response.data[0].embedding
```

### 1.2 Esquema de la base de datos vectorial

**Tabla:** `public.agent_technical_doc_chunk`

```sql
CREATE TABLE IF NOT EXISTS public.agent_technical_doc_chunk (
    id              bigserial PRIMARY KEY,
    doc_filename    text NOT NULL,           -- Nombre del PDF origen
    doc_path_lower  text NOT NULL,           -- Path normalizado (lowercase)
    chunk_index     integer NOT NULL DEFAULT 0,
    chunk_text      text NOT NULL,           -- Texto del fragmento (~2000 chars)
    marca           text,                    -- 'Pintuco', 'International', etc.
    familia_producto text,                   -- Familia del producto
    tipo_documento  varchar(30) NOT NULL DEFAULT 'ficha_tecnica',  -- ficha_tecnica | hoja_seguridad
    metadata        jsonb NOT NULL DEFAULT '{}'::jsonb,
    embedding       vector(1536) NOT NULL,   -- pgvector
    token_count     integer,
    ingested_at     timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_agent_doc_chunk UNIQUE (doc_path_lower, chunk_index)
);
```

**Índices:**
- `idx_agent_doc_chunk_filename` — B-tree en `doc_filename`
- `idx_agent_doc_chunk_marca` — B-tree en `marca`
- `idx_agent_doc_chunk_familia` — B-tree en `familia_producto`
- `idx_agent_doc_chunk_tipo` — B-tree en `tipo_documento`
- `idx_agent_doc_chunk_embedding` — **HNSW** en `embedding vector_cosine_ops` (`m=16, ef_construction=64`)

**Metadatos almacenados:** `marca`, `familia_producto`, `tipo_documento` como columnas explícitas + `metadata` JSONB libre. No se almacenan rendimientos, precios ni datos estructurados adicionales a nivel de chunk — son texto libre.

### 1.3 Búsqueda semántica (`search_technical_chunks`)

```python
def search_technical_chunks(query, top_k=5, marca_filter=None):
    embedding = _generate_query_embedding(query)
    # Cosine similarity: 1 - (embedding <=> query_vector)
    cur.execute(f"""
        SELECT doc_filename, doc_path_lower, chunk_index, chunk_text,
               marca, familia_producto, tipo_documento,
               1 - (embedding <=> %s::vector) AS similarity
        FROM public.agent_technical_doc_chunk
        WHERE 1=1 {marca_clause}
        ORDER BY embedding <=> %s::vector
        LIMIT %s
    """, params)
```

**Flujo de expansión portfolio-aware (segunda pasada):**
Si `best_similarity < 0.70` y no hay `producto` específico → expande con `PORTFOLIO_CATEGORY_MAP` y hace búsquedas RAG adicionales por los top-3 productos del portafolio. Chunks se fusionan y deduplicam.

### 1.4 Formato exacto de contexto entregado al LLM

**Función `build_rag_context`** (`main.py:7063`):

```python
def build_rag_context(chunks, max_chunks=4):
    # Filtra FDS/HDS (hojas de seguridad) — sin valor para recomendación
    # Threshold: similarity >= 0.25
    # Formato por chunk:
    #   [Fuente: {filename}]
    #   {chunk_text}
    # Separador entre chunks: "\n\n---\n\n"
    return "\n\n---\n\n".join(parts)
```

**Ejemplo de salida (lo que recibe el LLM en `respuesta_rag`):**

```
[Fuente: FT_KORAZA_FACHADAS.pdf]
Rendimiento: 12-16 m²/galón en superficies lisas. Preparación: limpiar con agua y
detergente, dejar secar 24h. Aplicar con rodillo de felpa de 3/8". Tiempo entre manos:
4 horas mínimo. Diluyente: agua (máximo 10%).

---

[Fuente: FT_KORAZA_FACHADAS.pdf]
Compatibilidad: sistema acrílico. Compatible con selladores acrílicos Pintuco.
No aplicar sobre superficies con pintura alquídica sin preparar. Temperatura de
aplicación: 10-35°C. Humedad relativa máxima: 85%.
```

**Payload JSON completo que recibe el LLM como resultado del tool call:**
```json
{
  "encontrado": true,
  "respuesta_rag": "[Fuente: FT_KORAZA_FACHADAS.pdf]\n{chunk1}\n\n---\n\n[Fuente: FT_KORAZA...]\n{chunk2}",
  "archivos_fuente": ["FT_KORAZA_FACHADAS.pdf"],
  "mejor_similitud": 0.8234,
  "mensaje": "⚡ INSTRUCCIÓN DE SÍNTESIS RAG (OBLIGATORIA): Los fragmentos en 'respuesta_rag' son DATOS CRUDOS...",
  "productos_inventario_relacionados": [ /* productos extraídos del RAG y cruzados con inventario */ ],
  "instruccion_industrial": "...",          // Solo si marca_filter == "international"
  "instruccion_bicomponente": "...",         // Solo si producto bicomponente detectado
  "conocimiento_comercial_ferreinox": [...]  // Expert knowledge inyectado (ver sección 2)
}
```

El campo `mensaje` contiene **8 instrucciones de síntesis obligatorias** que fuerzan al LLM a sintetizar (no copiar) el RAG, hacer cálculos con rendimiento mínimo, y escalar al Asesor Técnico Comercial si no hay precio.

---

## 2. Manejo del Comando "ENSEÑAR:" (Reglas de Negocio)

### 2.1 Almacenamiento

**Tabla:** `public.agent_expert_knowledge`

```sql
-- Inferida del código, no hay DDL separado visible en agent_schema.sql principal
-- (se crea con ensure_expert_knowledge_table() en runtime)
CREATE TABLE public.agent_expert_knowledge (
    id              serial PRIMARY KEY,
    cedula_experto  text NOT NULL,
    nombre_experto  text,
    contexto_tags   text,              -- "tanque agua potable", "piso industrial"
    producto_recomendado text,          -- "Epoxipoliamida"
    producto_desestimado text,          -- "Pintucoat"
    nota_comercial  text NOT NULL,      -- Lección técnica/comercial
    tipo            text,               -- 'recomendar' | 'evitar' | 'proceso' | 'sustitución'
    activo          boolean DEFAULT true,
    conversation_id integer,
    created_at      timestamptz DEFAULT now()
);
```

**Volumen actual:** 46 registros activos (11 desactivados: 3 duplicados, 3 contradichos, 5 redundantes). Pablo Mafla: 7 activos, Diego García: 39 activos.

**Expertos autorizados (hardcoded):**
```python
_AUTHORIZED_EXPERTS = {
    "1053774777": "PABLO CESAR MAFLA BANOL",
    "1088266407": "DIEGO MAURICIO GARCIA RENGIFO"
}
```

### 2.2 Flujo de escritura (ENSEÑAR → DB)

```
WhatsApp (Pablo/Diego) → "ENSEÑAR: para tanques de agua potable usar Epoxipoliamida, NO Pintucoat"
         ↓
agent_v3.py detect: _detect_ensenar(user_message) → True
         ↓
LLM recibe en system prompt: "⚠️ SÍ — ESTÁS HABLANDO CON EL EXPERTO AUTORIZADO {nombre}"
         ↓
LLM llama tool: registrar_conocimiento_experto({
    contexto_tags: "tanque agua potable",
    producto_recomendado: "Epoxipoliamida",
    producto_desestimado: "Pintucoat",
    nota_comercial: "Para tanques de agua potable...",
    tipo: "evitar"
})
         ↓
_handle_tool_registrar_conocimiento_experto():
  1. Valida cédula ∈ _AUTHORIZED_EXPERTS
  2. INSERT INTO agent_expert_knowledge
  3. invalidate_expert_knowledge_cache()  ← fuerza refresh
  4. Retorna {"guardado": true, "id": 47}
```

### 2.3 Flujo de lectura (inyección en consultas)

El conocimiento experto se inyecta en **DOS puntos**:

**Punto A — Tool `consultar_conocimiento_tecnico`** (`main.py:16390`):
```
LLM pide RAG → _handle_tool_consultar_conocimiento_tecnico →
  search_technical_chunks() → chunks RAG
  + fetch_expert_knowledge(pregunta + producto) → notas experto
  → resultado JSON incluye "conocimiento_comercial_ferreinox": [...]
```

**Punto B — Tool `consultar_inventario`** (`main.py:13927`):
```
LLM pide inventario → _handle_tool_consultar_inventario →
  lookup_product_context() → productos
  + fetch_expert_knowledge(producto + descripciones) → notas experto
  → resultado JSON incluye "conocimiento_experto_producto": [...]
```

**Función `fetch_expert_knowledge`** (`main.py:6788`):
```python
def fetch_expert_knowledge(query, limit=8):
    normalized = normalize_text_value(query)
    terms = [t for t in normalized.split() if len(t) >= 2][:10]
    all_rows = _get_expert_knowledge_cache()  # TTL 120s in-memory
    # Score: suma de cuántos terms aparecen en (contexto_tags + nota_comercial + productos)
    scored = [(sum(1 for t in terms if t in searchable), row) for row in all_rows]
    return [r for _, r in sorted(scored)[:limit]]
```

**Formato inyectado al LLM:**
```json
{
  "conocimiento_comercial_ferreinox": [
    {
      "tipo": "evitar",
      "contexto": "tanque agua potable",
      "recomendar": "Epoxipoliamida",
      "evitar": "Pintucoat",
      "nota": "Para tanques de agua potable usar Epoxipoliamida, NO Pintucoat"
    }
  ]
}
```

El system prompt instruye: *"Si `conocimiento_comercial_ferreinox` está presente → PREVALECE SOBRE TODO."*

---

## 3. Arquitectura del Tool Calling (Precios e Inventario)

### 3.1 JSON Schema de las herramientas

El LLM recibe **15 herramientas** definidas en `AGENT_TOOLS_V3` (`agent_prompt_v3.py`). Las 3 principales para inventario/precios:

#### `consultar_inventario` (producto unitario)
```json
{
  "type": "function",
  "function": {
    "name": "consultar_inventario",
    "description": "Busca disponibilidad y precios de UN producto en el inventario de Ferreinox. OBLIGATORIO llamar ANTES de mencionar cualquier precio o disponibilidad al cliente...",
    "parameters": {
      "type": "object",
      "properties": {
        "producto": {
          "type": "string",
          "description": "Nombre, descripción o código del producto. Incluye cantidad y presentación si el cliente las especificó. Ej: '8 galones viniltex blanco 1501'..."
        }
      },
      "required": ["producto"]
    }
  }
}
```

#### `consultar_inventario_lote` (batch, hasta 15 productos)
```json
{
  "type": "function",
  "function": {
    "name": "consultar_inventario_lote",
    "description": "Busca disponibilidad y precios de MÚLTIPLES productos en una sola llamada (hasta 15)...",
    "parameters": {
      "type": "object",
      "properties": {
        "productos": {
          "type": "array",
          "items": { "type": "string" },
          "description": "Lista de productos a buscar. Máximo 15."
        }
      },
      "required": ["productos"]
    }
  }
}
```

#### `consultar_conocimiento_tecnico` (RAG fichas técnicas)
```json
{
  "type": "function",
  "function": {
    "name": "consultar_conocimiento_tecnico",
    "description": "Busca información técnica en las fichas técnicas vectorizadas (RAG) y conocimiento experto Ferreinox. OBLIGATORIO llamar ANTES de recomendar cualquier producto o sistema de aplicación...",
    "parameters": {
      "type": "object",
      "properties": {
        "pregunta": { "type": "string", "description": "La pregunta técnica formulada con TÉRMINOS TÉCNICOS..." },
        "producto": { "type": "string", "description": "Nombre del producto. Ej: 'Viniltex', 'Koraza', 'Interseal 670'." },
        "marca":    { "type": "string", "description": "Filtro de marca: 'Pintuco', 'International'." }
      },
      "required": ["pregunta"]
    }
  }
}
```

### 3.2 Motor de búsqueda de productos (`lookup_product_context`)

**Pipeline de match** (cascada de 5 estrategias):

```
LLM: tool_call("consultar_inventario", {"producto": "8 galones viniltex blanco 1501"})
                           ↓
1. translate_customer_jargon(producto)     → normaliza jerga coloquial
2. extract_product_request(producto)       → extrae: core_terms, search_terms, product_codes, brand_filters, store_filters
3. apply_deterministic_product_alias_rules → mapea aliases conocidos
4. build_followup_inventory_request        → hereda contexto de producto previo si es follow-up
                           ↓
5. lookup_product_context(producto, request) — cascada:
   ├─ a) fetch_learned_product_references()    → agent_product_learning (aprendizaje previo)
   ├─ b) fetch_code_product_rows()             → búsqueda exacta por código en mv_productos
   ├─ c) fetch_curated_catalog_product_rows()  → agent_catalog_product (catálogo curado, ~1.7K rows)
   ├─ d) fetch_smart_product_rows()            → pg_trgm + fonética española + rotación ventas
   └─ e) fetch_term_product_rows()             → legacy ILIKE multi-term fallback
                           ↓
6. rank_product_match_rows() — scoring unificado:
   sort_key = (kit_promo_penalty, exact_code_score, specific_score, smart_score, rotation_score, match_score, stock)
                           ↓
7. Enriquecimiento por producto:
   ├─ fetch_product_price(referencia)           → agent_precios (pvp_sap / pvp_franquicia)
   ├─ fetch_product_companions(referencia)      → agent_product_companion (catalizadores, diluyentes)
   ├─ BICOMPONENT_CATALOG injection             → si bicomponente y no tiene catalizador
   ├─ _INTERNATIONAL_PRODUCTS_BY_CODE           → precios International IVA incluido
   └─ fetch_expert_knowledge()                  → notas de Pablo/Diego
                           ↓
8. Respuesta JSON al LLM
```

**Base de datos usada para inventario:**
- `mv_productos` — materialized view (~19,708 rows) con GIN trigram indexes. Búsqueda: ILIKE 0.6ms vs 11s en VIEW.
- `agent_precios` — 21,665 rows (4,999 con PVP > 0). Lookup por referencia exacta.
- `agent_catalog_product` — catálogo curado (~1,700 rows).
- `agent_product_learning` — aprendizaje de resoluciones previas.
- `agent_product_companion` — relaciones complementarias (catalizador, diluyente...).
- `mv_product_rotation` — ventas históricas para scoring de rotación.

### 3.3 Lógica de precios

```python
def fetch_product_price(referencia):
    # Busca en agent_precios:
    # COALESCE(NULLIF(pvp_sap, 0), NULLIF(pvp_franquicia, 0)) AS precio_mejor
    # pvp_sap → marcas Pintuco/MPY (impuestos EXCLUIDOS → +19% IVA)
    # pvp_franquicia → marcas complementarias (Goya, Yale, Abracol)
```

**Cascada de precio por producto:**
1. `fetch_product_price(referencia)` → agent_precios con pvp_sap/pvp_franquicia
2. Fallback International: `_INTERNATIONAL_PRODUCTS_BY_CODE[ref]` → JSON hardcoded con precios IVA incluido
3. Si nada: `precio_unitario = None`, `precio_nota = "Precio pendiente de confirmación"`

**Reglas IVA (inyectadas en tool response):**
- Pintuco: `"Este precio es ANTES DE IVA. Subtotal × cantidad + IVA 19% = Total a Pagar"`
- International: `"Precio International IVA INCLUIDO. NO sumes IVA de nuevo."` + `precio_iva_incluido: true`

**Guardia IVA (post-LLM en `agent_v3.py`):** Si la respuesta tiene `$` + keywords de cotización pero NO tiene "iva 19%" → fuerza re-generación con desglose Subtotal/IVA/Total.

---

## 4. Inyección de Contexto (`agent_context.py`)

### 4.1 Arquitectura del Turn Context Builder

El módulo reemplaza ~900 líneas de reglas estáticas del prompt V2 con **~15 líneas dinámicas** inyectadas POR TURNO. Python analiza la conversación ANTES de llamar al LLM y le dice exactamente qué hacer.

**Flujo:**
```
user_message llega
         ↓
classify_intent(message, context, history, auth)  → 1 de 12 intents
extract_diagnostic_data(message, history)          → {surface, condition, interior_exterior, area_m2, traffic}
detect_topic_change(message, history)              → bool
has_active_quotation(history)                      → bool
         ↓
build_turn_context() genera bloque de texto → se inyecta en {contexto_turno} del system prompt
```

### 4.2 Clasificación de intención (Python-side, no LLM)

**12 intents posibles:**
| Intent | Detección |
|--------|-----------|
| `saludo` | Regex: `hola`, `buenas tardes`, `hey`, etc. |
| `despedida` | Regex: `gracias`, `chao`, `adiós`, etc. |
| `reclamo` | Keywords: `reclamo`, `garantía`, `defecto`, etc. |
| `bi_interno` | Keywords + `internal_auth`: `ventas`, `facturación`, etc. |
| `documento` | Keywords: `ficha técnica`, `hoja de seguridad`, `fds` |
| `identidad` | Regex: `^\d{6,15}$` + pending_intent |
| `correccion` | Regex: `cambia X por Y`, `quita`, etc. + cotización activa |
| `confirmacion` | Regex: `sí`, `dale`, `confirmo` + cotización activa |
| `pedido_directo` | Producto específico (`_SPECIFIC_PRODUCTS`) + cantidad ó señal de precio |
| `asesoria` | Señal advisory/superficie SIN producto específico |
| `cotizacion` | Señal de precio sin contexto de producto nuevo |
| `general` | Fallback |

### 4.3 Formato exacto del contexto inyectado

**Ejemplo completo — intent `asesoria` con datos parciales:**
```
═══ CONTEXTO DEL TURNO ═══
Intención detectada: asesoria
Cliente: Juan Pérez (código 12345) — verificado ✅
Superficie detectada: fachada
Ubicación: exterior
Datos faltantes: condición (¿nuevo, pintado, con humedad, óxido?)
═══ INSTRUCCIÓN PARA ESTE TURNO ═══
Acción: Haz 1-2 preguntas conversacionales breves para completar el diagnóstico.
Todavía NO recomiendes productos ni llames herramientas de inventario.
═══════════════════════════

```

**Ejemplo — intent `pedido_directo` (empleado interno):**
```
═══ CONTEXTO DEL TURNO ═══
Intención detectada: pedido_directo
Empleado interno: PABLO MAFLA (administrador, sede Pereira)
═══ INSTRUCCIÓN PARA ESTE TURNO ═══
Empleado interno con producto específico. Directo a inventario, sin diagnóstico.
Acción: Llama consultar_inventario o consultar_inventario_lote con los productos.
Presenta cotización: producto + cant + precio unitario + subtotal. Al final: Subtotal + IVA 19% + Total.
═══════════════════════════
```

**Ejemplo — intent `confirmacion` con carrito:**
```
═══ CONTEXTO DEL TURNO ═══
Intención detectada: confirmacion
Cliente: María López (código 67890) — verificado ✅
Carrito activo: [2x KORAZA BLANCO GALON, 1x RODILLO FELPA 9"]
═══ INSTRUCCIÓN PARA ESTE TURNO ═══
El cliente aceptó la cotización.
Acción: Recopila datos faltantes (nombre, cédula si es pedido). Llama confirmar_pedido_y_generar_pdf.
NO repitas la cotización. Solo recoge lo que falta y cierra.
═══════════════════════════
```

### 4.4 Gestión del carrito (commercial_draft)

El carrito vive en `conversation_context["commercial_draft"]` — un dict persistido en la columna `contexto` (JSONB) de `agent_conversation`:

```python
commercial_draft = conversation_context.get("commercial_draft")
# Estructura esperada:
{
    "items": [
        {
            "referencia": "F51001501",
            "descripcion_comercial": "KORAZA BLANCO GALON 3.7L",
            "cantidad": 2,
            "precio_unitario": 89900,
            "unidad_medida": "galón"
        }
    ]
}
```

El contexto de turno muestra el carrito activo SOLO si no hay cambio de tema:
```python
if commercial_draft and not topic_changed:
    items_text = ", ".join(f"{it['cantidad']}x {it['descripcion_comercial']}" for it in items[:8])
    lines.append(f"Carrito activo: [{items_text}]")
```

Si hay cambio de tema (`detect_topic_change → True`):
```
⚡ CAMBIO DE TEMA: El cliente pregunta algo NUEVO. Ignora el pedido/cotización anterior.
```

### 4.5 Separación de intenciones: el sistema NUNCA mezcla

La separación ocurre en 3 capas:

1. **Python-side (agent_context.py):** `classify_intent()` produce UN intent. Las instrucciones del turno son específicas a ESE intent. No hay instrucciones para pedido si el intent es asesoría.

2. **Topic change detection:** Si el último bot message era cotización (tiene `$`) y el usuario viene con señales de tema nuevo → inyecta `⚡ CAMBIO DE TEMA`.

3. **Tool loop budget (agent_v3.py):** Máximo 6 iteraciones de tool calling, con dedup de RAG y budget por herramienta (`consultar_conocimiento_tecnico: max 2`, `buscar_documento_tecnico: max 2`).

---

## 5. Guardias de Seguridad Post-LLM (`agent_v3.py`)

Tres guardias que re-invocan al LLM si detectan violaciones en la respuesta generada:

| Guardia | Trigger | Acción |
|---------|---------|--------|
| **Química** | Respuesta contiene alquídico + poliuretano ó alquídico + epóxico | Inyecta `⛔ BLOQUEO QUÍMICO` + explicación. LLM regenera con tools. Max 3 retries. |
| **Bicomponente** | Respuesta menciona Interthane/Pintucoat/Interseal/Intergard SIN catalizador | Inyecta `⛔ BICOMPONENTE INCOMPLETO`. LLM busca catalizador. Max 3 retries. |
| **IVA** | Respuesta tiene ≥2 precios (`$`) sin desglose IVA 19% | Fuerza regeneración con `tool_choice="none"` para agregar Subtotal/IVA/Total. |

Las guardias se **saltan** si el mensaje es ENSEÑAR o saludo simple.

---

## 6. Diagrama de flujo completo del turno

```
User WhatsApp message
         ↓
    [main.py webhook]
         ↓
    generate_agent_reply_v3()
         ↓
    ┌─ build_turn_context() ──────────────────┐
    │  classify_intent() → intent             │
    │  extract_diagnostic_data() → diag       │
    │  detect_topic_change() → bool           │
    │  → ~15 líneas de contexto dinámico      │
    └─────────────────────────────────────────┘
         ↓
    Format AGENT_SYSTEM_PROMPT_V3 con:
      {contexto_turno}, {verificado}, {cliente_codigo},
      {nombre_cliente}, {borrador_activo}, {reclamo_activo},
      {empleado_activo}, {es_experto_autorizado}
         ↓
    messages = [system] + últimos 10 mensajes + user
         ↓
    ┌─ LLM CALL + TOOL LOOP (max 6 iters) ───┐
    │  OpenAI gpt-4o-mini, temperature=0.3    │
    │  tools=AGENT_TOOLS_V3, tool_choice=auto │
    │                                          │
    │  Per iteration:                          │
    │    tool_call → _execute_agent_tool()     │
    │    RAG dedup cache (_rag_cache)           │
    │    Per-tool budget enforcement            │
    │                                          │
    │  Si iters agotadas sin texto:            │
    │    → force tool_choice="none"            │
    └──────────────────────────────────────────┘
         ↓
    ┌─ GUARDIAS POST-LLM ────────────────────┐
    │  _guardia_quimica()                     │
    │  _guardia_bicomponente()                │
    │  _guardia_iva()                         │
    └─────────────────────────────────────────┘
         ↓
    Strip <thinking> tags
    Score confidence
    Detect farewell
         ↓
    Return {response_text, intent, tool_calls, context_updates, confidence}
```

---

## 7. Tablas PostgreSQL clave del agente

| Tabla | Propósito | Rows aprox |
|-------|-----------|------------|
| `agent_technical_doc_chunk` | RAG vectorial (fichas técnicas) | ~142,936 |
| `agent_expert_knowledge` | Conocimiento experto Pablo/Diego | 46 activos |
| `agent_precios` | Precios PVP (SAP + franquicia) | 21,665 |
| `agent_clientes` | Clientes (NIF, ciudad, segmento) | 45,230 |
| `mv_productos` | Materialized view inventario | ~19,708 |
| `agent_catalog_product` | Catálogo curado | ~1,700 |
| `agent_product_learning` | Aprendizaje de resolución producto | Variable |
| `agent_product_companion` | Relaciones complementarias | Variable |
| `mv_product_rotation` | Scoring rotación ventas | ~1,887 |
| `agent_conversation` | Conversaciones WhatsApp | Variable |
| `agent_message` | Mensajes (historial) | Variable |
| `agent_order` / `agent_order_line` | Pedidos estructurados | Variable |
| `agent_quote` / `agent_quote_line` | Cotizaciones estructuradas | Variable |

---

## 8. Limitaciones y deuda técnica identificada

1. **RAG sin metadata estructurada en chunks:** Los rendimientos, compatibilidades y tiempos de secado están como texto libre dentro de `chunk_text`. No hay extracción estructurada que permita consultas tipo "¿cuál es el rendimiento de Koraza?" sin depender del embedding similarity.

2. **Expert knowledge es substring matching:** `fetch_expert_knowledge()` usa ILIKE substring, no embeddings. Con 46 rows funciona, pero no escala para búsqueda semántica de reglas de negocio complejas.

3. **Precios International hardcoded:** Los precios de productos International/AkzoNobel vienen de un JSON estático (`_INTERNATIONAL_PRODUCTS_BY_CODE`), no de `agent_precios`. Cualquier cambio de precio requiere deploy.

4. **Sin re-ranking semántico post-retrieval:** El RAG hace cosine similarity puro contra pgvector sin re-ranking (e.g., cross-encoder). La segunda pasada portfolio-aware ayuda, pero no es un re-ranker real.

5. **El carrito es "soft":** `commercial_draft` vive en el JSONB de `contexto` en `agent_conversation`. No hay lock, no hay TTL. Si el LLM se confunde, puede sobreescribir ítems.

6. **Token pressure en tool responses:** Los responses de `consultar_inventario` incluyen clasificación, Abracol enrichment, bicomponente info, expert knowledge — todo junto. Para 10 productos, esto puede ser ~3K-5K tokens por tool response.

7. **Guardias post-LLM son costosas:** Cada guardia que se activa genera 1-4 llamadas LLM adicionales (con tools habilitados). Un turno con incompatibilidad química + bicomponente sin catalizador + sin IVA puede triplicar la latencia.

8. **No hay evaluación offline del RAG:** No hay pipeline automatizado para medir precision@k, recall@k o MRR del sistema de retrieval. Las auditorías son manuales con scripts ad-hoc.
